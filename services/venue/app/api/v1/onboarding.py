"""
=============================================================================
FILE: api/v1/onboarding.py
PURPOSE: Venue onboarding workflow endpoints
=============================================================================
"""

from typing import Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.venue import (
    OnboardingStatusResponse,
    OnboardingStepUpdate,
    OnboardingProgressResponse,
)
from app.services.onboarding_service import OnboardingService
from app.core.dependencies import get_onboarding_service, get_current_user

router = APIRouter()


@router.get("/{venue_id}/onboarding", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    venue_id: UUID,
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get current onboarding status and progress for a venue.

    Returns completed steps, current step, and remaining steps.
    """
    return await onboarding_service.get_onboarding_status(venue_id)


@router.get("/{venue_id}/onboarding/progress", response_model=OnboardingProgressResponse)
async def get_onboarding_progress(
    venue_id: UUID,
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get detailed onboarding progress with step details.

    Returns each step's completion status, required fields, and validation state.
    """
    return await onboarding_service.get_detailed_progress(venue_id)


@router.post("/{venue_id}/onboarding/start", response_model=OnboardingStatusResponse)
async def start_onboarding(
    venue_id: UUID,
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Start the onboarding process for a venue."""
    result = await onboarding_service.start_onboarding(venue_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Onboarding already started or venue not found",
        )
    return result


@router.patch("/{venue_id}/onboarding/step/{step_name}", response_model=OnboardingStatusResponse)
async def update_onboarding_step(
    venue_id: UUID,
    step_name: str,
    step_data: OnboardingStepUpdate,
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Update onboarding step status and data.

    Marks a step as complete or in progress with associated data.
    """
    result = await onboarding_service.update_step(
        venue_id,
        step_name,
        step_data.completed,
        step_data.data,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid step or onboarding not started",
        )
    return result


@router.post("/{venue_id}/onboarding/complete", response_model=OnboardingStatusResponse)
async def complete_onboarding(
    venue_id: UUID,
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Mark onboarding as complete.

    Validates all required steps are completed before finalizing.
    This will activate the venue if all requirements are met.
    """
    result = await onboarding_service.complete_onboarding(venue_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot complete onboarding - required steps incomplete",
        )
    return result


@router.post("/{venue_id}/onboarding/skip/{step_name}", response_model=OnboardingStatusResponse)
async def skip_onboarding_step(
    venue_id: UUID,
    step_name: str,
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Skip an optional onboarding step.

    Only optional steps can be skipped. Required steps must be completed.
    """
    result = await onboarding_service.skip_step(venue_id, step_name)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot skip this step - it may be required or invalid",
        )
    return result


@router.post("/{venue_id}/onboarding/reset", response_model=OnboardingStatusResponse)
async def reset_onboarding(
    venue_id: UUID,
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Reset onboarding to initial state.

    Use with caution - this will clear all onboarding progress.
    """
    return await onboarding_service.reset_onboarding(venue_id)


@router.get("/{venue_id}/onboarding/validate")
async def validate_onboarding(
    venue_id: UUID,
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Validate current onboarding state.

    Checks all completed steps still have valid data and returns any issues.
    """
    return await onboarding_service.validate_onboarding(venue_id)
