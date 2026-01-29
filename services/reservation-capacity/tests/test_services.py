"""Unit tests for reservation-capacity service layer."""

import string
from datetime import date, datetime, time, timedelta, timezone
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
    CapacityConfig,
    DepositStatus,
    RecurrenceFrequency,
)
from app.schemas.reservation import (
    ReservationCreate,
    ReservationItemCreate,
    RecurringReservationCreate,
    GroupBookingCreate,
    ResourceBlockCreate,
)
from app.services.reservation_service import ReservationService
from app.services.capacity_service import CapacityService
from app.services.validation_service import ValidationService
from app.services.recurring_service import RecurringReservationService
from app.services.group_booking_service import GroupBookingService
from app.services.deposit_service import DepositService
from app.services.notification_client import NotificationClient
from app.core.rate_limiter import RateLimiter, _memory_store
from app.core.errors import ErrorCode, ServiceError


# ═══════════════════════════════════════════════════════════════════════════════
# TestReservationService
# ═══════════════════════════════════════════════════════════════════════════════

class TestReservationService:
    """Tests for ReservationService."""

    # ------------------------------------------------------------------
    # test_generate_confirmation_code
    # ------------------------------------------------------------------

    def test_generate_confirmation_code(self):
        """Confirmation code must be 8 characters, uppercase letters + digits."""
        code = ReservationService._generate_confirmation_code()
        assert len(code) == 8
        allowed = set(string.ascii_uppercase + string.digits)
        assert all(ch in allowed for ch in code)

    def test_generate_confirmation_code_uniqueness(self):
        """Two consecutive calls should (almost certainly) produce different codes."""
        code_a = ReservationService._generate_confirmation_code()
        code_b = ReservationService._generate_confirmation_code()
        # Extremely unlikely to collide; assert they differ.
        assert code_a != code_b

    # ------------------------------------------------------------------
    # test_create_reservation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_reservation(self, mock_db, mock_event_publisher):
        """create_reservation should add a Reservation, commit, and publish an event."""
        service = ReservationService(mock_db, mock_event_publisher)
        venue_id = uuid4()
        customer_id = uuid4()

        data = ReservationCreate(
            customer_id=customer_id,
            reservation_type=ReservationType.BOWLING,
            reservation_date=date(2026, 3, 15),
            start_time=time(14, 0),
            end_time=time(15, 0),
            party_size=4,
            booking_channel=BookingChannel.ONLINE,
            items=[
                ReservationItemCreate(
                    item_type=ResourceType.BOWLING_LANE,
                    quantity=1,
                    duration_minutes=60,
                    base_price=Decimal("25.00"),
                ),
            ],
        )

        # _update_customer_stats runs an additional db.execute; stub it out
        # so we don't need to build the full scalars chain for stats.
        mock_stats_result = MagicMock()
        mock_stats_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_stats_result

        reservation = await service.create_reservation(venue_id, data)

        # Reservation should have been added to the session (once for the
        # reservation, once for the item, and possibly once for stats).
        assert mock_db.add.call_count >= 2  # reservation + item
        mock_db.flush.assert_awaited()
        mock_db.commit.assert_awaited()
        mock_db.refresh.assert_awaited()

        # Event publisher should have been called for RESERVATION_CREATED
        mock_event_publisher.publish.assert_awaited()
        call_args = mock_event_publisher.publish.call_args
        from app.services.event_publisher import EventType
        assert call_args[0][0] == EventType.RESERVATION_CREATED

    # ------------------------------------------------------------------
    # test_cancel_reservation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_cancel_reservation(self, mock_db, mock_event_publisher):
        """cancel_reservation should set status to CANCELLED and publish event."""
        service = ReservationService(mock_db, mock_event_publisher)
        reservation_id = uuid4()

        # Build a fake reservation returned by get_reservation
        fake_reservation = MagicMock(spec=Reservation)
        fake_reservation.id = reservation_id
        fake_reservation.venue_id = uuid4()
        fake_reservation.customer_id = uuid4()
        fake_reservation.status = ReservationStatus.CONFIRMED.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_reservation
        mock_db.execute.return_value = mock_result

        result = await service.cancel_reservation(reservation_id)

        assert result is not None
        assert result.status == ReservationStatus.CANCELLED.value
        mock_db.commit.assert_awaited()

        # Publish called for RESERVATION_CANCELLED
        mock_event_publisher.publish.assert_awaited()
        from app.services.event_publisher import EventType
        event_type_arg = mock_event_publisher.publish.call_args[0][0]
        assert event_type_arg == EventType.RESERVATION_CANCELLED

    # ------------------------------------------------------------------
    # test_check_in
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_check_in(self, mock_db, mock_event_publisher):
        """check_in should set status to CHECKED_IN."""
        service = ReservationService(mock_db, mock_event_publisher)
        reservation_id = uuid4()

        fake_reservation = MagicMock(spec=Reservation)
        fake_reservation.id = reservation_id
        fake_reservation.venue_id = uuid4()
        fake_reservation.status = ReservationStatus.CONFIRMED.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_reservation
        mock_db.execute.return_value = mock_result

        result = await service.check_in(reservation_id)

        assert result is not None
        assert result.status == ReservationStatus.CHECKED_IN.value
        mock_db.commit.assert_awaited()
        mock_db.refresh.assert_awaited()

    # ------------------------------------------------------------------
    # test_confirm_reservation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_confirm_reservation(self, mock_db, mock_event_publisher):
        """confirm_reservation should transition PENDING -> CONFIRMED."""
        service = ReservationService(mock_db, mock_event_publisher)
        reservation_id = uuid4()

        fake_reservation = MagicMock(spec=Reservation)
        fake_reservation.id = reservation_id
        fake_reservation.venue_id = uuid4()
        fake_reservation.status = ReservationStatus.PENDING.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_reservation
        mock_db.execute.return_value = mock_result

        result = await service.confirm_reservation(reservation_id)

        assert result is not None
        assert result.status == ReservationStatus.CONFIRMED.value
        mock_db.commit.assert_awaited()

        from app.services.event_publisher import EventType
        mock_event_publisher.publish.assert_awaited()
        assert mock_event_publisher.publish.call_args[0][0] == EventType.RESERVATION_CONFIRMED

    # ------------------------------------------------------------------
    # test_confirm_reservation_not_pending_returns_none
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_confirm_reservation_not_pending_returns_none(self, mock_db, mock_event_publisher):
        """confirm_reservation should return None when status is not PENDING."""
        service = ReservationService(mock_db, mock_event_publisher)
        reservation_id = uuid4()

        fake_reservation = MagicMock(spec=Reservation)
        fake_reservation.id = reservation_id
        fake_reservation.venue_id = uuid4()
        fake_reservation.status = ReservationStatus.CONFIRMED.value  # already confirmed

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_reservation
        mock_db.execute.return_value = mock_result

        result = await service.confirm_reservation(reservation_id)

        assert result is None
        # Event should NOT have been published
        mock_event_publisher.publish.assert_not_awaited()


