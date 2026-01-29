"""Bar inventory and pour tracking service."""

from typing import List, Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant import BarInventory, BarPour
from app.schemas.restaurant import BarInventoryCreate, BarInventoryUpdate, BarPourCreate
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()


class BarService:
    def __init__(self, db: AsyncSession, event_publisher: Optional[EventPublisher] = None):
        self.db = db
        self.event_publisher = event_publisher

    async def list_inventory(
        self,
        venue_id: UUID,
        product_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[BarInventory], int]:
        base_query = select(BarInventory).where(BarInventory.venue_id == venue_id)
        if product_type:
            base_query = base_query.where(BarInventory.product_type == product_type)

        count_result = await self.db.execute(select(func.count()).select_from(base_query.subquery()))
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        query = base_query.order_by(BarInventory.product_name).limit(page_size).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create_inventory_item(self, venue_id: UUID, data: BarInventoryCreate) -> BarInventory:
        item = BarInventory(
            venue_id=venue_id,
            product_name=data.product_name,
            product_type=data.product_type.value if data.product_type else None,
            brand=data.brand,
            size_ml=data.size_ml,
            abv_percentage=data.abv_percentage,
            quantity_in_stock=data.quantity_in_stock,
            par_level=data.par_level,
            cost_per_unit=data.cost_per_unit,
            price_per_unit=data.price_per_unit,
            supplier=data.supplier,
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        logger.info("bar_inventory_created", item_id=str(item.id))
        return item

    async def update_inventory_item(self, item_id: UUID, data: BarInventoryUpdate) -> Optional[BarInventory]:
        result = await self.db.execute(select(BarInventory).where(BarInventory.id == item_id))
        item = result.scalar_one_or_none()
        if not item:
            return None
        update_data = data.model_dump(exclude_unset=True)
        if "product_type" in update_data and update_data["product_type"]:
            update_data["product_type"] = update_data["product_type"].value
        for key, value in update_data.items():
            setattr(item, key, value)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def record_pour(self, venue_id: UUID, data: BarPourCreate) -> BarPour:
        pour = BarPour(
            order_item_id=data.order_item_id,
            bar_inventory_id=data.bar_inventory_id,
            quantity_poured_ml=data.quantity_poured_ml,
            bartender_staff_id=data.bartender_staff_id,
        )
        self.db.add(pour)

        # Deduct from inventory
        inv_result = await self.db.execute(
            select(BarInventory).where(BarInventory.id == data.bar_inventory_id)
        )
        inv = inv_result.scalar_one_or_none()
        if inv and inv.quantity_in_stock is not None:
            inv.quantity_in_stock -= data.quantity_poured_ml
            # Check low stock
            if inv.par_level and inv.quantity_in_stock <= inv.par_level:
                if self.event_publisher:
                    await self.event_publisher.publish(
                        EventType.BAR_LOW_STOCK,
                        {
                            "product_id": str(inv.id),
                            "product_name": inv.product_name,
                            "quantity_in_stock": str(inv.quantity_in_stock),
                            "par_level": str(inv.par_level),
                        },
                        venue_id=venue_id,
                    )
                logger.warning("bar_low_stock", product_id=str(inv.id), product_name=inv.product_name)

        await self.db.commit()
        await self.db.refresh(pour)
        logger.info("bar_pour_recorded", pour_id=str(pour.id))
        return pour

    async def get_low_stock(self, venue_id: UUID) -> List[BarInventory]:
        result = await self.db.execute(
            select(BarInventory).where(
                BarInventory.venue_id == venue_id,
                BarInventory.par_level.isnot(None),
                BarInventory.quantity_in_stock <= BarInventory.par_level,
            ).order_by(BarInventory.product_name)
        )
        return list(result.scalars().all())
