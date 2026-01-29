"""
=============================================================================
FILE: models/pos.py
PURPOSE: SQLAlchemy models for the POS Integration Service
=============================================================================

Core database models for the POS Integration Service:
- Transaction: Master POS transaction record
- Payment: Individual payment against a transaction
- Receipt: Generated receipt records
- Refund: Refund processing and tracking
- TaxRate: Venue-specific tax rate configuration
- CashDrawer: Cash drawer session management
- DailyReconciliation: End-of-day financial reconciliation
- ExternalPOSIntegration: Third-party POS system connections
- POSSyncLog: Sync history for external integrations
"""

import enum
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    String,
    Text,
    Boolean,
    Integer,
    Numeric,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


# =============================================================================
# ENUMS
# =============================================================================


class TransactionType(str, enum.Enum):
    """Type of POS transaction."""
    BOWLING = "bowling"
    ARCADE = "arcade"
    FOOD = "food"
    PARTY = "party"
    MEMBERSHIP = "membership"
    RETAIL = "retail"
    OTHER = "other"


class TransactionStatus(str, enum.Enum):
    """Status of a POS transaction."""
    PENDING = "pending"
    COMPLETED = "completed"
    VOIDED = "voided"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentMethod(str, enum.Enum):
    """Accepted payment methods."""
    CASH = "cash"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    GAME_CARD = "game_card"
    COMP = "comp"
    GIFT_CARD = "gift_card"
    MOBILE_PAY = "mobile_pay"


class PaymentStatus(str, enum.Enum):
    """Status of a payment attempt."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"


class PaymentProcessor(str, enum.Enum):
    """External payment processor."""
    STRIPE = "stripe"
    SQUARE = "square"
    INTERNAL = "internal"


class ReceiptType(str, enum.Enum):
    """Type of receipt generated."""
    CUSTOMER = "customer"
    MERCHANT = "merchant"
    REFUND = "refund"


class RefundReason(str, enum.Enum):
    """Reason for refund."""
    CUSTOMER_REQUEST = "customer_request"
    ERROR = "error"
    QUALITY_ISSUE = "quality_issue"
    CANCELLATION = "cancellation"
    OTHER = "other"


class RefundMethod(str, enum.Enum):
    """How the refund is issued."""
    ORIGINAL_PAYMENT = "original_payment"
    CASH = "cash"
    STORE_CREDIT = "store_credit"


class RefundStatus(str, enum.Enum):
    """Status of a refund request."""
    PENDING = "pending"
    APPROVED = "approved"
    PROCESSED = "processed"
    REJECTED = "rejected"


class CashDrawerStatus(str, enum.Enum):
    """Status of a cash drawer session."""
    OPEN = "open"
    CLOSED = "closed"
    RECONCILED = "reconciled"


class TaxType(str, enum.Enum):
    """Type of tax applied."""
    SALES_TAX = "sales_tax"
    AMUSEMENT_TAX = "amusement_tax"
    FOOD_TAX = "food_tax"
    BEVERAGE_TAX = "beverage_tax"


class ReconciliationStatus(str, enum.Enum):
    """Status of daily reconciliation."""
    PENDING = "pending"
    COMPLETED = "completed"
    DISPUTED = "disputed"


class ExternalPOSProvider(str, enum.Enum):
    """Supported external POS providers."""
    TOAST = "toast"
    SQUARE = "square"
    CLOVER = "clover"


class SyncStatus(str, enum.Enum):
    """Status of a sync operation."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class DiscountType(str, enum.Enum):
    """Type of discount applied."""
    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"
    BOGO = "bogo"
    MEMBER_DISCOUNT = "member_discount"
    PROMO_CODE = "promo_code"


