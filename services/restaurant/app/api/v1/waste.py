"""Food waste API routes."""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.restaurant import FoodWasteCreate, FoodWasteResponse, WasteAnalyticsResponse
from app.services.event_publisher import event_publisher
from app.services.waste_service import WasteService

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> WasteService:
    return WasteService(db, event_publisher)


@router.post("/waste/log", response_model=FoodWasteResponse, status_code=status.HTTP_201_CREATED)
async def log_waste(
    venue_id: UUID = Query(...),
    data: FoodWasteCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: WasteService = Depends(_get_service),
):
    return await service.log_waste(venue_id, data)


@router.get("/waste/analytics", response_model=WasteAnalyticsResponse)
async def get_waste_analytics(
    venue_id: UUID = Query(...),
    period_start: Optional[date] = Query(None),
    period_end: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user),
    service: WasteService = Depends(_get_service),
):
    return await service.get_waste_analytics(venue_id, period_start, period_end)
