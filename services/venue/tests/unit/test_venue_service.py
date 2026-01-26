"""
=============================================================================
FILE: tests/unit/test_venue_service.py
PURPOSE: Unit tests for VenueService class
=============================================================================
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.venue import Venue, VenueStatus, SubscriptionTier, OnboardingStatus
from app.schemas.venue import VenueCreate, VenueUpdate, VenueFilters, PaginationParams
from app.services.venue_service import VenueService


class TestVenueService:
    """Tests for VenueService class."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        session.delete = AsyncMock()
        return session

    @pytest.fixture
    def venue_service(self, mock_db_session):
        """Create VenueService instance with mock session."""
        return VenueService(mock_db_session)

    @pytest.fixture
    def sample_venue(self):
        """Create sample venue object."""
        return Venue(
            id=uuid.uuid4(),
            name="Test FEC",
            slug="test-fec",
            address_line1="123 Main St",
            city="Dallas",
            state="Texas",
            postal_code="75001",
            country="USA",
            timezone="America/Chicago",
            phone="+1-214-555-0100",
            email="test@fec.com",
            subscription_tier=SubscriptionTier.PRO,
            status=VenueStatus.ACTIVE,
            onboarding_status=OnboardingStatus.COMPLETED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    # -------------------------------------------------------------------------
    # Create Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_venue_success(self, venue_service, mock_db_session):
        """Test successful venue creation."""
        venue_data = VenueCreate(
            name="New FEC",
            address_line1="456 Oak Ave",
            city="Houston",
            state="Texas",
            postal_code="77001",
            phone="+1-713-555-0100",
            email="new@fec.com",
        )

        # Setup mock
        mock_db_session.refresh = AsyncMock(side_effect=lambda v: setattr(v, 'id', uuid.uuid4()))

        result = await venue_service.create_venue(venue_data)

        assert result is not None
        assert result.name == "New FEC"
        assert result.status == VenueStatus.PENDING
        assert result.onboarding_status == OnboardingStatus.NOT_STARTED
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_venue_generates_slug(self, venue_service, mock_db_session):
        """Test that slug is auto-generated from name."""
        venue_data = VenueCreate(
            name="My Awesome FEC Location",
            address_line1="123 Main St",
            city="Dallas",
            state="Texas",
            postal_code="75001",
            phone="+1-214-555-0100",
            email="test@fec.com",
        )

        result = await venue_service.create_venue(venue_data)

        assert "my-awesome-fec-location" in result.slug.lower()

    @pytest.mark.asyncio
    async def test_create_venue_with_custom_slug(self, venue_service, mock_db_session):
        """Test venue creation with custom slug."""
        venue_data = VenueCreate(
            name="My FEC",
            slug="custom-slug",
            address_line1="123 Main St",
            city="Dallas",
            state="Texas",
            postal_code="75001",
            phone="+1-214-555-0100",
            email="test@fec.com",
        )

        result = await venue_service.create_venue(venue_data)

        assert result.slug == "custom-slug"

    # -------------------------------------------------------------------------
    # Get Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_venue_by_id_found(self, venue_service, mock_db_session, sample_venue):
        """Test getting venue by ID when it exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_venue
        mock_db_session.execute.return_value = mock_result

        result = await venue_service.get_venue(sample_venue.id)

        assert result is not None
        assert result.id == sample_venue.id
        assert result.name == sample_venue.name

    @pytest.mark.asyncio
    async def test_get_venue_by_id_not_found(self, venue_service, mock_db_session):
        """Test getting venue by ID when it doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await venue_service.get_venue(uuid.uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_venue_by_slug(self, venue_service, mock_db_session, sample_venue):
        """Test getting venue by slug."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_venue
        mock_db_session.execute.return_value = mock_result

        result = await venue_service.get_venue_by_slug("test-fec")

        assert result is not None
        assert result.slug == "test-fec"

    # -------------------------------------------------------------------------
    # List Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_venues_no_filters(self, venue_service, mock_db_session, sample_venue):
        """Test listing venues without filters."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_venues_result = MagicMock()
        mock_venues_result.scalars.return_value.all.return_value = [sample_venue]

        mock_db_session.execute.side_effect = [mock_count_result, mock_venues_result]

        filters = VenueFilters()
        pagination = PaginationParams()

        venues, total = await venue_service.list_venues(filters, pagination)

        assert total == 1
        assert len(venues) == 1
        assert venues[0].name == sample_venue.name

    @pytest.mark.asyncio
    async def test_list_venues_with_status_filter(self, venue_service, mock_db_session, sample_venue):
        """Test listing venues with status filter."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_venues_result = MagicMock()
        mock_venues_result.scalars.return_value.all.return_value = [sample_venue]

        mock_db_session.execute.side_effect = [mock_count_result, mock_venues_result]

        filters = VenueFilters(status=VenueStatus.ACTIVE)
        pagination = PaginationParams()

        venues, total = await venue_service.list_venues(filters, pagination)

        assert total == 1
        mock_db_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_list_venues_pagination(self, venue_service, mock_db_session):
        """Test venue listing pagination."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 50

        mock_venues_result = MagicMock()
        mock_venues_result.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [mock_count_result, mock_venues_result]

        filters = VenueFilters()
        pagination = PaginationParams(page=2, page_size=10)

        venues, total = await venue_service.list_venues(filters, pagination)

        assert total == 50

    # -------------------------------------------------------------------------
    # Update Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_venue_success(self, venue_service, mock_db_session, sample_venue):
        """Test successful venue update."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_venue
        mock_db_session.execute.return_value = mock_result

        update_data = VenueUpdate(name="Updated FEC", description="New description")

        result = await venue_service.update_venue(sample_venue.id, update_data)

        assert result is not None
        assert result.name == "Updated FEC"
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_venue_not_found(self, venue_service, mock_db_session):
        """Test updating non-existent venue."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        update_data = VenueUpdate(name="Updated FEC")

        result = await venue_service.update_venue(uuid.uuid4(), update_data)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_venue_partial(self, venue_service, mock_db_session, sample_venue):
        """Test partial venue update."""
        original_name = sample_venue.name
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_venue
        mock_db_session.execute.return_value = mock_result

        update_data = VenueUpdate(description="Only updating description")

        result = await venue_service.update_venue(sample_venue.id, update_data)

        # Name should remain unchanged
        assert result.name == original_name
        assert result.description == "Only updating description"

    # -------------------------------------------------------------------------
    # Delete Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_venue_soft_delete(self, venue_service, mock_db_session, sample_venue):
        """Test soft delete of venue."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_venue
        mock_db_session.execute.return_value = mock_result

        result = await venue_service.delete_venue(sample_venue.id, hard_delete=False)

        assert result is True
        assert sample_venue.is_deleted is True
        assert sample_venue.deleted_at is not None

    @pytest.mark.asyncio
    async def test_delete_venue_hard_delete(self, venue_service, mock_db_session, sample_venue):
        """Test hard delete of venue."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_venue
        mock_db_session.execute.return_value = mock_result

        result = await venue_service.delete_venue(sample_venue.id, hard_delete=True)

        assert result is True
        mock_db_session.delete.assert_called_once_with(sample_venue)

    @pytest.mark.asyncio
    async def test_delete_venue_not_found(self, venue_service, mock_db_session):
        """Test deleting non-existent venue."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await venue_service.delete_venue(uuid.uuid4())

        assert result is False

    # -------------------------------------------------------------------------
    # Status Update Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_status(self, venue_service, mock_db_session, sample_venue):
        """Test venue status update."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_venue
        mock_db_session.execute.return_value = mock_result

        result = await venue_service.update_status(sample_venue.id, VenueStatus.SUSPENDED)

        assert result is not None
        assert result.status == VenueStatus.SUSPENDED

    # -------------------------------------------------------------------------
    # Bulk Operations Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_bulk_create_venues(self, venue_service, mock_db_session):
        """Test bulk venue creation."""
        venues_data = [
            VenueCreate(
                name=f"FEC {i}",
                address_line1=f"{i}00 Main St",
                city="Dallas",
                state="Texas",
                postal_code="75001",
                phone="+1-214-555-0100",
                email=f"fec{i}@test.com",
            )
            for i in range(3)
        ]

        result = await venue_service.bulk_create_venues(venues_data)

        assert len(result) == 3
        assert mock_db_session.add.call_count == 3

    @pytest.mark.asyncio
    async def test_bulk_create_with_franchise_id(self, venue_service, mock_db_session):
        """Test bulk venue creation with franchise ID."""
        franchise_id = uuid.uuid4()
        venues_data = [
            VenueCreate(
                name="FEC 1",
                address_line1="100 Main St",
                city="Dallas",
                state="Texas",
                postal_code="75001",
                phone="+1-214-555-0100",
                email="fec1@test.com",
            )
        ]

        result = await venue_service.bulk_create_venues(venues_data, franchise_id=franchise_id)

        assert len(result) == 1
        assert result[0].franchise_id == franchise_id
