"""
=============================================================================
FILE: tests/integration/test_features_api.py
PURPOSE: Integration tests for venue features API endpoints
=============================================================================
"""

import uuid
import pytest
from httpx import AsyncClient


class TestFeaturesAPI:
    """Integration tests for /api/v1/venues/{venue_id}/features endpoints."""

    # -------------------------------------------------------------------------
    # Get Features Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_venue_features_empty(self, client: AsyncClient, created_venue):
        """Test getting features when none enabled."""
        response = await client.get(f"/api/v1/venues/{created_venue.id}/features")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_venue_features_with_data(self, client: AsyncClient, created_venue_with_features):
        """Test getting features with existing data."""
        response = await client.get(f"/api/v1/venues/{created_venue_with_features.id}/features")

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

    # -------------------------------------------------------------------------
    # Get Available Features Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_available_features(self, client: AsyncClient, created_venue):
        """Test getting available features for tier."""
        response = await client.get(f"/api/v1/venues/{created_venue.id}/features/available")

        assert response.status_code == 200
        data = response.json()
        assert "available_features" in data
        assert "enabled_features" in data
        assert "can_enable" in data

    # -------------------------------------------------------------------------
    # Toggle Feature Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_toggle_feature_enable(self, client: AsyncClient, created_venue, sample_feature_toggle_data):
        """Test enabling a feature."""
        response = await client.post(
            f"/api/v1/venues/{created_venue.id}/features/bowling",
            json=sample_feature_toggle_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_enabled"] is True

    @pytest.mark.asyncio
    async def test_toggle_feature_disable(self, client: AsyncClient, created_venue_with_features):
        """Test disabling a feature."""
        response = await client.post(
            f"/api/v1/venues/{created_venue_with_features.id}/features/bowling",
            json={"enabled": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_enabled"] is False

    @pytest.mark.asyncio
    async def test_toggle_feature_with_config(self, client: AsyncClient, created_venue):
        """Test enabling feature with configuration."""
        response = await client.post(
            f"/api/v1/venues/{created_venue.id}/features/bowling",
            json={
                "enabled": True,
                "config": {"lanes": 24, "max_players_per_lane": 6},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["config"]["lanes"] == 24

    # -------------------------------------------------------------------------
    # Get Single Feature Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_single_feature(self, client: AsyncClient, created_venue_with_features):
        """Test getting single feature configuration."""
        response = await client.get(
            f"/api/v1/venues/{created_venue_with_features.id}/features/bowling"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["feature_name"] == "bowling"

    @pytest.mark.asyncio
    async def test_get_single_feature_not_found(self, client: AsyncClient, created_venue):
        """Test getting non-existent feature."""
        response = await client.get(
            f"/api/v1/venues/{created_venue.id}/features/nonexistent"
        )

        assert response.status_code == 404

    # -------------------------------------------------------------------------
    # Bulk Toggle Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_bulk_toggle_features(self, client: AsyncClient, created_venue):
        """Test bulk toggling features."""
        response = await client.put(
            f"/api/v1/venues/{created_venue.id}/features",
            json={
                "features": {
                    "bowling": True,
                    "arcade": True,
                    "pos": True,
                }
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "updated" in data
        assert "success" in data

    # -------------------------------------------------------------------------
    # Update Feature Config Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_feature_config(self, client: AsyncClient, created_venue_with_features):
        """Test updating feature configuration."""
        response = await client.patch(
            f"/api/v1/venues/{created_venue_with_features.id}/features/bowling/config",
            json={"lanes": 30, "max_players_per_lane": 8},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["config"]["lanes"] == 30
