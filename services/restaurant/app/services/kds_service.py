"""Kitchen Display System (KDS) service."""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.restaurant import (
    KDSItemStatus,
    KDSQueueItem,
    KitchenStation,
    RestaurantOrderItem,
)
from app.schemas.restaurant import KitchenStationCreate
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()


class KDSService:
    def __init__(self, db: AsyncSession, event_publisher: Optional[EventPublisher] = None):
        self.db = db
        self.event_publisher = event_publisher

    # ─── Stations ────────────────────────────────────────────────────────

    async def list_stations(self, venue_id: UUID) -> List[KitchenStation]:
        result = await self.db.execute(
            select(KitchenStation)
            .where(KitchenStation.venue_id == venue_id, KitchenStation.is_active == True)
            .order_by(KitchenStation.station_name)
        )
        return list(result.scalars().all())

    async def create_station(self, venue_id: UUID, data: KitchenStationCreate) -> KitchenStation:
        station = KitchenStation(
            venue_id=venue_id,
            station_name=data.station_name,
            station_type=data.station_type.value if data.station_type else None,
            printer_ip=data.printer_ip,
            is_active=data.is_active,
        )
        self.db.add(station)
        await self.db.commit()
        await self.db.refresh(station)
        return station

    # ─── Queue ───────────────────────────────────────────────────────────

    async def get_queue(
        self,
        venue_id: UUID,
        station_id: Optional[UUID] = None,
        status: Optional[KDSItemStatus] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[KDSQueueItem], int]:
        base_query = select(KDSQueueItem).join(
            RestaurantOrderItem, KDSQueueItem.order_item_id == RestaurantOrderItem.id, isouter=True
        )
        if station_id:
            base_query = base_query.where(KDSQueueItem.station_id == station_id)
        if status:
            base_query = base_query.where(KDSQueueItem.status == status.value)
        else:
            base_query = base_query.where(
                KDSQueueItem.status.in_([KDSItemStatus.QUEUED.value, KDSItemStatus.IN_PROGRESS.value])
            )

        count_result = await self.db.execute(select(func.count()).select_from(base_query.subquery()))
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        query = (
            base_query.options(selectinload(KDSQueueItem.order_item))
            .order_by(KDSQueueItem.priority.desc(), KDSQueueItem.created_at)
            .limit(page_size)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.scalars().unique().all()), total

    async def get_station_queue(self, station_id: UUID) -> List[KDSQueueItem]:
        return await self.get_queue(venue_id=None, station_id=station_id)

    async def start_item(self, kds_item_id: UUID) -> Optional[KDSQueueItem]:
        result = await self.db.execute(
            select(KDSQueueItem)
            .where(KDSQueueItem.id == kds_item_id)
            .options(selectinload(KDSQueueItem.order_item))
        )
        item = result.scalar_one_or_none()
        if not item:
            return None

        item.status = KDSItemStatus.IN_PROGRESS.value
        item.started_at = datetime.now(timezone.utc)

        # Update order item status
        if item.order_item:
            item.order_item.status = "PREPARING"
            item.order_item.fired_to_kitchen_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(item)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.KDS_ITEM_STARTED,
                {"kds_item_id": str(kds_item_id), "station_id": str(item.station_id)},
            )
        logger.info("kds_item_started", kds_item_id=str(kds_item_id))
        return item

    async def complete_item(self, kds_item_id: UUID) -> Optional[KDSQueueItem]:
        result = await self.db.execute(
            select(KDSQueueItem)
            .where(KDSQueueItem.id == kds_item_id)
            .options(selectinload(KDSQueueItem.order_item))
        )
        item = result.scalar_one_or_none()
        if not item:
            return None

        item.status = KDSItemStatus.COMPLETED.value
        item.completed_at = datetime.now(timezone.utc)

        # Update order item status
        if item.order_item:
            item.order_item.status = "READY"
            item.order_item.ready_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(item)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.KDS_ITEM_COMPLETED,
                {"kds_item_id": str(kds_item_id), "station_id": str(item.station_id)},
            )
        logger.info("kds_item_completed", kds_item_id=str(kds_item_id))
        return item

    async def fire_order_items_to_kds(
        self,
        order_item_ids: List[UUID],
        station_id: UUID,
        priority: int = 0,
    ) -> List[KDSQueueItem]:
        items = []
        for order_item_id in order_item_ids:
            kds_item = KDSQueueItem(
                order_item_id=order_item_id,
                station_id=station_id,
                priority=priority,
                status=KDSItemStatus.QUEUED.value,
            )
            self.db.add(kds_item)
            items.append(kds_item)

        await self.db.commit()
        for item in items:
            await self.db.refresh(item)
        logger.info("order_items_fired_to_kds", count=len(items), station_id=str(station_id))
        return items
