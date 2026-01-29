"""Food waste logging and analytics service."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant import FoodWasteLog, MenuItem
from app.schemas.restaurant import FoodWasteCreate, WasteAnalyticsResponse
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()


class WasteService:
    def __init__(self, db: AsyncSession, event_publisher: Optional[EventPublisher] = None):
        self.db = db
        self.event_publisher = event_publisher

    async def log_waste(self, venue_id: UUID, data: FoodWasteCreate) -> FoodWasteLog:
        waste = FoodWasteLog(
            venue_id=venue_id,
            waste_date=data.waste_date,
            menu_item_id=data.menu_item_id,
            inventory_item_id=data.inventory_item_id,
            quantity_wasted=data.quantity_wasted,
            waste_reason=data.waste_reason.value if data.waste_reason else None,
            estimated_cost=data.estimated_cost,
            logged_by=data.logged_by,
        )
        self.db.add(waste)
        await self.db.commit()
        await self.db.refresh(waste)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.WASTE_LOGGED,
                {
                    "waste_id": str(waste.id),
                    "quantity_wasted": str(data.quantity_wasted),
                    "waste_reason": data.waste_reason.value if data.waste_reason else None,
                    "estimated_cost": str(data.estimated_cost) if data.estimated_cost else None,
                },
                venue_id=venue_id,
            )
        logger.info("waste_logged", waste_id=str(waste.id))
        return waste

    async def get_waste_analytics(
        self,
        venue_id: UUID,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None,
    ) -> WasteAnalyticsResponse:
        if not period_start:
            period_start = date.today() - timedelta(days=30)
        if not period_end:
            period_end = date.today()

        # Total cost and count
        totals_query = select(
            func.coalesce(func.sum(FoodWasteLog.estimated_cost), 0).label("total_cost"),
            func.count(FoodWasteLog.id).label("total_items"),
        ).where(
            FoodWasteLog.venue_id == venue_id,
            FoodWasteLog.waste_date >= period_start,
            FoodWasteLog.waste_date <= period_end,
        )
        totals_result = await self.db.execute(totals_query)
        totals = totals_result.one()

        # Waste by reason
        reason_query = select(
            FoodWasteLog.waste_reason,
            func.count(FoodWasteLog.id).label("count"),
        ).where(
            FoodWasteLog.venue_id == venue_id,
            FoodWasteLog.waste_date >= period_start,
            FoodWasteLog.waste_date <= period_end,
            FoodWasteLog.waste_reason.isnot(None),
        ).group_by(FoodWasteLog.waste_reason)
        reason_result = await self.db.execute(reason_query)
        waste_by_reason = {row.waste_reason: row.count for row in reason_result.all()}

        # Top wasted items
        top_items_query = (
            select(
                FoodWasteLog.menu_item_id,
                func.sum(FoodWasteLog.quantity_wasted).label("total_qty"),
                func.sum(FoodWasteLog.estimated_cost).label("total_cost"),
            )
            .where(
                FoodWasteLog.venue_id == venue_id,
                FoodWasteLog.waste_date >= period_start,
                FoodWasteLog.waste_date <= period_end,
                FoodWasteLog.menu_item_id.isnot(None),
            )
            .group_by(FoodWasteLog.menu_item_id)
            .order_by(func.sum(FoodWasteLog.estimated_cost).desc())
            .limit(10)
        )
        top_result = await self.db.execute(top_items_query)
        top_wasted_items = [
            {
                "menu_item_id": str(row.menu_item_id),
                "total_quantity": float(row.total_qty),
                "total_cost": float(row.total_cost) if row.total_cost else 0,
            }
            for row in top_result.all()
        ]

        return WasteAnalyticsResponse(
            venue_id=venue_id,
            period_start=period_start,
            period_end=period_end,
            total_waste_cost=Decimal(str(totals.total_cost)),
            total_items_wasted=totals.total_items,
            waste_by_reason=waste_by_reason,
            top_wasted_items=top_wasted_items,
        )
