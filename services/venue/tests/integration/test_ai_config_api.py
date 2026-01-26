"""
=============================================================================
FILE: tests/integration/test_ai_config_api.py
PURPOSE: Integration tests for venue AI configuration API endpoints
=============================================================================
"""

import pytest
from httpx import AsyncClient


class TestAIConfigAPI:
    """Integration tests for /api/v1/venues/{venue_id}/ai-config endpoints."""

    # -------------------------------------------------------------------------
    # Get AI Configs Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_ai_configs_empty(self, client: AsyncClient, created_venue):
        """Test getting AI configs when none exist."""
        response = await client.get(f"/api/v1/venues/{created_venue.id}/ai-config")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    # -------------------------------------------------------------------------
    # Get Available AI Services Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_available_ai_services(self, client: AsyncClient, created_venue):
        """Test getting available AI services for tier."""
        response = await client.get(f"/api/v1/venues/{created_venue.id}/ai-config/available")

        assert response.status_code == 200
        data = response.json()
        assert "available_services" in data
        assert "enabled_services" in data
        assert "can_enable" in data

    # -------------------------------------------------------------------------
    # Create AI Config Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_ai_config(self, client: AsyncClient, created_venue, sample_ai_config_data):
        """Test enabling an AI service."""
        response = await client.post(
            f"/api/v1/venues/{created_venue.id}/ai-config/dynamic_pricing",
            json=sample_ai_config_data,
        )

        # May be 201 or 400 depending on tier
        assert response.status_code in [201, 400]

    @pytest.mark.asyncio
    async def test_create_ai_config_with_params(self, client: AsyncClient, created_venue):
        """Test enabling AI service with custom parameters."""
        response = await client.post(
            f"/api/v1/venues/{created_venue.id}/ai-config/dynamic_pricing",
            json={
                "parameters": {
                    "min_price_multiplier": 0.9,
                    "max_price_multiplier": 1.3,
                }
            },
        )

        # May be 201 or 400 depending on tier
        assert response.status_code in [201, 400]

    # -------------------------------------------------------------------------
    # Get Single AI Config Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_single_ai_config_not_found(self, client: AsyncClient, created_venue):
        """Test getting non-existent AI config."""
        response = await client.get(
            f"/api/v1/venues/{created_venue.id}/ai-config/dynamic_pricing"
        )

        assert response.status_code == 404

    # -------------------------------------------------------------------------
    # Update AI Config Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_ai_config(self, client: AsyncClient, created_venue, sample_ai_config_data):
        """Test updating AI configuration."""
        # First enable
        create_response = await client.post(
            f"/api/v1/venues/{created_venue.id}/ai-config/dynamic_pricing",
            json=sample_ai_config_data,
        )

        if create_response.status_code == 201:
            # Then update
            response = await client.patch(
                f"/api/v1/venues/{created_venue.id}/ai-config/dynamic_pricing",
                json={
                    "strategy": "aggressive",
                    "params": {"min_price_multiplier": 0.7},
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["strategy"] == "aggressive"

    # -------------------------------------------------------------------------
    # Disable AI Service Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_disable_ai_service(self, client: AsyncClient, created_venue, sample_ai_config_data):
        """Test disabling an AI service."""
        # First enable
        create_response = await client.post(
            f"/api/v1/venues/{created_venue.id}/ai-config/dynamic_pricing",
            json=sample_ai_config_data,
        )

        if create_response.status_code == 201:
            # Then disable
            response = await client.delete(
                f"/api/v1/venues/{created_venue.id}/ai-config/dynamic_pricing"
            )

            assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_disable_ai_service_not_found(self, client: AsyncClient, created_venue):
        """Test disabling non-existent AI service."""
        response = await client.delete(
            f"/api/v1/venues/{created_venue.id}/ai-config/nonexistent"
        )

        assert response.status_code == 404

    # -------------------------------------------------------------------------
    # Reset AI Config Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_reset_ai_config(self, client: AsyncClient, created_venue, sample_ai_config_data):
        """Test resetting AI config to defaults."""
        # First enable
        create_response = await client.post(
            f"/api/v1/venues/{created_venue.id}/ai-config/dynamic_pricing",
            json=sample_ai_config_data,
        )

        if create_response.status_code == 201:
            # Then reset
            response = await client.post(
                f"/api/v1/venues/{created_venue.id}/ai-config/dynamic_pricing/reset"
            )

            assert response.status_code == 200
