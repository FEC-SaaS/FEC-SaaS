"""
=============================================================================
FILE: schemas/payment.py
PURPOSE: Pydantic schemas for Payment Gateway Service
=============================================================================
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.models.payment import (
    ProcessorType,
    PaymentMethodType,
    CardBrand,
    TransactionType,
    TransactionStatus,
    RefundType,
    RefundStatus,
    BillingInterval,
    SubscriptionStatus,
    FraudRuleType,
    RiskLevel,
    FraudAlertStatus,
    RecommendedAction,
    DisputeType,
    DisputeStatus,
    ComplianceStatus,
)


# =============================================================================
# BASE SCHEMAS
# =============================================================================

class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = Field(default="created_at")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


class BillingAddress(BaseModel):
    """Billing address schema."""
    line1: str
    line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    postal_code: str
    country: str = Field(default="US")


# =============================================================================
# PAYMENT PROCESSOR SCHEMAS
# =============================================================================

class PaymentProcessorBase(BaseSchema):
    """Base processor schema."""
    processor_name: str = Field(..., min_length=1, max_length=50)
    processor_type: ProcessorType
    supported_methods: List[str] = Field(default_factory=list)
    api_version: Optional[str] = None
    fee_structure: Optional[Dict[str, Any]] = None


class PaymentProcessorCreate(PaymentProcessorBase):
    """Create processor schema."""
    pass


class PaymentProcessorResponse(PaymentProcessorBase):
    """Processor response schema."""
    id: UUID
    is_active: bool
    created_at: datetime


# =============================================================================
# VENUE PAYMENT CONFIG SCHEMAS
# =============================================================================

class VenuePaymentConfigCreate(BaseSchema):
    """Create venue payment config schema."""
    venue_id: UUID
    processor_id: UUID
    merchant_id: Optional[str] = None
    is_primary: bool = False
    settings: Optional[Dict[str, Any]] = None


class VenuePaymentConfigResponse(BaseSchema):
    """Venue payment config response schema."""
    id: UUID
    venue_id: UUID
    processor_id: UUID
    merchant_id: Optional[str]
    is_primary: bool
    is_active: bool
    created_at: datetime


# =============================================================================
# PAYMENT METHOD SCHEMAS
# =============================================================================

class PaymentMethodCreate(BaseSchema):
    """Create payment method schema."""
    customer_id: UUID
    venue_id: UUID
    payment_method_type: PaymentMethodType
    token: str = Field(..., description="Tokenized payment method from processor")
    card_brand: Optional[CardBrand] = None
    card_last_four: Optional[str] = Field(None, min_length=4, max_length=4)
    card_exp_month: Optional[int] = Field(None, ge=1, le=12)
    card_exp_year: Optional[int] = Field(None, ge=2024)
    billing_address: Optional[BillingAddress] = None
    nickname: Optional[str] = Field(None, max_length=100)
    set_as_default: bool = False


class PaymentMethodUpdate(BaseSchema):
    """Update payment method schema."""
    billing_address: Optional[BillingAddress] = None
    nickname: Optional[str] = None
    is_default: Optional[bool] = None


class PaymentMethodResponse(BaseSchema):
    """Payment method response schema."""
    id: UUID
    customer_id: UUID
    venue_id: UUID
    payment_method_type: PaymentMethodType
    card_brand: Optional[CardBrand]
    card_last_four: Optional[str]
    card_exp_month: Optional[int]
    card_exp_year: Optional[int]
    billing_address: Optional[Dict[str, Any]]
    nickname: Optional[str]
    is_default: bool
    is_expired: bool
    is_active: bool
    created_at: datetime


class PaymentMethodListResponse(BaseSchema):
    """List of payment methods response."""
    payment_methods: List[PaymentMethodResponse]
    total: int


# =============================================================================
# PAYMENT TRANSACTION SCHEMAS
# =============================================================================

class ChargeRequest(BaseSchema):
    """Charge payment request schema."""
    venue_id: UUID
    customer_id: Optional[UUID] = None
    payment_method_id: Optional[UUID] = None
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    description: Optional[str] = Field(None, max_length=500)
    order_id: Optional[UUID] = None
    invoice_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    # For new card payments (one-time)
    token: Optional[str] = None
    save_payment_method: bool = False
    
    # Fraud detection context
    ip_address: Optional[str] = None
    device_fingerprint: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v


class AuthorizeRequest(ChargeRequest):
    """Authorize payment request schema (capture later)."""
    capture: bool = False


class CaptureRequest(BaseSchema):
    """Capture authorized payment request schema."""
    amount: Optional[Decimal] = Field(None, gt=0, description="Optional partial capture amount")


class VoidRequest(BaseSchema):
    """Void payment request schema."""
    reason: Optional[str] = Field(None, max_length=255)


class PaymentResponse(BaseSchema):
    """Payment response schema."""
    id: UUID
    venue_id: UUID
    customer_id: Optional[UUID]
    payment_method_id: Optional[UUID]
    amount: Decimal
    currency: str
    transaction_type: TransactionType
    status: TransactionStatus
    processor_transaction_id: Optional[str]
    authorization_code: Optional[str]
    processor_fee: Optional[Decimal]
    net_amount: Optional[Decimal]
    error_code: Optional[str]
    error_message: Optional[str]
    fraud_score: Optional[Decimal]
    fraud_check_passed: Optional[bool]
    description: Optional[str]
    receipt_url: Optional[str]
    metadata: Optional[Dict[str, Any]]
    processed_at: Optional[datetime]
    created_at: datetime


class PaymentDetailResponse(PaymentResponse):
    """Detailed payment response including refunds."""
    refunds: List["RefundResponse"] = []
    fraud_alerts: List["FraudAlertResponse"] = []
    disputes: List["DisputeResponse"] = []


class PaymentListResponse(BaseSchema):
    """List of payments response."""
    payments: List[PaymentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# REFUND SCHEMAS
# =============================================================================

class RefundRequest(BaseSchema):
    """Refund request schema."""
    amount: Optional[Decimal] = Field(None, gt=0, description="Leave empty for full refund")
    reason: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class RefundResponse(BaseSchema):
    """Refund response schema."""
    id: UUID
    original_payment_id: UUID
    refund_amount: Decimal
    refund_reason: Optional[str]
    refund_type: RefundType
    status: RefundStatus
    processor_refund_id: Optional[str]
    failure_reason: Optional[str]
    processed_at: Optional[datetime]
    created_at: datetime


class RefundListResponse(BaseSchema):
    """List of refunds response."""
    refunds: List[RefundResponse]
    total: int


# =============================================================================
# SUBSCRIPTION SCHEMAS
# =============================================================================

class SubscriptionCreate(BaseSchema):
    """Create subscription schema."""
    customer_id: UUID
    venue_id: UUID
    payment_method_id: UUID
    membership_id: Optional[UUID] = None
    plan_name: str = Field(..., max_length=100)
    billing_interval: BillingInterval
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="USD")
    start_date: Optional[date] = None
    metadata: Optional[Dict[str, Any]] = None


class SubscriptionUpdate(BaseSchema):
    """Update subscription schema."""
    payment_method_id: Optional[UUID] = None
    amount: Optional[Decimal] = None


class SubscriptionResponse(BaseSchema):
    """Subscription response schema."""
    id: UUID
    customer_id: UUID
    venue_id: UUID
    membership_id: Optional[UUID]
    payment_method_id: UUID
    processor_subscription_id: Optional[str]
    plan_name: str
    billing_interval: BillingInterval
    amount: Decimal
    currency: str
    status: SubscriptionStatus
    start_date: date
    current_period_start: Optional[date]
    current_period_end: Optional[date]
    next_billing_date: Optional[date]
    cancelled_at: Optional[datetime]
    paused_at: Optional[datetime]
    failed_payment_count: int
    created_at: datetime


class SubscriptionListResponse(BaseSchema):
    """List of subscriptions response."""
    subscriptions: List[SubscriptionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# FRAUD DETECTION SCHEMAS
# =============================================================================

class FraudRuleCreate(BaseSchema):
    """Create fraud rule schema."""
    venue_id: Optional[UUID] = None
    rule_name: str = Field(..., max_length=255)
    rule_type: FraudRuleType
    rule_conditions: Dict[str, Any]
    risk_score_impact: int = Field(default=10, ge=1, le=100)
    description: Optional[str] = None
    priority: int = Field(default=100)


class FraudRuleUpdate(BaseSchema):
    """Update fraud rule schema."""
    rule_name: Optional[str] = None
    rule_conditions: Optional[Dict[str, Any]] = None
    risk_score_impact: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


class FraudRuleResponse(BaseSchema):
    """Fraud rule response schema."""
    id: UUID
    venue_id: Optional[UUID]
    rule_name: str
    rule_type: FraudRuleType
    rule_conditions: Dict[str, Any]
    risk_score_impact: int
    description: Optional[str]
    is_active: bool
    priority: int
    created_at: datetime


class FraudAlertResponse(BaseSchema):
    """Fraud alert response schema."""
    id: UUID
    payment_id: UUID
    alert_type: str
    fraud_score: Decimal
    risk_level: RiskLevel
    triggered_rules: List[str]
    rule_details: Optional[Dict[str, Any]]
    recommended_action: RecommendedAction
    status: FraudAlertStatus
    reviewed_by: Optional[UUID]
    review_notes: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime


class FraudAlertReview(BaseSchema):
    """Review fraud alert schema."""
    action: FraudAlertStatus
    notes: Optional[str] = None


class FraudAlertListResponse(BaseSchema):
    """List of fraud alerts response."""
    alerts: List[FraudAlertResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class FraudCheckResult(BaseSchema):
    """Fraud check result schema."""
    passed: bool
    fraud_score: Decimal
    risk_level: RiskLevel
    triggered_rules: List[str]
    recommended_action: RecommendedAction
    details: Dict[str, Any]


# =============================================================================
# DISPUTE SCHEMAS
# =============================================================================

class DisputeResponse(BaseSchema):
    """Dispute response schema."""
    id: UUID
    payment_id: UUID
    dispute_type: DisputeType
    dispute_reason: Optional[str]
    dispute_reason_code: Optional[str]
    dispute_amount: Decimal
    processor_dispute_id: Optional[str]
    dispute_date: date
    response_due_date: Optional[date]
    status: DisputeStatus
    evidence_submitted: Optional[Dict[str, Any]]
    evidence_due_date: Optional[date]
    resolution_date: Optional[date]
    resolution_notes: Optional[str]
    created_at: datetime


class DisputeEvidenceSubmit(BaseSchema):
    """Submit dispute evidence schema."""
    evidence_type: str
    evidence_data: Dict[str, Any]
    notes: Optional[str] = None


class DisputeListResponse(BaseSchema):
    """List of disputes response."""
    disputes: List[DisputeResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# PCI COMPLIANCE SCHEMAS
# =============================================================================

class PCIComplianceResponse(BaseSchema):
    """PCI compliance status response."""
    id: UUID
    venue_id: UUID
    compliance_check_type: str
    check_date: date
    status: ComplianceStatus
    compliance_level: str
    findings: Optional[Dict[str, Any]]
    remediation_required: bool
    remediation_deadline: Optional[date]
    next_check_date: Optional[date]
    created_at: datetime


class PCIComplianceCheckRequest(BaseSchema):
    """Request PCI compliance check."""
    venue_id: UUID
    check_type: str = Field(default="self_assessment")


# =============================================================================
# WEBHOOK SCHEMAS
# =============================================================================

class WebhookEvent(BaseSchema):
    """Webhook event schema."""
    event_type: str
    event_id: str
    processor: str
    payload: Dict[str, Any]
    timestamp: datetime


# =============================================================================
# ANALYTICS SCHEMAS
# =============================================================================

class PaymentAnalytics(BaseSchema):
    """Payment analytics response."""
    total_transactions: int
    total_volume: Decimal
    successful_transactions: int
    failed_transactions: int
    success_rate: Decimal
    average_transaction_amount: Decimal
    total_refunds: int
    refund_volume: Decimal
    total_disputes: int
    dispute_rate: Decimal
    period_start: date
    period_end: date


# Update forward references
PaymentDetailResponse.model_rebuild()
