"""
=============================================================================
FILE: tests/unit/test_onboarding_service.py
PURPOSE: Unit tests for OnboardingService class
=============================================================================
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.venue import Venue, VenueStatus, SubscriptionTier, OnboardingStatus
from app.services.onboarding_service import OnboardingService, ONBOARDING_STEPS


class TestOnboardingService:
    """Tests for OnboardingService class."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def onboarding_service(self, mock_db_session):
        """Create OnboardingService instance with mock session."""
        return OnboardingService(mock_db_session)

    @pytest.fixture
    def venue_id(self):
        """Generate test venue ID."""
        return uuid.uuid4()

    @pytest.fixture
    def new_venue(self, venue_id):
        """Create new venue not started onboarding."""
        return Venue(
            id=venue_id,
            name="New FEC",
            slug="new-fec",
            subscription_tier=SubscriptionTier.PRO,
            status=VenueStatus.PENDING,
            onboarding_status=OnboardingStatus.NOT_STARTED,
            onboarding_data=None,
            address_line1="123 Main St",
            city="Dallas",
            state="Texas",
            postal_code="75001",
            country="USA",
            timezone="America/Chicago",
            phone="+1-214-555-0100",
            email="test@fec.com",
        )

    @pytest.fixture
    def in_progress_venue(self, venue_id):
        """Create venue with onboarding in progress."""
        return Venue(
            id=venue_id,
            name="In Progress FEC",
            slug="in-progress-fec",
            subscription_tier=SubscriptionTier.PRO,
            status=VenueStatus.PENDING,
            onboarding_status=OnboardingStatus.IN_PROGRESS,
            onboarding_started_at=datetime.utcnow(),
            onboarding_data={
                "completed_steps": ["basic_info", "location"],
                "step_data": {
                    "basic_info": {"completed": True},
                    "location": {"completed": True},
                },
            },
            address_line1="123 Main St",
            city="Dallas",
            state="Texas",
            postal_code="75001",
            country="USA",
            timezone="America/Chicago",
            phone="+1-214-555-0100",
            email="test@fec.com",
        )

    @pytest.fixture
    def completed_venue(self, venue_id):
        """Create venue with completed onboarding."""
        return Venue(
            id=venue_id,
            name="Completed FEC",
            slug="completed-fec",
            subscription_tier=SubscriptionTier.PRO,
            status=VenueStatus.ACTIVE,
            onboarding_status=OnboardingStatus.COMPLETED,
            onboarding_started_at=datetime.utcnow(),
            onboarding_completed_at=datetime.utcnow(),
            address_line1="123 Main St",
            city="Dallas",
            state="Texas",
            postal_code="75001",
            country="USA",
            timezone="America/Chicago",
            phone="+1-214-555-0100",
            email="test@fec.com",
        )

    # -------------------------------------------------------------------------
    # Onboarding Steps Configuration Tests
    # -------------------------------------------------------------------------

    def test_onboarding_steps_defined(self):
        """Test that onboarding steps are properly defined."""
        assert len(ONBOARDING_STEPS) > 0
        for step in ONBOARDING_STEPS:
            assert "name" in step
            assert "display_name" in step
            assert "is_required" in step

    def test_required_steps_exist(self):
        """Test that required steps are marked."""
        required_steps = [s for s in ONBOARDING_STEPS if s["is_required"]]
        assert len(required_steps) > 0

    # -------------------------------------------------------------------------
    # Get Onboarding Status Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_onboarding_status_not_started(self, onboarding_service, mock_db_session, new_venue):
        """Test getting status for not started onboarding."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = new_venue
        mock_db_session.execute.return_value = mock_result

        result = await onboarding_service.get_onboarding_status(new_venue.id)

        assert result["status"] == OnboardingStatus.NOT_STARTED
        assert result["progress_percentage"] == 0
        assert len(result["steps_completed"]) == 0

    @pytest.mark.asyncio
    async def test_get_onboarding_status_in_progress(self, onboarding_service, mock_db_session, in_progress_venue):
        """Test getting status for in-progress onboarding."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = in_progress_venue
        mock_db_session.execute.return_value = mock_result

        result = await onboarding_service.get_onboarding_status(in_progress_venue.id)

        assert result["status"] == OnboardingStatus.IN_PROGRESS
        assert result["progress_percentage"] > 0
        assert "basic_info" in result["steps_completed"]
        assert "location" in result["steps_completed"]

    @pytest.mark.asyncio
    async def test_get_onboarding_status_completed(self, onboarding_service, mock_db_session, completed_venue):
        """Test getting status for completed onboarding."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = completed_venue
        mock_db_session.execute.return_value = mock_result

        result = await onboarding_service.get_onboarding_status(completed_venue.id)

        assert result["status"] == OnboardingStatus.COMPLETED
        assert result["progress_percentage"] == 100

    # -------------------------------------------------------------------------
    # Start Onboarding Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_start_onboarding_success(self, onboarding_service, mock_db_session, new_venue):
        """Test starting onboarding."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = new_venue
        mock_db_session.execute.return_value = mock_result

        result = await onboarding_service.start_onboarding(new_venue.id)

        assert result is not None
        assert new_venue.onboarding_status == OnboardingStatus.IN_PROGRESS
        assert new_venue.onboarding_started_at is not None

    @pytest.mark.asyncio
    async def test_start_onboarding_already_started(self, onboarding_service, mock_db_session, in_progress_venue):
        """Test starting already started onboarding."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = in_progress_venue
        mock_db_session.execute.return_value = mock_result

        result = await onboarding_service.start_onboarding(in_progress_venue.id)

        assert result is None

    @pytest.mark.asyncio
    async def test_start_onboarding_venue_not_found(self, onboarding_service, mock_db_session):
        """Test starting onboarding for non-existent venue."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await onboarding_service.start_onboarding(uuid.uuid4())

        assert result is None

    # -------------------------------------------------------------------------
    # Update Step Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_step_success(self, onboarding_service, mock_db_session, in_progress_venue):
        """Test updating onboarding step."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = in_progress_venue
        mock_db_session.execute.return_value = mock_result

        result = await onboarding_service.update_step(
            in_progress_venue.id,
            "hours",
            completed=True,
            data={"hours_set": True},
        )

        assert result is not None
        assert "hours" in result["steps_completed"]

    @pytest.mark.asyncio
    async def test_update_step_not_started(self, onboarding_service, mock_db_session, new_venue):
        """Test updating step for not started onboarding."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = new_venue
        mock_db_session.execute.return_value = mock_result

        result = await onboarding_service.update_step(
            new_venue.id,
            "basic_info",
            completed=True,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_update_step_invalid_step(self, onboarding_service, mock_db_session, in_progress_venue):
        """Test updating invalid step name."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = in_progress_venue
        mock_db_session.execute.return_value = mock_result

        result = await onboarding_service.update_step(
            in_progress_venue.id,
            "invalid_step",
            completed=True,
        )

        assert result is None

    # -------------------------------------------------------------------------
    # Complete Onboarding Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_complete_onboarding_success(self, onboarding_service, mock_db_session, venue_id):
        """Test completing onboarding when all required steps done."""
        # Create venue with all required steps completed
        all_required_steps = [s["name"] for s in ONBOARDING_STEPS if s["is_required"]]
        venue = Venue(
            id=venue_id,
            name="Ready FEC",
            slug="ready-fec",
            subscription_tier=SubscriptionTier.PRO,
            status=VenueStatus.PENDING,
            onboarding_status=OnboardingStatus.IN_PROGRESS,
            onboarding_started_at=datetime.utcnow(),
            onboarding_data={
                "completed_steps": all_required_steps,
                "step_data": {step: {"completed": True} for step in all_required_steps},
            },
            address_line1="123 Main St",
            city="Dallas",
            state="Texas",
            postal_code="75001",
            country="USA",
            timezone="America/Chicago",
            phone="+1-214-555-0100",
            email="test@fec.com",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = venue
        mock_db_session.execute.return_value = mock_result

        result = await onboarding_service.complete_onboarding(venue.id)

        assert result is not None
        assert venue.onboarding_status == OnboardingStatus.COMPLETED
        assert venue.status == VenueStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_complete_onboarding_missing_required(self, onboarding_service, mock_db_session, in_progress_venue):
        """Test completing onboarding with missing required steps."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = in_progress_venue
        mock_db_session.execute.return_value = mock_result

        result = await onboarding_service.complete_onboarding(in_progress_venue.id)

        assert result is None

    # -------------------------------------------------------------------------
    # Skip Step Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_skip_optional_step(self, onboarding_service, mock_db_session, in_progress_venue):
        """Test skipping optional step."""
        # Find an optional step
        optional_steps = [s["name"] for s in ONBOARDING_STEPS if not s["is_required"]]

        if optional_steps:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = in_progress_venue
            mock_db_session.execute.return_value = mock_result

            result = await onboarding_service.skip_step(in_progress_venue.id, optional_steps[0])

            assert result is not None

    @pytest.mark.asyncio
    async def test_skip_required_step_fails(self, onboarding_service, mock_db_session, in_progress_venue):
        """Test that skipping required step fails."""
        # Find a required step
        required_steps = [s["name"] for s in ONBOARDING_STEPS if s["is_required"]]

        if required_steps:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = in_progress_venue
            mock_db_session.execute.return_value = mock_result

            result = await onboarding_service.skip_step(in_progress_venue.id, required_steps[0])

            assert result is None

    # -------------------------------------------------------------------------
    # Reset Onboarding Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_reset_onboarding(self, onboarding_service, mock_db_session, in_progress_venue):
        """Test resetting onboarding."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = in_progress_venue
        mock_db_session.execute.return_value = mock_result

        result = await onboarding_service.reset_onboarding(in_progress_venue.id)

        assert result is not None
        assert in_progress_venue.onboarding_status == OnboardingStatus.NOT_STARTED
        assert in_progress_venue.onboarding_data is None

    # -------------------------------------------------------------------------
    # Validate Onboarding Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_validate_onboarding(self, onboarding_service, mock_db_session, in_progress_venue):
        """Test validating onboarding state."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = in_progress_venue
        mock_db_session.execute.return_value = mock_result

        result = await onboarding_service.validate_onboarding(in_progress_venue.id)

        assert "is_valid" in result
        assert "issues" in result
        assert "missing_required" in result

    # -------------------------------------------------------------------------
    # Get Detailed Progress Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_detailed_progress(self, onboarding_service, mock_db_session, in_progress_venue):
        """Test getting detailed onboarding progress."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = in_progress_venue
        mock_db_session.execute.return_value = mock_result

        result = await onboarding_service.get_detailed_progress(in_progress_venue.id)

        assert "venue_id" in result
        assert "status" in result
        assert "steps" in result
        assert "can_complete" in result
        assert "blocking_steps" in result
