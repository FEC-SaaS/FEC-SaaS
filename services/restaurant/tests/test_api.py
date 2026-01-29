"""API integration tests for restaurant service."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import get_current_user
from app.core.database import get_db
from app.main import app


VENUE_ID = str(uuid.UUID("12345678-1234-5678-1234-567812345678"))
USER_ID = str(uuid.UUID("abcdefab-cdef-abcd-efab-cdefabcdefab"))

MOCK_USER = {
    "user_id": uuid.UUID(USER_ID),
    "email": "test@example.com",
    "role": "admin",
    "venue_ids": [VENUE_ID],
}


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    db.close = AsyncMock()
    return db


@pytest.fixture
async def client(mock_db):
    async def override_auth():
        return MOCK_USER

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = override_auth
    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_check(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data


class TestTablesAPI:
    @pytest.mark.asyncio
    async def test_list_sections(self, client, mock_db):
        # Mock count query
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0

        # Mock data query
        mock_data = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_data.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(side_effect=[mock_count, mock_data])

        response = await client.get(
            f"/api/v1/restaurant/sections?venue_id={VENUE_ID}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_tables(self, client, mock_db):
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0

        mock_data = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_data.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(side_effect=[mock_count, mock_data])

        response = await client.get(
            f"/api/v1/restaurant/tables?venue_id={VENUE_ID}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] == 0


class TestReservationsAPI:
    @pytest.mark.asyncio
    async def test_list_reservations(self, client, mock_db):
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0

        mock_data = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_data.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(side_effect=[mock_count, mock_data])

        response = await client.get(
            f"/api/v1/restaurant/reservations?venue_id={VENUE_ID}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] == 0


class TestMenuAPI:
    @pytest.mark.asyncio
    async def test_list_categories(self, client, mock_db):
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0

        mock_data = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_data.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(side_effect=[mock_count, mock_data])

        response = await client.get(
            f"/api/v1/restaurant/menu/categories?venue_id={VENUE_ID}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    @pytest.mark.asyncio
    async def test_list_items(self, client, mock_db):
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0

        mock_data = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_data.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(side_effect=[mock_count, mock_data])

        response = await client.get(
            f"/api/v1/restaurant/menu/items?venue_id={VENUE_ID}"
        )
        assert response.status_code == 200


class TestOrdersAPI:
    @pytest.mark.asyncio
    async def test_list_orders(self, client, mock_db):
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0

        mock_data = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_data.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(side_effect=[mock_count, mock_data])

        response = await client.get(
            f"/api/v1/restaurant/orders?venue_id={VENUE_ID}"
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_order_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        order_id = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/restaurant/orders/{order_id}"
        )
        assert response.status_code == 404


class TestBarAPI:
    @pytest.mark.asyncio
    async def test_list_bar_inventory(self, client, mock_db):
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0

        mock_data = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_data.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(side_effect=[mock_count, mock_data])

        response = await client.get(
            f"/api/v1/restaurant/bar/inventory?venue_id={VENUE_ID}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data


class TestWasteAPI:
    @pytest.mark.asyncio
    async def test_get_waste_analytics(self, client, mock_db):
        mock_totals = MagicMock()
        mock_totals_row = MagicMock()
        mock_totals_row.total_cost = 0
        mock_totals_row.total_items = 0
        mock_totals.one.return_value = mock_totals_row

        mock_reasons = MagicMock()
        mock_reasons.all.return_value = []

        mock_top = MagicMock()
        mock_top.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_totals, mock_reasons, mock_top])

        response = await client.get(
            f"/api/v1/restaurant/waste/analytics?venue_id={VENUE_ID}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_waste_cost" in data


class TestTaxConfigAPI:
    @pytest.mark.asyncio
    async def test_get_tax_config_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            f"/api/v1/restaurant/tax-config?venue_id={VENUE_ID}"
        )
        assert response.status_code == 404
