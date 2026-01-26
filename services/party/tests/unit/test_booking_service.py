"""
=============================================================================
FILE: tests/unit/test_booking_service.py
PURPOSE: Unit tests for BookingService
=============================================================================
"""

import uuid
from datetime import date, time, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.party import (
    PartyBooking,
    PartyPackage,
    PartyAddon,
    PartyTimeline,
    BookingStatus,
    BookingType,
    TimelineStatus,
)
from app.services.booking_service import BookingService
from app.schemas.party import (
    PartyBookingCreate,
    PartyBookingUpdate,
    PartyBookingStatusUpdate,
    BookingAddonCreate,
    PaginationParams,
)


class TestBookingServiceCreate:
    """Tests for BookingService.create_booking method."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> BookingService:
        return BookingService(db_session)

    @pytest.mark.asyncio
    async def test_create_booking_success(
        self,
        service: BookingService,
        sample_package: PartyPackage,
        sample_venue_id: uuid.UUID,
        sample_customer_id: uuid.UUID,
    ):
        """Test successful booking creation."""
        party_date = date.today() + timedelta(days=14)
        booking_data = PartyBookingCreate(
            venue_id=sample_venue_id,
            customer_id=sample_customer_id,
            package_id=sample_package.id,
            booking_type=BookingType.BIRTHDAY,
            party_date=party_date,
            start_time=time(14, 0),
            guest_count=15,
            child_count=12,
            adult_count=3,
            guest_of_honor_name="Tommy",
            guest_of_honor_age=8,
            contact_name="John Smith",
            contact_email="john@example.com",
            contact_phone="555-1234",
            booking_source="web",
        )

        result = await service.create_booking(booking_data)

        assert result is not None
        assert result.id is not None
        assert result.booking_reference.startswith("PB-")
        assert result.venue_id == sample_venue_id
        assert result.customer_id == sample_customer_id
        assert result.package_id == sample_package.id
        assert result.status == BookingStatus.PENDING
        assert result.guest_count == 15
        assert result.guest_of_honor_name == "Tommy"

    @pytest.mark.asyncio
    async def test_create_booking_calculates_pricing(
        self,
        service: BookingService,
        sample_package: PartyPackage,
        sample_venue_id: uuid.UUID,
        sample_customer_id: uuid.UUID,
    ):
        """Test that booking calculates prices correctly."""
        party_date = date.today() + timedelta(days=14)
        booking_data = PartyBookingCreate(
            venue_id=sample_venue_id,
            customer_id=sample_customer_id,
            package_id=sample_package.id,
            party_date=party_date,
            start_time=time(14, 0),
            guest_count=15,  # 7 additional guests above min_guests of 8
            contact_name="John Smith",
            contact_email="john@example.com",
            contact_phone="555-1234",
        )

        result = await service.create_booking(booking_data)

        # Verify pricing calculations
        assert result.base_price > 0
        assert result.deposit_amount > 0
        assert result.balance_due == result.total_price

    @pytest.mark.asyncio
    async def test_create_booking_calculates_end_time(
        self,
        service: BookingService,
        sample_package: PartyPackage,
        sample_venue_id: uuid.UUID,
        sample_customer_id: uuid.UUID,
    ):
        """Test that end time is calculated from duration."""
        party_date = date.today() + timedelta(days=14)
        booking_data = PartyBookingCreate(
            venue_id=sample_venue_id,
            customer_id=sample_customer_id,
            package_id=sample_package.id,
            party_date=party_date,
            start_time=time(14, 0),  # 2:00 PM
            guest_count=10,
            contact_name="John Smith",
            contact_email="john@example.com",
            contact_phone="555-1234",
        )

        result = await service.create_booking(booking_data)

        # Package duration is 120 minutes, so end time should be 4:00 PM
        assert result.start_time == time(14, 0)
        assert result.end_time == time(16, 0)

    @pytest.mark.asyncio
    async def test_create_booking_with_addons(
        self,
        service: BookingService,
        sample_package: PartyPackage,
        sample_addon: PartyAddon,
        sample_venue_id: uuid.UUID,
        sample_customer_id: uuid.UUID,
    ):
        """Test booking creation with addons."""
        party_date = date.today() + timedelta(days=14)
        booking_data = PartyBookingCreate(
            venue_id=sample_venue_id,
            customer_id=sample_customer_id,
            package_id=sample_package.id,
            party_date=party_date,
            start_time=time(14, 0),
            guest_count=10,
            contact_name="John Smith",
            contact_email="john@example.com",
            contact_phone="555-1234",
            addons=[
                BookingAddonCreate(addon_id=sample_addon.id, quantity=2),
            ],
        )

        result = await service.create_booking(booking_data)

        assert result.addons_total > 0
        assert result.total_price > result.base_price

    @pytest.mark.asyncio
    async def test_create_booking_generates_unique_reference(
        self,
        service: BookingService,
        sample_package: PartyPackage,
        sample_venue_id: uuid.UUID,
        sample_customer_id: uuid.UUID,
    ):
        """Test that each booking gets a unique reference."""
        party_date = date.today() + timedelta(days=14)
        booking_data = PartyBookingCreate(
            venue_id=sample_venue_id,
            customer_id=sample_customer_id,
            package_id=sample_package.id,
            party_date=party_date,
            start_time=time(14, 0),
            guest_count=10,
            contact_name="John Smith",
            contact_email="john@example.com",
            contact_phone="555-1234",
        )

        booking1 = await service.create_booking(booking_data)
        booking2 = await service.create_booking(booking_data)

        assert booking1.booking_reference != booking2.booking_reference

    @pytest.mark.asyncio
    async def test_create_booking_package_not_found(
        self,
        service: BookingService,
        sample_venue_id: uuid.UUID,
        sample_customer_id: uuid.UUID,
    ):
        """Test booking creation fails when package doesn't exist."""
        party_date = date.today() + timedelta(days=14)
        booking_data = PartyBookingCreate(
            venue_id=sample_venue_id,
            customer_id=sample_customer_id,
            package_id=uuid.uuid4(),  # Non-existent package
            party_date=party_date,
            start_time=time(14, 0),
            guest_count=10,
            contact_name="John Smith",
            contact_email="john@example.com",
            contact_phone="555-1234",
        )

        with pytest.raises(ValueError, match="Package not found"):
            await service.create_booking(booking_data)


