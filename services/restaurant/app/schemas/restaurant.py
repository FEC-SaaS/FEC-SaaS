"""Restaurant service Pydantic schemas."""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.restaurant import (
    BarProductType,
    CategoryType,
    KDSItemStatus,
    MealTime,
    MenuBoardLayout,
    ModifierType,
    OrderItemStatus,
    OrderSource,
    OrderStatus,
    OrderType,
    ReservationStatus,
    SectionType,
    StationType,
    TableStatus,
    TableType,
    WasteReason,
)


class BaseSchema(BaseModel):
    model_config = {"from_attributes": True}


# ─── Sections ────────────────────────────────────────────────────────────────

class SectionCreate(BaseSchema):
    section_name: str = Field(..., max_length=100)
    section_type: Optional[SectionType] = None
    capacity: Optional[int] = Field(None, ge=1)
    is_active: bool = True


class SectionUpdate(BaseSchema):
    section_name: Optional[str] = Field(None, max_length=100)
    section_type: Optional[SectionType] = None
    capacity: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class SectionResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    section_name: str
    section_type: Optional[str] = None
    capacity: Optional[int] = None
    is_active: bool
    created_at: datetime


# ─── Tables ──────────────────────────────────────────────────────────────────

class TableCreate(BaseSchema):
    section_id: Optional[UUID] = None
    table_number: str = Field(..., max_length=20)
    seating_capacity: int = Field(..., ge=1)
    table_type: Optional[TableType] = None
    qr_code: Optional[str] = None


class TableUpdate(BaseSchema):
    section_id: Optional[UUID] = None
    table_number: Optional[str] = Field(None, max_length=20)
    seating_capacity: Optional[int] = Field(None, ge=1)
    table_type: Optional[TableType] = None
    status: Optional[TableStatus] = None
    qr_code: Optional[str] = None


class TableStatusUpdate(BaseSchema):
    status: TableStatus


class TableResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    section_id: Optional[UUID] = None
    table_number: str
    seating_capacity: int
    table_type: Optional[str] = None
    status: str
    qr_code: Optional[str] = None
    created_at: datetime
    section: Optional[SectionResponse] = None


class TableAvailabilityQuery(BaseSchema):
    reservation_date: Optional[date] = None
    reservation_time: Optional[time] = None
    party_size: Optional[int] = Field(None, ge=1)


# ─── Reservations ────────────────────────────────────────────────────────────

class ReservationCreate(BaseSchema):
    customer_id: Optional[UUID] = None
    table_id: Optional[UUID] = None
    reservation_date: date
    reservation_time: time
    party_size: int = Field(..., ge=1)
    special_requests: Optional[str] = None


class ReservationUpdate(BaseSchema):
    table_id: Optional[UUID] = None
    reservation_date: Optional[date] = None
    reservation_time: Optional[time] = None
    party_size: Optional[int] = Field(None, ge=1)
    special_requests: Optional[str] = None
    status: Optional[ReservationStatus] = None


class ReservationSeat(BaseSchema):
    table_id: Optional[UUID] = None


class ReservationResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    customer_id: Optional[UUID] = None
    table_id: Optional[UUID] = None
    reservation_date: date
    reservation_time: time
    party_size: int
    special_requests: Optional[str] = None
    status: str
    seated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    table: Optional[TableResponse] = None


# ─── Menu Categories ─────────────────────────────────────────────────────────

class MenuCategoryCreate(BaseSchema):
    category_name: str = Field(..., max_length=100)
    category_type: Optional[CategoryType] = None
    display_order: Optional[int] = None
    available_times: Optional[List[MealTime]] = None
    is_active: bool = True


class MenuCategoryUpdate(BaseSchema):
    category_name: Optional[str] = Field(None, max_length=100)
    category_type: Optional[CategoryType] = None
    display_order: Optional[int] = None
    available_times: Optional[List[MealTime]] = None
    is_active: Optional[bool] = None


class MenuCategoryResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    category_name: str
    category_type: Optional[str] = None
    display_order: Optional[int] = None
    available_times: Optional[List[str]] = None
    is_active: bool
    created_at: datetime


# ─── Menu Items ──────────────────────────────────────────────────────────────

