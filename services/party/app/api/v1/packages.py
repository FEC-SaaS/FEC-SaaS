"""
=============================================================================
FILE: api/v1/packages.py
PURPOSE: Party package CRUD API endpoints
=============================================================================
"""

from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.schemas.party import (
    PartyPackageCreate,
    PartyPackageUpdate,
    PartyPackageResponse,
    PartyPackageListResponse,
    PartyPackageDetailResponse,
    PaginationParams,
)
from app.services.package_service import PackageService
from app.core.dependencies import get_package_service, get_current_user

router = APIRouter()


@router.get("", response_model=PartyPackageListResponse)
async def list_packages(
    venue_id: UUID = Query(..., description="Venue ID to list packages for"),
    package_type: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=True),
    is_featured: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="display_order"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    package_service: PackageService = Depends(get_package_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    List all party packages for a venue.

    Supports filtering by type, active status, and featured flag.
    """
    pagination = PaginationParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    packages, total = await package_service.list_packages(
        venue_id=venue_id,
        pagination=pagination,
        package_type=package_type,
        is_active=is_active,
        is_featured=is_featured,
    )

    total_pages = (total + page_size - 1) // page_size

    return PartyPackageListResponse(
        packages=[PartyPackageResponse.model_validate(p) for p in packages],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=PartyPackageResponse, status_code=status.HTTP_201_CREATED)
async def create_package(
    package_data: PartyPackageCreate,
    package_service: PackageService = Depends(get_package_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create a new party package.

    The package will be created in active status by default.
    """
    package = await package_service.create_package(package_data)
    return PartyPackageResponse.model_validate(package)


@router.get("/{package_id}", response_model=PartyPackageDetailResponse)
async def get_package(
    package_id: UUID,
    package_service: PackageService = Depends(get_package_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get package by ID with default addons.
    """
    package = await package_service.get_package(package_id)
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )
    return PartyPackageDetailResponse.model_validate(package)


@router.put("/{package_id}", response_model=PartyPackageResponse)
async def update_package(
    package_id: UUID,
    update_data: PartyPackageUpdate,
    package_service: PackageService = Depends(get_package_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Update package information."""
    package = await package_service.update_package(package_id, update_data)
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )
    return PartyPackageResponse.model_validate(package)


@router.delete("/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_package(
    package_id: UUID,
    hard_delete: bool = Query(default=False),
    package_service: PackageService = Depends(get_package_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Delete a package.

    By default performs soft delete (sets is_active=false).
    Set hard_delete=true for permanent deletion.
    """
    deleted = await package_service.delete_package(package_id, hard_delete=hard_delete)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )


@router.post("/{package_id}/addons/{addon_id}", status_code=status.HTTP_201_CREATED)
async def add_default_addon(
    package_id: UUID,
    addon_id: UUID,
    quantity: int = Query(default=1, ge=1),
    is_included_free: bool = Query(default=True),
    discount_percentage: float = Query(default=0.0, ge=0, le=100),
    package_service: PackageService = Depends(get_package_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Add a default addon to a package."""
    result = await package_service.add_default_addon(
        package_id=package_id,
        addon_id=addon_id,
        quantity=quantity,
        is_included_free=is_included_free,
        discount_percentage=discount_percentage,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package or addon not found",
        )
    return {"message": "Addon added to package"}


@router.delete("/{package_id}/addons/{addon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_default_addon(
    package_id: UUID,
    addon_id: UUID,
    package_service: PackageService = Depends(get_package_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Remove a default addon from a package."""
    deleted = await package_service.remove_default_addon(package_id, addon_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package addon not found",
        )
