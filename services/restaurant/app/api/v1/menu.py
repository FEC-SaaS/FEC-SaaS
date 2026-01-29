"""Menu API routes."""

import math
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.restaurant import (
    FullMenuResponse,
    MenuCategoryCreate,
    MenuCategoryResponse,
    MenuCategoryUpdate,
    MenuCategoryWithItems,
    MenuItemAvailabilityUpdate,
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate,
    MenuModifierCreate,
    MenuModifierResponse,
    PaginatedResponse,
    RecipeCostResponse,
)
from app.services.event_publisher import event_publisher
from app.services.menu_service import MenuService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> MenuService:
    return MenuService(db, event_publisher)


@router.get("/menu", response_model=FullMenuResponse)
async def get_full_menu(
    venue_id: UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(_get_service),
):
    categories = await service.get_full_menu(venue_id)
    return FullMenuResponse(
        venue_id=venue_id,
        categories=[MenuCategoryWithItems.model_validate(c) for c in categories],
    )


@router.get("/menu/categories", response_model=PaginatedResponse)
async def list_categories(
    venue_id: UUID = Query(...),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(_get_service),
):
    if page_size is None:
        page_size = settings.DEFAULT_PAGE_SIZE
    items, total = await service.list_categories(venue_id, is_active, page, page_size)
    return PaginatedResponse(
        items=[MenuCategoryResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.post("/menu/categories", response_model=MenuCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    venue_id: UUID = Query(...),
    data: MenuCategoryCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(_get_service),
):
    return await service.create_category(venue_id, data)


@router.put("/menu/categories/{category_id}", response_model=MenuCategoryResponse)
async def update_category(
    category_id: UUID,
    data: MenuCategoryUpdate,
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(_get_service),
):
    result = await service.update_category(category_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Category not found")
    return result


@router.get("/menu/items", response_model=PaginatedResponse)
async def list_items(
    venue_id: UUID = Query(...),
    category_id: Optional[UUID] = Query(None),
    is_available: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(_get_service),
):
    if page_size is None:
        page_size = settings.DEFAULT_PAGE_SIZE
    items, total = await service.list_items(venue_id, category_id, is_available, page, page_size)
    return PaginatedResponse(
        items=[MenuItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.post("/menu/items", response_model=MenuItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    venue_id: UUID = Query(...),
    data: MenuItemCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(_get_service),
):
    return await service.create_item(venue_id, data)


@router.put("/menu/items/{item_id}", response_model=MenuItemResponse)
async def update_item(
    item_id: UUID,
    data: MenuItemUpdate,
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(_get_service),
):
    result = await service.update_item(item_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return result


@router.patch("/menu/items/{item_id}/availability", response_model=MenuItemResponse)
async def update_item_availability(
    item_id: UUID,
    data: MenuItemAvailabilityUpdate,
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(_get_service),
):
    result = await service.update_item_availability(item_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return result


@router.get("/menu/modifiers", response_model=List[MenuModifierResponse])
async def list_modifiers(
    venue_id: UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(_get_service),
):
    return await service.list_modifiers(venue_id)


@router.post("/menu/modifiers", response_model=MenuModifierResponse, status_code=status.HTTP_201_CREATED)
async def create_modifier(
    venue_id: UUID = Query(...),
    data: MenuModifierCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(_get_service),
):
    return await service.create_modifier(venue_id, data)


@router.get("/menu/recipes/{recipe_id}/cost", response_model=RecipeCostResponse)
async def get_recipe_cost(
    recipe_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(_get_service),
):
    result = await service.calculate_recipe_cost(recipe_id)
    if not result:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return result
