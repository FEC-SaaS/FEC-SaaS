"""
=============================================================================
FILE: api/v1/settings.py
PURPOSE: Venue settings management endpoints
=============================================================================
"""

from typing import List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.schemas.venue import (
    VenueSettingCreate,
    VenueSettingUpdate,
    VenueSettingResponse,
    VenueSettingsBulkUpdate,
)
from app.services.settings_service import SettingsService
from app.core.dependencies import get_settings_service, get_current_user

router = APIRouter()


@router.get("/{venue_id}/settings", response_model=List[VenueSettingResponse])
async def get_venue_settings(
    venue_id: UUID,
    category: str = Query(default=None),
    include_sensitive: bool = Query(default=False),
    settings_service: SettingsService = Depends(get_settings_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get all settings for a venue.

    Optionally filter by category. Sensitive settings are excluded by default.
    """
    return await settings_service.get_all_settings(
        venue_id,
        category=category,
        include_sensitive=include_sensitive,
    )


@router.get("/{venue_id}/settings/dict")
async def get_settings_dict(
    venue_id: UUID,
    category: str = Query(default=None),
    settings_service: SettingsService = Depends(get_settings_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get settings as a key-value dictionary."""
    return await settings_service.get_settings_as_dict(venue_id, category)


@router.get("/{venue_id}/settings/{setting_key}", response_model=VenueSettingResponse)
async def get_setting(
    venue_id: UUID,
    setting_key: str,
    settings_service: SettingsService = Depends(get_settings_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get a specific setting by key."""
    setting = await settings_service.get_setting(venue_id, setting_key)
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found",
        )
    return setting


@router.post(
    "/{venue_id}/settings/{setting_key}",
    response_model=VenueSettingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_or_update_setting(
    venue_id: UUID,
    setting_key: str,
    setting_data: VenueSettingCreate,
    settings_service: SettingsService = Depends(get_settings_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Create or update a setting."""
    # Ensure key matches URL
    setting_data.setting_key = setting_key
    return await settings_service.set_setting(venue_id, setting_data)


@router.patch("/{venue_id}/settings/{setting_key}", response_model=VenueSettingResponse)
async def update_setting(
    venue_id: UUID,
    setting_key: str,
    update_data: VenueSettingUpdate,
    settings_service: SettingsService = Depends(get_settings_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Update an existing setting."""
    setting = await settings_service.update_setting(venue_id, setting_key, update_data)
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found",
        )
    return setting


@router.delete("/{venue_id}/settings/{setting_key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_setting(
    venue_id: UUID,
    setting_key: str,
    settings_service: SettingsService = Depends(get_settings_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Delete a setting."""
    deleted = await settings_service.delete_setting(venue_id, setting_key)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found",
        )


@router.put("/{venue_id}/settings")
async def bulk_update_settings(
    venue_id: UUID,
    bulk_data: VenueSettingsBulkUpdate,
    settings_service: SettingsService = Depends(get_settings_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Bulk create/update settings."""
    count = await settings_service.bulk_set_settings(
        venue_id,
        bulk_data.settings,
        category=bulk_data.category,
    )
    return {"updated": count}
