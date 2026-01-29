"""Reservation & Capacity service Pydantic schemas."""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.reservation import (
    BookingChannel,
    DepositStatus,
    NoShowReason,
    NoteType,
    RecurrenceFrequency,
    ReminderChannel,
    ReminderType,
    ReservationStatus,
    ReservationType,
    ResourceType,
    TimePeriod,
    WaitlistStatus,
)


class BaseSchema(BaseModel):
    model_config = {"from_attributes": True}


# ─── Reservation Items ───────────────────────────────────────────────────────

class ReservationItemCreate(BaseSchema):
    item_type: ResourceType
    item_id: Optional[UUID] = None
    quantity: int = Field(default=1, ge=1)
    duration_minutes: Optional[int] = Field(None, ge=1)
    base_price: Optional[Decimal] = Field(None, ge=0)
    dynamic_price: Optional[Decimal] = Field(None, ge=0)


class ReservationItemResponse(BaseSchema):
    id: UUID
    reservation_id: UUID
    item_type: str
    item_id: Optional[UUID] = None
    quantity: int
    duration_minutes: Optional[int] = None
    base_price: Optional[Decimal] = None
    dynamic_price: Optional[Decimal] = None
    assigned_resource_id: Optional[UUID] = None
    created_at: datetime


# ─── Reservations ────────────────────────────────────────────────────────────

class ReservationCreate(BaseSchema):
    customer_id: Optional[UUID] = None
    reservation_type: ReservationType
    reservation_date: date
    start_time: time
    end_time: time
    party_size: int = Field(..., ge=1)
    booking_channel: Optional[BookingChannel] = None
    special_requests: Optional[str] = None
    deposit_required: bool = False
    deposit_amount: Optional[Decimal] = Field(None, ge=0)
    idempotency_key: Optional[str] = Field(None, max_length=64)
    items: List[ReservationItemCreate] = []


class ReservationUpdate(BaseSchema):
    reservation_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    party_size: Optional[int] = Field(None, ge=1)
    special_requests: Optional[str] = None
    status: Optional[ReservationStatus] = None


class ReservationResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    customer_id: Optional[UUID] = None
    reservation_type: str
    reservation_date: date
    start_time: time
    end_time: time
    party_size: int
    status: str
    confirmation_code: str
    no_show_probability: Optional[Decimal] = None
    booking_channel: Optional[str] = None
    special_requests: Optional[str] = None
    idempotency_key: Optional[str] = None
    # Deposit
    deposit_required: bool
    deposit_amount: Optional[Decimal] = None
    deposit_paid: bool
    deposit_status: Optional[str] = None
    deposit_transaction_id: Optional[str] = None
    deposit_paid_at: Optional[datetime] = None
    deposit_refunded_at: Optional[datetime] = None
    # Recurring
    is_recurring: bool = False
    recurrence_group_id: Optional[UUID] = None
    recurrence_frequency: Optional[str] = None
    recurrence_end_date: Optional[date] = None
    recurrence_index: Optional[int] = None
    # Group
    is_group_booking: bool = False
    group_booking_id: Optional[UUID] = None
    group_name: Optional[str] = None
    group_contact_name: Optional[str] = None
    group_contact_email: Optional[str] = None
    group_contact_phone: Optional[str] = None
    # Lifecycle
    checked_in_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    items: List[ReservationItemResponse] = []


# ─── Availability ────────────────────────────────────────────────────────────

class AvailabilityQuery(BaseSchema):
    resource_type: ResourceType
    start_date: date
    end_date: Optional[date] = None
    party_size: Optional[int] = Field(None, ge=1)


class TimeSlotResponse(BaseSchema):
    time_slot: time
    total_capacity: int
    reserved_capacity: int
    available_capacity: int
    is_available: bool
    dynamic_price_multiplier: Decimal


class DateAvailabilityResponse(BaseSchema):
    availability_date: date
    resource_type: str
    slots: List[TimeSlotResponse] = []


class HoldRequest(BaseSchema):
    resource_type: ResourceType
    hold_date: date
    time_slot: time
    quantity: int = Field(default=1, ge=1)


class HoldResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    resource_type: str
    hold_date: date
    time_slot: time
    quantity: int
    status: str
    expires_at: datetime
    created_at: datetime


# ─── Capacity Config ─────────────────────────────────────────────────────────

