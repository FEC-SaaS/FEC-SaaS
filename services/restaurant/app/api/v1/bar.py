"""Bar API routes."""

import math
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.restaurant import (
    BarInventoryCreate,
    BarInventoryResponse,
    BarInventoryUpdate,
    BarPourCreate,
    BarPourResponse,
    PaginatedResponse,
)
from app.services.event_publisher import event_publisher
from app.services.bar_service import BarService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> BarService:
    return BarService(db, event_publisher)


@router.get("/bar/inventory", response_model=PaginatedResponse)
async def list_bar_inventory(
    venue_id: UUID = Query(...),
    product_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: BarService = Depends(_get_service),
):
    if page_size is None:
        page_size = settings.DEFAULT_PAGE_SIZE
    items, total = await service.list_inventory(venue_id, product_type, page, page_size)
    return PaginatedResponse(
        items=[BarInventoryResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.post("/bar/inventory", response_model=BarInventoryResponse, status_code=status.HTTP_201_CREATED)
async def create_bar_inventory(
    venue_id: UUID = Query(...),
    data: BarInventoryCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: BarService = Depends(_get_service),
):
    return await service.create_inventory_item(venue_id, data)


@router.put("/bar/inventory/{item_id}", response_model=BarInventoryResponse)
async def update_bar_inventory(
    item_id: UUID,
    data: BarInventoryUpdate,
    current_user: dict = Depends(get_current_user),
    service: BarService = Depends(_get_service),
):
    result = await service.update_inventory_item(item_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Bar inventory item not found")
    return result


@router.post("/bar/pours", response_model=BarPourResponse, status_code=status.HTTP_201_CREATED)
async def record_pour(
    venue_id: UUID = Query(...),
    data: BarPourCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: BarService = Depends(_get_service),
):
    return await service.record_pour(venue_id, data)


@router.get("/bar/low-stock", response_model=List[BarInventoryResponse])
async def get_low_stock(
    venue_id: UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    service: BarService = Depends(_get_service),
):
    return await service.get_low_stock(venue_id)
