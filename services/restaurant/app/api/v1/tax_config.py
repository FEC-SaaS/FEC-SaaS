"""Venue tax configuration API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.restaurant import VenueTaxConfig
from app.schemas.restaurant import (
    VenueTaxConfigCreate,
    VenueTaxConfigResponse,
    VenueTaxConfigUpdate,
)

router = APIRouter()


@router.get("/tax-config", response_model=VenueTaxConfigResponse)
async def get_tax_config(
    venue_id: UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    result = await db.execute(
        select(VenueTaxConfig).where(VenueTaxConfig.venue_id == venue_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Tax config not found for this venue")
    return config


@router.post("/tax-config", response_model=VenueTaxConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_tax_config(
    venue_id: UUID = Query(...),
    data: VenueTaxConfigCreate = ...,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    # Check if config already exists
    existing = await db.execute(
        select(VenueTaxConfig).where(VenueTaxConfig.venue_id == venue_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Tax config already exists for this venue")

    config = VenueTaxConfig(
        venue_id=venue_id,
        tax_rate=data.tax_rate,
        tax_name=data.tax_name,
        delivery_tax_rate=data.delivery_tax_rate,
        takeout_tax_rate=data.takeout_tax_rate,
        is_tax_inclusive=data.is_tax_inclusive,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.put("/tax-config", response_model=VenueTaxConfigResponse)
async def update_tax_config(
    venue_id: UUID = Query(...),
    data: VenueTaxConfigUpdate = ...,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    result = await db.execute(
        select(VenueTaxConfig).where(VenueTaxConfig.venue_id == venue_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Tax config not found for this venue")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)
    await db.commit()
    await db.refresh(config)
    return config