# ═══════════════════════════════════════════════════════════════════════════════
# TestCapacityService
# ═══════════════════════════════════════════════════════════════════════════════

class TestCapacityService:
    """Tests for CapacityService."""

    @pytest.mark.asyncio
    async def test_get_real_time_capacity_returns_data(self, mock_db, mock_event_publisher):
        """get_real_time_capacity should return a dict with capacity fields."""
        venue_id = uuid4()
        resource_type = "BOWLING_LANE"

        # First db.execute -> get_config query
        mock_config = MagicMock(spec=CapacityConfig)
        mock_config.total_capacity = 10

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = mock_config

        # Second db.execute -> count of active reservations
        count_result = MagicMock()
        count_result.scalar.return_value = 3

        mock_db.execute = AsyncMock(side_effect=[config_result, count_result])

        service = CapacityService(mock_db, mock_event_publisher)
        result = await service.get_real_time_capacity(venue_id, resource_type)

        assert result["venue_id"] == venue_id
        assert result["resource_type"] == resource_type
        assert result["total_capacity"] == 10
        assert result["currently_reserved"] == 3
        assert result["currently_available"] == 7
        assert result["utilization_percentage"] == Decimal("30.00")
        assert "timestamp" in result


# ═══════════════════════════════════════════════════════════════════════════════
# TestRateLimiter
# ═══════════════════════════════════════════════════════════════════════════════

