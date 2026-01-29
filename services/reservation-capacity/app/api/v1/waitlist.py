"""Waitlist API routes."""

import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.reservation import PaginatedResponse, WaitlistCreate, WaitlistResponse
from app.services.event_publisher import event_publisher
from app.services.waitlist_service import WaitlistService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> WaitlistService:
    return WaitlistService(db, event_publisher)


@router.get("/reservations/waitlist", response_model=PaginatedResponse)
async def list_waitlist(
    venue_id: UUID = Query(...),
    reservation_type: Optional[str] = Query(None, alias="type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: WaitlistService = Depends(_get_service),
):
    if page_size is None:
        page_size = settings.DEFAULT_PAGE_SIZE
    items, total = await service.list_waitlist(venue_id, reservation_type, page, page_size)
    return PaginatedResponse(
        items=[WaitlistResponse.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.post("/reservations/waitlist", response_model=WaitlistResponse, status_code=status.HTTP_201_CREATED)
async def add_to_waitlist(
    venue_id: UUID = Query(...),
    data: WaitlistCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: WaitlistService = Depends(_get_service),
):
    return await service.add_to_waitlist(venue_id, data)


@router.delete("/reservations/waitlist/{waitlist_id}", response_model=WaitlistResponse)
async def remove_from_waitlist(
    waitlist_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: WaitlistService = Depends(_get_service),
):
    result = await service.remove_from_waitlist(waitlist_id)
    if not result:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")
    return result


@router.post("/reservations/waitlist/{waitlist_id}/notify", response_model=WaitlistResponse)
async def notify_waitlist_customer(
    waitlist_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: WaitlistService = Depends(_get_service),
):
    result = await service.notify_customer(waitlist_id)
    if not result:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")
    return result


@router.post("/reservations/waitlist/{waitlist_id}/convert", response_model=WaitlistResponse)
async def convert_waitlist_to_reservation(
    waitlist_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: WaitlistService = Depends(_get_service),
):
    result = await service.convert_to_reservation(waitlist_id)
    if not result:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")
    return result
