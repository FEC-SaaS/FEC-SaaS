"""
Pydantic schemas for Venue Service API.
"""

from app.schemas.venue import (
    # Base schemas
    VenueBase,
    VenueCreate,
    VenueUpdate,
    VenueResponse,
    VenueListResponse,
    VenueDetailResponse,
    # Hours schemas
    VenueHoursBase,
    VenueHoursCreate,
    VenueHoursUpdate,
    VenueHoursResponse,
    VenueSpecialHoursCreate,
    VenueSpecialHoursResponse,
    # Settings schemas
    VenueSettingBase,
    VenueSettingCreate,
    VenueSettingUpdate,
    VenueSettingResponse,
    VenueSettingsBulkUpdate,
    # Feature schemas
    VenueFeatureBase,
    VenueFeatureCreate,
    VenueFeatureUpdate,
    VenueFeatureResponse,
    # AI Config schemas
    VenueAIConfigBase,
    VenueAIConfigCreate,
    VenueAIConfigUpdate,
    VenueAIConfigResponse,
    # Performance schemas
    VenuePerformanceBase,
    VenuePerformanceCreate,
    VenuePerformanceResponse,
    VenueBenchmarkResponse,
    # Contact schemas
    VenueContactCreate,
    VenueContactResponse,
    # Image schemas
    VenueImageCreate,
    VenueImageResponse,
    # Onboarding schemas
    OnboardingStartRequest,
    OnboardingStepRequest,
    OnboardingStatusResponse,
    # Bulk operations
    BulkVenueCreate,
    BulkVenueUpdate,
    BulkSyncRequest,
    # Common
    PaginationParams,
    VenueFilters,
)

__all__ = [
    "VenueBase",
    "VenueCreate",
    "VenueUpdate",
    "VenueResponse",
    "VenueListResponse",
    "VenueDetailResponse",
    "VenueHoursBase",
    "VenueHoursCreate",
    "VenueHoursUpdate",
    "VenueHoursResponse",
    "VenueSpecialHoursCreate",
    "VenueSpecialHoursResponse",
    "VenueSettingBase",
    "VenueSettingCreate",
    "VenueSettingUpdate",
    "VenueSettingResponse",
    "VenueSettingsBulkUpdate",
    "VenueFeatureBase",
    "VenueFeatureCreate",
    "VenueFeatureUpdate",
    "VenueFeatureResponse",
    "VenueAIConfigBase",
    "VenueAIConfigCreate",
    "VenueAIConfigUpdate",
    "VenueAIConfigResponse",
    "VenuePerformanceBase",
    "VenuePerformanceCreate",
    "VenuePerformanceResponse",
    "VenueBenchmarkResponse",
    "VenueContactCreate",
    "VenueContactResponse",
    "VenueImageCreate",
    "VenueImageResponse",
    "OnboardingStartRequest",
    "OnboardingStepRequest",
    "OnboardingStatusResponse",
    "BulkVenueCreate",
    "BulkVenueUpdate",
    "BulkSyncRequest",
    "PaginationParams",
    "VenueFilters",
]
