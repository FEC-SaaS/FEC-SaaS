"""Unit tests for restaurant services."""

import uuid
from datetime import date, time, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from app.services.table_service import TableService
from app.services.reservation_service import ReservationService
from app.services.menu_service import MenuService
from app.services.order_service import OrderService
from app.services.bar_service import BarService
from app.services.waste_service import WasteService
from app.models.restaurant import (
    TableStatus,
    ReservationStatus,
    OrderStatus,
    OrderType,
)
from app.schemas.restaurant import (
    SectionCreate,
    TableCreate,
    TableStatusUpdate,
    ReservationCreate,
    ReservationSeat,
    MenuCategoryCreate,
    MenuItemCreate,
    MenuItemAvailabilityUpdate,
    OrderCreate,
    OrderItemCreate,
    OrderStatusUpdate,
    BarInventoryCreate,
    BarPourCreate,
    FoodWasteCreate,
)


VENUE_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")
USER_ID = uuid.UUID("abcdefab-cdef-abcd-efab-cdefabcdefab")


def _make_mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


def _make_mock_publisher():
    pub = AsyncMock()
    pub.publish = AsyncMock()
    return pub


# ─── TableService Tests ──────────────────────────────────────────────────────

class TestTableService:
    @pytest.mark.asyncio
    async def test_create_section(self):
        db = _make_mock_db()
        service = TableService(db, _make_mock_publisher())
        data = SectionCreate(section_name="Main Hall", capacity=50)

        # Mock refresh to set attributes on the added object
        async def mock_refresh(obj):
            obj.id = uuid.uuid4()
            obj.venue_id = VENUE_ID
            obj.created_at = datetime.now(timezone.utc)
        db.refresh = mock_refresh

        result = await service.create_section(VENUE_ID, data)
        db.add.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_table(self):
        db = _make_mock_db()
        service = TableService(db, _make_mock_publisher())
        data = TableCreate(table_number="T1", seating_capacity=4)

        async def mock_refresh(obj):
            obj.id = uuid.uuid4()
            obj.venue_id = VENUE_ID
            obj.status = "AVAILABLE"
            obj.created_at = datetime.now(timezone.utc)
        db.refresh = mock_refresh

        result = await service.create_table(VENUE_ID, data)
        db.add.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_sections_pagination(self):
        db = _make_mock_db()
        service = TableService(db, _make_mock_publisher())

        # First call returns count, second returns items
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5

        mock_items_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock(), MagicMock()]
        mock_items_result.scalars.return_value = mock_scalars

        db.execute = AsyncMock(side_effect=[mock_count_result, mock_items_result])

        items, total = await service.list_sections(VENUE_ID, page=1, page_size=10)
        assert total == 5
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_update_table_status(self):
        db = _make_mock_db()
        service = TableService(db, _make_mock_publisher())

        mock_table = MagicMock()
        mock_table.id = uuid.uuid4()
        mock_table.status = TableStatus.AVAILABLE.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_table
        db.execute = AsyncMock(return_value=mock_result)

        data = TableStatusUpdate(status=TableStatus.OCCUPIED)
        result = await service.update_table_status(mock_table.id, data)
        assert result is not None
        assert mock_table.status == TableStatus.OCCUPIED.value

    @pytest.mark.asyncio
    async def test_update_table_status_not_found(self):
        db = _make_mock_db()
        service = TableService(db, _make_mock_publisher())

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        data = TableStatusUpdate(status=TableStatus.OCCUPIED)
        result = await service.update_table_status(uuid.uuid4(), data)
        assert result is None


# ─── ReservationService Tests ────────────────────────────────────────────────

class TestReservationService:
    @pytest.mark.asyncio
    async def test_create_reservation(self):
        db = _make_mock_db()
        publisher = _make_mock_publisher()
        service = ReservationService(db, publisher)
        data = ReservationCreate(
            reservation_date=date(2025, 6, 15),
            reservation_time=time(19, 0),
            party_size=4,
        )

        async def mock_refresh(obj):
            obj.id = uuid.uuid4()
            obj.venue_id = VENUE_ID
            obj.status = ReservationStatus.CONFIRMED.value
            obj.created_at = datetime.now(timezone.utc)
        db.refresh = mock_refresh

        result = await service.create_reservation(VENUE_ID, data)
        db.add.assert_called_once()
        assert result.status == ReservationStatus.CONFIRMED.value

    @pytest.mark.asyncio
    async def test_seat_reservation(self):
        db = _make_mock_db()
        publisher = _make_mock_publisher()
        service = ReservationService(db, publisher)

        mock_reservation = MagicMock()
        mock_reservation.id = uuid.uuid4()
        mock_reservation.venue_id = VENUE_ID
        mock_reservation.table_id = None
        mock_reservation.status = ReservationStatus.CONFIRMED.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_reservation
        db.execute = AsyncMock(return_value=mock_result)

        data = ReservationSeat(table_id=uuid.uuid4())
        result = await service.seat_reservation(mock_reservation.id, data)
        assert result is not None
        assert mock_reservation.status == ReservationStatus.SEATED.value

    @pytest.mark.asyncio
    async def test_cancel_reservation(self):
        db = _make_mock_db()
        publisher = _make_mock_publisher()
        service = ReservationService(db, publisher)

        mock_reservation = MagicMock()
        mock_reservation.id = uuid.uuid4()
        mock_reservation.venue_id = VENUE_ID
        mock_reservation.status = ReservationStatus.CONFIRMED.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_reservation
        db.execute = AsyncMock(return_value=mock_result)

        result = await service.cancel_reservation(mock_reservation.id)
        assert result is not None
        assert mock_reservation.status == ReservationStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_cancel_reservation_not_found(self):
        db = _make_mock_db()
        service = ReservationService(db)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        result = await service.cancel_reservation(uuid.uuid4())
        assert result is None


