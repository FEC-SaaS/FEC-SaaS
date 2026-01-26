"""
=============================================================================
FILE: schemas/venue.py
PURPOSE: Pydantic schemas for Venue Service API
=============================================================================

Defines request/response schemas for all venue-related endpoints.
Uses Pydantic v2 for validation and serialization.
"""

from datetime import datetime, date, time
from typing import Optional, List, Dict, Any
from uuid import UUID
import re

from pydantic import BaseModel, Field, field_validator, ConfigDict, EmailStr


# =============================================================================
# ENUMS (matching database models)
# =============================================================================

from app.models.venue import (
    VenueStatus,
    SubscriptionTier,
    OnboardingStatus,
    SettingType,
    FeatureName,
    AIServiceName,
    AIStrategy,
    ContactType,
    ImageType,
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


class VenueFilters(BaseModel):
    """Filter parameters for venue list endpoint."""
    status: Optional[VenueStatus] = None
    subscription_tier: Optional[SubscriptionTier] = None
    city: Optional[str] = None
    state: Optional[str] = None
    franchise_id: Optional[UUID] = None
    search: Optional[str] = Field(default=None, description="Search by name or address")
    has_feature: Optional[str] = Field(default=None, description="Filter by enabled feature")


# =============================================================================
# VENUE HOURS SCHEMAS
# =============================================================================


class VenueHoursBase(BaseModel):
    """Base schema for venue hours."""
    day_of_week: int = Field(..., ge=0, le=6, description="0=Sunday, 6=Saturday")
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: bool = False
    is_24_hours: bool = False

    @field_validator("close_time")
    @classmethod
    def validate_close_after_open(cls, v: Optional[time], info) -> Optional[time]:
        """Validate close time is after open time (unless 24 hours)."""
        if v and info.data.get("open_time") and not info.data.get("is_24_hours"):
            if v <= info.data["open_time"]:
                # Allow overnight hours (e.g., 6pm - 2am)
                pass
        return v


class VenueHoursCreate(VenueHoursBase):
    """Schema for creating venue hours."""
    pass


class VenueHoursUpdate(BaseModel):
    """Schema for updating venue hours."""
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: Optional[bool] = None
    is_24_hours: Optional[bool] = None


class VenueHoursResponse(VenueHoursBase):
    """Response schema for venue hours."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venue_id: UUID


class VenueSpecialHoursCreate(BaseModel):
    """Schema for creating special hours."""
    date: date
    name: str = Field(..., max_length=100)
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: bool = False
    is_24_hours: bool = False
    notes: Optional[str] = None


class VenueSpecialHoursResponse(VenueSpecialHoursCreate):
    """Response schema for special hours."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venue_id: UUID
    created_at: datetime


# =============================================================================
# VENUE SETTINGS SCHEMAS
# =============================================================================


class VenueSettingBase(BaseModel):
    """Base schema for venue settings."""
    setting_key: str = Field(..., max_length=100, pattern="^[a-z][a-z0-9_]*$")
    setting_value: str
    setting_type: SettingType = SettingType.STRING
    description: Optional[str] = Field(default=None, max_length=255)
    is_sensitive: bool = False
    category: Optional[str] = Field(default=None, max_length=50)


class VenueSettingCreate(VenueSettingBase):
    """Schema for creating a venue setting."""
    pass


class VenueSettingUpdate(BaseModel):
    """Schema for updating a venue setting."""
    setting_value: Optional[str] = None
    description: Optional[str] = None
    is_sensitive: Optional[bool] = None


class VenueSettingResponse(VenueSettingBase):
    """Response schema for venue setting."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venue_id: UUID
    created_at: datetime
    updated_at: datetime


class VenueSettingsBulkUpdate(BaseModel):
    """Schema for bulk updating venue settings."""
    settings: Dict[str, Any] = Field(..., description="Key-value pairs to update")
    category: Optional[str] = Field(default=None, description="Category for new settings")


# =============================================================================
# VENUE FEATURE SCHEMAS
# =============================================================================


class VenueFeatureBase(BaseModel):
    """Base schema for venue features."""
    feature_name: str = Field(..., max_length=50)
    is_enabled: bool = True
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    notes: Optional[str] = None


class VenueFeatureCreate(VenueFeatureBase):
    """Schema for creating a venue feature."""
    pass


class VenueFeatureUpdate(BaseModel):
    """Schema for updating a venue feature."""
    is_enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class VenueFeatureResponse(VenueFeatureBase):
    """Response schema for venue feature."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venue_id: UUID
    enabled_at: Optional[datetime]
    disabled_at: Optional[datetime]
    created_at: datetime


# =============================================================================
# VENUE AI CONFIG SCHEMAS
# =============================================================================


class VenueAIConfigBase(BaseModel):
    """Base schema for venue AI configuration."""
    ai_service: str = Field(..., max_length=50)
    is_enabled: bool = False
    strategy: AIStrategy = AIStrategy.MODERATE
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)
    notes: Optional[str] = None


