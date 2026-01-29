"""
=============================================================================
FILE: tests/test_loyalty.py
PURPOSE: Tests for loyalty program functionality
=============================================================================
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    LoyaltyProgram,
    CustomerLoyaltyAccount,
    LoyaltyTransaction,
    MembershipTier,
    LoyaltyTransactionType,
)
from app.services import LoyaltyService
from app.schemas.membership import (
    LoyaltyProgramCreate,
    EarnPointsRequest,
    RedeemPointsRequest,
)


class TestLoyaltyProgram:
    """Tests for loyalty program management."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> LoyaltyService:
        return LoyaltyService(db_session)

    @pytest_asyncio.fixture
    async def venue_id(self) -> str:
        return uuid4()

    async def test_create_loyalty_program(
        self, service: LoyaltyService, venue_id, sample_loyalty_program_data
    ):
        """Test creating a loyalty program."""
        program_data = LoyaltyProgramCreate(**sample_loyalty_program_data)
        program = await service.create_program(venue_id, program_data)

        assert program is not None
        assert program.name == sample_loyalty_program_data["name"]
        assert program.points_per_dollar == sample_loyalty_program_data["points_per_dollar"]
        assert program.is_active is True

    async def test_get_venue_program(
        self, service: LoyaltyService, venue_id, sample_loyalty_program_data
    ):
        """Test getting loyalty program for a venue."""
        program_data = LoyaltyProgramCreate(**sample_loyalty_program_data)
        created = await service.create_program(venue_id, program_data)

        retrieved = await service.get_venue_program(venue_id)

        assert retrieved is not None
        assert retrieved.id == created.id


class TestLoyaltyAccounts:
    """Tests for customer loyalty accounts."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> LoyaltyService:
        return LoyaltyService(db_session)

    @pytest_asyncio.fixture
    async def loyalty_program(self, db_session: AsyncSession) -> LoyaltyProgram:
        """Create a test loyalty program."""
        venue_id = uuid4()
        program = LoyaltyProgram(
            venue_id=venue_id,
            name="Test Rewards",
            points_per_dollar=10.0,
            points_expiry_days=365,
            is_active=True,
        )
        db_session.add(program)
        await db_session.commit()
        await db_session.refresh(program)
        return program

    async def test_create_loyalty_account(
        self, service: LoyaltyService, loyalty_program: LoyaltyProgram
    ):
        """Test creating/getting a loyalty account."""
        customer_id = uuid4()

        account = await service.get_or_create_account(
            customer_id=customer_id,
            program_id=loyalty_program.id,
        )

        assert account is not None
        assert account.customer_id == customer_id
        assert account.points_balance == 0
        assert account.lifetime_points == 0

    async def test_get_existing_account(
        self, service: LoyaltyService, loyalty_program: LoyaltyProgram
    ):
        """Test getting an existing account."""
        customer_id = uuid4()

        # Create account
        account1 = await service.get_or_create_account(
            customer_id=customer_id,
            program_id=loyalty_program.id,
        )

        # Get again - should return same account
        account2 = await service.get_or_create_account(
            customer_id=customer_id,
            program_id=loyalty_program.id,
        )

        assert account1.id == account2.id


class TestPointsTransactions:
    """Tests for points earning and redemption."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> LoyaltyService:
        return LoyaltyService(db_session)

    @pytest_asyncio.fixture
    async def loyalty_account(
        self, db_session: AsyncSession
    ) -> CustomerLoyaltyAccount:
        """Create a test loyalty account with program."""
        venue_id = uuid4()
        program = LoyaltyProgram(
            venue_id=venue_id,
            name="Test Rewards",
            points_per_dollar=10.0,
            points_expiry_days=365,
            is_active=True,
        )
        db_session.add(program)
        await db_session.commit()

        account = CustomerLoyaltyAccount(
            customer_id=uuid4(),
            program_id=program.id,
            points_balance=0,
            lifetime_points=0,
        )
        db_session.add(account)
        await db_session.commit()
        await db_session.refresh(account)
        return account

    async def test_earn_points(
        self, service: LoyaltyService, loyalty_account: CustomerLoyaltyAccount
    ):
        """Test earning points."""
        request = EarnPointsRequest(
            points=100,
            reference_type="purchase",
            reference_id=str(uuid4()),
            description="Purchase reward",
        )

        transaction = await service.earn_points(loyalty_account.id, request)

        assert transaction is not None
        assert transaction.points == 100
        assert transaction.transaction_type == LoyaltyTransactionType.EARNED

        # Verify account balance updated
        account = await service.get_account(loyalty_account.id)
        assert account.points_balance == 100
        assert account.lifetime_points == 100

    async def test_earn_points_from_transaction_amount(
        self, service: LoyaltyService, loyalty_account: CustomerLoyaltyAccount
    ):
        """Test earning points based on transaction amount."""
        request = EarnPointsRequest(
            points=0,  # Will be calculated from amount
            transaction_amount=Decimal("50.00"),  # $50 = 500 points at 10 per $
            reference_type="purchase",
        )

        transaction = await service.earn_points(loyalty_account.id, request)

        assert transaction.points == 500  # 50 * 10 points per dollar

    async def test_redeem_points(
        self, service: LoyaltyService, loyalty_account: CustomerLoyaltyAccount
    ):
        """Test redeeming points."""
        # First earn some points
        earn_request = EarnPointsRequest(points=500)
        await service.earn_points(loyalty_account.id, earn_request)

        # Then redeem
        redeem_request = RedeemPointsRequest(
            points=200,
            reference_type="reward",
            reference_id=str(uuid4()),
        )

        transaction = await service.redeem_points(loyalty_account.id, redeem_request)

        assert transaction.points == -200
        assert transaction.transaction_type == LoyaltyTransactionType.REDEEMED

        # Verify balance
        account = await service.get_account(loyalty_account.id)
        assert account.points_balance == 300

    async def test_redeem_insufficient_points(
        self, service: LoyaltyService, loyalty_account: CustomerLoyaltyAccount
    ):
        """Test that redeeming more points than available fails."""
        redeem_request = RedeemPointsRequest(
            points=1000,  # More than balance
        )

        with pytest.raises(ValueError, match="Insufficient points"):
            await service.redeem_points(loyalty_account.id, redeem_request)

    async def test_transfer_points(
        self, service: LoyaltyService, db_session: AsyncSession
    ):
        """Test transferring points between accounts."""
        venue_id = uuid4()
        program = LoyaltyProgram(
            venue_id=venue_id,
            name="Transfer Test",
            points_per_dollar=10.0,
            is_active=True,
        )
        db_session.add(program)
        await db_session.commit()

        # Create two accounts
        account1 = CustomerLoyaltyAccount(
            customer_id=uuid4(),
            program_id=program.id,
            points_balance=500,
            lifetime_points=500,
        )
        account2 = CustomerLoyaltyAccount(
            customer_id=uuid4(),
            program_id=program.id,
            points_balance=0,
            lifetime_points=0,
        )
        db_session.add_all([account1, account2])
        await db_session.commit()
        await db_session.refresh(account1)
        await db_session.refresh(account2)

        # Transfer
        debit_txn, credit_txn = await service.transfer_points(
            from_account_id=account1.id,
            to_account_id=account2.id,
            points=200,
        )

        assert debit_txn.points == -200
        assert credit_txn.points == 200

        # Verify balances
        updated1 = await service.get_account(account1.id)
        updated2 = await service.get_account(account2.id)
        assert updated1.points_balance == 300
        assert updated2.points_balance == 200

    async def test_get_transaction_history(
        self, service: LoyaltyService, loyalty_account: CustomerLoyaltyAccount
    ):
        """Test getting transaction history."""
        # Create some transactions
        for i in range(5):
            request = EarnPointsRequest(points=100)
            await service.earn_points(loyalty_account.id, request)

        history = await service.get_transaction_history(
            account_id=loyalty_account.id,
            limit=10,
        )

        assert len(history) == 5
        # Should be ordered by created_at desc
        for i in range(len(history) - 1):
            assert history[i].created_at >= history[i + 1].created_at


