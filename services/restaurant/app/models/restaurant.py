"""Restaurant service database models."""

import enum
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


# ─── Enums ───────────────────────────────────────────────────────────────────

class SectionType(str, enum.Enum):
    DINING_ROOM = "DINING_ROOM"
    BAR = "BAR"
    PATIO = "PATIO"
    PRIVATE = "PRIVATE"


class TableType(str, enum.Enum):
    STANDARD = "STANDARD"
    BOOTH = "BOOTH"
    HIGH_TOP = "HIGH_TOP"
    BAR = "BAR"


class TableStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    RESERVED = "RESERVED"
    CLEANING = "CLEANING"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"


class ReservationStatus(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    SEATED = "SEATED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class CategoryType(str, enum.Enum):
    APPETIZERS = "APPETIZERS"
    ENTREES = "ENTREES"
    DESSERTS = "DESSERTS"
    DRINKS = "DRINKS"
    KIDS = "KIDS"


class MealTime(str, enum.Enum):
    BREAKFAST = "BREAKFAST"
    LUNCH = "LUNCH"
    DINNER = "DINNER"
    ALL_DAY = "ALL_DAY"


class ModifierType(str, enum.Enum):
    EXTRA = "EXTRA"
    SUBSTITUTION = "SUBSTITUTION"
    SIZE = "SIZE"
    COOKING_STYLE = "COOKING_STYLE"


class OrderType(str, enum.Enum):
    DINE_IN = "DINE_IN"
    TAKEOUT = "TAKEOUT"
    DELIVERY = "DELIVERY"
    CURBSIDE = "CURBSIDE"


class OrderSource(str, enum.Enum):
    POS = "POS"
    KIOSK = "KIOSK"
    MOBILE = "MOBILE"
    QR_CODE = "QR_CODE"
    ONLINE = "ONLINE"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    READY = "READY"
    SERVED = "SERVED"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class OrderItemStatus(str, enum.Enum):
    PENDING = "PENDING"
    FIRED = "FIRED"
    PREPARING = "PREPARING"
    READY = "READY"
    SERVED = "SERVED"
    CANCELLED = "CANCELLED"


class StationType(str, enum.Enum):
    GRILL = "GRILL"
    FRY = "FRY"
    SALAD = "SALAD"
    DESSERT = "DESSERT"
    BAR = "BAR"
    EXPO = "EXPO"


class KDSItemStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BUMPED = "BUMPED"


class BarProductType(str, enum.Enum):
    BEER = "BEER"
    WINE = "WINE"
    LIQUOR = "LIQUOR"
    MIXER = "MIXER"
    NON_ALCOHOLIC = "NON_ALCOHOLIC"


class WasteReason(str, enum.Enum):
    EXPIRED = "EXPIRED"
    OVERPRODUCTION = "OVERPRODUCTION"
    QUALITY = "QUALITY"
    CUSTOMER_RETURN = "CUSTOMER_RETURN"


class MenuBoardLayout(str, enum.Enum):
    GRID = "GRID"
    LIST = "LIST"
    FEATURED = "FEATURED"


# ─── Models ──────────────────────────────────────────────────────────────────

class RestaurantSection(Base, UUIDMixin):
    __tablename__ = "restaurant_sections"

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    section_name: Mapped[str] = mapped_column(String(100), nullable=False)
    section_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    tables: Mapped[List["DiningTable"]] = relationship("DiningTable", back_populates="section", lazy="selectin")


class DiningTable(Base, UUIDMixin):
    __tablename__ = "dining_tables"
    __table_args__ = (
        UniqueConstraint("venue_id", "table_number", name="uq_venue_table_number"),
    )

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    section_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("restaurant_sections.id"), nullable=True)
    table_number: Mapped[str] = mapped_column(String(20), nullable=False)
    seating_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    table_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=TableStatus.AVAILABLE.value, server_default="AVAILABLE")
    qr_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    section: Mapped[Optional["RestaurantSection"]] = relationship("RestaurantSection", back_populates="tables", lazy="selectin")
    reservations: Mapped[List["TableReservation"]] = relationship("TableReservation", back_populates="table", lazy="noload")


class TableReservation(Base, UUIDMixin):
    __tablename__ = "table_reservations"

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    table_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("dining_tables.id"), nullable=True)
    reservation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reservation_time: Mapped[time] = mapped_column(Time, nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    special_requests: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=ReservationStatus.CONFIRMED.value, server_default="CONFIRMED")
    seated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    table: Mapped[Optional["DiningTable"]] = relationship("DiningTable", back_populates="reservations", lazy="selectin")


class MenuCategory(Base, UUIDMixin):
    __tablename__ = "menu_categories"

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    display_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    available_times: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    items: Mapped[List["MenuItem"]] = relationship("MenuItem", back_populates="category", lazy="selectin")


class MenuItem(Base, UUIDMixin):
    __tablename__ = "menu_items"

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("menu_categories.id"), nullable=True)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    cost_of_goods: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    prep_time_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    calories: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    protein_grams: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 1), nullable=True)
    allergens: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    dietary_tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    spice_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    popularity_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    category: Mapped[Optional["MenuCategory"]] = relationship("MenuCategory", back_populates="items", lazy="selectin")
    modifiers: Mapped[List["MenuItemModifier"]] = relationship("MenuItemModifier", back_populates="item", lazy="selectin")
    recipe: Mapped[Optional["Recipe"]] = relationship("Recipe", back_populates="menu_item", uselist=False, lazy="noload")