# ─── MenuService Tests ───────────────────────────────────────────────────────

class TestMenuService:
    @pytest.mark.asyncio
    async def test_create_category(self):
        db = _make_mock_db()
        service = MenuService(db)
        data = MenuCategoryCreate(category_name="Appetizers")

        async def mock_refresh(obj):
            obj.id = uuid.uuid4()
            obj.venue_id = VENUE_ID
            obj.created_at = datetime.now(timezone.utc)
        db.refresh = mock_refresh

        result = await service.create_category(VENUE_ID, data)
        db.add.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_item(self):
        db = _make_mock_db()
        service = MenuService(db)
        data = MenuItemCreate(
            item_name="Caesar Salad",
            base_price=Decimal("12.99"),
        )

        async def mock_refresh(obj):
            obj.id = uuid.uuid4()
            obj.venue_id = VENUE_ID
            obj.is_available = True
            obj.created_at = datetime.now(timezone.utc)
        db.refresh = mock_refresh

        result = await service.create_item(VENUE_ID, data)
        db.add.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_update_item_availability(self):
        db = _make_mock_db()
        service = MenuService(db)

        mock_item = MagicMock()
        mock_item.id = uuid.uuid4()
        mock_item.is_available = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        db.execute = AsyncMock(return_value=mock_result)

        data = MenuItemAvailabilityUpdate(is_available=False)
        result = await service.update_item_availability(mock_item.id, data)
        assert result is not None
        assert mock_item.is_available is False

    @pytest.mark.asyncio
    async def test_list_categories_pagination(self):
        db = _make_mock_db()
        service = MenuService(db)

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 3

        mock_items_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock()]
        mock_items_result.scalars.return_value = mock_scalars

        db.execute = AsyncMock(side_effect=[mock_count_result, mock_items_result])

        items, total = await service.list_categories(VENUE_ID, page=1, page_size=10)
        assert total == 3
        assert len(items) == 1


# ─── OrderService Tests ──────────────────────────────────────────────────────

class TestOrderService:
    @pytest.mark.asyncio
    async def test_create_order(self):
        db = _make_mock_db()
        publisher = _make_mock_publisher()
        service = OrderService(db, publisher)

        # Mock the menu item lookup
        mock_menu_item = MagicMock()
        mock_menu_item.base_price = Decimal("15.00")

        mock_menu_result = MagicMock()
        mock_menu_result.scalar_one_or_none.return_value = mock_menu_item

        # Mock the tax config lookup (returns None -> default tax)
        mock_tax_result = MagicMock()
        mock_tax_result.scalar_one_or_none.return_value = None

        db.execute = AsyncMock(side_effect=[mock_tax_result, mock_menu_result])

        async def mock_refresh(obj):
            obj.id = uuid.uuid4()
            obj.venue_id = VENUE_ID
            obj.status = "PENDING"
            obj.ordered_at = datetime.now(timezone.utc)
            obj.created_at = datetime.now(timezone.utc)
            obj.items = []
        db.refresh = mock_refresh

        data = OrderCreate(
            items=[OrderItemCreate(menu_item_id=uuid.uuid4(), quantity=2)],
        )
        result = await service.create_order(VENUE_ID, data)
        db.add.assert_called()
        assert result is not None


# ─── BarService Tests ─────────────────────────────────────────────────────────

class TestBarService:
    @pytest.mark.asyncio
    async def test_create_inventory_item(self):
        db = _make_mock_db()
        service = BarService(db)
        data = BarInventoryCreate(
            product_name="Absolut Vodka",
            quantity_in_stock=Decimal("750"),
            cost_per_unit=Decimal("25.00"),
        )

        async def mock_refresh(obj):
            obj.id = uuid.uuid4()
            obj.venue_id = VENUE_ID
            obj.created_at = datetime.now(timezone.utc)
        db.refresh = mock_refresh

        result = await service.create_inventory_item(VENUE_ID, data)
        db.add.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_inventory_pagination(self):
        db = _make_mock_db()
        service = BarService(db)

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 10

        mock_items_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock(), MagicMock(), MagicMock()]
        mock_items_result.scalars.return_value = mock_scalars

        db.execute = AsyncMock(side_effect=[mock_count_result, mock_items_result])

        items, total = await service.list_inventory(VENUE_ID, page=1, page_size=10)
        assert total == 10
        assert len(items) == 3


# ─── WasteService Tests ──────────────────────────────────────────────────────

class TestWasteService:
    @pytest.mark.asyncio
    async def test_log_waste(self):
        db = _make_mock_db()
        publisher = _make_mock_publisher()
        service = WasteService(db, publisher)
        data = FoodWasteCreate(
            waste_date=date(2025, 6, 15),
            quantity_wasted=Decimal("2.5"),
            estimated_cost=Decimal("15.00"),
        )

        async def mock_refresh(obj):
            obj.id = uuid.uuid4()
            obj.venue_id = VENUE_ID
            obj.created_at = datetime.now(timezone.utc)
        db.refresh = mock_refresh

        result = await service.log_waste(VENUE_ID, data)
        db.add.assert_called_once()
        assert result is not None
