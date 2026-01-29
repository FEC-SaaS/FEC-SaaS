"""Reservation & Capacity service database models."""

import enum
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import List, Optional

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
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


# ─── Enums ───────────────────────────────────────────────────────────────────

class ReservationType(str, enum.Enum):
    BOWLING = "BOWLING"
    MINI_GOLF = "MINI_GOLF"
    FOOD = "FOOD"
    PARTY = "PARTY"
    MULTI_ACTIVITY = "MULTI_ACTIVITY"


class ReservationStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class BookingChannel(str, enum.Enum):
    PHONE = "PHONE"
    ONLINE = "ONLINE"
    MOBILE_APP = "MOBILE_APP"
    WALK_IN = "WALK_IN"
    KIOSK = "KIOSK"


class ResourceType(str, enum.Enum):
    BOWLING_LANE = "BOWLING_LANE"
    MINI_GOLF_COURSE = "MINI_GOLF_COURSE"
    DINING_TABLE = "DINING_TABLE"
    PARTY_ROOM = "PARTY_ROOM"
    ARCADE_AREA = "ARCADE_AREA"


class WaitlistStatus(str, enum.Enum):
    WAITING = "WAITING"
    NOTIFIED = "NOTIFIED"
    CONVERTED = "CONVERTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ReminderType(str, enum.Enum):
    CONFIRMATION = "CONFIRMATION"
    TWENTY_FOUR_HOUR = "24_HOUR"
    ONE_HOUR = "1_HOUR"
    CUSTOM = "CUSTOM"


class ReminderChannel(str, enum.Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"


class ReminderStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class NoShowReason(str, enum.Enum):
    NO_CONTACT = "NO_CONTACT"
    LATE_CANCEL = "LATE_CANCEL"
    FORGOT = "FORGOT"
    WEATHER = "WEATHER"
    OTHER = "OTHER"


class TimePeriod(str, enum.Enum):
    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"
    EVENING = "EVENING"
    NIGHT = "NIGHT"


class NoteType(str, enum.Enum):
    CUSTOMER_REQUEST = "CUSTOMER_REQUEST"
    STAFF_NOTE = "STAFF_NOTE"
    SYSTEM_NOTE = "SYSTEM_NOTE"


class HoldStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CONVERTED = "CONVERTED"
    EXPIRED = "EXPIRED"
    RELEASED = "RELEASED"


class RecurrenceFrequency(str, enum.Enum):
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"


class DepositStatus(str, enum.Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    COLLECTED = "COLLECTED"
    REFUNDED = "REFUNDED"
    FORFEITED = "FORFEITED"


# ─── Models ──────────────────────────────────────────────────────────────────

class Reservation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "reservations"
    __table_args__ = (
        # Item 4: Composite indexes on hot query paths
        Index("ix_reservations_venue_date_status", "venue_id", "reservation_date", "status"),
        Index("ix_reservations_venue_date_time", "venue_id", "reservation_date", "start_time"),
        Index("ix_reservations_customer_date", "customer_id", "reservation_date"),
        Index("ix_reservations_venue_type_date", "venue_id", "reservation_type", "reservation_date"),
    )

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    reservation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reservation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=ReservationStatus.CONFIRMED.value,
        server_default="CONFIRMED", index=True,
    )
    confirmation_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    no_show_probability: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    booking_channel: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    special_requests: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Item 3: Idempotency key
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)

    # Deposit fields (enhanced for item 8)
    deposit_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    deposit_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    deposit_paid: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    deposit_status: Mapped[str] = mapped_column(
        String(20), default=DepositStatus.NOT_REQUIRED.value, server_default="NOT_REQUIRED"
    )
    deposit_transaction_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    deposit_paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deposit_refunded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Item 6: Recurring reservation fields
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    recurrence_group_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    recurrence_frequency: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    recurrence_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    recurrence_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Item 7: Group/block reservation fields
    is_group_booking: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    group_booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    group_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    group_contact_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    group_contact_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    group_contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Lifecycle timestamps
    checked_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    items: Mapped[List["ReservationItem"]] = relationship(
        "ReservationItem", back_populates="reservation", lazy="selectin", cascade="all, delete-orphan"
    )
    reminders: Mapped[List["ReservationReminder"]] = relationship(
        "ReservationReminder", back_populates="reservation", lazy="noload", cascade="all, delete-orphan"
    )
    notes: Mapped[List["ReservationNote"]] = relationship(
        "ReservationNote", back_populates="reservation", lazy="noload", cascade="all, delete-orphan"
    )


