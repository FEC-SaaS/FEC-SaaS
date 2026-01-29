"""Table and section management service."""

from typing import List, Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant import (
    DiningTable,
    RestaurantSection,
    TableStatus,
)
from app.schemas.restaurant import (
    SectionCreate,
    SectionUpdate,
    TableCreate,
    TableStatusUpdate,
    TableUpdate,
)
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()


class TableService:
    def __init__(self, db: AsyncSession, event_publisher: Optional[EventPublisher] = None):
        self.db = db
        self.event_publisher = event_publisher

    # ─── Sections ────────────────────────────────────────────────────────

    async def list_sections(
        self,
        venue_id: UUID,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[RestaurantSection], int]:
        base_query = select(RestaurantSection).where(RestaurantSection.venue_id == venue_id)
        if is_active is not None:
            base_query = base_query.where(RestaurantSection.is_active == is_active)

        count_result = await self.db.execute(select(func.count()).select_from(base_query.subquery()))
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        query = base_query.order_by(RestaurantSection.section_name).limit(page_size).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create_section(self, venue_id: UUID, data: SectionCreate) -> RestaurantSection:
        section = RestaurantSection(
            venue_id=venue_id,
            section_name=data.section_name,
            section_type=data.section_type.value if data.section_type else None,
            capacity=data.capacity,
            is_active=data.is_active,
        )
        self.db.add(section)
        await self.db.commit()
        await self.db.refresh(section)
        logger.info("section_created", section_id=str(section.id), venue_id=str(venue_id))
        return section

    async def update_section(self, section_id: UUID, data: SectionUpdate) -> Optional[RestaurantSection]:
        result = await self.db.execute(select(RestaurantSection).where(RestaurantSection.id == section_id))
        section = result.scalar_one_or_none()
        if not section:
            return None
        update_data = data.model_dump(exclude_unset=True)
        if "section_type" in update_data and update_data["section_type"]:
            update_data["section_type"] = update_data["section_type"].value
        for key, value in update_data.items():
            setattr(section, key, value)
        await self.db.commit()
        await self.db.refresh(section)
        return section

    # ─── Tables ──────────────────────────────────────────────────────────

    async def list_tables(
        self,
        venue_id: UUID,
        section_id: Optional[UUID] = None,
        status: Optional[TableStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[DiningTable], int]:
        base_query = select(DiningTable).where(DiningTable.venue_id == venue_id)
        if section_id:
            base_query = base_query.where(DiningTable.section_id == section_id)
        if status:
            base_query = base_query.where(DiningTable.status == status.value)

        count_result = await self.db.execute(select(func.count()).select_from(base_query.subquery()))
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        query = base_query.order_by(DiningTable.table_number).limit(page_size).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_table(self, table_id: UUID) -> Optional[DiningTable]:
        result = await self.db.execute(select(DiningTable).where(DiningTable.id == table_id))
        return result.scalar_one_or_none()

    async def create_table(self, venue_id: UUID, data: TableCreate) -> DiningTable:
        table = DiningTable(
            venue_id=venue_id,
            section_id=data.section_id,
            table_number=data.table_number,
            seating_capacity=data.seating_capacity,
            table_type=data.table_type.value if data.table_type else None,
            qr_code=data.qr_code,
        )
        self.db.add(table)
        await self.db.commit()
        await self.db.refresh(table)
        logger.info("table_created", table_id=str(table.id), venue_id=str(venue_id))
        return table

    async def update_table_status(self, table_id: UUID, data: TableStatusUpdate) -> Optional[DiningTable]:
        table = await self.get_table(table_id)
        if not table:
            return None
        old_status = table.status
        table.status = data.status.value
        await self.db.commit()
        await self.db.refresh(table)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.TABLE_STATUS_CHANGED,
                {"table_id": str(table_id), "old_status": old_status, "new_status": data.status.value},
                venue_id=table.venue_id,
            )
        logger.info("table_status_updated", table_id=str(table_id), status=data.status.value)
        return table

    async def get_available_tables(
        self,
        venue_id: UUID,
        party_size: Optional[int] = None,
    ) -> List[DiningTable]:
        query = select(DiningTable).where(
            and_(
                DiningTable.venue_id == venue_id,
                DiningTable.status == TableStatus.AVAILABLE.value,
            )
        )
        if party_size:
            query = query.where(DiningTable.seating_capacity >= party_size)
        query = query.order_by(DiningTable.seating_capacity)
        result = await self.db.execute(query)
        return list(result.scalars().all())
