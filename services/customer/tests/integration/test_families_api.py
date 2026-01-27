"""
=============================================================================
FILE: tests/integration/test_families_api.py
PURPOSE: Integration tests for Family API endpoints
=============================================================================
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import FamilyFactory


class TestFamilyListEndpoint:
    """Tests for GET /api/v1/families/"""

    @pytest.mark.asyncio
    async def test_list_families_success(
        self, client: AsyncClient, sample_family, sample_venue_id
    ):
        """Test listing families for a venue."""
        response = await client.get(
            f"/api/v1/families/?venue_id={sample_venue_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_list_families_with_pagination(
        self, client: AsyncClient, sample_venue_id
    ):
        """Test listing families with limit and offset."""
        response = await client.get(
            f"/api/v1/families/?venue_id={sample_venue_id}&limit=10&offset=0"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_families_empty_venue(self, client: AsyncClient):
        """Test listing families for venue with no families."""
        response = await client.get(
            f"/api/v1/families/?venue_id={uuid4()}"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0


class TestFamilyCreateEndpoint:
    """Tests for POST /api/v1/families/"""

    @pytest.mark.asyncio
    async def test_create_family_success(self, client: AsyncClient, sample_venue_id):
        """Test creating a new family."""
        family_data = FamilyFactory.create_dict(
            venue_id=sample_venue_id,
            family_name="New Test Family",
        )

        response = await client.post(
            "/api/v1/families/",
            json=family_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["family_name"] == "New Test Family"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_family_with_notes(self, client: AsyncClient, sample_venue_id):
        """Test creating family with additional fields."""
        family_data = {
            "venue_id": sample_venue_id,
            "family_name": "Family With Notes",
            "address": "123 Test Street",
            "notes": "Premium family",
        }

        response = await client.post(
            "/api/v1/families/",
            json=family_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["notes"] == "Premium family"

    @pytest.mark.asyncio
    async def test_create_family_invalid_data(self, client: AsyncClient):
        """Test creating family with invalid data fails."""
        response = await client.post(
            "/api/v1/families/",
            json={"invalid": "data"},
        )

        assert response.status_code == 422


class TestFamilyGetEndpoint:
    """Tests for GET /api/v1/families/{family_id}"""

    @pytest.mark.asyncio
    async def test_get_family_success(self, client: AsyncClient, sample_family):
        """Test getting family by ID."""
        response = await client.get(f"/api/v1/families/{sample_family.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_family.id)
        assert data["family_name"] == sample_family.family_name

    @pytest.mark.asyncio
    async def test_get_family_not_found(self, client: AsyncClient):
        """Test getting non-existent family returns 404."""
        response = await client.get(f"/api/v1/families/{uuid4()}")

        assert response.status_code == 404


class TestFamilyUpdateEndpoint:
    """Tests for PUT /api/v1/families/{family_id}"""

    @pytest.mark.asyncio
    async def test_update_family_success(self, client: AsyncClient, sample_family):
        """Test updating family information."""
        update_data = {
            "family_name": "Updated Family Name",
            "notes": "Updated notes",
        }

        response = await client.put(
            f"/api/v1/families/{sample_family.id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["family_name"] == "Updated Family Name"
        assert data["notes"] == "Updated notes"

    @pytest.mark.asyncio
    async def test_update_family_partial(self, client: AsyncClient, sample_family):
        """Test partial update of family."""
        response = await client.put(
            f"/api/v1/families/{sample_family.id}",
            json={"notes": "Only notes changed"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == "Only notes changed"
        assert data["family_name"] == sample_family.family_name

    @pytest.mark.asyncio
    async def test_update_family_not_found(self, client: AsyncClient):
        """Test updating non-existent family returns 404."""
        response = await client.put(
            f"/api/v1/families/{uuid4()}",
            json={"family_name": "Test"},
        )

        assert response.status_code == 404


class TestFamilyDeleteEndpoint:
    """Tests for DELETE /api/v1/families/{family_id}"""

    @pytest.mark.asyncio
    async def test_delete_family_success(self, client: AsyncClient, sample_family):
        """Test deleting a family."""
        response = await client.delete(f"/api/v1/families/{sample_family.id}")

        assert response.status_code == 204

        # Verify family is deleted
        get_response = await client.get(f"/api/v1/families/{sample_family.id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_family_not_found(self, client: AsyncClient):
        """Test deleting non-existent family returns 404."""
        response = await client.delete(f"/api/v1/families/{uuid4()}")

        assert response.status_code == 404


class TestFamilyMemberEndpoints:
    """Tests for family member management endpoints."""

    @pytest.mark.asyncio
    async def test_add_family_member_success(
        self, client: AsyncClient, sample_family, sample_customer
    ):
        """Test adding a member to a family."""
        member_data = {
            "customer_id": str(sample_customer.id),
            "role": "primary",
        }

        response = await client.post(
            f"/api/v1/families/{sample_family.id}/members",
            json=member_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["customer_id"] == str(sample_customer.id)
        assert data["role"] == "primary"

    @pytest.mark.asyncio
    async def test_add_family_member_child(
        self, client: AsyncClient, sample_family, sample_customers
    ):
        """Test adding a child member to a family."""
        member_data = {
            "customer_id": str(sample_customers[0].id),
            "role": "child",
        }

        response = await client.post(
            f"/api/v1/families/{sample_family.id}/members",
            json=member_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "child"

    @pytest.mark.asyncio
    async def test_add_member_to_nonexistent_family(
        self, client: AsyncClient, sample_customer
    ):
        """Test adding member to non-existent family fails."""
        member_data = {
            "customer_id": str(sample_customer.id),
            "role": "member",
        }

        response = await client.post(
            f"/api/v1/families/{uuid4()}/members",
            json=member_data,
        )

        # Should return 400 or 404
        assert response.status_code in [400, 404]

    @pytest.mark.asyncio
    async def test_remove_family_member_success(
        self, client: AsyncClient, sample_family, sample_customer
    ):
        """Test removing a member from a family."""
        # First add the member
        member_data = {
            "customer_id": str(sample_customer.id),
            "role": "member",
        }
        add_response = await client.post(
            f"/api/v1/families/{sample_family.id}/members",
            json=member_data,
        )
        member_id = add_response.json()["id"]

        # Remove the member
        response = await client.delete(
            f"/api/v1/families/{sample_family.id}/members/{member_id}"
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_remove_nonexistent_member(self, client: AsyncClient, sample_family):
        """Test removing non-existent member returns 404."""
        response = await client.delete(
            f"/api/v1/families/{sample_family.id}/members/{uuid4()}"
        )

        assert response.status_code == 404


class TestFamilyMemberRoles:
    """Tests for different family member roles."""

    @pytest.mark.asyncio
    async def test_add_primary_member(
        self, client: AsyncClient, sample_family, sample_customers
    ):
        """Test adding primary role member."""
        response = await client.post(
            f"/api/v1/families/{sample_family.id}/members",
            json={
                "customer_id": str(sample_customers[0].id),
                "role": "primary",
            },
        )

        assert response.status_code == 201
        assert response.json()["role"] == "primary"

    @pytest.mark.asyncio
    async def test_add_guardian_member(
        self, client: AsyncClient, sample_family, sample_customers
    ):
        """Test adding guardian role member."""
        response = await client.post(
            f"/api/v1/families/{sample_family.id}/members",
            json={
                "customer_id": str(sample_customers[0].id),
                "role": "guardian",
            },
        )

        assert response.status_code == 201
        assert response.json()["role"] == "guardian"

    @pytest.mark.asyncio
    async def test_add_multiple_members(
        self, client: AsyncClient, sample_family, sample_customers
    ):
        """Test adding multiple members to a family."""
        roles = ["primary", "guardian", "child", "member"]

        for i, (customer, role) in enumerate(zip(sample_customers[:4], roles)):
            response = await client.post(
                f"/api/v1/families/{sample_family.id}/members",
                json={
                    "customer_id": str(customer.id),
                    "role": role,
                },
            )
            assert response.status_code == 201