class TestRateLimiter:
    """Tests for the in-memory rate limiter fallback."""

    def setup_method(self):
        """Clear the in-memory store before each test."""
        _memory_store.clear()

    def test_check_rate_limit_allows_within_limit(self):
        """Requests within the limit should be allowed."""
        limiter = RateLimiter()
        key = f"test:rate:{uuid4()}"
        allowed, remaining = limiter._check_memory(key, max_requests=5, window_seconds=60, now=1000.0)
        assert allowed is True
        assert remaining == 4

    def test_check_rate_limit_denies_over_limit(self):
        """Requests exceeding the limit should be denied."""
        limiter = RateLimiter()
        key = f"test:rate:{uuid4()}"
        now = 1000.0
        # Fill up the limit
        for i in range(5):
            allowed, remaining = limiter._check_memory(key, max_requests=5, window_seconds=60, now=now + i)
        # Sixth request should be denied
        allowed, remaining = limiter._check_memory(key, max_requests=5, window_seconds=60, now=now + 5)
        assert allowed is False
        assert remaining == 0

    def test_check_rate_limit_allows_after_window_expires(self):
        """Requests should be allowed after the window expires."""
        limiter = RateLimiter()
        key = f"test:rate:{uuid4()}"
        now = 1000.0
        # Fill up the limit
        for i in range(5):
            limiter._check_memory(key, max_requests=5, window_seconds=60, now=now + i)
        # After window expires, should allow again
        allowed, remaining = limiter._check_memory(key, max_requests=5, window_seconds=60, now=now + 61)
        assert allowed is True
        assert remaining == 4

    @pytest.mark.asyncio
    async def test_check_rate_limit_async_in_memory_mode(self):
        """check_rate_limit should use in-memory fallback when Redis is None."""
        limiter = RateLimiter()
        # _redis is None by default, so it uses in-memory mode
        key = f"test:async:{uuid4()}"
        allowed, remaining = await limiter.check_rate_limit(key, max_requests=3, window_seconds=60)
        assert allowed is True
        assert remaining == 2

    @pytest.mark.asyncio
    async def test_check_rate_limit_async_denies_when_exhausted(self):
        """check_rate_limit should deny after max requests exhausted."""
        limiter = RateLimiter()
        key = f"test:async_deny:{uuid4()}"
        for _ in range(3):
            await limiter.check_rate_limit(key, max_requests=3, window_seconds=60)
        allowed, remaining = await limiter.check_rate_limit(key, max_requests=3, window_seconds=60)
        assert allowed is False
        assert remaining == 0


