"""
=============================================================================
FILE: tests/integration/test_bookings_api.py
PURPOSE: Integration tests for Party Bookings API endpoints
=============================================================================
"""

import uuid
from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.party import PartyBooking, PartyPackage, PartyAddon, BookingStatus


class TestBookingsAPICreate:
    """Integration tests for POST /api/v1/bookings endpoint."""

    @pytest.mark.asyncio
    async def test_create_booking_success(
        self,
        async_client: AsyncClient,
        valid_booking_data: dict,
        auth_headers: dict,
    ):
        """Test successful booking creation."""
        response = await async_client.post(
            "/api/v1/bookings/",
            json=valid_booking_data,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["contact_name"] == valid_booking_data["contact_name"]
        assert data["guest_count"] == valid_booking_data["guest_count"]
        assert "booking_reference" in data
        assert data["booking_reference"].startswith("PB-")

    @pytest.mark.asyncio
    async def test_create_booking_missing_required_field(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_venue_id: uuid.UUID,
    ):
        """Test booking creation fails without required fields."""
        incomplete_data = {
            "venue_id": str(sample_venue_id),
            # Missing other required fields
        }

        response = await async_client.post(
            "/api/v1/bookings/",
            json=incomplete_data,
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_booking_invalid_email(
        self,
        async_client: AsyncClient,
        valid_booking_data: dict,
        auth_headers: dict,
    ):
        """Test booking creation fails with invalid email."""
        valid_booking_data["contact_email"] = "not-an-email"

        response = await async_client.post(
            "/api/v1/bookings/",
            json=valid_booking_data,
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_booking_with_addons(
        self,
        async_client: AsyncClient,
        valid_booking_data: dict,
        sample_addon: PartyAddon,
        auth_headers: dict,
    ):
        """Test booking creation with addons."""
        valid_booking_data["addons"] = [
            {"addon_id": str(sample_addon.id), "quantity": 2}
        ]

        response = await async_client.post(
            "/api/v1/bookings/",
            json=valid_booking_data,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert float(data["addons_total"]) > 0


class TestBookingsAPIGet:
    """Integration tests for GET /api/v1/bookings endpoints."""

    @pytest.mark.asyncio
    async def test_get_booking_success(
        self,
        async_client: AsyncClient,
        sample_booking: PartyBooking,
        auth_headers: dict,
    ):
        """Test successful booking retrieval."""
        response = await async_client.get(
            f"/api/v1/bookings/{sample_booking.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_booking.id)
        assert data["booking_reference"] == sample_booking.booking_reference

    @pytest.mark.asyncio
    async def test_get_booking_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test booking retrieval when not found."""
        random_id = uuid.uuid4()
        response = await async_client.get(
            f"/api/v1/bookings/{random_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_bookings_success(
        self,
        async_client: AsyncClient,
        sample_booking: PartyBooking,
        sample_venue_id: uuid.UUID,
        auth_headers: dict,
    ):
        """Test listing bookings."""
        response = await async_client.get(
            f"/api/v1/bookings/?venue_id={sample_venue_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "bookings" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_bookings_with_filters(
        self,
        async_client: AsyncClient,
        sample_booking: PartyBooking,
        sample_venue_id: uuid.UUID,
        auth_headers: dict,
    ):
        """Test filtering bookings."""
        response = await async_client.get(
            f"/api/v1/bookings/?venue_id={sample_venue_id}&status=pending",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        for booking in data["bookings"]:
            assert booking["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_bookings_date_range(
        self,
        async_client: AsyncClient,
        sample_venue_id: uuid.UUID,
        auth_headers: dict,
    ):
        """Test filtering bookings by date range."""
        today = date.today()
        date_from = today.isoformat()
        date_to = (today + timedelta(days=30)).isoformat()

        response = await async_client.get(
            f"/api/v1/bookings/?venue_id={sample_venue_id}&date_from={date_from}&date_to={date_to}",
            headers=auth_headers,
        )

        assert response.status_code == 200


class TestBookingsAPIUpdate:
    """Integration tests for PUT /api/v1/bookings/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_booking_success(
        self,
        async_client: AsyncClient,
        sample_booking: PartyBooking,
        auth_headers: dict,
    ):
        """Test successful booking update."""
        update_data = {
            "guest_count": 20,
            "special_requests": "Need extra chairs",
        }

        response = await async_client.put(
            f"/api/v1/bookings/{sample_booking.id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["guest_count"] == 20
        assert data["special_requests"] == "Need extra chairs"

    @pytest.mark.asyncio
    async def test_update_booking_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test update when booking doesn't exist."""
        random_id = uuid.uuid4()
        update_data = {"guest_count": 20}

        response = await async_client.put(
            f"/api/v1/bookings/{random_id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestBookingsAPIStatus:
    """Integration tests for booking status endpoints."""

    @pytest.mark.asyncio
    async def test_confirm_booking(
        self,
        async_client: AsyncClient,
        sample_booking: PartyBooking,
        auth_headers: dict,
    ):
        """Test confirming a booking."""
        response = await async_client.post(
            f"/api/v1/bookings/{sample_booking.id}/confirm",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "confirmed"
        assert data["confirmed_at"] is not None

    @pytest.mark.asyncio
    async def test_check_in_booking(
        self,
        async_client: AsyncClient,
        sample_booking: PartyBooking,
        auth_headers: dict,
    ):
        """Test checking in a booking."""
        response = await async_client.post(
            f"/api/v1/bookings/{sample_booking.id}/check-in",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "checked_in"
        assert data["checked_in_at"] is not None

    @pytest.mark.asyncio
    async def test_complete_booking(
        self,
        async_client: AsyncClient,
        sample_booking: PartyBooking,
        auth_headers: dict,
    ):
        """Test completing a booking."""
        response = await async_client.post(
            f"/api/v1/bookings/{sample_booking.id}/complete",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_cancel_booking(
        self,
        async_client: AsyncClient,
        sample_booking: PartyBooking,
        auth_headers: dict,
    ):
        """Test cancelling a booking."""
        response = await async_client.delete(
            f"/api/v1/bookings/{sample_booking.id}",
            json={"cancellation_reason": "Customer request"},
            headers=auth_headers,
        )

        assert response.status_code in [200, 204]


class TestBookingsAPIAddons:
    """Integration tests for booking addon endpoints."""

    @pytest.mark.asyncio
    async def test_add_addon_to_booking(
        self,
        async_client: AsyncClient,
        sample_booking: PartyBooking,
        sample_addon: PartyAddon,
        auth_headers: dict,
    ):
        """Test adding addon to booking."""
        addon_data = {
            "addon_id": str(sample_addon.id),
            "quantity": 2,
        }

        response = await async_client.post(
            f"/api/v1/bookings/{sample_booking.id}/addons",
            json=addon_data,
            headers=auth_headers,
        )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_remove_addon_from_booking(
        self,
        async_client: AsyncClient,
        sample_booking: PartyBooking,
        sample_addon: PartyAddon,
        auth_headers: dict,
    ):
        """Test removing addon from booking."""
        # First add the addon
        addon_data = {
            "addon_id": str(sample_addon.id),
            "quantity": 1,
        }
        await async_client.post(
            f"/api/v1/bookings/{sample_booking.id}/addons",
            json=addon_data,
            headers=auth_headers,
        )

        # Then remove it
        response = await async_client.delete(
            f"/api/v1/bookings/{sample_booking.id}/addons/{sample_addon.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204


class TestBookingsAPIAvailability:
    """Integration tests for availability checking endpoints."""

    @pytest.mark.asyncio
    async def test_check_availability_available(
        self,
        async_client: AsyncClient,
        sample_venue_id: uuid.UUID,
        auth_headers: dict,
    ):
        """Test checking availability when slot is available."""
        party_date = (date.today() + timedelta(days=30)).isoformat()

        response = await async_client.post(
            "/api/v1/bookings/check-availability",
            json={
                "venue_id": str(sample_venue_id),
                "party_date": party_date,
                "start_time": "10:00:00",
                "duration_minutes": 120,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "available" in data

    @pytest.mark.asyncio
    async def test_check_availability_conflict(
        self,
        async_client: AsyncClient,
        sample_booking: PartyBooking,
        sample_venue_id: uuid.UUID,
        auth_headers: dict,
    ):
        """Test checking availability when slot is taken."""
        response = await async_client.post(
            "/api/v1/bookings/check-availability",
            json={
                "venue_id": str(sample_venue_id),
                "party_date": sample_booking.party_date.isoformat(),
                "start_time": sample_booking.start_time.isoformat(),
                "duration_minutes": 120,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False


class TestBookingsAPICalendar:
    """Integration tests for calendar-related endpoints."""

    @pytest.mark.asyncio
    async def test_get_calendar(
        self,
        async_client: AsyncClient,
        sample_venue_id: uuid.UUID,
        auth_headers: dict,
    ):
        """Test getting calendar view."""
        today = date.today()
        start_date = today.isoformat()
        end_date = (today + timedelta(days=30)).isoformat()

        response = await async_client.get(
            f"/api/v1/bookings/calendar?venue_id={sample_venue_id}&start_date={start_date}&end_date={end_date}",
            headers=auth_headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_upcoming_bookings(
        self,
        async_client: AsyncClient,
        sample_venue_id: uuid.UUID,
        auth_headers: dict,
    ):
        """Test getting upcoming bookings."""
        response = await async_client.get(
            f"/api/v1/bookings/upcoming?venue_id={sample_venue_id}&limit=10",
            headers=auth_headers,
        )

        assert response.status_code == 200


class TestBookingsAPIInvoice:
    """Integration tests for invoice generation endpoint."""

    @pytest.mark.asyncio
    async def test_get_booking_invoice(
        self,
        async_client: AsyncClient,
        sample_booking: PartyBooking,
        auth_headers: dict,
    ):
        """Test getting booking invoice."""
        response = await async_client.get(
            f"/api/v1/bookings/{sample_booking.id}/invoice",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "booking_reference" in data
        assert "total_price" in data