class VenueAIConfigCreate(VenueAIConfigBase):
    """Schema for creating AI configuration."""
    pass


class VenueAIConfigUpdate(BaseModel):
    """Schema for updating AI configuration."""
    is_enabled: Optional[bool] = None
    strategy: Optional[AIStrategy] = None
    params: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class VenueAIConfigResponse(VenueAIConfigBase):
    """Response schema for AI configuration."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venue_id: UUID
    enabled_at: Optional[datetime]
    disabled_at: Optional[datetime]
    created_at: datetime


# =============================================================================
# VENUE PERFORMANCE SCHEMAS
# =============================================================================


class VenuePerformanceBase(BaseModel):
    """Base schema for venue performance metrics."""
    date: date

    # Revenue
    revenue: float = Field(default=0.0, ge=0)
    revenue_per_guest: Optional[float] = Field(default=None, ge=0)
    transaction_count: int = Field(default=0, ge=0)
    average_transaction: Optional[float] = Field(default=None, ge=0)

    # Customers
    guest_count: int = Field(default=0, ge=0)
    new_customers: int = Field(default=0, ge=0)
    returning_customers: int = Field(default=0, ge=0)
    party_bookings: int = Field(default=0, ge=0)

    # Operations
    labor_hours: Optional[float] = None
    labor_cost: Optional[float] = None
    labor_cost_percentage: Optional[float] = Field(default=None, ge=0, le=100)
    food_cost: Optional[float] = None
    food_cost_percentage: Optional[float] = Field(default=None, ge=0, le=100)
    food_waste_percentage: Optional[float] = Field(default=None, ge=0, le=100)

    # Satisfaction
    nps_score: Optional[float] = Field(default=None, ge=-100, le=100)
    review_count: int = Field(default=0, ge=0)
    average_rating: Optional[float] = Field(default=None, ge=0, le=5)

    # Capacity
    peak_occupancy: Optional[int] = None
    average_occupancy: Optional[float] = None
    capacity_utilization: Optional[float] = Field(default=None, ge=0, le=100)

    # Additional
    metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)


class VenuePerformanceCreate(VenuePerformanceBase):
    """Schema for creating performance record."""
    pass


class VenuePerformanceResponse(VenuePerformanceBase):
    """Response schema for performance record."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venue_id: UUID
    created_at: datetime


class VenueBenchmarkResponse(BaseModel):
    """Response schema for venue benchmarking."""
    venue_id: UUID
    venue_name: str
    period_start: date
    period_end: date

    # Rankings
    revenue_rank: int
    guest_count_rank: int
    revenue_per_guest_rank: int
    nps_rank: Optional[int] = None

    # Percentiles
    revenue_percentile: float
    guest_count_percentile: float

    # Averages
    avg_daily_revenue: float
    avg_daily_guests: int
    avg_revenue_per_guest: float
    avg_nps: Optional[float] = None

    # Comparison to network average
    revenue_vs_average: float  # Percentage above/below
    guests_vs_average: float


