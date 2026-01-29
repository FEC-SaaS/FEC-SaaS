"""Group/block reservation API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.reservation import (
    GroupBookingCreate,
    GroupBookingResponse,
    ReservationResponse,
)
from app.services.event_publisher import event_publisher
from app.services.group_booking_service import GroupBookingService

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> GroupBookingService:
    return GroupBookingService(db, event_publisher)


@router.post(
    "/reservations/group",
    response_model=GroupBookingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_group_booking(
    venue_id: UUID = Query(...),
    data: GroupBookingCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: GroupBookingService = Depends(_get_service),
):
    """Create a group/block booking with multiple resource reservations."""
    reservations = await service.create_group_booking(venue_id, data)
    return GroupBookingResponse(
        group_booking_id=reservations[0].group_booking_id,
        group_name=data.group_name,
        total_resources=len(reservations),
        total_party_size=sum(r.party_size for r in reservations),
        reservations=[ReservationResponse.model_validate(r) for r in reservations],
    )


@router.get("/reservations/group/{group_id}", response_model=GroupBookingResponse)
async def get_group_booking(
    group_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: GroupBookingService = Depends(_get_service),
):
    """Get all reservations in a group booking."""
    reservations = await service.get_group(group_id)
    if not reservations:
        raise HTTPException(status_code=404, detail="Group booking not found")
    return GroupBookingResponse(
        group_booking_id=group_id,
        group_name=reservations[0].group_name or "",
        total_resources=len(reservations),
        total_party_size=sum(r.party_size for r in reservations),
        reservations=[ReservationResponse.model_validate(r) for r in reservations],
    )


@router.delete("/reservations/group/{group_id}", response_model=GroupBookingResponse)
async def cancel_group_booking(
    group_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: GroupBookingService = Depends(_get_service),
):
    """Cancel all reservations in a group booking."""
    reservations = await service.cancel_group(group_id)
    if not reservations:
        raise HTTPException(status_code=404, detail="No cancellable reservations found")
    return GroupBookingResponse(
        group_booking_id=group_id,
        group_name=reservations[0].group_name or "",
        total_resources=len(reservations),
        total_party_size=sum(r.party_size for r in reservations),
        reservations=[ReservationResponse.model_validate(r) for r in reservations],
    )
