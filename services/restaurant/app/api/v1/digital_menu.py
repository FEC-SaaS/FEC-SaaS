"""Digital menu board API routes."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.restaurant import DigitalMenuBoard, HappyHourSchedule
from app.schemas.restaurant import (
    DigitalMenuBoardCreate,
    DigitalMenuBoardResponse,
    DigitalMenuBoardUpdate,
    HappyHourCreate,
    HappyHourResponse,
)

router = APIRouter()


@router.get("/digital-menu", response_model=List[DigitalMenuBoardResponse])
async def list_digital_menus(
    venue_id: UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DigitalMenuBoard)
        .where(DigitalMenuBoard.venue_id == venue_id)
        .order_by(DigitalMenuBoard.board_name)
    )
    return list(result.scalars().all())


@router.post("/digital-menu", response_model=DigitalMenuBoardResponse, status_code=status.HTTP_201_CREATED)
async def create_digital_menu(
    venue_id: UUID = Query(...),
    data: DigitalMenuBoardCreate = ...,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    board = DigitalMenuBoard(
        venue_id=venue_id,
        board_name=data.board_name,
        board_location=data.board_location,
        display_categories=data.display_categories,
        layout_type=data.layout_type.value if data.layout_type else None,
        is_active=data.is_active,
    )
    db.add(board)
    await db.commit()
    await db.refresh(board)
    return board


@router.put("/digital-menu/{board_id}", response_model=DigitalMenuBoardResponse)
async def update_digital_menu(
    board_id: UUID,
    data: DigitalMenuBoardUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DigitalMenuBoard).where(DigitalMenuBoard.id == board_id))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Digital menu board not found")
    update_data = data.model_dump(exclude_unset=True)
    if "layout_type" in update_data and update_data["layout_type"]:
        update_data["layout_type"] = update_data["layout_type"].value
    for key, value in update_data.items():
        setattr(board, key, value)
    await db.commit()
    await db.refresh(board)
    return board


# ─── Happy Hour ──────────────────────────────────────────────────────────

@router.get("/happy-hours", response_model=List[HappyHourResponse])
async def list_happy_hours(
    venue_id: UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HappyHourSchedule)
        .where(HappyHourSchedule.venue_id == venue_id)
        .order_by(HappyHourSchedule.day_of_week, HappyHourSchedule.start_time)
    )
    return list(result.scalars().all())


@router.post("/happy-hours", response_model=HappyHourResponse, status_code=status.HTTP_201_CREATED)
async def create_happy_hour(
    venue_id: UUID = Query(...),
    data: HappyHourCreate = ...,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    schedule = HappyHourSchedule(
        venue_id=venue_id,
        schedule_name=data.schedule_name,
        day_of_week=data.day_of_week,
        start_time=data.start_time,
        end_time=data.end_time,
        discount_percentage=data.discount_percentage,
        affected_categories=data.affected_categories,
        is_active=data.is_active,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule
