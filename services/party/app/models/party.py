"""
=============================================================================
FILE: models/party.py
PURPOSE: SQLAlchemy models for party and event management
=============================================================================

Core database models for the Party & Events Service:
- PartyPackage: Party package configurations and pricing
- PartyAddon: Upsell items (extra time, decorations, etc.)
- PartyPackageAddon: Default addons included in packages
- PartyBooking: Individual party bookings
- PartyBookingAddon: Addons selected for a booking
- CorporateEvent: B2B corporate event bookings
- PartyTimeline: Execution timeline items
- PartyHostAssignment: Staff assignments for parties
"""

import enum
import uuid
from datetime import datetime, date, time
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    String,
    Text,
    Boolean,
    Integer,
    Numeric,
    Date,
    Time,
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


class PackageType(str, enum.Enum):
    """Party package types."""
    BIRTHDAY = "birthday"
    CORPORATE = "corporate"
    HOLIDAY = "holiday"
    CUSTOM = "custom"
    GROUP = "group"
    VIP = "vip"


class AddonType(str, enum.Enum):
    """Party addon types."""
    EXTRA_TIME = "extra_time"
    PREMIUM_FOOD = "premium_food"
    DECORATIONS = "decorations"
    PARTY_FAVORS = "party_favors"
    ENTERTAINMENT = "entertainment"
    PHOTOGRAPHY = "photography"
    CUSTOM = "custom"


class BookingType(str, enum.Enum):
    """Party booking types."""
    BIRTHDAY = "birthday"
    CORPORATE = "corporate"
    HOLIDAY = "holiday"
    PRIVATE = "private"
    GROUP = "group"


class BookingStatus(str, enum.Enum):
    """Party booking status."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DEPOSIT_PAID = "deposit_paid"
    FULLY_PAID = "fully_paid"
    CHECKED_IN = "checked_in"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class CorporateEventType(str, enum.Enum):
    """Corporate event types."""
    TEAM_BUILDING = "team_building"
    HAPPY_HOUR = "happy_hour"
    CONFERENCE = "conference"
    HOLIDAY_PARTY = "holiday_party"
    PRODUCT_LAUNCH = "product_launch"
    CLIENT_ENTERTAINMENT = "client_entertainment"
    PRIVATE_BUYOUT = "private_buyout"


class CorporateEventStatus(str, enum.Enum):
    """Corporate event status."""
    INQUIRY = "inquiry"
    PROPOSAL_SENT = "proposal_sent"
    NEGOTIATING = "negotiating"
    CONFIRMED = "confirmed"
    DEPOSIT_PAID = "deposit_paid"
    FULLY_PAID = "fully_paid"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    LOST = "lost"


class TimelineStatus(str, enum.Enum):
    """Timeline item status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    DELAYED = "delayed"


class HostRole(str, enum.Enum):
    """Party host roles."""
    PRIMARY_HOST = "primary_host"
    ASSISTANT = "assistant"
    FOOD_RUNNER = "food_runner"
    GAME_ATTENDANT = "game_attendant"
    PHOTOGRAPHER = "photographer"


# =============================================================================
# MODELS
# =============================================================================


