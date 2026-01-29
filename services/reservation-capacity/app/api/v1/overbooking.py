"""Overbooking rules API routes."""

from typing import List, Optional
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.reservation import OverbookingRule, ResourceType
from app.schemas.reservation import (
    OverbookingForecastResponse,
    OverbookingRuleCreate,
    OverbookingRuleResponse,
    OverbookingRuleUpdate,
)

router = APIRouter()


@router.get("/capacity/overbooking-rules", response_model=List[OverbookingRuleResponse])
async def list_overbooking_rules(
    venue_id: UUID = Query(...),
    resource_type: Optional[ResourceType] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(OverbookingRule).where(OverbookingRule.venue_id == venue_id)
    if resource_type:
        query = query.where(OverbookingRule.resource_type == resource_type.value)
    query = query.order_by(OverbookingRule.resource_type, OverbookingRule.day_of_week)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.put("/capacity/overbooking-rules", response_model=OverbookingRuleResponse)
async def create_or_update_overbooking_rule(
    venue_id: UUID = Query(...),
    data: OverbookingRuleCreate = ...,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Check if exists
    query = select(OverbookingRule).where(
        OverbookingRule.venue_id == venue_id,
        OverbookingRule.resource_type == data.resource_type.value,
    )
    if data.day_of_week is not None:
        query = query.where(OverbookingRule.day_of_week == data.day_of_week)
    if data.time_period:
        query = query.where(OverbookingRule.time_period == data.time_period.value)

    result = await db.execute(query)
    rule = result.scalar_one_or_none()

    if rule:
        rule.active_overbooking_rate = data.active_overbooking_rate
        if data.time_period:
            rule.time_period = data.time_period.value
    else:
        rule = OverbookingRule(
            venue_id=venue_id,
            resource_type=data.resource_type.value,
            day_of_week=data.day_of_week,
            time_period=data.time_period.value if data.time_period else None,
            active_overbooking_rate=data.active_overbooking_rate,
        )
        db.add(rule)

    await db.commit()
    await db.refresh(rule)
    return rule


@router.get("/capacity/overbooking-forecast", response_model=OverbookingForecastResponse)
async def get_overbooking_forecast(
    venue_id: UUID = Query(...),
    resource_type: ResourceType = Query(...),
    forecast_date: date = Query(..., alias="date"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from decimal import Decimal
    # Simple forecast based on historical no-show rate
    query = select(OverbookingRule).where(
        OverbookingRule.venue_id == venue_id,
        OverbookingRule.resource_type == resource_type.value,
    )
    result = await db.execute(query)
    rules = list(result.scalars().all())

    avg_no_show = Decimal("0")
    current_rate = Decimal("0")
    if rules:
        rates = [r.historical_no_show_rate or Decimal("0") for r in rules]
        avg_no_show = sum(rates) / len(rates)
        active_rates = [r.active_overbooking_rate or Decimal("0") for r in rules]
        current_rate = sum(active_rates) / len(active_rates) if active_rates else Decimal("0")

    return OverbookingForecastResponse(
        venue_id=venue_id,
        resource_type=resource_type.value,
        date=forecast_date,
        expected_no_shows=int(avg_no_show),
        recommended_overbooking=int(avg_no_show * Decimal("1.1")),
        current_overbooking_rate=current_rate,
        confidence=Decimal("0.75"),
    )
