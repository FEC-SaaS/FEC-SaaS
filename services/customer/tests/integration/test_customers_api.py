"""
=============================================================================
FILE: tests/integration/test_customers_api.py
PURPOSE: Integration tests for Customer API endpoints
=============================================================================
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import CustomerFactory


class TestCustomerListEndpoint:
    """Tests for GET /api/v1/customers/"""

    @pytest.mark.asyncio
    async def test_list_customers_success(
        self, client: AsyncClient, sample_customers, sample_venue_id
    ):
        """Test listing customers returns paginated results."""
        response = await client.get(
            f"/api/v1/customers/?venue_id={sample_venue_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert "customers" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        assert len(data["customers"]) >= 1

    @pytest.mark.asyncio
    async def test_list_customers_pagination(
        self, client: AsyncClient, sample_customers, sample_venue_id
    ):
        """Test pagination parameters work correctly."""
        response = await client.get(
            f"/api/v1/customers/?venue_id={sample_venue_id}&page=1&page_size=2"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["customers"]) <= 2
        assert data["page"] == 1
        assert data["page_size"] == 2

    @pytest.mark.asyncio
    async def test_list_customers_filter_by_type(
        self, client: AsyncClient, sample_customers, sample_venue_id
    ):
        """Test filtering customers by type."""
        response = await client.get(
            f"/api/v1/customers/?venue_id={sample_venue_id}&customer_type=individual"
        )

        assert response.status_code == 200
        data = response.json()
        for customer in data["customers"]:
            assert customer["customer_type"] == "individual"


class TestCustomerCreateEndpoint:
    """Tests for POST /api/v1/customers/"""

    @pytest.mark.asyncio
    async def test_create_customer_success(self, client: AsyncClient, sample_venue_id):
        """Test creating a new customer."""
        customer_data = CustomerFactory.create_dict(venue_id=sample_venue_id)

        response = await client.post(
            "/api/v1/customers/",
            json=customer_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == customer_data["first_name"]
        assert data["last_name"] == customer_data["last_name"]
        assert data["email"] == customer_data["email"]
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_customer_duplicate_email(
        self, client: AsyncClient, sample_customer, sample_venue_id
    ):
        """Test creating customer with duplicate email fails."""
        customer_data = CustomerFactory.create_dict(
            venue_id=sample_venue_id,
            email=sample_customer.email,
        )

        response = await client.post(
            "/api/v1/customers/",
            json=customer_data,
        )

        assert response.status_code == 409
        assert "email already exists" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_customer_invalid_data(self, client: AsyncClient):
        """Test creating customer with invalid data fails."""
        response = await client.post(
            "/api/v1/customers/",
            json={"invalid": "data"},
        )

        assert response.status_code == 422


class TestCustomerGetEndpoint:
    """Tests for GET /api/v1/customers/{customer_id}"""

    @pytest.mark.asyncio
    async def test_get_customer_success(self, client: AsyncClient, sample_customer):
        """Test getting customer by ID."""
        response = await client.get(f"/api/v1/customers/{sample_customer.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_customer.id)
        assert data["first_name"] == sample_customer.first_name

    @pytest.mark.asyncio
    async def test_get_customer_not_found(self, client: AsyncClient):
        """Test getting non-existent customer returns 404."""
        response = await client.get(f"/api/v1/customers/{uuid4()}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_customer_includes_stats(self, client: AsyncClient, sample_customer):
        """Test get customer includes visit stats."""
        response = await client.get(f"/api/v1/customers/{sample_customer.id}")

        assert response.status_code == 200
        data = response.json()
        assert "total_visits" in data
        assert "total_spend" in data


class TestCustomerUpdateEndpoint:
    """Tests for PUT /api/v1/customers/{customer_id}"""

    @pytest.mark.asyncio
    async def test_update_customer_success(self, client: AsyncClient, sample_customer):
        """Test updating customer information."""
        update_data = {
            "first_name": "Updated",
            "last_name": "Customer",
        }

        response = await client.put(
            f"/api/v1/customers/{sample_customer.id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert data["last_name"] == "Customer"

    @pytest.mark.asyncio
    async def test_update_customer_not_found(self, client: AsyncClient):
        """Test updating non-existent customer returns 404."""
        response = await client.put(
            f"/api/v1/customers/{uuid4()}",
            json={"first_name": "Test"},
        )

        assert response.status_code == 404


class TestCustomerDeleteEndpoint:
    """Tests for DELETE /api/v1/customers/{customer_id}"""

    @pytest.mark.asyncio
    async def test_delete_customer_success(self, client: AsyncClient, sample_customer):
        """Test soft deleting a customer."""
        response = await client.delete(f"/api/v1/customers/{sample_customer.id}")

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_customer_gdpr(self, client: AsyncClient, sample_customer):
        """Test GDPR-compliant deletion."""
        response = await client.delete(
            f"/api/v1/customers/{sample_customer.id}?gdpr_delete=true"
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_customer_not_found(self, client: AsyncClient):
        """Test deleting non-existent customer returns 404."""
        response = await client.delete(f"/api/v1/customers/{uuid4()}")

        assert response.status_code == 404


class TestCustomerSearchEndpoint:
    """Tests for GET /api/v1/customers/search"""

    @pytest.mark.asyncio
    async def test_search_customers_by_query(
        self, client: AsyncClient, sample_customers, sample_venue_id
    ):
        """Test searching customers by name."""
        response = await client.get(
            f"/api/v1/customers/search?venue_id={sample_venue_id}&query=Customer"
        )

        assert response.status_code == 200
        data = response.json()
        assert "customers" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_search_customers_by_segment(
        self, client: AsyncClient, sample_venue_id
    ):
        """Test searching customers by segment."""
        response = await client.get(
            f"/api/v1/customers/search?venue_id={sample_venue_id}&segment=vip"
        )

        assert response.status_code == 200


class TestCustomerPreferencesEndpoint:
    """Tests for customer preferences endpoints."""

    @pytest.mark.asyncio
    async def test_get_preferences(self, client: AsyncClient, sample_customer):
        """Test getting customer preferences."""
        response = await client.get(
            f"/api/v1/customers/{sample_customer.id}/preferences"
        )

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_add_preference(self, client: AsyncClient, sample_customer):
        """Test adding customer preference."""
        response = await client.post(
            f"/api/v1/customers/{sample_customer.id}/preferences",
            params={
                "preference_type": "favorite_activity",
                "preference_value": "Bowling",
                "is_stated": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["preference_value"] == "Bowling"


class TestCustomerAtRiskEndpoint:
    """Tests for GET /api/v1/customers/at-risk"""

    @pytest.mark.asyncio
    async def test_get_at_risk_customers(self, client: AsyncClient, sample_venue_id):
        """Test getting at-risk customers."""
        response = await client.get(
            f"/api/v1/customers/at-risk?venue_id={sample_venue_id}"
        )

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_get_at_risk_customers_with_level(
        self, client: AsyncClient, sample_venue_id
    ):
        """Test getting at-risk customers with specific level."""
        response = await client.get(
            f"/api/v1/customers/at-risk?venue_id={sample_venue_id}&risk_level=high"
        )

        assert response.status_code == 200


class TestCustomerWinbackEndpoint:
    """Tests for POST /api/v1/customers/{customer_id}/winback"""

    @pytest.mark.asyncio
    async def test_trigger_winback(self, client: AsyncClient, sample_customer):
        """Test triggering winback campaign."""
        response = await client.post(
            f"/api/v1/customers/{sample_customer.id}/winback"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "campaign_triggered"
        assert data["customer_id"] == str(sample_customer.id)


class TestCustomerRecalculateSegmentsEndpoint:
    """Tests for POST /api/v1/customers/recalculate-segments"""

    @pytest.mark.asyncio
    async def test_recalculate_segments(self, client: AsyncClient, sample_venue_id):
        """Test triggering segment recalculation."""
        response = await client.post(
            f"/api/v1/customers/recalculate-segments?venue_id={sample_venue_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "customers_processed" in data