class ShiftStatus(str, enum.Enum):
    """Status of an employee shift."""
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AuditAction(str, enum.Enum):
    """Type of audit log action."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VOID = "void"
    REFUND = "refund"
    APPROVE = "approve"
    REJECT = "reject"
    STATUS_CHANGE = "status_change"
    PAYMENT_PROCESS = "payment_process"
    DRAWER_OPEN = "drawer_open"
    DRAWER_CLOSE = "drawer_close"


class TipPoolStatus(str, enum.Enum):
    """Status of a tip pool."""
    OPEN = "open"
    CLOSED = "closed"
    DISTRIBUTED = "distributed"


class FraudAlertSeverity(str, enum.Enum):
    """Severity level of a fraud alert."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FraudAlertStatus(str, enum.Enum):
    """Status of a fraud alert investigation."""
    NEW = "new"
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"


# =============================================================================
# MODELS
# =============================================================================


class Transaction(Base, UUIDMixin, TimestampMixin):
    """
    Master POS transaction record.

    Represents a single sale transaction at a venue, linking to
    payments, receipts, and refunds. Supports multiple transaction
    types (bowling, arcade, food, party, etc.) and tracks full
    financial details including subtotal, tax, tips, and discounts.
    """
    __tablename__ = "pos_transactions"

    # Core references
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    cashier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    activity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )

    # Transaction details
    transaction_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default=TransactionType.OTHER.value
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=TransactionStatus.PENDING.value
    )

    # Financial amounts
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    tip_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USD"
    )

    # Additional info
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )

    # Relationships
    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        back_populates="transaction",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    receipts: Mapped[List["Receipt"]] = relationship(
        "Receipt",
        back_populates="transaction",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    refunds: Mapped[List["Refund"]] = relationship(
        "Refund",
        back_populates="transaction",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    line_items: Mapped[List["TransactionLineItem"]] = relationship(
        "TransactionLineItem",
        back_populates="transaction",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__ = (
        Index("idx_pos_txn_venue_created", "venue_id", "created_at"),
        Index("idx_pos_txn_venue_type", "venue_id", "transaction_type"),
        Index("idx_pos_txn_venue_status", "venue_id", "status"),
    )


class Payment(Base, UUIDMixin, TimestampMixin):
    """
    Individual payment against a transaction.

    A transaction can have multiple payments (split payments).
    Tracks payment method, processor details, card info, and
    approval/error status.
    """
    __tablename__ = "pos_payments"

    # References
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pos_transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )

    # Payment details
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_processor: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PaymentStatus.PENDING.value
    )

    # Processor info
    processor_transaction_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    card_last_four: Mapped[Optional[str]] = mapped_column(
        String(4), nullable=True
    )
    card_brand: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    approval_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payment_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    transaction: Mapped["Transaction"] = relationship(
        "Transaction", back_populates="payments"
    )

    __table_args__ = (
        Index("idx_pos_pay_txn", "transaction_id"),
        Index("idx_pos_pay_venue_status", "venue_id", "status"),
        Index("idx_pos_pay_processor_txn", "processor_transaction_id"),
    )


class Receipt(Base, UUIDMixin, TimestampMixin):
    """
    Generated receipt record.

    Stores receipt data for customer, merchant, and refund receipts.
    Tracks print and email delivery status.
    """
    __tablename__ = "pos_receipts"

    # References
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pos_transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )

    # Receipt details
    receipt_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True
    )
    receipt_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ReceiptType.CUSTOMER.value
    )
    receipt_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Delivery tracking
    printed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    emailed_to: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    emailed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    transaction: Mapped["Transaction"] = relationship(
        "Transaction", back_populates="receipts"
    )

    __table_args__ = (
        Index("idx_pos_rcpt_venue_number", "venue_id", "receipt_number"),
        Index("idx_pos_rcpt_txn", "transaction_id"),
    )