# ═══════════════════════════════════════════════════════════════════════════════
# TestValidationService
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidationService:
    """Tests for ValidationService input validation and conflict detection."""

    # ------------------------------------------------------------------
    # test_validate_date_not_in_past
    # ------------------------------------------------------------------

    def test_past_date_rejected(self, mock_db):
        """Validation should raise ServiceError for a past reservation date."""
        service = ValidationService(mock_db)
        past_date = date.today() - timedelta(days=5)
        with pytest.raises(ServiceError) as exc_info:
            service._validate_date_not_in_past(past_date)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error_code"] == ErrorCode.RESERVATION_PAST_DATE.value

    def test_today_date_accepted(self, mock_db):
        """Today's date should be accepted (not in the past)."""
        service = ValidationService(mock_db)
        # Should not raise
        service._validate_date_not_in_past(date.today())

    def test_future_date_accepted(self, mock_db):
        """A future date should be accepted."""
        service = ValidationService(mock_db)
        future_date = date.today() + timedelta(days=30)
        # Should not raise
        service._validate_date_not_in_past(future_date)

    # ------------------------------------------------------------------
    # test_validate_time_range
    # ------------------------------------------------------------------

    def test_invalid_time_range_rejected(self, mock_db):
        """start_time >= end_time should be rejected."""
        service = ValidationService(mock_db)
        with pytest.raises(ServiceError) as exc_info:
            service._validate_time_range(time(15, 0), time(14, 0))
        assert exc_info.value.detail["error_code"] == ErrorCode.RESERVATION_INVALID_TIME_RANGE.value

    def test_equal_times_rejected(self, mock_db):
        """start_time == end_time should be rejected."""
        service = ValidationService(mock_db)
        with pytest.raises(ServiceError) as exc_info:
            service._validate_time_range(time(14, 0), time(14, 0))
        assert exc_info.value.detail["error_code"] == ErrorCode.RESERVATION_INVALID_TIME_RANGE.value

    def test_valid_time_range_accepted(self, mock_db):
        """start_time < end_time should be accepted."""
        service = ValidationService(mock_db)
        # Should not raise
        service._validate_time_range(time(14, 0), time(15, 0))

    # ------------------------------------------------------------------
    # test_validate_party_size
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_party_size_exceeds_max_rejected(self, mock_db):
        """Party size exceeding max should be rejected."""
        service = ValidationService(mock_db)

        mock_config = MagicMock(spec=CapacityConfig)
        mock_config.max_party_size = 10
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db.execute.return_value = mock_result

        data = ReservationCreate(
            reservation_type=ReservationType.BOWLING,
            reservation_date=date.today() + timedelta(days=7),
            start_time=time(14, 0),
            end_time=time(15, 0),
            party_size=25,
            items=[
                ReservationItemCreate(
                    item_type=ResourceType.BOWLING_LANE,
                    quantity=1,
                    duration_minutes=60,
                    base_price=Decimal("25.00"),
                ),
            ],
        )

        with pytest.raises(ServiceError) as exc_info:
            await service._validate_party_size(uuid4(), data)
        assert exc_info.value.detail["error_code"] == ErrorCode.RESERVATION_PARTY_SIZE_EXCEEDED.value

    @pytest.mark.asyncio
    async def test_party_size_within_limit_accepted(self, mock_db):
        """Party size within max should be accepted."""
        service = ValidationService(mock_db)

        mock_config = MagicMock(spec=CapacityConfig)
        mock_config.max_party_size = 50
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db.execute.return_value = mock_result

        data = ReservationCreate(
            reservation_type=ReservationType.BOWLING,
            reservation_date=date.today() + timedelta(days=7),
            start_time=time(14, 0),
            end_time=time(15, 0),
            party_size=4,
            items=[
                ReservationItemCreate(
                    item_type=ResourceType.BOWLING_LANE,
                    quantity=1,
                    duration_minutes=60,
                    base_price=Decimal("25.00"),
                ),
            ],
        )

        # Should not raise
        await service._validate_party_size(uuid4(), data)

    # ------------------------------------------------------------------
    # test_validate_business_hours
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_outside_business_hours_rejected(self, mock_db):
        """Reservation outside business hours should be rejected."""
        service = ValidationService(mock_db)

        mock_config = MagicMock(spec=CapacityConfig)
        mock_config.business_hours_start = time(9, 0)
        mock_config.business_hours_end = time(22, 0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db.execute.return_value = mock_result

        data = ReservationCreate(
            reservation_type=ReservationType.BOWLING,
            reservation_date=date.today() + timedelta(days=7),
            start_time=time(7, 0),  # Before business hours
            end_time=time(8, 0),
            party_size=4,
            items=[
                ReservationItemCreate(
                    item_type=ResourceType.BOWLING_LANE,
                    quantity=1,
                ),
            ],
        )

        with pytest.raises(ServiceError) as exc_info:
            await service._validate_business_hours(uuid4(), data)
        assert exc_info.value.detail["error_code"] == ErrorCode.RESERVATION_OUTSIDE_BUSINESS_HOURS.value

    @pytest.mark.asyncio
    async def test_within_business_hours_accepted(self, mock_db):
        """Reservation within business hours should be accepted."""
        service = ValidationService(mock_db)

        mock_config = MagicMock(spec=CapacityConfig)
        mock_config.business_hours_start = time(9, 0)
        mock_config.business_hours_end = time(22, 0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db.execute.return_value = mock_result

        data = ReservationCreate(
            reservation_type=ReservationType.BOWLING,
            reservation_date=date.today() + timedelta(days=7),
            start_time=time(14, 0),
            end_time=time(15, 0),
            party_size=4,
            items=[
                ReservationItemCreate(
                    item_type=ResourceType.BOWLING_LANE,
                    quantity=1,
                ),
            ],
        )

        # Should not raise
        await service._validate_business_hours(uuid4(), data)

    @pytest.mark.asyncio
    async def test_no_business_hours_config_accepted(self, mock_db):
        """When no business hours are configured, any time should be accepted."""
        service = ValidationService(mock_db)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        data = ReservationCreate(
            reservation_type=ReservationType.BOWLING,
            reservation_date=date.today() + timedelta(days=7),
            start_time=time(3, 0),  # Very early
            end_time=time(4, 0),
            party_size=4,
            items=[
                ReservationItemCreate(
                    item_type=ResourceType.BOWLING_LANE,
                    quantity=1,
                ),
            ],
        )

        # Should not raise
        await service._validate_business_hours(uuid4(), data)


# ═══════════════════════════════════════════════════════════════════════════════
# TestRecurringReservationService
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecurringReservationService:
    """Tests for RecurringReservationService."""

    @pytest.mark.asyncio
    async def test_create_recurring_series(self, mock_db, mock_event_publisher):
        """create_recurring_series should create multiple reservations."""
        service = RecurringReservationService(mock_db, mock_event_publisher)
        venue_id = uuid4()

        data = RecurringReservationCreate(
            reservation_type=ReservationType.BOWLING,
            reservation_date=date.today() + timedelta(days=7),
            start_time=time(14, 0),
            end_time=time(15, 0),
            party_size=4,
            recurrence_frequency=RecurrenceFrequency.WEEKLY,
            max_occurrences=4,
            items=[
                ReservationItemCreate(
                    item_type=ResourceType.BOWLING_LANE,
                    quantity=1,
                    duration_minutes=60,
                    base_price=Decimal("25.00"),
                ),
            ],
        )

        result = await service.create_recurring_series(venue_id, data)

        assert len(result) == 4
        # Each reservation should have been added to the session
        assert mock_db.add.call_count >= 4  # at least 4 reservations + items
        mock_db.commit.assert_awaited_once()
        # Event publisher should be called once for the series
        mock_event_publisher.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_recurring_series_end_before_start_rejected(self, mock_db, mock_event_publisher):
        """Recurring series with end date before start should be rejected."""
        service = RecurringReservationService(mock_db, mock_event_publisher)
        venue_id = uuid4()
        start_date = date.today() + timedelta(days=30)

        data = RecurringReservationCreate(
            reservation_type=ReservationType.BOWLING,
            reservation_date=start_date,
            start_time=time(14, 0),
            end_time=time(15, 0),
            party_size=4,
            recurrence_frequency=RecurrenceFrequency.WEEKLY,
            recurrence_end_date=start_date - timedelta(days=5),  # Before start
            items=[],
        )

        with pytest.raises(ServiceError) as exc_info:
            await service.create_recurring_series(venue_id, data)
        assert exc_info.value.detail["error_code"] == ErrorCode.RECURRING_END_BEFORE_START.value

    @pytest.mark.asyncio
    async def test_get_series(self, mock_db, mock_event_publisher):
        """get_series should return reservations matching the group_id."""
        service = RecurringReservationService(mock_db, mock_event_publisher)
        group_id = uuid4()

        fake_res_1 = MagicMock(spec=Reservation)
        fake_res_1.recurrence_group_id = group_id
        fake_res_2 = MagicMock(spec=Reservation)
        fake_res_2.recurrence_group_id = group_id

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [fake_res_1, fake_res_2]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        result = await service.get_series(group_id)
        assert len(result) == 2

    def test_generate_dates_weekly(self, mock_db, mock_event_publisher):
        """_generate_dates with WEEKLY frequency should produce weekly dates."""
        service = RecurringReservationService(mock_db, mock_event_publisher)
        start = date(2026, 6, 1)
        dates = service._generate_dates(
            start, RecurrenceFrequency.WEEKLY,
            end_date=date(2026, 6, 29),
            max_occurrences=10,
        )
        assert len(dates) == 5  # June 1, 8, 15, 22, 29
        for i in range(1, len(dates)):
            assert (dates[i] - dates[i - 1]).days == 7

    def test_generate_dates_monthly(self, mock_db, mock_event_publisher):
        """_generate_dates with MONTHLY frequency should produce monthly dates."""
        service = RecurringReservationService(mock_db, mock_event_publisher)
        start = date(2026, 1, 15)
        dates = service._generate_dates(
            start, RecurrenceFrequency.MONTHLY,
            end_date=date(2026, 4, 30),
            max_occurrences=10,
        )
        assert len(dates) == 4  # Jan, Feb, Mar, Apr


# ═══════════════════════════════════════════════════════════════════════════════
# TestGroupBookingService
# ═══════════════════════════════════════════════════════════════════════════════

class TestGroupBookingService:
    """Tests for GroupBookingService."""

    @pytest.mark.asyncio
    async def test_create_group_booking(self, mock_db, mock_event_publisher):
        """create_group_booking should create reservations for each resource block."""
        service = GroupBookingService(mock_db, mock_event_publisher)
        venue_id = uuid4()

        # Mock capacity validation: no config found (skips check)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        data = GroupBookingCreate(
            reservation_type=ReservationType.PARTY,
            reservation_date=date.today() + timedelta(days=14),
            start_time=time(18, 0),
            end_time=time(20, 0),
            group_name="Birthday Party",
            group_contact_name="John Doe",
            group_contact_email="john@example.com",
            resource_blocks=[
                ResourceBlockCreate(
                    resource_type=ResourceType.PARTY_ROOM,
                    quantity=1,
                    party_size=20,
                    duration_minutes=120,
                    base_price=Decimal("200.00"),
                ),
                ResourceBlockCreate(
                    resource_type=ResourceType.BOWLING_LANE,
                    quantity=2,
                    party_size=10,
                    duration_minutes=120,
                    base_price=Decimal("50.00"),
                ),
            ],
        )

        result = await service.create_group_booking(venue_id, data)

        assert len(result) == 2  # Two resource blocks = two reservations
        # Each reservation + item = add called at least 4 times
        assert mock_db.add.call_count >= 4
        mock_db.commit.assert_awaited_once()
        mock_event_publisher.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cancel_group(self, mock_db, mock_event_publisher):
        """cancel_group should set all group reservations to CANCELLED."""
        service = GroupBookingService(mock_db, mock_event_publisher)
        group_id = uuid4()

        fake_res_1 = MagicMock(spec=Reservation)
        fake_res_1.status = ReservationStatus.PENDING.value
        fake_res_2 = MagicMock(spec=Reservation)
        fake_res_2.status = ReservationStatus.CONFIRMED.value

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [fake_res_1, fake_res_2]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        result = await service.cancel_group(group_id)

        assert len(result) == 2
        assert fake_res_1.status == ReservationStatus.CANCELLED.value
        assert fake_res_2.status == ReservationStatus.CANCELLED.value
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_group_size_exceeded_rejected(self, mock_db, mock_event_publisher):
        """Total party size > 500 should be rejected."""
        service = GroupBookingService(mock_db, mock_event_publisher)
        venue_id = uuid4()

        # Mock capacity validation: no config found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        data = GroupBookingCreate(
            reservation_type=ReservationType.PARTY,
            reservation_date=date.today() + timedelta(days=14),
            start_time=time(18, 0),
            end_time=time(20, 0),
            group_name="Huge Event",
            group_contact_name="Jane Doe",
            resource_blocks=[
                ResourceBlockCreate(
                    resource_type=ResourceType.PARTY_ROOM,
                    quantity=1,
                    party_size=300,
                ),
                ResourceBlockCreate(
                    resource_type=ResourceType.BOWLING_LANE,
                    quantity=1,
                    party_size=250,
                ),
            ],
        )

        with pytest.raises(ServiceError) as exc_info:
            await service.create_group_booking(venue_id, data)
        assert exc_info.value.detail["error_code"] == ErrorCode.GROUP_SIZE_EXCEEDED.value


