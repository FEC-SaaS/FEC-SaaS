"""
=============================================================================
FILE: tests/unit/test_performance_service.py
PURPOSE: Unit tests for PerformanceService class
=============================================================================
"""

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.venue import VenuePerformance
from app.schemas.venue import VenuePerformanceCreate
from app.services.performance_service import PerformanceService


class TestPerformanceService:
    """Tests for PerformanceService class."""

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
    def performance_service(self, mock_db_session):
        """Create PerformanceService instance with mock session."""
        return PerformanceService(mock_db_session)

    @pytest.fixture
    def venue_id(self):
        """Generate test venue ID."""
        return uuid.uuid4()

    @pytest.fixture
    def sample_performance(self, venue_id):
        """Create sample performance object."""
        return VenuePerformance(
            id=uuid.uuid4(),
            venue_id=venue_id,
            date=date.today(),
            revenue=15000.00,
            revenue_per_guest=45.00,
            transaction_count=333,
            average_transaction=45.00,
            guest_count=333,
            new_customers=50,
            returning_customers=283,
            party_bookings=5,
            nps_score=72.0,
            review_count=15,
            average_rating=4.5,
        )

    @pytest.fixture
    def performance_history(self, venue_id):
        """Create sample performance history."""
        return [
            VenuePerformance(
                id=uuid.uuid4(),
                venue_id=venue_id,
                date=date.today() - timedelta(days=i),
                revenue=15000.00 - (i * 100),
                guest_count=333 - i,
            )
            for i in range(7)
        ]

    # -------------------------------------------------------------------------
    # Get Performance History Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_performance_history(self, performance_service, mock_db_session, venue_id, performance_history):
        """Test getting performance history."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = performance_history
        mock_db_session.execute.return_value = mock_result

        result = await performance_service.get_performance_history(venue_id)

        assert len(result) == 7

    @pytest.mark.asyncio
    async def test_get_performance_history_with_date_range(self, performance_service, mock_db_session, venue_id, performance_history):
        """Test getting performance history with date range."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = performance_history[:3]
        mock_db_session.execute.return_value = mock_result

        start_date = date.today() - timedelta(days=2)
        end_date = date.today()

        result = await performance_service.get_performance_history(
            venue_id,
            start_date=start_date,
            end_date=end_date,
        )

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_get_performance_history_empty(self, performance_service, mock_db_session, venue_id):
        """Test getting empty performance history."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        result = await performance_service.get_performance_history(venue_id)

        assert len(result) == 0

    # -------------------------------------------------------------------------
    # Get Latest Performance Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_latest_performance(self, performance_service, mock_db_session, venue_id, sample_performance):
        """Test getting latest performance record."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_performance
        mock_db_session.execute.return_value = mock_result

        result = await performance_service.get_latest_performance(venue_id)

        assert result is not None
        assert result.date == date.today()

    @pytest.mark.asyncio
    async def test_get_latest_performance_none(self, performance_service, mock_db_session, venue_id):
        """Test getting latest performance when none exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await performance_service.get_latest_performance(venue_id)

        assert result is None

    # -------------------------------------------------------------------------
    # Record Performance Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_record_performance(self, performance_service, mock_db_session, venue_id):
        """Test recording new performance data."""
        performance_data = VenuePerformanceCreate(
            date=date.today(),
            revenue=20000.00,
            guest_count=400,
            transaction_count=400,
        )

        result = await performance_service.record_performance(venue_id, performance_data)

        assert result is not None
        assert result.revenue == 20000.00
        mock_db_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_performance_calculates_metrics(self, performance_service, mock_db_session, venue_id):
        """Test that recording calculates derived metrics."""
        performance_data = VenuePerformanceCreate(
            date=date.today(),
            revenue=20000.00,
            guest_count=400,
            transaction_count=500,
        )

        result = await performance_service.record_performance(venue_id, performance_data)

        assert result is not None
        # revenue_per_guest should be calculated
        assert result.revenue_per_guest == 50.00  # 20000 / 400

    # -------------------------------------------------------------------------
    # Get Performance Summary Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_performance_summary(self, performance_service, mock_db_session, venue_id, performance_history):
        """Test getting performance summary."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = performance_history
        mock_db_session.execute.return_value = mock_result

        result = await performance_service.get_performance_summary(venue_id)

        assert "total_revenue" in result
        assert "average_daily_revenue" in result
        assert "total_guests" in result
        assert "period_days" in result

    @pytest.mark.asyncio
    async def test_get_performance_summary_empty(self, performance_service, mock_db_session, venue_id):
        """Test getting summary with no data."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        result = await performance_service.get_performance_summary(venue_id)

        assert result["total_revenue"] == 0
        assert result["total_guests"] == 0

    # -------------------------------------------------------------------------
    # Compare Venues Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_compare_venues(self, performance_service, mock_db_session, venue_id):
        """Test comparing venue performance."""
        compare_ids = [uuid.uuid4(), uuid.uuid4()]

        # Mock performances for multiple venues
        performances = [
            VenuePerformance(
                id=uuid.uuid4(),
                venue_id=vid,
                date=date.today(),
                revenue=15000.00 + (i * 1000),
                guest_count=300 + (i * 10),
            )
            for i, vid in enumerate([venue_id] + compare_ids)
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = performances
        mock_db_session.execute.return_value = mock_result

        result = await performance_service.compare_venues(
            venue_id,
            compare_to_ids=compare_ids,
        )

        assert "base_venue_id" in result
        assert "metrics" in result

    # -------------------------------------------------------------------------
    # Franchise Leaderboard Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_franchise_leaderboard(self, performance_service, mock_db_session):
        """Test getting franchise leaderboard."""
        franchise_id = uuid.uuid4()

        # Create mock venue performances
        venues_data = [
            (uuid.uuid4(), "Venue A", 50000.00),
            (uuid.uuid4(), "Venue B", 45000.00),
            (uuid.uuid4(), "Venue C", 40000.00),
        ]

        mock_result = MagicMock()
        mock_result.all.return_value = venues_data
        mock_db_session.execute.return_value = mock_result

        result = await performance_service.get_franchise_leaderboard(
            franchise_id,
            metric="revenue",
            period="month",
        )

        assert "leaderboard" in result
        assert "franchise_id" in result
        assert "metric" in result

    # -------------------------------------------------------------------------
    # Analyze Trends Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_analyze_trends(self, performance_service, mock_db_session, venue_id, performance_history):
        """Test analyzing performance trends."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = performance_history
        mock_db_session.execute.return_value = mock_result

        result = await performance_service.analyze_trends(
            venue_id,
            metrics=["revenue", "guest_count"],
            period="week",
        )

        assert "venue_id" in result
        assert "trends" in result

    # -------------------------------------------------------------------------
    # Delete Performance Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_performance(self, performance_service, mock_db_session, venue_id, sample_performance):
        """Test deleting performance record."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_performance
        mock_db_session.execute.return_value = mock_result

        result = await performance_service.delete_performance(venue_id, sample_performance.id)

        assert result is True
        mock_db_session.delete.assert_called_once_with(sample_performance)

    @pytest.mark.asyncio
    async def test_delete_performance_not_found(self, performance_service, mock_db_session, venue_id):
        """Test deleting non-existent performance record."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await performance_service.delete_performance(venue_id, uuid.uuid4())

        assert result is False