class Refund(Base, UUIDMixin, TimestampMixin):
    """
    Refund processing and tracking.

    Records refund requests against transactions, including
    approval workflow, processing status, and processor references.
    """
    __tablename__ = "pos_refunds"

    # References
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pos_transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )

    # Refund details
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    refund_reason: Mapped[str] = mapped_column(String(30), nullable=False)
    refund_method: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RefundStatus.PENDING.value
    )

    # Approval and processing
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processor_refund_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # Relationships
    transaction: Mapped["Transaction"] = relationship(
        "Transaction", back_populates="refunds"
    )

    __table_args__ = (
        Index("idx_pos_refund_txn", "transaction_id"),
        Index("idx_pos_refund_venue_status", "venue_id", "status"),
        Index("idx_pos_refund_venue_created", "venue_id", "created_at"),
    )


class TaxRate(Base, UUIDMixin, TimestampMixin):
    """
    Venue-specific tax rate configuration.

    Stores tax rates by type and jurisdiction with effective date
    ranges. Supports multiple tax types (sales, amusement, food,
    beverage) that can apply to specific transaction types.
    """
    __tablename__ = "pos_tax_rates"

    # Core fields
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    tax_type: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    applies_to: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    jurisdiction: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )

    __table_args__ = (
        Index("idx_pos_tax_venue_type_active", "venue_id", "tax_type", "is_active"),
        Index("idx_pos_tax_venue_effective", "venue_id", "effective_date"),
    )


class Shift(Base, UUIDMixin, TimestampMixin):
    """
    Employee shift management.

    Tracks employee shifts at a venue including scheduled and actual
    start/end times, break minutes, and status. Links to cash drawer
    sessions opened during the shift.
    """
    __tablename__ = "pos_shifts"

    # Core references
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    employee_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Scheduled times
    scheduled_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    scheduled_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Actual times
    actual_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Status and details
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ShiftStatus.SCHEDULED.value
    )
    break_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    cash_drawers: Mapped[List["CashDrawer"]] = relationship(
        "CashDrawer",
        back_populates="shift",
        lazy="noload",
    )

    __table_args__ = (
        Index("idx_pos_shift_venue_employee", "venue_id", "employee_id"),
        Index("idx_pos_shift_venue_status", "venue_id", "status"),
        Index("idx_pos_shift_venue_scheduled_start", "venue_id", "scheduled_start"),
    )


class CashDrawer(Base, UUIDMixin, TimestampMixin):
    """
    Cash drawer session management.

    Tracks the lifecycle of a cash drawer session from opening
    to closing, including cash counts, drops, and variance
    calculations for reconciliation.
    """
    __tablename__ = "pos_cash_drawers"

    # Core references
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    terminal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    cashier_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    shift_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pos_shifts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Status and timing
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CashDrawerStatus.OPEN.value
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Cash amounts
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    closing_cash: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    expected_cash: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    variance: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    cash_drops_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )

    # Additional info
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    drawer_transactions: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )

    # Relationships
    shift: Mapped[Optional["Shift"]] = relationship(
        "Shift", back_populates="cash_drawers"
    )

    __table_args__ = (
        Index("idx_pos_drawer_venue_status", "venue_id", "status"),
        Index("idx_pos_drawer_venue_cashier", "venue_id", "cashier_id"),
        Index(
            "idx_pos_drawer_venue_terminal_status",
            "venue_id", "terminal_id", "status",
        ),
    )


class DailyReconciliation(Base, UUIDMixin, TimestampMixin):
    """
    End-of-day financial reconciliation.

    Aggregates all transaction data for a venue on a given date,
    providing totals for sales, taxes, tips, discounts, refunds,
    and payment method breakdowns. Supports variance tracking
    and manager sign-off.
    """
    __tablename__ = "pos_daily_reconciliations"

    # Core references
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    reconciliation_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ReconciliationStatus.PENDING.value
    )

    # Transaction summary
    total_transactions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    gross_sales: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    net_sales: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    total_tax: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    total_tips: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    total_discounts: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    total_refunds: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )

    # Payment method breakdowns
    cash_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    card_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    other_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )

    # Variance tracking
    variance_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    variance_details: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )

    # Sign-off
    reconciled_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    reconciled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "venue_id", "reconciliation_date",
            name="uq_pos_recon_venue_date",
        ),
        Index(
            "idx_pos_recon_venue_date_status",
            "venue_id", "reconciliation_date", "status",
        ),
    )


