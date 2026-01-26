"""
=============================================================================
FILE: api/v1/features.py
PURPOSE: Venue feature management endpoints
=============================================================================
"""

from typing import List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.venue import (
    VenueFeatureToggle,
    VenueFeatureResponse,
    VenueFeaturesBulkToggle,
)
from app.services.feature_service import FeatureService
from app.core.dependencies import get_feature_service, get_current_user

router = APIRouter()


@router.get("/{venue_id}/features", response_model=List[VenueFeatureResponse])
async def get_venue_features(
    venue_id: UUID,
    feature_service: FeatureService = Depends(get_feature_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get all features for a venue with their enabled status."""
    return await feature_service.get_features(venue_id)


@router.get("/{venue_id}/features/available")
async def get_available_features(
    venue_id: UUID,
    feature_service: FeatureService = Depends(get_feature_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get features available for venue's subscription tier.

    Returns both enabled and available features based on subscription.
    """
    available = await feature_service.get_available_features(venue_id)
    enabled = await feature_service.get_features(venue_id)
    enabled_names = {f.feature_name for f in enabled if f.enabled}

    return {
        "venue_id": venue_id,
        "available_features": list(available),
        "enabled_features": list(enabled_names),
        "can_enable": list(available - enabled_names),
    }


@router.post("/{venue_id}/features/{feature_name}", response_model=VenueFeatureResponse)
async def toggle_feature(
    venue_id: UUID,
    feature_name: str,
    toggle_data: VenueFeatureToggle,
    feature_service: FeatureService = Depends(get_feature_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Enable or disable a feature for a venue.

    Feature must be available for the venue's subscription tier.
    """
    feature = await feature_service.toggle_feature(
        venue_id,
        feature_name,
        toggle_data.enabled,
        config=toggle_data.config,
    )
    if not feature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feature not available for this subscription tier",
        )
    return feature


@router.put("/{venue_id}/features")
async def bulk_toggle_features(
    venue_id: UUID,
    bulk_data: VenueFeaturesBulkToggle,
    feature_service: FeatureService = Depends(get_feature_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Bulk enable/disable features for a venue."""
    results = await feature_service.bulk_toggle_features(
        venue_id,
        bulk_data.features,
    )
    return {
        "venue_id": venue_id,
        "updated": len(results["success"]),
        "failed": len(results["failed"]),
        "success": results["success"],
        "failed_features": results["failed"],
    }


@router.get("/{venue_id}/features/{feature_name}", response_model=VenueFeatureResponse)
async def get_feature(
    venue_id: UUID,
    feature_name: str,
    feature_service: FeatureService = Depends(get_feature_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get a specific feature configuration."""
    feature = await feature_service.get_feature(venue_id, feature_name)
    if not feature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feature not found",
        )
    return feature


@router.patch("/{venue_id}/features/{feature_name}/config", response_model=VenueFeatureResponse)
async def update_feature_config(
    venue_id: UUID,
    feature_name: str,
    config: Dict[str, Any],
    feature_service: FeatureService = Depends(get_feature_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Update feature configuration without changing enabled status."""
    feature = await feature_service.update_feature_config(venue_id, feature_name, config)
    if not feature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feature not found or not enabled",
        )
    return feature
