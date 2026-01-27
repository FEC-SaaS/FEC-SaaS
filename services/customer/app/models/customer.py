"""
=============================================================================
FILE: models/customer.py
PURPOSE: SQLAlchemy models for customer management (GuestIQ)
=============================================================================

Core database models for the Customer Service:
- Customer: Customer profiles (B2C and B2B)
- CustomerFamily: Family groupings
- CustomerFamilyMember: Family member relationships
- CustomerVisit: Visit history tracking
- CustomerActivity: Activity tracking within visits
- CustomerSegment: Customer segmentation (VIP, Premium, etc.)
- CustomerLTV: Lifetime value calculations
- CustomerChurnRisk: Churn risk scoring
- CustomerPreference: Customer preferences
- CustomerNextVisitPrediction: Visit prediction data
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
    Enum,
    ForeignKey,
    UniqueConstraint,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# =============================================================================
# ENUMS
# =============================================================================


class CustomerType(str, enum.Enum):
    """Customer types."""
    B2C = "b2c"  # Individual consumer
    B2B = "b2b"  # Business/corporate


class SegmentType(str, enum.Enum):
    """Customer segment types."""
    VIP = "vip"
    PREMIUM = "premium"
    STANDARD = "standard"
    AT_RISK = "at_risk"
    NEW = "new"
    CHURNED = "churned"
    INACTIVE = "inactive"


class RiskLevel(str, enum.Enum):
    """Churn risk levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActivityType(str, enum.Enum):
    """Customer activity types."""
    BOWLING = "bowling"
    ARCADE = "arcade"
    FOOD = "food"
    BEVERAGE = "beverage"
    MINI_GOLF = "mini_golf"
    LASER_TAG = "laser_tag"
    PARTY = "party"
    MERCHANDISE = "merchandise"
    OTHER = "other"


class RelationshipType(str, enum.Enum):
    """Family relationship types."""
    PARENT = "parent"
    CHILD = "child"
    SPOUSE = "spouse"
    SIBLING = "sibling"
    GRANDPARENT = "grandparent"
    OTHER = "other"


class Gender(str, enum.Enum):
    """Gender options."""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class VisitSource(str, enum.Enum):
    """Visit source tracking."""
    WALK_IN = "walk_in"
    RESERVATION = "reservation"
    PARTY_BOOKING = "party_booking"
    CORPORATE_EVENT = "corporate_event"
    MEMBERSHIP = "membership"
    PROMOTION = "promotion"
    REFERRAL = "referral"
    OTHER = "other"


# =============================================================================
# MODELS
# =============================================================================


