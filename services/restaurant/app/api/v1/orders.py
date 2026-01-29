"""Orders API routes."""

import math
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.config import get_settings
from app.models.restaurant import OrderStatus
from app.schemas.restaurant import (
    OrderCreate,
    OrderItemCreate,
    OrderResponse,
    OrderStatusUpdate,
    PaginatedResponse,
)
from app.services.event_publisher import event_publisher
from app.services.order_service import OrderService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> OrderService:
    return OrderService(db, event_publisher)


@router.get("/orders", response_model=PaginatedResponse)
async def list_orders(
    venue_id: UUID = Query(...),
    status_filter: Optional[OrderStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    service: OrderService = Depends(_get_service),
):
    if page_size is None:
        page_size = settings.DEFAULT_PAGE_SIZE
    items, total = await service.list_orders(venue_id, status_filter, page, page_size)
    return PaginatedResponse(
        items=[OrderResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    venue_id: UUID = Query(...),
    data: OrderCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: OrderService = Depends(_get_service),
):
    return await service.create_order(venue_id, data)


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: OrderService = Depends(_get_service),
):
    order = await service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/orders/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: UUID,
    data: OrderStatusUpdate,
    current_user: dict = Depends(get_current_user),
    service: OrderService = Depends(_get_service),
):
    result = await service.update_order_status(order_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Order not found")
    return result


@router.post("/orders/{order_id}/items", response_model=OrderResponse)
async def add_items_to_order(
    order_id: UUID,
    items: List[OrderItemCreate],
    current_user: dict = Depends(get_current_user),
    service: OrderService = Depends(_get_service),
):
    result = await service.add_items_to_order(order_id, items)
    if not result:
        raise HTTPException(status_code=404, detail="Order not found")
    return result
