import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BOOLEAN,
    DECIMAL,
    INTEGER,
    JSON,
    TIMESTAMP,
    Column,
    Enum,
    ForeignKey,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


# =============================================================================
# Enums for Industry-Leading Features
# =============================================================================

import enum


class LoyaltyTier(str, enum.Enum):
    """Loyalty tier progression system (from Intercard feature)."""
    BRONZE = "BRONZE"
    SILVER = "SILVER"
    GOLD = "GOLD"
    PLATINUM = "PLATINUM"


class MembershipStatus(str, enum.Enum):
    """Membership status (from Omnify feature)."""
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class FamilyRole(str, enum.Enum):
    """Role within a family group (from Embed/Sacoa features)."""
    PARENT = "PARENT"
    GUARDIAN = "GUARDIAN"
    CHILD = "CHILD"
    DEPENDENT = "DEPENDENT"


# =============================================================================
# Core User Model (Enhanced)
# =============================================================================


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=False, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    date_of_birth = Column(TIMESTAMP, nullable=True)  # For birthday rewards
    email_verified = Column(BOOLEAN, default=False)
    phone_verified = Column(BOOLEAN, default=False)
    facial_recognition_consent = Column(BOOLEAN, default=False)
    facial_recognition_enrolled = Column(BOOLEAN, default=False)

    # Industry-leading: Multi-language support (from Sacoa)
    preferred_language = Column(String(10), default="en")
    preferred_currency = Column(String(3), default="USD")  # From Oracle MICROS

    # Industry-leading: Loyalty tier (from Intercard)
    loyalty_tier = Column(
        Enum(LoyaltyTier, name="loyalty_tier_enum"),
        default=LoyaltyTier.BRONZE
    )
    loyalty_points = Column(INTEGER, default=0)
    lifetime_points = Column(INTEGER, default=0)

    # Industry-leading: Accessibility (from Sacoa)
    accessibility_needs = Column(JSON, nullable=True)  # {visual: bool, audio: bool, motor: bool}

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(TIMESTAMP, nullable=True)

    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all,delete")
    venue_roles = relationship(
        "UserVenueRole", back_populates="user", cascade="all,delete-orphan"
    )
    privacy_consents = relationship(
        "PrivacyConsent", back_populates="user", cascade="all,delete-orphan"
    )
    # Industry-leading relationships
    family_memberships = relationship(
        "FamilyMember", back_populates="user", foreign_keys="FamilyMember.user_id",
        cascade="all,delete-orphan"
    )
    parental_controls = relationship(
        "ParentalControl", back_populates="parent", foreign_keys="ParentalControl.parent_id",
        cascade="all,delete-orphan"
    )
    memberships = relationship(
        "Membership", back_populates="user", cascade="all,delete-orphan"
    )
    preferences = relationship(
        "UserPreference", back_populates="user", cascade="all,delete-orphan"
    )


class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    permissions = relationship(
        "RolePermission", back_populates="role", cascade="all,delete-orphan"
    )


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    resource = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)
    description = Column(String, nullable=True)

    roles = relationship(
        "RolePermission", back_populates="permission", cascade="all,delete-orphan"
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(
        UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )

    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="roles")