class MenuItemCreate(BaseSchema):
    category_id: Optional[UUID] = None
    item_name: str = Field(..., max_length=255)
    description: Optional[str] = None
    base_price: Decimal = Field(..., ge=0)
    cost_of_goods: Optional[Decimal] = Field(None, ge=0)
    prep_time_minutes: Optional[int] = Field(None, ge=0)
    calories: Optional[int] = Field(None, ge=0)
    protein_grams: Optional[Decimal] = Field(None, ge=0)
    allergens: Optional[List[str]] = None
    dietary_tags: Optional[List[str]] = None
    spice_level: Optional[int] = Field(None, ge=0, le=5)
    is_available: bool = True
    image_url: Optional[str] = None


class MenuItemUpdate(BaseSchema):
    category_id: Optional[UUID] = None
    item_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    base_price: Optional[Decimal] = Field(None, ge=0)
    cost_of_goods: Optional[Decimal] = Field(None, ge=0)
    prep_time_minutes: Optional[int] = Field(None, ge=0)
    calories: Optional[int] = Field(None, ge=0)
    protein_grams: Optional[Decimal] = Field(None, ge=0)
    allergens: Optional[List[str]] = None
    dietary_tags: Optional[List[str]] = None
    spice_level: Optional[int] = Field(None, ge=0, le=5)
    is_available: Optional[bool] = None
    image_url: Optional[str] = None


class MenuItemAvailabilityUpdate(BaseSchema):
    is_available: bool


class MenuItemResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    category_id: Optional[UUID] = None
    item_name: str
    description: Optional[str] = None
    base_price: Decimal
    cost_of_goods: Optional[Decimal] = None
    prep_time_minutes: Optional[int] = None
    calories: Optional[int] = None
    protein_grams: Optional[Decimal] = None
    allergens: Optional[List[str]] = None
    dietary_tags: Optional[List[str]] = None
    spice_level: Optional[int] = None
    is_available: bool
    popularity_score: Optional[Decimal] = None
    image_url: Optional[str] = None
    created_at: datetime


# ─── Menu Modifiers ──────────────────────────────────────────────────────────

class MenuModifierCreate(BaseSchema):
    modifier_name: str = Field(..., max_length=100)
    modifier_type: Optional[ModifierType] = None
    price_adjustment: Decimal = Field(default=0)
    is_active: bool = True


class MenuModifierResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    modifier_name: str
    modifier_type: Optional[str] = None
    price_adjustment: Decimal
    is_active: bool
    created_at: datetime


# ─── Full Menu Response ──────────────────────────────────────────────────────

class MenuCategoryWithItems(MenuCategoryResponse):
    items: List[MenuItemResponse] = []


class FullMenuResponse(BaseSchema):
    venue_id: UUID
    categories: List[MenuCategoryWithItems] = []


# ─── Orders ──────────────────────────────────────────────────────────────────

class OrderItemCreate(BaseSchema):
    menu_item_id: UUID
    quantity: int = Field(default=1, ge=1)
    modifiers: Optional[Dict[str, Any]] = None
    special_requests: Optional[str] = None


class OrderCreate(BaseSchema):
    customer_id: Optional[UUID] = None
    order_type: Optional[OrderType] = None
    order_source: Optional[OrderSource] = None
    table_id: Optional[UUID] = None
    party_booking_id: Optional[UUID] = None
    server_staff_id: Optional[UUID] = None
    special_instructions: Optional[str] = None
    items: List[OrderItemCreate] = Field(..., min_length=1)


class OrderStatusUpdate(BaseSchema):
    status: OrderStatus


class OrderItemResponse(BaseSchema):
    id: UUID
    order_id: UUID
    menu_item_id: Optional[UUID] = None
    quantity: int
    unit_price: Decimal
    modifiers: Optional[Dict[str, Any]] = None
    special_requests: Optional[str] = None
    status: str
    fired_to_kitchen_at: Optional[datetime] = None
    ready_at: Optional[datetime] = None
    served_at: Optional[datetime] = None
    created_at: datetime


class OrderResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    customer_id: Optional[UUID] = None
    order_type: Optional[str] = None
    order_source: Optional[str] = None
    table_id: Optional[UUID] = None
    party_booking_id: Optional[UUID] = None
    server_staff_id: Optional[UUID] = None
    subtotal: Decimal
    tax: Optional[Decimal] = None
    tip: Optional[Decimal] = None
    delivery_fee: Optional[Decimal] = None
    total: Decimal
    status: str
    ordered_at: datetime
    ready_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    special_instructions: Optional[str] = None
    created_at: datetime
    items: List[OrderItemResponse] = []


# ─── KDS ─────────────────────────────────────────────────────────────────────

class KitchenStationCreate(BaseSchema):
    station_name: str = Field(..., max_length=100)
    station_type: Optional[StationType] = None
    printer_ip: Optional[str] = None
    is_active: bool = True


class KitchenStationResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    station_name: str
    station_type: Optional[str] = None
    printer_ip: Optional[str] = None
    is_active: bool
    created_at: datetime


class KDSQueueItemResponse(BaseSchema):
    id: UUID
    order_item_id: Optional[UUID] = None
    station_id: Optional[UUID] = None
    priority: int
    estimated_prep_minutes: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    status: str
    created_at: datetime
    order_item: Optional[OrderItemResponse] = None


# ─── Bar ─────────────────────────────────────────────────────────────────────

class BarInventoryCreate(BaseSchema):
    product_name: str = Field(..., max_length=255)
    product_type: Optional[BarProductType] = None
    brand: Optional[str] = Field(None, max_length=100)
    size_ml: Optional[int] = Field(None, ge=0)
    abv_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    quantity_in_stock: Optional[Decimal] = Field(None, ge=0)
    par_level: Optional[Decimal] = Field(None, ge=0)
    cost_per_unit: Optional[Decimal] = Field(None, ge=0)
    price_per_unit: Optional[Decimal] = Field(None, ge=0)
    supplier: Optional[str] = Field(None, max_length=100)


class BarInventoryUpdate(BaseSchema):
    product_name: Optional[str] = Field(None, max_length=255)
    product_type: Optional[BarProductType] = None
    brand: Optional[str] = Field(None, max_length=100)
    quantity_in_stock: Optional[Decimal] = Field(None, ge=0)
    par_level: Optional[Decimal] = Field(None, ge=0)
    cost_per_unit: Optional[Decimal] = Field(None, ge=0)
    price_per_unit: Optional[Decimal] = Field(None, ge=0)
    supplier: Optional[str] = Field(None, max_length=100)


class BarInventoryResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    product_name: str
    product_type: Optional[str] = None
    brand: Optional[str] = None
    size_ml: Optional[int] = None
    abv_percentage: Optional[Decimal] = None
    quantity_in_stock: Optional[Decimal] = None
    par_level: Optional[Decimal] = None
    cost_per_unit: Optional[Decimal] = None
    price_per_unit: Optional[Decimal] = None
    supplier: Optional[str] = None
    last_restocked_at: Optional[datetime] = None
    created_at: datetime


class BarPourCreate(BaseSchema):
    order_item_id: Optional[UUID] = None
    bar_inventory_id: UUID
    quantity_poured_ml: Decimal = Field(..., ge=0)
    bartender_staff_id: Optional[UUID] = None


class BarPourResponse(BaseSchema):
    id: UUID
    order_item_id: Optional[UUID] = None
    bar_inventory_id: Optional[UUID] = None
    quantity_poured_ml: Optional[Decimal] = None
    bartender_staff_id: Optional[UUID] = None
    poured_at: datetime


# ─── Waste ───────────────────────────────────────────────────────────────────

class FoodWasteCreate(BaseSchema):
    waste_date: date
    menu_item_id: Optional[UUID] = None
    inventory_item_id: Optional[UUID] = None
    quantity_wasted: Decimal = Field(..., ge=0)
    waste_reason: Optional[WasteReason] = None
    estimated_cost: Optional[Decimal] = Field(None, ge=0)
    logged_by: Optional[UUID] = None


class FoodWasteResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    waste_date: date
    menu_item_id: Optional[UUID] = None
    inventory_item_id: Optional[UUID] = None
    quantity_wasted: Decimal
    waste_reason: Optional[str] = None
    estimated_cost: Optional[Decimal] = None
    logged_by: Optional[UUID] = None
    created_at: datetime


