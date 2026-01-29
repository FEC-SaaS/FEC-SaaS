"""Reservation API routes."""

import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.reservation import ReservationStatus, ReservationType
from app.schemas.reservation import (
    NoteCreate,
    NoteResponse,
    PaginatedResponse,
    ReservationCreate,
    ReservationResponse,
    ReservationUpdate,
)
from app.core.rate_limiter import check_reservation_create_rate
from app.services.event_publisher import event_publisher
from app.services.reservation_service import ReservationService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> ReservationService:
    return ReservationService(db, event_publisher)


@router.get("/reservations", response_model=PaginatedResponse)
async def list_reservations(
    venue_id: UUID = Query(...),
    reservation_type: Optional[ReservationType] = Query(None, alias="type"),
    reservation_date: Optional[str] = Query(None, alias="date"),
    status_filter: Optional[ReservationStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: ReservationService = Depends(_get_service),
):
    if page_size is None:
        page_size = settings.DEFAULT_PAGE_SIZE
    from datetime import date as date_type
    res_date = date_type.fromisoformat(reservation_date) if reservation_date else None
    res_type = reservation_type.value if reservation_type else None
    status_val = status_filter.value if status_filter else None
    items, total = await service.list_reservations(
        venue_id, res_type, res_date, status_val, page, page_size
    )
    return PaginatedResponse(
        items=[ReservationResponse.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.post("/reservations", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
async def create_reservation(
    venue_id: UUID = Query(...),
    data: ReservationCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: ReservationService = Depends(_get_service),
    _rate_limit: None = Depends(check_reservation_create_rate),
):
    return await service.create_reservation(venue_id, data)


@router.get("/reservations/{reservation_id}", response_model=ReservationResponse)
async def get_reservation(
    reservation_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: ReservationService = Depends(_get_service),
):
    result = await service.get_reservation(reservation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return result


@router.put("/reservations/{reservation_id}", response_model=ReservationResponse)
async def update_reservation(
    reservation_id: UUID,
    data: ReservationUpdate,
    current_user: dict = Depends(get_current_user),
    service: ReservationService = Depends(_get_service),
):
    result = await service.update_reservation(reservation_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return result


@router.delete("/reservations/{reservation_id}", response_model=ReservationResponse)
async def cancel_reservation(
    reservation_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: ReservationService = Depends(_get_service),
):
    result = await service.cancel_reservation(reservation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return result


@router.post("/reservations/{reservation_id}/check-in", response_model=ReservationResponse)
async def check_in(
    reservation_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: ReservationService = Depends(_get_service),
):
    result = await service.check_in(reservation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return result


@router.post("/reservations/{reservation_id}/no-show")
async def mark_no_show(
    reservation_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.no_show_service import NoShowService
    service = NoShowService(db, event_publisher)
    result = await service.mark_no_show(reservation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return {"status": "marked_as_no_show", "reservation_id": str(reservation_id)}


@router.post("/reservations/{reservation_id}/confirm", response_model=ReservationResponse)
async def confirm_reservation(
    reservation_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: ReservationService = Depends(_get_service),
):
    result = await service.confirm_reservation(reservation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reservation not found or not in PENDING status")
    return result