class UserVenueRole(Base):
    __tablename__ = "user_venue_roles"
    __table_args__ = (UniqueConstraint("user_id", "venue_id", name="uq_user_venue"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    venue_id = Column(UUID(as_uuid=True), nullable=False)  # FK to venues.id in venue service
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(TIMESTAMP, default=datetime.utcnow)

    user = relationship("User", back_populates="venue_roles")
    role = relationship("Role")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(500), nullable=False, index=True)
    refresh_token = Column(String(500), nullable=False)
    expires_at = Column(TIMESTAMP, nullable=False)
    device_info = Column(JSON, nullable=True)
    ip_address = Column(INET, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")


class PrivacyConsent(Base):
    __tablename__ = "privacy_consents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    consent_type = Column(String(50), nullable=False)
    granted = Column(BOOLEAN, default=False)
    granted_at = Column(TIMESTAMP, nullable=True)
    revoked_at = Column(TIMESTAMP, nullable=True)
    consent_metadata = Column(JSON, nullable=True)  # renamed from 'metadata' (reserved)

    user = relationship("User", back_populates="privacy_consents")


# =============================================================================
# Industry-Leading Feature: Family Account Linking (from Embed/Sacoa)
# =============================================================================


class FamilyGroup(Base):
    """Family group for linking related accounts."""
    __tablename__ = "family_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)  # e.g., "The Smith Family"
    primary_contact_id = Column(UUID(as_uuid=True), nullable=False)  # Main account holder
    shared_rewards_enabled = Column(BOOLEAN, default=False)  # Share loyalty points
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    members = relationship("FamilyMember", back_populates="family", cascade="all,delete-orphan")


class FamilyMember(Base):
    """Links users to family groups with specific roles."""
    __tablename__ = "family_members"
    __table_args__ = (UniqueConstraint("family_id", "user_id", name="uq_family_user"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), ForeignKey("family_groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    family_role = Column(
        Enum(FamilyRole, name="family_role_enum"),
        default=FamilyRole.DEPENDENT
    )
    nickname = Column(String(50), nullable=True)  # e.g., "Dad", "Junior"
    can_manage_family = Column(BOOLEAN, default=False)  # Can add/remove members
    joined_at = Column(TIMESTAMP, default=datetime.utcnow)

    family = relationship("FamilyGroup", back_populates="members")
    user = relationship("User", back_populates="family_memberships")


# =============================================================================
# Industry-Leading Feature: Parental Controls (from Embed)
# =============================================================================


class ParentalControl(Base):
    """Parental controls for child accounts (spending limits, restrictions)."""
    __tablename__ = "parental_controls"
    __table_args__ = (UniqueConstraint("parent_id", "child_id", name="uq_parent_child"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    child_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Spending controls
    daily_spend_limit = Column(DECIMAL(10, 2), nullable=True)  # Max spend per day
    hourly_spend_limit = Column(DECIMAL(10, 2), nullable=True)  # Max spend per hour
    total_balance_limit = Column(DECIMAL(10, 2), nullable=True)  # Max card balance

    # Time controls
    allowed_play_start = Column(Time, nullable=True)  # e.g., 10:00 AM
    allowed_play_end = Column(Time, nullable=True)  # e.g., 8:00 PM
    blackout_dates = Column(JSON, nullable=True)  # List of dates when play is blocked

    # Content controls
    restricted_game_types = Column(JSON, nullable=True)  # e.g., ["gambling", "violent"]
    age_restriction_override = Column(BOOLEAN, default=False)

    # Monitoring
    activity_notifications = Column(BOOLEAN, default=True)  # Notify parent of activity
    low_balance_alerts = Column(BOOLEAN, default=True)  # Alert when balance is low
    spend_alerts = Column(BOOLEAN, default=True)  # Alert on each purchase

    is_active = Column(BOOLEAN, default=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = relationship("User", back_populates="parental_controls", foreign_keys=[parent_id])
    child = relationship("User", foreign_keys=[child_id])


# =============================================================================
# Industry-Leading Feature: Membership System (from Omnify)
# =============================================================================


class MembershipPlan(Base):
    """Membership plans available for purchase."""
    __tablename__ = "membership_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id = Column(UUID(as_uuid=True), nullable=True)  # NULL = available at all venues
    name = Column(String(100), nullable=False)
    description = Column(String, nullable=True)
    plan_type = Column(String(50), nullable=False)  # INDIVIDUAL, FAMILY, CORPORATE
    billing_period = Column(String(20), nullable=False)  # MONTHLY, ANNUAL, PAY_AS_YOU_GO
    price = Column(DECIMAL(10, 2), nullable=False)

    # Benefits
    free_games_per_period = Column(INTEGER, default=0)
    discount_percentage = Column(DECIMAL(5, 2), default=0)
    priority_booking = Column(BOOLEAN, default=False)
    guest_passes_per_period = Column(INTEGER, default=0)
    bonus_points_multiplier = Column(DECIMAL(3, 2), default=1.0)

    # Restrictions
    max_freezes_per_year = Column(INTEGER, default=2)
    freeze_duration_days = Column(INTEGER, default=30)
    min_commitment_months = Column(INTEGER, default=0)

    is_active = Column(BOOLEAN, default=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)


class Membership(Base):
    """User membership subscriptions."""
    __tablename__ = "memberships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("membership_plans.id"), nullable=False)
    venue_id = Column(UUID(as_uuid=True), nullable=True)  # For venue-specific memberships

    status = Column(
        Enum(MembershipStatus, name="membership_status_enum"),
        default=MembershipStatus.ACTIVE
    )

    # Dates
    start_date = Column(TIMESTAMP, nullable=False)
    end_date = Column(TIMESTAMP, nullable=True)  # NULL for auto-renewing
    next_billing_date = Column(TIMESTAMP, nullable=True)

    # Freeze tracking (from Omnify)
    freeze_start_date = Column(TIMESTAMP, nullable=True)
    freeze_end_date = Column(TIMESTAMP, nullable=True)
    freezes_used_this_year = Column(INTEGER, default=0)

    # Usage tracking
    games_used_this_period = Column(INTEGER, default=0)
    guest_passes_used_this_period = Column(INTEGER, default=0)

    auto_renew = Column(BOOLEAN, default=True)
    cancellation_reason = Column(String, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="memberships")
    plan = relationship("MembershipPlan")


# =============================================================================
# Industry-Leading Feature: User Preferences (Multi-language, Dietary, etc.)
# =============================================================================


class UserPreference(Base):
    """Extended user preferences for personalization."""
    __tablename__ = "user_preferences"
    __table_args__ = (UniqueConstraint("user_id", "preference_key", name="uq_user_preference"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    preference_key = Column(String(100), nullable=False)
    preference_value = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="preferences")


# Common preference keys:
# - "dietary_restrictions": ["vegan", "gluten_free", "nut_allergy"]
# - "notification_preferences": {"email": true, "sms": false, "push": true}
# - "favorite_games": ["bowling", "laser_tag"]
# - "accessibility_settings": {"high_contrast": true, "large_text": true}
# - "marketing_preferences": {"birthday_offers": true, "weekly_deals": false}


# =============================================================================
# Industry-Leading Feature: Lost Card Protection (from Embed)
# =============================================================================


class CardProtection(Base):
    """Lost card protection and balance transfer tracking."""
    __tablename__ = "card_protections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    card_identifier = Column(String(100), nullable=False)  # RFID/card number
    card_type = Column(String(50), default="GAME_CARD")  # GAME_CARD, RFID_WRISTBAND

    is_active = Column(BOOLEAN, default=True)
    is_frozen = Column(BOOLEAN, default=False)  # Temporary freeze
    frozen_at = Column(TIMESTAMP, nullable=True)
    frozen_reason = Column(String, nullable=True)

    # Balance at time of report (for recovery)
    reported_lost_at = Column(TIMESTAMP, nullable=True)
    balance_at_loss = Column(DECIMAL(10, 2), nullable=True)
    balance_transferred = Column(BOOLEAN, default=False)
    transferred_to_card = Column(String(100), nullable=True)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

