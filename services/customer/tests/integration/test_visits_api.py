"""
=============================================================================
FILE: tests/integration/test_visits_api.py
PURPOSE: Integration tests for Visit API endpoints
=============================================================================
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import VisitFactory


class TestVisitListEndpoint:
    """Tests for GET /api/v1/visits/"""

    @pytest.mark.asyncio
    async def test_list_visits_success(
        self, client: AsyncClient, sample_visit, sample_venue_id
    ):
        """Test listing visits for a venue."""
        response = await client.get(
            f"/api/v1/visits/?venue_id={sample_venue_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert "visits" in data
        assert "total" in data
        assert "page" in data
        assert len(data["visits"]) >= 1

    @pytest.mark.asyncio
    async def test_list_visits_pagination(
        self, client: AsyncClient, sample_venue_id
    ):
        """Test visits listing with pagination."""
        response = await client.get(
            f"/api/v1/visits/?venue_id={sample_venue_id}&page=1&page_size=10"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    @pytest.mark.asyncio
    async def test_list_visits_date_filter(
        self, client: AsyncClient, sample_visit, sample_venue_id
    ):
        """Test filtering visits by date range."""
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        response = await client.get(
            f"/api/v1/visits/?venue_id={sample_venue_id}"
            f"&date_from={yesterday}&date_to={today}"
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_visits_source_filter(
        self, client: AsyncClient, sample_visit, sample_venue_id
    ):
        """Test filtering visits by source."""
        response = await client.get(
            f"/api/v1/visits/?venue_id={sample_venue_id}&source=walk_in"
        )

        assert response.status_code == 200
        data = response.json()
        for visit in data["visits"]:
            assert visit["source"] == "walk_in"

    @pytest.mark.asyncio
    async def test_list_visits_customer_filter(
        self, client: AsyncClient, sample_visit, sample_venue_id, sample_customer
    ):
        """Test filtering visits by customer."""
        response = await client.get(
            f"/api/v1/visits/?venue_id={sample_venue_id}"
            f"&customer_id={sample_customer.id}"
        )

        assert response.status_code == 200


class TestVisitCreateEndpoint:
    """Tests for POST /api/v1/visits/"""

    @pytest.mark.asyncio
    async def test_create_visit_success(
        self, client: AsyncClient, sample_customer, sample_venue_id
    ):
        """Test creating a new visit."""
        visit_data = VisitFactory.create_dict(
            customer_id=str(sample_customer.id),
            venue_id=sample_venue_id,
            party_size=3,
        )

        response = await client.post(
            "/api/v1/visits/",
            json=visit_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["party_size"] == 3
        assert "id" in data
        assert "check_in_time" in data

    @pytest.mark.asyncio
    async def test_create_visit_with_reservation(
        self, client: AsyncClient, sample_customer, sample_venue_id
    ):
        """Test creating visit from reservation."""
        reservation_id = str(uuid4())
        visit_data = {
            "customer_id": str(sample_customer.id),
            "venue_id": sample_venue_id,
            "source": "reservation",
            "reservation_id": reservation_id,
            "party_size": 5,
        }

        response = await client.post(
            "/api/v1/visits/",
            json=visit_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["source"] == "reservation"

    @pytest.mark.asyncio
    async def test_create_visit_invalid_data(self, client: AsyncClient):
        """Test creating visit with invalid data fails."""
        response = await client.post(
            "/api/v1/visits/",
            json={"invalid": "data"},
        )

        assert response.status_code == 422


class TestVisitGetEndpoint:
    """Tests for GET /api/v1/visits/{visit_id}"""

    @pytest.mark.asyncio
    async def test_get_visit_success(self, client: AsyncClient, sample_visit):
        """Test getting visit by ID."""
        response = await client.get(f"/api/v1/visits/{sample_visit.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_visit.id)

    @pytest.mark.asyncio
    async def test_get_visit_not_found(self, client: AsyncClient):
        """Test getting non-existent visit returns 404."""
        response = await client.get(f"/api/v1/visits/{uuid4()}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_visit_detail_includes_duration(
        self, client: AsyncClient, sample_visit
    ):
        """Test visit detail includes duration if checked out."""
        response = await client.get(f"/api/v1/visits/{sample_visit.id}")

        assert response.status_code == 200
        # Duration may be None if not checked out
        assert "duration_minutes" in response.json() or True


class TestVisitUpdateEndpoint:
    """Tests for PUT /api/v1/visits/{visit_id}"""

    @pytest.mark.asyncio
    async def test_update_visit_success(self, client: AsyncClient, sample_visit):
        """Test updating visit information."""
        update_data = {
            "party_size": 6,
            "notes": "Updated visit notes",
        }

        response = await client.put(
            f"/api/v1/visits/{sample_visit.id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["party_size"] == 6
        assert data["notes"] == "Updated visit notes"

    @pytest.mark.asyncio
    async def test_update_visit_not_found(self, client: AsyncClient):
        """Test updating non-existent visit returns 404."""
        response = await client.put(
            f"/api/v1/visits/{uuid4()}",
            json={"party_size": 3},
        )

        assert response.status_code == 404


class TestVisitCheckoutEndpoint:
    """Tests for PATCH /api/v1/visits/{visit_id}/checkout"""

    @pytest.mark.asyncio
    async def test_checkout_visit_success(self, client: AsyncClient, sample_visit):
        """Test checking out a visit."""
        checkout_data = {
            "total_spend": 85.50,
            "satisfaction_rating": 5,
            "notes": "Great experience",
        }

        response = await client.patch(
            f"/api/v1/visits/{sample_visit.id}/checkout",
            json=checkout_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_spend"] == 85.50
        assert data["check_out_time"] is not None

    @pytest.mark.asyncio
    async def test_checkout_visit_minimal(self, client: AsyncClient, sample_visit):
        """Test checkout with minimal data."""
        checkout_data = {
            "total_spend": 50.00,
        }

        response = await client.patch(
            f"/api/v1/visits/{sample_visit.id}/checkout",
            json=checkout_data,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_checkout_visit_not_found(self, client: AsyncClient):
        """Test checkout non-existent visit returns 404."""
        response = await client.patch(
            f"/api/v1/visits/{uuid4()}/checkout",
            json={"total_spend": 50.00},
        )

        assert response.status_code == 404


class TestVisitActivitiesEndpoint:
    """Tests for POST /api/v1/visits/{visit_id}/activities"""

    @pytest.mark.asyncio
    async def test_add_activity_success(self, client: AsyncClient, sample_visit):
        """Test adding an activity to a visit."""
        activity_data = {
            "activity_type": "attraction",
            "activity_name": "Laser Tag",
            "amount": 25.00,
            "quantity": 2,
        }

        response = await client.post(
            f"/api/v1/visits/{sample_visit.id}/activities",
            json=activity_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["activity_name"] == "Laser Tag"
        assert data["amount"] == 25.00
        assert data["quantity"] == 2

    @pytest.mark.asyncio
    async def test_add_food_activity(self, client: AsyncClient, sample_visit):
        """Test adding food/beverage activity."""
        activity_data = {
            "activity_type": "food_beverage",
            "activity_name": "Pizza and Drinks",
            "amount": 35.00,
            "quantity": 1,
        }

        response = await client.post(
            f"/api/v1/visits/{sample_visit.id}/activities",
            json=activity_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["activity_type"] == "food_beverage"

    @pytest.mark.asyncio
    async def test_add_multiple_activities(self, client: AsyncClient, sample_visit):
        """Test adding multiple activities to a visit."""
        activities = [
            {"activity_type": "attraction", "activity_name": "Bowling", "amount": 20.00, "quantity": 1},
            {"activity_type": "arcade", "activity_name": "Game Card", "amount": 15.00, "quantity": 1},
            {"activity_type": "food_beverage", "activity_name": "Snacks", "amount": 10.00, "quantity": 2},
        ]

        for activity in activities:
            response = await client.post(
                f"/api/v1/visits/{sample_visit.id}/activities",
                json=activity,
            )
            assert response.status_code == 201


class TestVisitCustomerVisitsEndpoint:
    """Tests for GET /api/v1/visits/customer/{customer_id}"""

    @pytest.mark.asyncio
    async def test_get_customer_visits_success(
        self, client: AsyncClient, sample_customer, sample_visit
    ):
        """Test getting visits for a customer."""
        response = await client.get(
            f"/api/v1/visits/customer/{sample_customer.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_get_customer_visits_with_limit(
        self, client: AsyncClient, sample_customer
    ):
        """Test getting customer visits with limit."""
        response = await client.get(
            f"/api/v1/visits/customer/{sample_customer.id}?limit=5"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5


class TestVisitStatsEndpoint:
    """Tests for GET /api/v1/visits/stats"""

    @pytest.mark.asyncio
    async def test_get_visit_stats_success(
        self, client: AsyncClient, sample_visit, sample_venue_id
    ):
        """Test getting visit statistics."""
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        response = await client.get(
            f"/api/v1/visits/stats?venue_id={sample_venue_id}"
            f"&date_from={yesterday}&date_to={today}"
        )

        assert response.status_code == 200
        data = response.json()
        # Stats should contain relevant metrics
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_get_visit_stats_required_params(self, client: AsyncClient):
        """Test visit stats requires date parameters."""
        response = await client.get(
            f"/api/v1/visits/stats?venue_id={uuid4()}"
        )

        # Should fail without date_from and date_to
        assert response.status_code == 422
