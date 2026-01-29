"""Integration tests for reservation-capacity API endpoints."""

import math
from datetime import date, time, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.reservation import (
    Reservation,
    ReservationStatus,
    ReservationType,
    ResourceType,
    BookingChannel,
    DepositStatus,
    RecurrenceFrequency,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Health Check
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_health_check(test_client):
    """GET /health should return 200 with status=healthy."""
    response = await test_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "reservation-capacity"
    assert "version" in body


# ═══════════════════════════════════════════════════════════════════════════════
# Authentication Guard
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_reservations_requires_auth(unauthenticated_test_client):
    """
    GET /api/v1/reservations without a token should return 403
    (FastAPI's HTTPBearer returns 403 when no credentials are supplied).
    """
    venue_id = uuid4()
    response = await unauthenticated_test_client.get(
        f"/api/v1/reservations?venue_id={venue_id}"
    )
    assert response.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# Create Reservation
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_reservation_201(test_client, mock_db):
    """
    POST /api/v1/reservations?venue_id=... with valid JSON body should
    return 201 and a reservation object.
    """
    venue_id = uuid4()
    reservation_id = uuid4()
    now_dt = "2026-03-15T00:00:00+00:00"

    # The service's create_reservation ultimately returns a Reservation model.
    # We mock db.add, flush, commit, and refresh to be no-ops, and we patch
    # ReservationService.create_reservation to return a pre-built response.
    from app.services.reservation_service import ReservationService

    fake_reservation = MagicMock(spec=Reservation)
    fake_reservation.id = reservation_id
    fake_reservation.venue_id = venue_id
    fake_reservation.customer_id = None
    fake_reservation.reservation_type = ReservationType.BOWLING.value
    fake_reservation.reservation_date = date(2026, 3, 15)
    fake_reservation.start_time = time(14, 0)
    fake_reservation.end_time = time(15, 0)
    fake_reservation.party_size = 4
    fake_reservation.status = ReservationStatus.PENDING.value
    fake_reservation.confirmation_code = "AB12CD34"
    fake_reservation.no_show_probability = None
    fake_reservation.booking_channel = BookingChannel.ONLINE.value
    fake_reservation.special_requests = None
    fake_reservation.deposit_required = False
    fake_reservation.deposit_amount = None
    fake_reservation.deposit_paid = False
    fake_reservation.checked_in_at = None
    fake_reservation.completed_at = None
    fake_reservation.cancelled_at = None
    fake_reservation.created_at = now_dt
    fake_reservation.updated_at = now_dt
    fake_reservation.items = []

    original_create = ReservationService.create_reservation

    async def _mock_create(self, vid, data):
        return fake_reservation

    ReservationService.create_reservation = _mock_create  # type: ignore[assignment]

    try:
        payload = {
            "reservation_type": "BOWLING",
            "reservation_date": "2026-03-15",
            "start_time": "14:00:00",
            "end_time": "15:00:00",
            "party_size": 4,
            "booking_channel": "ONLINE",
            "items": [],
        }

        response = await test_client.post(
            f"/api/v1/reservations?venue_id={venue_id}",
            json=payload,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["confirmation_code"] == "AB12CD34"
        assert body["status"] == "PENDING"
        assert body["party_size"] == 4
    finally:
        ReservationService.create_reservation = original_create  # type: ignore[assignment]


# ═══════════════════════════════════════════════════════════════════════════════
# Get Reservation – Not Found
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_reservation_not_found(test_client, mock_db):
    """
    GET /api/v1/reservations/{bad_id} should return 404 when the
    reservation does not exist.
    """
    bad_id = uuid4()

    # Make db.execute return no result (scalar_one_or_none -> None)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    response = await test_client.get(f"/api/v1/reservations/{bad_id}")
    assert response.status_code == 404
    body = response.json()
    assert body["detail"] == "Reservation not found"


# ═══════════════════════════════════════════════════════════════════════════════
# Create Recurring Series
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_recurring_series_201(test_client, mock_db):
    """
    POST /api/v1/reservations/recurring?venue_id=... should return 201
    with a recurring series response.
    """
    venue_id = uuid4()
    group_id = uuid4()
    now_dt = "2026-03-15T00:00:00+00:00"
    future_date = date.today() + timedelta(days=7)

    from app.services.recurring_service import RecurringReservationService

    # Build fake reservations for the series
    fake_reservations = []
    for i in range(4):
        fake_res = MagicMock(spec=Reservation)
        fake_res.id = uuid4()
        fake_res.venue_id = venue_id
        fake_res.customer_id = None
        fake_res.reservation_type = ReservationType.BOWLING.value
        fake_res.reservation_date = future_date + timedelta(weeks=i)
        fake_res.start_time = time(14, 0)
        fake_res.end_time = time(15, 0)
        fake_res.party_size = 4
        fake_res.status = ReservationStatus.PENDING.value
        fake_res.confirmation_code = f"RC{i:06d}"
        fake_res.no_show_probability = None
        fake_res.booking_channel = BookingChannel.ONLINE.value
        fake_res.special_requests = None
        fake_res.idempotency_key = None
        fake_res.deposit_required = False
        fake_res.deposit_amount = None
        fake_res.deposit_paid = False
        fake_res.deposit_status = None
        fake_res.deposit_transaction_id = None
        fake_res.deposit_paid_at = None
        fake_res.deposit_refunded_at = None
        fake_res.is_recurring = True
        fake_res.recurrence_group_id = group_id
        fake_res.recurrence_frequency = RecurrenceFrequency.WEEKLY.value
        fake_res.recurrence_end_date = None
        fake_res.recurrence_index = i
        fake_res.is_group_booking = False
        fake_res.group_booking_id = None
        fake_res.group_name = None
        fake_res.group_contact_name = None
        fake_res.group_contact_email = None
        fake_res.group_contact_phone = None
        fake_res.checked_in_at = None
        fake_res.completed_at = None
        fake_res.cancelled_at = None
        fake_res.created_at = now_dt
        fake_res.updated_at = now_dt
        fake_res.items = []
        fake_reservations.append(fake_res)

    original_create = RecurringReservationService.create_recurring_series

    async def _mock_create(self, vid, data):
        return fake_reservations

    RecurringReservationService.create_recurring_series = _mock_create  # type: ignore[assignment]

    try:
        payload = {
            "reservation_type": "BOWLING",
            "reservation_date": str(future_date),
            "start_time": "14:00:00",
            "end_time": "15:00:00",
            "party_size": 4,
            "recurrence_frequency": "WEEKLY",
            "max_occurrences": 4,
            "items": [],
        }

        response = await test_client.post(
            f"/api/v1/reservations/recurring?venue_id={venue_id}",
            json=payload,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["total_count"] == 4
        assert body["frequency"] == "WEEKLY"
        assert str(body["recurrence_group_id"]) == str(group_id)
        assert len(body["reservations"]) == 4
    finally:
        RecurringReservationService.create_recurring_series = original_create  # type: ignore[assignment]


# ═══════════════════════════════════════════════════════════════════════════════
# Create Group Booking
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_group_booking_201(test_client, mock_db):
    """
    POST /api/v1/reservations/group?venue_id=... should return 201
    with a group booking response.
    """
    venue_id = uuid4()
    group_id = uuid4()
    now_dt = "2026-04-01T00:00:00+00:00"
    future_date = date.today() + timedelta(days=14)

    from app.services.group_booking_service import GroupBookingService

    # Build two fake reservations for the group
    fake_reservations = []
    for i in range(2):
        fake_res = MagicMock(spec=Reservation)
        fake_res.id = uuid4()
        fake_res.venue_id = venue_id
        fake_res.customer_id = None
        fake_res.reservation_type = ReservationType.PARTY.value
        fake_res.reservation_date = future_date
        fake_res.start_time = time(18, 0)
        fake_res.end_time = time(20, 0)
        fake_res.party_size = 15
        fake_res.status = ReservationStatus.PENDING.value
        fake_res.confirmation_code = f"GRP{i:05d}"
        fake_res.no_show_probability = None
        fake_res.booking_channel = None
        fake_res.special_requests = None
        fake_res.idempotency_key = None
        fake_res.deposit_required = False
        fake_res.deposit_amount = None
        fake_res.deposit_paid = False
        fake_res.deposit_status = None
        fake_res.deposit_transaction_id = None
        fake_res.deposit_paid_at = None
        fake_res.deposit_refunded_at = None
        fake_res.is_recurring = False
        fake_res.recurrence_group_id = None
        fake_res.recurrence_frequency = None
        fake_res.recurrence_end_date = None
        fake_res.recurrence_index = None
        fake_res.is_group_booking = True
        fake_res.group_booking_id = group_id
        fake_res.group_name = "Corporate Event"
        fake_res.group_contact_name = "Jane Manager"
        fake_res.group_contact_email = "jane@corp.com"
        fake_res.group_contact_phone = "555-0100"
        fake_res.checked_in_at = None
        fake_res.completed_at = None
        fake_res.cancelled_at = None
        fake_res.created_at = now_dt
        fake_res.updated_at = now_dt
        fake_res.items = []
        fake_reservations.append(fake_res)

    original_create = GroupBookingService.create_group_booking

    async def _mock_create(self, vid, data):
        return fake_reservations

    GroupBookingService.create_group_booking = _mock_create  # type: ignore[assignment]

    try:
        payload = {
            "reservation_type": "PARTY",
            "reservation_date": str(future_date),
            "start_time": "18:00:00",
            "end_time": "20:00:00",
            "group_name": "Corporate Event",
            "group_contact_name": "Jane Manager",
            "group_contact_email": "jane@corp.com",
            "group_contact_phone": "555-0100",
            "resource_blocks": [
                {
                    "resource_type": "PARTY_ROOM",
                    "quantity": 1,
                    "party_size": 15,
                    "duration_minutes": 120,
                    "base_price": "200.00",
                },
                {
                    "resource_type": "BOWLING_LANE",
                    "quantity": 2,
                    "party_size": 15,
                    "duration_minutes": 120,
                    "base_price": "50.00",
                },
            ],
        }

        response = await test_client.post(
            f"/api/v1/reservations/group?venue_id={venue_id}",
            json=payload,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["group_name"] == "Corporate Event"
        assert body["total_resources"] == 2
        assert body["total_party_size"] == 30
        assert str(body["group_booking_id"]) == str(group_id)
        assert len(body["reservations"]) == 2
    finally:
        GroupBookingService.create_group_booking = original_create  # type: ignore[assignment]


# ═══════════════════════════════════════════════════════════════════════════════
# Deposit – Collect
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_collect_deposit(test_client, mock_db):
    """
    POST /api/v1/reservations/{id}/deposit/collect should collect deposit
    and return deposit response.
    """
    reservation_id = uuid4()
    customer_id = uuid4()

    from app.services.deposit_service import DepositService

    original_collect = DepositService.collect_deposit

    async def _mock_collect(self, rid, amount, cid, payment_method_id=None):
        return {
            "status": "collected",
            "reservation_id": str(rid),
            "transaction_id": "txn_mock_789",
            "amount": str(amount),
        }

    DepositService.collect_deposit = _mock_collect  # type: ignore[assignment]

    try:
        payload = {
            "amount": "50.00",
            "customer_id": str(customer_id),
        }

        response = await test_client.post(
            f"/api/v1/reservations/{reservation_id}/deposit/collect",
            json=payload,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "collected"
        assert body["transaction_id"] == "txn_mock_789"
    finally:
        DepositService.collect_deposit = original_collect  # type: ignore[assignment]


# ═══════════════════════════════════════════════════════════════════════════════
# Deposit – Refund
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_refund_deposit(test_client, mock_db):
    """
    POST /api/v1/reservations/{id}/deposit/refund should process refund
    and return deposit response.
    """
    reservation_id = uuid4()

    from app.services.deposit_service import DepositService

    original_refund = DepositService.refund_deposit

    async def _mock_refund(self, rid, reason="customer_request"):
        return {
            "status": "refunded",
            "reservation_id": str(rid),
            "amount": "50.00",
        }

    DepositService.refund_deposit = _mock_refund  # type: ignore[assignment]

    try:
        response = await test_client.post(
            f"/api/v1/reservations/{reservation_id}/deposit/refund?reason=customer_request",
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "refunded"
        assert body["amount"] == "50.00"
    finally:
        DepositService.refund_deposit = original_refund  # type: ignore[assignment]


# ═══════════════════════════════════════════════════════════════════════════════
# Rate Limiting – 429
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_rate_limit_returns_429(test_client, mock_db):
    """
    POST /api/v1/reservations should return 429 when the rate limiter
    dependency denies the request.
    """
    venue_id = uuid4()

    from app.core.rate_limiter import check_reservation_create_rate

    # Override the rate-limit dependency to always raise 429
    from app.main import app
    from fastapi import HTTPException, status

    async def _always_deny(request=None, venue_id=None):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many reservation requests. Please try again later.",
                "retry_after_seconds": 60,
            },
        )

    app.dependency_overrides[check_reservation_create_rate] = _always_deny

    try:
        payload = {
            "reservation_type": "BOWLING",
            "reservation_date": str(date.today() + timedelta(days=7)),
            "start_time": "14:00:00",
            "end_time": "15:00:00",
            "party_size": 4,
            "booking_channel": "ONLINE",
            "items": [],
        }

        response = await test_client.post(
            f"/api/v1/reservations?venue_id={venue_id}",
            json=payload,
        )
        assert response.status_code == 429
        body = response.json()
        assert body["detail"]["error_code"] == "RATE_LIMIT_EXCEEDED"
    finally:
        # Remove the override so other tests are not affected
        app.dependency_overrides.pop(check_reservation_create_rate, None)