class MenuModifier(Base, UUIDMixin):
    __tablename__ = "menu_modifiers"

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    modifier_name: Mapped[str] = mapped_column(String(100), nullable=False)
    modifier_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    price_adjustment: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    item_associations: Mapped[List["MenuItemModifier"]] = relationship("MenuItemModifier", back_populates="modifier", lazy="noload")


class MenuItemModifier(Base):
    __tablename__ = "menu_item_modifiers"

    item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="CASCADE"), primary_key=True)
    modifier_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("menu_modifiers.id", ondelete="CASCADE"), primary_key=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Relationships
    item: Mapped["MenuItem"] = relationship("MenuItem", back_populates="modifiers", lazy="selectin")
    modifier: Mapped["MenuModifier"] = relationship("MenuModifier", back_populates="item_associations", lazy="selectin")


class RestaurantOrder(Base, UUIDMixin):
    __tablename__ = "restaurant_orders"

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    order_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    order_source: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    table_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("dining_tables.id"), nullable=True)
    party_booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    server_staff_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tax: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    tip: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    delivery_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=OrderStatus.PENDING.value, server_default="PENDING", index=True)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ready_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    special_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    items: Mapped[List["RestaurantOrderItem"]] = relationship("RestaurantOrderItem", back_populates="order", lazy="selectin", cascade="all, delete-orphan")
    table: Mapped[Optional["DiningTable"]] = relationship("DiningTable", lazy="selectin")


class RestaurantOrderItem(Base, UUIDMixin):
    __tablename__ = "restaurant_order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("restaurant_orders.id", ondelete="CASCADE"), nullable=False)
    menu_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("menu_items.id"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    modifiers: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    special_requests: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=OrderItemStatus.PENDING.value, server_default="PENDING")
    fired_to_kitchen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ready_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    served_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    order: Mapped["RestaurantOrder"] = relationship("RestaurantOrder", back_populates="items", lazy="selectin")
    menu_item: Mapped[Optional["MenuItem"]] = relationship("MenuItem", lazy="selectin")
    kds_entry: Mapped[Optional["KDSQueueItem"]] = relationship("KDSQueueItem", back_populates="order_item", uselist=False, lazy="noload")


class KitchenStation(Base, UUIDMixin):
    __tablename__ = "kitchen_stations"

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    station_name: Mapped[str] = mapped_column(String(100), nullable=False)
    station_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    printer_ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    queue_items: Mapped[List["KDSQueueItem"]] = relationship("KDSQueueItem", back_populates="station", lazy="noload")


class KDSQueueItem(Base, UUIDMixin):
    __tablename__ = "kds_queue"

    order_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("restaurant_order_items.id"), nullable=True)
    station_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("kitchen_stations.id"), nullable=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    estimated_prep_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=KDSItemStatus.QUEUED.value, server_default="QUEUED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    order_item: Mapped[Optional["RestaurantOrderItem"]] = relationship("RestaurantOrderItem", back_populates="kds_entry", lazy="selectin")
    station: Mapped[Optional["KitchenStation"]] = relationship("KitchenStation", back_populates="queue_items", lazy="selectin")


class BarInventory(Base, UUIDMixin):
    __tablename__ = "bar_inventory"

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size_ml: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    abv_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2), nullable=True)
    quantity_in_stock: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    par_level: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    cost_per_unit: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    price_per_unit: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    supplier: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_restocked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BarPour(Base, UUIDMixin):
    __tablename__ = "bar_pours"

    order_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("restaurant_order_items.id"), nullable=True)
    bar_inventory_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bar_inventory.id"), nullable=True)
    quantity_poured_ml: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    bartender_staff_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    poured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    inventory_item: Mapped[Optional["BarInventory"]] = relationship("BarInventory", lazy="selectin")


class Recipe(Base, UUIDMixin):
    __tablename__ = "recipes"

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    menu_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("menu_items.id"), nullable=True)
    recipe_name: Mapped[str] = mapped_column(String(255), nullable=False)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prep_time_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cook_time_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    yield_servings: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    menu_item: Mapped[Optional["MenuItem"]] = relationship("MenuItem", back_populates="recipe", lazy="selectin")
    ingredients: Mapped[List["RecipeIngredient"]] = relationship("RecipeIngredient", back_populates="recipe", lazy="selectin", cascade="all, delete-orphan")


class RecipeIngredient(Base, UUIDMixin):
    __tablename__ = "recipe_ingredients"

    recipe_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    inventory_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    recipe: Mapped["Recipe"] = relationship("Recipe", back_populates="ingredients", lazy="selectin")


class FoodWasteLog(Base, UUIDMixin):
    __tablename__ = "food_waste_log"

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    waste_date: Mapped[date] = mapped_column(Date, nullable=False)
    menu_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("menu_items.id"), nullable=True)
    inventory_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    quantity_wasted: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    waste_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    logged_by: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    menu_item: Mapped[Optional["MenuItem"]] = relationship("MenuItem", lazy="selectin")


class HappyHourSchedule(Base, UUIDMixin):
    __tablename__ = "happy_hour_schedules"

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    schedule_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    day_of_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    end_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    discount_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    affected_categories: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class VenueTaxConfig(Base, UUIDMixin):
    __tablename__ = "venue_tax_configs"
    __table_args__ = (
        UniqueConstraint("venue_id", name="uq_venue_tax_config"),
    )

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0.0800"))
    tax_name: Mapped[str] = mapped_column(String(50), default="Sales Tax", server_default="Sales Tax")
    delivery_tax_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    takeout_tax_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    is_tax_inclusive: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class DigitalMenuBoard(Base, UUIDMixin):
    __tablename__ = "digital_menu_boards"

    venue_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    board_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    board_location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    display_categories: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    layout_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