class TestTierProgress:
    """Tests for tier progress tracking."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> LoyaltyService:
        return LoyaltyService(db_session)

    @pytest_asyncio.fixture
    async def program_with_tiers(
        self, db_session: AsyncSession
    ) -> tuple[LoyaltyProgram, list[MembershipTier]]:
        """Create a program with multiple tiers."""
        venue_id = uuid4()

        # Create tiers
        tiers = []
        tier_data = [
            ("Bronze", 0, 1),
            ("Silver", 1000, 2),
            ("Gold", 5000, 3),
            ("Platinum", 10000, 4),
        ]
        for name, min_points, level in tier_data:
            tier = MembershipTier(
                venue_id=venue_id,
                name=name,
                min_points=min_points,
                level=level,
                is_active=True,
            )
            db_session.add(tier)
            tiers.append(tier)

        # Create program
        program = LoyaltyProgram(
            venue_id=venue_id,
            name="Tiered Rewards",
            points_per_dollar=10.0,
            is_active=True,
        )
        db_session.add(program)
        await db_session.commit()

        for tier in tiers:
            await db_session.refresh(tier)
        await db_session.refresh(program)

        return program, tiers

    async def test_get_tier_progress(
        self, service: LoyaltyService, program_with_tiers, db_session: AsyncSession
    ):
        """Test getting tier progress information."""
        program, tiers = program_with_tiers

        account = CustomerLoyaltyAccount(
            customer_id=uuid4(),
            program_id=program.id,
            tier_id=tiers[1].id,  # Silver
            points_balance=1500,
            lifetime_points=1500,
        )
        db_session.add(account)
        await db_session.commit()
        await db_session.refresh(account)

        progress = await service.get_tier_progress(account.id)

        assert progress["current_tier"] is not None
        assert progress["current_tier"].name == "Silver"
        assert progress["next_tier"] is not None
        assert progress["next_tier"].name == "Gold"
        assert progress["points_to_next_tier"] == 3500  # 5000 - 1500