class Customer(Base):
    """
    Customer profiles.

    Stores both B2C (individual) and B2B (corporate) customer information.
    Central entity for all customer-related data.
    """
    __tablename__ = "customers"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Personal information
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    gender: Mapped[Optional[Gender]] = mapped_column(Enum(Gender))

    # Customer type
    customer_type: Mapped[CustomerType] = mapped_column(
        Enum(CustomerType),
        default=CustomerType.B2C,
        nullable=False,
    )

    # B2B specific fields
    company_name: Mapped[Optional[str]] = mapped_column(String(255))
    job_title: Mapped[Optional[str]] = mapped_column(String(100))

    # Address
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(100))
    postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(100), default="USA")

    # Marketing preferences
    marketing_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    sms_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    email_opt_in: Mapped[bool] = mapped_column(Boolean, default=True)

    # Notes and metadata
    notes: Mapped[Optional[str]] = mapped_column(Text)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSONB, default=list)
    meta_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Source tracking
    acquisition_source: Mapped[Optional[str]] = mapped_column(String(100))
    acquisition_campaign: Mapped[Optional[str]] = mapped_column(String(100))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # GDPR
    gdpr_consent_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    gdpr_data_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    families: Mapped[List["CustomerFamilyMember"]] = relationship(
        "CustomerFamilyMember",
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    visits: Mapped[List["CustomerVisit"]] = relationship(
        "CustomerVisit",
        back_populates="customer",
        cascade="all, delete-orphan",
        order_by="desc(CustomerVisit.check_in_time)",
    )
    segments: Mapped[List["CustomerSegment"]] = relationship(
        "CustomerSegment",
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    ltv: Mapped[Optional["CustomerLTV"]] = relationship(
        "CustomerLTV",
        back_populates="customer",
        uselist=False,
        cascade="all, delete-orphan",
    )
    churn_risk: Mapped[Optional["CustomerChurnRisk"]] = relationship(
        "CustomerChurnRisk",
        back_populates="customer",
        uselist=False,
        cascade="all, delete-orphan",
    )
    preferences: Mapped[List["CustomerPreference"]] = relationship(
        "CustomerPreference",
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    next_visit_prediction: Mapped[Optional["CustomerNextVisitPrediction"]] = relationship(
        "CustomerNextVisitPrediction",
        back_populates="customer",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("venue_id", "email", name="uq_customer_venue_email"),
        UniqueConstraint("venue_id", "phone", name="uq_customer_venue_phone"),
        Index("idx_customers_venue_active", "venue_id", "is_active"),
        Index("idx_customers_name", "first_name", "last_name"),
        Index("idx_customers_dob", "date_of_birth"),
    )

    @property
    def full_name(self) -> str:
        """Return customer's full name."""
        return f"{self.first_name} {self.last_name}"


class CustomerFamily(Base):
    """
    Customer family groupings.

    Groups related customers for family tracking and promotions.
    """
    __tablename__ = "customer_families"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    family_name: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    primary_customer: Mapped["Customer"] = relationship("Customer")
    members: Mapped[List["CustomerFamilyMember"]] = relationship(
        "CustomerFamilyMember",
        back_populates="family",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_family_venue", "venue_id"),
    )


class CustomerFamilyMember(Base):
    """
    Family member junction table.

    Links customers to families with relationship type.
    """
    __tablename__ = "customer_family_members"

    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_families.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[RelationshipType] = mapped_column(
        Enum(RelationshipType),
        default=RelationshipType.OTHER,
        nullable=False,
    )

    # Relationships
    family: Mapped["CustomerFamily"] = relationship(
        "CustomerFamily",
        back_populates="members",
    )
    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="families",
    )

    __table_args__ = (
        UniqueConstraint("family_id", "customer_id", name="uq_family_customer"),
    )


class CustomerVisit(Base):
    """
    Customer visit tracking.

    Records each visit with check-in/out times, spending, and source.
    """
    __tablename__ = "customer_visits"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Timing
    check_in_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    check_out_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Spending
    total_spend: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0.00"),
    )

    # Party details
    guest_count: Mapped[int] = mapped_column(Integer, default=1)
    child_count: Mapped[int] = mapped_column(Integer, default=0)
    adult_count: Mapped[int] = mapped_column(Integer, default=1)

    # Source
    source: Mapped[VisitSource] = mapped_column(
        Enum(VisitSource),
        default=VisitSource.WALK_IN,
        nullable=False,
    )

    # Reference IDs
    booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))

    # Satisfaction
    satisfaction_score: Mapped[Optional[int]] = mapped_column(Integer)  # 1-10
    feedback: Mapped[Optional[str]] = mapped_column(Text)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="visits",
    )
    activities: Mapped[List["CustomerActivity"]] = relationship(
        "CustomerActivity",
        back_populates="visit",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_visits_customer_time", "customer_id", "check_in_time"),
        Index("idx_visits_venue_time", "venue_id", "check_in_time"),
        CheckConstraint("satisfaction_score IS NULL OR (satisfaction_score >= 1 AND satisfaction_score <= 10)",
                       name="ck_satisfaction_range"),
    )

    @property
    def duration_minutes(self) -> Optional[int]:
        """Calculate visit duration in minutes."""
        if self.check_out_time:
            delta = self.check_out_time - self.check_in_time
            return int(delta.total_seconds() / 60)
        return None


class CustomerActivity(Base):
    """
    Customer activity tracking within visits.

    Detailed breakdown of activities during a visit.
    """
    __tablename__ = "customer_activities"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Activity details
    activity_type: Mapped[ActivityType] = mapped_column(
        Enum(ActivityType),
        nullable=False,
        index=True,
    )
    activity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    activity_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Timing
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)

    # Spending
    amount_spent: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0.00"),
    )

    # Satisfaction
    satisfaction_score: Mapped[Optional[int]] = mapped_column(Integer)  # 1-10

    # Relationships
    visit: Mapped["CustomerVisit"] = relationship(
        "CustomerVisit",
        back_populates="activities",
    )

    __table_args__ = (
        CheckConstraint("satisfaction_score IS NULL OR (satisfaction_score >= 1 AND satisfaction_score <= 10)",
                       name="ck_activity_satisfaction_range"),
    )


