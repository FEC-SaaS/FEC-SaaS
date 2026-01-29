from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.pos import (
    AuditAction,
    BarcodeType,
    DiscountType,
    ExternalPOSProvider,
    FraudAlertSeverity,
    FraudAlertStatus,
    PaymentMethod,
    PaymentProcessor,
    ReceiptTemplateType,
    ReceiptType,
    RefundMethod,
    RefundReason,
    ShiftStatus,
    TaxType,
    TipPoolStatus,
    TransactionType,
)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class BaseSchema(BaseModel):
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Transaction schemas
# ---------------------------------------------------------------------------

class TransactionLineItem(BaseSchema):
    description: str
    quantity: int = 1
    unit_price: Decimal
    total_price: Decimal
    activity_type: Optional[str] = None
    activity_id: Optional[UUID] = None


class TransactionCreate(BaseSchema):
    transaction_type: TransactionType
    customer_id: Optional[UUID] = None
    cashier_id: Optional[UUID] = None
    activity_id: Optional[UUID] = None
    line_items: List[TransactionLineItem]
    subtotal: Decimal
    tax_amount: Decimal = Decimal("0")
    tip_amount: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    total_amount: Decimal
    currency: str = "USD"
    notes: Optional[str] = None
    metadata_: Optional[dict] = Field(None, alias="metadata")


class TransactionResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    customer_id: Optional[UUID] = None
    cashier_id: Optional[UUID] = None
    activity_id: Optional[UUID] = None
    transaction_type: str
    status: str
    subtotal: Decimal
    tax_amount: Decimal
    tip_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    currency: str
    notes: Optional[str] = None
    metadata_: Optional[dict] = Field(None, alias="metadata")
    idempotency_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Payment schemas
# ---------------------------------------------------------------------------

class PaymentCreate(BaseSchema):
    payment_method: PaymentMethod
    payment_processor: Optional[PaymentProcessor] = None
    amount: Decimal = Field(gt=0)
    card_last_four: Optional[str] = None
    card_brand: Optional[str] = None
    payment_data: Optional[dict] = None


class PaymentResponse(BaseSchema):
    id: UUID
    transaction_id: UUID
    venue_id: UUID
    payment_method: str
    payment_processor: Optional[str] = None
    amount: Decimal
    status: str
    processor_transaction_id: Optional[str] = None
    card_last_four: Optional[str] = None
    card_brand: Optional[str] = None
    approval_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Receipt schemas
# ---------------------------------------------------------------------------

class ReceiptGenerateRequest(BaseSchema):
    receipt_type: ReceiptType = ReceiptType.CUSTOMER


class ReceiptEmailRequest(BaseSchema):
    email: str


class ReceiptResponse(BaseSchema):
    id: UUID
    transaction_id: UUID
    venue_id: UUID
    receipt_number: str
    receipt_type: str
    receipt_data: Optional[dict] = None
    printed_at: Optional[datetime] = None
    emailed_to: Optional[str] = None
    emailed_at: Optional[datetime] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Refund schemas
# ---------------------------------------------------------------------------

class RefundCreate(BaseSchema):
    refund_amount: Decimal = Field(gt=0)
    refund_reason: RefundReason
    refund_method: RefundMethod
    notes: Optional[str] = None


class RefundApprove(BaseSchema):
    approved_by: UUID


class RefundResponse(BaseSchema):
    id: UUID
    transaction_id: UUID
    venue_id: UUID
    refund_amount: Decimal
    refund_reason: str
    refund_method: str
    status: str
    approved_by: Optional[UUID] = None
    processed_at: Optional[datetime] = None
    notes: Optional[str] = None
    processor_refund_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Cash Drawer schemas
# ---------------------------------------------------------------------------

class DrawerOpenRequest(BaseSchema):
    terminal_id: str
    opening_cash: Decimal


class DrawerCloseRequest(BaseSchema):
    closing_cash: Decimal
    notes: Optional[str] = None


class CashDropRequest(BaseSchema):
    amount: Decimal = Field(gt=0)
    notes: Optional[str] = None


class DrawerResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    terminal_id: str
    cashier_id: UUID
    shift_id: Optional[UUID] = None
    status: str
    opened_at: datetime
    closed_at: Optional[datetime] = None
    opening_cash: Decimal
    closing_cash: Optional[Decimal] = None
    expected_cash: Optional[Decimal] = None
    variance: Optional[Decimal] = None
    cash_drops_total: Optional[Decimal] = None
    notes: Optional[str] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Tax schemas
