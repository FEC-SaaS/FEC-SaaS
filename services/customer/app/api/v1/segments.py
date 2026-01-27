"""
=============================================================================
FILE: api/v1/segments.py
PURPOSE: Customer segmentation API endpoints
=============================================================================
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user
from app.services.segmentation_service import SegmentationService
from app.schemas.customer import (
    SegmentResponse,
    SegmentAssignment,
    CustomerResponse,
    PaginationParams,
)
from app.models.customer import SegmentType

# OpenAPI Tags
TAGS = ["Segments"]

router = APIRouter(tags=TAGS)


@router.get(
    "/{segment_type}/customers",
    summary="Get customers by segment",
    description="""
    Retrieve all customers belonging to a specific segment.

    **Available segments:**
    - **VIP**: Top-tier customers with highest LTV and visit frequency
    - **PREMIUM**: High-value customers with strong engagement
    - **STANDARD**: Regular customers with moderate engagement
    - **NEW**: Recently acquired customers (< 30 days)
    - **AT_RISK**: Customers showing early signs of disengagement
    - **CHURNED**: Previously active customers who stopped visiting
    - **INACTIVE**: Customers with no recent activity

    Segments are calculated based on:
    - Visit frequency
    - Total spend / LTV
    - Days since last visit
    - Engagement patterns

    **Events published:** `segment.changed` when a customer moves between segments
    """,
    responses={
        200: {"description": "List of customers in segment with pagination"},
        401: {"description": "Unauthorized"},
    },
)
async def get_customers_by_segment(
    segment_type: SegmentType,
    venue_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get customers in a specific segment."""
    service = SegmentationService(db)
    pagination = PaginationParams(page=page, page_size=page_size)

    customers, total = await service.get_customers_by_segment(
        venue_id=venue_id,
        segment_type=segment_type,
        pagination=pagination,
    )

    total_pages = (total + page_size - 1) // page_size

    return {
        "segment_type": segment_type.value,
        "customers": [CustomerResponse.model_validate(c) for c in customers],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get(
    "/customer/{customer_id}",
    response_model=SegmentResponse,
    summary="Get customer's segment",
    description="""
    Retrieve the current segment assignment for a specific customer.

    Returns:
    - segment_type: The current segment
    - score: Numeric score within the segment (0-100)
    - assigned_at: When the segment was assigned
    - expires_at: Expiration date for temporary segments (e.g., VIP trials)
    """,
    responses={
        200: {"description": "Customer's current segment"},
        404: {"description": "Customer segment not found"},
    },
)
async def get_customer_segment(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get the current segment for a customer."""
    service = SegmentationService(db)
    segment = await service.get_customer_segment(customer_id)

    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer segment not found",
        )

    return SegmentResponse.model_validate(segment)


@router.post(
    "/assign",
    response_model=SegmentResponse,
    summary="Manually assign segment",
    description="""
    Manually assign a segment to a customer.

    Use this for:
    - **VIP upgrades**: Manually promote a customer to VIP status
    - **Trial periods**: Give temporary premium access
    - **Override automation**: Force a specific segment regardless of metrics

    **Required:**
    - customer_id: The customer to assign
    - segment_type: The segment to assign

    **Optional:**
    - score: Custom score (0-100)
    - expires_at: Expiration date for temporary assignments

    **Note**: Manual assignments will be overwritten by the next automatic
    recalculation unless you disable auto-segmentation for the customer.
    """,
    responses={
        200: {"description": "Segment assigned successfully"},
        404: {"description": "Customer not found"},
        422: {"description": "Validation error"},
    },
)
async def assign_segment(
    assignment: SegmentAssignment,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Manually assign a segment to a customer."""
    service = SegmentationService(db)
    segment = await service.assign_segment(
        customer_id=assignment.customer_id,
        segment_type=assignment.segment_type,
        score=assignment.score or 0,
        expires_at=assignment.expires_at,
    )
    return SegmentResponse.model_validate(segment)


@router.post(
    "/customer/{customer_id}/recalculate",
    response_model=SegmentResponse,
    summary="Recalculate customer segment",
    description="""
    Trigger immediate segment recalculation for a specific customer.

    The segmentation algorithm considers:
    - **Visit frequency**: How often the customer visits
    - **Total spend**: Lifetime revenue from the customer
    - **Average spend**: Per-visit average
    - **Days since last visit**: Recency of engagement
    - **Visit trends**: Is engagement increasing or decreasing?

    **Segment thresholds (configurable):**
    - VIP: Top 5% by LTV + visits 4+/month
    - Premium: Top 20% by LTV + visits 2+/month
    - At-Risk: No visit in 45-90 days
    - Churned: No visit in 90+ days
    - Inactive: No visit in 180+ days

    Publishes `segment.changed` event if the segment changes.
    """,
    responses={
        200: {"description": "Recalculated segment"},
        404: {"description": "Customer not found"},
    },
)
async def recalculate_customer_segment(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Recalculate segment for a specific customer."""
    service = SegmentationService(db)
    segment = await service.recalculate_customer_segment(customer_id)
    return SegmentResponse.model_validate(segment)


@router.get(
    "/stats",
    summary="Get segment statistics",
    description="""
    Get segment distribution statistics for a venue.

    Returns counts for each segment:
    - Number of customers per segment
    - Percentage of total customer base
    - Segment health indicators

    Useful for:
    - Dashboard widgets
    - Segment health monitoring
    - Marketing campaign targeting
    """,
    responses={
        200: {"description": "Segment distribution statistics"},
    },
)
async def get_segment_stats(
    venue_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get segment distribution statistics."""
    service = SegmentationService(db)
    stats = await service.get_segment_stats(venue_id)
    return {"venue_id": str(venue_id), "segments": stats}
