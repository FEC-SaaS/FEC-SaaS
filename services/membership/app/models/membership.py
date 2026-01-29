"""
=============================================================================
FILE: models/membership.py
PURPOSE: SQLAlchemy models for Membership, Loyalty & Subscription Service
=============================================================================

Database Tables (17 total):
1. membership_tiers - Membership tier definitions
2. subscription_plans - Subscription plan configurations
3. customer_subscriptions - Active customer subscriptions
4. subscription_invoices - Billing invoices
5. subscription_usage_limits - Usage tracking per subscription
6. loyalty_programs - Venue loyalty program settings
7. customer_loyalty_accounts - Customer loyalty balances
8. loyalty_transactions - Points earned/redeemed history
9. rewards_catalog - Available rewards
10. reward_redemptions - Redeemed rewards tracking
11. family_memberships - Family membership groups
12. family_membership_members - Family member links
13. corporate_subscriptions - Corporate/business subscriptions
14. corporate_subscription_employees - Corporate employee links
15. referral_rewards - Referral tracking
16. subscription_pauses - Pause history
17. dunning_attempts - Failed payment retry tracking
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


# =============================================================================
# ENUMS
# =============================================================================

class BillingInterval(str, Enum):
    """Billing interval options."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    WEEKLY = "weekly"


class PlanType(str, Enum):
    """Subscription plan types."""
    MEMBERSHIP = "membership"
    ACTIVITY_PASS = "activity_pass"
    UNLIMITED_PLAY = "unlimited_play"
    VIP = "vip"


class SubscriptionStatus(str, Enum):
    """Subscription statuses."""
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    TRIALING = "trialing"


class InvoiceStatus(str, Enum):
    """Invoice statuses."""
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


class UsageType(str, Enum):
    """Subscription usage types."""
    BOWLING_HOURS = "bowling_hours"
    BOWLING_GAMES = "bowling_games"
    ARCADE_CREDITS = "arcade_credits"
    FOOD_DOLLARS = "food_dollars"
    PARTY_HOURS = "party_hours"
    MINI_GOLF_ROUNDS = "mini_golf_rounds"
    LASER_TAG_GAMES = "laser_tag_games"
    SHOE_RENTALS = "shoe_rentals"
    GUEST_PASSES = "guest_passes"


class UsageResetPeriod(str, Enum):
    """Usage limit reset periods."""
    MONTHLY = "monthly"
    BILLING_CYCLE = "billing_cycle"
    WEEKLY = "weekly"


class LoyaltyTransactionType(str, Enum):
    """Loyalty transaction types."""
    EARNED = "earned"
    REDEEMED = "redeemed"
    EXPIRED = "expired"
    BONUS = "bonus"
    ADJUSTED = "adjusted"
    REFERRAL = "referral"
    SIGNUP = "signup"
    BIRTHDAY = "birthday"


class RewardType(str, Enum):
    """Reward types."""
    DISCOUNT = "discount"
    FREE_ITEM = "free_item"
    CREDIT = "credit"
    EXPERIENCE = "experience"
    MERCHANDISE = "merchandise"
    UPGRADE = "upgrade"


class RedemptionStatus(str, Enum):
    """Reward redemption statuses."""
    PENDING = "pending"
    USED = "used"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ReferralStatus(str, Enum):
    """Referral statuses."""
    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RelationshipType(str, Enum):
    """Family member relationship types."""
    SPOUSE = "spouse"
    CHILD = "child"
    PARENT = "parent"
    SIBLING = "sibling"
    OTHER = "other"


