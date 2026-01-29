"""Kitchen Display System (KDS) API routes."""

import math
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.restaurant import KDSItemStatus
from app.schemas.restaurant import (
    KDSQueueItemResponse,
    KitchenStationCreate,
    KitchenStationResponse,
    PaginatedResponse,
)
from app.services.event_publisher import event_publisher
from app.services.kds_service import KDSService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> KDSService:
    return KDSService(db, event_publisher)


@router.get("/kds/stations", response_model=List[KitchenStationResponse])
async def list_stations(
    venue_id: UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    service: KDSService = Depends(_get_service),
):
    return await service.list_stations(venue_id)


@router.post("/kds/stations", response_model=KitchenStationResponse, status_code=status.HTTP_201_CREATED)
async def create_station(
    venue_id: UUID = Query(...),
    data: KitchenStationCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: KDSService = Depends(_get_service),
):
    return await service.create_station(venue_id, data)


@router.get("/kds/queue", response_model=PaginatedResponse)
async def get_queue(
    venue_id: UUID = Query(...),
    station_id: Optional[UUID] = Query(None),
    status_filter: Optional[KDSItemStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    service: KDSService = Depends(_get_service),
):
    if page_size is None:
        page_size = 50  # KDS default larger page
    items, total = await service.get_queue(venue_id, station_id, status_filter, page, page_size)
    return PaginatedResponse(
        items=[KDSQueueItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.get("/kds/stations/{station_id}/queue", response_model=List[KDSQueueItemResponse])
async def get_station_queue(
    station_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: KDSService = Depends(_get_service),
):
    return await service.get_station_queue(station_id)


@router.patch("/kds/items/{kds_item_id}/start", response_model=KDSQueueItemResponse)
async def start_kds_item(
    kds_item_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: KDSService = Depends(_get_service),
):
    result = await service.start_item(kds_item_id)
    if not result:
        raise HTTPException(status_code=404, detail="KDS item not found")
    return result


@router.patch("/kds/items/{kds_item_id}/complete", response_model=KDSQueueItemResponse)
async def complete_kds_item(
    kds_item_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: KDSService = Depends(_get_service),
):
    result = await service.complete_item(kds_item_id)
    if not result:
        raise HTTPException(status_code=404, detail="KDS item not found")
    return result