class TestBookingServiceGet:
    """Tests for BookingService.get_booking method."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> BookingService:
        return BookingService(db_session)

    @pytest.mark.asyncio
    async def test_get_booking_success(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
    ):
        """Test successful booking retrieval."""
        result = await service.get_booking(sample_booking.id)

        assert result is not None
        assert result.id == sample_booking.id
        assert result.booking_reference == sample_booking.booking_reference

    @pytest.mark.asyncio
    async def test_get_booking_not_found(self, service: BookingService):
        """Test booking retrieval when not found."""
        random_id = uuid.uuid4()
        result = await service.get_booking(random_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_booking_excludes_deleted(
        self,
        service: BookingService,
        db_session: AsyncSession,
        booking_factory,
    ):
        """Test that deleted bookings are not returned."""
        deleted_booking = booking_factory.create(is_deleted=True)
        db_session.add(deleted_booking)
        await db_session.flush()

        result = await service.get_booking(deleted_booking.id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_booking_by_reference(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
    ):
        """Test booking retrieval by reference code."""
        result = await service.get_booking_by_reference(sample_booking.booking_reference)

        assert result is not None
        assert result.id == sample_booking.id


class TestBookingServiceList:
    """Tests for BookingService.list_bookings method."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> BookingService:
        return BookingService(db_session)

    @pytest.mark.asyncio
    async def test_list_bookings_empty(
        self,
        service: BookingService,
        sample_venue_id: uuid.UUID,
    ):
        """Test listing bookings when none exist."""
        pagination = PaginationParams(page=1, page_size=10)
        bookings, total = await service.list_bookings(sample_venue_id, pagination)

        assert bookings == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_bookings_with_data(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
        sample_venue_id: uuid.UUID,
    ):
        """Test listing bookings with existing data."""
        pagination = PaginationParams(page=1, page_size=10)
        bookings, total = await service.list_bookings(sample_venue_id, pagination)

        assert total == 1
        assert len(bookings) == 1
        assert bookings[0].id == sample_booking.id

    @pytest.mark.asyncio
    async def test_list_bookings_filter_by_status(
        self,
        service: BookingService,
        db_session: AsyncSession,
        sample_venue_id: uuid.UUID,
        sample_customer_id: uuid.UUID,
        sample_package: PartyPackage,
        booking_factory,
    ):
        """Test filtering bookings by status."""
        pending = booking_factory.create(
            venue_id=sample_venue_id,
            customer_id=sample_customer_id,
            package_id=sample_package.id,
            status=BookingStatus.PENDING,
        )
        confirmed = booking_factory.create(
            venue_id=sample_venue_id,
            customer_id=sample_customer_id,
            package_id=sample_package.id,
            status=BookingStatus.CONFIRMED,
        )
        db_session.add_all([pending, confirmed])
        await db_session.flush()

        pagination = PaginationParams(page=1, page_size=10)
        bookings, total = await service.list_bookings(
            sample_venue_id,
            pagination,
            status=BookingStatus.CONFIRMED,
        )

        assert total == 1
        assert bookings[0].status == BookingStatus.CONFIRMED

    @pytest.mark.asyncio
    async def test_list_bookings_filter_by_date_range(
        self,
        service: BookingService,
        db_session: AsyncSession,
        sample_venue_id: uuid.UUID,
        sample_customer_id: uuid.UUID,
        sample_package: PartyPackage,
        booking_factory,
    ):
        """Test filtering bookings by date range."""
        today = date.today()
        booking1 = booking_factory.create(
            venue_id=sample_venue_id,
            customer_id=sample_customer_id,
            package_id=sample_package.id,
            party_date=today + timedelta(days=7),
        )
        booking2 = booking_factory.create(
            venue_id=sample_venue_id,
            customer_id=sample_customer_id,
            package_id=sample_package.id,
            party_date=today + timedelta(days=30),
        )
        db_session.add_all([booking1, booking2])
        await db_session.flush()

        pagination = PaginationParams(page=1, page_size=10)
        bookings, total = await service.list_bookings(
            sample_venue_id,
            pagination,
            date_from=today + timedelta(days=1),
            date_to=today + timedelta(days=14),
        )

        assert total == 1
        assert bookings[0].party_date == today + timedelta(days=7)

    @pytest.mark.asyncio
    async def test_list_bookings_filter_by_customer(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
        sample_venue_id: uuid.UUID,
        sample_customer_id: uuid.UUID,
    ):
        """Test filtering bookings by customer ID."""
        pagination = PaginationParams(page=1, page_size=10)
        bookings, total = await service.list_bookings(
            sample_venue_id,
            pagination,
            customer_id=sample_customer_id,
        )

        assert total == 1
        assert bookings[0].customer_id == sample_customer_id


