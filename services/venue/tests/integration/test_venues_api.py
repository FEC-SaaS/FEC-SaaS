"""
=============================================================================
FILE: tests/integration/test_venues_api.py
PURPOSE: Integration tests for venue API endpoints
=============================================================================
"""

import uuid
import pytest
from httpx import AsyncClient


class TestVenuesAPI:
    """Integration tests for /api/v1/venues endpoints."""

    # -------------------------------------------------------------------------
    # List Venues Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_venues_empty(self, client: AsyncClient):
        """Test listing venues when none exist."""
        response = await client.get("/api/v1/venues")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["venues"] == []

    @pytest.mark.asyncio
    async def test_list_venues_with_data(self, client: AsyncClient, created_venue):
        """Test listing venues with existing data."""
        response = await client.get("/api/v1/venues")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["venues"]) >= 1

    @pytest.mark.asyncio
    async def test_list_venues_pagination(self, client: AsyncClient):
        """Test venue list pagination."""
        response = await client.get("/api/v1/venues?page=1&page_size=5")

        assert response.status_code == 200
        data = response.json()
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data

    @pytest.mark.asyncio
    async def test_list_venues_filter_by_status(self, client: AsyncClient, created_venue):
        """Test filtering venues by status."""
        response = await client.get("/api/v1/venues?status=active")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_venues_filter_by_city(self, client: AsyncClient, created_venue):
        """Test filtering venues by city."""
        response = await client.get("/api/v1/venues?city=Dallas")

        assert response.status_code == 200

    # -------------------------------------------------------------------------
    # Create Venue Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_venue_success(self, client: AsyncClient, sample_venue_data):
        """Test successful venue creation."""
        response = await client.post("/api/v1/venues", json=sample_venue_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_venue_data["name"]
        assert "id" in data
        assert "slug" in data

    @pytest.mark.asyncio
    async def test_create_venue_with_custom_slug(self, client: AsyncClient, sample_venue_data):
        """Test venue creation with custom slug."""
        sample_venue_data["slug"] = "my-custom-slug"
        response = await client.post("/api/v1/venues", json=sample_venue_data)

        assert response.status_code == 201
        data = response.json()
        assert data["slug"] == "my-custom-slug"

    @pytest.mark.asyncio
    async def test_create_venue_missing_required_fields(self, client: AsyncClient):
        """Test venue creation with missing required fields."""
        incomplete_data = {"name": "Test FEC"}  # Missing required fields

        response = await client.post("/api/v1/venues", json=incomplete_data)

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_create_venue_invalid_email(self, client: AsyncClient, sample_venue_data):
        """Test venue creation with invalid email."""
        sample_venue_data["email"] = "invalid-email"

        response = await client.post("/api/v1/venues", json=sample_venue_data)

        assert response.status_code == 422

    # -------------------------------------------------------------------------
    # Get Venue Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_venue_by_id(self, client: AsyncClient, created_venue):
        """Test getting venue by ID."""
        response = await client.get(f"/api/v1/venues/{created_venue.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(created_venue.id)
        assert data["name"] == created_venue.name

    @pytest.mark.asyncio
    async def test_get_venue_not_found(self, client: AsyncClient):
        """Test getting non-existent venue."""
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/v1/venues/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_venue_by_slug(self, client: AsyncClient, created_venue):
        """Test getting venue by slug."""
        response = await client.get(f"/api/v1/venues/slug/{created_venue.slug}")

        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == created_venue.slug

    @pytest.mark.asyncio
    async def test_get_venue_includes_related_data(self, client: AsyncClient, created_venue_with_hours):
        """Test that venue detail includes related data."""
        response = await client.get(f"/api/v1/venues/{created_venue_with_hours.id}")

        assert response.status_code == 200
        data = response.json()
        assert "hours" in data

    # -------------------------------------------------------------------------
    # Update Venue Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_venue_success(self, client: AsyncClient, created_venue, sample_venue_update_data):
        """Test successful venue update."""
        response = await client.put(
            f"/api/v1/venues/{created_venue.id}",
            json=sample_venue_update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_venue_update_data["name"]

    @pytest.mark.asyncio
    async def test_update_venue_partial(self, client: AsyncClient, created_venue):
        """Test partial venue update."""
        update_data = {"description": "New description only"}

        response = await client.put(
            f"/api/v1/venues/{created_venue.id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "New description only"
        assert data["name"] == created_venue.name  # Name unchanged

    @pytest.mark.asyncio
    async def test_update_venue_not_found(self, client: AsyncClient, sample_venue_update_data):
        """Test updating non-existent venue."""
        fake_id = uuid.uuid4()
        response = await client.put(
            f"/api/v1/venues/{fake_id}",
            json=sample_venue_update_data,
        )

        assert response.status_code == 404

    # -------------------------------------------------------------------------
    # Delete Venue Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_venue_soft(self, client: AsyncClient, created_venue):
        """Test soft delete venue."""
        response = await client.delete(f"/api/v1/venues/{created_venue.id}")

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_venue_hard(self, client: AsyncClient, created_venue):
        """Test hard delete venue."""
        response = await client.delete(
            f"/api/v1/venues/{created_venue.id}?hard_delete=true"
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_venue_not_found(self, client: AsyncClient):
        """Test deleting non-existent venue."""
        fake_id = uuid.uuid4()
        response = await client.delete(f"/api/v1/venues/{fake_id}")

        assert response.status_code == 404

    # -------------------------------------------------------------------------
    # Status Update Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_venue_status(self, client: AsyncClient, created_venue):
        """Test updating venue status."""
        response = await client.patch(
            f"/api/v1/venues/{created_venue.id}/status?new_status=suspended"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "suspended"

    # -------------------------------------------------------------------------
    # Franchise Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_franchise_venues(self, client: AsyncClient):
        """Test listing venues by franchise."""
        franchise_id = uuid.uuid4()
        response = await client.get(f"/api/v1/venues/franchise/{franchise_id}")

        assert response.status_code == 200

    # -------------------------------------------------------------------------
    # Bulk Operations Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_bulk_create_venues(self, client: AsyncClient, sample_venue_data):
        """Test bulk venue creation."""
        venues = [
            {**sample_venue_data, "name": f"FEC {i}", "email": f"fec{i}@test.com"}
            for i in range(3)
        ]

        response = await client.post(
            "/api/v1/venues/bulk",
            json={"venues": venues},
        )

        assert response.status_code == 201
        data = response.json()
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_bulk_update_venues(self, client: AsyncClient, created_venue):
        """Test bulk venue update."""
        response = await client.patch(
            "/api/v1/venues/bulk",
            json={
                "venue_ids": [str(created_venue.id)],
                "update": {"description": "Bulk updated"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "updated" in data

    # -------------------------------------------------------------------------
    # Health Check Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