class CustomerSegment(Base):
    """
    Customer segmentation.

    Assigns customers to segments for targeted marketing and analysis.
    """
    __tablename__ = "customer_segments"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Segment details
    segment_type: Mapped[SegmentType] = mapped_column(
        Enum(SegmentType),
        nullable=False,
        index=True,
    )
    score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
    )

    # Validity
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Calculation details
    calculation_factors: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relationships
    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="segments",
    )

    __table_args__ = (
        Index("idx_segments_customer_type", "customer_id", "segment_type"),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_segment_score_range"),
    )


class CustomerLTV(Base):
    """
    Customer lifetime value calculations.

    Stores calculated LTV and related metrics.
    """
    __tablename__ = "customer_ltv"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # LTV metrics
    calculated_ltv: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    visit_frequency: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
    )  # Visits per month
    avg_spend: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0.00"),
    )  # Per visit
    expected_lifespan_months: Mapped[int] = mapped_column(Integer, default=12)

    # Totals
    total_visits: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
    )

    # Timestamps
    first_visit_date: Mapped[Optional[date]] = mapped_column(Date)
    last_visit_date: Mapped[Optional[date]] = mapped_column(Date)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        onupdate="now()",
    )

    # Calculation details
    calculation_details: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relationships
    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="ltv",
    )


class CustomerChurnRisk(Base):
    """
    Customer churn risk scoring.

    Real-time churn prediction and risk factors.
    """
    __tablename__ = "customer_churn_risk"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Risk metrics
    risk_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )  # 0-100, higher = more risk
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel),
        nullable=False,
        index=True,
    )

    # Contributing factors
    days_since_last_visit: Mapped[int] = mapped_column(Integer, default=0)
    visit_frequency_trend: Mapped[Optional[str]] = mapped_column(String(20))  # increasing, decreasing, stable
    spend_trend: Mapped[Optional[str]] = mapped_column(String(20))
    factors_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Prediction
    predicted_churn_date: Mapped[Optional[date]] = mapped_column(Date)
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
    )

    # Timestamps
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="churn_risk",
    )

    __table_args__ = (
        Index("idx_churn_risk_level", "risk_level"),
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="ck_churn_score_range"),
    )


class CustomerPreference(Base):
    """
    Customer preferences and learned behaviors.

    Stores detected and stated preferences for personalization.
    """
    __tablename__ = "customer_preferences"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Preference details
    preference_type: Mapped[str] = mapped_column(String(50), nullable=False)
    preference_value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("50.00"),
    )  # 0-100

    # Source
    is_stated: Mapped[bool] = mapped_column(Boolean, default=False)  # True if customer stated
    is_inferred: Mapped[bool] = mapped_column(Boolean, default=True)  # True if system inferred

    # Metadata
    source_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relationships
    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="preferences",
    )

    __table_args__ = (
        UniqueConstraint("customer_id", "preference_type", "preference_value",
                        name="uq_customer_preference"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 100",
                       name="ck_preference_confidence_range"),
    )


class CustomerNextVisitPrediction(Base):
    """
    Next visit prediction data.

    AI-generated predictions for when customer will visit next.
    """
    __tablename__ = "customer_next_visit_predictions"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Prediction
    predicted_date: Mapped[date] = mapped_column(Date, nullable=False)
    predicted_day_of_week: Mapped[Optional[int]] = mapped_column(Integer)  # 0-6
    predicted_time_of_day: Mapped[Optional[str]] = mapped_column(String(20))  # morning, afternoon, evening

    # Confidence
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("50.00"),
    )  # 0-100

    # Model details
    factors_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    model_version: Mapped[Optional[str]] = mapped_column(String(50))

    # Relationships
    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="next_visit_prediction",
    )

    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 100",
                       name="ck_prediction_confidence_range"),
    )