# =============================================================================
# VENUE CONTACT SCHEMAS
# =============================================================================


class VenueContactCreate(BaseModel):
    """Schema for creating venue contact."""
    contact_type: ContactType
    name: str = Field(..., max_length=255)
    title: Optional[str] = Field(default=None, max_length=100)
    email: EmailStr
    phone: str = Field(..., max_length=20)
    is_primary: bool = False
    notes: Optional[str] = None


class VenueContactResponse(VenueContactCreate):
    """Response schema for venue contact."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venue_id: UUID
    created_at: datetime


# =============================================================================
# VENUE IMAGE SCHEMAS
# =============================================================================


class VenueImageCreate(BaseModel):
    """Schema for creating venue image."""
    image_type: ImageType
    url: str = Field(..., max_length=500)
    alt_text: Optional[str] = Field(default=None, max_length=255)
    title: Optional[str] = Field(default=None, max_length=255)
    sort_order: int = 0
    is_active: bool = True


class VenueImageResponse(VenueImageCreate):
    """Response schema for venue image."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venue_id: UUID
    created_at: datetime


# =============================================================================
# MAIN VENUE SCHEMAS
# =============================================================================


class VenueBase(BaseModel):
    """Base schema for venue."""
    name: str = Field(..., min_length=1, max_length=255)
    legal_name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None

    # Location
    address_line1: str = Field(..., max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: str = Field(..., max_length=100)
    state: str = Field(..., max_length=100)
    postal_code: str = Field(..., max_length=20)
    country: str = Field(default="USA", max_length=100)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    timezone: str = Field(default="America/Chicago", max_length=50)

    # Contact
    phone: str = Field(..., max_length=20)
    email: EmailStr
    website: Optional[str] = Field(default=None, max_length=255)

    # Business
    tax_id: Optional[str] = Field(default=None, max_length=50)
    subscription_tier: SubscriptionTier = SubscriptionTier.STARTER
    total_capacity: Optional[int] = Field(default=None, ge=0)
    square_footage: Optional[int] = Field(default=None, ge=0)
    franchise_id: Optional[UUID] = None
    is_flagship: bool = False


class VenueCreate(VenueBase):
    """Schema for creating a venue."""
    slug: Optional[str] = Field(default=None, max_length=255)
    hours: Optional[List[VenueHoursCreate]] = None
    features: Optional[List[str]] = Field(
        default=None,
        description="List of feature names to enable"
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        """Validate slug format."""
        if v and not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", v):
            raise ValueError("Slug must be lowercase alphanumeric with hyphens")
        return v


class VenueUpdate(BaseModel):
    """Schema for updating a venue."""
    name: Optional[str] = Field(default=None, max_length=255)
    legal_name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None

    # Location
    address_line1: Optional[str] = Field(default=None, max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    country: Optional[str] = Field(default=None, max_length=100)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    timezone: Optional[str] = Field(default=None, max_length=50)

    # Contact
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[EmailStr] = None
    website: Optional[str] = Field(default=None, max_length=255)

    # Business
    tax_id: Optional[str] = Field(default=None, max_length=50)
    subscription_tier: Optional[SubscriptionTier] = None
    status: Optional[VenueStatus] = None
    total_capacity: Optional[int] = Field(default=None, ge=0)
    square_footage: Optional[int] = Field(default=None, ge=0)
    is_flagship: Optional[bool] = None
    extra_data: Optional[Dict[str, Any]] = None


class VenueResponse(VenueBase):
    """Basic response schema for venue."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    status: VenueStatus
    onboarding_status: OnboardingStatus
    go_live_date: Optional[date]
    created_at: datetime
    updated_at: datetime


class VenueListResponse(BaseModel):
    """Paginated list response for venues."""
    venues: List[VenueResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class VenueDetailResponse(VenueResponse):
    """Detailed response schema for venue with related data."""
    hours: List[VenueHoursResponse] = []
    special_hours: List[VenueSpecialHoursResponse] = []
    features: List[VenueFeatureResponse] = []
    ai_configs: List[VenueAIConfigResponse] = []
    contacts: List[VenueContactResponse] = []
    images: List[VenueImageResponse] = []
    extra_data: Optional[Dict[str, Any]] = None


# =============================================================================
# ONBOARDING SCHEMAS
# =============================================================================


class OnboardingStartRequest(BaseModel):
    """Request to start venue onboarding."""
    venue_id: UUID


class OnboardingStepRequest(BaseModel):
    """Request to complete an onboarding step."""
    step_name: str = Field(..., description="Name of the step being completed")
    step_data: Dict[str, Any] = Field(default_factory=dict, description="Step completion data")


class OnboardingStatusResponse(BaseModel):
    """Response for onboarding status check."""
    venue_id: UUID
    status: OnboardingStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    steps_completed: List[str]
    steps_remaining: List[str]
    progress_percentage: float
    expires_at: Optional[datetime] = None


# =============================================================================
# BULK OPERATION SCHEMAS
# =============================================================================


class BulkVenueCreate(BaseModel):
    """Request for bulk venue creation."""
    venues: List[VenueCreate] = Field(..., min_length=1, max_length=100)
    franchise_id: Optional[UUID] = None


class BulkVenueUpdate(BaseModel):
    """Request for bulk venue update."""
    venue_ids: List[UUID] = Field(..., min_length=1, max_length=100)
    update: VenueUpdate


class BulkSyncRequest(BaseModel):
    """Request for syncing configuration to multiple venues."""
    venue_ids: List[UUID] = Field(..., min_length=1, max_length=100)
    sync_features: bool = False
    sync_settings: bool = False
    sync_ai_config: bool = False
    settings_to_sync: Optional[Dict[str, Any]] = None
    features_to_sync: Optional[List[str]] = None


# =============================================================================
# FEATURE TOGGLE SCHEMAS
# =============================================================================


class VenueFeatureToggle(BaseModel):
    """Schema for toggling a feature on/off."""
    enabled: bool
    config: Optional[Dict[str, Any]] = None


class VenueFeaturesBulkToggle(BaseModel):
    """Schema for bulk toggling features."""
    features: Dict[str, bool] = Field(
        ...,
        description="Dictionary of feature_name: enabled pairs"
    )


# =============================================================================
# PERFORMANCE COMPARISON SCHEMAS
# =============================================================================


class VenuePerformanceMetric(BaseModel):
    """Single venue performance metric for comparison."""
    venue_id: UUID
    venue_name: str
    value: float
    rank: int


class PerformanceComparison(BaseModel):
    """Performance comparison response."""
    base_venue_id: UUID
    comparison_period_start: date
    comparison_period_end: date
    metrics: Dict[str, List[VenuePerformanceMetric]]
    summary: Dict[str, Any]


# =============================================================================
# ONBOARDING EXTENDED SCHEMAS
# =============================================================================


class OnboardingStepDetail(BaseModel):
    """Details for a single onboarding step."""
    name: str
    display_name: str
    description: str
    is_required: bool
    is_completed: bool
    is_skipped: bool
    completed_at: Optional[datetime] = None
    data: Optional[Dict[str, Any]] = None
    validation_errors: List[str] = []


class OnboardingStepUpdate(BaseModel):
    """Schema for updating an onboarding step."""
    completed: bool = True
    data: Optional[Dict[str, Any]] = None


class OnboardingProgressResponse(BaseModel):
    """Detailed onboarding progress response."""
    venue_id: UUID
    status: OnboardingStatus
    progress_percentage: float
    steps: List[OnboardingStepDetail]
    can_complete: bool
    blocking_steps: List[str]
    estimated_time_remaining: Optional[str] = None
