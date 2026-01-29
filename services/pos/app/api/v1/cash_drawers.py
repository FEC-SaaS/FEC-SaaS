"""Cash drawer API routes for the POS service."""

import math
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.pos import (
    CashDropRequest,
    DrawerCloseRequest,
    DrawerOpenRequest,
    DrawerResponse,
    PaginatedResponse,
)
from app.services.event_publisher import event_publisher
from app.services.cash_drawer_service import CashDrawerService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> CashDrawerService:
    return CashDrawerService(db, event_publisher)


# ---------------------------------------------------------------------------
# POST /pos/cash-drawers/open — open a cash drawer
# ---------------------------------------------------------------------------
@router.post(
    "/pos/cash-drawers/open",
    response_model=DrawerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Open a cash drawer",
)
async def open_drawer(
    body: DrawerOpenRequest,
    venue_id: UUID = Query(..., description="Venue for the cash drawer"),
    service: CashDrawerService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> DrawerResponse:
    """Open a new cash drawer session for a terminal."""
    drawer = await service.open_drawer(venue_id, body, current_user)
    return DrawerResponse.model_validate(drawer)


# ---------------------------------------------------------------------------
# POST /pos/cash-drawers/{drawer_id}/close — close a cash drawer
# ---------------------------------------------------------------------------
@router.post(
    "/pos/cash-drawers/{drawer_id}/close",
    response_model=DrawerResponse,
    summary="Close a cash drawer",
)
async def close_drawer(
    drawer_id: UUID,
    body: DrawerCloseRequest,
    service: CashDrawerService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> DrawerResponse:
    """Close an open cash drawer session and record the closing cash amount."""
    drawer = await service.close_drawer(drawer_id, body)
    if not drawer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cash drawer not found",
        )
    return DrawerResponse.model_validate(drawer)


# ---------------------------------------------------------------------------
# POST /pos/cash-drawers/{drawer_id}/drop — record a cash drop
# ---------------------------------------------------------------------------
@router.post(
    "/pos/cash-drawers/{drawer_id}/drop",
    response_model=DrawerResponse,
    summary="Record a cash drop",
)
async def cash_drop(
    drawer_id: UUID,
    body: CashDropRequest,
    service: CashDrawerService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> DrawerResponse:
    """Record a cash drop from an open cash drawer."""
    drawer = await service.cash_drop(drawer_id, body)
    if not drawer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cash drawer not found",
        )
    return DrawerResponse.model_validate(drawer)


# ---------------------------------------------------------------------------
# GET /pos/cash-drawers/{drawer_id} — get cash drawer details
# ---------------------------------------------------------------------------
@router.get(
    "/pos/cash-drawers/{drawer_id}",
    response_model=DrawerResponse,
    summary="Get cash drawer details",
)
async def get_drawer(
    drawer_id: UUID,
    service: CashDrawerService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> DrawerResponse:
    """Retrieve a single cash drawer session by its ID."""
    drawer = await service.get_drawer(drawer_id)
    if not drawer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cash drawer not found",
        )
    return DrawerResponse.model_validate(drawer)


# ---------------------------------------------------------------------------
# GET /pos/cash-drawers — list cash drawers
# ---------------------------------------------------------------------------
@router.get(
    "/pos/cash-drawers",
    response_model=PaginatedResponse,
    summary="List cash drawers",
)
async def list_drawers(
    venue_id: UUID = Query(..., description="Venue to list drawers for"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by drawer status"),
    date_from: Optional[datetime] = Query(None, description="Start of date range"),
    date_to: Optional[datetime] = Query(None, description="End of date range"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    service: CashDrawerService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> PaginatedResponse:
    """Return a paginated list of cash drawer sessions for a venue."""
    drawers, total = await service.list_drawers(
        venue_id=venue_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[DrawerResponse.model_validate(d) for d in drawers],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )
