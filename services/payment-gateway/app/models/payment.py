"""
=============================================================================
FILE: models/payment.py
PURPOSE: Payment Gateway database models
=============================================================================
"""

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# =============================================================================
# ENUMS
# =============================================================================

class ProcessorType(str, enum.Enum):
    GATEWAY = "gateway"
    PROCESSOR = "processor"
    PSP = "psp"


class PaymentMethodType(str, enum.Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    ACH = "ach"
    DIGITAL_WALLET = "digital_wallet"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"


class CardBrand(str, enum.Enum):
    VISA = "visa"
    MASTERCARD = "mastercard"
    AMEX = "amex"
    DISCOVER = "discover"
    DINERS = "diners"
    JCB = "jcb"
    UNIONPAY = "unionpay"
    UNKNOWN = "unknown"


class TransactionType(str, enum.Enum):
    CHARGE = "charge"
    AUTHORIZE = "authorize"
    CAPTURE = "capture"
    REFUND = "refund"
    VOID = "void"


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REQUIRES_ACTION = "requires_action"


class RefundType(str, enum.Enum):
    FULL = "full"
    PARTIAL = "partial"


class RefundStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BillingInterval(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"


class FraudRuleType(str, enum.Enum):
    VELOCITY = "velocity"
    AMOUNT_THRESHOLD = "amount_threshold"
    GEO_LOCATION = "geo_location"
    DEVICE_FINGERPRINT = "device_fingerprint"
    IP_ADDRESS = "ip_address"
    CARD_TESTING = "card_testing"
    CUSTOM = "custom"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FraudAlertStatus(str, enum.Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"
    CONFIRMED = "confirmed"


class RecommendedAction(str, enum.Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REVIEW = "review"
    CHALLENGE = "challenge"


class DisputeType(str, enum.Enum):
    CHARGEBACK = "chargeback"
    INQUIRY = "inquiry"
    RETRIEVAL = "retrieval"
    PRE_ARBITRATION = "pre_arbitration"


class DisputeStatus(str, enum.Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    WON = "won"
    LOST = "lost"
    ACCEPTED = "accepted"
    EXPIRED = "expired"


class ComplianceStatus(str, enum.Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"


# =============================================================================
# MODELS
# =============================================================================

class PaymentProcessor(Base):
    """Payment processor configurations (Stripe, Square, etc.)."""
    
    __tablename__ = "payment_processors"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    processor_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    processor_type: Mapped[ProcessorType] = mapped_column(Enum(ProcessorType), nullable=False)
    supported_methods: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    api_version: Mapped[Optional[str]] = mapped_column(String(20))
    fee_structure: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    webhook_url: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    venue_configs: Mapped[List["VenuePaymentConfig"]] = relationship(back_populates="processor", cascade="all, delete-orphan")


class VenuePaymentConfig(Base):
    """Venue-specific payment processor configuration."""
    
    __tablename__ = "venue_payment_configs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    venue_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    processor_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_processors.id", ondelete="CASCADE"), nullable=False)
    api_credentials_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    merchant_id: Mapped[Optional[str]] = mapped_column(String(255))
    webhook_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    processor: Mapped["PaymentProcessor"] = relationship(back_populates="venue_configs")


class CustomerPaymentMethod(Base):
    """Tokenized customer payment methods."""
    
    __tablename__ = "customer_payment_methods"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    customer_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    venue_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    payment_method_type: Mapped[PaymentMethodType] = mapped_column(Enum(PaymentMethodType), nullable=False)
    processor_token: Mapped[str] = mapped_column(String(255), nullable=False)
    processor_customer_id: Mapped[Optional[str]] = mapped_column(String(255))
    card_brand: Mapped[Optional[CardBrand]] = mapped_column(Enum(CardBrand))
    card_last_four: Mapped[Optional[str]] = mapped_column(String(4))
    card_exp_month: Mapped[Optional[int]] = mapped_column(Integer)
    card_exp_year: Mapped[Optional[int]] = mapped_column(Integer)
    card_fingerprint: Mapped[Optional[str]] = mapped_column(String(255))
    billing_address: Mapped[Optional[dict]] = mapped_column(JSONB)
    nickname: Mapped[Optional[str]] = mapped_column(String(100))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_expired: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    transactions: Mapped[List["PaymentTransaction"]] = relationship(back_populates="payment_method")
    subscriptions: Mapped[List["SubscriptionPayment"]] = relationship(back_populates="payment_method")


class PaymentTransaction(Base):
    """Payment transaction records."""
    
    __tablename__ = "payment_transactions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    venue_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    customer_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), index=True)
    payment_method_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("customer_payment_methods.id", ondelete="SET NULL"))
    processor_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_processors.id", ondelete="SET NULL"))
    
    order_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True))
    invoice_id: Mapped[Optional[str]] = mapped_column(String(100))
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(Enum(TransactionStatus), default=TransactionStatus.PENDING, index=True)
    
    processor_transaction_id: Mapped[Optional[str]] = mapped_column(String(255))
    authorization_code: Mapped[Optional[str]] = mapped_column(String(50))
    processor_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    net_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    
    error_code: Mapped[Optional[str]] = mapped_column(String(50))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    decline_code: Mapped[Optional[str]] = mapped_column(String(50))
    
    fraud_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    fraud_check_passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String(255))
    
    description: Mapped[Optional[str]] = mapped_column(String(500))
    extra_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, default=dict)
    receipt_url: Mapped[Optional[str]] = mapped_column(String(500))
    
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    payment_method: Mapped[Optional["CustomerPaymentMethod"]] = relationship(back_populates="transactions")
    refunds: Mapped[List["PaymentRefund"]] = relationship(back_populates="original_payment", cascade="all, delete-orphan")
    fraud_alerts: Mapped[List["FraudAlert"]] = relationship(back_populates="payment", cascade="all, delete-orphan")
    disputes: Mapped[List["PaymentDispute"]] = relationship(back_populates="payment", cascade="all, delete-orphan")