class CapacityConfigCreate(BaseSchema):
    resource_type: ResourceType
    total_capacity: int = Field(..., ge=1)
    buffer_percentage: Decimal = Field(default=Decimal("10.0"), ge=0, le=100)
    overbooking_percentage: Decimal = Field(default=Decimal("5.0"), ge=0, le=50)
    min_advance_booking_minutes: int = Field(default=30, ge=0)
    max_advance_booking_days: int = Field(default=90, ge=1)
    business_hours_start: Optional[time] = None
    business_hours_end: Optional[time] = None
    max_party_size: int = Field(default=50, ge=1)


class CapacityConfigUpdate(BaseSchema):
    total_capacity: Optional[int] = Field(None, ge=1)
    buffer_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    overbooking_percentage: Optional[Decimal] = Field(None, ge=0, le=50)
    min_advance_booking_minutes: Optional[int] = Field(None, ge=0)
    max_advance_booking_days: Optional[int] = Field(None, ge=1)


class CapacityConfigResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    resource_type: str
    total_capacity: int
    buffer_percentage: Decimal
    overbooking_percentage: Decimal
    min_advance_booking_minutes: int
    max_advance_booking_days: int
    business_hours_start: Optional[time] = None
    business_hours_end: Optional[time] = None
    max_party_size: int = 50
    created_at: datetime


class RealTimeCapacityResponse(BaseSchema):
    venue_id: UUID
    resource_type: str
    total_capacity: int
    currently_reserved: int
    currently_available: int
    utilization_percentage: Decimal
    timestamp: datetime


class CapacityForecastSlot(BaseSchema):
    time_slot: time
    predicted_demand: int
    available_capacity: int
    utilization_percentage: Decimal


class CapacityForecastResponse(BaseSchema):
    venue_id: UUID
    resource_type: str
    forecast_date: date
    slots: List[CapacityForecastSlot] = []


# ─── Waitlist ────────────────────────────────────────────────────────────────

class WaitlistCreate(BaseSchema):
    customer_id: Optional[UUID] = None
    reservation_type: ReservationType
    desired_date: date
    desired_time: time
    party_size: int = Field(..., ge=1)
    notes: Optional[str] = None


class WaitlistResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    customer_id: Optional[UUID] = None
    reservation_type: str
    desired_date: date
    desired_time: time
    party_size: int
    priority: int
    status: str
    notified_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime


class WaitlistConvertRequest(BaseSchema):
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    items: List[ReservationItemCreate] = []


# ─── Reminders ───────────────────────────────────────────────────────────────

class ReminderCreate(BaseSchema):
    reminder_type: ReminderType
    reminder_channel: ReminderChannel
    scheduled_send_time: datetime


class ReminderResponse(BaseSchema):
    id: UUID
    reservation_id: UUID
    reminder_type: str
    reminder_channel: str
    scheduled_send_time: datetime
    sent_at: Optional[datetime] = None
    status: str
    notification_id: Optional[str] = None
    notification_error: Optional[str] = None
    created_at: datetime


# ─── No-Shows ────────────────────────────────────────────────────────────────

class NoShowCreate(BaseSchema):
    reason: Optional[NoShowReason] = None
    reservation_value: Optional[Decimal] = Field(None, ge=0)


class NoShowResponse(BaseSchema):
    id: UUID
    customer_id: Optional[UUID] = None
    reservation_id: UUID
    no_show_date: date
    reservation_value: Optional[Decimal] = None
    reason: Optional[str] = None
    created_at: datetime


class CustomerReservationStatsResponse(BaseSchema):
    id: UUID
    customer_id: UUID
    total_reservations: int
    completed_reservations: int
    cancelled_reservations: int
    no_show_count: int
    no_show_rate: Decimal
    avg_party_size: Optional[Decimal] = None
    last_reservation_date: Optional[date] = None
    reliability_score: Decimal
    updated_at: datetime


# ─── Overbooking ─────────────────────────────────────────────────────────────

class OverbookingRuleCreate(BaseSchema):
    resource_type: ResourceType
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    time_period: Optional[TimePeriod] = None
    active_overbooking_rate: Decimal = Field(..., ge=0, le=50)


class OverbookingRuleUpdate(BaseSchema):
    active_overbooking_rate: Optional[Decimal] = Field(None, ge=0, le=50)
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    time_period: Optional[TimePeriod] = None


class OverbookingRuleResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    resource_type: str
    day_of_week: Optional[int] = None
    time_period: Optional[str] = None
    historical_no_show_rate: Optional[Decimal] = None
    recommended_overbooking_rate: Optional[Decimal] = None
    active_overbooking_rate: Optional[Decimal] = None
    updated_at: datetime


class OverbookingForecastResponse(BaseSchema):
    venue_id: UUID
    resource_type: str
    date: date
    expected_no_shows: int
    recommended_overbooking: int
    current_overbooking_rate: Decimal
    confidence: Decimal


