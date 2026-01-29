"""Capacity management API routes."""

import math
from typing import Optional
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.reservation import ResourceType
from app.schemas.reservation import (
    CapacityConfigCreate,
    CapacityConfigResponse,
    CapacityConfigUpdate,
    CapacityForecastResponse,
    PaginatedResponse,
    RealTimeCapacityResponse,
)
from app.services.event_publisher import event_publisher
from app.services.capacity_service import CapacityService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> CapacityService:
    return CapacityService(db, event_publisher)


@router.get("/capacity/config", response_model=PaginatedResponse)
async def list_capacity_configs(
    venue_id: UUID = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: CapacityService = Depends(_get_service),
):
    if page_size is None:
        page_size = settings.DEFAULT_PAGE_SIZE
    items, total = await service.list_configs(venue_id, page, page_size)
    return PaginatedResponse(
        items=[CapacityConfigResponse.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.put("/capacity/config", response_model=CapacityConfigResponse)
async def create_or_update_capacity_config(
    venue_id: UUID = Query(...),
    data: CapacityConfigCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: CapacityService = Depends(_get_service),
):
    return await service.create_or_update_config(venue_id, data)


@router.get("/capacity/real-time", response_model=RealTimeCapacityResponse)
async def get_real_time_capacity(
    venue_id: UUID = Query(...),
    resource_type: ResourceType = Query(...),
    current_user: dict = Depends(get_current_user),
    service: CapacityService = Depends(_get_service),
):
    result = await service.get_real_time_capacity(venue_id, resource_type.value)
    return result


@router.get("/capacity/forecast", response_model=CapacityForecastResponse)
async def get_capacity_forecast(
    venue_id: UUID = Query(...),
    resource_type: ResourceType = Query(...),
    forecast_date: date = Query(..., alias="date"),
    current_user: dict = Depends(get_current_user),
    service: CapacityService = Depends(_get_service),
):
    result = await service.get_capacity_forecast(venue_id, resource_type.value, forecast_date)
    return result