class PaymentRefund(Base):
    """Payment refund records."""
    
    __tablename__ = "payment_refunds"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    original_payment_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_transactions.id", ondelete="CASCADE"), nullable=False, index=True)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    refund_reason: Mapped[Optional[str]] = mapped_column(String(100))
    refund_type: Mapped[RefundType] = mapped_column(Enum(RefundType), nullable=False)
    status: Mapped[RefundStatus] = mapped_column(Enum(RefundStatus), default=RefundStatus.PENDING)
    processor_refund_id: Mapped[Optional[str]] = mapped_column(String(255))
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)
    initiated_by: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    extra_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, default=dict)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    original_payment: Mapped["PaymentTransaction"] = relationship(back_populates="refunds")


class SubscriptionPayment(Base):
    """Recurring subscription payment records."""
    
    __tablename__ = "subscription_payments"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    customer_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    venue_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    membership_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True))
    payment_method_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customer_payment_methods.id", ondelete="RESTRICT"), nullable=False)
    processor_subscription_id: Mapped[Optional[str]] = mapped_column(String(255))
    processor_customer_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    plan_name: Mapped[str] = mapped_column(String(100), nullable=False)
    billing_interval: Mapped[BillingInterval] = mapped_column(Enum(BillingInterval), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_period_start: Mapped[Optional[date]] = mapped_column(Date)
    current_period_end: Mapped[Optional[date]] = mapped_column(Date)
    next_billing_date: Mapped[Optional[date]] = mapped_column(Date)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    failed_payment_count: Mapped[int] = mapped_column(Integer, default=0)
    last_payment_error: Mapped[Optional[str]] = mapped_column(Text)
    extra_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    payment_method: Mapped["CustomerPaymentMethod"] = relationship(back_populates="subscriptions")


class FraudDetectionRule(Base):
    """Fraud detection rules configuration."""
    
    __tablename__ = "fraud_detection_rules"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    venue_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), index=True)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[FraudRuleType] = mapped_column(Enum(FraudRuleType), nullable=False)
    rule_conditions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    risk_score_impact: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FraudAlert(Base):
    """Fraud detection alerts."""
    
    __tablename__ = "fraud_alerts"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    payment_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_transactions.id", ondelete="CASCADE"), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    fraud_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), nullable=False, index=True)
    triggered_rules: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    rule_details: Mapped[Optional[dict]] = mapped_column(JSONB)
    recommended_action: Mapped[RecommendedAction] = mapped_column(Enum(RecommendedAction), nullable=False)
    status: Mapped[FraudAlertStatus] = mapped_column(Enum(FraudAlertStatus), default=FraudAlertStatus.PENDING)
    reviewed_by: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True))
    review_notes: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    payment: Mapped["PaymentTransaction"] = relationship(back_populates="fraud_alerts")


class PaymentDispute(Base):
    """Payment disputes and chargebacks."""
    
    __tablename__ = "payment_disputes"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    payment_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_transactions.id", ondelete="CASCADE"), nullable=False)
    dispute_type: Mapped[DisputeType] = mapped_column(Enum(DisputeType), nullable=False)
    dispute_reason: Mapped[Optional[str]] = mapped_column(String(100))
    dispute_reason_code: Mapped[Optional[str]] = mapped_column(String(50))
    dispute_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    processor_dispute_id: Mapped[Optional[str]] = mapped_column(String(255))
    dispute_date: Mapped[date] = mapped_column(Date, nullable=False)
    response_due_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[DisputeStatus] = mapped_column(Enum(DisputeStatus), default=DisputeStatus.OPEN, index=True)
    evidence_submitted: Mapped[Optional[dict]] = mapped_column(JSONB)
    evidence_due_date: Mapped[Optional[date]] = mapped_column(Date)
    resolution_date: Mapped[Optional[date]] = mapped_column(Date)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    payment: Mapped["PaymentTransaction"] = relationship(back_populates="disputes")


class PCIComplianceLog(Base):
    """PCI compliance tracking and audit logs."""
    
    __tablename__ = "pci_compliance_logs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    venue_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    compliance_check_type: Mapped[str] = mapped_column(String(50), nullable=False)
    check_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ComplianceStatus] = mapped_column(Enum(ComplianceStatus), nullable=False)
    compliance_level: Mapped[str] = mapped_column(String(20), default="SAQ-A")
    findings: Mapped[Optional[dict]] = mapped_column(JSONB)
    remediation_required: Mapped[bool] = mapped_column(Boolean, default=False)
    remediation_deadline: Mapped[Optional[date]] = mapped_column(Date)
    remediation_completed: Mapped[Optional[date]] = mapped_column(Date)
    next_check_date: Mapped[Optional[date]] = mapped_column(Date)
    auditor: Mapped[Optional[str]] = mapped_column(String(255))
    certificate_url: Mapped[Optional[str]] = mapped_column(String(500))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