class ExternalPOSIntegration(Base, UUIDMixin, TimestampMixin):
    """
    Third-party POS system connections.

    Stores configuration for integrations with external POS
    providers (Toast, Square, Clover) including encrypted
    credentials, sync settings, and provider-specific config.
    """
    __tablename__ = "pos_external_integrations"

    # Core references
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Credentials (encrypted at application layer)
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    api_secret_encrypted: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    # Provider details
    location_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    webhook_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    sync_frequency_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=15
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    sync_logs: Mapped[List["POSSyncLog"]] = relationship(
        "POSSyncLog",
        back_populates="integration",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint(
            "venue_id", "provider",
            name="uq_pos_ext_venue_provider",
        ),
        Index(
            "idx_pos_ext_venue_provider_active",
            "venue_id", "provider", "is_active",
        ),
    )


class POSSyncLog(Base, UUIDMixin, TimestampMixin):
    """
    Sync history for external integrations.

    Logs each sync operation with an external POS provider,
    tracking record counts, errors, and duration for monitoring
    and debugging.
    """
    __tablename__ = "pos_sync_logs"

    # References
    integration_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pos_external_integrations.id", ondelete="CASCADE"),
        nullable=False,
    )
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )

    # Sync details
    sync_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    records_synced: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    records_failed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    error_details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    # Relationships
    integration: Mapped["ExternalPOSIntegration"] = relationship(
        "ExternalPOSIntegration", back_populates="sync_logs"
    )

    __table_args__ = (
        Index("idx_pos_sync_integration_status", "integration_id", "status"),
        Index("idx_pos_sync_venue_started", "venue_id", "started_at"),
    )


class Discount(Base, UUIDMixin, TimestampMixin):
    """
    Venue-specific discount configuration.

    Stores discount definitions including percentage, fixed amount,
    BOGO, member discounts, and promo codes. Supports validity periods,
    usage limits, and minimum purchase requirements.
    """
    __tablename__ = "pos_discounts"

    # Core references
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )

    # Discount identification
    code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Discount configuration
    discount_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default=DiscountType.PERCENTAGE.value
    )
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    min_purchase_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    max_discount_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    applies_to: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Validity period
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Usage limits
    max_uses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_uses: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # Status and requirements
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    requires_member: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    __table_args__ = (
        Index("idx_pos_discount_venue_code", "venue_id", "code", unique=True),
        Index("idx_pos_discount_venue_active", "venue_id", "is_active"),
    )


class TransactionLineItem(Base, UUIDMixin, TimestampMixin):
    """
    Individual line item within a transaction.

    Represents a single product or service sold within a transaction,
    including quantity, pricing, discounts, and tax calculations.
    Links to optional product inventory and discount records.
    """
    __tablename__ = "pos_line_items"

    # Core references
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pos_transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )

    # Product identification
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    product_sku: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_category: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )

    # Quantity and pricing
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Discount applied
    discount_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pos_discounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )

    # Tax and total
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Additional info
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    # Relationships
    transaction: Mapped["Transaction"] = relationship(
        "Transaction", back_populates="line_items"
    )

    __table_args__ = (
        Index("idx_pos_line_item_txn", "transaction_id"),
        Index("idx_pos_line_item_venue_product", "venue_id", "product_id"),
    )


class AuditLog(Base, UUIDMixin):
    """
    Immutable audit log for POS operations.

    Records all significant actions performed on POS entities including
    transactions, payments, refunds, and cash drawers. Stores both old
    and new values for tracking changes, along with actor information
    and request metadata.

    Note: Audit logs are immutable - they only have created_at, no updated_at.
    """
    __tablename__ = "pos_audit_logs"

    # Core references
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )

    # Entity being audited
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )

    # Action details
    action: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    # Actor information
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    actor_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # State tracking
    old_values: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Request metadata
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=True
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    # Timestamp (audit logs are immutable, so only created_at)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "idx_pos_audit_venue_entity",
            "venue_id", "entity_type", "entity_id",
        ),
        Index("idx_pos_audit_venue_created", "venue_id", "created_at"),
        Index("idx_pos_audit_actor", "actor_id"),
    )


