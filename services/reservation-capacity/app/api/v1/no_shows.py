"""No-show management API routes."""

import math
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.reservation import (
    CustomerReservationStatsResponse,
    NoShowResponse,
    PaginatedResponse,
    ReservationResponse,
)
from app.services.event_publisher import event_publisher
from app.services.no_show_service import NoShowService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> NoShowService:
    return NoShowService(db, event_publisher)


@router.get("/reservations/no-shows", response_model=PaginatedResponse)
async def list_no_shows(
    venue_id: UUID = Query(...),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: NoShowService = Depends(_get_service),
):
    if page_size is None:
        page_size = settings.DEFAULT_PAGE_SIZE
    items, total = await service.list_no_shows(venue_id, start_date, end_date, page, page_size)
    return PaginatedResponse(
        items=[NoShowResponse.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.get("/customers/{customer_id}/reservation-history", response_model=List[ReservationResponse])
async def get_customer_reservation_history(
    customer_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: NoShowService = Depends(_get_service),
):
    return await service.get_customer_history(customer_id)


@router.get("/customers/{customer_id}/reliability-score", response_model=CustomerReservationStatsResponse)
async def get_customer_reliability_score(
    customer_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: NoShowService = Depends(_get_service),
):
    result = await service.get_reliability_score(customer_id)
    if not result:
        raise HTTPException(status_code=404, detail="Customer stats not found")
    return result
