"""Database models for notification service.

Based on the notification-service.sh specification.
"""
import uuid
from datetime import datetime, time

from sqlalchemy import (
    ARRAY,
    BOOLEAN,
    INTEGER,
    TIMESTAMP,
    Column,
    ForeignKey,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class NotificationTemplate(Base):
    """Notification templates for venues."""
    __tablename__ = "notification_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    template_name = Column(String(255), nullable=False)
    notification_type = Column(String(50), nullable=False, index=True)
    channels = Column(ARRAY(String), nullable=False)  # EMAIL, SMS, PUSH, IN_APP
    priority = Column(String(20), default="MEDIUM")
    content = Column(JSON, nullable=False)  # {email: {subject, body}, sms: {message}, push: {title, body}}
    variables = Column(ARRAY(String), nullable=True)  # List of variable names used in template
    is_active = Column(BOOLEAN, default=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationQueue(Base):
    """Queue of notifications to be sent."""
    __tablename__ = "notification_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("notification_batches.id"), nullable=True)
    recipient_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    recipient_type = Column(String(20), default="CUSTOMER")  # CUSTOMER, STAFF, ADMIN
    recipient_email = Column(String(255), nullable=True)
    recipient_phone = Column(String(20), nullable=True)
    notification_type = Column(String(50), nullable=False, index=True)
    channel = Column(String(20), nullable=False)  # EMAIL, SMS, PUSH, IN_APP
    priority = Column(String(20), default="MEDIUM", index=True)
    content = Column(JSON, nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("notification_templates.id"), nullable=True)
    scheduled_send_time = Column(TIMESTAMP, nullable=True, index=True)
    status = Column(String(20), default="QUEUED", index=True)  # QUEUED, SENDING, SENT, DELIVERED, FAILED, CANCELLED
    attempts = Column(INTEGER, default=0)
    max_attempts = Column(INTEGER, default=3)
    sent_at = Column(TIMESTAMP, nullable=True)
    delivered_at = Column(TIMESTAMP, nullable=True)
    read_at = Column(TIMESTAMP, nullable=True)
    error_message = Column(Text, nullable=True)
    provider_message_id = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    template = relationship("NotificationTemplate")
    batch = relationship("NotificationBatch", back_populates="notifications")
    tracking = relationship("NotificationDeliveryTracking", back_populates="notification", uselist=False)


class UserNotificationPreference(Base):
    """User preferences for notifications."""
    __tablename__ = "user_notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", "notification_type", name="uq_user_notification_type"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    notification_type = Column(String(50), nullable=False)
    email_enabled = Column(BOOLEAN, default=True)
    sms_enabled = Column(BOOLEAN, default=True)
    push_enabled = Column(BOOLEAN, default=True)
    in_app_enabled = Column(BOOLEAN, default=True)
    frequency = Column(String(20), default="IMMEDIATE")  # IMMEDIATE, DIGEST_DAILY, DIGEST_WEEKLY
    quiet_hours_start = Column(Time, nullable=True)
    quiet_hours_end = Column(Time, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationBatch(Base):
    """Batch notifications for bulk sending."""
    __tablename__ = "notification_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    batch_name = Column(String(255), nullable=True)
    notification_type = Column(String(50), nullable=False)
    recipient_count = Column(INTEGER, default=0)
    status = Column(String(20), default="PENDING")  # PENDING, PROCESSING, COMPLETED, FAILED
    scheduled_time = Column(TIMESTAMP, nullable=True)
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    success_count = Column(INTEGER, default=0)
    failure_count = Column(INTEGER, default=0)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    notifications = relationship("NotificationQueue", back_populates="batch")


class NotificationDeliveryTracking(Base):
    """Detailed tracking for notification delivery."""
    __tablename__ = "notification_delivery_tracking"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_queue_id = Column(UUID(as_uuid=True), ForeignKey("notification_queue.id", ondelete="CASCADE"), nullable=False, unique=True)
    channel = Column(String(20), nullable=False)
    sent_at = Column(TIMESTAMP, nullable=True)
    delivered_at = Column(TIMESTAMP, nullable=True)
    opened_at = Column(TIMESTAMP, nullable=True)
    clicked_at = Column(TIMESTAMP, nullable=True)
    bounced_at = Column(TIMESTAMP, nullable=True)
    delivery_status = Column(String(20), nullable=True)  # SENT, DELIVERED, OPENED, CLICKED, BOUNCED, FAILED
    provider_message_id = Column(String(255), nullable=True)
    provider_response = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    notification = relationship("NotificationQueue", back_populates="tracking")
