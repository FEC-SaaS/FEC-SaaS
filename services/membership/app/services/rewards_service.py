"""
=============================================================================
FILE: services/rewards_service.py
PURPOSE: Rewards catalog and redemption management service
=============================================================================
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    RewardsCatalog,
    RewardRedemption,
    CustomerLoyaltyAccount,
    RewardType,
    RedemptionStatus,
)
from app.schemas.membership import (
    RewardCreate,
    RewardUpdate,
    RedeemRewardRequest,
)


class RewardsService:
    """Service for managing rewards catalog and redemptions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # REWARDS CATALOG
    # =========================================================================

    async def create_reward(
        self, venue_id: UUID, reward_data: RewardCreate
    ) -> RewardsCatalog:
        """Create a new reward in the catalog."""
        reward = RewardsCatalog(
            venue_id=venue_id,
            name=reward_data.name,
            description=reward_data.description,
            reward_type=reward_data.reward_type,
            points_required=reward_data.points_required,
            monetary_value=reward_data.monetary_value,
            discount_percent=reward_data.discount_percent,
            quantity_available=reward_data.quantity_available,
            max_redemptions_per_customer=reward_data.max_redemptions_per_customer,
            valid_from=reward_data.valid_from or datetime.utcnow(),
            valid_until=reward_data.valid_until,
            terms_conditions=reward_data.terms_conditions,
            image_url=reward_data.image_url,
            tier_restrictions=reward_data.tier_restrictions or [],
            is_active=True,
        )
        self.db.add(reward)
        await self.db.commit()
        await self.db.refresh(reward)
        return reward

    async def get_reward(self, reward_id: UUID) -> Optional[RewardsCatalog]:
        """Get a reward by ID."""
        result = await self.db.execute(
            select(RewardsCatalog).where(RewardsCatalog.id == reward_id)
        )
        return result.scalar_one_or_none()

    async def list_rewards(
        self,
        venue_id: UUID,
        reward_type: Optional[RewardType] = None,
        tier_id: Optional[UUID] = None,
        active_only: bool = True,
        available_only: bool = True,
    ) -> List[RewardsCatalog]:
        """List rewards in the catalog."""
        query = select(RewardsCatalog).where(
            RewardsCatalog.venue_id == venue_id
        )

        if reward_type:
            query = query.where(RewardsCatalog.reward_type == reward_type)

        if active_only:
            query = query.where(RewardsCatalog.is_active == True)
            now = datetime.utcnow()
            query = query.where(
                and_(
                    RewardsCatalog.valid_from <= now,
                    or_(
                        RewardsCatalog.valid_until.is_(None),
                        RewardsCatalog.valid_until >= now,
                    ),
                )
            )

        if available_only:
            query = query.where(
                or_(
                    RewardsCatalog.quantity_available.is_(None),
                    RewardsCatalog.quantity_available > 0,
                )
            )

        query = query.order_by(RewardsCatalog.points_required)

        result = await self.db.execute(query)
        rewards = list(result.scalars().all())

        # Filter by tier if specified
        if tier_id:
            rewards = [
                r for r in rewards
                if not r.tier_restrictions
                or str(tier_id) in [str(t) for t in r.tier_restrictions]
            ]

        return rewards

    async def update_reward(
        self, reward_id: UUID, reward_data: RewardUpdate
    ) -> Optional[RewardsCatalog]:
        """Update a reward."""
        reward = await self.get_reward(reward_id)
        if not reward:
            return None

        update_data = reward_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(reward, field, value)

        await self.db.commit()
        await self.db.refresh(reward)
        return reward

    async def deactivate_reward(self, reward_id: UUID) -> bool:
        """Deactivate a reward."""
        reward = await self.get_reward(reward_id)
        if not reward:
            return False
        reward.is_active = False
        await self.db.commit()
        return True

    async def get_available_rewards_for_customer(
        self,
        venue_id: UUID,
        customer_id: UUID,
        account_id: UUID,
    ) -> List[Dict[str, Any]]:
        """Get rewards available for a specific customer based on points and tier."""
        # Get customer's loyalty account
        result = await self.db.execute(
            select(CustomerLoyaltyAccount)
            .where(CustomerLoyaltyAccount.id == account_id)
            .options(selectinload(CustomerLoyaltyAccount.tier))
        )
        account = result.scalar_one_or_none()
        if not account:
            return []

        # Get all active rewards
        rewards = await self.list_rewards(
            venue_id=venue_id,
            tier_id=account.tier_id,
            active_only=True,
            available_only=True,
        )

        # Check redemption limits
        available_rewards = []
        for reward in rewards:
            can_redeem, reason = await self._can_redeem(
                account, reward, customer_id
            )
            available_rewards.append({
                "reward": reward,
                "can_redeem": can_redeem,
                "reason": reason if not can_redeem else None,
                "points_needed": max(
                    0, reward.points_required - account.points_balance
                ),
            })

        return available_rewards

    # =========================================================================
    # REDEMPTIONS
    # =========================================================================

    async def redeem_reward(
        self,
        customer_id: UUID,
        account_id: UUID,
        request: RedeemRewardRequest,
    ) -> RewardRedemption:
        """Redeem a reward."""
        # Get account and reward
        result = await self.db.execute(
            select(CustomerLoyaltyAccount).where(
                CustomerLoyaltyAccount.id == account_id
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            raise ValueError("Loyalty account not found")

        reward = await self.get_reward(request.reward_id)
        if not reward:
            raise ValueError("Reward not found")

        # Check if can redeem
        can_redeem, reason = await self._can_redeem(account, reward, customer_id)
        if not can_redeem:
            raise ValueError(reason)

        # Calculate points and value
        quantity = request.quantity or 1
        total_points = reward.points_required * quantity
        total_value = None
        if reward.monetary_value:
            total_value = reward.monetary_value * quantity

        # Generate redemption code
        redemption_code = self._generate_redemption_code()

        # Create redemption record
        redemption = RewardRedemption(
            customer_id=customer_id,
            reward_id=reward.id,
            quantity=quantity,
            points_spent=total_points,
            monetary_value=total_value,
            status=RedemptionStatus.PENDING,
            redemption_code=redemption_code,
            expires_at=datetime.utcnow() + timedelta(days=30),  # 30 day expiry
        )
        self.db.add(redemption)

        # Deduct points
        account.points_balance -= total_points

        # Update reward quantity
        if reward.quantity_available is not None:
            reward.quantity_available -= quantity

        await self.db.commit()
        await self.db.refresh(redemption)
        return redemption

    async def get_redemption(
        self, redemption_id: UUID
    ) -> Optional[RewardRedemption]:
        """Get a redemption by ID."""
        result = await self.db.execute(
            select(RewardRedemption)
            .where(RewardRedemption.id == redemption_id)
            .options(selectinload(RewardRedemption.reward))
        )
        return result.scalar_one_or_none()

    async def get_redemption_by_code(
        self, redemption_code: str
    ) -> Optional[RewardRedemption]:
        """Get a redemption by code."""
        result = await self.db.execute(
            select(RewardRedemption)
            .where(RewardRedemption.redemption_code == redemption_code)
            .options(selectinload(RewardRedemption.reward))
        )
        return result.scalar_one_or_none()

    async def get_customer_redemptions(
        self,
        customer_id: UUID,
        status: Optional[RedemptionStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RewardRedemption]:
        """Get redemptions for a customer."""
        query = select(RewardRedemption).where(
            RewardRedemption.customer_id == customer_id
        )
        if status:
            query = query.where(RewardRedemption.status == status)
        query = query.order_by(RewardRedemption.created_at.desc())
        query = query.offset(offset).limit(limit)
        query = query.options(selectinload(RewardRedemption.reward))

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def fulfill_redemption(
        self,
        redemption_id: UUID,
        fulfilled_by: Optional[UUID] = None,
        notes: Optional[str] = None,
    ) -> Optional[RewardRedemption]:
        """Mark a redemption as fulfilled."""
        redemption = await self.get_redemption(redemption_id)
        if not redemption:
            return None

        if redemption.status != RedemptionStatus.PENDING:
            raise ValueError("Can only fulfill pending redemptions")

        redemption.status = RedemptionStatus.FULFILLED
        redemption.fulfilled_at = datetime.utcnow()
        redemption.fulfilled_by = fulfilled_by

        await self.db.commit()
        await self.db.refresh(redemption)
        return redemption

    async def cancel_redemption(
        self,
        redemption_id: UUID,
        reason: Optional[str] = None,
        refund_points: bool = True,
    ) -> Optional[RewardRedemption]:
        """Cancel a redemption."""
        redemption = await self.get_redemption(redemption_id)
        if not redemption:
            return None

        if redemption.status not in [
            RedemptionStatus.PENDING,
            RedemptionStatus.FULFILLED,
        ]:
            raise ValueError("Cannot cancel this redemption")

        redemption.status = RedemptionStatus.CANCELLED

        if refund_points:
            # Refund points to customer
            result = await self.db.execute(
                select(CustomerLoyaltyAccount).where(
                    and_(
                        CustomerLoyaltyAccount.customer_id == redemption.customer_id,
                        CustomerLoyaltyAccount.program_id.in_(
                            select(RewardsCatalog.venue_id).where(
                                RewardsCatalog.id == redemption.reward_id
                            )
                        ),
                    )
                )
            )
            account = result.scalar_one_or_none()
            if account:
                account.points_balance += redemption.points_spent

            # Restore reward quantity
            reward = await self.get_reward(redemption.reward_id)
            if reward and reward.quantity_available is not None:
                reward.quantity_available += redemption.quantity

        await self.db.commit()
        await self.db.refresh(redemption)
        return redemption

    async def expire_redemptions(self) -> int:
        """Expire pending redemptions past their expiry date."""
        now = datetime.utcnow()
        result = await self.db.execute(
            select(RewardRedemption).where(
                and_(
                    RewardRedemption.status == RedemptionStatus.PENDING,
                    RewardRedemption.expires_at <= now,
                )
            )
        )
        expired_redemptions = list(result.scalars().all())

        for redemption in expired_redemptions:
            redemption.status = RedemptionStatus.EXPIRED

        await self.db.commit()
        return len(expired_redemptions)

    # =========================================================================
    # HELPERS
    # =========================================================================

    async def _can_redeem(
        self,
        account: CustomerLoyaltyAccount,
        reward: RewardsCatalog,
        customer_id: UUID,
    ) -> tuple[bool, str]:
        """Check if a customer can redeem a reward."""
        # Check points balance
        if account.points_balance < reward.points_required:
            return False, "Insufficient points"

        # Check if reward is active
        if not reward.is_active:
            return False, "Reward is not active"

        # Check validity dates
        now = datetime.utcnow()
        if reward.valid_from and reward.valid_from > now:
            return False, "Reward is not yet available"
        if reward.valid_until and reward.valid_until < now:
            return False, "Reward has expired"

        # Check quantity
        if reward.quantity_available is not None and reward.quantity_available <= 0:
            return False, "Reward is out of stock"

        # Check tier restrictions
        if reward.tier_restrictions:
            if not account.tier_id:
                return False, "Tier membership required"
            if str(account.tier_id) not in [
                str(t) for t in reward.tier_restrictions
            ]:
                return False, "Your tier does not qualify for this reward"

        # Check max redemptions per customer
        if reward.max_redemptions_per_customer:
            result = await self.db.execute(
                select(func.count(RewardRedemption.id)).where(
                    and_(
                        RewardRedemption.customer_id == customer_id,
                        RewardRedemption.reward_id == reward.id,
                        RewardRedemption.status.in_([
                            RedemptionStatus.PENDING,
                            RedemptionStatus.FULFILLED,
                        ]),
                    )
                )
            )
            count = result.scalar() or 0
            if count >= reward.max_redemptions_per_customer:
                return False, "Maximum redemptions reached for this reward"

        return True, ""

    def _generate_redemption_code(self) -> str:
        """Generate a unique redemption code."""
        import secrets
        import string
        alphabet = string.ascii_uppercase + string.digits
        return "RWD-" + "".join(secrets.choice(alphabet) for _ in range(8))
