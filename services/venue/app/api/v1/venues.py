"""
=============================================================================
FILE: api/v1/venues.py
PURPOSE: Venue CRUD API endpoints
=============================================================================
"""

from typing import Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.schemas.venue import (
    VenueCreate,
    VenueUpdate,
    VenueResponse,
    VenueListResponse,
    VenueDetailResponse,
    VenueFilters,
    PaginationParams,
    BulkVenueCreate,
    BulkVenueUpdate,
)
from app.models.venue import VenueStatus
from app.services.venue_service import VenueService
from app.core.dependencies import get_venue_service, get_current_user

router = APIRouter()


@router.get("", response_model=VenueListResponse)
async def list_venues(
    # Filters
    status: VenueStatus = Query(default=None),
    subscription_tier: str = Query(default=None),
    city: str = Query(default=None),
    state: str = Query(default=None),
    franchise_id: UUID = Query(default=None),
    search: str = Query(default=None),
    has_feature: str = Query(default=None),
    # Pagination
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    # Dependencies
    venue_service: VenueService = Depends(get_venue_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    List all venues with filtering and pagination.

    Supports filtering by status, subscription tier, location, and features.
    """
    filters = VenueFilters(
        status=status,
        subscription_tier=subscription_tier,
        city=city,
        state=state,
        franchise_id=franchise_id,
        search=search,
        has_feature=has_feature,
    )
    pagination = PaginationParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    venues, total = await venue_service.list_venues(filters, pagination)

    total_pages = (total + page_size - 1) // page_size

    return VenueListResponse(
        venues=[VenueResponse.model_validate(v) for v in venues],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=VenueResponse, status_code=status.HTTP_201_CREATED)
async def create_venue(
    venue_data: VenueCreate,
    venue_service: VenueService = Depends(get_venue_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create a new venue.

    The venue will be created with PENDING status and NOT_STARTED onboarding.
    """
    venue = await venue_service.create_venue(venue_data)
    return VenueResponse.model_validate(venue)


@router.get("/{venue_id}", response_model=VenueDetailResponse)
async def get_venue(
    venue_id: UUID,
    venue_service: VenueService = Depends(get_venue_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get venue by ID with all related data.

    Returns venue details including hours, features, AI config, etc.
    """
    venue = await venue_service.get_venue(venue_id)
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venue not found",
        )
    return VenueDetailResponse.model_validate(venue)


@router.get("/slug/{slug}", response_model=VenueResponse)
async def get_venue_by_slug(
    slug: str,
    venue_service: VenueService = Depends(get_venue_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get venue by slug."""
    venue = await venue_service.get_venue_by_slug(slug)
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venue not found",
        )
    return VenueResponse.model_validate(venue)


@router.put("/{venue_id}", response_model=VenueResponse)
async def update_venue(
    venue_id: UUID,
    update_data: VenueUpdate,
    venue_service: VenueService = Depends(get_venue_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Update venue information."""
    venue = await venue_service.update_venue(venue_id, update_data)
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venue not found",
        )
    return VenueResponse.model_validate(venue)


@router.delete("/{venue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_venue(
    venue_id: UUID,
    hard_delete: bool = Query(default=False),
    venue_service: VenueService = Depends(get_venue_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Delete a venue.

    By default performs soft delete. Set hard_delete=true for permanent deletion.
    """
    deleted = await venue_service.delete_venue(venue_id, hard_delete=hard_delete)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venue not found",
        )


@router.patch("/{venue_id}/status", response_model=VenueResponse)
async def update_venue_status(
    venue_id: UUID,
    new_status: VenueStatus,
    venue_service: VenueService = Depends(get_venue_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Update venue status."""
    venue = await venue_service.update_status(venue_id, new_status)
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venue not found",
        )
    return VenueResponse.model_validate(venue)


# Franchise endpoints
@router.get("/franchise/{franchise_id}", response_model=list[VenueResponse])
async def list_franchise_venues(
    franchise_id: UUID,
    venue_service: VenueService = Depends(get_venue_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """List all venues for a franchise."""
    venues = await venue_service.list_franchise_venues(franchise_id)
    return [VenueResponse.model_validate(v) for v in venues]


# Bulk operations
@router.post("/bulk", response_model=list[VenueResponse], status_code=status.HTTP_201_CREATED)
async def bulk_create_venues(
    data: BulkVenueCreate,
    venue_service: VenueService = Depends(get_venue_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Create multiple venues at once."""
    venues = await venue_service.bulk_create_venues(
        data.venues,
        franchise_id=data.franchise_id,
    )
    return [VenueResponse.model_validate(v) for v in venues]


@router.patch("/bulk", response_model=dict)
async def bulk_update_venues(
    data: BulkVenueUpdate,
    venue_service: VenueService = Depends(get_venue_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Update multiple venues at once."""
    count = await venue_service.bulk_update_venues(data.venue_ids, data.update)
    return {"updated": count, "requested": len(data.venue_ids)}


# Health check (public)
@router.get("/health", include_in_schema=False)
async def health_check():
    """Venue service health check."""
    return {"status": "healthy", "service": "venue"}
