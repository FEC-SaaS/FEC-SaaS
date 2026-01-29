"""
=============================================================================
FILE: tests/test_api.py
PURPOSE: Integration tests for API endpoints
=============================================================================
"""

import pytest
import pytest_asyncio
from uuid import uuid4

from httpx import AsyncClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test basic health check endpoint."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_readiness_check(self, client: AsyncClient):
        """Test readiness check endpoint."""
        response = await client.get("/health/ready")

        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    @pytest.mark.asyncio
    async def test_liveness_check(self, client: AsyncClient):
        """Test liveness check endpoint."""
        response = await client.get("/health/live")

        assert response.status_code == 200
        assert response.json()["status"] == "alive"


class TestRootEndpoint:
    """Tests for root endpoint."""

    @pytest.mark.asyncio
    async def test_root(self, client: AsyncClient):
        """Test root endpoint returns service info."""
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "docs" in data


class TestSubscriptionEndpoints:
    """Tests for subscription API endpoints."""

    @pytest.mark.asyncio
    async def test_list_plans_unauthenticated(self, client: AsyncClient):
        """Test listing plans works without authentication."""
        venue_id = str(uuid4())
        response = await client.get(f"/api/v1/subscriptions/plans?venue_id={venue_id}")

        # Should return empty list for new venue
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_create_plan_requires_auth(self, client: AsyncClient):
        """Test that creating a plan requires authentication."""
        venue_id = str(uuid4())
        response = await client.post(
            f"/api/v1/subscriptions/plans?venue_id={venue_id}",
            json={
                "name": "Test Plan",
                "billing_interval": "monthly",
                "price": "29.99",
            },
        )

        assert response.status_code == 403  # Forbidden without auth

    @pytest.mark.asyncio
    async def test_create_plan_with_auth(
        self, client: AsyncClient, admin_jwt_token: str, admin_user: dict
    ):
        """Test creating a plan with authentication."""
        venue_id = str(admin_user["venue_id"])

        response = await client.post(
            f"/api/v1/subscriptions/plans?venue_id={venue_id}",
            json={
                "name": "Premium Plan",
                "description": "Full access membership",
                "billing_interval": "monthly",
                "price": "49.99",
                "currency": "USD",
                "trial_days": 7,
            },
            headers={"Authorization": f"Bearer {admin_jwt_token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Premium Plan"
        assert data["price"] == "49.99"


class TestLoyaltyEndpoints:
    """Tests for loyalty API endpoints."""

    @pytest.mark.asyncio
    async def test_get_program_not_found(self, client: AsyncClient):
        """Test getting non-existent program returns 404."""
        program_id = str(uuid4())
        response = await client.get(f"/api/v1/loyalty/programs/{program_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_enroll_requires_auth(self, client: AsyncClient):
        """Test enrolling in loyalty program requires auth."""
        program_id = str(uuid4())
        response = await client.post(
            f"/api/v1/loyalty/accounts/enroll?program_id={program_id}"
        )

        assert response.status_code == 403


class TestRewardsEndpoints:
    """Tests for rewards API endpoints."""

    @pytest.mark.asyncio
    async def test_list_rewards(self, client: AsyncClient):
        """Test listing rewards catalog."""
        venue_id = str(uuid4())
        response = await client.get(f"/api/v1/rewards/catalog?venue_id={venue_id}")

        assert response.status_code == 200
        assert response.json() == []  # Empty for new venue

    @pytest.mark.asyncio
    async def test_redeem_requires_auth(self, client: AsyncClient):
        """Test reward redemption requires authentication."""
        account_id = str(uuid4())
        response = await client.post(
            f"/api/v1/rewards/redeem?account_id={account_id}",
            json={
                "reward_id": str(uuid4()),
            },
        )

        assert response.status_code == 403


class TestTierEndpoints:
    """Tests for membership tier endpoints."""

    @pytest.mark.asyncio
    async def test_list_tiers(self, client: AsyncClient):
        """Test listing membership tiers."""
        venue_id = str(uuid4())
        response = await client.get(f"/api/v1/tiers?venue_id={venue_id}")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_tier_not_found(self, client: AsyncClient):
        """Test getting non-existent tier returns 404."""
        tier_id = str(uuid4())
        response = await client.get(f"/api/v1/tiers/{tier_id}")

        assert response.status_code == 404


class TestReferralEndpoints:
    """Tests for referral API endpoints."""

    @pytest.mark.asyncio
    async def test_validate_invalid_code(self, client: AsyncClient):
        """Test validating an invalid referral code."""
        response = await client.get("/api/v1/referrals/validate/INVALID123")

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False

    @pytest.mark.asyncio
    async def test_create_referral_requires_auth(self, client: AsyncClient):
        """Test creating referral code requires auth."""
        venue_id = str(uuid4())
        response = await client.post(
            f"/api/v1/referrals/code?venue_id={venue_id}"
        )

        assert response.status_code == 403


class TestCorporateEndpoints:
    """Tests for corporate subscription endpoints."""

    @pytest.mark.asyncio
    async def test_check_employee_access_not_found(self, client: AsyncClient):
        """Test checking access for unknown employee."""
        response = await client.get(
            "/api/v1/corporate/check-access/unknown@example.com"
        )

        assert response.status_code == 200
        assert response.json()["has_access"] is False