class PartyPackage(Base):
    """
    Party package configurations.

    Defines available party packages with pricing, duration, and included features.
    """
    __tablename__ = "party_packages"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    package_name: Mapped[str] = mapped_column(String(255), nullable=False)
    package_type: Mapped[PackageType] = mapped_column(
        Enum(PackageType),
        default=PackageType.BIRTHDAY,
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Guest limits
    min_guests: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    max_guests: Mapped[int] = mapped_column(Integer, nullable=False, default=25)

    # Pricing
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    price_per_additional_guest: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    deposit_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("25.00"),
        nullable=False,
    )

    # Duration
    duration_minutes: Mapped[int] = mapped_column(Integer, default=120, nullable=False)

    # Inclusions
    includes_food: Mapped[bool] = mapped_column(Boolean, default=True)
    includes_drinks: Mapped[bool] = mapped_column(Boolean, default=True)
    includes_cake: Mapped[bool] = mapped_column(Boolean, default=False)
    includes_decorations: Mapped[bool] = mapped_column(Boolean, default=True)
    includes_invitations: Mapped[bool] = mapped_column(Boolean, default=False)
    included_activities: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Display
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Metadata
    meta_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relationships
    default_addons: Mapped[List["PartyPackageAddon"]] = relationship(
        "PartyPackageAddon",
        back_populates="package",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    bookings: Mapped[List["PartyBooking"]] = relationship(
        "PartyBooking",
        back_populates="package",
        lazy="dynamic",
    )

    __table_args__ = (
        UniqueConstraint("venue_id", "package_name", name="uq_venue_package_name"),
        Index("idx_packages_venue_active", "venue_id", "is_active"),
        Index("idx_packages_type_active", "package_type", "is_active"),
        CheckConstraint("min_guests > 0", name="ck_min_guests_positive"),
        CheckConstraint("max_guests >= min_guests", name="ck_max_gte_min_guests"),
        CheckConstraint("base_price >= 0", name="ck_base_price_positive"),
        CheckConstraint("duration_minutes > 0", name="ck_duration_positive"),
    )


class PartyAddon(Base):
    """
    Party add-ons (upsells).

    Additional items that can be added to party bookings.
    """
    __tablename__ = "party_addons"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    addon_name: Mapped[str] = mapped_column(String(255), nullable=False)
    addon_type: Mapped[AddonType] = mapped_column(
        Enum(AddonType),
        default=AddonType.CUSTOM,
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Pricing
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    price_type: Mapped[str] = mapped_column(
        String(20),
        default="fixed",  # fixed, per_guest, per_hour
        nullable=False,
    )

    # Constraints
    min_quantity: Mapped[int] = mapped_column(Integer, default=1)
    max_quantity: Mapped[Optional[int]] = mapped_column(Integer)
    requires_advance_notice_hours: Mapped[int] = mapped_column(Integer, default=0)

    # Display
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    image_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # AI upsell settings
    upsell_priority: Mapped[int] = mapped_column(Integer, default=0)
    upsell_message: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("venue_id", "addon_name", name="uq_venue_addon_name"),
        Index("idx_addons_venue_active", "venue_id", "is_active"),
        CheckConstraint("price >= 0", name="ck_addon_price_positive"),
    )


class PartyPackageAddon(Base):
    """
    Default addons included in packages.

    Junction table for packages and their default add-ons.
    """
    __tablename__ = "party_package_addons"

    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("party_packages.id", ondelete="CASCADE"),
        nullable=False,
    )
    addon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("party_addons.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    is_included_free: Mapped[bool] = mapped_column(Boolean, default=True)
    discount_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
    )

    # Relationships
    package: Mapped["PartyPackage"] = relationship(
        "PartyPackage",
        back_populates="default_addons",
    )
    addon: Mapped["PartyAddon"] = relationship("PartyAddon")

    __table_args__ = (
        UniqueConstraint("package_id", "addon_id", name="uq_package_addon"),
    )


