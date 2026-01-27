"""
=============================================================================
FILE: tests/unit/test_family_service.py
PURPOSE: Unit tests for FamilyService
=============================================================================
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.family_service import FamilyService
from app.schemas.customer import (
    FamilyCreate,
    FamilyUpdate,
    FamilyMemberCreate,
)
from app.models.customer import FamilyRole
from tests.conftest import FamilyFactory, CustomerFactory


class TestFamilyServiceCreate:
    """Tests for family creation."""

    @pytest.mark.asyncio
    async def test_create_family_success(self, db_session: AsyncSession, sample_venue_id):
        """Test successful family creation."""
        service = FamilyService(db_session)

        family_data = FamilyCreate(
            venue_id=sample_venue_id,
            family_name="Johnson Family",
            address="123 Main St",
            notes="VIP family",
        )

        family = await service.create_family(family_data)

        assert family is not None
        assert family.family_name == "Johnson Family"
        assert family.venue_id == sample_venue_id

    @pytest.mark.asyncio
    async def test_create_family_minimal(self, db_session: AsyncSession, sample_venue_id):
        """Test creating family with minimal data."""
        service = FamilyService(db_session)

        family_data = FamilyCreate(
            venue_id=sample_venue_id,
            family_name="Minimal Family",
        )

        family = await service.create_family(family_data)

        assert family is not None
        assert family.family_name == "Minimal Family"


class TestFamilyServiceGet:
    """Tests for family retrieval."""

    @pytest.mark.asyncio
    async def test_get_family_by_id(self, db_session: AsyncSession, sample_family):
        """Test getting family by ID."""
        service = FamilyService(db_session)

        family = await service.get_family(sample_family.id)

        assert family is not None
        assert family.id == sample_family.id

    @pytest.mark.asyncio
    async def test_get_family_not_found(self, db_session: AsyncSession):
        """Test getting non-existent family."""
        service = FamilyService(db_session)

        family = await service.get_family(uuid4())

        assert family is None


class TestFamilyServiceList:
    """Tests for family listing."""

    @pytest.mark.asyncio
    async def test_list_families(self, db_session: AsyncSession, sample_family, sample_venue_id):
        """Test listing families for venue."""
        service = FamilyService(db_session)

        families = await service.list_families(
            venue_id=sample_venue_id,
            limit=10,
            offset=0,
        )

        assert len(families) >= 1

    @pytest.mark.asyncio
    async def test_list_families_empty_venue(self, db_session: AsyncSession):
        """Test listing families for venue with no families."""
        service = FamilyService(db_session)

        families = await service.list_families(
            venue_id=str(uuid4()),
            limit=10,
            offset=0,
        )

        assert len(families) == 0

    @pytest.mark.asyncio
    async def test_list_families_pagination(self, db_session: AsyncSession, sample_venue_id):
        """Test family listing with pagination."""
        service = FamilyService(db_session)

        # Create multiple families
        for i in range(5):
            family_data = FamilyCreate(
                venue_id=sample_venue_id,
                family_name=f"Family {i}",
            )
            await service.create_family(family_data)

        families = await service.list_families(
            venue_id=sample_venue_id,
            limit=2,
            offset=0,
        )

        assert len(families) == 2


class TestFamilyServiceUpdate:
    """Tests for family updates."""

    @pytest.mark.asyncio
    async def test_update_family_success(self, db_session: AsyncSession, sample_family):
        """Test successful family update."""
        service = FamilyService(db_session)

        update_data = FamilyUpdate(
            family_name="Updated Family Name",
            notes="New notes",
        )

        updated = await service.update_family(sample_family.id, update_data)

        assert updated is not None
        assert updated.family_name == "Updated Family Name"
        assert updated.notes == "New notes"

    @pytest.mark.asyncio
    async def test_update_family_partial(self, db_session: AsyncSession, sample_family):
        """Test partial family update."""
        service = FamilyService(db_session)
        original_name = sample_family.family_name

        update_data = FamilyUpdate(notes="Only notes updated")

        updated = await service.update_family(sample_family.id, update_data)

        assert updated.family_name == original_name
        assert updated.notes == "Only notes updated"

    @pytest.mark.asyncio
    async def test_update_family_not_found(self, db_session: AsyncSession):
        """Test updating non-existent family."""
        service = FamilyService(db_session)

        update_data = FamilyUpdate(family_name="Test")

        updated = await service.update_family(uuid4(), update_data)

        assert updated is None


class TestFamilyServiceDelete:
    """Tests for family deletion."""

    @pytest.mark.asyncio
    async def test_delete_family_success(self, db_session: AsyncSession, sample_family):
        """Test successful family deletion."""
        service = FamilyService(db_session)

        deleted = await service.delete_family(sample_family.id)

        assert deleted is True

        # Verify family is deleted
        family = await service.get_family(sample_family.id)
        assert family is None

    @pytest.mark.asyncio
    async def test_delete_family_not_found(self, db_session: AsyncSession):
        """Test deleting non-existent family."""
        service = FamilyService(db_session)

        deleted = await service.delete_family(uuid4())

        assert deleted is False


class TestFamilyServiceMembers:
    """Tests for family member management."""

    @pytest.mark.asyncio
    async def test_add_family_member(self, db_session: AsyncSession, sample_family, sample_customer):
        """Test adding member to family."""
        service = FamilyService(db_session)

        member_data = FamilyMemberCreate(
            customer_id=sample_customer.id,
            role=FamilyRole.PRIMARY,
        )

        member = await service.add_family_member(sample_family.id, member_data)

        assert member is not None
        assert str(member.customer_id) == str(sample_customer.id)
        assert member.role == FamilyRole.PRIMARY

    @pytest.mark.asyncio
    async def test_add_family_member_different_roles(
        self, db_session: AsyncSession, sample_family, sample_customers
    ):
        """Test adding members with different roles."""
        service = FamilyService(db_session)

        # Add primary
        member_data = FamilyMemberCreate(
            customer_id=sample_customers[0].id,
            role=FamilyRole.PRIMARY,
        )
        member1 = await service.add_family_member(sample_family.id, member_data)

        # Add child
        member_data = FamilyMemberCreate(
            customer_id=sample_customers[1].id,
            role=FamilyRole.CHILD,
        )
        member2 = await service.add_family_member(sample_family.id, member_data)

        assert member1.role == FamilyRole.PRIMARY
        assert member2.role == FamilyRole.CHILD

    @pytest.mark.asyncio
    async def test_remove_family_member(self, db_session: AsyncSession, sample_family, sample_customer):
        """Test removing member from family."""
        service = FamilyService(db_session)

        # Add member first
        member_data = FamilyMemberCreate(
            customer_id=sample_customer.id,
            role=FamilyRole.MEMBER,
        )
        member = await service.add_family_member(sample_family.id, member_data)

        # Remove member
        removed = await service.remove_family_member(sample_family.id, member.id)

        assert removed is True

    @pytest.mark.asyncio
    async def test_remove_family_member_not_found(self, db_session: AsyncSession, sample_family):
        """Test removing non-existent member."""
        service = FamilyService(db_session)

        removed = await service.remove_family_member(sample_family.id, uuid4())

        assert removed is False

    @pytest.mark.asyncio
    async def test_add_member_invalid_family(self, db_session: AsyncSession, sample_customer):
        """Test adding member to non-existent family."""
        service = FamilyService(db_session)

        member_data = FamilyMemberCreate(
            customer_id=sample_customer.id,
            role=FamilyRole.MEMBER,
        )

        member = await service.add_family_member(uuid4(), member_data)

        # Should return None or handle gracefully
        assert member is None


class TestFamilyServiceWithMembers:
    """Tests for family operations with members."""

    @pytest.mark.asyncio
    async def test_get_family_with_members(
        self, db_session: AsyncSession, sample_family, sample_customers
    ):
        """Test getting family includes members."""
        service = FamilyService(db_session)

        # Add members
        for customer in sample_customers[:3]:
            member_data = FamilyMemberCreate(
                customer_id=customer.id,
                role=FamilyRole.MEMBER,
            )
            await service.add_family_member(sample_family.id, member_data)

        family = await service.get_family(sample_family.id)

        assert family is not None
        # Family should have members loaded
        assert hasattr(family, 'members')

    @pytest.mark.asyncio
    async def test_delete_family_with_members(
        self, db_session: AsyncSession, sample_family, sample_customer
    ):
        """Test deleting family also handles members."""
        service = FamilyService(db_session)

        # Add member
        member_data = FamilyMemberCreate(
            customer_id=sample_customer.id,
            role=FamilyRole.MEMBER,
        )
        await service.add_family_member(sample_family.id, member_data)

        # Delete family
        deleted = await service.delete_family(sample_family.id)

        assert deleted is True
