"""
=============================================================================
FILE: models/venue.py
PURPOSE: SQLAlchemy models for venue management
=============================================================================

Core database models for the Venue Management Service:
- Venue: Master venue record with location and subscription info
- VenueHours: Regular operating hours per day of week
- VenueSpecialHours: Holiday and special occasion hours
- VenueSetting: Key-value configuration store
- VenueFeature: Feature flags per venue (bowling, arcade, etc.)
- VenueAIConfig: AI service configuration per venue
- VenuePerformance: Daily performance metrics for benchmarking
- VenueContact: Additional contact persons for venue
- VenueImage: Venue photos and media
"""

import enum
import uuid
from datetime import datetime, date, time
from typing import Optional, List

from sqlalchemy import (
    String,
    Text,
    Boolean,
    Integer,
    Float,
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


class VenueStatus(str, enum.Enum):
    """Venue operational status."""
    PENDING = "pending"           # Onboarding not complete
    ACTIVE = "active"             # Fully operational
    INACTIVE = "inactive"         # Temporarily closed
    SUSPENDED = "suspended"       # Payment or compliance issue
    CLOSED = "closed"            # Permanently closed


class SubscriptionTier(str, enum.Enum):
    """Subscription pricing tier."""
    STARTER = "starter"           # $999/month - Basic features
    PRO = "pro"                   # $2,499/month - Advanced features
    ENTERPRISE = "enterprise"     # $4,999/month - All features


class OnboardingStatus(str, enum.Enum):
    """Onboarding workflow status."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"


class SettingType(str, enum.Enum):
    """Type of setting value."""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    JSON = "json"


class FeatureName(str, enum.Enum):
    """Available venue features."""
    BOWLING = "bowling"
    ARCADE = "arcade"
    FOOD_BEVERAGE = "food_beverage"
    MINI_GOLF = "mini_golf"
    LASER_TAG = "laser_tag"
    PARTIES = "parties"
    GO_KARTS = "go_karts"
    BUMPER_CARS = "bumper_cars"
    TRAMPOLINE = "trampoline"
    ESCAPE_ROOM = "escape_room"
    VR_EXPERIENCE = "vr_experience"
    REDEMPTION = "redemption"
    LOYALTY = "loyalty"
    MOBILE_APP = "mobile_app"
    RESERVATIONS = "reservations"
    EVENTS = "events"


class AIServiceName(str, enum.Enum):
    """Available AI services."""
    DYNAMIC_PRICING = "dynamic_pricing"
    SMART_STAFF = "smart_staff"
    CHURN_PREDICTION = "churn_prediction"
    PARTY_FLOW = "party_flow"
    GAME_FLOOR = "game_floor"
    FOOD_WASTE = "food_waste"
    SENTIMENT = "sentiment"
    RECOMMENDATION = "recommendation"


class AIStrategy(str, enum.Enum):
    """AI optimization strategy."""
    AGGRESSIVE = "aggressive"     # Maximize revenue/efficiency
    MODERATE = "moderate"         # Balance cost and experience
    CONSERVATIVE = "conservative" # Prioritize customer satisfaction


class DayOfWeek(int, enum.Enum):
    """Day of week (0 = Sunday, 6 = Saturday)."""
    SUNDAY = 0
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6


class ContactType(str, enum.Enum):
    """Contact person type."""
    OWNER = "owner"
    MANAGER = "manager"
    OPERATIONS = "operations"
    BILLING = "billing"
    TECHNICAL = "technical"
    EMERGENCY = "emergency"


class ImageType(str, enum.Enum):
    """Venue image type."""
    LOGO = "logo"
    COVER = "cover"
    GALLERY = "gallery"
    FLOOR_PLAN = "floor_plan"
    MENU = "menu"


# =============================================================================
# MODELS
# =============================================================================


class Venue(Base):
    """
    Master venue record.

    Contains core information about a venue including location,
    contact details, subscription tier, and operational status.
    """
    __tablename__ = "venues"

    # Basic Information
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    legal_name: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    # Location
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(100), default="USA", nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    timezone: Mapped[str] = mapped_column(String(50), default="America/Chicago", nullable=False)

    # Contact
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[Optional[str]] = mapped_column(String(255))

    # Business
    tax_id: Mapped[Optional[str]] = mapped_column(String(50))
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier),
        default=SubscriptionTier.STARTER,
        nullable=False,
        index=True,
    )
    status: Mapped[VenueStatus] = mapped_column(
        Enum(VenueStatus),
        default=VenueStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Onboarding
    onboarding_status: Mapped[OnboardingStatus] = mapped_column(
        Enum(OnboardingStatus),
        default=OnboardingStatus.NOT_STARTED,
        nullable=False,
    )
    onboarding_started_at: Mapped[Optional[datetime]] = mapped_column()
    onboarding_completed_at: Mapped[Optional[datetime]] = mapped_column()
    go_live_date: Mapped[Optional[date]] = mapped_column(Date)

    # Capacity
    total_capacity: Mapped[Optional[int]] = mapped_column(Integer)
    square_footage: Mapped[Optional[int]] = mapped_column(Integer)

    # Franchise
    franchise_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), index=True)
    is_flagship: Mapped[bool] = mapped_column(Boolean, default=False)

    # Extra Data (note: 'metadata' is reserved in SQLAlchemy)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column()

    # Relationships
    hours: Mapped[List["VenueHours"]] = relationship(
        "VenueHours",
        back_populates="venue",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    special_hours: Mapped[List["VenueSpecialHours"]] = relationship(
        "VenueSpecialHours",
        back_populates="venue",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    settings: Mapped[List["VenueSetting"]] = relationship(
        "VenueSetting",
        back_populates="venue",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    features: Mapped[List["VenueFeature"]] = relationship(
        "VenueFeature",
        back_populates="venue",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    ai_configs: Mapped[List["VenueAIConfig"]] = relationship(
        "VenueAIConfig",
        back_populates="venue",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    performance_records: Mapped[List["VenuePerformance"]] = relationship(
        "VenuePerformance",
        back_populates="venue",
        cascade="all, delete-orphan",
    )
    contacts: Mapped[List["VenueContact"]] = relationship(
        "VenueContact",
        back_populates="venue",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    images: Mapped[List["VenueImage"]] = relationship(
        "VenueImage",
        back_populates="venue",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_venues_city_state", "city", "state"),
        Index("idx_venues_franchise", "franchise_id"),
        Index("idx_venues_status_tier", "status", "subscription_tier"),
    )


class VenueHours(Base):
    """
    Regular operating hours for a venue.

    Stores the standard weekly schedule with open/close times
    for each day of the week.
    """
    __tablename__ = "venue_hours"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Sunday, 6=Saturday
    open_time: Mapped[Optional[time]] = mapped_column(Time)
    close_time: Mapped[Optional[time]] = mapped_column(Time)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_24_hours: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    venue: Mapped["Venue"] = relationship("Venue", back_populates="hours")

    __table_args__ = (
        UniqueConstraint("venue_id", "day_of_week", name="uq_venue_hours_day"),
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="ck_valid_day"),
    )


class VenueSpecialHours(Base):
    """
    Special hours for holidays and special occasions.

    Overrides regular hours for specific dates like holidays,
    special events, or seasonal adjustments.
    """
    __tablename__ = "venue_special_hours"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "Christmas Day"
    open_time: Mapped[Optional[time]] = mapped_column(Time)
    close_time: Mapped[Optional[time]] = mapped_column(Time)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_24_hours: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    venue: Mapped["Venue"] = relationship("Venue", back_populates="special_hours")

    __table_args__ = (
        UniqueConstraint("venue_id", "date", name="uq_venue_special_date"),
    )


class VenueSetting(Base):
    """
    Key-value configuration store for venue settings.

    Flexible storage for venue-specific configuration that can
    vary between venues without schema changes.
    """
    __tablename__ = "venue_settings"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    setting_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    setting_value: Mapped[str] = mapped_column(Text, nullable=False)
    setting_type: Mapped[SettingType] = mapped_column(
        Enum(SettingType),
        default=SettingType.STRING,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(String(255))
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[Optional[str]] = mapped_column(String(50), index=True)

    # Relationships
    venue: Mapped["Venue"] = relationship("Venue", back_populates="settings")

    __table_args__ = (
        UniqueConstraint("venue_id", "setting_key", name="uq_venue_setting_key"),
        Index("idx_venue_settings_category", "venue_id", "category"),
    )


class VenueFeature(Base):
    """
    Feature enablement per venue.

    Controls which features (bowling, arcade, food, etc.) are
    enabled for each venue along with feature-specific configuration.
    """
    __tablename__ = "venue_features"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    enabled_at: Mapped[Optional[datetime]] = mapped_column()
    disabled_at: Mapped[Optional[datetime]] = mapped_column()
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    venue: Mapped["Venue"] = relationship("Venue", back_populates="features")

    __table_args__ = (
        UniqueConstraint("venue_id", "feature_name", name="uq_venue_feature"),
    )


class VenueAIConfig(Base):
    """
    AI service configuration per venue.

    Controls which AI services are enabled for each venue and
    their optimization strategy (aggressive, moderate, conservative).
    """
    __tablename__ = "venue_ai_configs"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ai_service: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    strategy: Mapped[AIStrategy] = mapped_column(
        Enum(AIStrategy),
        default=AIStrategy.MODERATE,
        nullable=False,
    )
    params: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    enabled_at: Mapped[Optional[datetime]] = mapped_column()
    disabled_at: Mapped[Optional[datetime]] = mapped_column()
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    venue: Mapped["Venue"] = relationship("Venue", back_populates="ai_configs")

    __table_args__ = (
        UniqueConstraint("venue_id", "ai_service", name="uq_venue_ai_service"),
    )


class VenuePerformance(Base):
    """
    Daily performance metrics for benchmarking.

    Stores key performance indicators for each venue to enable
    cross-venue comparison and trend analysis.
    """
    __tablename__ = "venue_performance"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Revenue metrics
    revenue: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    revenue_per_guest: Mapped[Optional[float]] = mapped_column(Float)
    transaction_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_transaction: Mapped[Optional[float]] = mapped_column(Float)

    # Customer metrics
    guest_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_customers: Mapped[int] = mapped_column(Integer, default=0)
    returning_customers: Mapped[int] = mapped_column(Integer, default=0)
    party_bookings: Mapped[int] = mapped_column(Integer, default=0)

    # Operational metrics
    labor_hours: Mapped[Optional[float]] = mapped_column(Float)
    labor_cost: Mapped[Optional[float]] = mapped_column(Float)
    labor_cost_percentage: Mapped[Optional[float]] = mapped_column(Float)
    food_cost: Mapped[Optional[float]] = mapped_column(Float)
    food_cost_percentage: Mapped[Optional[float]] = mapped_column(Float)
    food_waste_percentage: Mapped[Optional[float]] = mapped_column(Float)

    # Satisfaction metrics
    nps_score: Mapped[Optional[float]] = mapped_column(Float)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    average_rating: Mapped[Optional[float]] = mapped_column(Float)

    # Capacity metrics
    peak_occupancy: Mapped[Optional[int]] = mapped_column(Integer)
    average_occupancy: Mapped[Optional[float]] = mapped_column(Float)
    capacity_utilization: Mapped[Optional[float]] = mapped_column(Float)

    # Additional metrics as JSON
    metrics: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relationships
    venue: Mapped["Venue"] = relationship("Venue", back_populates="performance_records")

    __table_args__ = (
        UniqueConstraint("venue_id", "date", name="uq_venue_performance_date"),
        Index("idx_venue_performance_date_range", "venue_id", "date"),
    )


class VenueContact(Base):
    """
    Additional contact persons for a venue.

    Stores information about key contacts like managers,
    owners, and emergency contacts.
    """
    __tablename__ = "venue_contacts"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_type: Mapped[ContactType] = mapped_column(
        Enum(ContactType),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    venue: Mapped["Venue"] = relationship("Venue", back_populates="contacts")


class VenueImage(Base):
    """
    Venue photos and media.

    Stores references to venue images including logos,
    cover photos, gallery images, and floor plans.
    """
    __tablename__ = "venue_images"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_type: Mapped[ImageType] = mapped_column(
        Enum(ImageType),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    alt_text: Mapped[Optional[str]] = mapped_column(String(255))
    title: Mapped[Optional[str]] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    venue: Mapped["Venue"] = relationship("Venue", back_populates="images")

    __table_args__ = (
        Index("idx_venue_images_type", "venue_id", "image_type"),
    )
