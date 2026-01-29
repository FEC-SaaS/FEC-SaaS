"""Menu management service."""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.restaurant import (
    MenuCategory,
    MenuItem,
    MenuItemModifier,
    MenuModifier,
    Recipe,
    RecipeIngredient,
)
from app.schemas.restaurant import (
    MenuCategoryCreate,
    MenuCategoryUpdate,
    MenuItemAvailabilityUpdate,
    MenuItemCreate,
    MenuItemUpdate,
    MenuModifierCreate,
    RecipeCostResponse,
)
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()
settings = get_settings()


class MenuService:
    def __init__(self, db: AsyncSession, event_publisher: Optional[EventPublisher] = None):
        self.db = db
        self.event_publisher = event_publisher

    # ─── Categories ──────────────────────────────────────────────────────

    async def list_categories(
        self,
        venue_id: UUID,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[MenuCategory], int]:
        base_query = select(MenuCategory).where(MenuCategory.venue_id == venue_id)
        if is_active is not None:
            base_query = base_query.where(MenuCategory.is_active == is_active)

        count_result = await self.db.execute(select(func.count()).select_from(base_query.subquery()))
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        query = base_query.order_by(MenuCategory.display_order, MenuCategory.category_name).limit(page_size).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create_category(self, venue_id: UUID, data: MenuCategoryCreate) -> MenuCategory:
        category = MenuCategory(
            venue_id=venue_id,
            category_name=data.category_name,
            category_type=data.category_type.value if data.category_type else None,
            display_order=data.display_order,
            available_times=[t.value for t in data.available_times] if data.available_times else None,
            is_active=data.is_active,
        )
        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)
        logger.info("menu_category_created", category_id=str(category.id))
        return category

    async def update_category(self, category_id: UUID, data: MenuCategoryUpdate) -> Optional[MenuCategory]:
        result = await self.db.execute(select(MenuCategory).where(MenuCategory.id == category_id))
        category = result.scalar_one_or_none()
        if not category:
            return None
        update_data = data.model_dump(exclude_unset=True)
        if "category_type" in update_data and update_data["category_type"]:
            update_data["category_type"] = update_data["category_type"].value
        if "available_times" in update_data and update_data["available_times"]:
            update_data["available_times"] = [t.value for t in update_data["available_times"]]
        for key, value in update_data.items():
            setattr(category, key, value)
        await self.db.commit()
        await self.db.refresh(category)
        return category

    # ─── Items ───────────────────────────────────────────────────────────

    async def list_items(
        self,
        venue_id: UUID,
        category_id: Optional[UUID] = None,
        is_available: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[MenuItem], int]:
        base_query = select(MenuItem).where(MenuItem.venue_id == venue_id)
        if category_id:
            base_query = base_query.where(MenuItem.category_id == category_id)
        if is_available is not None:
            base_query = base_query.where(MenuItem.is_available == is_available)

        count_result = await self.db.execute(select(func.count()).select_from(base_query.subquery()))
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        query = base_query.order_by(MenuItem.item_name).limit(page_size).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_item(self, item_id: UUID) -> Optional[MenuItem]:
        result = await self.db.execute(select(MenuItem).where(MenuItem.id == item_id))
        return result.scalar_one_or_none()

    async def create_item(self, venue_id: UUID, data: MenuItemCreate) -> MenuItem:
        item = MenuItem(
            venue_id=venue_id,
            category_id=data.category_id,
            item_name=data.item_name,
            description=data.description,
            base_price=data.base_price,
            cost_of_goods=data.cost_of_goods,
            prep_time_minutes=data.prep_time_minutes,
            calories=data.calories,
            protein_grams=data.protein_grams,
            allergens=data.allergens,
            dietary_tags=data.dietary_tags,
            spice_level=data.spice_level,
            is_available=data.is_available,
            image_url=data.image_url,
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        logger.info("menu_item_created", item_id=str(item.id))
        return item

    async def update_item(self, item_id: UUID, data: MenuItemUpdate) -> Optional[MenuItem]:
        item = await self.get_item(item_id)
        if not item:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(item, key, value)
        await self.db.commit()
        await self.db.refresh(item)

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.MENU_ITEM_UPDATED,
                {"item_id": str(item_id), "item_name": item.item_name},
                venue_id=item.venue_id,
            )
        return item

    async def update_item_availability(self, item_id: UUID, data: MenuItemAvailabilityUpdate) -> Optional[MenuItem]:
        item = await self.get_item(item_id)
        if not item:
            return None
        item.is_available = data.is_available
        await self.db.commit()
        await self.db.refresh(item)
        logger.info("menu_item_availability_updated", item_id=str(item_id), is_available=data.is_available)
        return item

    # ─── Full Menu ───────────────────────────────────────────────────────

    async def get_full_menu(self, venue_id: UUID) -> List[MenuCategory]:
        query = (
            select(MenuCategory)
            .where(MenuCategory.venue_id == venue_id, MenuCategory.is_active == True)
            .options(selectinload(MenuCategory.items))
            .order_by(MenuCategory.display_order, MenuCategory.category_name)
        )
        result = await self.db.execute(query)
        return list(result.scalars().unique().all())

    # ─── Modifiers ───────────────────────────────────────────────────────

    async def list_modifiers(self, venue_id: UUID) -> List[MenuModifier]:
        result = await self.db.execute(
            select(MenuModifier).where(MenuModifier.venue_id == venue_id).order_by(MenuModifier.modifier_name)
        )
        return list(result.scalars().all())

    async def create_modifier(self, venue_id: UUID, data: MenuModifierCreate) -> MenuModifier:
        modifier = MenuModifier(
            venue_id=venue_id,
            modifier_name=data.modifier_name,
            modifier_type=data.modifier_type.value if data.modifier_type else None,
            price_adjustment=data.price_adjustment,
            is_active=data.is_active,
        )
        self.db.add(modifier)
        await self.db.commit()
        await self.db.refresh(modifier)
        return modifier

    # ─── Recipe Cost Calculation ─────────────────────────────────────────

    async def calculate_recipe_cost(self, recipe_id: UUID) -> Optional[RecipeCostResponse]:
        """Calculate the cost of a recipe by fetching ingredient prices from the Inventory Service."""
        result = await self.db.execute(
            select(Recipe)
            .where(Recipe.id == recipe_id)
            .options(selectinload(Recipe.ingredients))
        )
        recipe = result.scalar_one_or_none()
        if not recipe:
            return None

        total_cost = Decimal("0")
        ingredient_details = []

        # Gather inventory_item_ids to fetch from Inventory Service
        inv_ids = [
            str(ing.inventory_item_id)
            for ing in recipe.ingredients
            if ing.inventory_item_id
        ]

        inv_prices: Dict[str, Decimal] = {}
        if inv_ids:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"{settings.INVENTORY_SERVICE_URL}/api/v1/inventory/items/bulk",
                        params={"ids": ",".join(inv_ids)},
                    )
                    if response.status_code == 200:
                        for item in response.json():
                            inv_prices[item["id"]] = Decimal(str(item.get("unit_cost", 0)))
            except Exception as e:
                logger.warning("inventory_service_unavailable", error=str(e))

        for ingredient in recipe.ingredients:
            unit_cost = Decimal("0")
            if ingredient.inventory_item_id:
                unit_cost = inv_prices.get(str(ingredient.inventory_item_id), Decimal("0"))
            line_cost = unit_cost * ingredient.quantity
            total_cost += line_cost

            ingredient_details.append({
                "ingredient_id": str(ingredient.id),
                "inventory_item_id": str(ingredient.inventory_item_id) if ingredient.inventory_item_id else None,
                "quantity": float(ingredient.quantity),
                "unit": ingredient.unit,
                "unit_cost": float(unit_cost),
                "line_cost": float(line_cost),
                "notes": ingredient.notes,
            })

        cost_per_serving = total_cost / recipe.yield_servings if recipe.yield_servings > 0 else total_cost

        return RecipeCostResponse(
            recipe_id=recipe.id,
            recipe_name=recipe.recipe_name,
            total_ingredient_cost=total_cost,
            yield_servings=recipe.yield_servings,
            cost_per_serving=cost_per_serving,
            ingredients=ingredient_details,
        )