# ═══════════════════════════════════════════════════════════════════════════════
# TestDepositService
# ═══════════════════════════════════════════════════════════════════════════════

class TestDepositService:
    """Tests for DepositService."""

    @pytest.mark.asyncio
    async def test_collect_deposit_success(self, mock_db):
        """collect_deposit should call the payment service and update the reservation."""
        service = DepositService(mock_db)
        reservation_id = uuid4()
        customer_id = uuid4()

        fake_reservation = MagicMock(spec=Reservation)
        fake_reservation.id = reservation_id
        fake_reservation.confirmation_code = "AB12CD34"
        fake_reservation.deposit_status = DepositStatus.PENDING.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_reservation
        mock_db.execute.return_value = mock_result

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"transaction_id": "txn_12345"}

        with patch("app.services.deposit_service.httpx.AsyncClient") as mock_client_cls:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client_instance

            result = await service.collect_deposit(
                reservation_id, Decimal("25.00"), customer_id
            )

        assert result["status"] == "collected"
        assert result["transaction_id"] == "txn_12345"
        assert fake_reservation.deposit_status == DepositStatus.COLLECTED.value
        assert fake_reservation.deposit_paid is True
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_collect_deposit_already_collected(self, mock_db):
        """collect_deposit should return already_collected when deposit was already collected."""
        service = DepositService(mock_db)
        reservation_id = uuid4()

        fake_reservation = MagicMock(spec=Reservation)
        fake_reservation.id = reservation_id
        fake_reservation.deposit_status = DepositStatus.COLLECTED.value
        fake_reservation.deposit_transaction_id = "txn_existing"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_reservation
        mock_db.execute.return_value = mock_result

        result = await service.collect_deposit(
            reservation_id, Decimal("25.00"), uuid4()
        )

        assert result["status"] == "already_collected"
        assert result["transaction_id"] == "txn_existing"

    @pytest.mark.asyncio
    async def test_collect_deposit_reservation_not_found(self, mock_db):
        """collect_deposit should raise 404 when reservation not found."""
        service = DepositService(mock_db)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ServiceError) as exc_info:
            await service.collect_deposit(uuid4(), Decimal("25.00"), uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_refund_deposit_success(self, mock_db):
        """refund_deposit should call payment service and update status to REFUNDED."""
        service = DepositService(mock_db)
        reservation_id = uuid4()

        fake_reservation = MagicMock(spec=Reservation)
        fake_reservation.id = reservation_id
        fake_reservation.deposit_status = DepositStatus.COLLECTED.value
        fake_reservation.deposit_transaction_id = "txn_12345"
        fake_reservation.deposit_amount = Decimal("25.00")
        fake_reservation.confirmation_code = "AB12CD34"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_reservation
        mock_db.execute.return_value = mock_result

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "refunded"}

        with patch("app.services.deposit_service.httpx.AsyncClient") as mock_client_cls:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client_instance

            result = await service.refund_deposit(reservation_id, reason="cancellation")

        assert result["status"] == "refunded"
        assert fake_reservation.deposit_status == DepositStatus.REFUNDED.value
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_refund_deposit_no_deposit_to_refund(self, mock_db):
        """refund_deposit should return no_deposit_to_refund when deposit is not collected."""
        service = DepositService(mock_db)
        reservation_id = uuid4()

        fake_reservation = MagicMock(spec=Reservation)
        fake_reservation.id = reservation_id
        fake_reservation.deposit_status = DepositStatus.PENDING.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_reservation
        mock_db.execute.return_value = mock_result

        result = await service.refund_deposit(reservation_id)
        assert result["status"] == "no_deposit_to_refund"

    @pytest.mark.asyncio
    async def test_forfeit_deposit(self, mock_db):
        """forfeit_deposit should set status to FORFEITED."""
        service = DepositService(mock_db)
        reservation_id = uuid4()

        fake_reservation = MagicMock(spec=Reservation)
        fake_reservation.id = reservation_id
        fake_reservation.deposit_status = DepositStatus.COLLECTED.value
        fake_reservation.deposit_amount = Decimal("25.00")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_reservation
        mock_db.execute.return_value = mock_result

        result = await service.forfeit_deposit(reservation_id)

        assert result["status"] == "forfeited"
        assert fake_reservation.deposit_status == DepositStatus.FORFEITED.value
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_forfeit_deposit_not_found(self, mock_db):
        """forfeit_deposit should raise 404 when reservation not found."""
        service = DepositService(mock_db)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ServiceError) as exc_info:
            await service.forfeit_deposit(uuid4())
        assert exc_info.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# TestNotificationClient
