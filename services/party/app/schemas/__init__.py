"""
Party Service Schemas

Pydantic schemas for request/response validation.
"""

from app.schemas.party import (
    # Pagination
    PaginationParams,
    # Package schemas
    PartyPackageBase,
    PartyPackageCreate,
    PartyPackageUpdate,
    PartyPackageResponse,
    PartyPackageListResponse,
    PartyPackageDetailResponse,
    # Addon schemas
    PartyAddonBase,
    PartyAddonCreate,
    PartyAddonUpdate,
    PartyAddonResponse,
    PartyAddonListResponse,
    # Booking schemas
    PartyBookingBase,
    PartyBookingCreate,
    PartyBookingUpdate,
    PartyBookingResponse,
    PartyBookingListResponse,
    PartyBookingDetailResponse,
    PartyBookingStatusUpdate,
    # Booking addon schemas
    BookingAddonCreate,
    BookingAddonResponse,
    # Corporate event schemas
    CorporateEventBase,
    CorporateEventCreate,
    CorporateEventUpdate,
    CorporateEventResponse,
    CorporateEventListResponse,
    CorporateEventStatusUpdate,
    # Timeline schemas
    PartyTimelineBase,
    PartyTimelineCreate,
    PartyTimelineUpdate,
    PartyTimelineResponse,
    TimelineItemComplete,
    # Host assignment schemas
    HostAssignmentCreate,
    HostAssignmentResponse,
    # Analytics schemas
    PartyRevenueStats,
    PartyPerformanceMetrics,
    UpsellConversionStats,
)

__all__ = [
    "PaginationParams",
    "PartyPackageBase",
    "PartyPackageCreate",
    "PartyPackageUpdate",
    "PartyPackageResponse",
    "PartyPackageListResponse",
    "PartyPackageDetailResponse",
    "PartyAddonBase",
    "PartyAddonCreate",
    "PartyAddonUpdate",
    "PartyAddonResponse",
    "PartyAddonListResponse",
    "PartyBookingBase",
    "PartyBookingCreate",
    "PartyBookingUpdate",
    "PartyBookingResponse",
    "PartyBookingListResponse",
    "PartyBookingDetailResponse",
    "PartyBookingStatusUpdate",
    "BookingAddonCreate",
    "BookingAddonResponse",
    "CorporateEventBase",
    "CorporateEventCreate",
    "CorporateEventUpdate",
    "CorporateEventResponse",
    "CorporateEventListResponse",
    "CorporateEventStatusUpdate",
    "PartyTimelineBase",
    "PartyTimelineCreate",
    "PartyTimelineUpdate",
    "PartyTimelineResponse",
    "TimelineItemComplete",
    "HostAssignmentCreate",
    "HostAssignmentResponse",
    "PartyRevenueStats",
    "PartyPerformanceMetrics",
    "UpsellConversionStats",
]
