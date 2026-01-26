"""Initial venue schema

Revision ID: 001
Revises:
Create Date: 2025-01-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    venue_status_enum = postgresql.ENUM(
        "PENDING", "ACTIVE", "INACTIVE", "SUSPENDED", "CLOSED",
        name="venuestatus",
        create_type=False,
    )
    venue_status_enum.create(op.get_bind(), checkfirst=True)

    subscription_tier_enum = postgresql.ENUM(
        "STARTER", "PRO", "ENTERPRISE",
        name="subscriptiontier",
        create_type=False,
    )
    subscription_tier_enum.create(op.get_bind(), checkfirst=True)

    onboarding_status_enum = postgresql.ENUM(
        "NOT_STARTED", "IN_PROGRESS", "COMPLETED", "EXPIRED",
        name="onboardingstatus",
        create_type=False,
    )
    onboarding_status_enum.create(op.get_bind(), checkfirst=True)

    setting_type_enum = postgresql.ENUM(
        "STRING", "INTEGER", "FLOAT", "BOOLEAN", "JSON", "SECRET",
        name="settingtype",
        create_type=False,
    )
    setting_type_enum.create(op.get_bind(), checkfirst=True)

    ai_strategy_enum = postgresql.ENUM(
        "CONSERVATIVE", "MODERATE", "AGGRESSIVE", "CUSTOM",
        name="aistrategy",
        create_type=False,
    )
    ai_strategy_enum.create(op.get_bind(), checkfirst=True)

    contact_type_enum = postgresql.ENUM(
        "OWNER", "MANAGER", "TECHNICAL", "BILLING", "EMERGENCY", "OTHER",
        name="contacttype",
        create_type=False,
    )
    contact_type_enum.create(op.get_bind(), checkfirst=True)

    image_type_enum = postgresql.ENUM(
        "LOGO", "HERO", "GALLERY", "MENU", "FLOOR_PLAN", "OTHER",
        name="imagetype",
        create_type=False,
    )
    image_type_enum.create(op.get_bind(), checkfirst=True)

    # Create venues table
    op.create_table(
        "venues",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", postgresql.ENUM("PENDING", "ACTIVE", "INACTIVE", "SUSPENDED", "CLOSED", name="venuestatus", create_type=False), nullable=False),
        sa.Column("subscription_tier", postgresql.ENUM("STARTER", "PRO", "ENTERPRISE", name="subscriptiontier", create_type=False), nullable=False),
        sa.Column("onboarding_status", postgresql.ENUM("NOT_STARTED", "IN_PROGRESS", "COMPLETED", "EXPIRED", name="onboardingstatus", create_type=False), nullable=False),
        sa.Column("onboarding_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("onboarding_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("go_live_date", sa.Date(), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=False),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("postal_code", sa.String(length=20), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("timezone", sa.String(length=50), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("tax_id", sa.String(length=50), nullable=True),
        sa.Column("total_capacity", sa.Integer(), nullable=True),
        sa.Column("square_footage", sa.Integer(), nullable=True),
        sa.Column("franchise_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_flagship", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("extra_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_venues_slug", "venues", ["slug"], unique=True)
    op.create_index("ix_venues_status", "venues", ["status"])
    op.create_index("ix_venues_subscription_tier", "venues", ["subscription_tier"])
    op.create_index("ix_venues_franchise_id", "venues", ["franchise_id"])
    op.create_index("ix_venues_city_state", "venues", ["city", "state"])
    op.create_index("ix_venues_created_at", "venues", ["created_at"])

    # Create venue_hours table
    op.create_table(
        "venue_hours",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("open_time", sa.Time(), nullable=True),
        sa.Column("close_time", sa.Time(), nullable=True),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_24_hours", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_venue_hours_venue_day", "venue_hours", ["venue_id", "day_of_week"], unique=True)

    # Create venue_special_hours table
    op.create_table(
        "venue_special_hours",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("open_time", sa.Time(), nullable=True),
        sa.Column("close_time", sa.Time(), nullable=True),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_24_hours", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_venue_special_hours_venue_date", "venue_special_hours", ["venue_id", "date"], unique=True)

    # Create venue_settings table
    op.create_table(
        "venue_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("setting_key", sa.String(length=100), nullable=False),
        sa.Column("setting_value", sa.Text(), nullable=False),
        sa.Column("setting_type", postgresql.ENUM("STRING", "INTEGER", "FLOAT", "BOOLEAN", "JSON", "SECRET", name="settingtype", create_type=False), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_venue_settings_venue_key", "venue_settings", ["venue_id", "setting_key"], unique=True)
    op.create_index("ix_venue_settings_category", "venue_settings", ["venue_id", "category"])

    # Create venue_features table
    op.create_table(
        "venue_features",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feature_name", sa.String(length=50), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_venue_features_venue_feature", "venue_features", ["venue_id", "feature_name"], unique=True)
    op.create_index("ix_venue_features_enabled", "venue_features", ["venue_id", "is_enabled"])

    # Create venue_ai_configs table
    op.create_table(
        "venue_ai_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ai_service", sa.String(length=50), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("strategy", postgresql.ENUM("CONSERVATIVE", "MODERATE", "AGGRESSIVE", "CUSTOM", name="aistrategy", create_type=False), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_venue_ai_configs_venue_service", "venue_ai_configs", ["venue_id", "ai_service"], unique=True)
    op.create_index("ix_venue_ai_configs_enabled", "venue_ai_configs", ["venue_id", "is_enabled"])

    # Create venue_performance table
    op.create_table(
        "venue_performance",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("revenue", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("revenue_per_guest", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("transaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_transaction", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("guest_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_customers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("returning_customers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("party_bookings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("labor_hours", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("labor_cost", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("labor_cost_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("food_cost", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("food_cost_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("food_waste_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("nps_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_rating", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("peak_occupancy", sa.Integer(), nullable=True),
        sa.Column("average_occupancy", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("capacity_utilization", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_venue_performance_venue_date", "venue_performance", ["venue_id", "date"], unique=True)
    op.create_index("ix_venue_performance_date", "venue_performance", ["date"])

    # Create venue_contacts table
    op.create_table(
        "venue_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_type", postgresql.ENUM("OWNER", "MANAGER", "TECHNICAL", "BILLING", "EMERGENCY", "OTHER", name="contacttype", create_type=False), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_venue_contacts_venue_type", "venue_contacts", ["venue_id", "contact_type"])
    op.create_index("ix_venue_contacts_primary", "venue_contacts", ["venue_id", "is_primary"])

    # Create venue_images table
    op.create_table(
        "venue_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("image_type", postgresql.ENUM("LOGO", "HERO", "GALLERY", "MENU", "FLOOR_PLAN", "OTHER", name="imagetype", create_type=False), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("alt_text", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_venue_images_venue_type", "venue_images", ["venue_id", "image_type"])
    op.create_index("ix_venue_images_sort", "venue_images", ["venue_id", "sort_order"])


def downgrade() -> None:
    # Drop tables
    op.drop_table("venue_images")
    op.drop_table("venue_contacts")
    op.drop_table("venue_performance")
    op.drop_table("venue_ai_configs")
    op.drop_table("venue_features")
    op.drop_table("venue_settings")
    op.drop_table("venue_special_hours")
    op.drop_table("venue_hours")
    op.drop_table("venues")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS imagetype")
    op.execute("DROP TYPE IF EXISTS contacttype")
    op.execute("DROP TYPE IF EXISTS aistrategy")
    op.execute("DROP TYPE IF EXISTS settingtype")
    op.execute("DROP TYPE IF EXISTS onboardingstatus")
    op.execute("DROP TYPE IF EXISTS subscriptiontier")
    op.execute("DROP TYPE IF EXISTS venuestatus")