class WasteAnalyticsResponse(BaseSchema):
    venue_id: UUID
    period_start: date
    period_end: date
    total_waste_cost: Decimal
    total_items_wasted: int
    waste_by_reason: Dict[str, int] = {}
    top_wasted_items: List[Dict[str, Any]] = []


# ─── Digital Menu Boards ─────────────────────────────────────────────────────

class DigitalMenuBoardCreate(BaseSchema):
    board_name: Optional[str] = Field(None, max_length=100)
    board_location: Optional[str] = Field(None, max_length=100)
    display_categories: Optional[List[str]] = None
    layout_type: Optional[MenuBoardLayout] = None
    is_active: bool = True


class DigitalMenuBoardUpdate(BaseSchema):
    board_name: Optional[str] = Field(None, max_length=100)
    board_location: Optional[str] = Field(None, max_length=100)
    display_categories: Optional[List[str]] = None
    layout_type: Optional[MenuBoardLayout] = None
    is_active: Optional[bool] = None


class DigitalMenuBoardResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    board_name: Optional[str] = None
    board_location: Optional[str] = None
    display_categories: Optional[List[str]] = None
    layout_type: Optional[str] = None
    is_active: bool
    created_at: datetime


# ─── Happy Hour ──────────────────────────────────────────────────────────────

class HappyHourCreate(BaseSchema):
    schedule_name: Optional[str] = Field(None, max_length=100)
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: time
    end_time: time
    discount_percentage: Decimal = Field(..., ge=0, le=100)
    affected_categories: Optional[List[str]] = None
    is_active: bool = True


class HappyHourResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    schedule_name: Optional[str] = None
    day_of_week: Optional[int] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    discount_percentage: Optional[Decimal] = None
    affected_categories: Optional[List[str]] = None
    is_active: bool
    created_at: datetime


# ─── Recipes ─────────────────────────────────────────────────────────────────

class RecipeIngredientCreate(BaseSchema):
    inventory_item_id: Optional[UUID] = None
    quantity: Decimal = Field(..., ge=0)
    unit: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None


class RecipeCreate(BaseSchema):
    menu_item_id: Optional[UUID] = None
    recipe_name: str = Field(..., max_length=255)
    instructions: Optional[str] = None
    prep_time_minutes: Optional[int] = Field(None, ge=0)
    cook_time_minutes: Optional[int] = Field(None, ge=0)
    yield_servings: int = Field(default=1, ge=1)
    ingredients: List[RecipeIngredientCreate] = []


class RecipeIngredientResponse(BaseSchema):
    id: UUID
    recipe_id: UUID
    inventory_item_id: Optional[UUID] = None
    quantity: Decimal
    unit: Optional[str] = None
    notes: Optional[str] = None


class RecipeResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    menu_item_id: Optional[UUID] = None
    recipe_name: str
    instructions: Optional[str] = None
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    yield_servings: int
    created_at: datetime
    ingredients: List[RecipeIngredientResponse] = []


# ─── Venue Tax Config ────────────────────────────────────────────────────────

class VenueTaxConfigCreate(BaseSchema):
    tax_rate: Decimal = Field(default=Decimal("0.0800"), ge=0, le=1)
    tax_name: str = Field(default="Sales Tax", max_length=50)
    delivery_tax_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    takeout_tax_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    is_tax_inclusive: bool = False


class VenueTaxConfigUpdate(BaseSchema):
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    tax_name: Optional[str] = Field(None, max_length=50)
    delivery_tax_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    takeout_tax_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    is_tax_inclusive: Optional[bool] = None


class VenueTaxConfigResponse(BaseSchema):
    id: UUID
    venue_id: UUID
    tax_rate: Decimal
    tax_name: str
    delivery_tax_rate: Optional[Decimal] = None
    takeout_tax_rate: Optional[Decimal] = None
    is_tax_inclusive: bool
    created_at: datetime
    updated_at: datetime


# ─── Recipe Cost ─────────────────────────────────────────────────────────────

class RecipeCostResponse(BaseSchema):
    recipe_id: UUID
    recipe_name: str
    total_ingredient_cost: Decimal
    yield_servings: int
    cost_per_serving: Decimal
    ingredients: List[Dict[str, Any]] = []


# ─── Pagination ──────────────────────────────────────────────────────────────

class PaginatedResponse(BaseSchema):
    items: List[Any] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
