"""
=============================================================================
FILE: tests/unit/test_hours_service.py
PURPOSE: Unit tests for HoursService class
=============================================================================
"""

import uuid
from datetime import datetime, date, time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.venue import VenueHours, VenueSpecialHours
from app.schemas.venue import VenueHoursCreate, VenueHoursUpdate, VenueSpecialHoursCreate
from app.services.hours_service import HoursService


class TestHoursService:
    """Tests for HoursService class."""

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
    def hours_service(self, mock_db_session):
        """Create HoursService instance with mock session."""
        return HoursService(mock_db_session)

    @pytest.fixture
    def venue_id(self):
        """Generate test venue ID."""
        return uuid.uuid4()

    @pytest.fixture
    def sample_hours(self, venue_id):
        """Create sample hours objects."""
        return [
            VenueHours(
                id=uuid.uuid4(),
                venue_id=venue_id,
                day_of_week=i,
                open_time=time(10, 0) if i > 0 else None,
                close_time=time(21, 0) if i > 0 else None,
                is_closed=i == 0,
            )
            for i in range(7)
        ]

    # -------------------------------------------------------------------------
    # Get Hours Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_hours_success(self, hours_service, mock_db_session, venue_id, sample_hours):
        """Test getting venue hours."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_hours
        mock_db_session.execute.return_value = mock_result

        result = await hours_service.get_hours(venue_id)

        assert len(result) == 7
        assert result[0].is_closed is True  # Sunday
        assert result[1].open_time == time(10, 0)

    @pytest.mark.asyncio
    async def test_get_hours_empty(self, hours_service, mock_db_session, venue_id):
        """Test getting hours for venue with no hours set."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        result = await hours_service.get_hours(venue_id)

        assert len(result) == 0

    # -------------------------------------------------------------------------
    # Set Hours Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_set_hours_creates_all_days(self, hours_service, mock_db_session, venue_id):
        """Test setting hours for all days of week."""
        hours_data = [
            VenueHoursCreate(day_of_week=i, open_time=time(10, 0), close_time=time(21, 0))
            for i in range(7)
        ]

        result = await hours_service.set_hours(venue_id, hours_data)

        assert len(result) == 7
        assert mock_db_session.execute.called  # Delete existing
        assert mock_db_session.add.call_count == 7

    @pytest.mark.asyncio
    async def test_set_hours_replaces_existing(self, hours_service, mock_db_session, venue_id):
        """Test that set_hours replaces existing hours."""
        hours_data = [
            VenueHoursCreate(day_of_week=1, open_time=time(9, 0), close_time=time(22, 0))
        ]

        await hours_service.set_hours(venue_id, hours_data)

        # Should delete existing hours first
        mock_db_session.execute.assert_called()

    # -------------------------------------------------------------------------
    # Update Day Hours Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_day_hours_existing(self, hours_service, mock_db_session, venue_id, sample_hours):
        """Test updating hours for existing day."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_hours[1]  # Monday
        mock_db_session.execute.return_value = mock_result

        update_data = VenueHoursUpdate(open_time=time(9, 0))

        result = await hours_service.update_day_hours(venue_id, 1, update_data)

        assert result is not None
        assert result.open_time == time(9, 0)

    @pytest.mark.asyncio
    async def test_update_day_hours_creates_new(self, hours_service, mock_db_session, venue_id):
        """Test updating hours for non-existing day creates new record."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        update_data = VenueHoursUpdate(open_time=time(10, 0), close_time=time(21, 0))

        result = await hours_service.update_day_hours(venue_id, 3, update_data)

        assert result is not None
        mock_db_session.add.assert_called_once()

    # -------------------------------------------------------------------------
    # Is Open Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_is_open_during_hours(self, hours_service, mock_db_session, venue_id, sample_hours):
        """Test is_open returns True during operating hours."""
        # Monday 2pm
        check_date = date(2025, 1, 27)  # Monday
        check_time = time(14, 0)

        mock_regular_result = MagicMock()
        mock_regular_result.scalar_one_or_none.return_value = sample_hours[1]  # Monday
        mock_special_result = MagicMock()
        mock_special_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.side_effect = [mock_special_result, mock_regular_result]

        result = await hours_service.is_open(venue_id, check_date, check_time)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_open_closed_day(self, hours_service, mock_db_session, venue_id, sample_hours):
        """Test is_open returns False on closed day."""
        check_date = date(2025, 1, 26)  # Sunday
        check_time = time(14, 0)

        mock_regular_result = MagicMock()
        mock_regular_result.scalar_one_or_none.return_value = sample_hours[0]  # Sunday (closed)
        mock_special_result = MagicMock()
        mock_special_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.side_effect = [mock_special_result, mock_regular_result]

        result = await hours_service.is_open(venue_id, check_date, check_time)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_open_special_hours_override(self, hours_service, mock_db_session, venue_id):
        """Test special hours override regular hours."""
        check_date = date(2025, 12, 25)  # Christmas
        check_time = time(14, 0)

        special_hours = VenueSpecialHours(
            id=uuid.uuid4(),
            venue_id=venue_id,
            date=check_date,
            name="Christmas Day",
            is_closed=True,
        )

        mock_special_result = MagicMock()
        mock_special_result.scalar_one_or_none.return_value = special_hours
        mock_db_session.execute.return_value = mock_special_result

        result = await hours_service.is_open(venue_id, check_date, check_time)

        assert result is False

    # -------------------------------------------------------------------------
    # Special Hours Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_special_hours(self, hours_service, mock_db_session, venue_id):
        """Test getting special hours."""
        special = VenueSpecialHours(
            id=uuid.uuid4(),
            venue_id=venue_id,
            date=date(2025, 12, 25),
            name="Christmas",
            is_closed=True,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [special]
        mock_db_session.execute.return_value = mock_result

        result = await hours_service.get_special_hours(venue_id)

        assert len(result) == 1
        assert result[0].name == "Christmas"

    @pytest.mark.asyncio
    async def test_create_special_hours(self, hours_service, mock_db_session, venue_id):
        """Test creating special hours."""
        special_data = VenueSpecialHoursCreate(
            date=date(2025, 7, 4),
            name="Independence Day",
            open_time=time(12, 0),
            close_time=time(18, 0),
        )

        result = await hours_service.create_special_hours(venue_id, special_data)

        assert result is not None
        assert result.name == "Independence Day"
        mock_db_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_special_hours(self, hours_service, mock_db_session, venue_id):
        """Test deleting special hours."""
        special_id = uuid.uuid4()
        special = VenueSpecialHours(
            id=special_id,
            venue_id=venue_id,
            date=date(2025, 12, 25),
            name="Christmas",
            is_closed=True,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = special
        mock_db_session.execute.return_value = mock_result

        result = await hours_service.delete_special_hours(venue_id, special_id)

        assert result is True
        mock_db_session.delete.assert_called_once_with(special)
