"""Recurring reservation API routes."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.reservation import (
    RecurringReservationCreate,
    RecurringSeriesResponse,
    ReservationResponse,
)
from app.services.event_publisher import event_publisher
from app.services.recurring_service import RecurringReservationService

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> RecurringReservationService:
    return RecurringReservationService(db, event_publisher)


@router.post(
    "/reservations/recurring",
    response_model=RecurringSeriesResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_recurring_series(
    venue_id: UUID = Query(...),
    data: RecurringReservationCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: RecurringReservationService = Depends(_get_service),
):
    """Create a series of recurring reservations (weekly, biweekly, or monthly)."""
    reservations = await service.create_recurring_series(venue_id, data)
    return RecurringSeriesResponse(
        recurrence_group_id=reservations[0].recurrence_group_id,
        frequency=data.recurrence_frequency.value,
        total_count=len(reservations),
        reservations=[ReservationResponse.model_validate(r) for r in reservations],
    )


@router.get("/reservations/recurring/{group_id}", response_model=RecurringSeriesResponse)
async def get_recurring_series(
    group_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: RecurringReservationService = Depends(_get_service),
):
    """Get all reservations in a recurring series."""
    reservations = await service.get_series(group_id)
    if not reservations:
        raise HTTPException(status_code=404, detail="Recurring series not found")
    return RecurringSeriesResponse(
        recurrence_group_id=group_id,
        frequency=reservations[0].recurrence_frequency or "UNKNOWN",
        total_count=len(reservations),
        reservations=[ReservationResponse.model_validate(r) for r in reservations],
    )


@router.delete("/reservations/recurring/{group_id}", response_model=RecurringSeriesResponse)
async def cancel_recurring_series(
    group_id: UUID,
    future_only: bool = Query(False),
    current_user: dict = Depends(get_current_user),
    service: RecurringReservationService = Depends(_get_service),
):
    """Cancel all (or future only) reservations in a recurring series."""
    reservations = await service.cancel_series(group_id, cancel_future_only=future_only)
    if not reservations:
        raise HTTPException(status_code=404, detail="No cancellable reservations found")
    return RecurringSeriesResponse(
        recurrence_group_id=group_id,
        frequency=reservations[0].recurrence_frequency or "UNKNOWN",
        total_count=len(reservations),
        reservations=[ReservationResponse.model_validate(r) for r in reservations],
    )
