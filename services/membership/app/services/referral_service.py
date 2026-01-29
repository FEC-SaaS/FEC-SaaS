"""
=============================================================================
FILE: services/referral_service.py
PURPOSE: Referral rewards management service
=============================================================================
"""

import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ReferralReward,
    CustomerLoyaltyAccount,
    LoyaltyTransaction,
    ReferralStatus,
    LoyaltyTransactionType,
)
from app.schemas.membership import GenerateReferralRequest
from app.config import settings


class ReferralService:
    """Service for managing referral rewards."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # REFERRAL CODES
    # =========================================================================

    async def create_referral_code(
        self,
        referrer_id: UUID,
        venue_id: UUID,
        referrer_reward_points: Optional[int] = None,
        referred_reward_points: Optional[int] = None,
        expires_in_days: int = 90,
    ) -> ReferralReward:
        """Create a new referral code for a customer."""
        # Check if customer already has an active referral code
        existing = await self.get_active_referral_code(referrer_id, venue_id)
        if existing:
            return existing

        # Generate unique code
        code = self._generate_referral_code()

        referral = ReferralReward(
            venue_id=venue_id,
            referrer_id=referrer_id,
            referral_code=code,
            referrer_reward_points=referrer_reward_points
            or settings.max_referral_bonus_points,
            referred_reward_points=referred_reward_points
            or (settings.max_referral_bonus_points // 2),
            status=ReferralStatus.ACTIVE,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days),
        )
        self.db.add(referral)
        await self.db.commit()
        await self.db.refresh(referral)
        return referral

    async def get_referral(self, referral_id: UUID) -> Optional[ReferralReward]:
        """Get a referral by ID."""
        result = await self.db.execute(
            select(ReferralReward).where(ReferralReward.id == referral_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Optional[ReferralReward]:
        """Get a referral by code."""
        result = await self.db.execute(
            select(ReferralReward).where(ReferralReward.referral_code == code)
        )
        return result.scalar_one_or_none()

    async def get_active_referral_code(
        self, referrer_id: UUID, venue_id: UUID
    ) -> Optional[ReferralReward]:
        """Get active referral code for a customer."""
        result = await self.db.execute(
            select(ReferralReward).where(
                and_(
                    ReferralReward.referrer_id == referrer_id,
                    ReferralReward.venue_id == venue_id,
                    ReferralReward.status == ReferralStatus.ACTIVE,
                    or_(
                        ReferralReward.expires_at.is_(None),
                        ReferralReward.expires_at > datetime.utcnow(),
                    ),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_customer_referrals(
        self,
        referrer_id: UUID,
        status: Optional[ReferralStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ReferralReward]:
        """Get all referrals made by a customer."""
        query = select(ReferralReward).where(
            ReferralReward.referrer_id == referrer_id
        )
        if status:
            query = query.where(ReferralReward.status == status)
        query = query.order_by(ReferralReward.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # =========================================================================
    # REFERRAL REDEMPTION
    # =========================================================================

    async def use_referral_code(
        self,
        code: str,
        referred_id: UUID,
    ) -> Dict[str, Any]:
        """Use a referral code (new customer signing up)."""
        referral = await self.get_by_code(code)
        if not referral:
            raise ValueError("Invalid referral code")

        # Validate referral
        if referral.status != ReferralStatus.ACTIVE:
            raise ValueError("Referral code is no longer active")

        if referral.expires_at and referral.expires_at < datetime.utcnow():
            raise ValueError("Referral code has expired")

        if referral.referrer_id == referred_id:
            raise ValueError("Cannot use your own referral code")

        # Check if referred customer already used a code
        existing_referred = await self._has_been_referred(referred_id)
        if existing_referred:
            raise ValueError("You have already used a referral code")

        # Update referral with referred customer
        referral.referred_id = referred_id
        referral.status = ReferralStatus.PENDING
        referral.referred_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(referral)

        return {
            "referral_id": referral.id,
            "referrer_id": referral.referrer_id,
            "referred_reward_points": referral.referred_reward_points,
            "status": "pending",
            "message": "Referral recorded. Rewards will be issued after qualifying action.",
        }

    async def complete_referral(
        self,
        referral_id: UUID,
        qualifying_action: str = "subscription",
    ) -> Dict[str, Any]:
        """Complete a referral and issue rewards."""
        referral = await self.get_referral(referral_id)
        if not referral:
            raise ValueError("Referral not found")

        if referral.status != ReferralStatus.PENDING:
            raise ValueError("Referral is not in pending status")

        # Issue rewards to both parties
        rewards_issued = {
            "referrer": None,
            "referred": None,
        }

        # Get or create loyalty accounts for both users
        # Issue referrer reward
        if referral.referrer_reward_points > 0:
            referrer_account = await self._get_or_create_loyalty_account(
                referral.referrer_id, referral.venue_id
            )
            if referrer_account:
                referrer_txn = LoyaltyTransaction(
                    account_id=referrer_account.id,
                    transaction_type=LoyaltyTransactionType.REFERRAL,
                    points=referral.referrer_reward_points,
                    reference_type="referral",
                    reference_id=str(referral.id),
                    description=f"Referral reward for inviting a friend",
                )
                self.db.add(referrer_txn)
                referrer_account.points_balance += referral.referrer_reward_points
                referrer_account.lifetime_points += referral.referrer_reward_points
                rewards_issued["referrer"] = {
                    "account_id": referrer_account.id,
                    "points": referral.referrer_reward_points,
                }

        # Issue referred reward
        if referral.referred_id and referral.referred_reward_points > 0:
            referred_account = await self._get_or_create_loyalty_account(
                referral.referred_id, referral.venue_id
            )
            if referred_account:
                referred_txn = LoyaltyTransaction(
                    account_id=referred_account.id,
                    transaction_type=LoyaltyTransactionType.REFERRAL,
                    points=referral.referred_reward_points,
                    reference_type="referral",
                    reference_id=str(referral.id),
                    description=f"Welcome bonus from referral",
                )
                self.db.add(referred_txn)
                referred_account.points_balance += referral.referred_reward_points
                referred_account.lifetime_points += referral.referred_reward_points
                rewards_issued["referred"] = {
                    "account_id": referred_account.id,
                    "points": referral.referred_reward_points,
                }

        # Update referral status
        referral.status = ReferralStatus.COMPLETED
        referral.completed_at = datetime.utcnow()
        referral.qualifying_action = qualifying_action

        await self.db.commit()

        return {
            "referral_id": referral.id,
            "status": "completed",
            "rewards_issued": rewards_issued,
        }

    async def expire_referral(self, referral_id: UUID) -> bool:
        """Expire a referral that was not completed."""
        referral = await self.get_referral(referral_id)
        if not referral:
            return False

        if referral.status in [ReferralStatus.COMPLETED, ReferralStatus.EXPIRED]:
            return False

        referral.status = ReferralStatus.EXPIRED
        await self.db.commit()
        return True

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    async def get_referral_stats(
        self, referrer_id: UUID, venue_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get referral statistics for a customer."""
        query = select(ReferralReward).where(
            ReferralReward.referrer_id == referrer_id
        )
        if venue_id:
            query = query.where(ReferralReward.venue_id == venue_id)

        result = await self.db.execute(query)
        referrals = list(result.scalars().all())

        total_referrals = len(referrals)
        completed = len([r for r in referrals if r.status == ReferralStatus.COMPLETED])
        pending = len([r for r in referrals if r.status == ReferralStatus.PENDING])
        expired = len([r for r in referrals if r.status == ReferralStatus.EXPIRED])
        active_codes = len([r for r in referrals if r.status == ReferralStatus.ACTIVE])

        total_points_earned = sum(
            r.referrer_reward_points for r in referrals
            if r.status == ReferralStatus.COMPLETED
        )

        return {
            "total_referrals": total_referrals,
            "completed": completed,
            "pending": pending,
            "expired": expired,
            "active_codes": active_codes,
            "total_points_earned": total_points_earned,
            "conversion_rate": (
                (completed / total_referrals) * 100
                if total_referrals > 0
                else 0
            ),
        }

    async def get_venue_referral_stats(
        self, venue_id: UUID
    ) -> Dict[str, Any]:
        """Get referral statistics for a venue."""
        result = await self.db.execute(
            select(ReferralReward).where(ReferralReward.venue_id == venue_id)
        )
        referrals = list(result.scalars().all())

        total = len(referrals)
        completed = len([r for r in referrals if r.status == ReferralStatus.COMPLETED])
        pending = len([r for r in referrals if r.status == ReferralStatus.PENDING])

        total_referrer_points = sum(
            r.referrer_reward_points for r in referrals
            if r.status == ReferralStatus.COMPLETED
        )
        total_referred_points = sum(
            r.referred_reward_points for r in referrals
            if r.status == ReferralStatus.COMPLETED
        )

        # Get top referrers
        referrer_counts: Dict[UUID, int] = {}
        for r in referrals:
            if r.status == ReferralStatus.COMPLETED:
                referrer_counts[r.referrer_id] = (
                    referrer_counts.get(r.referrer_id, 0) + 1
                )

        top_referrers = sorted(
            referrer_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return {
            "total_referrals": total,
            "completed": completed,
            "pending": pending,
            "conversion_rate": (completed / total) * 100 if total > 0 else 0,
            "total_referrer_points_issued": total_referrer_points,
            "total_referred_points_issued": total_referred_points,
            "top_referrers": [
                {"customer_id": str(cid), "referral_count": count}
                for cid, count in top_referrers
            ],
        }

    async def get_leaderboard(
        self,
        venue_id: UUID,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get referral leaderboard for a venue."""
        result = await self.db.execute(
            select(
                ReferralReward.referrer_id,
                func.count(ReferralReward.id).label("referral_count"),
                func.sum(ReferralReward.referrer_reward_points).label("total_points"),
            )
            .where(
                and_(
                    ReferralReward.venue_id == venue_id,
                    ReferralReward.status == ReferralStatus.COMPLETED,
                )
            )
            .group_by(ReferralReward.referrer_id)
            .order_by(func.count(ReferralReward.id).desc())
            .limit(limit)
        )

        leaderboard = []
        for row in result:
            leaderboard.append({
                "rank": len(leaderboard) + 1,
                "customer_id": str(row.referrer_id),
                "referral_count": row.referral_count,
                "total_points_earned": row.total_points or 0,
            })

        return leaderboard

    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================

    async def expire_old_referrals(self) -> int:
        """Expire all referrals past their expiry date."""
        now = datetime.utcnow()
        result = await self.db.execute(
            select(ReferralReward).where(
                and_(
                    ReferralReward.status.in_([
                        ReferralStatus.ACTIVE,
                        ReferralStatus.PENDING,
                    ]),
                    ReferralReward.expires_at <= now,
                )
            )
        )
        expired_referrals = list(result.scalars().all())

        for referral in expired_referrals:
            referral.status = ReferralStatus.EXPIRED

        await self.db.commit()
        return len(expired_referrals)

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _generate_referral_code(self, length: int = 8) -> str:
        """Generate a unique referral code."""
        alphabet = string.ascii_uppercase + string.digits
        return "REF-" + "".join(secrets.choice(alphabet) for _ in range(length))

    async def _has_been_referred(self, customer_id: UUID) -> bool:
        """Check if a customer has already been referred."""
        result = await self.db.execute(
            select(ReferralReward).where(
                and_(
                    ReferralReward.referred_id == customer_id,
                    ReferralReward.status.in_([
                        ReferralStatus.PENDING,
                        ReferralStatus.COMPLETED,
                    ]),
                )
            )
        )
        return result.scalar_one_or_none() is not None

    async def _get_or_create_loyalty_account(
        self, customer_id: UUID, venue_id: UUID
    ) -> Optional[CustomerLoyaltyAccount]:
        """Get or create a loyalty account for referral rewards."""
        # Find loyalty program for venue
        from app.models import LoyaltyProgram

        result = await self.db.execute(
            select(LoyaltyProgram).where(
                and_(
                    LoyaltyProgram.venue_id == venue_id,
                    LoyaltyProgram.is_active == True,
                )
            )
        )
        program = result.scalar_one_or_none()
        if not program:
            return None

        # Get or create account
        result = await self.db.execute(
            select(CustomerLoyaltyAccount).where(
                and_(
                    CustomerLoyaltyAccount.customer_id == customer_id,
                    CustomerLoyaltyAccount.program_id == program.id,
                )
            )
        )
        account = result.scalar_one_or_none()

        if not account:
            account = CustomerLoyaltyAccount(
                customer_id=customer_id,
                program_id=program.id,
                points_balance=0,
                lifetime_points=0,
            )
            self.db.add(account)
            await self.db.flush()

        return account
