"""
=============================================================================
FILE: schemas/party.py
PURPOSE: Pydantic schemas for Party Service API
=============================================================================

Defines request/response schemas for all party-related endpoints.
Uses Pydantic v2 for validation and serialization.
"""

from datetime import datetime, date, time
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ConfigDict, EmailStr


# Import enums from models
from app.models.party import (
    PackageType,
    AddonType,
    BookingType,
    BookingStatus,
    CorporateEventType,
    CorporateEventStatus,
    TimelineStatus,
    HostRole,
)


# =============================================================================
# COMMON SCHEMAS
# =============================================================================


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(default="created_at", description="Field to sort by")
    sort_order: Optional[str] = Field(default="desc", pattern="^(asc|desc)$")


# =============================================================================
# PARTY PACKAGE SCHEMAS
# =============================================================================


class PartyPackageBase(BaseModel):
    """Base schema for party packages."""
    package_name: str = Field(..., min_length=1, max_length=255)
    package_type: PackageType = PackageType.BIRTHDAY
    description: Optional[str] = None
    min_guests: int = Field(default=8, ge=1)
    max_guests: int = Field(default=25, ge=1)
    base_price: Decimal = Field(..., ge=0)
    price_per_additional_guest: Optional[Decimal] = Field(default=None, ge=0)
    deposit_percentage: Decimal = Field(default=Decimal("25.00"), ge=0, le=100)
    duration_minutes: int = Field(default=120, ge=30)
    includes_food: bool = True
    includes_drinks: bool = True
    includes_cake: bool = False
    includes_decorations: bool = True
    includes_invitations: bool = False
    included_activities: Optional[Dict[str, Any]] = Field(default_factory=dict)
    display_order: int = Field(default=0, ge=0)
    is_featured: bool = False
    image_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("max_guests")
    @classmethod
    def validate_max_guests(cls, v: int, info) -> int:
        """Ensure max_guests >= min_guests."""
        if "min_guests" in info.data and v < info.data["min_guests"]:
            raise ValueError("max_guests must be >= min_guests")
        return v


class PartyPackageCreate(PartyPackageBase):
    """Schema for creating a party package."""
    venue_id: UUID
    default_addon_ids: Optional[List[UUID]] = None


class PartyPackageUpdate(BaseModel):
    """Schema for updating a party package."""
    package_name: Optional[str] = Field(default=None, max_length=255)
    package_type: Optional[PackageType] = None
    description: Optional[str] = None
    min_guests: Optional[int] = Field(default=None, ge=1)
    max_guests: Optional[int] = Field(default=None, ge=1)
    base_price: Optional[Decimal] = Field(default=None, ge=0)
    price_per_additional_guest: Optional[Decimal] = Field(default=None, ge=0)
    deposit_percentage: Optional[Decimal] = Field(default=None, ge=0, le=100)
    duration_minutes: Optional[int] = Field(default=None, ge=30)
    includes_food: Optional[bool] = None
    includes_drinks: Optional[bool] = None
    includes_cake: Optional[bool] = None
    includes_decorations: Optional[bool] = None
    includes_invitations: Optional[bool] = None
    included_activities: Optional[Dict[str, Any]] = None
    display_order: Optional[int] = Field(default=None, ge=0)
    is_featured: Optional[bool] = None
    is_active: Optional[bool] = None
    image_url: Optional[str] = Field(default=None, max_length=500)