# ---------------------------------------------------------------------------

class TaxRateCreate(BaseSchema):
    tax_type: TaxType
    name: str
    rate: Decimal = Field(gt=0, le=1)
    applies_to: Optional[List[str]] = None
    effective_date: date
    end_date: Optional[date] = None
    jurisdiction: Optional[str] = None


class TaxRateUpdate(BaseSchema):
    name: Optional[str] = None
    rate: Optional[Decimal] = None
    applies_to: Optional[List[str]] = None
    is_active: Optional[bool] = None
    end_date: Optional[date] = None


class TaxRateResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    tax_type: str
    name: str
    rate: Decimal
    applies_to: Optional[List[str]] = None
    is_active: bool
    effective_date: date
    end_date: Optional[date] = None
    jurisdiction: Optional[str] = None


class TaxCalculationRequest(BaseSchema):
    transaction_type: TransactionType
    subtotal: Decimal


class TaxCalculationResponse(BaseSchema):
    transaction_type: str
    subtotal: Decimal
    tax_rates: List[dict]
    total_tax: Decimal
    total_with_tax: Decimal


# ---------------------------------------------------------------------------
# Reconciliation schemas
# ---------------------------------------------------------------------------

class ReconciliationCreate(BaseSchema):
    reconciliation_date: date


class ReconciliationResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    reconciliation_date: date
    status: str
    total_transactions: int
    gross_sales: Decimal
    net_sales: Decimal
    total_tax: Decimal
    total_tips: Decimal
    total_discounts: Decimal
    total_refunds: Decimal
    cash_total: Decimal
    card_total: Decimal
    other_total: Decimal
    variance_amount: Decimal
    variance_details: Optional[dict] = None
    reconciled_by: Optional[UUID] = None
    reconciled_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# External POS Integration schemas
# ---------------------------------------------------------------------------

class IntegrationCreate(BaseSchema):
    provider: ExternalPOSProvider
    provider_name: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    location_id: Optional[str] = None
    webhook_url: Optional[str] = None
    sync_frequency_minutes: int = 15
    config: Optional[dict] = None


class IntegrationUpdate(BaseSchema):
    provider_name: Optional[str] = None
    location_id: Optional[str] = None
    webhook_url: Optional[str] = None
    sync_frequency_minutes: Optional[int] = None
    is_active: Optional[bool] = None
    config: Optional[dict] = None


class IntegrationResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    provider: str
    provider_name: str
    location_id: Optional[str] = None
    webhook_url: Optional[str] = None
    sync_frequency_minutes: int
    is_active: bool
    last_sync_at: Optional[datetime] = None
    config: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class SyncLogResponse(BaseSchema):
    id: UUID
    integration_id: UUID
    venue_id: UUID
    sync_type: str
    status: str
    records_synced: int
    records_failed: int
    error_details: Optional[dict] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None


# ---------------------------------------------------------------------------
# Discount schemas
# ---------------------------------------------------------------------------

class DiscountCreate(BaseSchema):
    code: Optional[str] = None
    name: str
    description: Optional[str] = None
    discount_type: DiscountType
    value: Decimal = Field(gt=0)
    min_purchase_amount: Optional[Decimal] = None
    max_discount_amount: Optional[Decimal] = None
    applies_to: Optional[dict] = None
    start_date: date
    end_date: Optional[date] = None
    max_uses: Optional[int] = None
    is_active: bool = True
    requires_member: bool = False


class DiscountUpdate(BaseSchema):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    discount_type: Optional[DiscountType] = None
    value: Optional[Decimal] = None
    min_purchase_amount: Optional[Decimal] = None
    max_discount_amount: Optional[Decimal] = None
    applies_to: Optional[dict] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    max_uses: Optional[int] = None
    is_active: Optional[bool] = None
    requires_member: Optional[bool] = None


class DiscountResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    code: Optional[str] = None
    name: str
    description: Optional[str] = None
    discount_type: str
    value: Decimal
    min_purchase_amount: Optional[Decimal] = None
    max_discount_amount: Optional[Decimal] = None
    applies_to: Optional[dict] = None
    start_date: date
    end_date: Optional[date] = None
    max_uses: Optional[int] = None
    current_uses: int
    is_active: bool
    requires_member: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Line Item schemas