class DunningStatus(str, Enum):
    """Dunning attempt statuses."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# =============================================================================
# MEMBERSHIP & SUBSCRIPTION TABLES
# =============================================================================

class MembershipTier(Base, UUIDMixin, TimestampMixin):
    """Membership tier definitions."""

    __tablename__ = "membership_tiers"

    venue_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    tier_name: Mapped[str] = mapped_column(String(50), nullable=False)
    tier_level: Mapped[int] = mapped_column(Integer, default=1)
    monthly_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    annual_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    setup_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    benefits_description: Mapped[Optional[str]] = mapped_column(Text)
    benefits: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, default=dict)
    max_family_members: Mapped[int] = mapped_column(Integer, default=1)
    points_multiplier: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("1.0"))
    free_guest_passes_monthly: Mapped[int] = mapped_column(Integer, default=0)
    discount_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    priority_booking: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    subscription_plans: Mapped[List["SubscriptionPlan"]] = relationship(
        back_populates="tier", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_membership_tiers_venue_active", "venue_id", "is_active"),
    )


class SubscriptionPlan(Base, UUIDMixin, TimestampMixin):
    """Subscription plan configurations."""

    __tablename__ = "subscription_plans"

    venue_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    tier_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("membership_tiers.id"), nullable=True
    )
    plan_name: Mapped[str] = mapped_column(String(100), nullable=False)
    plan_type: Mapped[PlanType] = mapped_column(String(30), nullable=False)
    billing_interval: Mapped[BillingInterval] = mapped_column(String(20), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    setup_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    trial_days: Mapped[int] = mapped_column(Integer, default=0)
    included_benefits: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, default=dict)
    usage_limits: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, default=dict)
    description: Mapped[Optional[str]] = mapped_column(Text)
    terms_conditions: Mapped[Optional[str]] = mapped_column(Text)
    max_subscribers: Mapped[Optional[int]] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    tier: Mapped[Optional["MembershipTier"]] = relationship(back_populates="subscription_plans")
    subscriptions: Mapped[List["CustomerSubscription"]] = relationship(back_populates="plan")

    __table_args__ = (
        Index("ix_subscription_plans_venue_active", "venue_id", "is_active"),
    )


class CustomerSubscription(Base, UUIDMixin, TimestampMixin):
    """Customer subscription records."""

    __tablename__ = "customer_subscriptions"

    customer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    venue_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    plan_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False
    )
    tier_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("membership_tiers.id")
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        String(20), default=SubscriptionStatus.PENDING
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_period_start: Mapped[Optional[date]] = mapped_column(Date)
    current_period_end: Mapped[Optional[date]] = mapped_column(Date)
    trial_end: Mapped[Optional[date]] = mapped_column(Date)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(255))
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    payment_method_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True))
    processor_subscription_id: Mapped[Optional[str]] = mapped_column(String(255))
    processor_customer_id: Mapped[Optional[str]] = mapped_column(String(255))
    failed_payment_count: Mapped[int] = mapped_column(Integer, default=0)
    last_payment_date: Mapped[Optional[date]] = mapped_column(Date)
    next_billing_date: Mapped[Optional[date]] = mapped_column(Date)
    extra_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB, default=dict)

    # Relationships
    plan: Mapped["SubscriptionPlan"] = relationship(back_populates="subscriptions")
    tier: Mapped[Optional["MembershipTier"]] = relationship()
    invoices: Mapped[List["SubscriptionInvoice"]] = relationship(
        back_populates="subscription", lazy="selectin"
    )
    usage_limits: Mapped[List["SubscriptionUsageLimit"]] = relationship(
        back_populates="subscription", lazy="selectin"
    )
    pauses: Mapped[List["SubscriptionPause"]] = relationship(
        back_populates="subscription", lazy="selectin"
    )
    dunning_attempts: Mapped[List["DunningAttempt"]] = relationship(
        back_populates="subscription", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_customer_subscriptions_status", "status"),
        Index("ix_customer_subscriptions_next_billing", "next_billing_date"),
        Index("ix_customer_subscriptions_customer_venue", "customer_id", "venue_id"),
    )


class SubscriptionInvoice(Base, UUIDMixin, TimestampMixin):
    """Subscription billing invoices."""

    __tablename__ = "subscription_invoices"

    subscription_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customer_subscriptions.id"), nullable=False, index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_due: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    status: Mapped[InvoiceStatus] = mapped_column(String(20), default=InvoiceStatus.DRAFT)
    processor_invoice_id: Mapped[Optional[str]] = mapped_column(String(255))
    payment_method: Mapped[Optional[str]] = mapped_column(String(50))
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_payment_attempt: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)
    line_items: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, default=list)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    subscription: Mapped["CustomerSubscription"] = relationship(back_populates="invoices")
    dunning_attempts: Mapped[List["DunningAttempt"]] = relationship(
        back_populates="invoice", lazy="selectin"
    )


class SubscriptionUsageLimit(Base, UUIDMixin, TimestampMixin):
    """Subscription usage tracking."""

    __tablename__ = "subscription_usage_limits"

    subscription_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customer_subscriptions.id"), nullable=False, index=True
    )
    usage_type: Mapped[UsageType] = mapped_column(String(50), nullable=False)
    included_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    used_quantity: Mapped[int] = mapped_column(Integer, default=0)
    rollover_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    rollover_quantity: Mapped[int] = mapped_column(Integer, default=0)
    reset_period: Mapped[UsageResetPeriod] = mapped_column(
        String(20), default=UsageResetPeriod.BILLING_CYCLE
    )
    last_reset_date: Mapped[Optional[date]] = mapped_column(Date)
    next_reset_date: Mapped[Optional[date]] = mapped_column(Date)

    # Relationships
    subscription: Mapped["CustomerSubscription"] = relationship(back_populates="usage_limits")

    __table_args__ = (
        UniqueConstraint("subscription_id", "usage_type", name="uq_subscription_usage_type"),
    )


class SubscriptionPause(Base, UUIDMixin, TimestampMixin):
    """Subscription pause history."""

    __tablename__ = "subscription_pauses"

    subscription_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customer_subscriptions.id"), nullable=False, index=True
    )
    pause_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    pause_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_resume_date: Mapped[Optional[date]] = mapped_column(Date)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    initiated_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True))

    # Relationships
    subscription: Mapped["CustomerSubscription"] = relationship(back_populates="pauses")


class DunningAttempt(Base, UUIDMixin, TimestampMixin):
    """Failed payment retry tracking."""

    __tablename__ = "dunning_attempts"

    subscription_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customer_subscriptions.id"), nullable=False, index=True
    )
    invoice_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("subscription_invoices.id"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[DunningStatus] = mapped_column(String(20), default=DunningStatus.PENDING)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    processor_response: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)

    # Relationships
    subscription: Mapped["CustomerSubscription"] = relationship(back_populates="dunning_attempts")
    invoice: Mapped["SubscriptionInvoice"] = relationship(back_populates="dunning_attempts")


# =============================================================================
# LOYALTY PROGRAM TABLES
# =============================================================================

class LoyaltyProgram(Base, UUIDMixin, TimestampMixin):
    """Venue loyalty program settings."""

    __tablename__ = "loyalty_programs"

    venue_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, unique=True)
    program_name: Mapped[str] = mapped_column(String(100), nullable=False)
    points_per_dollar: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("1.0"))
    points_expiry_days: Mapped[Optional[int]] = mapped_column(Integer)
    minimum_redemption_points: Mapped[int] = mapped_column(Integer, default=100)
    signup_bonus_points: Mapped[int] = mapped_column(Integer, default=0)
    birthday_bonus_points: Mapped[int] = mapped_column(Integer, default=0)
    referral_bonus_points: Mapped[int] = mapped_column(Integer, default=0)
    terms_conditions: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    accounts: Mapped[List["CustomerLoyaltyAccount"]] = relationship(
        back_populates="program", lazy="selectin"
    )
    rewards: Mapped[List["RewardsCatalog"]] = relationship(
        back_populates="program", lazy="selectin"
    )


class CustomerLoyaltyAccount(Base, UUIDMixin, TimestampMixin):
    """Customer loyalty account balances."""

    __tablename__ = "customer_loyalty_accounts"

    customer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    program_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("loyalty_programs.id"), nullable=False
    )
    points_balance: Mapped[int] = mapped_column(Integer, default=0)
    lifetime_points_earned: Mapped[int] = mapped_column(Integer, default=0)
    lifetime_points_redeemed: Mapped[int] = mapped_column(Integer, default=0)
    tier_multiplier: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("1.0"))
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_earned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_redeemed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    program: Mapped["LoyaltyProgram"] = relationship(back_populates="accounts")
    transactions: Mapped[List["LoyaltyTransaction"]] = relationship(
        back_populates="account", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("customer_id", "program_id", name="uq_customer_program"),
    )


class LoyaltyTransaction(Base, UUIDMixin, TimestampMixin):
    """Loyalty points transaction history."""

    __tablename__ = "loyalty_transactions"

    loyalty_account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customer_loyalty_accounts.id"), nullable=False, index=True
    )
    transaction_type: Mapped[LoyaltyTransactionType] = mapped_column(String(20), nullable=False)
    points_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[Optional[str]] = mapped_column(String(50))
    reference_id: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    expires_at: Mapped[Optional[date]] = mapped_column(Date)
    multiplier_applied: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("1.0"))
    order_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    extra_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB, default=dict)

    # Relationships
    account: Mapped["CustomerLoyaltyAccount"] = relationship(back_populates="transactions")

    __table_args__ = (
        Index("ix_loyalty_transactions_date", "created_at"),
    )


# =============================================================================
# REWARDS TABLES
# =============================================================================

class RewardsCatalog(Base, UUIDMixin, TimestampMixin):
    """Available rewards catalog."""

    __tablename__ = "rewards_catalog"

    venue_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    program_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("loyalty_programs.id")
    )
    reward_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reward_type: Mapped[RewardType] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    points_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    monetary_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    discount_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    quantity_available: Mapped[Optional[int]] = mapped_column(Integer)
    quantity_redeemed: Mapped[int] = mapped_column(Integer, default=0)
    max_redemptions_per_customer: Mapped[Optional[int]] = mapped_column(Integer)
    valid_from: Mapped[Optional[date]] = mapped_column(Date)
    valid_until: Mapped[Optional[date]] = mapped_column(Date)
    applicable_items: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    terms_conditions: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    program: Mapped[Optional["LoyaltyProgram"]] = relationship(back_populates="rewards")
    redemptions: Mapped[List["RewardRedemption"]] = relationship(
        back_populates="reward", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_rewards_catalog_venue_active", "venue_id", "is_active"),
    )


class RewardRedemption(Base, UUIDMixin, TimestampMixin):
    """Reward redemption records."""

    __tablename__ = "reward_redemptions"

    customer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    reward_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("rewards_catalog.id"), nullable=False
    )
    loyalty_account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customer_loyalty_accounts.id"), nullable=False
    )
    points_spent: Mapped[int] = mapped_column(Integer, nullable=False)
    redemption_code: Mapped[str] = mapped_column(String(50), unique=True)
    status: Mapped[RedemptionStatus] = mapped_column(String(20), default=RedemptionStatus.PENDING)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    order_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    reward: Mapped["RewardsCatalog"] = relationship(back_populates="redemptions")

    __table_args__ = (
        Index("ix_reward_redemptions_customer", "customer_id"),
        Index("ix_reward_redemptions_status", "status"),
    )


# =============================================================================
# FAMILY & CORPORATE TABLES
# =============================================================================

class FamilyMembership(Base, UUIDMixin, TimestampMixin):
    """Family membership groups."""

    __tablename__ = "family_memberships"

    primary_customer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    subscription_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customer_subscriptions.id"), nullable=False
    )
    family_name: Mapped[Optional[str]] = mapped_column(String(100))
    max_members: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    members: Mapped[List["FamilyMembershipMember"]] = relationship(
        back_populates="family", cascade="all, delete-orphan", lazy="selectin"
    )


class FamilyMembershipMember(Base, UUIDMixin, TimestampMixin):
    """Family membership member links."""

    __tablename__ = "family_membership_members"

    family_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("family_memberships.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    member_relationship: Mapped[RelationshipType] = mapped_column("relationship", String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    added_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True))

    # Relationships
    family: Mapped["FamilyMembership"] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("family_id", "customer_id", name="uq_family_customer"),
    )


class CorporateSubscription(Base, UUIDMixin, TimestampMixin):
    """Corporate/business subscriptions."""

    __tablename__ = "corporate_subscriptions"

    venue_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    billing_contact_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False
    )
    employee_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    active_employee_count: Mapped[int] = mapped_column(Integer, default=0)
    discount_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    custom_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    status: Mapped[SubscriptionStatus] = mapped_column(String(20), default=SubscriptionStatus.ACTIVE)
    contract_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_end_date: Mapped[Optional[date]] = mapped_column(Date)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    billing_email: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    employees: Mapped[List["CorporateSubscriptionEmployee"]] = relationship(
        back_populates="corporate_subscription", cascade="all, delete-orphan", lazy="selectin"
    )


class CorporateSubscriptionEmployee(Base, UUIDMixin, TimestampMixin):
    """Corporate subscription employee links."""

    __tablename__ = "corporate_subscription_employees"

    corporate_subscription_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("corporate_subscriptions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    customer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    employee_email: Mapped[str] = mapped_column(String(255), nullable=False)
    employee_name: Mapped[Optional[str]] = mapped_column(String(255))
    department: Mapped[Optional[str]] = mapped_column(String(100))
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    corporate_subscription: Mapped["CorporateSubscription"] = relationship(back_populates="employees")

    __table_args__ = (
        UniqueConstraint(
            "corporate_subscription_id", "customer_id", name="uq_corporate_customer"
        ),
    )


# =============================================================================
# REFERRAL TABLES
# =============================================================================

class ReferralReward(Base, UUIDMixin, TimestampMixin):
    """Referral tracking and rewards."""

    __tablename__ = "referral_rewards"

    venue_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    referrer_customer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    referred_customer_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True))
    referral_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    referrer_reward_type: Mapped[str] = mapped_column(String(50), nullable=False)
    referrer_reward_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    referred_reward_type: Mapped[str] = mapped_column(String(50), nullable=False)
    referred_reward_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[ReferralStatus] = mapped_column(String(20), default=ReferralStatus.PENDING)
    referred_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    referrer_rewarded: Mapped[bool] = mapped_column(Boolean, default=False)
    referred_rewarded: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_referral_rewards_referrer", "referrer_customer_id"),
        Index("ix_referral_rewards_code", "referral_code"),
    )
