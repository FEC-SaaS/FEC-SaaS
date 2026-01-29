"""Shared fixtures for the POS Integration Service test suite."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Database session fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """AsyncMock for SQLAlchemy AsyncSession.

    Provides ``execute``, ``commit``, ``refresh``, ``add``, and ``flush``
    as async callables.  ``execute`` returns a mock result whose
    ``.scalars().first()`` chain returns ``None`` by default (override in
    individual tests).
    """
    session = AsyncMock()

    # Default result object returned by execute()
    default_result = MagicMock()
    default_result.scalars.return_value.first.return_value = None
    default_result.scalars.return_value.all.return_value = []
    default_result.scalar.return_value = 0
    default_result.one.return_value = MagicMock(
        total_transactions=0,
        gross_sales=Decimal("0"),
        net_sales=Decimal("0"),
        total_tax=Decimal("0"),
        total_tips=Decimal("0"),
        total_discounts=Decimal("0"),
    )

    session.execute.return_value = default_result
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    return session


# ---------------------------------------------------------------------------
# Event publisher fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_event_publisher():
    """AsyncMock for EventPublisher with ``publish``, ``connect``, and
    ``disconnect`` methods."""
    publisher = AsyncMock()
    publisher.publish = AsyncMock()
    publisher.connect = AsyncMock()
    publisher.disconnect = AsyncMock()
    return publisher


# ---------------------------------------------------------------------------
# User / identity fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_current_user():
    """Return a dict that mirrors the shape produced by ``get_current_user``."""
    return {
        "user_id": uuid.uuid4(),
        "email": "cashier@example.com",
        "role": "manager",
        "venue_ids": [str(uuid.uuid4())],
    }


# ---------------------------------------------------------------------------
# Common UUID fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_venue_id() -> uuid.UUID:
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def test_customer_id() -> uuid.UUID:
    return uuid.UUID("22222222-2222-2222-2222-222222222222")


# ---------------------------------------------------------------------------
# Sample data dicts (mirrors Pydantic schema input shapes)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_transaction_data(test_customer_id):
    """Dict suitable for ``TransactionCreate``."""
    return {
        "transaction_type": "bowling",
        "customer_id": str(test_customer_id),
        "line_items": [
            {
                "description": "1 hour bowling",
                "quantity": 1,
                "unit_price": "50.00",
                "total_price": "50.00",
                "activity_type": "bowling",
            },
        ],
        "subtotal": "50.00",
        "tax_amount": "4.00",
        "tip_amount": "0.00",
        "discount_amount": "0.00",
        "total_amount": "54.00",
        "currency": "USD",
        "notes": "Test transaction",
    }


@pytest.fixture
def sample_payment_data():
    """Dict suitable for ``PaymentCreate``."""
    return {
        "payment_method": "credit_card",
        "amount": "54.00",
    }


@pytest.fixture
def sample_refund_data():
    """Dict suitable for ``RefundCreate``."""
    return {
        "refund_amount": "54.00",
        "refund_reason": "customer_request",
        "refund_method": "original_payment",
        "notes": "Customer requested full refund",
    }


@pytest.fixture
def sample_drawer_data():
    """Dict suitable for ``DrawerOpenRequest``."""
    return {
        "terminal_id": "TERM-01",
        "opening_cash": "200.00",
    }


@pytest.fixture
def sample_tax_rate_data():
    """Dict suitable for ``TaxRateCreate``."""
    return {
        "tax_type": "sales_tax",
        "name": "State Sales Tax",
        "rate": "0.08",
        "effective_date": str(date.today()),
        "jurisdiction": "CA",
    }


# ---------------------------------------------------------------------------
# Discount fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_discount_data(test_venue_id):
    """Dict suitable for ``DiscountCreate``."""
    return {
        "name": "Happy Hour 20% Off",
        "discount_type": "percentage",
        "value": "20.00",
        "applies_to": "food_beverage",
        "venue_id": str(test_venue_id),
        "start_time": "16:00:00",
        "end_time": "18:00:00",
        "active_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "is_active": True,
        "min_purchase_amount": "0.00",
        "max_discount_amount": None,
    }


@pytest.fixture
def sample_discount(test_venue_id):
    """Return a MagicMock that mimics a Discount ORM instance."""
    discount = MagicMock()
    discount.id = uuid.uuid4()
    discount.venue_id = test_venue_id
    discount.name = "Happy Hour 20% Off"
    discount.discount_type = "percentage"
    discount.value = Decimal("20.00")
    discount.applies_to = "food_beverage"
    discount.start_time = "16:00:00"
    discount.end_time = "18:00:00"
    discount.active_days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    discount.is_active = True
    discount.min_purchase_amount = Decimal("0.00")
    discount.max_discount_amount = None
    discount.created_at = datetime.utcnow()
    discount.updated_at = datetime.utcnow()
    return discount


# ---------------------------------------------------------------------------
# Shift fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_shift_data(test_venue_id):
    """Dict suitable for ``ShiftCreate``."""
    return {
        "venue_id": str(test_venue_id),
        "employee_id": str(uuid.uuid4()),
        "terminal_id": "TERM-01",
    }


@pytest.fixture
def sample_shift(test_venue_id):
    """Return a MagicMock that mimics a Shift ORM instance."""
    shift = MagicMock()
    shift.id = uuid.uuid4()
    shift.venue_id = test_venue_id
    shift.employee_id = uuid.uuid4()
    shift.terminal_id = "TERM-01"
    shift.started_at = datetime.utcnow()
    shift.ended_at = None
    shift.status = "active"
    shift.total_sales = Decimal("0.00")
    shift.transaction_count = 0
    shift.break_minutes = 0
    shift.notes = None
    shift.created_at = datetime.utcnow()
    shift.updated_at = datetime.utcnow()
    return shift


# ---------------------------------------------------------------------------
# Tip Pool fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_tip_pool_data(test_venue_id):
    """Dict suitable for ``TipPoolCreate``."""
    return {
        "venue_id": str(test_venue_id),
        "pool_date": str(date.today()),
        "distribution_method": "hours_worked",
        "total_tips": "450.00",
    }


@pytest.fixture
def sample_tip_pool(test_venue_id):
    """Return a MagicMock that mimics a TipPool ORM instance."""
    tip_pool = MagicMock()
    tip_pool.id = uuid.uuid4()
    tip_pool.venue_id = test_venue_id
    tip_pool.pool_date = date.today()
    tip_pool.distribution_method = "hours_worked"
    tip_pool.total_tips = Decimal("450.00")
    tip_pool.status = "pending"
    tip_pool.distributed_at = None
    tip_pool.distributed_by = None
    tip_pool.created_at = datetime.utcnow()
    tip_pool.updated_at = datetime.utcnow()
    return tip_pool


@pytest.fixture
def sample_tip_distribution(test_venue_id):
    """Return a MagicMock that mimics a TipDistribution ORM instance."""
    dist = MagicMock()
    dist.id = uuid.uuid4()
    dist.tip_pool_id = uuid.uuid4()
    dist.employee_id = uuid.uuid4()
    dist.hours_worked = Decimal("8.0")
    dist.tip_amount = Decimal("167.44")
    dist.created_at = datetime.utcnow()
    return dist


# ---------------------------------------------------------------------------
# Currency fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_currency_data():
    """Dict suitable for ``CurrencyCreate``."""
    return {
        "code": "EUR",
        "name": "Euro",
        "symbol": "€",
        "exchange_rate": "0.92",
        "decimal_places": 2,
        "is_active": True,
    }


@pytest.fixture
def sample_currency():
    """Return a MagicMock that mimics a Currency ORM instance."""
    currency = MagicMock()
    currency.id = uuid.uuid4()
    currency.code = "EUR"
    currency.name = "Euro"
    currency.symbol = "€"
    currency.exchange_rate = Decimal("0.92")
    currency.decimal_places = 2
    currency.is_active = True
    currency.last_updated = datetime.utcnow()
    currency.created_at = datetime.utcnow()
    return currency


# ---------------------------------------------------------------------------
# Receipt Template fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_receipt_template_data(test_venue_id):
    """Dict suitable for ``ReceiptTemplateCreate``."""
    return {
        "name": "Bowling Receipt",
        "template_type": "thermal",
        "venue_id": str(test_venue_id),
        "header_text": "Welcome to Fun Bowl!",
        "footer_text": "Thank you for bowling with us!",
        "show_logo": True,
        "show_tax_breakdown": True,
        "template_body": "<div>{{transaction_details}}</div>",
    }


@pytest.fixture
def sample_receipt_template(test_venue_id):
    """Return a MagicMock that mimics a ReceiptTemplate ORM instance."""
    template = MagicMock()
    template.id = uuid.uuid4()
    template.venue_id = test_venue_id
    template.name = "Bowling Receipt"
    template.template_type = "thermal"
    template.header_text = "Welcome to Fun Bowl!"
    template.footer_text = "Thank you for bowling with us!"
    template.show_logo = True
    template.show_tax_breakdown = True
    template.template_body = "<div>{{transaction_details}}</div>"
    template.is_default = False
    template.is_active = True
    template.created_at = datetime.utcnow()
    template.updated_at = datetime.utcnow()
    return template


# ---------------------------------------------------------------------------
# Fraud Alert fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_fraud_alert_data(test_venue_id):
    """Dict suitable for internal fraud alert creation."""
    return {
        "venue_id": str(test_venue_id),
        "transaction_id": str(uuid.uuid4()),
        "alert_type": "velocity_check",
        "severity": "high",
        "fraud_score": "0.92",
        "details": {
            "reason": "Multiple high-value transactions in short time window",
            "transactions_count": 5,
            "time_window_minutes": 10,
        },
    }


@pytest.fixture
def sample_fraud_alert(test_venue_id):
    """Return a MagicMock that mimics a FraudAlert ORM instance."""
    alert = MagicMock()
    alert.id = uuid.uuid4()
    alert.venue_id = test_venue_id
    alert.transaction_id = uuid.uuid4()
    alert.alert_type = "velocity_check"
    alert.severity = "high"
    alert.fraud_score = Decimal("0.92")
    alert.status = "pending"
    alert.details = {
        "reason": "Multiple high-value transactions in short time window",
        "transactions_count": 5,
        "time_window_minutes": 10,
    }
    alert.investigator_id = None
    alert.investigated_at = None
    alert.resolution = None
    alert.action_taken = None
    alert.resolved_by = None
    alert.resolved_at = None
    alert.created_at = datetime.utcnow()
    alert.updated_at = datetime.utcnow()
    return alert


# ---------------------------------------------------------------------------
# Audit Log fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_audit_log_data(test_venue_id):
    """Dict suitable for internal audit log creation."""
    return {
        "venue_id": str(test_venue_id),
        "user_id": str(uuid.uuid4()),
        "action": "transaction.created",
        "resource_type": "transaction",
        "resource_id": str(uuid.uuid4()),
        "details": {
            "transaction_type": "bowling",
            "total_amount": "54.00",
        },
        "ip_address": "192.168.1.100",
        "user_agent": "Mozilla/5.0",
    }


@pytest.fixture
def sample_audit_log(test_venue_id):
    """Return a MagicMock that mimics an AuditLog ORM instance."""
    log = MagicMock()
    log.id = uuid.uuid4()
    log.venue_id = test_venue_id
    log.user_id = uuid.uuid4()
    log.action = "transaction.created"
    log.resource_type = "transaction"
    log.resource_id = uuid.uuid4()
    log.details = {
        "transaction_type": "bowling",
        "total_amount": "54.00",
    }
    log.ip_address = "192.168.1.100"
    log.user_agent = "Mozilla/5.0"
    log.created_at = datetime.utcnow()
    return log


# ---------------------------------------------------------------------------
# Line Item fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_line_item_data():
    """Dict suitable for ``LineItemCreate``."""
    return {
        "product_id": str(uuid.uuid4()),
        "description": "1 hour bowling",
        "quantity": 1,
        "unit_price": "50.00",
        "total_price": "50.00",
        "activity_type": "bowling",
        "tax_rate": "0.08",
        "tax_amount": "4.00",
    }


@pytest.fixture
def sample_line_item():
    """Return a MagicMock that mimics a TransactionLineItem ORM instance."""
    item = MagicMock()
    item.id = uuid.uuid4()
    item.transaction_id = uuid.uuid4()
    item.product_id = uuid.uuid4()
    item.description = "1 hour bowling"
    item.quantity = 1
    item.unit_price = Decimal("50.00")
    item.total_price = Decimal("50.00")
    item.activity_type = "bowling"
    item.tax_rate = Decimal("0.08")
    item.tax_amount = Decimal("4.00")
    item.discount_amount = Decimal("0.00")
    item.created_at = datetime.utcnow()
    return item