class TipPool(Base, UUIDMixin, TimestampMixin):
    """
    Tip pool for distributing tips among employees.

    Aggregates tips for a shift date at a venue and tracks distribution
    to participating employees. Supports multiple distribution methods
    (equal, hours-based, sales-based) and maintains a complete record
    of pool participants and their allocated shares.
    """
    __tablename__ = "pos_tip_pools"

    # Core references
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    shift_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TipPoolStatus.OPEN.value
    )

    # Financial amounts
    total_tips: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    distributed_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )

    # Pool configuration
    pool_participants: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )  # [{employee_id, employee_name, hours_worked, tip_share}]
    distribution_method: Mapped[str] = mapped_column(
        String(30), nullable=False, default="hours_based"
    )  # "equal", "hours_based", "sales_based"

    # Additional info
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Distribution tracking
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    distributed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    distributed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )

    # Relationships
    distributions: Mapped[List["TipDistribution"]] = relationship(
        "TipDistribution",
        back_populates="tip_pool",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint(
            "venue_id", "shift_date",
            name="uq_pos_tip_pool_venue_date",
        ),
        Index("idx_pos_tip_pool_venue_status", "venue_id", "status"),
    )


class TipDistribution(Base, UUIDMixin, TimestampMixin):
    """
    Individual tip distribution to an employee.

    Records the actual distribution of tips from a tip pool to a specific
    employee, including the hours worked, calculated tip amount, and
    payment tracking information.
    """
    __tablename__ = "pos_tip_distributions"

    # References
    tip_pool_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pos_tip_pools.id", ondelete="CASCADE"),
        nullable=False,
    )
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )

    # Employee details
    employee_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    employee_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Distribution details
    hours_worked: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=0
    )
    tip_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    # Payment tracking
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payment_method: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True
    )  # "cash", "payroll", "direct_deposit"

    # Additional info
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    tip_pool: Mapped["TipPool"] = relationship(
        "TipPool", back_populates="distributions"
    )

    __table_args__ = (
        Index("idx_pos_tip_dist_pool", "tip_pool_id"),
        Index("idx_pos_tip_dist_venue_employee", "venue_id", "employee_id"),
        Index("idx_pos_tip_dist_venue_created", "venue_id", "created_at"),
    )


class ReceiptTemplateType(str, enum.Enum):
    """Type of receipt template."""
    THERMAL = "thermal"
    FULL_PAGE = "full_page"
    EMAIL = "email"
    SMS = "sms"


class BarcodeType(str, enum.Enum):
    """Type of barcode for receipts."""
    QR = "qr"
    CODE128 = "code128"
    CODE39 = "code39"


class ReceiptTemplate(Base, UUIDMixin, TimestampMixin):
    """
    Customizable receipt template for a venue.

    Stores receipt template configurations that define how receipts are formatted
    and rendered for different output types (thermal printers, full-page printers,
    email, SMS). Each venue can have multiple templates with one default per type.

    Templates control:
    - Header content (logo, venue info)
    - Line item display options
    - Tax and payment breakdowns
    - Footer messages and promotions
    - Barcode/QR code generation
    - Custom CSS for HTML outputs
    """
    __tablename__ = "pos_receipt_templates"

    # Core references
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    template_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ReceiptTemplateType.THERMAL.value
    )

    # Status flags
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    # Header configuration
    header_logo_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    header_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Venue name, address, phone, etc.

    # Content configuration
    show_itemized: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    show_tax_breakdown: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    show_payment_details: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    show_cashier_name: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    show_transaction_id: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    show_barcode: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    barcode_type: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # "qr", "code128", "code39"

    # Footer configuration
    footer_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Thank you message, return policy
    footer_promo: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Current promotion

    # Custom styling
    custom_css: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # For email/web receipts
    template_data: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )  # Additional template configuration

    __table_args__ = (
        UniqueConstraint(
            "venue_id", "name",
            name="uq_pos_receipt_template_venue_name",
        ),
        Index(
            "idx_pos_receipt_template_venue_type_default",
            "venue_id", "template_type", "is_default",
        ),
        Index("idx_pos_receipt_template_venue_active", "venue_id", "is_active"),
    )


