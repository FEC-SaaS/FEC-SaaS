"""
=============================================================================
FILE: tests/integration/test_hours_api.py
PURPOSE: Integration tests for venue hours API endpoints
=============================================================================
"""

import uuid
import pytest
from httpx import AsyncClient


class TestHoursAPI:
    """Integration tests for /api/v1/venues/{venue_id}/hours endpoints."""

    # -------------------------------------------------------------------------
    # Get Hours Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_venue_hours_empty(self, client: AsyncClient, created_venue):
        """Test getting hours when none set."""
        response = await client.get(f"/api/v1/venues/{created_venue.id}/hours")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_venue_hours_with_data(self, client: AsyncClient, created_venue_with_hours):
        """Test getting hours with existing data."""
        response = await client.get(f"/api/v1/venues/{created_venue_with_hours.id}/hours")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 7  # 7 days of week

    # -------------------------------------------------------------------------
    # Set Hours Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_set_venue_hours(self, client: AsyncClient, created_venue, sample_hours_data):
        """Test setting venue hours."""
        response = await client.put(
            f"/api/v1/venues/{created_venue.id}/hours",
            json=sample_hours_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 7

    @pytest.mark.asyncio
    async def test_set_hours_replaces_existing(self, client: AsyncClient, created_venue_with_hours, sample_hours_data):
        """Test that setting hours replaces existing."""
        # Modify one day
        sample_hours_data[1]["open_time"] = "09:00:00"

        response = await client.put(
            f"/api/v1/venues/{created_venue_with_hours.id}/hours",
            json=sample_hours_data,
        )

        assert response.status_code == 200
        data = response.json()
        # Find Monday (day_of_week = 1)
        monday = next(h for h in data if h["day_of_week"] == 1)
        assert monday["open_time"] == "09:00:00"

    # -------------------------------------------------------------------------
    # Update Day Hours Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_day_hours(self, client: AsyncClient, created_venue_with_hours):
        """Test updating hours for specific day."""
        response = await client.patch(
            f"/api/v1/venues/{created_venue_with_hours.id}/hours/1",
            json={"open_time": "08:00:00"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["open_time"] == "08:00:00"

    @pytest.mark.asyncio
    async def test_update_day_hours_invalid_day(self, client: AsyncClient, created_venue):
        """Test updating hours for invalid day."""
        response = await client.patch(
            f"/api/v1/venues/{created_venue.id}/hours/7",  # Invalid: 0-6 only
            json={"open_time": "10:00:00"},
        )

        assert response.status_code == 400

    # -------------------------------------------------------------------------
    # Is Open Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_check_is_open(self, client: AsyncClient, created_venue_with_hours):
        """Test checking if venue is open."""
        response = await client.get(f"/api/v1/venues/{created_venue_with_hours.id}/is-open")

        assert response.status_code == 200
        data = response.json()
        assert "is_open" in data
        assert "venue_id" in data

    @pytest.mark.asyncio
    async def test_check_is_open_specific_time(self, client: AsyncClient, created_venue_with_hours):
        """Test checking if venue is open at specific time."""
        response = await client.get(
            f"/api/v1/venues/{created_venue_with_hours.id}/is-open"
            "?check_date=2025-01-27&check_time=14:00:00"
        )

        assert response.status_code == 200

    # -------------------------------------------------------------------------
    # Special Hours Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_special_hours(self, client: AsyncClient, created_venue):
        """Test getting special hours."""
        response = await client.get(f"/api/v1/venues/{created_venue.id}/hours/special")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_create_special_hours(self, client: AsyncClient, created_venue, sample_special_hours_data):
        """Test creating special hours."""
        response = await client.post(
            f"/api/v1/venues/{created_venue.id}/hours/special",
            json=sample_special_hours_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_special_hours_data["name"]

    @pytest.mark.asyncio
    async def test_delete_special_hours(self, client: AsyncClient, created_venue, sample_special_hours_data):
        """Test deleting special hours."""
        # First create
        create_response = await client.post(
            f"/api/v1/venues/{created_venue.id}/hours/special",
            json=sample_special_hours_data,
        )
        special_id = create_response.json()["id"]

        # Then delete
        response = await client.delete(
            f"/api/v1/venues/{created_venue.id}/hours/special/{special_id}"
        )

        assert response.status_code == 204