class PartyBooking(Base):
    """
    Individual party bookings.

    Stores all party reservation details including guest info,
    pricing, and status tracking.
    """
    __tablename__ = "party_bookings"

    # References
    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("party_packages.id"),
        nullable=False,
    )

    # Booking details
    booking_type: Mapped[BookingType] = mapped_column(
        Enum(BookingType),
        default=BookingType.BIRTHDAY,
        nullable=False,
        index=True,
    )
    booking_reference: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    # Schedule
    party_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    # Guest info
    guest_count: Mapped[int] = mapped_column(Integer, nullable=False)
    child_count: Mapped[Optional[int]] = mapped_column(Integer)
    adult_count: Mapped[Optional[int]] = mapped_column(Integer)

    # Guest of honor
    guest_of_honor_name: Mapped[Optional[str]] = mapped_column(String(255))
    guest_of_honor_age: Mapped[Optional[int]] = mapped_column(Integer)

    # Contact info
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(20), nullable=False)

    # Pricing
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    addons_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Payments
    deposit_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    deposit_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    deposit_paid_at: Mapped[Optional[datetime]] = mapped_column()
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    balance_due: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Status
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus),
        default=BookingStatus.PENDING,
        nullable=False,
        index=True,
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column()
    checked_in_at: Mapped[Optional[datetime]] = mapped_column()
    completed_at: Mapped[Optional[datetime]] = mapped_column()
    cancelled_at: Mapped[Optional[datetime]] = mapped_column()
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Special requests
    special_requests: Mapped[Optional[str]] = mapped_column(Text)
    dietary_restrictions: Mapped[Optional[str]] = mapped_column(Text)
    allergy_info: Mapped[Optional[str]] = mapped_column(Text)

    # Room/area assignment
    assigned_area: Mapped[Optional[str]] = mapped_column(String(100))

    # Internal notes
    internal_notes: Mapped[Optional[str]] = mapped_column(Text)

    # AI/analytics
    upsell_suggestions_shown: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    upsell_suggestions_accepted: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    ai_insights: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Source tracking
    booking_source: Mapped[Optional[str]] = mapped_column(String(50))  # web, phone, walk-in, etc.
    campaign_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column()

    # Relationships
    package: Mapped["PartyPackage"] = relationship(
        "PartyPackage",
        back_populates="bookings",
    )
    addons: Mapped[List["PartyBookingAddon"]] = relationship(
        "PartyBookingAddon",
        back_populates="booking",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    timeline: Mapped[List["PartyTimeline"]] = relationship(
        "PartyTimeline",
        back_populates="booking",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    host_assignments: Mapped[List["PartyHostAssignment"]] = relationship(
        "PartyHostAssignment",
        back_populates="booking",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_bookings_venue_date", "venue_id", "party_date"),
        Index("idx_bookings_customer", "customer_id"),
        Index("idx_bookings_status_date", "status", "party_date"),
        Index("idx_bookings_venue_status", "venue_id", "status"),
        CheckConstraint("guest_count > 0", name="ck_guest_count_positive"),
        CheckConstraint("total_price >= 0", name="ck_total_price_positive"),
    )


class PartyBookingAddon(Base):
    """
    Addons selected for a specific booking.

    Junction table between bookings and addons with quantity and pricing.
    """
    __tablename__ = "party_booking_addons"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("party_bookings.id", ondelete="CASCADE"),
        nullable=False,
    )
    addon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("party_addons.id"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Was this an AI-suggested upsell?
    was_upsell_suggestion: Mapped[bool] = mapped_column(Boolean, default=False)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    booking: Mapped["PartyBooking"] = relationship(
        "PartyBooking",
        back_populates="addons",
    )
    addon: Mapped["PartyAddon"] = relationship("PartyAddon")

    __table_args__ = (
        UniqueConstraint("booking_id", "addon_id", name="uq_booking_addon"),
        CheckConstraint("quantity > 0", name="ck_addon_quantity_positive"),
    )


class CorporateEvent(Base):
    """
    Corporate event bookings (B2B).

    Handles larger, more complex corporate bookings with
    proposals, negotiations, and custom requirements.
    """
    __tablename__ = "corporate_events"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Company info
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_industry: Mapped[Optional[str]] = mapped_column(String(100))
    company_size: Mapped[Optional[str]] = mapped_column(String(50))  # SMB, Enterprise, etc.

    # Contact info
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20))
    contact_title: Mapped[Optional[str]] = mapped_column(String(100))

    # Event details
    event_type: Mapped[CorporateEventType] = mapped_column(
        Enum(CorporateEventType),
        nullable=False,
        index=True,
    )
    event_name: Mapped[Optional[str]] = mapped_column(String(255))
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    # Attendance
    attendee_count: Mapped[int] = mapped_column(Integer, nullable=False)
    min_attendees: Mapped[Optional[int]] = mapped_column(Integer)
    max_attendees: Mapped[Optional[int]] = mapped_column(Integer)

    # Budget and pricing
    estimated_budget: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    quoted_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    final_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    deposit_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    deposit_paid: Mapped[bool] = mapped_column(Boolean, default=False)

    # Status
    status: Mapped[CorporateEventStatus] = mapped_column(
        Enum(CorporateEventStatus),
        default=CorporateEventStatus.INQUIRY,
        nullable=False,
        index=True,
    )

    # Lead scoring (AI-generated)
    lead_score: Mapped[Optional[int]] = mapped_column(Integer)  # 0-100
    lead_score_factors: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Requirements
    special_requests: Mapped[Optional[str]] = mapped_column(Text)
    catering_requirements: Mapped[Optional[str]] = mapped_column(Text)
    beverage_requirements: Mapped[Optional[str]] = mapped_column(Text)
    av_requirements: Mapped[Optional[str]] = mapped_column(Text)
    space_requirements: Mapped[Optional[str]] = mapped_column(Text)

    # Proposal tracking
    proposal_sent_at: Mapped[Optional[datetime]] = mapped_column()
    proposal_expires_at: Mapped[Optional[datetime]] = mapped_column()
    proposal_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Follow-up tracking
    last_contact_date: Mapped[Optional[datetime]] = mapped_column()
    next_follow_up_date: Mapped[Optional[datetime]] = mapped_column()
    follow_up_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Assigned sales rep
    assigned_rep_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))

    # Outcome tracking
    confirmed_at: Mapped[Optional[datetime]] = mapped_column()
    completed_at: Mapped[Optional[datetime]] = mapped_column()
    lost_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Internal notes
    internal_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    __table_args__ = (
        Index("idx_corporate_venue_date", "venue_id", "event_date"),
        Index("idx_corporate_status", "status"),
        Index("idx_corporate_lead_score", "lead_score"),
        CheckConstraint("attendee_count > 0", name="ck_attendee_count_positive"),
        CheckConstraint("lead_score IS NULL OR (lead_score >= 0 AND lead_score <= 100)",
                       name="ck_lead_score_range"),
    )