# ─── Notes ───────────────────────────────────────────────────────────────────

class NoteCreate(BaseSchema):
    note_text: str = Field(..., min_length=1)
    note_type: Optional[NoteType] = None


class NoteResponse(BaseSchema):
    id: UUID
    reservation_id: UUID
    note_text: str
    note_type: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: datetime


# ─── Analytics ───────────────────────────────────────────────────────────────

class UtilizationAnalyticsResponse(BaseSchema):
    venue_id: UUID
    period_start: date
    period_end: date
    resource_type: Optional[str] = None
    avg_utilization_percentage: Decimal
    peak_utilization_percentage: Decimal
    total_reservations: int
    total_capacity_hours: Decimal
    utilized_hours: Decimal
    daily_breakdown: List[Dict[str, Any]] = []


class NoShowAnalyticsResponse(BaseSchema):
    venue_id: UUID
    period_start: date
    period_end: date
    total_no_shows: int
    no_show_rate: Decimal
    estimated_lost_revenue: Decimal
    no_shows_by_reason: Dict[str, int] = {}
    no_shows_by_day: Dict[str, int] = {}
    top_no_show_customers: List[Dict[str, Any]] = []


class RevenueAnalyticsResponse(BaseSchema):
    venue_id: UUID
    period_start: date
    period_end: date
    total_reservation_revenue: Decimal
    avg_revenue_per_reservation: Decimal
    revenue_by_type: Dict[str, Decimal] = {}
    revenue_by_channel: Dict[str, Decimal] = {}
    daily_revenue: List[Dict[str, Any]] = []


class ChannelAnalyticsResponse(BaseSchema):
    venue_id: UUID
    period_start: date
    period_end: date
    total_bookings: int
    bookings_by_channel: Dict[str, int] = {}
    conversion_rates: Dict[str, Decimal] = {}
    avg_lead_time_by_channel: Dict[str, Decimal] = {}


# ─── Recurring Reservations ──────────────────────────────────────────────────

class RecurringReservationCreate(BaseSchema):
    customer_id: Optional[UUID] = None
    reservation_type: ReservationType
    reservation_date: date
    start_time: time
    end_time: time
    party_size: int = Field(..., ge=1)
    booking_channel: Optional[BookingChannel] = None
    special_requests: Optional[str] = None
    deposit_required: bool = False
    deposit_amount: Optional[Decimal] = Field(None, ge=0)
    items: List[ReservationItemCreate] = []
    recurrence_frequency: RecurrenceFrequency
    recurrence_end_date: Optional[date] = None
    max_occurrences: Optional[int] = Field(None, ge=2, le=52)


class RecurringSeriesResponse(BaseSchema):
    recurrence_group_id: UUID
    frequency: str
    total_count: int
    reservations: List[ReservationResponse] = []


# ─── Group/Block Reservations ───────────────────────────────────────────────

class ResourceBlockCreate(BaseSchema):
    resource_type: ResourceType
    resource_id: Optional[UUID] = None
    quantity: int = Field(default=1, ge=1)
    party_size: int = Field(..., ge=1)
    duration_minutes: Optional[int] = Field(None, ge=1)
    base_price: Optional[Decimal] = Field(None, ge=0)


class GroupBookingCreate(BaseSchema):
    customer_id: Optional[UUID] = None
    reservation_type: ReservationType
    reservation_date: date
    start_time: time
    end_time: time
    booking_channel: Optional[BookingChannel] = None
    special_requests: Optional[str] = None
    deposit_required: bool = False
    deposit_amount: Optional[Decimal] = Field(None, ge=0)
    group_name: str = Field(..., min_length=1, max_length=200)
    group_contact_name: str = Field(..., min_length=1, max_length=200)
    group_contact_email: Optional[str] = Field(None, max_length=200)
    group_contact_phone: Optional[str] = Field(None, max_length=50)
    resource_blocks: List[ResourceBlockCreate] = Field(..., min_length=1)


class GroupBookingResponse(BaseSchema):
    group_booking_id: UUID
    group_name: str
    total_resources: int
    total_party_size: int
    reservations: List[ReservationResponse] = []


# ─── Deposit ────────────────────────────────────────────────────────────────

class DepositCollectRequest(BaseSchema):
    amount: Decimal = Field(..., gt=0)
    customer_id: UUID
    payment_method_id: Optional[str] = None


class DepositResponse(BaseSchema):
    status: str
    reservation_id: str
    transaction_id: Optional[str] = None
    amount: Optional[str] = None


# ─── Pagination ──────────────────────────────────────────────────────────────

class PaginatedResponse(BaseSchema):
    items: List[Any] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
