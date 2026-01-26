"""
=============================================================================
FILE: api/v1/ai_config.py
PURPOSE: Venue AI service configuration endpoints
=============================================================================
"""

from typing import List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.venue import (
    VenueAIConfigCreate,
    VenueAIConfigUpdate,
    VenueAIConfigResponse,
)
from app.services.ai_config_service import AIConfigService
from app.core.dependencies import get_ai_config_service, get_current_user

router = APIRouter()


@router.get("/{venue_id}/ai-config", response_model=List[VenueAIConfigResponse])
async def get_ai_configs(
    venue_id: UUID,
    ai_config_service: AIConfigService = Depends(get_ai_config_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get all AI service configurations for a venue."""
    return await ai_config_service.get_ai_configs(venue_id)


@router.get("/{venue_id}/ai-config/available")
async def get_available_ai_services(
    venue_id: UUID,
    ai_config_service: AIConfigService = Depends(get_ai_config_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get AI services available for venue's subscription tier.

    Returns available services with their default configurations.
    """
    available = await ai_config_service.get_available_ai_services(venue_id)
    configs = await ai_config_service.get_ai_configs(venue_id)
    enabled_services = {c.service_name for c in configs if c.enabled}

    return {
        "venue_id": venue_id,
        "available_services": list(available),
        "enabled_services": list(enabled_services),
        "can_enable": list(available - enabled_services),
    }


@router.post(
    "/{venue_id}/ai-config/{service_name}",
    response_model=VenueAIConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ai_config(
    venue_id: UUID,
    service_name: str,
    config_data: VenueAIConfigCreate,
    ai_config_service: AIConfigService = Depends(get_ai_config_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Enable and configure an AI service for a venue.

    Service must be available for the venue's subscription tier.
    """
    config = await ai_config_service.enable_ai_service(
        venue_id,
        service_name,
        config_data.parameters,
    )
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI service not available for this subscription tier",
        )
    return config


@router.get("/{venue_id}/ai-config/{service_name}", response_model=VenueAIConfigResponse)
async def get_ai_config(
    venue_id: UUID,
    service_name: str,
    ai_config_service: AIConfigService = Depends(get_ai_config_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Get configuration for a specific AI service."""
    config = await ai_config_service.get_ai_config(venue_id, service_name)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI config not found",
        )
    return config


@router.patch("/{venue_id}/ai-config/{service_name}", response_model=VenueAIConfigResponse)
async def update_ai_config(
    venue_id: UUID,
    service_name: str,
    update_data: VenueAIConfigUpdate,
    ai_config_service: AIConfigService = Depends(get_ai_config_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Update AI service configuration."""
    config = await ai_config_service.update_ai_config(
        venue_id,
        service_name,
        update_data,
    )
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI config not found",
        )
    return config


@router.delete("/{venue_id}/ai-config/{service_name}", status_code=status.HTTP_204_NO_CONTENT)
async def disable_ai_service(
    venue_id: UUID,
    service_name: str,
    ai_config_service: AIConfigService = Depends(get_ai_config_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Disable an AI service for a venue."""
    disabled = await ai_config_service.disable_ai_service(venue_id, service_name)
    if not disabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI config not found",
        )


@router.post("/{venue_id}/ai-config/{service_name}/reset", response_model=VenueAIConfigResponse)
async def reset_ai_config(
    venue_id: UUID,
    service_name: str,
    ai_config_service: AIConfigService = Depends(get_ai_config_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Reset AI service to default parameters."""
    config = await ai_config_service.reset_to_defaults(venue_id, service_name)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI config not found",
        )
    return config