# ---------------------------------------------------------------------------

class LineItemCreate(BaseSchema):
    product_id: Optional[UUID] = None
    product_sku: Optional[str] = None
    product_name: str
    product_category: Optional[str] = None
    quantity: int = Field(ge=1, default=1)
    unit_price: Decimal
    subtotal: Decimal
    discount_id: Optional[UUID] = None
    discount_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    total: Decimal
    metadata_: Optional[dict] = Field(None, alias="metadata")


class LineItemResponse(BaseSchema):
    id: UUID
    transaction_id: UUID
    venue_id: UUID
    product_id: Optional[UUID] = None
    product_sku: Optional[str] = None
    product_name: str
    product_category: Optional[str] = None
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    discount_id: Optional[UUID] = None
    discount_amount: Decimal
    tax_amount: Decimal
    total: Decimal
    metadata_: Optional[dict] = Field(None, alias="metadata")
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Shift schemas
# ---------------------------------------------------------------------------

class ShiftCreate(BaseSchema):
    employee_id: UUID
    employee_name: str
    scheduled_start: datetime
    scheduled_end: datetime
    notes: Optional[str] = None


class ShiftUpdate(BaseSchema):
    employee_name: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    status: Optional[ShiftStatus] = None
    break_minutes: Optional[int] = None
    notes: Optional[str] = None


class ShiftResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    employee_id: UUID
    employee_name: str
    scheduled_start: datetime
    scheduled_end: datetime
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    status: str
    break_minutes: int
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Audit Log schemas
# ---------------------------------------------------------------------------

class AuditLogResponse(BaseSchema):
    """Read-only audit log response. Audit logs are created internally."""
    id: UUID
    venue_id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    actor_id: Optional[UUID] = None
    actor_name: Optional[str] = None
    old_values: Optional[dict] = None
    new_values: Optional[dict] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata_: Optional[dict] = Field(None, alias="metadata")
    created_at: datetime


# ---------------------------------------------------------------------------
# Tip Pool schemas
# ---------------------------------------------------------------------------

class TipPoolParticipant(BaseSchema):
    """Individual participant in a tip pool."""
    employee_id: UUID
    employee_name: str
    hours_worked: Decimal = Field(ge=0)
    tip_share: Optional[Decimal] = None


class TipPoolCreate(BaseSchema):
    """Request to create a new tip pool."""
    shift_date: date
    distribution_method: str = Field(
        default="hours_based",
        pattern="^(equal|hours_based|sales_based)$",
        description="Method for distributing tips: 'equal', 'hours_based', or 'sales_based'"
    )
    notes: Optional[str] = None


class TipPoolUpdate(BaseSchema):
    """Request to update a tip pool."""
    distribution_method: Optional[str] = Field(
        default=None,
        pattern="^(equal|hours_based|sales_based)$"
    )
    notes: Optional[str] = None


class TipPoolAddTips(BaseSchema):
    """Request to add tips to a tip pool."""
    amount: Decimal = Field(gt=0, description="Amount of tips to add")


class TipPoolAddParticipant(BaseSchema):
    """Request to add a participant to a tip pool."""
    employee_id: UUID
    employee_name: str
    hours_worked: Decimal = Field(ge=0)


class TipPoolResponse(BaseSchema):
    """Full tip pool response."""
    id: UUID
    venue_id: UUID
    shift_date: date
    status: str
    total_tips: Decimal
    distributed_amount: Decimal
    pool_participants: Optional[List[TipPoolParticipant]] = None
    distribution_method: str
    notes: Optional[str] = None
    closed_at: Optional[datetime] = None
    distributed_at: Optional[datetime] = None
    distributed_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class TipDistributionResponse(BaseSchema):
    """Individual tip distribution response."""
    id: UUID
    tip_pool_id: UUID
    venue_id: UUID
    employee_id: UUID
    employee_name: str
    hours_worked: Decimal
    tip_amount: Decimal
    paid_at: Optional[datetime] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TipDistributionPreview(BaseSchema):
    """Preview of a single employee's tip distribution."""
    employee_id: UUID
    employee_name: str
    hours_worked: Decimal
    tip_amount: Decimal
    percentage: Decimal


class TipDistributionCalculation(BaseSchema):
    """Response from distribution calculation preview."""
    pool_id: UUID
    total_tips: Decimal
    distribution_method: str
    total_hours: Decimal
    participant_count: int
    distributions: List[TipDistributionPreview]


