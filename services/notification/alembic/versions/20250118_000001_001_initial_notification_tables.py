"""Initial notification service tables.

Revision ID: 001
Revises:
Create Date: 2025-01-18

Creates the core notification tables:
- notification_templates: Reusable notification templates
- notification_queue: Queue of notifications to be sent
- notification_batches: Batch notification tracking
- user_notification_preferences: Per-user notification settings
- notification_delivery_tracking: Detailed delivery tracking
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON, ARRAY

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create notification_templates table
    op.create_table(
        "notification_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("venue_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("template_name", sa.String(255), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False, index=True),
        sa.Column("channels", ARRAY(sa.String), nullable=False),
        sa.Column("priority", sa.String(20), server_default="MEDIUM"),
        sa.Column("content", JSON, nullable=False),
        sa.Column("variables", ARRAY(sa.String), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # Create notification_batches table (before notification_queue due to FK)
    op.create_table(
        "notification_batches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("venue_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("batch_name", sa.String(255), nullable=True),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("recipient_count", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(20), server_default="PENDING"),
        sa.Column("scheduled_time", sa.TIMESTAMP, nullable=True),
        sa.Column("started_at", sa.TIMESTAMP, nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP, nullable=True),
        sa.Column("success_count", sa.Integer, server_default="0"),
        sa.Column("failure_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # Create notification_queue table
    op.create_table(
        "notification_queue",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("venue_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("batch_id", UUID(as_uuid=True), sa.ForeignKey("notification_batches.id"), nullable=True),
        sa.Column("recipient_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("recipient_type", sa.String(20), server_default="CUSTOMER"),
        sa.Column("recipient_email", sa.String(255), nullable=True),
        sa.Column("recipient_phone", sa.String(20), nullable=True),
        sa.Column("notification_type", sa.String(50), nullable=False, index=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("priority", sa.String(20), server_default="MEDIUM", index=True),
        sa.Column("content", JSON, nullable=False),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("notification_templates.id"), nullable=True),
        sa.Column("scheduled_send_time", sa.TIMESTAMP, nullable=True, index=True),
        sa.Column("status", sa.String(20), server_default="QUEUED", index=True),
        sa.Column("attempts", sa.Integer, server_default="0"),
        sa.Column("max_attempts", sa.Integer, server_default="3"),
        sa.Column("sent_at", sa.TIMESTAMP, nullable=True),
        sa.Column("delivered_at", sa.TIMESTAMP, nullable=True),
        sa.Column("read_at", sa.TIMESTAMP, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # Create user_notification_preferences table
    op.create_table(
        "user_notification_preferences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("email_enabled", sa.Boolean, server_default="true"),
        sa.Column("sms_enabled", sa.Boolean, server_default="true"),
        sa.Column("push_enabled", sa.Boolean, server_default="true"),
        sa.Column("in_app_enabled", sa.Boolean, server_default="true"),
        sa.Column("frequency", sa.String(20), server_default="IMMEDIATE"),
        sa.Column("quiet_hours_start", sa.Time, nullable=True),
        sa.Column("quiet_hours_end", sa.Time, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", "notification_type", name="uq_user_notification_type"),
    )

    # Create notification_delivery_tracking table
    op.create_table(
        "notification_delivery_tracking",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("notification_queue_id", UUID(as_uuid=True), sa.ForeignKey("notification_queue.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("sent_at", sa.TIMESTAMP, nullable=True),
        sa.Column("delivered_at", sa.TIMESTAMP, nullable=True),
        sa.Column("opened_at", sa.TIMESTAMP, nullable=True),
        sa.Column("clicked_at", sa.TIMESTAMP, nullable=True),
        sa.Column("bounced_at", sa.TIMESTAMP, nullable=True),
        sa.Column("delivery_status", sa.String(20), nullable=True),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("provider_response", JSON, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # Create indexes for common queries
    op.create_index("ix_notification_queue_status_priority", "notification_queue", ["status", "priority"])
    op.create_index("ix_notification_queue_recipient_channel", "notification_queue", ["recipient_id", "channel"])
    op.create_index("ix_notification_templates_venue_type", "notification_templates", ["venue_id", "notification_type"])


def downgrade() -> None:
    op.drop_index("ix_notification_templates_venue_type", table_name="notification_templates")
    op.drop_index("ix_notification_queue_recipient_channel", table_name="notification_queue")
    op.drop_index("ix_notification_queue_status_priority", table_name="notification_queue")

    op.drop_table("notification_delivery_tracking")
    op.drop_table("user_notification_preferences")
    op.drop_table("notification_queue")
    op.drop_table("notification_batches")
    op.drop_table("notification_templates")
