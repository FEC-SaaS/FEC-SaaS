"""
=============================================================================
FILE: api/v1/customers.py
PURPOSE: Customer management API endpoints
=============================================================================
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

# OpenAPI Tags
TAGS = ["Customers"]

from app.core.dependencies import get_db, get_current_user
from app.services.customer_service import CustomerService
from app.services.segmentation_service import SegmentationService
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerDetailResponse,
    CustomerListResponse,
    CustomerSearch,
    PreferenceCreate,
    PreferenceResponse,
    PaginationParams,
)
from app.models.customer import CustomerType, SegmentType

router = APIRouter(tags=TAGS)


@router.get(
    "/",
    response_model=CustomerListResponse,
    summary="List customers",
    description="""
    Retrieve a paginated list of customers for a venue.

    Supports filtering by:
    - **customer_type**: Filter by B2C or B2B customers
    - **segment**: Filter by customer segment (VIP, Premium, Standard, etc.)
    - **is_active**: Filter by active/inactive status

    Results are sorted by the specified field (default: created_at desc).
    """,
    responses={
        200: {"description": "List of customers with pagination info"},
        401: {"description": "Unauthorized - Invalid or missing authentication"},
    },
)
async def list_customers(
    venue_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    customer_type: Optional[CustomerType] = None,
    segment: Optional[SegmentType] = None,
    is_active: Optional[bool] = True,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List customers for a venue with filtering and pagination."""
    service = CustomerService(db)
    pagination = PaginationParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    customers, total = await service.list_customers(
        venue_id=venue_id,
        pagination=pagination,
        customer_type=customer_type,
        segment=segment,
        is_active=is_active,
    )

    total_pages = (total + page_size - 1) // page_size

    return CustomerListResponse(
        customers=[CustomerResponse.model_validate(c) for c in customers],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "/",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer",
    description="""
    Create a new customer profile.

    **Required fields:**
    - venue_id: The venue this customer belongs to
    - first_name, last_name: Customer name

    **Optional fields:**
    - email, phone: Contact information (must be unique per venue)
    - customer_type: B2C (individual) or B2B (corporate)
    - address fields, marketing preferences, etc.

    A new customer is automatically:
    - Assigned to the "NEW" segment
    - Initialized with LTV and churn risk tracking

    **Events published:** `customer.created`
    """,
    responses={
        201: {"description": "Customer created successfully"},
        409: {"description": "Customer with this email/phone already exists"},
        422: {"description": "Validation error"},
    },
)
async def create_customer(
    customer_data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new customer."""
    service = CustomerService(db)

    # Check for existing customer with same email/phone
    if customer_data.email:
        existing = await service.get_customer_by_email(
            customer_data.venue_id,
            customer_data.email,
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer with this email already exists",
            )

    if customer_data.phone:
        existing = await service.get_customer_by_phone(
            customer_data.venue_id,
            customer_data.phone,
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer with this phone already exists",
            )

    customer = await service.create_customer(customer_data)
    return CustomerResponse.model_validate(customer)


@router.get(
    "/search",
    response_model=CustomerListResponse,
    summary="Search customers",
    description="""
    Search customers by various criteria.

    **Search options:**
    - **query**: Free text search across name, email, phone, company
    - **customer_type**: Filter by B2C or B2B
    - **segment**: Filter by segment type
    - **is_active**: Filter by active status

    Results are paginated and can be sorted.
    """,
)
async def search_customers(
    query: Optional[str] = None,
    venue_id: Optional[UUID] = None,
    customer_type: Optional[CustomerType] = None,
    segment: Optional[SegmentType] = None,
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Search customers by various criteria."""
    service = CustomerService(db)
    pagination = PaginationParams(page=page, page_size=page_size)

    search = CustomerSearch(
        query=query,
        venue_id=venue_id,
        customer_type=customer_type,
        segment=segment,
        is_active=is_active,
    )

    customers, total = await service.search_customers(search, pagination)
    total_pages = (total + page_size - 1) // page_size

    return CustomerListResponse(
        customers=[CustomerResponse.model_validate(c) for c in customers],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/at-risk",
    summary="Get at-risk customers",
    description="""
    Get customers at risk of churning.

    Returns customers with HIGH or CRITICAL churn risk by default.
    Optionally filter by specific risk level.

    Useful for:
    - Targeted win-back campaigns
    - Proactive customer outreach
    - Churn prevention initiatives
    """,
)
async def get_at_risk_customers(
    venue_id: UUID,
    risk_level: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get customers at risk of churning."""
    from app.models.customer import RiskLevel

    service = CustomerService(db)
    level = RiskLevel(risk_level) if risk_level else None
    customers = await service.get_at_risk_customers(venue_id, level, limit)

    return [CustomerResponse.model_validate(c) for c in customers]


@router.get("/{customer_id}", response_model=CustomerDetailResponse)
async def get_customer(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get customer details by ID."""
    service = CustomerService(db)
    customer = await service.get_customer(customer_id)

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    # Get additional data
    total_visits = await service.get_customer_visits_count(customer_id)
    total_spend = await service.get_customer_total_spend(customer_id)

    response = CustomerDetailResponse.model_validate(customer)
    response.total_visits = total_visits
    response.total_spend = total_spend

    return response


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    update_data: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update customer information."""
    service = CustomerService(db)
    customer = await service.update_customer(customer_id, update_data)

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    return CustomerResponse.model_validate(customer)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: UUID,
    gdpr_delete: bool = Query(False, description="GDPR-compliant data deletion"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a customer (soft delete or GDPR compliant)."""
    service = CustomerService(db)
    deleted = await service.delete_customer(customer_id, gdpr_delete)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )


@router.get("/{customer_id}/preferences", response_model=list[PreferenceResponse])
async def get_customer_preferences(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get customer preferences."""
    service = CustomerService(db)
    preferences = await service.get_customer_preferences(customer_id)
    return [PreferenceResponse.model_validate(p) for p in preferences]


@router.post(
    "/{customer_id}/preferences",
    response_model=PreferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_customer_preference(
    customer_id: UUID,
    preference_type: str,
    preference_value: str,
    is_stated: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add a preference for a customer."""
    service = CustomerService(db)
    preference = await service.add_customer_preference(
        customer_id=customer_id,
        preference_type=preference_type,
        preference_value=preference_value,
        is_stated=is_stated,
    )
    return PreferenceResponse.model_validate(preference)


@router.post("/{customer_id}/winback")
async def trigger_winback_campaign(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Trigger a win-back campaign for a customer."""
    # This would integrate with the notification/marketing service
    return {
        "status": "campaign_triggered",
        "customer_id": str(customer_id),
        "message": "Win-back campaign initiated",
    }


@router.post("/recalculate-segments")
async def recalculate_segments(
    venue_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Trigger segment recalculation for all customers."""
    service = SegmentationService(db)
    count = await service.recalculate_all_segments(venue_id)

    return {
        "status": "completed",
        "customers_processed": count,
    }