class TipSummary(BaseSchema):
    """Summary of tips for a venue over a date range."""
    venue_id: UUID
    date_from: date
    date_to: date
    total_pools: int
    total_tips_collected: Decimal
    total_tips_distributed: Decimal
    total_participants: int
    pools_by_status: dict
    average_tip_per_pool: Decimal
    average_tip_per_employee: Decimal


# ---------------------------------------------------------------------------
# Receipt Template schemas
# ---------------------------------------------------------------------------

class ReceiptTemplateCreate(BaseSchema):
    """Request to create a new receipt template."""
    name: str = Field(..., min_length=1, max_length=100)
    template_type: ReceiptTemplateType = ReceiptTemplateType.THERMAL
    is_default: bool = False
    is_active: bool = True

    # Header configuration
    header_logo_url: Optional[str] = Field(None, max_length=500)
    header_text: Optional[str] = None

    # Content configuration
    show_itemized: bool = True
    show_tax_breakdown: bool = True
    show_payment_details: bool = True
    show_cashier_name: bool = True
    show_transaction_id: bool = True
    show_barcode: bool = False
    barcode_type: Optional[BarcodeType] = None

    # Footer configuration
    footer_text: Optional[str] = None
    footer_promo: Optional[str] = None

    # Custom styling
    custom_css: Optional[str] = None
    template_data: Optional[dict] = None


