"""
=============================================================================
FILE: tests/integration/test_settings_api.py
PURPOSE: Integration tests for venue settings API endpoints
=============================================================================
"""

import pytest
from httpx import AsyncClient


class TestSettingsAPI:
    """Integration tests for /api/v1/venues/{venue_id}/settings endpoints."""

    # -------------------------------------------------------------------------
    # Get Settings Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_venue_settings_empty(self, client: AsyncClient, created_venue):
        """Test getting settings when none exist."""
        response = await client.get(f"/api/v1/venues/{created_venue.id}/settings")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_settings_by_category(self, client: AsyncClient, created_venue):
        """Test getting settings filtered by category."""
        response = await client.get(
            f"/api/v1/venues/{created_venue.id}/settings?category=parties"
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_settings_include_sensitive(self, client: AsyncClient, created_venue):
        """Test getting settings including sensitive ones."""
        response = await client.get(
            f"/api/v1/venues/{created_venue.id}/settings?include_sensitive=true"
        )

        assert response.status_code == 200

    # -------------------------------------------------------------------------
    # Get Settings Dict Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_settings_dict(self, client: AsyncClient, created_venue):
        """Test getting settings as dictionary."""
        response = await client.get(f"/api/v1/venues/{created_venue.id}/settings/dict")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    # -------------------------------------------------------------------------
    # Create/Update Setting Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_setting(self, client: AsyncClient, created_venue, sample_setting_data):
        """Test creating a setting."""
        response = await client.post(
            f"/api/v1/venues/{created_venue.id}/settings/{sample_setting_data['setting_key']}",
            json=sample_setting_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["setting_key"] == sample_setting_data["setting_key"]
        assert data["setting_value"] == sample_setting_data["setting_value"]

    @pytest.mark.asyncio
    async def test_update_setting_via_post(self, client: AsyncClient, created_venue, sample_setting_data):
        """Test updating existing setting via POST."""
        # Create first
        await client.post(
            f"/api/v1/venues/{created_venue.id}/settings/{sample_setting_data['setting_key']}",
            json=sample_setting_data,
        )

        # Update
        updated_data = {**sample_setting_data, "setting_value": "100"}
        response = await client.post(
            f"/api/v1/venues/{created_venue.id}/settings/{sample_setting_data['setting_key']}",
            json=updated_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["setting_value"] == "100"

    # -------------------------------------------------------------------------
    # Get Single Setting Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_single_setting(self, client: AsyncClient, created_venue, sample_setting_data):
        """Test getting single setting."""
        # Create first
        await client.post(
            f"/api/v1/venues/{created_venue.id}/settings/{sample_setting_data['setting_key']}",
            json=sample_setting_data,
        )

        # Get
        response = await client.get(
            f"/api/v1/venues/{created_venue.id}/settings/{sample_setting_data['setting_key']}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["setting_key"] == sample_setting_data["setting_key"]

    @pytest.mark.asyncio
    async def test_get_single_setting_not_found(self, client: AsyncClient, created_venue):
        """Test getting non-existent setting."""
        response = await client.get(
            f"/api/v1/venues/{created_venue.id}/settings/nonexistent"
        )

        assert response.status_code == 404

    # -------------------------------------------------------------------------
    # Update Setting Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_setting(self, client: AsyncClient, created_venue, sample_setting_data):
        """Test updating setting via PATCH."""
        # Create first
        await client.post(
            f"/api/v1/venues/{created_venue.id}/settings/{sample_setting_data['setting_key']}",
            json=sample_setting_data,
        )

        # Update
        response = await client.patch(
            f"/api/v1/venues/{created_venue.id}/settings/{sample_setting_data['setting_key']}",
            json={"setting_value": "75", "description": "Updated description"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["setting_value"] == "75"
        assert data["description"] == "Updated description"

    # -------------------------------------------------------------------------
    # Delete Setting Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_setting(self, client: AsyncClient, created_venue, sample_setting_data):
        """Test deleting setting."""
        # Create first
        await client.post(
            f"/api/v1/venues/{created_venue.id}/settings/{sample_setting_data['setting_key']}",
            json=sample_setting_data,
        )

        # Delete
        response = await client.delete(
            f"/api/v1/venues/{created_venue.id}/settings/{sample_setting_data['setting_key']}"
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_setting_not_found(self, client: AsyncClient, created_venue):
        """Test deleting non-existent setting."""
        response = await client.delete(
            f"/api/v1/venues/{created_venue.id}/settings/nonexistent"
        )

        assert response.status_code == 404

    # -------------------------------------------------------------------------
    # Bulk Update Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_bulk_update_settings(self, client: AsyncClient, created_venue):
        """Test bulk updating settings."""
        response = await client.put(
            f"/api/v1/venues/{created_venue.id}/settings",
            json={
                "settings": {
                    "setting1": "value1",
                    "setting2": "value2",
                    "setting3": "value3",
                },
                "category": "test",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["updated"] == 3
