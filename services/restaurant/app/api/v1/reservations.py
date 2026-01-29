"""Reservation API routes."""

import math
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.restaurant import ReservationStatus
from app.schemas.restaurant import (
    PaginatedResponse,
    ReservationCreate,
    ReservationResponse,
    ReservationSeat,
)
from app.services.event_publisher import event_publisher
from app.services.reservation_service import ReservationService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> ReservationService:
    return ReservationService(db, event_publisher)


@router.get("/reservations", response_model=PaginatedResponse)
async def list_reservations(
    venue_id: UUID = Query(...),
    reservation_date: Optional[date] = Query(None),
    status_filter: Optional[ReservationStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: ReservationService = Depends(_get_service),
):
    if page_size is None:
        page_size = settings.DEFAULT_PAGE_SIZE
    items, total = await service.list_reservations(venue_id, reservation_date, status_filter, page, page_size)
    return PaginatedResponse(
        items=[ReservationResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.post("/reservations", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
async def create_reservation(
    venue_id: UUID = Query(...),
    data: ReservationCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: ReservationService = Depends(_get_service),
):
    return await service.create_reservation(venue_id, data)


@router.post("/reservations/{reservation_id}/seat", response_model=ReservationResponse)
async def seat_reservation(
    reservation_id: UUID,
    data: ReservationSeat,
    current_user: dict = Depends(get_current_user),
    service: ReservationService = Depends(_get_service),
):
    result = await service.seat_reservation(reservation_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return result


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationResponse)
async def cancel_reservation(
    reservation_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: ReservationService = Depends(_get_service),
):
    result = await service.cancel_reservation(reservation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return result
