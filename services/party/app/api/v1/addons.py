"""
=============================================================================
FILE: api/v1/addons.py
PURPOSE: Party addon CRUD API endpoints
=============================================================================
"""

from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.schemas.party import (
    PartyAddonCreate,
    PartyAddonUpdate,
    PartyAddonResponse,
    PartyAddonListResponse,
    PaginationParams,
)
from app.models.party import AddonType
from app.services.addon_service import AddonService
from app.core.dependencies import get_addon_service, get_current_user

router = APIRouter()


@router.get("", response_model=PartyAddonListResponse)
async def list_addons(
    venue_id: UUID = Query(..., description="Venue ID to list addons for"),
    addon_type: Optional[AddonType] = Query(default=None),
    is_active: Optional[bool] = Query(default=True),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="display_order"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    addon_service: AddonService = Depends(get_addon_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    List all party addons for a venue.

    Supports filtering by type and active status.
    """
    pagination = PaginationParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    addons, total = await addon_service.list_addons(
        venue_id=venue_id,
        pagination=pagination,
        addon_type=addon_type,
        is_active=is_active,
    )

    total_pages = (total + page_size - 1) // page_size

    return PartyAddonListResponse(
        addons=[PartyAddonResponse.model_validate(a) for a in addons],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=PartyAddonResponse, status_code=status.HTTP_201_CREATED)
async def create_addon(
    addon_data: PartyAddonCreate,
    addon_service: AddonService = Depends(get_addon_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create a new party addon.

    The addon will be created in active status by default.
    """
    addon = await addon_service.create_addon(addon_data)
    return PartyAddonResponse.model_validate(addon)


@router.get("/upsell-suggestions", response_model=list[PartyAddonResponse])
async def get_upsell_suggestions(
    venue_id: UUID = Query(..., description="Venue ID"),
    package_id: Optional[UUID] = Query(default=None),
    limit: int = Query(default=5, ge=1, le=20),
    addon_service: AddonService = Depends(get_addon_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get upsell addon suggestions for AI-powered recommendations.

    Returns addons sorted by upsell priority.
    """
    addons = await addon_service.get_upsell_suggestions(
        venue_id=venue_id,
        package_id=package_id,
        limit=limit,
    )
    return [PartyAddonResponse.model_validate(a) for a in addons]


@router.get("/{addon_id}", response_model=PartyAddonResponse)
async def get_addon(
    addon_id: UUID,
    addon_service: AddonService = Depends(get_addon_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get addon by ID."""
    addon = await addon_service.get_addon(addon_id)
    if not addon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Addon not found",
        )
    return PartyAddonResponse.model_validate(addon)


@router.put("/{addon_id}", response_model=PartyAddonResponse)
async def update_addon(
    addon_id: UUID,
    update_data: PartyAddonUpdate,
    addon_service: AddonService = Depends(get_addon_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Update addon information."""
    addon = await addon_service.update_addon(addon_id, update_data)
    if not addon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Addon not found",
        )
    return PartyAddonResponse.model_validate(addon)


@router.delete("/{addon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_addon(
    addon_id: UUID,
    hard_delete: bool = Query(default=False),
    addon_service: AddonService = Depends(get_addon_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Delete an addon.

    By default performs soft delete (sets is_active=false).
    Set hard_delete=true for permanent deletion.
    """
    deleted = await addon_service.delete_addon(addon_id, hard_delete=hard_delete)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Addon not found",
        )
