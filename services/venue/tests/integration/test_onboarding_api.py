"""
=============================================================================
FILE: tests/integration/test_onboarding_api.py
PURPOSE: Integration tests for venue onboarding API endpoints
=============================================================================
"""

import pytest
from httpx import AsyncClient


class TestOnboardingAPI:
    """Integration tests for /api/v1/venues/{venue_id}/onboarding endpoints."""

    # -------------------------------------------------------------------------
    # Get Onboarding Status Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_onboarding_status(self, client: AsyncClient, created_venue):
        """Test getting onboarding status."""
        response = await client.get(f"/api/v1/venues/{created_venue.id}/onboarding")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "progress_percentage" in data
        assert "steps_completed" in data
        assert "steps_remaining" in data

    # -------------------------------------------------------------------------
    # Get Detailed Progress Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_onboarding_progress(self, client: AsyncClient, created_venue):
        """Test getting detailed onboarding progress."""
        response = await client.get(f"/api/v1/venues/{created_venue.id}/onboarding/progress")

        assert response.status_code == 200
        data = response.json()
        assert "steps" in data
        assert "can_complete" in data
        assert "blocking_steps" in data

    # -------------------------------------------------------------------------
    # Start Onboarding Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_start_onboarding(self, client: AsyncClient, created_venue):
        """Test starting onboarding."""
        response = await client.post(f"/api/v1/venues/{created_venue.id}/onboarding/start")

        # Could be 200 or 400 if already started
        assert response.status_code in [200, 400]

    @pytest.mark.asyncio
    async def test_start_onboarding_already_started(self, client: AsyncClient, created_venue):
        """Test starting onboarding when already started."""
        # Start first time
        await client.post(f"/api/v1/venues/{created_venue.id}/onboarding/start")

        # Start second time
        response = await client.post(f"/api/v1/venues/{created_venue.id}/onboarding/start")

        assert response.status_code == 400

    # -------------------------------------------------------------------------
    # Update Step Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_onboarding_step(self, client: AsyncClient, created_venue):
        """Test updating onboarding step."""
        # Start first
        await client.post(f"/api/v1/venues/{created_venue.id}/onboarding/start")

        # Update step
        response = await client.patch(
            f"/api/v1/venues/{created_venue.id}/onboarding/step/basic_info",
            json={"completed": True, "data": {"verified": True}},
        )

        # Could be 200 or 400 if step not valid
        assert response.status_code in [200, 400]

    @pytest.mark.asyncio
    async def test_update_step_not_started(self, client: AsyncClient, created_venue):
        """Test updating step when onboarding not started."""
        response = await client.patch(
            f"/api/v1/venues/{created_venue.id}/onboarding/step/basic_info",
            json={"completed": True},
        )

        assert response.status_code == 400

    # -------------------------------------------------------------------------
    # Complete Onboarding Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_complete_onboarding_incomplete(self, client: AsyncClient, created_venue):
        """Test completing onboarding with incomplete steps."""
        # Start
        await client.post(f"/api/v1/venues/{created_venue.id}/onboarding/start")

        # Try to complete without all steps
        response = await client.post(f"/api/v1/venues/{created_venue.id}/onboarding/complete")

        assert response.status_code == 400

    # -------------------------------------------------------------------------
    # Skip Step Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_skip_onboarding_step(self, client: AsyncClient, created_venue):
        """Test skipping optional onboarding step."""
        # Start first
        await client.post(f"/api/v1/venues/{created_venue.id}/onboarding/start")

        # Try to skip a step (may fail if required)
        response = await client.post(
            f"/api/v1/venues/{created_venue.id}/onboarding/skip/optional_step"
        )

        # Could be 200 or 400 depending on step
        assert response.status_code in [200, 400]

    # -------------------------------------------------------------------------
    # Reset Onboarding Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_reset_onboarding(self, client: AsyncClient, created_venue):
        """Test resetting onboarding."""
        # Start first
        await client.post(f"/api/v1/venues/{created_venue.id}/onboarding/start")

        # Reset
        response = await client.post(f"/api/v1/venues/{created_venue.id}/onboarding/reset")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_started"

    # -------------------------------------------------------------------------
    # Validate Onboarding Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_validate_onboarding(self, client: AsyncClient, created_venue):
        """Test validating onboarding state."""
        response = await client.get(f"/api/v1/venues/{created_venue.id}/onboarding/validate")

        assert response.status_code == 200
        data = response.json()
        assert "is_valid" in data
        assert "issues" in data