# ═══════════════════════════════════════════════════════════════════════════════

class TestNotificationClient:
    """Tests for NotificationClient HTTP integration."""

    @pytest.mark.asyncio
    async def test_send_reservation_confirmation_success(self):
        """send_reservation_confirmation should POST to notification service and return notification_id."""
        client = NotificationClient()
        customer_id = uuid4()

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"notification_id": "notif_abc123"}

        with patch("app.services.notification_client.httpx.AsyncClient") as mock_client_cls:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client_instance

            result = await client.send_reservation_confirmation(
                customer_id=customer_id,
                email="test@example.com",
                confirmation_code="AB12CD34",
                reservation_date="2026-03-15",
                start_time="14:00",
                venue_name="Test Venue",
                party_size=4,
            )

        assert result == "notif_abc123"
        # Verify the POST was called
        mock_client_instance.post.assert_awaited_once()
        call_args = mock_client_instance.post.call_args
        assert "/api/v1/notifications" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["template"] == "reservation_confirmation"
        assert payload["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_send_reservation_confirmation_service_unavailable(self):
        """send_reservation_confirmation should return None when service is unreachable."""
        client = NotificationClient()
        customer_id = uuid4()

        with patch("app.services.notification_client.httpx.AsyncClient") as mock_client_cls:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(
                side_effect=Exception("Connection refused")
            )
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client_instance

            result = await client.send_reservation_confirmation(
                customer_id=customer_id,
                email="test@example.com",
                confirmation_code="AB12CD34",
                reservation_date="2026-03-15",
                start_time="14:00",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_send_reservation_confirmation_non_success_status(self):
        """send_reservation_confirmation should return None on non-2xx response."""
        client = NotificationClient()
        customer_id = uuid4()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("app.services.notification_client.httpx.AsyncClient") as mock_client_cls:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client_instance

            result = await client.send_reservation_confirmation(
                customer_id=customer_id,
                email="test@example.com",
                confirmation_code="AB12CD34",
                reservation_date="2026-03-15",
                start_time="14:00",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_send_cancellation_notice_success(self):
        """send_cancellation_notice should return notification_id on success."""
        client = NotificationClient()
        customer_id = uuid4()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "notif_cancel_456"}

        with patch("app.services.notification_client.httpx.AsyncClient") as mock_client_cls:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client_instance

            result = await client.send_cancellation_notice(
                customer_id=customer_id,
                email="test@example.com",
                confirmation_code="AB12CD34",
                reservation_date="2026-03-15",
                refund_amount="25.00",
            )

        assert result == "notif_cancel_456"