class ReceiptTemplateUpdate(BaseSchema):
    """Request to update an existing receipt template."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    template_type: Optional[ReceiptTemplateType] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None

    # Header configuration
    header_logo_url: Optional[str] = Field(None, max_length=500)
    header_text: Optional[str] = None

    # Content configuration
    show_itemized: Optional[bool] = None
    show_tax_breakdown: Optional[bool] = None
    show_payment_details: Optional[bool] = None
    show_cashier_name: Optional[bool] = None
    show_transaction_id: Optional[bool] = None
    show_barcode: Optional[bool] = None
    barcode_type: Optional[BarcodeType] = None

    # Footer configuration
    footer_text: Optional[str] = None
    footer_promo: Optional[str] = None

    # Custom styling
    custom_css: Optional[str] = None
    template_data: Optional[dict] = None


class ReceiptTemplateResponse(BaseSchema):
    """Full receipt template response."""
    id: UUID
    venue_id: UUID
    name: str
    template_type: str
    is_default: bool
    is_active: bool

    # Header configuration
    header_logo_url: Optional[str] = None
    header_text: Optional[str] = None

    # Content configuration
    show_itemized: bool
    show_tax_breakdown: bool
    show_payment_details: bool
    show_cashier_name: bool
    show_transaction_id: bool
    show_barcode: bool
    barcode_type: Optional[str] = None

    # Footer configuration
    footer_text: Optional[str] = None
    footer_promo: Optional[str] = None

    # Custom styling
    custom_css: Optional[str] = None
    template_data: Optional[dict] = None

    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Fraud Alert schemas
# ---------------------------------------------------------------------------

class FraudAlertUpdate(BaseSchema):
    """Request to update a fraud alert status."""
    status: FraudAlertStatus
    notes: Optional[str] = None
    resolved_by: Optional[UUID] = None


class FraudAlertAssign(BaseSchema):
    """Request to assign a fraud alert to a user."""
    assigned_to: UUID


class FraudAlertResponse(BaseSchema):
    """Full fraud alert response."""
    id: UUID
    venue_id: UUID
    alert_type: str
    severity: str
    status: str

    # Entity reference
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None

    # Alert details
    title: str
    description: str
    detection_data: Optional[dict] = None
    threshold_value: Optional[Decimal] = None
    actual_value: Optional[Decimal] = None

    # Assignment and resolution
    assigned_to: Optional[UUID] = None
    resolved_by: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None

    created_at: datetime
    updated_at: datetime


class FraudAlertSummaryByType(BaseSchema):
    """Fraud alert count by type."""
    alert_type: str
    count: int


class FraudAlertSummaryBySeverity(BaseSchema):
    """Fraud alert count by severity."""
    severity: str
    count: int


class FraudAlertSummaryByStatus(BaseSchema):
    """Fraud alert count by status."""
    status: str
    count: int


class FraudSummary(BaseSchema):
    """Summary of fraud alerts for a venue over a date range."""
    venue_id: UUID
    date_from: date
    date_to: date
    total_alerts: int
    new_alerts: int
    investigating_alerts: int
    confirmed_alerts: int
    dismissed_alerts: int
    resolved_alerts: int
    by_type: List[FraudAlertSummaryByType]
    by_severity: List[FraudAlertSummaryBySeverity]
    by_status: List[FraudAlertSummaryByStatus]
    critical_unresolved: int
    high_unresolved: int
    average_resolution_hours: Optional[Decimal] = None


# ---------------------------------------------------------------------------
# Currency schemas
# ---------------------------------------------------------------------------

class CurrencyCreate(BaseSchema):
    """
    Request to create a new currency for a venue.

    Attributes:
        code: ISO 4217 currency code (3 characters, e.g., USD, EUR, GBP).
        name: Human-readable currency name (e.g., US Dollar).
        symbol: Currency symbol for display (e.g., $, EUR, GBP).
        decimal_places: Number of decimal places for this currency (default 2).
        exchange_rate: Conversion rate to the venue's base currency.
        is_base: Whether this is the venue's base currency.
    """
    code: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code (e.g., USD, EUR, GBP)"
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Human-readable currency name"
    )
    symbol: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Currency symbol for display (e.g., $, EUR, GBP)"
    )
    decimal_places: int = Field(
        default=2,
        ge=0,
        le=8,
        description="Number of decimal places for this currency"
    )
    exchange_rate: Decimal = Field(
        ...,
        gt=0,
        description="Conversion rate to venue base currency"
    )
    is_base: bool = Field(
        default=False,
        description="True if this is the venue's base currency"
    )


class CurrencyUpdate(BaseSchema):
    """
    Request to update an existing currency.

    All fields are optional; only provided fields will be updated.

    Attributes:
        name: Updated currency name.
        symbol: Updated currency symbol.
        decimal_places: Updated decimal places.
        exchange_rate: Updated exchange rate.
        is_active: Whether the currency is available for transactions.
    """
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Updated currency name"
    )
    symbol: Optional[str] = Field(
        None,
        min_length=1,
        max_length=10,
        description="Updated currency symbol"
    )
    decimal_places: Optional[int] = Field(
        None,
        ge=0,
        le=8,
        description="Updated decimal places"
    )
    exchange_rate: Optional[Decimal] = Field(
        None,
        gt=0,
        description="Updated exchange rate"
    )
    is_active: Optional[bool] = Field(
        None,
        description="Whether the currency is available for transactions"
    )


class CurrencyResponse(BaseSchema):
    """
    Full currency response with all fields.

    Attributes:
        id: Unique currency identifier.
        venue_id: The venue this currency belongs to.
        code: ISO 4217 currency code.
        name: Human-readable currency name.
        symbol: Currency symbol for display.
        decimal_places: Number of decimal places.
        exchange_rate: Conversion rate to venue base currency.
        is_base: Whether this is the venue's base currency.
        is_active: Whether the currency is available for transactions.
        last_rate_update: Timestamp of last exchange rate update.
        created_at: Record creation timestamp.
        updated_at: Record last update timestamp.
    """
    id: UUID
    venue_id: UUID
    code: str
    name: str
    symbol: str
    decimal_places: int
    exchange_rate: Decimal
    is_base: bool
    is_active: bool
    last_rate_update: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class CurrencyConversionRequest(BaseSchema):
    """
    Request to convert an amount between currencies.

    Attributes:
        amount: The amount to convert.
        from_currency: Source currency code (e.g., USD).
        to_currency: Target currency code (e.g., EUR).
    """
    amount: Decimal = Field(
        ...,
        description="The amount to convert"
    )
    from_currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Source currency code (e.g., USD)"
    )
    to_currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Target currency code (e.g., EUR)"
    )


class CurrencyConversionResponse(BaseSchema):
    """
    Response containing the converted amount and conversion details.

    Attributes:
        original_amount: The original amount before conversion.
        converted_amount: The amount after conversion.
        from_currency: Source currency code.
        to_currency: Target currency code.
        exchange_rate: The exchange rate used for conversion.
        formatted_original: Original amount formatted with currency symbol.
        formatted_converted: Converted amount formatted with currency symbol.
    """
    original_amount: Decimal
    converted_amount: Decimal
    from_currency: str
    to_currency: str
    exchange_rate: Decimal
    formatted_original: str
    formatted_converted: str
