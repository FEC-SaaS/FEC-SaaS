"""Tables and sections API routes."""

import math
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.restaurant import TableStatus
from app.schemas.restaurant import (
    PaginatedResponse,
    SectionCreate,
    SectionResponse,
    SectionUpdate,
    TableCreate,
    TableResponse,
    TableStatusUpdate,
    TableUpdate,
)
from app.services.event_publisher import event_publisher
from app.services.table_service import TableService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> TableService:
    return TableService(db, event_publisher)


@router.get("/sections", response_model=PaginatedResponse)
async def list_sections(
    venue_id: UUID = Query(...),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: TableService = Depends(_get_service),
):
    if page_size is None:
        page_size = settings.DEFAULT_PAGE_SIZE
    items, total = await service.list_sections(venue_id, is_active, page, page_size)
    return PaginatedResponse(
        items=[SectionResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.post("/sections", response_model=SectionResponse, status_code=status.HTTP_201_CREATED)
async def create_section(
    venue_id: UUID = Query(...),
    data: SectionCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: TableService = Depends(_get_service),
):
    return await service.create_section(venue_id, data)


@router.get("/tables", response_model=PaginatedResponse)
async def list_tables(
    venue_id: UUID = Query(...),
    section_id: Optional[UUID] = Query(None),
    status_filter: Optional[TableStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: TableService = Depends(_get_service),
):
    if page_size is None:
        page_size = settings.DEFAULT_PAGE_SIZE
    items, total = await service.list_tables(venue_id, section_id, status_filter, page, page_size)
    return PaginatedResponse(
        items=[TableResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.post("/tables", response_model=TableResponse, status_code=status.HTTP_201_CREATED)
async def create_table(
    venue_id: UUID = Query(...),
    data: TableCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: TableService = Depends(_get_service),
):
    return await service.create_table(venue_id, data)


@router.get("/tables/availability", response_model=List[TableResponse])
async def get_available_tables(
    venue_id: UUID = Query(...),
    party_size: Optional[int] = Query(None, ge=1),
    current_user: dict = Depends(get_current_user),
    service: TableService = Depends(_get_service),
):
    return await service.get_available_tables(venue_id, party_size)


@router.patch("/tables/{table_id}/status", response_model=TableResponse)
async def update_table_status(
    table_id: UUID,
    data: TableStatusUpdate,
    current_user: dict = Depends(get_current_user),
    service: TableService = Depends(_get_service),
):
    result = await service.update_table_status(table_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Table not found")
    return result