class PartyPackageResponse(PartyPackageBase):
    """Response schema for party package."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venue_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PartyPackageListResponse(BaseModel):
    """Paginated list response for packages."""
    packages: List[PartyPackageResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PartyPackageAddonResponse(BaseModel):
    """Response for package default addons."""
    model_config = ConfigDict(from_attributes=True)

    addon_id: UUID
    quantity: int
    is_included_free: bool
    discount_percentage: Decimal


class PartyPackageDetailResponse(PartyPackageResponse):
    """Detailed response with addons."""
    default_addons: List[PartyPackageAddonResponse] = []


# =============================================================================
# PARTY ADDON SCHEMAS
# =============================================================================


class PartyAddonBase(BaseModel):
    """Base schema for party addons."""
    addon_name: str = Field(..., min_length=1, max_length=255)
    addon_type: AddonType = AddonType.CUSTOM
    description: Optional[str] = None
    price: Decimal = Field(..., ge=0)
    price_type: str = Field(default="fixed", pattern="^(fixed|per_guest|per_hour)$")
    min_quantity: int = Field(default=1, ge=1)
    max_quantity: Optional[int] = Field(default=None, ge=1)
    requires_advance_notice_hours: int = Field(default=0, ge=0)
    display_order: int = Field(default=0, ge=0)
    image_url: Optional[str] = Field(default=None, max_length=500)
    upsell_priority: int = Field(default=0, ge=0)
    upsell_message: Optional[str] = None


class PartyAddonCreate(PartyAddonBase):
    """Schema for creating a party addon."""
    venue_id: UUID


class PartyAddonUpdate(BaseModel):
    """Schema for updating a party addon."""
    addon_name: Optional[str] = Field(default=None, max_length=255)
    addon_type: Optional[AddonType] = None
    description: Optional[str] = None
    price: Optional[Decimal] = Field(default=None, ge=0)
    price_type: Optional[str] = Field(default=None, pattern="^(fixed|per_guest|per_hour)$")
    min_quantity: Optional[int] = Field(default=None, ge=1)
    max_quantity: Optional[int] = Field(default=None, ge=1)
    requires_advance_notice_hours: Optional[int] = Field(default=None, ge=0)
    display_order: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None
    image_url: Optional[str] = Field(default=None, max_length=500)
    upsell_priority: Optional[int] = Field(default=None, ge=0)
    upsell_message: Optional[str] = None


class PartyAddonResponse(PartyAddonBase):
    """Response schema for party addon."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venue_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PartyAddonListResponse(BaseModel):
    """Paginated list response for addons."""
    addons: List[PartyAddonResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# PARTY BOOKING SCHEMAS
# =============================================================================


class BookingAddonCreate(BaseModel):
    """Schema for adding addon to booking."""
    addon_id: UUID
    quantity: int = Field(default=1, ge=1)
    notes: Optional[str] = None


class BookingAddonResponse(BaseModel):
    """Response for booking addon."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    addon_id: UUID
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    was_upsell_suggestion: bool
    notes: Optional[str]


class PartyBookingBase(BaseModel):
    """Base schema for party bookings."""
    booking_type: BookingType = BookingType.BIRTHDAY
    party_date: date
    start_time: time
    guest_count: int = Field(..., ge=1)
    child_count: Optional[int] = Field(default=None, ge=0)
    adult_count: Optional[int] = Field(default=None, ge=0)
    guest_of_honor_name: Optional[str] = Field(default=None, max_length=255)
    guest_of_honor_age: Optional[int] = Field(default=None, ge=0)
    contact_name: str = Field(..., min_length=1, max_length=255)
    contact_email: EmailStr
    contact_phone: str = Field(..., max_length=20)
    special_requests: Optional[str] = None
    dietary_restrictions: Optional[str] = None
    allergy_info: Optional[str] = None
    booking_source: Optional[str] = Field(default=None, max_length=50)


class PartyBookingCreate(PartyBookingBase):
    """Schema for creating a party booking."""
    venue_id: UUID
    customer_id: UUID
    package_id: UUID
    addons: Optional[List[BookingAddonCreate]] = None


class PartyBookingUpdate(BaseModel):
    """Schema for updating a party booking."""
    party_date: Optional[date] = None
    start_time: Optional[time] = None
    guest_count: Optional[int] = Field(default=None, ge=1)
    child_count: Optional[int] = Field(default=None, ge=0)
    adult_count: Optional[int] = Field(default=None, ge=0)
    guest_of_honor_name: Optional[str] = Field(default=None, max_length=255)
    guest_of_honor_age: Optional[int] = Field(default=None, ge=0)
    contact_name: Optional[str] = Field(default=None, max_length=255)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(default=None, max_length=20)
    special_requests: Optional[str] = None
    dietary_restrictions: Optional[str] = None
    allergy_info: Optional[str] = None
    assigned_area: Optional[str] = Field(default=None, max_length=100)
    internal_notes: Optional[str] = None


class PartyBookingStatusUpdate(BaseModel):
    """Schema for updating booking status."""
    status: BookingStatus
    cancellation_reason: Optional[str] = None


class PartyBookingResponse(BaseModel):
    """Response schema for party booking."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venue_id: UUID
    customer_id: UUID
    package_id: UUID
    booking_type: BookingType
    booking_reference: str
    party_date: date
    start_time: time
    end_time: time
    guest_count: int
    child_count: Optional[int]
    adult_count: Optional[int]
    guest_of_honor_name: Optional[str]
    guest_of_honor_age: Optional[int]
    contact_name: str
    contact_email: str
    contact_phone: str
    base_price: Decimal
    addons_total: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_price: Decimal
    deposit_amount: Decimal
    deposit_paid: bool
    amount_paid: Decimal
    balance_due: Decimal
    status: BookingStatus
    special_requests: Optional[str]
    dietary_restrictions: Optional[str]
    assigned_area: Optional[str]
    booking_source: Optional[str]
    created_at: datetime
    updated_at: datetime


class PartyBookingListResponse(BaseModel):
    """Paginated list response for bookings."""
    bookings: List[PartyBookingResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PartyTimelineResponse(BaseModel):
    """Response for timeline item."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_name: str
    item_description: Optional[str]
    item_category: Optional[str]
    scheduled_time: time
    duration_minutes: int
    actual_time: Optional[time]
    status: TimelineStatus
    assigned_staff_id: Optional[UUID]
    sequence_order: int
    notes: Optional[str]


class HostAssignmentResponse(BaseModel):
    """Response for host assignment."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    staff_id: UUID
    role: HostRole
    start_time: Optional[time]
    end_time: Optional[time]
    confirmed: bool
    checked_in: bool


class PartyBookingDetailResponse(PartyBookingResponse):
    """Detailed response with addons, timeline, and staff."""
    addons: List[BookingAddonResponse] = []
    timeline: List[PartyTimelineResponse] = []
    host_assignments: List[HostAssignmentResponse] = []


# =============================================================================
# CORPORATE EVENT SCHEMAS
# =============================================================================


class CorporateEventBase(BaseModel):
    """Base schema for corporate events."""
    company_name: str = Field(..., min_length=1, max_length=255)
    company_industry: Optional[str] = Field(default=None, max_length=100)
    company_size: Optional[str] = Field(default=None, max_length=50)
    contact_name: str = Field(..., min_length=1, max_length=255)
    contact_email: EmailStr
    contact_phone: Optional[str] = Field(default=None, max_length=20)
    contact_title: Optional[str] = Field(default=None, max_length=100)
    event_type: CorporateEventType
    event_name: Optional[str] = Field(default=None, max_length=255)
    event_date: date
    start_time: time
    end_time: time
    attendee_count: int = Field(..., ge=1)
    min_attendees: Optional[int] = Field(default=None, ge=1)
    max_attendees: Optional[int] = Field(default=None, ge=1)
    estimated_budget: Optional[Decimal] = Field(default=None, ge=0)
    special_requests: Optional[str] = None
    catering_requirements: Optional[str] = None
    beverage_requirements: Optional[str] = None
    av_requirements: Optional[str] = None
    space_requirements: Optional[str] = None


class CorporateEventCreate(CorporateEventBase):
    """Schema for creating a corporate event."""
    venue_id: UUID


class CorporateEventUpdate(BaseModel):
    """Schema for updating a corporate event."""
    company_name: Optional[str] = Field(default=None, max_length=255)
    company_industry: Optional[str] = Field(default=None, max_length=100)
    company_size: Optional[str] = Field(default=None, max_length=50)
    contact_name: Optional[str] = Field(default=None, max_length=255)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(default=None, max_length=20)
    contact_title: Optional[str] = Field(default=None, max_length=100)
    event_type: Optional[CorporateEventType] = None
    event_name: Optional[str] = Field(default=None, max_length=255)
    event_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    attendee_count: Optional[int] = Field(default=None, ge=1)
    min_attendees: Optional[int] = Field(default=None, ge=1)
    max_attendees: Optional[int] = Field(default=None, ge=1)
    estimated_budget: Optional[Decimal] = Field(default=None, ge=0)
    quoted_price: Optional[Decimal] = Field(default=None, ge=0)
    final_price: Optional[Decimal] = Field(default=None, ge=0)
    deposit_amount: Optional[Decimal] = Field(default=None, ge=0)
    special_requests: Optional[str] = None
    catering_requirements: Optional[str] = None
    beverage_requirements: Optional[str] = None
    av_requirements: Optional[str] = None
    space_requirements: Optional[str] = None
    assigned_rep_id: Optional[UUID] = None
    next_follow_up_date: Optional[datetime] = None
    follow_up_notes: Optional[str] = None
    internal_notes: Optional[str] = None


class CorporateEventStatusUpdate(BaseModel):
    """Schema for updating corporate event status."""
    status: CorporateEventStatus
    lost_reason: Optional[str] = None
    proposal_url: Optional[str] = Field(default=None, max_length=500)


class CorporateEventResponse(CorporateEventBase):
    """Response schema for corporate event."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venue_id: UUID
    status: CorporateEventStatus
    lead_score: Optional[int]
    quoted_price: Optional[Decimal]
    final_price: Optional[Decimal]
    deposit_amount: Optional[Decimal]
    deposit_paid: bool
    proposal_sent_at: Optional[datetime]
    proposal_expires_at: Optional[datetime]
    proposal_url: Optional[str]
    last_contact_date: Optional[datetime]
    next_follow_up_date: Optional[datetime]
    assigned_rep_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime


class CorporateEventListResponse(BaseModel):
    """Paginated list response for corporate events."""
    events: List[CorporateEventResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# TIMELINE SCHEMAS
# =============================================================================


class PartyTimelineBase(BaseModel):
    """Base schema for timeline items."""
    item_name: str = Field(..., min_length=1, max_length=255)
    item_description: Optional[str] = None
    item_category: Optional[str] = Field(default=None, max_length=50)
    scheduled_time: time
    duration_minutes: int = Field(default=15, ge=1)
    assigned_staff_id: Optional[UUID] = None
    sequence_order: int = Field(default=0, ge=0)


class PartyTimelineCreate(PartyTimelineBase):
    """Schema for creating timeline item."""
    booking_id: UUID


class PartyTimelineUpdate(BaseModel):
    """Schema for updating timeline item."""
    item_name: Optional[str] = Field(default=None, max_length=255)
    item_description: Optional[str] = None
    item_category: Optional[str] = Field(default=None, max_length=50)
    scheduled_time: Optional[time] = None
    duration_minutes: Optional[int] = Field(default=None, ge=1)
    assigned_staff_id: Optional[UUID] = None
    sequence_order: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None


class TimelineItemComplete(BaseModel):
    """Schema for completing a timeline item."""
    actual_time: Optional[time] = None
    notes: Optional[str] = None
    delay_reason: Optional[str] = None


# =============================================================================
# HOST ASSIGNMENT SCHEMAS
# =============================================================================


class HostAssignmentCreate(BaseModel):
    """Schema for creating host assignment."""
    booking_id: UUID
    staff_id: UUID
    role: HostRole = HostRole.PRIMARY_HOST
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    notes: Optional[str] = None


class HostAssignmentUpdate(BaseModel):
    """Schema for updating host assignment."""
    role: Optional[HostRole] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    confirmed: Optional[bool] = None
    notes: Optional[str] = None


# =============================================================================
# ANALYTICS SCHEMAS
# =============================================================================


class PartyRevenueStats(BaseModel):
    """Party revenue statistics."""
    period_start: date
    period_end: date
    total_revenue: Decimal
    total_bookings: int
    average_booking_value: Decimal
    total_addons_revenue: Decimal
    deposit_revenue: Decimal
    revenue_by_package_type: Dict[str, Decimal]
    revenue_by_booking_type: Dict[str, Decimal]
    top_packages: List[Dict[str, Any]]
    top_addons: List[Dict[str, Any]]
    comparison_to_previous: Optional[Dict[str, float]] = None


class PartyPerformanceMetrics(BaseModel):
    """Party performance metrics."""
    period_start: date
    period_end: date
    total_parties: int
    completed_parties: int
    cancelled_parties: int
    no_show_parties: int
    completion_rate: float
    cancellation_rate: float
    average_party_size: float
    average_duration_minutes: float
    on_time_start_rate: float
    average_satisfaction_score: Optional[float] = None
    timeline_completion_rate: float
    busiest_days: List[Dict[str, Any]]
    busiest_times: List[Dict[str, Any]]


class UpsellConversionStats(BaseModel):
    """Upsell conversion statistics."""
    period_start: date
    period_end: date
    total_bookings: int
    bookings_with_upsells: int
    upsell_conversion_rate: float
    total_upsell_revenue: Decimal
    average_upsell_value: Decimal
    top_converting_addons: List[Dict[str, Any]]
    upsell_acceptance_by_source: Dict[str, float]
    ai_suggested_acceptance_rate: Optional[float] = None
