"""
=============================================================================
FILE: schemas/membership.py
PURPOSE: Pydantic schemas for Membership Service
=============================================================================
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.models.membership import (
    BillingInterval,
    PlanType,
    SubscriptionStatus,
    InvoiceStatus,
    UsageType,
    UsageResetPeriod,
    LoyaltyTransactionType,
    RewardType,
    RedemptionStatus,
    ReferralStatus,
    RelationshipType,
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


# =============================================================================
# MEMBERSHIP TIER SCHEMAS
# =============================================================================

class MembershipTierBase(BaseSchema):
    """Base membership tier schema."""
    tier_name: str = Field(..., min_length=1, max_length=50)
    tier_level: int = Field(default=1, ge=1)
    monthly_fee: Decimal = Field(..., ge=0)
    annual_fee: Optional[Decimal] = Field(None, ge=0)
    setup_fee: Decimal = Field(default=Decimal("0"), ge=0)
    benefits_description: Optional[str] = None
    benefits: Optional[Dict[str, Any]] = Field(default_factory=dict)
    max_family_members: int = Field(default=1, ge=1)
    points_multiplier: Decimal = Field(default=Decimal("1.0"), ge=1, le=10)
    free_guest_passes_monthly: int = Field(default=0, ge=0)
    discount_percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    priority_booking: bool = False


class MembershipTierCreate(MembershipTierBase):
    """Create membership tier schema."""
    venue_id: UUID


class MembershipTierUpdate(BaseSchema):
    """Update membership tier schema."""
    tier_name: Optional[str] = None
    tier_level: Optional[int] = None
    monthly_fee: Optional[Decimal] = None
    annual_fee: Optional[Decimal] = None
    setup_fee: Optional[Decimal] = None
    benefits_description: Optional[str] = None
    benefits: Optional[Dict[str, Any]] = None
    max_family_members: Optional[int] = None
    points_multiplier: Optional[Decimal] = None
    free_guest_passes_monthly: Optional[int] = None
    discount_percentage: Optional[Decimal] = None
    priority_booking: Optional[bool] = None
    is_active: Optional[bool] = None


class MembershipTierResponse(MembershipTierBase):
    """Membership tier response schema."""
    id: UUID
    venue_id: UUID
    is_active: bool
    created_at: datetime


# =============================================================================
# SUBSCRIPTION PLAN SCHEMAS
# =============================================================================

class SubscriptionPlanBase(BaseSchema):
    """Base subscription plan schema."""
    plan_name: str = Field(..., min_length=1, max_length=100)
    plan_type: PlanType
    billing_interval: BillingInterval
    price: Decimal = Field(..., gt=0)
    setup_fee: Decimal = Field(default=Decimal("0"), ge=0)
    trial_days: int = Field(default=0, ge=0)
    included_benefits: Optional[Dict[str, Any]] = Field(default_factory=dict)
    usage_limits: Optional[Dict[str, Any]] = Field(default_factory=dict)
    description: Optional[str] = None
    terms_conditions: Optional[str] = None
    max_subscribers: Optional[int] = Field(None, ge=1)


class SubscriptionPlanCreate(SubscriptionPlanBase):
    """Create subscription plan schema."""
    venue_id: UUID
    tier_id: Optional[UUID] = None


class SubscriptionPlanUpdate(BaseSchema):
    """Update subscription plan schema."""
    plan_name: Optional[str] = None
    price: Optional[Decimal] = None
    setup_fee: Optional[Decimal] = None
    trial_days: Optional[int] = None
    included_benefits: Optional[Dict[str, Any]] = None
    usage_limits: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    terms_conditions: Optional[str] = None
    max_subscribers: Optional[int] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    sort_order: Optional[int] = None


class SubscriptionPlanResponse(SubscriptionPlanBase):
    """Subscription plan response schema."""
    id: UUID
    venue_id: UUID
    tier_id: Optional[UUID]
    is_active: bool
    is_featured: bool
    sort_order: int
    created_at: datetime


class SubscriptionPlanListResponse(BaseSchema):
    """List of subscription plans response."""
    plans: List[SubscriptionPlanResponse]
    total: int


# =============================================================================
# CUSTOMER SUBSCRIPTION SCHEMAS
# =============================================================================

class SubscribeRequest(BaseSchema):
    """Subscribe to a plan request."""
    customer_id: UUID
    venue_id: UUID
    plan_id: UUID
    payment_method_id: UUID
    start_date: Optional[date] = None
    apply_trial: bool = True
    referral_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SubscriptionResponse(BaseSchema):
    """Customer subscription response."""
    id: UUID
    customer_id: UUID
    venue_id: UUID
    plan_id: UUID
    tier_id: Optional[UUID]
    status: SubscriptionStatus
    start_date: date
    current_period_start: Optional[date]
    current_period_end: Optional[date]
    trial_end: Optional[date]
    cancel_at_period_end: bool
    cancelled_at: Optional[datetime]
    paused_at: Optional[datetime]
    failed_payment_count: int
    last_payment_date: Optional[date]
    next_billing_date: Optional[date]
    created_at: datetime


class SubscriptionDetailResponse(SubscriptionResponse):
    """Detailed subscription response with related data."""
    plan: SubscriptionPlanResponse
    tier: Optional[MembershipTierResponse]
    usage_limits: List["UsageLimitResponse"] = []


class SubscriptionListResponse(BaseSchema):
    """List of subscriptions response."""
    subscriptions: List[SubscriptionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SubscriptionUpgradeRequest(BaseSchema):
    """Upgrade subscription request."""
    new_plan_id: UUID
    prorate: bool = True


class SubscriptionPauseRequest(BaseSchema):
    """Pause subscription request."""
    pause_end_date: date
    reason: Optional[str] = None

    @field_validator("pause_end_date")
    @classmethod
    def validate_pause_date(cls, v):
        if v <= date.today():
            raise ValueError("Pause end date must be in the future")
        return v


class SubscriptionCancelRequest(BaseSchema):
    """Cancel subscription request."""
    cancel_at_period_end: bool = True
    reason: Optional[str] = None


# =============================================================================
# INVOICE SCHEMAS
# =============================================================================

class InvoiceResponse(BaseSchema):
    """Subscription invoice response."""
    id: UUID
    subscription_id: UUID
    invoice_number: Optional[str]
    invoice_date: date
    due_date: date
    amount_due: Decimal
    amount_paid: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    status: InvoiceStatus
    payment_method: Optional[str]
    paid_at: Optional[datetime]
    failure_reason: Optional[str]
    line_items: Optional[List[Dict[str, Any]]]
    created_at: datetime


class InvoiceListResponse(BaseSchema):
    """List of invoices response."""
    invoices: List[InvoiceResponse]
    total: int


# =============================================================================
# USAGE LIMIT SCHEMAS
# =============================================================================

class UsageLimitResponse(BaseSchema):
    """Subscription usage limit response."""
    id: UUID
    subscription_id: UUID
    usage_type: UsageType
    included_quantity: int
    used_quantity: int
    remaining_quantity: int = 0
    rollover_allowed: bool
    rollover_quantity: int
    reset_period: UsageResetPeriod
    next_reset_date: Optional[date]

    @field_validator("remaining_quantity", mode="before")
    @classmethod
    def calculate_remaining(cls, v, info):
        data = info.data
        included = data.get("included_quantity", 0)
        used = data.get("used_quantity", 0)
        rollover = data.get("rollover_quantity", 0)
        return max(0, included + rollover - used)


class UsageLimitCreate(BaseSchema):
    """Create usage limit for a plan."""
    usage_type: UsageType
    limit_value: int = Field(..., ge=1)
    reset_period: UsageResetPeriod


class UsageRecordRequest(BaseSchema):
    """Record usage request."""
    usage_type: UsageType
    quantity: int = Field(..., ge=1)
    reference_id: Optional[str] = None


# =============================================================================
# LOYALTY PROGRAM SCHEMAS
# =============================================================================

class LoyaltyProgramBase(BaseSchema):
    """Base loyalty program schema."""
    program_name: str = Field(..., min_length=1, max_length=100)
    points_per_dollar: Decimal = Field(default=Decimal("1.0"), ge=0)
    points_expiry_days: Optional[int] = Field(None, ge=1)
    minimum_redemption_points: int = Field(default=100, ge=0)
    signup_bonus_points: int = Field(default=0, ge=0)
    birthday_bonus_points: int = Field(default=0, ge=0)
    referral_bonus_points: int = Field(default=0, ge=0)
    terms_conditions: Optional[str] = None


class LoyaltyProgramCreate(LoyaltyProgramBase):
    """Create loyalty program schema."""
    venue_id: UUID


class LoyaltyProgramUpdate(BaseSchema):
    """Update loyalty program schema."""
    program_name: Optional[str] = None
    points_per_dollar: Optional[Decimal] = None
    points_expiry_days: Optional[int] = None
    minimum_redemption_points: Optional[int] = None
    signup_bonus_points: Optional[int] = None
    birthday_bonus_points: Optional[int] = None
    referral_bonus_points: Optional[int] = None
    terms_conditions: Optional[str] = None
    is_active: Optional[bool] = None


class LoyaltyProgramResponse(LoyaltyProgramBase):
    """Loyalty program response."""
    id: UUID
    venue_id: UUID
    is_active: bool
    created_at: datetime


# =============================================================================
# LOYALTY ACCOUNT SCHEMAS
# =============================================================================

class LoyaltyAccountResponse(BaseSchema):
    """Customer loyalty account response."""
    id: UUID
    customer_id: UUID
    program_id: UUID
    points_balance: int
    lifetime_points_earned: int
    lifetime_points_redeemed: int
    tier_multiplier: Decimal
    last_activity_at: Optional[datetime]
    created_at: datetime


class EarnPointsRequest(BaseSchema):
    """Earn points request."""
    customer_id: UUID
    venue_id: UUID
    order_amount: Decimal = Field(..., gt=0)
    order_id: Optional[str] = None
    description: Optional[str] = None


class EarnPointsResponse(BaseSchema):
    """Earn points response."""
    points_earned: int
    multiplier_applied: Decimal
    new_balance: int
    transaction_id: UUID


class RedeemPointsRequest(BaseSchema):
    """Redeem points request."""
    customer_id: UUID
    venue_id: UUID
    points_amount: int = Field(..., gt=0)
    reason: Optional[str] = None


class RedeemPointsResponse(BaseSchema):
    """Redeem points response."""
    points_redeemed: int
    new_balance: int
    transaction_id: UUID


class LoyaltyTransactionResponse(BaseSchema):
    """Loyalty transaction response."""
    id: UUID
    loyalty_account_id: UUID
    transaction_type: LoyaltyTransactionType
    points_amount: int
    balance_after: int
    reference_type: Optional[str]
    reference_id: Optional[str]
    description: Optional[str]
    expires_at: Optional[date]
    multiplier_applied: Decimal
    order_amount: Optional[Decimal]
    created_at: datetime


class LoyaltyTransactionListResponse(BaseSchema):
    """List of loyalty transactions response."""
    transactions: List[LoyaltyTransactionResponse]
    total: int
    page: int
    page_size: int


class TierProgressResponse(BaseSchema):
    """Tier progress information."""
    current_tier: Optional[MembershipTierResponse] = None
    next_tier: Optional[MembershipTierResponse] = None
    lifetime_points: int
    points_to_next_tier: Optional[int] = None
    progress_percent: Optional[float] = None


# =============================================================================
# REWARDS SCHEMAS
# =============================================================================

class RewardBase(BaseSchema):
    """Base reward schema."""
    reward_name: str = Field(..., min_length=1, max_length=255)
    reward_type: RewardType
    description: Optional[str] = None
    points_cost: int = Field(..., ge=1)
    monetary_value: Optional[Decimal] = Field(None, ge=0)
    discount_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    quantity_available: Optional[int] = Field(None, ge=0)
    max_redemptions_per_customer: Optional[int] = Field(None, ge=1)
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    applicable_items: Optional[List[str]] = None
    terms_conditions: Optional[str] = None
    image_url: Optional[str] = None


class RewardCreate(RewardBase):
    """Create reward schema."""
    venue_id: UUID
    program_id: Optional[UUID] = None


class RewardUpdate(BaseSchema):
    """Update reward schema."""
    reward_name: Optional[str] = None
    description: Optional[str] = None
    points_cost: Optional[int] = None
    monetary_value: Optional[Decimal] = None
    discount_percentage: Optional[Decimal] = None
    quantity_available: Optional[int] = None
    max_redemptions_per_customer: Optional[int] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    applicable_items: Optional[List[str]] = None
    terms_conditions: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None


class RewardResponse(RewardBase):
    """Reward response."""
    id: UUID
    venue_id: UUID
    program_id: Optional[UUID]
    quantity_redeemed: int
    is_active: bool
    is_featured: bool
    sort_order: int
    created_at: datetime


class RewardListResponse(BaseSchema):
    """List of rewards response."""
    rewards: List[RewardResponse]
    total: int


class RedeemRewardRequest(BaseSchema):
    """Redeem reward request."""
    customer_id: UUID
    reward_id: UUID


class RedemptionResponse(BaseSchema):
    """Reward redemption response."""
    id: UUID
    customer_id: UUID
    reward_id: UUID
    points_spent: int
    redemption_code: str
    status: RedemptionStatus
    used_at: Optional[datetime]
    expires_at: datetime
    created_at: datetime


class RedemptionListResponse(BaseSchema):
    """List of redemptions response."""
    redemptions: List[RedemptionResponse]
    total: int


# =============================================================================
# FAMILY MEMBERSHIP SCHEMAS
# =============================================================================

class FamilyMemberRequest(BaseSchema):
    """Add family member request."""
    customer_id: UUID
    relationship: RelationshipType


class FamilyMemberResponse(BaseSchema):
    """Family member response."""
    id: UUID
    family_id: UUID
    customer_id: UUID
    relationship: RelationshipType
    is_active: bool
    created_at: datetime


class FamilyMembershipCreate(BaseSchema):
    """Create family membership request."""
    primary_customer_id: UUID
    subscription_id: UUID
    family_name: Optional[str] = None
    members: List[FamilyMemberRequest] = []


class FamilyMembershipResponse(BaseSchema):
    """Family membership response."""
    id: UUID
    primary_customer_id: UUID
    subscription_id: UUID
    family_name: Optional[str]
    max_members: int
    members: List[FamilyMemberResponse] = []
    created_at: datetime


# =============================================================================
# CORPORATE SUBSCRIPTION SCHEMAS
# =============================================================================

class CorporateEmployeeRequest(BaseSchema):
    """Add corporate employee request."""
    customer_id: UUID
    employee_email: str
    employee_name: Optional[str] = None
    department: Optional[str] = None


class CorporateEmployeeResponse(BaseSchema):
    """Corporate employee response."""
    id: UUID
    corporate_subscription_id: UUID
    customer_id: UUID
    employee_email: str
    employee_name: Optional[str]
    department: Optional[str]
    activated_at: Optional[datetime]
    is_active: bool
    created_at: datetime


class CorporateSubscriptionCreate(BaseSchema):
    """Create corporate subscription request."""
    venue_id: UUID
    company_name: str = Field(..., min_length=1, max_length=255)
    billing_contact_id: UUID
    plan_id: UUID
    employee_limit: int = Field(..., ge=1)
    discount_percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    custom_price: Optional[Decimal] = Field(None, gt=0)
    contract_start_date: date
    contract_end_date: Optional[date] = None
    billing_email: Optional[str] = None
    notes: Optional[str] = None


class CorporateSubscriptionUpdate(BaseSchema):
    """Update corporate subscription request."""
    company_name: Optional[str] = None
    employee_limit: Optional[int] = None
    discount_percentage: Optional[Decimal] = None
    custom_price: Optional[Decimal] = None
    contract_end_date: Optional[date] = None
    auto_renew: Optional[bool] = None
    billing_email: Optional[str] = None
    notes: Optional[str] = None


class CorporateSubscriptionResponse(BaseSchema):
    """Corporate subscription response."""
    id: UUID
    venue_id: UUID
    company_name: str
    billing_contact_id: UUID
    plan_id: UUID
    employee_limit: int
    active_employee_count: int
    discount_percentage: Decimal
    custom_price: Optional[Decimal]
    status: SubscriptionStatus
    contract_start_date: date
    contract_end_date: Optional[date]
    auto_renew: bool
    billing_email: Optional[str]
    employees: List[CorporateEmployeeResponse] = []
    created_at: datetime


class CorporateSubscriptionListResponse(BaseSchema):
    """List of corporate subscriptions response."""
    subscriptions: List[CorporateSubscriptionResponse]
    total: int


# =============================================================================
# REFERRAL SCHEMAS
# =============================================================================

class GenerateReferralRequest(BaseSchema):
    """Generate referral code request."""
    customer_id: UUID
    venue_id: UUID


class ReferralCodeResponse(BaseSchema):
    """Referral code response."""
    referral_code: str
    referrer_customer_id: UUID
    referrer_reward_type: str
    referrer_reward_value: Decimal
    referred_reward_type: str
    referred_reward_value: Decimal
    expires_at: Optional[datetime]


class ApplyReferralRequest(BaseSchema):
    """Apply referral code request."""
    referral_code: str
    referred_customer_id: UUID


class ReferralResponse(BaseSchema):
    """Referral response."""
    id: UUID
    venue_id: UUID
    referrer_customer_id: UUID
    referred_customer_id: Optional[UUID]
    referral_code: str
    referrer_reward_type: str
    referrer_reward_value: Decimal
    referred_reward_type: str
    referred_reward_value: Decimal
    status: ReferralStatus
    referred_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime


class ReferralStatsResponse(BaseSchema):
    """Referral statistics response."""
    total_referrals: int
    completed_referrals: int
    pending_referrals: int
    total_rewards_earned: Decimal
    referrals: List[ReferralResponse] = []


# =============================================================================
# ANALYTICS SCHEMAS
# =============================================================================

class MRRAnalytics(BaseSchema):
    """Monthly Recurring Revenue analytics."""
    total_mrr: Decimal
    mrr_change: Decimal
    mrr_change_percentage: Decimal
    new_mrr: Decimal
    churned_mrr: Decimal
    expansion_mrr: Decimal
    active_subscriptions: int
    period_start: date
    period_end: date


class ChurnAnalytics(BaseSchema):
    """Churn analytics."""
    churn_rate: Decimal
    churned_subscriptions: int
    at_risk_subscriptions: int
    retained_subscriptions: int
    churn_reasons: Dict[str, int]
    period_start: date
    period_end: date


class LTVAnalytics(BaseSchema):
    """Lifetime Value analytics."""
    average_ltv: Decimal
    ltv_by_tier: Dict[str, Decimal]
    ltv_trend: str
    customer_count: int
    period_start: date
    period_end: date


class MembershipAnalytics(BaseSchema):
    """Overall membership analytics."""
    total_members: int
    active_members: int
    new_members_this_month: int
    members_by_tier: Dict[str, int]
    loyalty_points_issued: int
    loyalty_points_redeemed: int
    rewards_redeemed: int
    mrr: Decimal
    arr: Decimal


# Forward references
SubscriptionDetailResponse.model_rebuild()
