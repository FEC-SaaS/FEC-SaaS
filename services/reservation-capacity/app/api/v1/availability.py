"""Availability and time slot API routes."""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.reservation import ResourceType
from app.schemas.reservation import (
    DateAvailabilityResponse,
    HoldRequest,
    HoldResponse,
    TimeSlotResponse,
)
from app.services.event_publisher import event_publisher
from app.services.capacity_service import CapacityService

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> CapacityService:
    return CapacityService(db, event_publisher)


@router.get("/reservations/availability", response_model=List[DateAvailabilityResponse])
async def check_availability(
    venue_id: UUID = Query(...),
    resource_type: ResourceType = Query(...),
    start_date: date = Query(...),
    end_date: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user),
    service: CapacityService = Depends(_get_service),
):
    results = await service.get_availability(venue_id, resource_type.value, start_date, end_date)
    return results


@router.get("/reservations/time-slots", response_model=List[TimeSlotResponse])
async def get_time_slots(
    venue_id: UUID = Query(...),
    resource_type: ResourceType = Query(...),
    target_date: date = Query(..., alias="date"),
    party_size: Optional[int] = Query(None, ge=1),
    current_user: dict = Depends(get_current_user),
    service: CapacityService = Depends(_get_service),
):
    slots = await service.get_time_slots(venue_id, resource_type.value, target_date, party_size)
    return [TimeSlotResponse.model_validate(s) for s in slots]


@router.post("/reservations/hold", response_model=HoldResponse, status_code=status.HTTP_201_CREATED)
async def hold_time_slot(
    venue_id: UUID = Query(...),
    data: HoldRequest = ...,
    current_user: dict = Depends(get_current_user),
    service: CapacityService = Depends(_get_service),
):
    held_by = current_user.get("user_id")
    return await service.hold_time_slot(venue_id, data, held_by)


@router.post("/reservations/release-hold")
async def release_hold(
    hold_id: UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    service: CapacityService = Depends(_get_service),
):
    result = await service.release_hold(hold_id)
    if not result:
        raise HTTPException(status_code=404, detail="Hold not found")
    return {"status": "released", "hold_id": str(hold_id)}
