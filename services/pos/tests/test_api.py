"""API-level tests for POS Integration Service endpoints.

Uses ``httpx.AsyncClient`` against the FastAPI ``app`` with mocked
service methods and authentication dependencies.

Covers:
- TransactionAPI       (4 tests)
- PaymentAPI           (2 tests)
- CashDrawerAPI        (2 tests)
- ReconciliationAPI    (2 tests)
- DiscountAPI          (3 tests)
- ShiftAPI             (3 tests)
- TipPoolAPI           (2 tests)
- CurrencyAPI          (2 tests)
- ReportAPI            (3 tests)
- FraudAlertAPI        (3 tests)
- AuditLogAPI          (2 tests)
- ReceiptTemplateAPI   (3 tests)
- WebhookAPI           (4 tests)
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.pos import (
    CashDrawerStatus,
    PaymentStatus,
    ReconciliationStatus,
    TransactionStatus,
)


# =============================================================================
# Shared helpers
# =============================================================================

TEST_VENUE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
TEST_USER = {
    "user_id": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    "email": "manager@example.com",
    "role": "manager",
    "venue_ids": [str(TEST_VENUE_ID)],
}


def _override_auth():
    """Dependency override that bypasses JWT validation."""
    async def _get_user():
        return TEST_USER
    return _get_user


def _override_db():
    """Dependency override that returns an AsyncMock session."""
    async def _get_session():
        yield AsyncMock()
    return _get_session


def _mock_transaction(
    transaction_id: uuid.UUID | None = None,
    status: str = TransactionStatus.PENDING.value,
):
    """Return a mock object that looks like a Transaction ORM instance."""
    txn = MagicMock()
    txn.id = transaction_id or uuid.uuid4()
    txn.venue_id = TEST_VENUE_ID
    txn.customer_id = None
    txn.cashier_id = None
    txn.activity_id = None
    txn.transaction_type = "bowling"
    txn.status = status
    txn.subtotal = Decimal("50.00")
    txn.tax_amount = Decimal("4.00")
    txn.tip_amount = Decimal("0.00")
    txn.discount_amount = Decimal("0.00")
    txn.total_amount = Decimal("54.00")
    txn.currency = "USD"
    txn.notes = None
    txn.metadata_ = None
    txn.idempotency_key = None
    txn.created_at = datetime(2026, 1, 15, 12, 0, 0)
    txn.updated_at = datetime(2026, 1, 15, 12, 0, 0)
    return txn


def _mock_payment(
    payment_id: uuid.UUID | None = None,
    status: str = PaymentStatus.COMPLETED.value,
):
    pay = MagicMock()
    pay.id = payment_id or uuid.uuid4()
    pay.transaction_id = uuid.uuid4()
    pay.venue_id = TEST_VENUE_ID
    pay.payment_method = "credit_card"
    pay.payment_processor = None
    pay.amount = Decimal("54.00")
    pay.status = status
    pay.processor_transaction_id = None
    pay.card_last_four = None
    pay.card_brand = None
    pay.approval_code = "XYZ789"
    pay.error_message = None
    pay.created_at = datetime(2026, 1, 15, 12, 0, 0)
    return pay


def _mock_drawer(
    drawer_id: uuid.UUID | None = None,
    status: str = CashDrawerStatus.OPEN.value,
):
    drawer = MagicMock()
    drawer.id = drawer_id or uuid.uuid4()
    drawer.venue_id = TEST_VENUE_ID
    drawer.terminal_id = "TERM-01"
    drawer.cashier_id = TEST_USER["user_id"]
    drawer.status = status
    drawer.opened_at = datetime(2026, 1, 15, 8, 0, 0)
    drawer.closed_at = None
    drawer.opening_cash = Decimal("200.00")
    drawer.closing_cash = None
    drawer.expected_cash = None
    drawer.variance = None
    drawer.cash_drops_total = Decimal("0")
    drawer.notes = None
    drawer.created_at = datetime(2026, 1, 15, 8, 0, 0)
    return drawer


def _mock_reconciliation(
    recon_id: uuid.UUID | None = None,
    status: str = ReconciliationStatus.PENDING.value,
):
    recon = MagicMock()
    recon.id = recon_id or uuid.uuid4()
    recon.venue_id = TEST_VENUE_ID
    recon.reconciliation_date = date(2026, 1, 15)
    recon.status = status
    recon.total_transactions = 25
    recon.gross_sales = Decimal("5000.00")
    recon.net_sales = Decimal("5400.00")
    recon.total_tax = Decimal("400.00")
    recon.total_tips = Decimal("200.00")
    recon.total_discounts = Decimal("50.00")
    recon.total_refunds = Decimal("100.00")
    recon.cash_total = Decimal("1200.00")
    recon.card_total = Decimal("3800.00")
    recon.other_total = Decimal("400.00")
    recon.variance_amount = Decimal("0.00")
    recon.variance_details = None
    recon.reconciled_by = None
    recon.reconciled_at = None
    recon.notes = None
    recon.created_at = datetime(2026, 1, 15, 23, 0, 0)
    recon.updated_at = datetime(2026, 1, 15, 23, 0, 0)
    return recon


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _apply_dependency_overrides():
    """Override authentication and database dependencies for all tests."""
    app.dependency_overrides[get_current_user] = _override_auth()
    app.dependency_overrides[get_db] = _override_db()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# =============================================================================
# Transaction API
# =============================================================================


class TestTransactionAPI:
    """Tests for /api/v1/pos/transactions endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.transactions._get_service")
    async def test_list_transactions_200(self, mock_get_svc, client):
        txn = _mock_transaction()
        svc = AsyncMock()
        svc.list_transactions.return_value = ([txn], 1)
        mock_get_svc.return_value = svc

        resp = await client.get(
            f"/api/v1/pos/transactions?venue_id={TEST_VENUE_ID}&page=1&page_size=20"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1

    @pytest.mark.asyncio
    @patch("app.api.v1.transactions._get_service")
    async def test_create_transaction_201(self, mock_get_svc, client):
        txn = _mock_transaction(status=TransactionStatus.PENDING.value)
        svc = AsyncMock()
        svc.create_transaction.return_value = txn
        mock_get_svc.return_value = svc

        payload = {
            "transaction_type": "bowling",
            "line_items": [
                {
                    "description": "1 hour bowling",
                    "quantity": 1,
                    "unit_price": "50.00",
                    "total_price": "50.00",
                }
            ],
            "subtotal": "50.00",
            "tax_amount": "4.00",
            "total_amount": "54.00",
        }
        resp = await client.post(
            f"/api/v1/pos/transactions?venue_id={TEST_VENUE_ID}",
            json=payload,
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    @patch("app.api.v1.transactions._get_service")
    async def test_get_transaction_200(self, mock_get_svc, client):
        txn_id = uuid.uuid4()
        txn = _mock_transaction(transaction_id=txn_id)
        svc = AsyncMock()
        svc.get_transaction.return_value = txn
        mock_get_svc.return_value = svc

        resp = await client.get(f"/api/v1/pos/transactions/{txn_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == str(txn_id)

    @pytest.mark.asyncio
    @patch("app.api.v1.transactions._get_service")
    async def test_void_transaction_200(self, mock_get_svc, client):
        txn_id = uuid.uuid4()
        txn = _mock_transaction(
            transaction_id=txn_id,
            status=TransactionStatus.VOIDED.value,
        )
        svc = AsyncMock()
        svc.void_transaction.return_value = txn
        mock_get_svc.return_value = svc

        resp = await client.patch(f"/api/v1/pos/transactions/{txn_id}/void")
        assert resp.status_code == 200
        assert resp.json()["status"] == "voided"


# =============================================================================
# Payment API
# =============================================================================


class TestPaymentAPI:
    """Tests for /api/v1/pos payments endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.payments._get_service")
    async def test_process_payment_201(self, mock_get_svc, client):
        pay = _mock_payment()
        svc = AsyncMock()
        svc.process_payment.return_value = pay
        mock_get_svc.return_value = svc

        txn_id = uuid.uuid4()
        payload = {
            "payment_method": "credit_card",
            "amount": "54.00",
        }
        resp = await client.post(
            f"/api/v1/pos/transactions/{txn_id}/payments?venue_id={TEST_VENUE_ID}",
            json=payload,
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    @patch("app.api.v1.payments._get_service")
    async def test_reverse_payment_200(self, mock_get_svc, client):
        pay_id = uuid.uuid4()
        pay = _mock_payment(payment_id=pay_id, status=PaymentStatus.REVERSED.value)
        svc = AsyncMock()
        svc.reverse_payment.return_value = pay
        mock_get_svc.return_value = svc

        resp = await client.post(f"/api/v1/pos/payments/{pay_id}/reverse")
        assert resp.status_code == 200
        assert resp.json()["status"] == "reversed"


# =============================================================================
# Cash Drawer API
# =============================================================================


class TestCashDrawerAPI:
    """Tests for /api/v1/pos/cash-drawers endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.cash_drawers._get_service")
    async def test_open_drawer_201(self, mock_get_svc, client):
        drawer = _mock_drawer()
        svc = AsyncMock()
        svc.open_drawer.return_value = drawer
        mock_get_svc.return_value = svc

        payload = {"terminal_id": "TERM-01", "opening_cash": "200.00"}
        resp = await client.post(
            f"/api/v1/pos/cash-drawers/open?venue_id={TEST_VENUE_ID}",
            json=payload,
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "open"

    @pytest.mark.asyncio
    @patch("app.api.v1.cash_drawers._get_service")
    async def test_close_drawer_200(self, mock_get_svc, client):
        drawer_id = uuid.uuid4()
        drawer = _mock_drawer(drawer_id=drawer_id, status=CashDrawerStatus.CLOSED.value)
        drawer.closing_cash = Decimal("245.00")
        drawer.expected_cash = Decimal("250.00")
        drawer.variance = Decimal("-5.00")
        drawer.closed_at = datetime(2026, 1, 15, 17, 0, 0)
        svc = AsyncMock()
        svc.close_drawer.return_value = drawer
        mock_get_svc.return_value = svc

        payload = {"closing_cash": "245.00"}
        resp = await client.post(
            f"/api/v1/pos/cash-drawers/{drawer_id}/close",
            json=payload,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"


# =============================================================================
# Reconciliation API
# =============================================================================


class TestReconciliationAPI:
    """Tests for /api/v1/pos/reconciliation endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.reconciliation._get_service")
    async def test_create_reconciliation_201(self, mock_get_svc, client):
        recon = _mock_reconciliation()
        svc = AsyncMock()
        svc.create_reconciliation.return_value = recon
        mock_get_svc.return_value = svc

        payload = {"reconciliation_date": "2026-01-15"}
        resp = await client.post(
            f"/api/v1/pos/reconciliation/daily?venue_id={TEST_VENUE_ID}",
            json=payload,
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    @patch("app.api.v1.reconciliation._get_service")
    async def test_complete_reconciliation_200(self, mock_get_svc, client):
        recon_id = uuid.uuid4()
        recon = _mock_reconciliation(
            recon_id=recon_id,
            status=ReconciliationStatus.COMPLETED.value,
        )
        recon.reconciled_by = TEST_USER["user_id"]
        recon.reconciled_at = datetime(2026, 1, 15, 23, 30, 0)
        svc = AsyncMock()
        svc.complete_reconciliation.return_value = recon
        mock_get_svc.return_value = svc

        resp = await client.patch(
            f"/api/v1/pos/reconciliation/{recon_id}/complete"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"


# =============================================================================
# Discount API
# =============================================================================


def _mock_discount(
    discount_id: uuid.UUID | None = None,
    is_active: bool = True,
):
    discount = MagicMock()
    discount.id = discount_id or uuid.uuid4()
    discount.venue_id = TEST_VENUE_ID
    discount.name = "Happy Hour 20% Off"
    discount.discount_type = "percentage"
    discount.value = Decimal("20.00")
    discount.applies_to = "food_beverage"
    discount.is_active = is_active
    discount.start_time = "16:00:00"
    discount.end_time = "18:00:00"
    discount.active_days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    discount.min_purchase_amount = Decimal("0.00")
    discount.max_discount_amount = None
    discount.created_at = datetime(2026, 1, 15, 12, 0, 0)
    discount.updated_at = datetime(2026, 1, 15, 12, 0, 0)
    return discount


class TestDiscountAPI:
    """Tests for /api/v1/pos/discounts endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.discounts._get_service")
    async def test_create_discount_201(self, mock_get_svc, client):
        discount = _mock_discount()
        svc = AsyncMock()
        svc.create_discount.return_value = discount
        mock_get_svc.return_value = svc

        payload = {
            "name": "Happy Hour 20% Off",
            "discount_type": "percentage",
            "value": "20.00",
            "applies_to": "food_beverage",
        }
        resp = await client.post(
            f"/api/v1/pos/discounts?venue_id={TEST_VENUE_ID}",
            json=payload,
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    @patch("app.api.v1.discounts._get_service")
    async def test_list_discounts_200(self, mock_get_svc, client):
        discount = _mock_discount()
        svc = AsyncMock()
        svc.list_discounts.return_value = ([discount], 1)
        mock_get_svc.return_value = svc

        resp = await client.get(
            f"/api/v1/pos/discounts?venue_id={TEST_VENUE_ID}"
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.asyncio
    @patch("app.api.v1.discounts._get_service")
    async def test_apply_discount_200(self, mock_get_svc, client):
        svc = AsyncMock()
        svc.apply_discount.return_value = {
            "discount_id": str(uuid.uuid4()),
            "transaction_id": str(uuid.uuid4()),
            "discount_amount": "20.00",
        }
        mock_get_svc.return_value = svc

        discount_id = uuid.uuid4()
        payload = {"transaction_id": str(uuid.uuid4())}
        resp = await client.post(
            f"/api/v1/pos/discounts/{discount_id}/apply",
            json=payload,
        )
        assert resp.status_code == 200


# =============================================================================
# Shift API
# =============================================================================


def _mock_shift(
    shift_id: uuid.UUID | None = None,
    status: str = "active",
):
    shift = MagicMock()
    shift.id = shift_id or uuid.uuid4()
    shift.venue_id = TEST_VENUE_ID
    shift.employee_id = TEST_USER["user_id"]
    shift.terminal_id = "TERM-01"
    shift.status = status
    shift.started_at = datetime(2026, 1, 15, 8, 0, 0)
    shift.ended_at = None
    shift.total_sales = Decimal("0.00")
    shift.transaction_count = 0
    shift.break_minutes = 0
    shift.notes = None
    shift.created_at = datetime(2026, 1, 15, 8, 0, 0)
    shift.updated_at = datetime(2026, 1, 15, 8, 0, 0)
    return shift


class TestShiftAPI:
    """Tests for /api/v1/pos/shifts endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.shifts._get_service")
    async def test_start_shift_201(self, mock_get_svc, client):
        shift = _mock_shift()
        svc = AsyncMock()
        svc.start_shift.return_value = shift
        mock_get_svc.return_value = svc

        payload = {"terminal_id": "TERM-01"}
        resp = await client.post(
            f"/api/v1/pos/shifts/start?venue_id={TEST_VENUE_ID}",
            json=payload,
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "active"

    @pytest.mark.asyncio
    @patch("app.api.v1.shifts._get_service")
    async def test_end_shift_200(self, mock_get_svc, client):
        shift_id = uuid.uuid4()
        shift = _mock_shift(shift_id=shift_id, status="completed")
        shift.ended_at = datetime(2026, 1, 15, 17, 0, 0)
        shift.total_sales = Decimal("1250.00")
        shift.transaction_count = 45
        svc = AsyncMock()
        svc.end_shift.return_value = shift
        mock_get_svc.return_value = svc

        payload = {"notes": "Good shift"}
        resp = await client.post(
            f"/api/v1/pos/shifts/{shift_id}/end",
            json=payload,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    @pytest.mark.asyncio
    @patch("app.api.v1.shifts._get_service")
    async def test_list_shifts_200(self, mock_get_svc, client):
        shift = _mock_shift()
        svc = AsyncMock()
        svc.list_shifts.return_value = ([shift], 1)
        mock_get_svc.return_value = svc

        resp = await client.get(
            f"/api/v1/pos/shifts?venue_id={TEST_VENUE_ID}"
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


# =============================================================================
# Tip Pool API
# =============================================================================


def _mock_tip_pool(
    pool_id: uuid.UUID | None = None,
    status: str = "pending",
):
    pool = MagicMock()
    pool.id = pool_id or uuid.uuid4()
    pool.venue_id = TEST_VENUE_ID
    pool.pool_date = date(2026, 1, 15)
    pool.distribution_method = "hours_worked"
    pool.total_tips = Decimal("450.00")
    pool.status = status
    pool.distributed_at = None
    pool.distributed_by = None
    pool.created_at = datetime(2026, 1, 15, 23, 0, 0)
    pool.updated_at = datetime(2026, 1, 15, 23, 0, 0)
    return pool


class TestTipPoolAPI:
    """Tests for /api/v1/pos/tip-pools endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.tip_pools._get_service")
    async def test_create_tip_pool_201(self, mock_get_svc, client):
        pool = _mock_tip_pool()
        svc = AsyncMock()
        svc.create_tip_pool.return_value = pool
        mock_get_svc.return_value = svc

        payload = {
            "pool_date": "2026-01-15",
            "distribution_method": "hours_worked",
            "total_tips": "450.00",
        }
        resp = await client.post(
            f"/api/v1/pos/tip-pools?venue_id={TEST_VENUE_ID}",
            json=payload,
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    @patch("app.api.v1.tip_pools._get_service")
    async def test_distribute_tips_200(self, mock_get_svc, client):
        pool_id = uuid.uuid4()
        pool = _mock_tip_pool(pool_id=pool_id, status="distributed")
        pool.distributed_at = datetime(2026, 1, 15, 23, 30, 0)
        pool.distributed_by = TEST_USER["user_id"]
        svc = AsyncMock()
        svc.distribute_tips.return_value = pool
        mock_get_svc.return_value = svc

        payload = {
            "employees": [
                {"employee_id": str(uuid.uuid4()), "hours_worked": 8.0},
            ]
        }
        resp = await client.post(
            f"/api/v1/pos/tip-pools/{pool_id}/distribute",
            json=payload,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "distributed"


# =============================================================================
# Currency API
# =============================================================================


def _mock_currency(
    currency_id: uuid.UUID | None = None,
    code: str = "EUR",
):
    currency = MagicMock()
    currency.id = currency_id or uuid.uuid4()
    currency.code = code
    currency.name = "Euro"
    currency.symbol = "€"
    currency.exchange_rate = Decimal("0.92")
    currency.decimal_places = 2
    currency.is_active = True
    currency.last_updated = datetime(2026, 1, 15, 12, 0, 0)
    currency.created_at = datetime(2026, 1, 15, 12, 0, 0)
    return currency


class TestCurrencyAPI:
    """Tests for /api/v1/pos/currencies endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.currencies._get_service")
    async def test_add_currency_201(self, mock_get_svc, client):
        currency = _mock_currency()
        svc = AsyncMock()
        svc.add_currency.return_value = currency
        mock_get_svc.return_value = svc

        payload = {
            "code": "EUR",
            "name": "Euro",
            "symbol": "€",
            "exchange_rate": "0.92",
            "decimal_places": 2,
        }
        resp = await client.post(
            "/api/v1/pos/currencies",
            json=payload,
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    @patch("app.api.v1.currencies._get_service")
    async def test_convert_currency_200(self, mock_get_svc, client):
        svc = AsyncMock()
        svc.convert.return_value = {
            "from_currency": "USD",
            "to_currency": "EUR",
            "original_amount": "100.00",
            "converted_amount": "92.00",
            "exchange_rate": "0.92",
        }
        mock_get_svc.return_value = svc

        payload = {
            "amount": "100.00",
            "from_currency": "USD",
            "to_currency": "EUR",
        }
        resp = await client.post(
            "/api/v1/pos/currencies/convert",
            json=payload,
        )
        assert resp.status_code == 200
        assert resp.json()["converted_amount"] == "92.00"


# =============================================================================
# Report API
# =============================================================================


class TestReportAPI:
    """Tests for /api/v1/pos/reports endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.reports._get_service")
    async def test_get_sales_report_200(self, mock_get_svc, client):
        svc = AsyncMock()
        svc.get_sales_report.return_value = {
            "venue_id": str(TEST_VENUE_ID),
            "start_date": "2026-01-01",
            "end_date": "2026-01-28",
            "total_transactions": 500,
            "gross_sales": "25000.00",
            "net_sales": "23750.00",
            "total_tax": "2000.00",
            "total_tips": "1000.00",
            "total_discounts": "250.00",
        }
        mock_get_svc.return_value = svc

        resp = await client.get(
            f"/api/v1/pos/reports/sales?venue_id={TEST_VENUE_ID}&start_date=2026-01-01&end_date=2026-01-28"
        )
        assert resp.status_code == 200
        assert resp.json()["total_transactions"] == 500

    @pytest.mark.asyncio
    @patch("app.api.v1.reports._get_service")
    async def test_get_employee_performance_200(self, mock_get_svc, client):
        svc = AsyncMock()
        svc.get_employee_performance.return_value = [
            {
                "employee_id": str(uuid.uuid4()),
                "transaction_count": 50,
                "total_sales": "2500.00",
                "average_transaction": "50.00",
            }
        ]
        mock_get_svc.return_value = svc

        resp = await client.get(
            f"/api/v1/pos/reports/employee-performance?venue_id={TEST_VENUE_ID}&start_date=2026-01-01&end_date=2026-01-28"
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    @patch("app.api.v1.reports._get_service")
    async def test_get_hourly_sales_200(self, mock_get_svc, client):
        svc = AsyncMock()
        svc.get_hourly_sales.return_value = [
            {"hour": 10, "transaction_count": 5, "total_sales": "250.00"},
            {"hour": 11, "transaction_count": 8, "total_sales": "400.00"},
        ]
        mock_get_svc.return_value = svc

        resp = await client.get(
            f"/api/v1/pos/reports/hourly-sales?venue_id={TEST_VENUE_ID}&date=2026-01-28"
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2


# =============================================================================
# Fraud Alert API
# =============================================================================


def _mock_fraud_alert(
    alert_id: uuid.UUID | None = None,
    status: str = "pending",
):
    alert = MagicMock()
    alert.id = alert_id or uuid.uuid4()
    alert.venue_id = TEST_VENUE_ID
    alert.transaction_id = uuid.uuid4()
    alert.alert_type = "velocity_check"
    alert.severity = "high"
    alert.fraud_score = Decimal("0.92")
    alert.status = status
    alert.details = {"reason": "Multiple high-value transactions"}
    alert.investigator_id = None
    alert.investigated_at = None
    alert.resolution = None
    alert.action_taken = None
    alert.resolved_by = None
    alert.resolved_at = None
    alert.created_at = datetime(2026, 1, 15, 12, 0, 0)
    alert.updated_at = datetime(2026, 1, 15, 12, 0, 0)
    return alert


class TestFraudAlertAPI:
    """Tests for /api/v1/pos/fraud-alerts endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.fraud_alerts._get_service")
    async def test_list_fraud_alerts_200(self, mock_get_svc, client):
        alert = _mock_fraud_alert()
        svc = AsyncMock()
        svc.list_alerts.return_value = ([alert], 1)
        mock_get_svc.return_value = svc

        resp = await client.get(
            f"/api/v1/pos/fraud-alerts?venue_id={TEST_VENUE_ID}"
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.asyncio
    @patch("app.api.v1.fraud_alerts._get_service")
    async def test_investigate_alert_200(self, mock_get_svc, client):
        alert_id = uuid.uuid4()
        alert = _mock_fraud_alert(alert_id=alert_id, status="investigating")
        alert.investigator_id = TEST_USER["user_id"]
        alert.investigated_at = datetime(2026, 1, 15, 14, 0, 0)
        svc = AsyncMock()
        svc.investigate_alert.return_value = alert
        mock_get_svc.return_value = svc

        payload = {"notes": "Reviewing transaction patterns"}
        resp = await client.post(
            f"/api/v1/pos/fraud-alerts/{alert_id}/investigate",
            json=payload,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "investigating"

    @pytest.mark.asyncio
    @patch("app.api.v1.fraud_alerts._get_service")
    async def test_resolve_alert_200(self, mock_get_svc, client):
        alert_id = uuid.uuid4()
        alert = _mock_fraud_alert(alert_id=alert_id, status="resolved")
        alert.resolution = "confirmed_fraud"
        alert.action_taken = "Voided transaction"
        alert.resolved_by = TEST_USER["user_id"]
        alert.resolved_at = datetime(2026, 1, 15, 15, 0, 0)
        svc = AsyncMock()
        svc.resolve_alert.return_value = alert
        mock_get_svc.return_value = svc

        payload = {
            "resolution": "confirmed_fraud",
            "action_taken": "Voided transaction",
        }
        resp = await client.post(
            f"/api/v1/pos/fraud-alerts/{alert_id}/resolve",
            json=payload,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"


# =============================================================================
# Audit Log API
# =============================================================================


def _mock_audit_log(
    log_id: uuid.UUID | None = None,
):
    log = MagicMock()
    log.id = log_id or uuid.uuid4()
    log.venue_id = TEST_VENUE_ID
    log.user_id = TEST_USER["user_id"]
    log.action = "transaction.created"
    log.resource_type = "transaction"
    log.resource_id = uuid.uuid4()
    log.details = {"amount": "54.00"}
    log.ip_address = "192.168.1.100"
    log.user_agent = "TestAgent/1.0"
    log.created_at = datetime(2026, 1, 15, 12, 0, 0)
    return log


class TestAuditLogAPI:
    """Tests for /api/v1/pos/audit-logs endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.audit_logs._get_service")
    async def test_list_audit_logs_200(self, mock_get_svc, client):
        log = _mock_audit_log()
        svc = AsyncMock()
        svc.list_audit_logs.return_value = ([log], 1)
        mock_get_svc.return_value = svc

        resp = await client.get(
            f"/api/v1/pos/audit-logs?venue_id={TEST_VENUE_ID}"
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.asyncio
    @patch("app.api.v1.audit_logs._get_service")
    async def test_get_audit_log_200(self, mock_get_svc, client):
        log_id = uuid.uuid4()
        log = _mock_audit_log(log_id=log_id)
        svc = AsyncMock()
        svc.get_audit_log.return_value = log
        mock_get_svc.return_value = svc

        resp = await client.get(f"/api/v1/pos/audit-logs/{log_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == str(log_id)


# =============================================================================
# Receipt Template API
# =============================================================================


def _mock_receipt_template(
    template_id: uuid.UUID | None = None,
    is_active: bool = True,
):
    template = MagicMock()
    template.id = template_id or uuid.uuid4()
    template.venue_id = TEST_VENUE_ID
    template.name = "Bowling Receipt"
    template.template_type = "thermal"
    template.header_text = "Welcome to Fun Bowl!"
    template.footer_text = "Thank you!"
    template.show_logo = True
    template.show_tax_breakdown = True
    template.template_body = "<div>{{details}}</div>"
    template.is_default = False
    template.is_active = is_active
    template.created_at = datetime(2026, 1, 15, 12, 0, 0)
    template.updated_at = datetime(2026, 1, 15, 12, 0, 0)
    return template


class TestReceiptTemplateAPI:
    """Tests for /api/v1/pos/receipt-templates endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.receipt_templates._get_service")
    async def test_create_template_201(self, mock_get_svc, client):
        template = _mock_receipt_template()
        svc = AsyncMock()
        svc.create_template.return_value = template
        mock_get_svc.return_value = svc

        payload = {
            "name": "Bowling Receipt",
            "template_type": "thermal",
            "header_text": "Welcome!",
            "footer_text": "Thanks!",
            "show_logo": True,
            "show_tax_breakdown": True,
            "template_body": "<div>{{details}}</div>",
        }
        resp = await client.post(
            f"/api/v1/pos/receipt-templates?venue_id={TEST_VENUE_ID}",
            json=payload,
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    @patch("app.api.v1.receipt_templates._get_service")
    async def test_list_templates_200(self, mock_get_svc, client):
        template = _mock_receipt_template()
        svc = AsyncMock()
        svc.list_templates.return_value = ([template], 1)
        mock_get_svc.return_value = svc

        resp = await client.get(
            f"/api/v1/pos/receipt-templates?venue_id={TEST_VENUE_ID}"
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.asyncio
    @patch("app.api.v1.receipt_templates._get_service")
    async def test_preview_template_200(self, mock_get_svc, client):
        template_id = uuid.uuid4()
        svc = AsyncMock()
        svc.render_template.return_value = {
            "template_id": str(template_id),
            "rendered_content": "<html>Receipt content</html>",
        }
        mock_get_svc.return_value = svc

        payload = {"sample_transaction_id": str(uuid.uuid4())}
        resp = await client.post(
            f"/api/v1/pos/receipt-templates/{template_id}/preview",
            json=payload,
        )
        assert resp.status_code == 200
        assert "rendered_content" in resp.json()


# =============================================================================
# Webhook API
# =============================================================================


class TestWebhookAPI:
    """Tests for /api/v1/pos/webhooks endpoints."""

    @pytest.mark.asyncio
    @patch("app.api.v1.webhooks._verify_stripe_signature")
    @patch("app.api.v1.webhooks._process_stripe_event")
    async def test_stripe_webhook_200(self, mock_process, mock_verify, client):
        mock_verify.return_value = True
        mock_process.return_value = {"status": "processed"}

        payload = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_123"}},
        }
        resp = await client.post(
            "/api/v1/pos/webhooks/stripe",
            json=payload,
            headers={"Stripe-Signature": "test_signature"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @patch("app.api.v1.webhooks._verify_toast_signature")
    @patch("app.api.v1.webhooks._process_toast_event")
    async def test_toast_webhook_200(self, mock_process, mock_verify, client):
        mock_verify.return_value = True
        mock_process.return_value = {"status": "processed"}

        payload = {
            "eventType": "ORDER_COMPLETED",
            "orderId": "toast-order-123",
        }
        resp = await client.post(
            "/api/v1/pos/webhooks/toast",
            json=payload,
            headers={"X-Toast-Signature": "test_signature"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @patch("app.api.v1.webhooks._verify_square_signature")
    @patch("app.api.v1.webhooks._process_square_event")
    async def test_square_webhook_200(self, mock_process, mock_verify, client):
        mock_verify.return_value = True
        mock_process.return_value = {"status": "processed"}

        payload = {
            "type": "payment.completed",
            "data": {"id": "sq_payment_123"},
        }
        resp = await client.post(
            "/api/v1/pos/webhooks/square",
            json=payload,
            headers={"X-Square-Signature": "test_signature"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @patch("app.api.v1.webhooks._verify_clover_signature")
    @patch("app.api.v1.webhooks._process_clover_event")
    async def test_clover_webhook_200(self, mock_process, mock_verify, client):
        mock_verify.return_value = True
        mock_process.return_value = {"status": "processed"}

        payload = {
            "type": "ORDER_CREATED",
            "data": {"orderId": "clover-order-123"},
        }
        resp = await client.post(
            "/api/v1/pos/webhooks/clover",
            json=payload,
            headers={"X-Clover-Signature": "test_signature"},
        )
        assert resp.status_code == 200
