"""
=============================================================================
FILE: tests/integration/test_packages_api.py
PURPOSE: Integration tests for Party Packages API endpoints
=============================================================================
"""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.models.party import PartyPackage, PartyAddon, PackageType


class TestPackagesAPICreate:
    """Integration tests for POST /api/v1/packages endpoint."""

    @pytest.mark.asyncio
    async def test_create_package_success(
        self,
        async_client: AsyncClient,
        valid_package_data: dict,
        auth_headers: dict,
    ):
        """Test successful package creation."""
        response = await async_client.post(
            "/api/v1/packages/",
            json=valid_package_data,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["package_name"] == valid_package_data["package_name"]
        assert data["package_type"] == valid_package_data["package_type"]
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_package_missing_required_field(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_venue_id: uuid.UUID,
    ):
        """Test package creation fails without required fields."""
        incomplete_data = {
            "venue_id": str(sample_venue_id),
            # Missing package_name and base_price
        }

        response = await async_client.post(
            "/api/v1/packages/",
            json=incomplete_data,
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_package_invalid_price(
        self,
        async_client: AsyncClient,
        valid_package_data: dict,
        auth_headers: dict,
    ):
        """Test package creation fails with negative price."""
        valid_package_data["base_price"] = "-100.00"

        response = await async_client.post(
            "/api/v1/packages/",
            json=valid_package_data,
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_package_invalid_guest_range(
        self,
        async_client: AsyncClient,
        valid_package_data: dict,
        auth_headers: dict,
    ):
        """Test package creation fails when max_guests < min_guests."""
        valid_package_data["min_guests"] = 20
        valid_package_data["max_guests"] = 10

        response = await async_client.post(
            "/api/v1/packages/",
            json=valid_package_data,
            headers=auth_headers,
        )

        assert response.status_code == 422


class TestPackagesAPIGet:
    """Integration tests for GET /api/v1/packages endpoints."""

    @pytest.mark.asyncio
    async def test_get_package_success(
        self,
        async_client: AsyncClient,
        sample_package: PartyPackage,
        auth_headers: dict,
    ):
        """Test successful package retrieval."""
        response = await async_client.get(
            f"/api/v1/packages/{sample_package.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_package.id)
        assert data["package_name"] == sample_package.package_name

    @pytest.mark.asyncio
    async def test_get_package_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test package retrieval when not found."""
        random_id = uuid.uuid4()
        response = await async_client.get(
            f"/api/v1/packages/{random_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_packages_success(
        self,
        async_client: AsyncClient,
        sample_package: PartyPackage,
        sample_venue_id: uuid.UUID,
        auth_headers: dict,
    ):
        """Test listing packages."""
        response = await async_client.get(
            f"/api/v1/packages/?venue_id={sample_venue_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "packages" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_packages_with_pagination(
        self,
        async_client: AsyncClient,
        sample_venue_id: uuid.UUID,
        auth_headers: dict,
    ):
        """Test packages list pagination."""
        response = await async_client.get(
            f"/api/v1/packages/?venue_id={sample_venue_id}&page=1&page_size=5",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    @pytest.mark.asyncio
    async def test_list_packages_filter_by_type(
        self,
        async_client: AsyncClient,
        sample_package: PartyPackage,
        sample_venue_id: uuid.UUID,
        auth_headers: dict,
    ):
        """Test filtering packages by type."""
        response = await async_client.get(
            f"/api/v1/packages/?venue_id={sample_venue_id}&package_type=birthday",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        for package in data["packages"]:
            assert package["package_type"] == "birthday"


class TestPackagesAPIUpdate:
    """Integration tests for PUT /api/v1/packages/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_package_success(
        self,
        async_client: AsyncClient,
        sample_package: PartyPackage,
        auth_headers: dict,
    ):
        """Test successful package update."""
        update_data = {
            "package_name": "Updated Party Package",
            "base_price": "399.99",
        }

        response = await async_client.put(
            f"/api/v1/packages/{sample_package.id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["package_name"] == "Updated Party Package"
        assert data["base_price"] == "399.99"

    @pytest.mark.asyncio
    async def test_update_package_partial(
        self,
        async_client: AsyncClient,
        sample_package: PartyPackage,
        auth_headers: dict,
    ):
        """Test partial package update."""
        update_data = {
            "is_featured": True,
        }

        response = await async_client.put(
            f"/api/v1/packages/{sample_package.id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_featured"] is True
        assert data["package_name"] == sample_package.package_name

    @pytest.mark.asyncio
    async def test_update_package_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test update when package doesn't exist."""
        random_id = uuid.uuid4()
        update_data = {"package_name": "New Name"}

        response = await async_client.put(
            f"/api/v1/packages/{random_id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestPackagesAPIDelete:
    """Integration tests for DELETE /api/v1/packages/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_package_success(
        self,
        async_client: AsyncClient,
        sample_package: PartyPackage,
        auth_headers: dict,
    ):
        """Test successful package deletion."""
        response = await async_client.delete(
            f"/api/v1/packages/{sample_package.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_package_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test delete when package doesn't exist."""
        random_id = uuid.uuid4()
        response = await async_client.delete(
            f"/api/v1/packages/{random_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestPackagesAPIAddons:
    """Integration tests for package addon endpoints."""

    @pytest.mark.asyncio
    async def test_get_package_addons(
        self,
        async_client: AsyncClient,
        sample_package: PartyPackage,
        auth_headers: dict,
    ):
        """Test getting package addons."""
        response = await async_client.get(
            f"/api/v1/packages/{sample_package.id}/addons",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_add_addon_to_package(
        self,
        async_client: AsyncClient,
        sample_package: PartyPackage,
        sample_addon: PartyAddon,
        auth_headers: dict,
    ):
        """Test adding addon to package."""
        response = await async_client.post(
            f"/api/v1/packages/{sample_package.id}/addons/{sample_addon.id}",
            json={"quantity": 1, "is_included_free": True},
            headers=auth_headers,
        )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_remove_addon_from_package(
        self,
        async_client: AsyncClient,
        sample_package: PartyPackage,
        sample_addon: PartyAddon,
        auth_headers: dict,
    ):
        """Test removing addon from package."""
        # First add the addon
        await async_client.post(
            f"/api/v1/packages/{sample_package.id}/addons/{sample_addon.id}",
            json={"quantity": 1, "is_included_free": True},
            headers=auth_headers,
        )

        # Then remove it
        response = await async_client.delete(
            f"/api/v1/packages/{sample_package.id}/addons/{sample_addon.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204


class TestPackagesAPISpecialOperations:
    """Integration tests for special package operations."""

    @pytest.mark.asyncio
    async def test_toggle_package_active(
        self,
        async_client: AsyncClient,
        sample_package: PartyPackage,
        auth_headers: dict,
    ):
        """Test toggling package active status."""
        original_status = sample_package.is_active

        response = await async_client.post(
            f"/api/v1/packages/{sample_package.id}/toggle-active",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] != original_status

    @pytest.mark.asyncio
    async def test_clone_package(
        self,
        async_client: AsyncClient,
        sample_package: PartyPackage,
        auth_headers: dict,
    ):
        """Test cloning a package."""
        response = await async_client.post(
            f"/api/v1/packages/{sample_package.id}/clone",
            json={"new_name": "Cloned Package"},
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["package_name"] == "Cloned Package"
        assert data["id"] != str(sample_package.id)