class FraudAlert(Base, UUIDMixin, TimestampMixin):
    """
    Fraud detection alert.

    Records suspected fraudulent activity detected by the fraud detection
    service. Alerts can be generated from various checks including high void
    rates, unusual refund patterns, after-hours transactions, large discounts,
    excessive comps, cash drawer variances, split transactions, and repeated voids.

    Each alert tracks:
    - The type and severity of the suspected fraud
    - The entity involved (transaction, cashier, terminal)
    - Detection data and threshold comparisons
    - Investigation status and resolution details
    """
    __tablename__ = "pos_fraud_alerts"

    # Core references
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )

    # Alert classification
    alert_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "high_void_rate", "unusual_refunds", "after_hours", "large_discount", etc.
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default=FraudAlertSeverity.MEDIUM.value
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=FraudAlertStatus.NEW.value
    )

    # Entity reference (what triggered the alert)
    entity_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # "transaction", "cashier", "terminal"
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )

    # Alert details
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    detection_data: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )  # Raw data that triggered alert

    # Threshold comparison
    threshold_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    actual_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), nullable=True
    )

    # Assignment and resolution
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_pos_fraud_alert_venue_status", "venue_id", "status"),
        Index("idx_pos_fraud_alert_venue_severity", "venue_id", "severity"),
        Index("idx_pos_fraud_alert_venue_created", "venue_id", "created_at"),
    )


class Currency(Base, UUIDMixin, TimestampMixin):
    """
    Currency configuration for a venue.

    Stores currency definitions with exchange rates for multi-currency support.
    Each venue has one base currency (is_base=True) and can have multiple
    additional currencies with configurable exchange rates. Supports automatic
    rate updates and currency conversion for international POS operations.

    Attributes:
        venue_id: The venue this currency configuration belongs to.
        code: ISO 4217 currency code (e.g., USD, EUR, GBP).
        name: Human-readable currency name (e.g., US Dollar).
        symbol: Currency symbol for display (e.g., $, EUR, GBP).
        decimal_places: Number of decimal places for this currency (default 2).
        exchange_rate: Conversion rate to the venue's base currency.
        is_base: True if this is the venue's base currency (rate should be 1.0).
        is_active: Whether this currency is currently available for transactions.
        last_rate_update: Timestamp of the last exchange rate update.
    """
    __tablename__ = "pos_currencies"

    # Core reference
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )

    # Currency identification
    code: Mapped[str] = mapped_column(
        String(3), nullable=False,
        comment="ISO 4217 currency code (e.g., USD, EUR, GBP)"
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Human-readable currency name"
    )
    symbol: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="Currency symbol for display (e.g., $, EUR, GBP)"
    )

    # Currency configuration
    decimal_places: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2,
        comment="Number of decimal places for this currency"
    )
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("1.000000"),
        comment="Conversion rate to venue base currency"
    )

    # Status flags
    is_base: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
        comment="True if this is the venue's base currency"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true",
        comment="Whether this currency is available for transactions"
    )

    # Rate tracking
    last_rate_update: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp of the last exchange rate update"
    )

    __table_args__ = (
        UniqueConstraint(
            "venue_id", "code",
            name="uq_pos_currency_venue_code",
        ),
        Index("idx_pos_currency_venue_base", "venue_id", "is_base"),
        Index("idx_pos_currency_venue_active", "venue_id", "is_active"),
    )
