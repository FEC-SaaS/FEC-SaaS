"""Order management service."""

import math
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.restaurant import (
    MenuItem,
    OrderItemStatus,
    OrderStatus,
    OrderType,
    RestaurantOrder,
    RestaurantOrderItem,
    VenueTaxConfig,
)
from app.schemas.restaurant import OrderCreate, OrderItemCreate, OrderStatusUpdate
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()

DEFAULT_TAX_RATE = Decimal("0.0800")


class OrderService:
    def __init__(self, db: AsyncSession, event_publisher: Optional[EventPublisher] = None):
        self.db = db
        self.event_publisher = event_publisher

    async def _get_tax_rate(self, venue_id: UUID, order_type: Optional[str] = None) -> Decimal:
        """Get the tax rate for a venue, with order-type-specific overrides."""
        result = await self.db.execute(
            select(VenueTaxConfig).where(VenueTaxConfig.venue_id == venue_id)
        )
        config = result.scalar_one_or_none()
        if not config:
            return DEFAULT_TAX_RATE

        if order_type == OrderType.DELIVERY.value and config.delivery_tax_rate is not None:
            return config.delivery_tax_rate
        if order_type == OrderType.TAKEOUT.value and config.takeout_tax_rate is not None:
            return config.takeout_tax_rate
        return config.tax_rate

    async def get_order(self, order_id: UUID) -> Optional[RestaurantOrder]:
        result = await self.db.execute(
            select(RestaurantOrder)
            .where(RestaurantOrder.id == order_id)
            .options(selectinload(RestaurantOrder.items))
        )
        return result.scalar_one_or_none()

    async def list_orders(
        self,
        venue_id: UUID,
        status: Optional[OrderStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[RestaurantOrder], int]:
        base_query = select(RestaurantOrder).where(RestaurantOrder.venue_id == venue_id)
        if status:
            base_query = base_query.where(RestaurantOrder.status == status.value)

        # Count
        count_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar() or 0

        # Items
        offset = (page - 1) * page_size
        query = (
            base_query
            .options(selectinload(RestaurantOrder.items))
            .order_by(RestaurantOrder.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        result = await self.db.execute(query)
        items = list(result.scalars().unique().all())
        return items, total

    async def create_order(self, venue_id: UUID, data: OrderCreate) -> RestaurantOrder:
        # Fetch menu items to get prices
        item_ids = [item.menu_item_id for item in data.items]
        menu_result = await self.db.execute(select(MenuItem).where(MenuItem.id.in_(item_ids)))
        menu_items = {str(mi.id): mi for mi in menu_result.scalars().all()}

        # Calculate totals
        subtotal = Decimal("0")
        order_items = []
        for item_data in data.items:
            menu_item = menu_items.get(str(item_data.menu_item_id))
            unit_price = menu_item.base_price if menu_item else Decimal("0")
            line_total = unit_price * item_data.quantity
            subtotal += line_total

            order_items.append(
                RestaurantOrderItem(
                    menu_item_id=item_data.menu_item_id,
                    quantity=item_data.quantity,
                    unit_price=unit_price,
                    modifiers=item_data.modifiers,
                    special_requests=item_data.special_requests,
                    status=OrderItemStatus.PENDING.value,
                )
            )

        # Get venue-specific tax rate
        order_type_val = data.order_type.value if data.order_type else None
        tax_rate = await self._get_tax_rate(venue_id, order_type_val)
        tax = subtotal * tax_rate
        total = subtotal + tax

        order = RestaurantOrder(
            venue_id=venue_id,
            customer_id=data.customer_id,
            order_type=order_type_val,
            order_source=data.order_source.value if data.order_source else None,
            table_id=data.table_id,
            party_booking_id=data.party_booking_id,
            server_staff_id=data.server_staff_id,
            subtotal=subtotal,
            tax=tax,
            total=total,
            special_instructions=data.special_instructions,
            status=OrderStatus.PENDING.value,
            items=order_items,
        )
        self.db.add(order)
        await self.db.commit()
        await self.db.refresh(order)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.ORDER_CREATED,
                {
                    "order_id": str(order.id),
                    "order_type": order.order_type,
                    "total": str(order.total),
                    "item_count": len(order_items),
                    "tax_rate": str(tax_rate),
                },
                venue_id=venue_id,
            )
        logger.info("order_created", order_id=str(order.id), total=str(total), tax_rate=str(tax_rate))
        return order

    async def update_order_status(self, order_id: UUID, data: OrderStatusUpdate) -> Optional[RestaurantOrder]:
        order = await self.get_order(order_id)
        if not order:
            return None

        old_status = order.status
        order.status = data.status.value

        if data.status == OrderStatus.READY:
            from datetime import datetime, timezone
            order.ready_at = datetime.now(timezone.utc)
        elif data.status == OrderStatus.DELIVERED:
            from datetime import datetime, timezone
            order.delivered_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(order)

        event_type = EventType.ORDER_STATUS_CHANGED
        if data.status == OrderStatus.COMPLETED:
            event_type = EventType.ORDER_COMPLETED
        elif data.status == OrderStatus.CANCELLED:
            event_type = EventType.ORDER_CANCELLED

        if self.event_publisher:
            await self.event_publisher.publish(
                event_type,
                {"order_id": str(order_id), "old_status": old_status, "new_status": data.status.value},
                venue_id=order.venue_id,
            )
        logger.info("order_status_updated", order_id=str(order_id), status=data.status.value)
        return order

    async def add_items_to_order(self, order_id: UUID, items: List[OrderItemCreate]) -> Optional[RestaurantOrder]:
        order = await self.get_order(order_id)
        if not order:
            return None

        item_ids = [item.menu_item_id for item in items]
        menu_result = await self.db.execute(select(MenuItem).where(MenuItem.id.in_(item_ids)))
        menu_items = {str(mi.id): mi for mi in menu_result.scalars().all()}

        added_subtotal = Decimal("0")
        for item_data in items:
            menu_item = menu_items.get(str(item_data.menu_item_id))
            unit_price = menu_item.base_price if menu_item else Decimal("0")
            added_subtotal += unit_price * item_data.quantity

            order_item = RestaurantOrderItem(
                order_id=order_id,
                menu_item_id=item_data.menu_item_id,
                quantity=item_data.quantity,
                unit_price=unit_price,
                modifiers=item_data.modifiers,
                special_requests=item_data.special_requests,
                status=OrderItemStatus.PENDING.value,
            )
            self.db.add(order_item)

        # Recalculate totals with venue-specific tax
        order.subtotal += added_subtotal
        tax_rate = await self._get_tax_rate(order.venue_id, order.order_type)
        order.tax = order.subtotal * tax_rate
        order.total = order.subtotal + order.tax + (order.tip or Decimal("0")) + (order.delivery_fee or Decimal("0"))

        await self.db.commit()
        await self.db.refresh(order)
        logger.info("order_items_added", order_id=str(order_id), items_added=len(items))
        return order
