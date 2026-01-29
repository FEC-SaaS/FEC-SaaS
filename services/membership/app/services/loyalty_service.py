"""
=============================================================================
FILE: services/loyalty_service.py
PURPOSE: Loyalty points program management service
=============================================================================
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    LoyaltyProgram,
    CustomerLoyaltyAccount,
    LoyaltyTransaction,
    MembershipTier,
    LoyaltyTransactionType,
)
from app.schemas.membership import (
    LoyaltyProgramCreate,
    LoyaltyProgramUpdate,
    EarnPointsRequest,
    RedeemPointsRequest,
)
from app.config import settings


class LoyaltyService:
    """Service for managing loyalty points programs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # LOYALTY PROGRAMS
    # =========================================================================

    async def create_program(
        self, venue_id: UUID, program_data: LoyaltyProgramCreate
    ) -> LoyaltyProgram:
        """Create a new loyalty program for a venue."""
        program = LoyaltyProgram(
            venue_id=venue_id,
            name=program_data.name,
            description=program_data.description,
            points_per_dollar=program_data.points_per_dollar
            or settings.default_points_per_dollar,
            points_expiry_days=program_data.points_expiry_days
            or settings.default_points_expiry_days,
            tier_multipliers=program_data.tier_multipliers or {},
            bonus_rules=program_data.bonus_rules or {},
            is_active=True,
        )
        self.db.add(program)
        await self.db.commit()
        await self.db.refresh(program)
        return program

    async def get_program(self, program_id: UUID) -> Optional[LoyaltyProgram]:
        """Get a loyalty program by ID."""
        result = await self.db.execute(
            select(LoyaltyProgram).where(LoyaltyProgram.id == program_id)
        )
        return result.scalar_one_or_none()

    async def get_venue_program(
        self, venue_id: UUID
    ) -> Optional[LoyaltyProgram]:
        """Get the active loyalty program for a venue."""
        result = await self.db.execute(
            select(LoyaltyProgram).where(
                and_(
                    LoyaltyProgram.venue_id == venue_id,
                    LoyaltyProgram.is_active == True,
                )
            )
        )
        return result.scalar_one_or_none()

    async def update_program(
        self, program_id: UUID, program_data: LoyaltyProgramUpdate
    ) -> Optional[LoyaltyProgram]:
        """Update a loyalty program."""
        program = await self.get_program(program_id)
        if not program:
            return None

        update_data = program_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(program, field, value)

        await self.db.commit()
        await self.db.refresh(program)
        return program

    async def deactivate_program(self, program_id: UUID) -> bool:
        """Deactivate a loyalty program."""
        program = await self.get_program(program_id)
        if not program:
            return False
        program.is_active = False
        await self.db.commit()
        return True

    # =========================================================================
    # CUSTOMER LOYALTY ACCOUNTS
    # =========================================================================

    async def get_or_create_account(
        self,
        customer_id: UUID,
        program_id: UUID,
        tier_id: Optional[UUID] = None,
    ) -> CustomerLoyaltyAccount:
        """Get or create a customer loyalty account."""
        result = await self.db.execute(
            select(CustomerLoyaltyAccount).where(
                and_(
                    CustomerLoyaltyAccount.customer_id == customer_id,
                    CustomerLoyaltyAccount.program_id == program_id,
                )
            )
        )
        account = result.scalar_one_or_none()

        if not account:
            account = CustomerLoyaltyAccount(
                customer_id=customer_id,
                program_id=program_id,
                tier_id=tier_id,
                points_balance=0,
                lifetime_points=0,
                points_expiring_soon=0,
            )
            self.db.add(account)
            await self.db.commit()
            await self.db.refresh(account)

        return account

    async def get_account(
        self, account_id: UUID
    ) -> Optional[CustomerLoyaltyAccount]:
        """Get a loyalty account by ID."""
        result = await self.db.execute(
            select(CustomerLoyaltyAccount)
            .where(CustomerLoyaltyAccount.id == account_id)
            .options(
                selectinload(CustomerLoyaltyAccount.tier),
                selectinload(CustomerLoyaltyAccount.program),
            )
        )
        return result.scalar_one_or_none()

    async def get_customer_account(
        self, customer_id: UUID, program_id: UUID
    ) -> Optional[CustomerLoyaltyAccount]:
        """Get a customer's loyalty account for a specific program."""
        result = await self.db.execute(
            select(CustomerLoyaltyAccount)
            .where(
                and_(
                    CustomerLoyaltyAccount.customer_id == customer_id,
                    CustomerLoyaltyAccount.program_id == program_id,
                )
            )
            .options(
                selectinload(CustomerLoyaltyAccount.tier),
                selectinload(CustomerLoyaltyAccount.program),
            )
        )
        return result.scalar_one_or_none()

    async def get_customer_accounts(
        self, customer_id: UUID
    ) -> List[CustomerLoyaltyAccount]:
        """Get all loyalty accounts for a customer."""
        result = await self.db.execute(
            select(CustomerLoyaltyAccount)
            .where(CustomerLoyaltyAccount.customer_id == customer_id)
            .options(
                selectinload(CustomerLoyaltyAccount.tier),
                selectinload(CustomerLoyaltyAccount.program),
            )
        )
        return list(result.scalars().all())

    # =========================================================================
    # POINTS TRANSACTIONS
    # =========================================================================

    async def earn_points(
        self,
        account_id: UUID,
        request: EarnPointsRequest,
    ) -> LoyaltyTransaction:
        """Award points to a customer's loyalty account."""
        account = await self.get_account(account_id)
        if not account:
            raise ValueError("Loyalty account not found")

        program = await self.get_program(account.program_id)
        if not program or not program.is_active:
            raise ValueError("Loyalty program is not active")

        # Calculate points with multipliers
        base_points = request.points
        if request.transaction_amount:
            base_points = int(
                request.transaction_amount * Decimal(program.points_per_dollar)
            )

        # Apply tier multiplier if applicable
        multiplier = Decimal("1.0")
        if account.tier_id and program.tier_multipliers:
            tier_key = str(account.tier_id)
            multiplier = Decimal(
                str(program.tier_multipliers.get(tier_key, "1.0"))
            )

        # Apply bonus rules
        bonus_points = self._calculate_bonus_points(
            base_points, program.bonus_rules, request.metadata or {}
        )

        final_points = int(base_points * multiplier) + bonus_points

        # Calculate expiry date
        expires_at = None
        if program.points_expiry_days:
            expires_at = datetime.utcnow() + timedelta(
                days=program.points_expiry_days
            )

        # Create transaction
        transaction = LoyaltyTransaction(
            account_id=account.id,
            transaction_type=LoyaltyTransactionType.EARNED,
            points=final_points,
            reference_type=request.reference_type,
            reference_id=request.reference_id,
            description=request.description or "Points earned",
            expires_at=expires_at,
            extra_metadata={
                "base_points": base_points,
                "multiplier": str(multiplier),
                "bonus_points": bonus_points,
                **(request.metadata or {}),
            },
        )
        self.db.add(transaction)

        # Update account balance
        account.points_balance += final_points
        account.lifetime_points += final_points

        # Check for tier upgrade
        await self._check_tier_upgrade(account)

        await self.db.commit()
        await self.db.refresh(transaction)
        return transaction

    async def redeem_points(
        self,
        account_id: UUID,
        request: RedeemPointsRequest,
    ) -> LoyaltyTransaction:
        """Redeem points from a customer's loyalty account."""
        account = await self.get_account(account_id)
        if not account:
            raise ValueError("Loyalty account not found")

        if account.points_balance < request.points:
            raise ValueError("Insufficient points balance")

        # Create redemption transaction
        transaction = LoyaltyTransaction(
            account_id=account.id,
            transaction_type=LoyaltyTransactionType.REDEEMED,
            points=-request.points,
            reference_type=request.reference_type,
            reference_id=request.reference_id,
            description=request.description or "Points redeemed",
            extra_metadata=request.metadata or {},
        )
        self.db.add(transaction)

        # Update account balance
        account.points_balance -= request.points

        await self.db.commit()
        await self.db.refresh(transaction)
        return transaction

    async def adjust_points(
        self,
        account_id: UUID,
        points: int,
        reason: str,
        admin_id: Optional[UUID] = None,
    ) -> LoyaltyTransaction:
        """Manually adjust points (admin action)."""
        account = await self.get_account(account_id)
        if not account:
            raise ValueError("Loyalty account not found")

        transaction_type = (
            LoyaltyTransactionType.ADJUSTED
            if points > 0
            else LoyaltyTransactionType.EXPIRED
        )

        transaction = LoyaltyTransaction(
            account_id=account.id,
            transaction_type=transaction_type,
            points=points,
            description=reason,
            extra_metadata={"admin_id": str(admin_id)} if admin_id else {},
        )
        self.db.add(transaction)

        account.points_balance += points
        if points > 0:
            account.lifetime_points += points

        await self.db.commit()
        await self.db.refresh(transaction)
        return transaction

    async def transfer_points(
        self,
        from_account_id: UUID,
        to_account_id: UUID,
        points: int,
        reason: Optional[str] = None,
    ) -> tuple[LoyaltyTransaction, LoyaltyTransaction]:
        """Transfer points between accounts."""
        from_account = await self.get_account(from_account_id)
        to_account = await self.get_account(to_account_id)

        if not from_account or not to_account:
            raise ValueError("One or both accounts not found")

        if from_account.points_balance < points:
            raise ValueError("Insufficient points for transfer")

        # Create debit transaction
        debit_txn = LoyaltyTransaction(
            account_id=from_account.id,
            transaction_type=LoyaltyTransactionType.TRANSFERRED,
            points=-points,
            description=reason or f"Transfer to account {to_account_id}",
            extra_metadata={"to_account_id": str(to_account_id)},
        )
        self.db.add(debit_txn)

        # Create credit transaction
        credit_txn = LoyaltyTransaction(
            account_id=to_account.id,
            transaction_type=LoyaltyTransactionType.BONUS,
            points=points,
            description=reason or f"Transfer from account {from_account_id}",
            extra_metadata={"from_account_id": str(from_account_id)},
        )
        self.db.add(credit_txn)

        # Update balances
        from_account.points_balance -= points
        to_account.points_balance += points
        to_account.lifetime_points += points

        await self.db.commit()
        await self.db.refresh(debit_txn)
        await self.db.refresh(credit_txn)
        return debit_txn, credit_txn

    async def get_transaction_history(
        self,
        account_id: UUID,
        limit: int = 50,
        offset: int = 0,
        transaction_type: Optional[LoyaltyTransactionType] = None,
    ) -> List[LoyaltyTransaction]:
        """Get transaction history for an account."""
        query = select(LoyaltyTransaction).where(
            LoyaltyTransaction.account_id == account_id
        )
        if transaction_type:
            query = query.where(
                LoyaltyTransaction.transaction_type == transaction_type
            )
        query = query.order_by(LoyaltyTransaction.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # =========================================================================
    # POINTS EXPIRATION
    # =========================================================================

    async def process_expiring_points(self) -> int:
        """Process and expire points that have reached expiry date."""
        now = datetime.utcnow()

        # Find all earned transactions with expiry dates that have passed
        result = await self.db.execute(
            select(LoyaltyTransaction).where(
                and_(
                    LoyaltyTransaction.transaction_type
                    == LoyaltyTransactionType.EARNED,
                    LoyaltyTransaction.expires_at <= now,
                    LoyaltyTransaction.expires_at.isnot(None),
                )
            )
        )
        expiring_transactions = list(result.scalars().all())

        expired_count = 0
        for txn in expiring_transactions:
            account = await self.get_account(txn.account_id)
            if account and account.points_balance >= txn.points:
                # Create expiration transaction
                expire_txn = LoyaltyTransaction(
                    account_id=account.id,
                    transaction_type=LoyaltyTransactionType.EXPIRED,
                    points=-txn.points,
                    description="Points expired",
                    extra_metadata={"original_transaction_id": str(txn.id)},
                )
                self.db.add(expire_txn)
                account.points_balance -= txn.points

                # Mark original transaction as processed
                txn.expires_at = None  # Prevent reprocessing
                expired_count += 1

        await self.db.commit()
        return expired_count

    async def get_expiring_soon(
        self, account_id: UUID, days: int = 30
    ) -> Dict[str, Any]:
        """Get points expiring soon for an account."""
        cutoff = datetime.utcnow() + timedelta(days=days)

        result = await self.db.execute(
            select(func.sum(LoyaltyTransaction.points)).where(
                and_(
                    LoyaltyTransaction.account_id == account_id,
                    LoyaltyTransaction.transaction_type
                    == LoyaltyTransactionType.EARNED,
                    LoyaltyTransaction.expires_at <= cutoff,
                    LoyaltyTransaction.expires_at > datetime.utcnow(),
                )
            )
        )
        expiring_points = result.scalar() or 0

        # Update account
        account = await self.get_account(account_id)
        if account:
            account.points_expiring_soon = expiring_points
            await self.db.commit()

        return {
            "points_expiring": expiring_points,
            "expires_within_days": days,
            "expiry_date": cutoff,
        }

    # =========================================================================
    # TIER MANAGEMENT
    # =========================================================================

    async def _check_tier_upgrade(
        self, account: CustomerLoyaltyAccount
    ) -> Optional[MembershipTier]:
        """Check and apply tier upgrade based on lifetime points."""
        program = await self.get_program(account.program_id)
        if not program:
            return None

        # Get all tiers for the venue, ordered by threshold
        result = await self.db.execute(
            select(MembershipTier)
            .where(MembershipTier.venue_id == program.venue_id)
            .order_by(MembershipTier.min_points.desc())
        )
        tiers = list(result.scalars().all())

        # Find the highest tier the customer qualifies for
        new_tier = None
        for tier in tiers:
            if account.lifetime_points >= tier.min_points:
                new_tier = tier
                break

        if new_tier and (
            not account.tier_id or new_tier.id != account.tier_id
        ):
            old_tier_id = account.tier_id
            account.tier_id = new_tier.id
            await self.db.commit()

            # Could trigger tier change notification here
            return new_tier

        return None

    async def get_tier_progress(
        self, account_id: UUID
    ) -> Dict[str, Any]:
        """Get tier progress information for an account."""
        account = await self.get_account(account_id)
        if not account:
            raise ValueError("Account not found")

        program = await self.get_program(account.program_id)
        if not program:
            raise ValueError("Program not found")

        # Get all tiers
        result = await self.db.execute(
            select(MembershipTier)
            .where(MembershipTier.venue_id == program.venue_id)
            .order_by(MembershipTier.min_points)
        )
        tiers = list(result.scalars().all())

        current_tier = None
        next_tier = None

        for i, tier in enumerate(tiers):
            if account.tier_id and tier.id == account.tier_id:
                current_tier = tier
                if i + 1 < len(tiers):
                    next_tier = tiers[i + 1]
                break
            elif account.lifetime_points < tier.min_points:
                next_tier = tier
                if i > 0:
                    current_tier = tiers[i - 1]
                break

        points_to_next = None
        progress_percent = None
        if next_tier:
            points_to_next = next_tier.min_points - account.lifetime_points
            if current_tier:
                range_points = next_tier.min_points - current_tier.min_points
                progress = account.lifetime_points - current_tier.min_points
                progress_percent = min(100, (progress / range_points) * 100)

        return {
            "current_tier": current_tier,
            "next_tier": next_tier,
            "lifetime_points": account.lifetime_points,
            "points_to_next_tier": max(0, points_to_next) if points_to_next else None,
            "progress_percent": progress_percent,
        }

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _calculate_bonus_points(
        self,
        base_points: int,
        bonus_rules: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> int:
        """Calculate bonus points based on rules."""
        bonus = 0

        # Birthday bonus
        if metadata.get("is_birthday") and bonus_rules.get("birthday_multiplier"):
            bonus += int(base_points * (bonus_rules["birthday_multiplier"] - 1))

        # First purchase bonus
        if metadata.get("is_first_purchase") and bonus_rules.get(
            "first_purchase_bonus"
        ):
            bonus += bonus_rules["first_purchase_bonus"]

        # Category bonuses
        category = metadata.get("category")
        if category and bonus_rules.get("category_bonuses", {}).get(category):
            bonus += bonus_rules["category_bonuses"][category]

        # Double points days
        if metadata.get("is_double_points_day") and bonus_rules.get(
            "double_points_enabled"
        ):
            bonus += base_points  # Double the base points

        return bonus
