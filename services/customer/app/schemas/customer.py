"""
=============================================================================
FILE: schemas/customer.py
PURPOSE: Pydantic schemas for Customer Service API
=============================================================================

Defines request/response schemas for all customer-related endpoints.
Uses Pydantic v2 for validation and serialization.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ConfigDict, EmailStr

from app.models.customer import (
    CustomerType,
    SegmentType,
    RiskLevel,
    ActivityType,
    RelationshipType,
    Gender,
    VisitSource,
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
# CUSTOMER SCHEMAS
# =============================================================================


class CustomerBase(BaseModel):
    """Base schema for customers."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=20)
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    customer_type: CustomerType = CustomerType.B2C
    company_name: Optional[str] = Field(default=None, max_length=255)
    job_title: Optional[str] = Field(default=None, max_length=100)
    address_line1: Optional[str] = Field(default=None, max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    country: str = Field(default="USA", max_length=100)
    marketing_opt_in: bool = False
    sms_opt_in: bool = False
    email_opt_in: bool = True
    notes: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    acquisition_source: Optional[str] = Field(default=None, max_length=100)
    acquisition_campaign: Optional[str] = Field(default=None, max_length=100)


class CustomerCreate(CustomerBase):
    """Schema for creating a customer."""
    venue_id: UUID


class CustomerUpdate(BaseModel):
    """Schema for updating a customer."""
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=20)
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    customer_type: Optional[CustomerType] = None
    company_name: Optional[str] = Field(default=None, max_length=255)
    job_title: Optional[str] = Field(default=None, max_length=100)
    address_line1: Optional[str] = Field(default=None, max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    country: Optional[str] = Field(default=None, max_length=100)
    marketing_opt_in: Optional[bool] = None
    sms_opt_in: Optional[bool] = None
    email_opt_in: Optional[bool] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class CustomerResponse(CustomerBase):
    """Response schema for customer."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venue_id: UUID
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class CustomerDetailResponse(CustomerResponse):
    """Detailed customer response with related data."""
    segments: List["SegmentResponse"] = []
    ltv: Optional["LTVResponse"] = None
    churn_risk: Optional["ChurnRiskResponse"] = None
    preferences: List["PreferenceResponse"] = []
    recent_visits: List["VisitResponse"] = []
    total_visits: int = 0
    total_spend: Decimal = Decimal("0.00")


class CustomerListResponse(BaseModel):
    """Paginated list response for customers."""
    customers: List[CustomerResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CustomerSearch(BaseModel):
    """Search parameters for customers."""
    query: Optional[str] = Field(default=None, min_length=2)
    venue_id: Optional[UUID] = None
    customer_type: Optional[CustomerType] = None
    segment: Optional[SegmentType] = None
    is_active: Optional[bool] = None
    has_email: Optional[bool] = None
    has_phone: Optional[bool] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None


# =============================================================================
# FAMILY SCHEMAS
# =============================================================================


class FamilyMemberCreate(BaseModel):
    """Schema for adding a family member."""
    customer_id: UUID
    relation_type: RelationshipType = RelationshipType.OTHER


class FamilyMemberResponse(BaseModel):
    """Response for family member."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    relation_type: RelationshipType
    customer: Optional[CustomerResponse] = None


class FamilyBase(BaseModel):
    """Base schema for families."""
    family_name: str = Field(..., min_length=1, max_length=255)
    notes: Optional[str] = None


class FamilyCreate(FamilyBase):
    """Schema for creating a family."""
    venue_id: UUID
    primary_customer_id: UUID
    members: Optional[List[FamilyMemberCreate]] = None


class FamilyUpdate(BaseModel):
    """Schema for updating a family."""
    family_name: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None


class FamilyResponse(FamilyBase):
    """Response schema for family."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venue_id: UUID
    primary_customer_id: UUID
    members: List[FamilyMemberResponse] = []
    created_at: datetime
    updated_at: datetime


# =============================================================================
# VISIT SCHEMAS
# =============================================================================


class ActivityBase(BaseModel):
    """Base schema for activities."""
    activity_type: ActivityType
    activity_id: Optional[UUID] = None
    activity_name: Optional[str] = Field(default=None, max_length=255)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(default=None, ge=0)
    amount_spent: Decimal = Field(default=Decimal("0.00"), ge=0)
    satisfaction_score: Optional[int] = Field(default=None, ge=1, le=10)


class ActivityCreate(ActivityBase):
    """Schema for creating an activity."""
    visit_id: UUID


class ActivityResponse(ActivityBase):
    """Response schema for activity."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class VisitBase(BaseModel):
    """Base schema for visits."""
    check_in_time: datetime
    source: VisitSource = VisitSource.WALK_IN
    guest_count: int = Field(default=1, ge=1)
    child_count: int = Field(default=0, ge=0)
    adult_count: int = Field(default=1, ge=0)
    booking_id: Optional[UUID] = None
    notes: Optional[str] = None


class VisitCreate(VisitBase):
    """Schema for creating a visit."""
    customer_id: UUID
    venue_id: UUID
    activities: Optional[List[ActivityBase]] = None


class VisitUpdate(BaseModel):
    """Schema for updating a visit."""
    total_spend: Optional[Decimal] = Field(default=None, ge=0)
    guest_count: Optional[int] = Field(default=None, ge=1)
    child_count: Optional[int] = Field(default=None, ge=0)
    adult_count: Optional[int] = Field(default=None, ge=0)
    satisfaction_score: Optional[int] = Field(default=None, ge=1, le=10)
    feedback: Optional[str] = None
    notes: Optional[str] = None


class VisitCheckout(BaseModel):
    """Schema for checking out a visit."""
    check_out_time: Optional[datetime] = None
    total_spend: Optional[Decimal] = Field(default=None, ge=0)
    satisfaction_score: Optional[int] = Field(default=None, ge=1, le=10)
    feedback: Optional[str] = None


class VisitResponse(VisitBase):
    """Response schema for visit."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    venue_id: UUID
    check_out_time: Optional[datetime]
    total_spend: Decimal
    satisfaction_score: Optional[int]
    feedback: Optional[str]
    created_at: datetime


class VisitDetailResponse(VisitResponse):
    """Detailed visit response with activities."""
    activities: List[ActivityResponse] = []
    duration_minutes: Optional[int] = None


class VisitListResponse(BaseModel):
    """Paginated list response for visits."""
    visits: List[VisitResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# SEGMENT SCHEMAS
# =============================================================================


class SegmentResponse(BaseModel):
    """Response schema for segment."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    segment_type: SegmentType
    score: Decimal
    assigned_at: datetime
    expires_at: Optional[datetime]


class SegmentAssignment(BaseModel):
    """Schema for manual segment assignment."""
    customer_id: UUID
    segment_type: SegmentType
    score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    expires_at: Optional[datetime] = None


class SegmentCustomersResponse(BaseModel):
    """Response for customers in a segment."""
    segment_type: SegmentType
    customers: List[CustomerResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# LTV SCHEMAS
# =============================================================================


class LTVResponse(BaseModel):
    """Response schema for LTV."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    calculated_ltv: Decimal
    visit_frequency: Decimal
    avg_spend: Decimal
    expected_lifespan_months: int
    total_visits: int
    total_revenue: Decimal
    first_visit_date: Optional[date]
    last_visit_date: Optional[date]
    last_updated: datetime


class LTVCalculation(BaseModel):
    """Schema for LTV calculation request."""
    customer_id: UUID
    force_recalculate: bool = False


# =============================================================================
# CHURN SCHEMAS
# =============================================================================


class ChurnRiskResponse(BaseModel):
    """Response schema for churn risk."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    risk_score: Decimal
    risk_level: RiskLevel
    days_since_last_visit: int
    visit_frequency_trend: Optional[str]
    spend_trend: Optional[str]
    factors_json: Optional[Dict[str, Any]]
    predicted_churn_date: Optional[date]
    confidence: Decimal
    calculated_at: datetime


class ChurnRiskCalculation(BaseModel):
    """Schema for churn risk calculation request."""
    customer_id: UUID
    force_recalculate: bool = False


# =============================================================================
# PREFERENCE SCHEMAS
# =============================================================================


class PreferenceBase(BaseModel):
    """Base schema for preferences."""
    preference_type: str = Field(..., max_length=50)
    preference_value: str
    confidence_score: Decimal = Field(default=Decimal("50.00"), ge=0, le=100)
    is_stated: bool = False


class PreferenceCreate(PreferenceBase):
    """Schema for creating a preference."""
    customer_id: UUID


class PreferenceResponse(PreferenceBase):
    """Response schema for preference."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    is_inferred: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# ANALYTICS SCHEMAS
# =============================================================================


class VisitStats(BaseModel):
    """Visit statistics."""
    period_start: date
    period_end: date
    total_visits: int
    unique_customers: int
    new_customers: int
    returning_customers: int
    avg_visit_duration_minutes: float
    avg_spend_per_visit: Decimal
    total_revenue: Decimal
    avg_party_size: float
    peak_days: List[Dict[str, Any]]
    peak_hours: List[Dict[str, Any]]


class SegmentStats(BaseModel):
    """Segment statistics."""
    segment_type: SegmentType
    customer_count: int
    percentage: float
    avg_ltv: Decimal
    avg_visits: float
    avg_spend: Decimal
    trend: str  # growing, declining, stable


class ChurnStats(BaseModel):
    """Churn statistics."""
    period_start: date
    period_end: date
    total_at_risk: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    churned_count: int
    churn_rate: float
    win_back_count: int
    avg_days_to_churn: float


class CustomerAnalytics(BaseModel):
    """Comprehensive customer analytics."""
    period_start: date
    period_end: date
    total_customers: int
    active_customers: int
    new_customers: int
    avg_ltv: Decimal
    total_revenue: Decimal
    visit_stats: VisitStats
    segment_breakdown: List[SegmentStats]
    churn_stats: ChurnStats
    top_customers: List[Dict[str, Any]]
    growth_rate: float


# Forward references for nested schemas
CustomerDetailResponse.model_rebuild()