class ReservationItem(Base, UUIDMixin):
    __tablename__ = "reservation_items"
    __table_args__ = (
        Index("ix_reservation_items_reservation_id", "reservation_id"),
        Index("ix_reservation_items_item_type", "item_type"),
    )

    reservation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False
    )
    item_type: Mapped[str] = mapped_column(String(50), nullable=False)
    item_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    base_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    dynamic_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    # Item 10: resource assignment for conflict detection
    assigned_resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    reservation: Mapped["Reservation"] = relationship("Reservation", back_populates="items", lazy="selectin")


class CapacityConfig(Base, UUIDMixin):
    __tablename__ = "capacity_config"
    __table_args__ = (
        UniqueConstraint("venue_id", "resource_type", name="uq_venue_resource_type"),
    )

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    total_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    buffer_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("10.0"), server_default="10.0")
    overbooking_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("5.0"), server_default="5.0")
    min_advance_booking_minutes: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    max_advance_booking_days: Mapped[int] = mapped_column(Integer, default=90, server_default="90")
    # Item 2: Business hours per resource
    business_hours_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    business_hours_end: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    max_party_size: Mapped[int] = mapped_column(Integer, default=50, server_default="50")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TimeSlotAvailability(Base, UUIDMixin):
    __tablename__ = "time_slot_availability"
    __table_args__ = (
        UniqueConstraint("venue_id", "resource_type", "availability_date", "time_slot",
                         name="uq_venue_resource_date_slot"),
        Index("ix_timeslot_venue_resource_date", "venue_id", "resource_type", "availability_date"),
    )

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    availability_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    time_slot: Mapped[time] = mapped_column(Time, nullable=False)
    total_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_capacity: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    available_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    dynamic_price_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("1.0"), server_default="1.0"
    )
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReservationWaitlist(Base, UUIDMixin):
    __tablename__ = "reservation_waitlist"
    __table_args__ = (
        Index("ix_waitlist_venue_date", "venue_id", "desired_date"),
    )

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    reservation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    desired_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    desired_time: Mapped[time] = mapped_column(Time, nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(
        String(20), default=WaitlistStatus.WAITING.value, server_default="WAITING"
    )
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReservationReminder(Base, UUIDMixin):
    __tablename__ = "reservation_reminders"
    __table_args__ = (
        Index("ix_reminders_status_scheduled", "status", "scheduled_send_time"),
    )

    reservation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False
    )
    reminder_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reminder_channel: Mapped[str] = mapped_column(String(20), nullable=False)
    scheduled_send_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=ReminderStatus.PENDING.value, server_default="PENDING"
    )
    # Item 9: Notification integration tracking
    notification_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notification_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    reservation: Mapped["Reservation"] = relationship("Reservation", back_populates="reminders", lazy="selectin")


class NoShowHistory(Base, UUIDMixin):
    __tablename__ = "no_show_history"
    __table_args__ = (
        Index("ix_no_show_customer_date", "customer_id", "no_show_date"),
    )

    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    reservation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("reservations.id"), nullable=False
    )
    no_show_date: Mapped[date] = mapped_column(Date, nullable=False)
    reservation_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    reservation: Mapped["Reservation"] = relationship("Reservation", lazy="selectin")


class CustomerReservationStats(Base, UUIDMixin):
    __tablename__ = "customer_reservation_stats"
    __table_args__ = (
        UniqueConstraint("customer_id", name="uq_customer_stats"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    total_reservations: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    completed_reservations: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cancelled_reservations: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    no_show_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    no_show_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), server_default="0")
    avg_party_size: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 1), nullable=True)
    last_reservation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    reliability_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("100"), server_default="100", index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OverbookingRule(Base, UUIDMixin):
    __tablename__ = "overbooking_rules"
    __table_args__ = (
        Index("ix_overbooking_venue_resource", "venue_id", "resource_type"),
    )

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    day_of_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0=Sunday, 6=Saturday
    time_period: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    historical_no_show_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    recommended_overbooking_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    active_overbooking_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReservationNote(Base, UUIDMixin):
    __tablename__ = "reservation_notes"

    reservation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False
    )
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    reservation: Mapped["Reservation"] = relationship("Reservation", back_populates="notes", lazy="selectin")


class TimeSlotHold(Base, UUIDMixin):
    __tablename__ = "time_slot_holds"
    __table_args__ = (
        Index("ix_holds_status_expires", "status", "expires_at"),
        Index("ix_holds_venue_date_slot", "venue_id", "hold_date", "time_slot"),
    )

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    hold_date: Mapped[date] = mapped_column(Date, nullable=False)
    time_slot: Mapped[time] = mapped_column(Time, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    held_by: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=HoldStatus.ACTIVE.value, server_default="ACTIVE")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IdempotencyRecord(Base, UUIDMixin):
    """Tracks idempotency keys to prevent duplicate reservation creation."""
    __tablename__ = "idempotency_records"
    __table_args__ = (
        Index("ix_idempotency_key_created", "idempotency_key", "created_at"),
    )

    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    reservation_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False, default=201)
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