class PartyTimeline(Base):
    """
    Party execution timeline.

    Defines the scheduled activities and their completion status
    for party execution management.
    """
    __tablename__ = "party_timelines"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("party_bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Timeline item details
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    item_description: Mapped[Optional[str]] = mapped_column(Text)
    item_category: Mapped[Optional[str]] = mapped_column(String(50))  # food, activity, setup, etc.

    # Scheduling
    scheduled_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=15)

    # Execution
    actual_time: Mapped[Optional[time]] = mapped_column(Time)
    status: Mapped[TimelineStatus] = mapped_column(
        Enum(TimelineStatus),
        default=TimelineStatus.PENDING,
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column()
    completed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))

    # Assignment
    assigned_staff_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))

    # Order
    sequence_order: Mapped[int] = mapped_column(Integer, default=0)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text)
    delay_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    booking: Mapped["PartyBooking"] = relationship(
        "PartyBooking",
        back_populates="timeline",
    )

    __table_args__ = (
        Index("idx_timeline_booking_order", "booking_id", "sequence_order"),
    )


class PartyHostAssignment(Base):
    """
    Staff assignments for party hosting.

    Tracks which staff members are assigned to each party
    and their specific roles.
    """
    __tablename__ = "party_host_assignments"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("party_bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    role: Mapped[HostRole] = mapped_column(
        Enum(HostRole),
        default=HostRole.PRIMARY_HOST,
        nullable=False,
    )

    # Schedule
    start_time: Mapped[Optional[time]] = mapped_column(Time)
    end_time: Mapped[Optional[time]] = mapped_column(Time)

    # Status
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    checked_in: Mapped[bool] = mapped_column(Boolean, default=False)
    checked_in_at: Mapped[Optional[datetime]] = mapped_column()

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    booking: Mapped["PartyBooking"] = relationship(
        "PartyBooking",
        back_populates="host_assignments",
    )

    __table_args__ = (
        UniqueConstraint("booking_id", "staff_id", "role", name="uq_booking_staff_role"),
        Index("idx_host_staff_date", "staff_id"),
    )
