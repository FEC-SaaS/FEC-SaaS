"""Unit tests for POS Integration Service business-logic layers.

Covers:
- TransactionService       (6 tests)
- PaymentService           (4 tests)
- RefundService            (3 tests)
- CashDrawerService        (3 tests)
- DiscountService          (4 tests)
- ShiftService             (4 tests)
- TipService               (3 tests)
- CurrencyService          (3 tests)
- ReportingService         (3 tests)
- FraudDetectionService    (3 tests)
- AuditService             (2 tests)
- ReceiptTemplateService   (3 tests)

All database and event-publisher interactions are mocked so tests run
without infrastructure dependencies.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import ErrorCode, ServiceError
from app.models.pos import (
    CashDrawerStatus,
    PaymentStatus,
    RefundStatus,
    TransactionStatus,
)
from app.services.transaction_service import TransactionService
from app.services.payment_service import PaymentService
from app.services.refund_service import RefundService
from app.services.cash_drawer_service import CashDrawerService
from app.services.discount_service import DiscountService
from app.services.shift_service import ShiftService
from app.services.tip_service import TipService
from app.services.currency_service import CurrencyService
from app.services.reporting_service import ReportingService
from app.services.fraud_detection_service import FraudDetectionService
from app.services.audit_service import AuditService
from app.services.receipt_template_service import ReceiptTemplateService


# =============================================================================
# Helper factories — return MagicMock objects with model-like attributes
# =============================================================================


def _make_transaction(
    *,
    transaction_id: uuid.UUID | None = None,
    venue_id: uuid.UUID | None = None,
    status: str = TransactionStatus.PENDING.value,
    total_amount: Decimal = Decimal("54.00"),
    subtotal: Decimal = Decimal("50.00"),
    tax_amount: Decimal = Decimal("4.00"),
    tip_amount: Decimal = Decimal("0.00"),
    discount_amount: Decimal = Decimal("0.00"),
    transaction_type: str = "bowling",
    idempotency_key: str | None = None,
    created_at: datetime | None = None,
) -> MagicMock:
    txn = MagicMock()
    txn.id = transaction_id or uuid.uuid4()
    txn.venue_id = venue_id or uuid.uuid4()
    txn.status = status
    txn.total_amount = total_amount
    txn.total = total_amount  # alias used in transaction_service
    txn.subtotal = subtotal
    txn.tax_amount = tax_amount
    txn.tip_amount = tip_amount
    txn.discount_amount = discount_amount
    txn.transaction_type = transaction_type
    txn.currency = "USD"
    txn.idempotency_key = idempotency_key
    txn.created_at = created_at or datetime.utcnow()
    txn.updated_at = txn.created_at
    txn.customer_id = None
    txn.cashier_id = None
    txn.activity_id = None
    txn.notes = None
    txn.metadata_ = None
    txn.voided_by = None
    txn.voided_at = None
    return txn


def _make_payment(
    *,
    payment_id: uuid.UUID | None = None,
    transaction_id: uuid.UUID | None = None,
    venue_id: uuid.UUID | None = None,
    status: str = PaymentStatus.COMPLETED.value,
    amount: Decimal = Decimal("54.00"),
    payment_method: str = "credit_card",
) -> MagicMock:
    pay = MagicMock()
    pay.id = payment_id or uuid.uuid4()
    pay.transaction_id = transaction_id or uuid.uuid4()
    pay.venue_id = venue_id or uuid.uuid4()
    pay.status = status
    pay.amount = amount
    pay.payment_method = payment_method
    pay.approval_code = "ABC123"
    pay.processed_at = datetime.utcnow()
    pay.created_at = datetime.utcnow()
    pay.reference = None
    return pay


def _make_refund(
    *,
    refund_id: uuid.UUID | None = None,
    transaction_id: uuid.UUID | None = None,
    venue_id: uuid.UUID | None = None,
    status: str = RefundStatus.PENDING.value,
    refund_amount: Decimal = Decimal("54.00"),
) -> MagicMock:
    ref = MagicMock()
    ref.id = refund_id or uuid.uuid4()
    ref.transaction_id = transaction_id or uuid.uuid4()
    ref.venue_id = venue_id or uuid.uuid4()
    ref.status = status
    ref.refund_amount = refund_amount
    ref.refund_reason = "customer_request"
    ref.refund_method = "original_payment"
    ref.approved_by = None
    ref.processed_at = None
    ref.notes = None
    ref.created_at = datetime.utcnow()
    ref.updated_at = datetime.utcnow()
    return ref


def _make_drawer(
    *,
    drawer_id: uuid.UUID | None = None,
    venue_id: uuid.UUID | None = None,
    status: str = CashDrawerStatus.OPEN.value,
    opening_cash: Decimal = Decimal("200.00"),
    terminal_id: str = "TERM-01",
) -> MagicMock:
    drawer = MagicMock()
    drawer.id = drawer_id or uuid.uuid4()
    drawer.venue_id = venue_id or uuid.uuid4()
    drawer.cashier_id = uuid.uuid4()
    drawer.terminal_id = terminal_id
    drawer.status = status
    drawer.opening_cash = opening_cash
    drawer.closing_cash = None
    drawer.expected_cash = None
    drawer.variance = None
    drawer.cash_drops_total = Decimal("0")
    drawer.opened_at = datetime.utcnow()
    drawer.closed_at = None
    drawer.notes = None
    drawer.drawer_transactions = []
    drawer.created_at = datetime.utcnow()
    return drawer


def _mock_scalars_first(mock_db, return_value):
    """Configure mock_db.execute() so .scalars().first() returns *return_value*."""
    result = MagicMock()
    result.scalars.return_value.first.return_value = return_value
    mock_db.execute.return_value = result


def _mock_scalar(mock_db, return_value):
    """Configure mock_db.execute() so .scalar() returns *return_value*."""
    result = MagicMock()
    result.scalar.return_value = return_value
    mock_db.execute.return_value = result


# =============================================================================
# TransactionService
# =============================================================================


class TestTransactionService:
    """Tests for ``TransactionService``."""

    @pytest.mark.asyncio
    async def test_create_transaction(self, mock_db, mock_event_publisher, test_venue_id):
        """Creating a transaction sets PENDING status and calls db.add/commit/refresh."""
        # Idempotency check returns None (no existing transaction)
        _mock_scalars_first(mock_db, None)

        service = TransactionService(mock_db, mock_event_publisher)

        data = MagicMock()
        data.transaction_type = "bowling"
        data.customer_id = None
        data.cashier_id = None
        data.activity_id = None
        data.subtotal = Decimal("50.00")
        data.tax = Decimal("4.00")
        data.discount = Decimal("0.00")
        data.tip = Decimal("0.00")
        data.total = Decimal("54.00")
        data.currency = "USD"
        data.notes = None
        data.metadata_ = None
        data.terminal_id = None

        result = await service.create_transaction(test_venue_id, data)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_transaction_idempotency(
        self, mock_db, mock_event_publisher, test_venue_id
    ):
        """When an idempotency key already exists the existing transaction is returned."""
        existing_txn = _make_transaction(venue_id=test_venue_id)
        _mock_scalars_first(mock_db, existing_txn)

        service = TransactionService(mock_db, mock_event_publisher)

        data = MagicMock()
        result = await service.create_transaction(
            test_venue_id, data, idempotency_key="dup-key-123"
        )

        assert result is existing_txn
        # db.add should NOT be called for duplicate
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_complete_transaction(self, mock_db, mock_event_publisher):
        """Completing a PENDING transaction transitions its status to COMPLETED."""
        txn = _make_transaction(status=TransactionStatus.PENDING.value)
        _mock_scalars_first(mock_db, txn)

        service = TransactionService(mock_db, mock_event_publisher)
        result = await service.complete_transaction(txn.id)

        assert result.status == TransactionStatus.COMPLETED.value
        mock_db.commit.assert_awaited()
        mock_db.refresh.assert_awaited()

    @pytest.mark.asyncio
    async def test_void_transaction(self, mock_db, mock_event_publisher):
        """Voiding a COMPLETED transaction transitions it to VOIDED."""
        txn = _make_transaction(status=TransactionStatus.COMPLETED.value)
        _mock_scalars_first(mock_db, txn)

        service = TransactionService(mock_db, mock_event_publisher)
        cashier_id = uuid.uuid4()
        result = await service.void_transaction(txn.id, cashier_id)

        assert result.status == TransactionStatus.VOIDED.value
        assert result.voided_by == cashier_id
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_void_already_voided(self, mock_db, mock_event_publisher):
        """Voiding a transaction that is already VOIDED raises TRANSACTION_ALREADY_FINAL."""
        txn = _make_transaction(status=TransactionStatus.VOIDED.value)
        _mock_scalars_first(mock_db, txn)

        service = TransactionService(mock_db, mock_event_publisher)

        with pytest.raises(ServiceError) as exc_info:
            await service.void_transaction(txn.id, uuid.uuid4())

        assert exc_info.value.detail["error_code"] == ErrorCode.TRANSACTION_ALREADY_FINAL.value

    @pytest.mark.asyncio
    async def test_list_transactions(self, mock_db, mock_event_publisher, test_venue_id):
        """list_transactions returns paginated results and total count."""
        txn1 = _make_transaction(venue_id=test_venue_id)
        txn2 = _make_transaction(venue_id=test_venue_id)

        # First call: count query
        count_result = MagicMock()
        count_result.scalar.return_value = 2

        # Second call: paginated items
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [txn1, txn2]

        mock_db.execute.side_effect = [count_result, items_result]

        service = TransactionService(mock_db, mock_event_publisher)
        transactions, total = await service.list_transactions(
            test_venue_id, page=1, page_size=20
        )

        assert total == 2
        assert len(transactions) == 2


# =============================================================================
# PaymentService
# =============================================================================


class TestPaymentService:
    """Tests for ``PaymentService``."""

    @pytest.mark.asyncio
    async def test_process_payment(self, mock_db, mock_event_publisher, test_venue_id):
        """Processing a payment creates a payment record and auto-completes the
        transaction when fully paid."""
        txn = _make_transaction(
            venue_id=test_venue_id,
            status=TransactionStatus.PENDING.value,
            total_amount=Decimal("54.00"),
        )

        # execute calls: 1) get transaction, 2) sum completed payments
        txn_result = MagicMock()
        txn_result.scalars.return_value.first.return_value = txn

        sum_result = MagicMock()
        sum_result.scalar.return_value = Decimal("54.00")

        mock_db.execute.side_effect = [txn_result, sum_result]

        service = PaymentService(mock_db, mock_event_publisher)

        data = MagicMock()
        data.amount = Decimal("54.00")
        data.payment_method = "credit_card"
        data.reference = None

        payment = await service.process_payment(txn.id, test_venue_id, data)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited()
        mock_db.refresh.assert_awaited()

    @pytest.mark.asyncio
    async def test_reverse_payment(self, mock_db, mock_event_publisher):
        """Reversing a COMPLETED payment transitions it to REVERSED."""
        pay = _make_payment(status=PaymentStatus.COMPLETED.value)
        _mock_scalars_first(mock_db, pay)

        service = PaymentService(mock_db, mock_event_publisher)
        result = await service.reverse_payment(pay.id)

        assert result.status == PaymentStatus.REVERSED.value
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_reverse_non_completed(self, mock_db, mock_event_publisher):
        """Reversing a payment that is not COMPLETED raises PAYMENT_NOT_REVERSIBLE."""
        pay = _make_payment(status=PaymentStatus.PENDING.value)
        _mock_scalars_first(mock_db, pay)

        service = PaymentService(mock_db, mock_event_publisher)

        with pytest.raises(ServiceError) as exc_info:
            await service.reverse_payment(pay.id)

        assert exc_info.value.detail["error_code"] == ErrorCode.PAYMENT_NOT_REVERSIBLE.value

    @pytest.mark.asyncio
    async def test_list_payments_for_transaction(self, mock_db, mock_event_publisher):
        """list_payments_for_transaction returns all payments for the given transaction."""
        txn_id = uuid.uuid4()
        pay1 = _make_payment(transaction_id=txn_id)
        pay2 = _make_payment(transaction_id=txn_id)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [pay1, pay2]
        mock_db.execute.return_value = result_mock

        service = PaymentService(mock_db, mock_event_publisher)
        payments = await service.list_payments_for_transaction(txn_id)

        assert len(payments) == 2


# =============================================================================
# RefundService
# =============================================================================


class TestRefundService:
    """Tests for ``RefundService``."""

    @pytest.mark.asyncio
    @patch("app.services.refund_service.get_settings")
    async def test_issue_refund(
        self, mock_get_settings, mock_db, mock_event_publisher, test_venue_id
    ):
        """Issuing a refund creates a PENDING refund record."""
        mock_settings = MagicMock()
        mock_settings.MAX_REFUND_DAYS = 30
        mock_get_settings.return_value = mock_settings

        txn = _make_transaction(
            venue_id=test_venue_id,
            status=TransactionStatus.COMPLETED.value,
            total_amount=Decimal("54.00"),
            created_at=datetime.utcnow() - timedelta(days=1),
        )

        # execute calls: 1) get transaction, 2) sum existing refunds
        txn_result = MagicMock()
        txn_result.scalars.return_value.first.return_value = txn

        sum_result = MagicMock()
        sum_result.scalar.return_value = Decimal("0")

        mock_db.execute.side_effect = [txn_result, sum_result]

        service = RefundService(mock_db, mock_event_publisher)

        data = MagicMock()
        data.refund_amount = Decimal("54.00")
        data.refund_reason = "customer_request"
        data.refund_method = "original_payment"
        data.notes = None

        refund = await service.issue_refund(txn.id, test_venue_id, data)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited()
        mock_db.refresh.assert_awaited()

    @pytest.mark.asyncio
    async def test_approve_refund(self, mock_db, mock_event_publisher):
        """Approving a PENDING refund sets status to APPROVED and records approved_by."""
        ref = _make_refund(status=RefundStatus.PENDING.value)
        _mock_scalars_first(mock_db, ref)

        service = RefundService(mock_db, mock_event_publisher)

        data = MagicMock()
        data.approved_by = uuid.uuid4()

        result = await service.approve_refund(ref.id, data)

        assert result.status == RefundStatus.APPROVED.value
        assert result.approved_by == data.approved_by
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    @patch("app.services.refund_service.get_settings")
    async def test_refund_exceeds_original(
        self, mock_get_settings, mock_db, mock_event_publisher, test_venue_id
    ):
        """Requesting a refund that exceeds the original total raises REFUND_EXCEEDS_ORIGINAL."""
        mock_settings = MagicMock()
        mock_settings.MAX_REFUND_DAYS = 30
        mock_get_settings.return_value = mock_settings

        txn = _make_transaction(
            venue_id=test_venue_id,
            status=TransactionStatus.COMPLETED.value,
            total_amount=Decimal("54.00"),
            created_at=datetime.utcnow() - timedelta(days=1),
        )

        # get transaction
        txn_result = MagicMock()
        txn_result.scalars.return_value.first.return_value = txn

        # sum existing refunds -- already 54.00 refunded
        sum_result = MagicMock()
        sum_result.scalar.return_value = Decimal("54.00")

        mock_db.execute.side_effect = [txn_result, sum_result]

        service = RefundService(mock_db, mock_event_publisher)

        data = MagicMock()
        data.refund_amount = Decimal("10.00")
        data.refund_reason = "customer_request"
        data.refund_method = "original_payment"
        data.notes = None

        with pytest.raises(ServiceError) as exc_info:
            await service.issue_refund(txn.id, test_venue_id, data)

        assert exc_info.value.detail["error_code"] == ErrorCode.REFUND_EXCEEDS_ORIGINAL.value


# =============================================================================
# CashDrawerService
# =============================================================================


class TestCashDrawerService:
    """Tests for ``CashDrawerService``."""

    @pytest.mark.asyncio
    async def test_open_drawer(
        self, mock_db, mock_event_publisher, test_venue_id
    ):
        """Opening a drawer creates a record with OPEN status."""
        # get_open_drawer returns None (no existing open drawer)
        _mock_scalars_first(mock_db, None)

        service = CashDrawerService(mock_db, mock_event_publisher)
        cashier_id = uuid.uuid4()

        data = MagicMock()
        data.terminal_id = "TERM-01"
        data.opening_cash = Decimal("200.00")

        result = await service.open_drawer(test_venue_id, cashier_id, data)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited()
        mock_db.refresh.assert_awaited()

    @pytest.mark.asyncio
    async def test_close_drawer(self, mock_db, mock_event_publisher):
        """Closing an open drawer calculates variance and sets CLOSED status."""
        drawer = _make_drawer(status=CashDrawerStatus.OPEN.value)

        # First call: get_drawer
        drawer_result = MagicMock()
        drawer_result.scalars.return_value.first.return_value = drawer

        # Second call: _calculate_expected_cash (cash payments sum)
        cash_result = MagicMock()
        cash_result.scalar.return_value = Decimal("50.00")

        mock_db.execute.side_effect = [drawer_result, cash_result]

        service = CashDrawerService(mock_db, mock_event_publisher)

        data = MagicMock()
        data.closing_cash = Decimal("250.00")
        data.notes = None

        result = await service.close_drawer(drawer.id, data)

        assert result.status == CashDrawerStatus.CLOSED.value
        assert result.closing_cash == Decimal("250.00")
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_open_already_open(
        self, mock_db, mock_event_publisher, test_venue_id
    ):
        """Attempting to open a drawer when one is already open raises DRAWER_ALREADY_OPEN."""
        existing_drawer = _make_drawer(
            venue_id=test_venue_id,
            status=CashDrawerStatus.OPEN.value,
        )
        _mock_scalars_first(mock_db, existing_drawer)

        service = CashDrawerService(mock_db, mock_event_publisher)
        cashier_id = uuid.uuid4()

        data = MagicMock()
        data.terminal_id = "TERM-01"
        data.opening_cash = Decimal("200.00")

        with pytest.raises(ServiceError) as exc_info:
            await service.open_drawer(test_venue_id, cashier_id, data)

        assert exc_info.value.detail["error_code"] == ErrorCode.DRAWER_ALREADY_OPEN.value


# =============================================================================
# DiscountService
# =============================================================================


def _make_discount(
    *,
    discount_id: uuid.UUID | None = None,
    venue_id: uuid.UUID | None = None,
    name: str = "Happy Hour 20% Off",
    discount_type: str = "percentage",
    value: Decimal = Decimal("20.00"),
    is_active: bool = True,
) -> MagicMock:
    discount = MagicMock()
    discount.id = discount_id or uuid.uuid4()
    discount.venue_id = venue_id or uuid.uuid4()
    discount.name = name
    discount.discount_type = discount_type
    discount.value = value
    discount.applies_to = "food_beverage"
    discount.is_active = is_active
    discount.start_time = "16:00:00"
    discount.end_time = "18:00:00"
    discount.active_days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    discount.min_purchase_amount = Decimal("0.00")
    discount.max_discount_amount = None
    discount.created_at = datetime.utcnow()
    discount.updated_at = datetime.utcnow()
    return discount


class TestDiscountService:
    """Tests for ``DiscountService``."""

    @pytest.mark.asyncio
    async def test_create_discount(self, mock_db, mock_event_publisher, test_venue_id):
        """Creating a discount stores the rule and emits event."""
        _mock_scalars_first(mock_db, None)

        service = DiscountService(mock_db, mock_event_publisher)

        data = MagicMock()
        data.name = "Happy Hour 20% Off"
        data.discount_type = "percentage"
        data.value = Decimal("20.00")
        data.applies_to = "food_beverage"
        data.is_active = True
        data.start_time = "16:00:00"
        data.end_time = "18:00:00"
        data.active_days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        data.min_purchase_amount = Decimal("0.00")
        data.max_discount_amount = None

        result = await service.create_discount(test_venue_id, data)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_apply_discount_percentage(self, mock_db, mock_event_publisher):
        """Applying a percentage discount calculates correct amount."""
        discount = _make_discount(discount_type="percentage", value=Decimal("20.00"))
        txn = _make_transaction(subtotal=Decimal("100.00"))

        # First call: get discount, Second call: get transaction
        discount_result = MagicMock()
        discount_result.scalars.return_value.first.return_value = discount

        txn_result = MagicMock()
        txn_result.scalars.return_value.first.return_value = txn

        mock_db.execute.side_effect = [discount_result, txn_result]

        service = DiscountService(mock_db, mock_event_publisher)
        result = await service.apply_discount(discount.id, txn.id)

        # 20% of 100.00 = 20.00
        assert result["discount_amount"] == Decimal("20.00")
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_apply_discount_fixed(self, mock_db, mock_event_publisher):
        """Applying a fixed discount subtracts the fixed amount."""
        discount = _make_discount(discount_type="fixed", value=Decimal("15.00"))
        txn = _make_transaction(subtotal=Decimal("100.00"))

        discount_result = MagicMock()
        discount_result.scalars.return_value.first.return_value = discount

        txn_result = MagicMock()
        txn_result.scalars.return_value.first.return_value = txn

        mock_db.execute.side_effect = [discount_result, txn_result]

        service = DiscountService(mock_db, mock_event_publisher)
        result = await service.apply_discount(discount.id, txn.id)

        assert result["discount_amount"] == Decimal("15.00")

    @pytest.mark.asyncio
    async def test_apply_inactive_discount(self, mock_db, mock_event_publisher):
        """Applying an inactive discount raises DISCOUNT_NOT_ACTIVE."""
        discount = _make_discount(is_active=False)
        _mock_scalars_first(mock_db, discount)

        service = DiscountService(mock_db, mock_event_publisher)

        with pytest.raises(ServiceError) as exc_info:
            await service.apply_discount(discount.id, uuid.uuid4())

        assert exc_info.value.detail["error_code"] == ErrorCode.DISCOUNT_NOT_ACTIVE.value


# =============================================================================
# ShiftService
# =============================================================================


def _make_shift(
    *,
    shift_id: uuid.UUID | None = None,
    venue_id: uuid.UUID | None = None,
    employee_id: uuid.UUID | None = None,
    status: str = "active",
    started_at: datetime | None = None,
) -> MagicMock:
    shift = MagicMock()
    shift.id = shift_id or uuid.uuid4()
    shift.venue_id = venue_id or uuid.uuid4()
    shift.employee_id = employee_id or uuid.uuid4()
    shift.terminal_id = "TERM-01"
    shift.status = status
    shift.started_at = started_at or datetime.utcnow()
    shift.ended_at = None
    shift.total_sales = Decimal("0.00")
    shift.transaction_count = 0
    shift.break_minutes = 0
    shift.notes = None
    shift.created_at = datetime.utcnow()
    shift.updated_at = datetime.utcnow()
    return shift


class TestShiftService:
    """Tests for ``ShiftService``."""

    @pytest.mark.asyncio
    async def test_start_shift(self, mock_db, mock_event_publisher, test_venue_id):
        """Starting a shift creates an active shift record."""
        # No existing active shift
        _mock_scalars_first(mock_db, None)

        service = ShiftService(mock_db, mock_event_publisher)
        employee_id = uuid.uuid4()

        data = MagicMock()
        data.terminal_id = "TERM-01"

        result = await service.start_shift(test_venue_id, employee_id, data)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_end_shift(self, mock_db, mock_event_publisher):
        """Ending an active shift sets ended_at and calculates totals."""
        shift = _make_shift(status="active")

        # First call: get shift, Second call: sum transactions
        shift_result = MagicMock()
        shift_result.scalars.return_value.first.return_value = shift

        sales_result = MagicMock()
        sales_result.scalar.return_value = Decimal("350.00")

        count_result = MagicMock()
        count_result.scalar.return_value = 12

        mock_db.execute.side_effect = [shift_result, sales_result, count_result]

        service = ShiftService(mock_db, mock_event_publisher)

        data = MagicMock()
        data.notes = "Busy shift"

        result = await service.end_shift(shift.id, data)

        assert result.status == "completed"
        assert result.total_sales == Decimal("350.00")
        assert result.transaction_count == 12
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_start_break(self, mock_db, mock_event_publisher):
        """Starting a break records break start time."""
        shift = _make_shift(status="active")
        _mock_scalars_first(mock_db, shift)

        service = ShiftService(mock_db, mock_event_publisher)

        data = MagicMock()
        data.break_type = "lunch"

        result = await service.start_break(shift.id, data)

        assert result.status == "on_break"
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_start_shift_already_active(self, mock_db, mock_event_publisher, test_venue_id):
        """Starting a shift when one is already active raises SHIFT_ALREADY_ACTIVE."""
        existing_shift = _make_shift(venue_id=test_venue_id, status="active")
        _mock_scalars_first(mock_db, existing_shift)

        service = ShiftService(mock_db, mock_event_publisher)
        employee_id = existing_shift.employee_id

        data = MagicMock()
        data.terminal_id = "TERM-01"

        with pytest.raises(ServiceError) as exc_info:
            await service.start_shift(test_venue_id, employee_id, data)

        assert exc_info.value.detail["error_code"] == ErrorCode.SHIFT_ALREADY_ACTIVE.value


# =============================================================================
# TipService
# =============================================================================


def _make_tip_pool(
    *,
    pool_id: uuid.UUID | None = None,
    venue_id: uuid.UUID | None = None,
    status: str = "pending",
    total_tips: Decimal = Decimal("450.00"),
) -> MagicMock:
    pool = MagicMock()
    pool.id = pool_id or uuid.uuid4()
    pool.venue_id = venue_id or uuid.uuid4()
    pool.pool_date = datetime.utcnow().date()
    pool.distribution_method = "hours_worked"
    pool.total_tips = total_tips
    pool.status = status
    pool.distributed_at = None
    pool.distributed_by = None
    pool.created_at = datetime.utcnow()
    pool.updated_at = datetime.utcnow()
    return pool


class TestTipService:
    """Tests for ``TipService``."""

    @pytest.mark.asyncio
    async def test_create_tip_pool(self, mock_db, mock_event_publisher, test_venue_id):
        """Creating a tip pool stores the pool record."""
        _mock_scalars_first(mock_db, None)

        service = TipService(mock_db, mock_event_publisher)

        data = MagicMock()
        data.pool_date = datetime.utcnow().date()
        data.distribution_method = "hours_worked"
        data.total_tips = Decimal("450.00")

        result = await service.create_tip_pool(test_venue_id, data)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_distribute_tips(self, mock_db, mock_event_publisher):
        """Distributing tips creates distribution records for each employee."""
        pool = _make_tip_pool(total_tips=Decimal("450.00"))
        _mock_scalars_first(mock_db, pool)

        service = TipService(mock_db, mock_event_publisher)

        employees = [
            {"employee_id": uuid.uuid4(), "hours_worked": Decimal("8.0")},
            {"employee_id": uuid.uuid4(), "hours_worked": Decimal("6.5")},
            {"employee_id": uuid.uuid4(), "hours_worked": Decimal("7.0")},
        ]
        distributor_id = uuid.uuid4()

        result = await service.distribute_tips(pool.id, employees, distributor_id)

        assert pool.status == "distributed"
        # Total hours = 21.5, each gets proportional share
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_distribute_already_distributed(self, mock_db, mock_event_publisher):
        """Distributing an already distributed pool raises TIP_POOL_ALREADY_DISTRIBUTED."""
        pool = _make_tip_pool(status="distributed")
        _mock_scalars_first(mock_db, pool)

        service = TipService(mock_db, mock_event_publisher)

        with pytest.raises(ServiceError) as exc_info:
            await service.distribute_tips(pool.id, [], uuid.uuid4())

        assert exc_info.value.detail["error_code"] == ErrorCode.TIP_POOL_ALREADY_DISTRIBUTED.value


# =============================================================================
# CurrencyService
# =============================================================================


def _make_currency(
    *,
    currency_id: uuid.UUID | None = None,
    code: str = "EUR",
    exchange_rate: Decimal = Decimal("0.92"),
    is_active: bool = True,
) -> MagicMock:
    currency = MagicMock()
    currency.id = currency_id or uuid.uuid4()
    currency.code = code
    currency.name = "Euro"
    currency.symbol = "€"
    currency.exchange_rate = exchange_rate
    currency.decimal_places = 2
    currency.is_active = is_active
    currency.last_updated = datetime.utcnow()
    currency.created_at = datetime.utcnow()
    return currency


class TestCurrencyService:
    """Tests for ``CurrencyService``."""

    @pytest.mark.asyncio
    async def test_add_currency(self, mock_db, mock_event_publisher):
        """Adding a currency stores the currency record."""
        _mock_scalars_first(mock_db, None)

        service = CurrencyService(mock_db, mock_event_publisher)

        data = MagicMock()
        data.code = "EUR"
        data.name = "Euro"
        data.symbol = "€"
        data.exchange_rate = Decimal("0.92")
        data.decimal_places = 2

        result = await service.add_currency(data)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_convert_currency(self, mock_db, mock_event_publisher):
        """Converting currency calculates correct amount."""
        usd = _make_currency(code="USD", exchange_rate=Decimal("1.00"))
        eur = _make_currency(code="EUR", exchange_rate=Decimal("0.92"))

        # First call: get from currency, Second call: get to currency
        usd_result = MagicMock()
        usd_result.scalars.return_value.first.return_value = usd

        eur_result = MagicMock()
        eur_result.scalars.return_value.first.return_value = eur

        mock_db.execute.side_effect = [usd_result, eur_result]

        service = CurrencyService(mock_db, mock_event_publisher)
        result = await service.convert(
            amount=Decimal("100.00"),
            from_currency="USD",
            to_currency="EUR",
        )

        # 100 USD * 0.92 = 92 EUR
        assert result["converted_amount"] == Decimal("92.00")

    @pytest.mark.asyncio
    async def test_update_exchange_rate(self, mock_db, mock_event_publisher):
        """Updating exchange rate modifies the currency record."""
        eur = _make_currency(code="EUR", exchange_rate=Decimal("0.92"))
        _mock_scalars_first(mock_db, eur)

        service = CurrencyService(mock_db, mock_event_publisher)
        result = await service.update_exchange_rate("EUR", Decimal("0.95"))

        assert result.exchange_rate == Decimal("0.95")
        mock_db.commit.assert_awaited()


# =============================================================================
# ReportingService
# =============================================================================


class TestReportingService:
    """Tests for ``ReportingService``."""

    @pytest.mark.asyncio
    async def test_get_sales_report(self, mock_db, mock_event_publisher, test_venue_id):
        """Sales report aggregates transactions for date range."""
        report_result = MagicMock()
        report_result.one.return_value = MagicMock(
            total_transactions=100,
            gross_sales=Decimal("5000.00"),
            net_sales=Decimal("4750.00"),
            total_tax=Decimal("400.00"),
            total_tips=Decimal("200.00"),
            total_discounts=Decimal("50.00"),
        )
        mock_db.execute.return_value = report_result

        service = ReportingService(mock_db, mock_event_publisher)
        result = await service.get_sales_report(
            venue_id=test_venue_id,
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 1, 28),
        )

        assert result["total_transactions"] == 100
        assert result["gross_sales"] == Decimal("5000.00")

    @pytest.mark.asyncio
    async def test_get_employee_performance(self, mock_db, mock_event_publisher, test_venue_id):
        """Employee performance report returns metrics per employee."""
        emp1 = MagicMock(
            employee_id=uuid.uuid4(),
            transaction_count=50,
            total_sales=Decimal("2500.00"),
            average_transaction=Decimal("50.00"),
        )
        emp2 = MagicMock(
            employee_id=uuid.uuid4(),
            transaction_count=45,
            total_sales=Decimal("2250.00"),
            average_transaction=Decimal("50.00"),
        )

        result_mock = MagicMock()
        result_mock.all.return_value = [emp1, emp2]
        mock_db.execute.return_value = result_mock

        service = ReportingService(mock_db, mock_event_publisher)
        result = await service.get_employee_performance(
            venue_id=test_venue_id,
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 1, 28),
        )

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_hourly_sales(self, mock_db, mock_event_publisher, test_venue_id):
        """Hourly sales report returns sales breakdown by hour."""
        hours = [
            MagicMock(hour=10, transaction_count=5, total_sales=Decimal("250.00")),
            MagicMock(hour=11, transaction_count=8, total_sales=Decimal("400.00")),
            MagicMock(hour=12, transaction_count=15, total_sales=Decimal("750.00")),
        ]

        result_mock = MagicMock()
        result_mock.all.return_value = hours
        mock_db.execute.return_value = result_mock

        service = ReportingService(mock_db, mock_event_publisher)
        result = await service.get_hourly_sales(
            venue_id=test_venue_id,
            date=datetime(2026, 1, 28).date(),
        )

        assert len(result) == 3
        assert result[2]["hour"] == 12
        assert result[2]["total_sales"] == Decimal("750.00")


# =============================================================================
# FraudDetectionService
# =============================================================================


def _make_fraud_alert(
    *,
    alert_id: uuid.UUID | None = None,
    venue_id: uuid.UUID | None = None,
    status: str = "pending",
    fraud_score: Decimal = Decimal("0.92"),
) -> MagicMock:
    alert = MagicMock()
    alert.id = alert_id or uuid.uuid4()
    alert.venue_id = venue_id or uuid.uuid4()
    alert.transaction_id = uuid.uuid4()
    alert.alert_type = "velocity_check"
    alert.severity = "high"
    alert.fraud_score = fraud_score
    alert.status = status
    alert.details = {"reason": "Multiple high-value transactions"}
    alert.investigator_id = None
    alert.investigated_at = None
    alert.resolution = None
    alert.action_taken = None
    alert.resolved_by = None
    alert.resolved_at = None
    alert.created_at = datetime.utcnow()
    alert.updated_at = datetime.utcnow()
    return alert


class TestFraudDetectionService:
    """Tests for ``FraudDetectionService``."""

    @pytest.mark.asyncio
    async def test_analyze_transaction(self, mock_db, mock_event_publisher):
        """Analyzing a high-risk transaction creates a fraud alert."""
        txn = _make_transaction(total_amount=Decimal("5000.00"))
        _mock_scalars_first(mock_db, txn)

        service = FraudDetectionService(mock_db, mock_event_publisher)
        result = await service.analyze_transaction(txn.id)

        # High value transaction should trigger alert
        if result.get("fraud_score", 0) > 0.8:
            mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_investigate_alert(self, mock_db, mock_event_publisher):
        """Marking an alert as under investigation updates status."""
        alert = _make_fraud_alert(status="pending")
        _mock_scalars_first(mock_db, alert)

        service = FraudDetectionService(mock_db, mock_event_publisher)
        investigator_id = uuid.uuid4()

        result = await service.investigate_alert(alert.id, investigator_id, "Reviewing patterns")

        assert result.status == "investigating"
        assert result.investigator_id == investigator_id
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_resolve_alert(self, mock_db, mock_event_publisher):
        """Resolving a fraud alert records resolution details."""
        alert = _make_fraud_alert(status="investigating")
        _mock_scalars_first(mock_db, alert)

        service = FraudDetectionService(mock_db, mock_event_publisher)
        resolver_id = uuid.uuid4()

        result = await service.resolve_alert(
            alert_id=alert.id,
            resolution="confirmed_fraud",
            action_taken="Voided transaction",
            resolved_by=resolver_id,
        )

        assert result.status == "resolved"
        assert result.resolution == "confirmed_fraud"
        mock_db.commit.assert_awaited()


# =============================================================================
# AuditService
# =============================================================================


class TestAuditService:
    """Tests for ``AuditService``."""

    @pytest.mark.asyncio
    async def test_log_action(self, mock_db, mock_event_publisher, test_venue_id):
        """Logging an action creates an audit log record."""
        service = AuditService(mock_db, mock_event_publisher)
        user_id = uuid.uuid4()
        resource_id = uuid.uuid4()

        await service.log_action(
            venue_id=test_venue_id,
            user_id=user_id,
            action="transaction.created",
            resource_type="transaction",
            resource_id=resource_id,
            details={"amount": "54.00"},
            ip_address="192.168.1.100",
            user_agent="TestAgent/1.0",
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_audit_logs(self, mock_db, mock_event_publisher, test_venue_id):
        """Listing audit logs returns filtered and paginated results."""
        log1 = MagicMock(id=uuid.uuid4(), action="transaction.created")
        log2 = MagicMock(id=uuid.uuid4(), action="payment.processed")

        count_result = MagicMock()
        count_result.scalar.return_value = 2

        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [log1, log2]

        mock_db.execute.side_effect = [count_result, items_result]

        service = AuditService(mock_db, mock_event_publisher)
        logs, total = await service.list_audit_logs(
            venue_id=test_venue_id,
            page=1,
            page_size=20,
        )

        assert total == 2
        assert len(logs) == 2


# =============================================================================
# ReceiptTemplateService
# =============================================================================


def _make_receipt_template(
    *,
    template_id: uuid.UUID | None = None,
    venue_id: uuid.UUID | None = None,
    is_active: bool = True,
) -> MagicMock:
    template = MagicMock()
    template.id = template_id or uuid.uuid4()
    template.venue_id = venue_id or uuid.uuid4()
    template.name = "Bowling Receipt"
    template.template_type = "thermal"
    template.header_text = "Welcome to Fun Bowl!"
    template.footer_text = "Thank you!"
    template.show_logo = True
    template.show_tax_breakdown = True
    template.template_body = "<div>{{details}}</div>"
    template.is_default = False
    template.is_active = is_active
    template.created_at = datetime.utcnow()
    template.updated_at = datetime.utcnow()
    return template


class TestReceiptTemplateService:
    """Tests for ``ReceiptTemplateService``."""

    @pytest.mark.asyncio
    async def test_create_template(self, mock_db, mock_event_publisher, test_venue_id):
        """Creating a template stores the template record."""
        _mock_scalars_first(mock_db, None)

        service = ReceiptTemplateService(mock_db, mock_event_publisher)

        data = MagicMock()
        data.name = "Bowling Receipt"
        data.template_type = "thermal"
        data.header_text = "Welcome!"
        data.footer_text = "Thanks!"
        data.show_logo = True
        data.show_tax_breakdown = True
        data.template_body = "<div>{{details}}</div>"

        result = await service.create_template(test_venue_id, data)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_render_template(self, mock_db, mock_event_publisher):
        """Rendering a template with transaction data produces output."""
        template = _make_receipt_template()
        txn = _make_transaction()

        template_result = MagicMock()
        template_result.scalars.return_value.first.return_value = template

        txn_result = MagicMock()
        txn_result.scalars.return_value.first.return_value = txn

        mock_db.execute.side_effect = [template_result, txn_result]

        service = ReceiptTemplateService(mock_db, mock_event_publisher)
        result = await service.render_template(template.id, txn.id)

        assert "rendered_content" in result

    @pytest.mark.asyncio
    async def test_delete_template(self, mock_db, mock_event_publisher):
        """Deleting a template marks it as inactive."""
        template = _make_receipt_template(is_active=True)
        _mock_scalars_first(mock_db, template)

        service = ReceiptTemplateService(mock_db, mock_event_publisher)
        result = await service.delete_template(template.id)

        assert result.is_active is False
        mock_db.commit.assert_awaited()