class TestBookingServiceUpdate:
    """Tests for BookingService.update_booking method."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> BookingService:
        return BookingService(db_session)

    @pytest.mark.asyncio
    async def test_update_booking_success(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
    ):
        """Test successful booking update."""
        update_data = PartyBookingUpdate(
            guest_count=20,
            special_requests="Extra balloons please",
        )

        result = await service.update_booking(sample_booking.id, update_data)

        assert result is not None
        assert result.guest_count == 20
        assert result.special_requests == "Extra balloons please"

    @pytest.mark.asyncio
    async def test_update_booking_partial(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
    ):
        """Test partial booking update."""
        original_contact = sample_booking.contact_name
        update_data = PartyBookingUpdate(guest_count=25)

        result = await service.update_booking(sample_booking.id, update_data)

        assert result is not None
        assert result.guest_count == 25
        assert result.contact_name == original_contact

    @pytest.mark.asyncio
    async def test_update_booking_not_found(self, service: BookingService):
        """Test update when booking doesn't exist."""
        random_id = uuid.uuid4()
        update_data = PartyBookingUpdate(guest_count=20)

        result = await service.update_booking(random_id, update_data)

        assert result is None


class TestBookingServiceStatus:
    """Tests for BookingService status management methods."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> BookingService:
        return BookingService(db_session)

    @pytest.mark.asyncio
    async def test_update_status_to_confirmed(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
    ):
        """Test updating booking status to confirmed."""
        status_update = PartyBookingStatusUpdate(status=BookingStatus.CONFIRMED)

        result = await service.update_booking_status(sample_booking.id, status_update)

        assert result is not None
        assert result.status == BookingStatus.CONFIRMED
        assert result.confirmed_at is not None

    @pytest.mark.asyncio
    async def test_update_status_to_checked_in(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
    ):
        """Test updating booking status to checked in."""
        status_update = PartyBookingStatusUpdate(status=BookingStatus.CHECKED_IN)

        result = await service.update_booking_status(sample_booking.id, status_update)

        assert result is not None
        assert result.status == BookingStatus.CHECKED_IN
        assert result.checked_in_at is not None

    @pytest.mark.asyncio
    async def test_update_status_to_completed(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
    ):
        """Test updating booking status to completed."""
        status_update = PartyBookingStatusUpdate(status=BookingStatus.COMPLETED)

        result = await service.update_booking_status(sample_booking.id, status_update)

        assert result is not None
        assert result.status == BookingStatus.COMPLETED
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_update_status_to_cancelled(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
    ):
        """Test updating booking status to cancelled."""
        status_update = PartyBookingStatusUpdate(
            status=BookingStatus.CANCELLED,
            cancellation_reason="Customer requested cancellation",
        )

        result = await service.update_booking_status(sample_booking.id, status_update)

        assert result is not None
        assert result.status == BookingStatus.CANCELLED
        assert result.cancelled_at is not None
        assert result.cancellation_reason == "Customer requested cancellation"

    @pytest.mark.asyncio
    async def test_check_in_booking(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
    ):
        """Test check-in shortcut method."""
        result = await service.check_in_booking(sample_booking.id)

        assert result is not None
        assert result.status == BookingStatus.CHECKED_IN

    @pytest.mark.asyncio
    async def test_complete_booking(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
    ):
        """Test complete shortcut method."""
        result = await service.complete_booking(sample_booking.id)

        assert result is not None
        assert result.status == BookingStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_cancel_booking(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
    ):
        """Test cancel shortcut method."""
        result = await service.cancel_booking(sample_booking.id, "No longer needed")

        assert result is not None
        assert result.status == BookingStatus.CANCELLED
        assert result.cancellation_reason == "No longer needed"


class TestBookingServiceAddons:
    """Tests for BookingService addon management methods."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> BookingService:
        return BookingService(db_session)

    @pytest.mark.asyncio
    async def test_add_booking_addon(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
        sample_addon: PartyAddon,
    ):
        """Test adding an addon to a booking."""
        addon_data = BookingAddonCreate(addon_id=sample_addon.id, quantity=2)

        result = await service.add_booking_addon(sample_booking.id, addon_data)

        assert result is not None
        assert result.booking_id == sample_booking.id
        assert result.addon_id == sample_addon.id
        assert result.quantity == 2

    @pytest.mark.asyncio
    async def test_add_booking_addon_updates_totals(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
        sample_addon: PartyAddon,
    ):
        """Test that adding addon updates booking totals."""
        original_total = sample_booking.total_price
        addon_data = BookingAddonCreate(addon_id=sample_addon.id, quantity=1)

        await service.add_booking_addon(sample_booking.id, addon_data)

        # Refresh booking to get updated values
        updated_booking = await service.get_booking(sample_booking.id)
        assert updated_booking.addons_total > 0
        assert updated_booking.total_price > original_total

    @pytest.mark.asyncio
    async def test_remove_booking_addon(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
        sample_addon: PartyAddon,
    ):
        """Test removing an addon from a booking."""
        # First add an addon
        addon_data = BookingAddonCreate(addon_id=sample_addon.id, quantity=1)
        await service.add_booking_addon(sample_booking.id, addon_data)

        # Then remove it
        result = await service.remove_booking_addon(sample_booking.id, sample_addon.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_remove_booking_addon_not_found(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
    ):
        """Test removing addon that doesn't exist."""
        random_id = uuid.uuid4()
        result = await service.remove_booking_addon(sample_booking.id, random_id)

        assert result is False


class TestBookingServiceDelete:
    """Tests for BookingService.delete_booking method."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> BookingService:
        return BookingService(db_session)

    @pytest.mark.asyncio
    async def test_delete_booking_soft(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
    ):
        """Test soft delete booking."""
        result = await service.delete_booking(sample_booking.id)

        assert result is True

        # Verify booking is soft deleted
        booking = await service.get_booking(sample_booking.id)
        assert booking is None  # Should not be returned

    @pytest.mark.asyncio
    async def test_delete_booking_not_found(self, service: BookingService):
        """Test delete when booking doesn't exist."""
        random_id = uuid.uuid4()
        result = await service.delete_booking(random_id)

        assert result is False


class TestBookingServiceAvailability:
    """Tests for BookingService availability checking methods."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> BookingService:
        return BookingService(db_session)

    @pytest.mark.asyncio
    async def test_check_availability_empty(
        self,
        service: BookingService,
        sample_venue_id: uuid.UUID,
    ):
        """Test availability when no bookings exist."""
        party_date = date.today() + timedelta(days=14)
        is_available = await service.check_availability(
            venue_id=sample_venue_id,
            party_date=party_date,
            start_time=time(14, 0),
            duration_minutes=120,
        )

        assert is_available is True

    @pytest.mark.asyncio
    async def test_check_availability_conflict(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
        sample_venue_id: uuid.UUID,
    ):
        """Test availability when time slot is taken."""
        is_available = await service.check_availability(
            venue_id=sample_venue_id,
            party_date=sample_booking.party_date,
            start_time=sample_booking.start_time,
            duration_minutes=120,
        )

        assert is_available is False

    @pytest.mark.asyncio
    async def test_check_availability_different_day(
        self,
        service: BookingService,
        sample_booking: PartyBooking,
        sample_venue_id: uuid.UUID,
    ):
        """Test availability on a different day."""
        different_date = sample_booking.party_date + timedelta(days=1)
        is_available = await service.check_availability(
            venue_id=sample_venue_id,
            party_date=different_date,
            start_time=sample_booking.start_time,
            duration_minutes=120,
        )

        assert is_available is True


class TestBookingServiceTodayBookings:
    """Tests for BookingService.get_today_bookings method."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> BookingService:
        return BookingService(db_session)

    @pytest.mark.asyncio
    async def test_get_today_bookings_empty(
        self,
        service: BookingService,
        sample_venue_id: uuid.UUID,
    ):
        """Test getting today's bookings when none exist."""
        result = await service.get_today_bookings(sample_venue_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_today_bookings_with_data(
        self,
        service: BookingService,
        db_session: AsyncSession,
        sample_venue_id: uuid.UUID,
        sample_customer_id: uuid.UUID,
        sample_package: PartyPackage,
        booking_factory,
    ):
        """Test getting today's bookings with existing data."""
        today_booking = booking_factory.create(
            venue_id=sample_venue_id,
            customer_id=sample_customer_id,
            package_id=sample_package.id,
            party_date=date.today(),
            status=BookingStatus.CONFIRMED,
        )
        db_session.add(today_booking)
        await db_session.flush()

        result = await service.get_today_bookings(sample_venue_id)

        assert len(result) == 1
        assert result[0].party_date == date.today()

    @pytest.mark.asyncio
    async def test_get_today_bookings_excludes_cancelled(
        self,
        service: BookingService,
        db_session: AsyncSession,
        sample_venue_id: uuid.UUID,
        sample_customer_id: uuid.UUID,
        sample_package: PartyPackage,
        booking_factory,
    ):
        """Test that cancelled bookings are excluded."""
        cancelled_booking = booking_factory.create(
            venue_id=sample_venue_id,
            customer_id=sample_customer_id,
            package_id=sample_package.id,
            party_date=date.today(),
            status=BookingStatus.CANCELLED,
        )
        db_session.add(cancelled_booking)
        await db_session.flush()

        result = await service.get_today_bookings(sample_venue_id)

        assert len(result) == 0
