"""Notification schemas for request/response validation."""
from datetime import datetime, time
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class Channel(str, Enum):
    """Notification delivery channels."""
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"
    IN_APP = "IN_APP"


class Priority(str, Enum):
    """Notification priority levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class NotificationStatus(str, Enum):
    """Notification queue status."""
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NotificationType(str, Enum):
    """Types of notifications in FEC SaaS."""
    # Reservation notifications
    RESERVATION_CONFIRMED = "RESERVATION_CONFIRMED"
    RESERVATION_REMINDER = "RESERVATION_REMINDER"
    RESERVATION_CANCELLED = "RESERVATION_CANCELLED"
    RESERVATION_MODIFIED = "RESERVATION_MODIFIED"

    # Party notifications
    PARTY_REMINDER = "PARTY_REMINDER"
    PARTY_CHECKIN = "PARTY_CHECKIN"
    PARTY_COMPLETE = "PARTY_COMPLETE"

    # Waiver notifications
    WAIVER_REQUIRED = "WAIVER_REQUIRED"
    WAIVER_SIGNED = "WAIVER_SIGNED"
    WAIVER_EXPIRING = "WAIVER_EXPIRING"

    # Account notifications
    WELCOME = "WELCOME"
    PASSWORD_RESET = "PASSWORD_RESET"
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"

    # Marketing notifications
    PROMOTION = "PROMOTION"
    BIRTHDAY = "BIRTHDAY"
    LOYALTY_REWARD = "LOYALTY_REWARD"

    # Staff notifications
    SHIFT_REMINDER = "SHIFT_REMINDER"
    TASK_ASSIGNED = "TASK_ASSIGNED"
    ALERT = "ALERT"

    # Custom
    CUSTOM = "CUSTOM"


class RecipientType(str, Enum):
    """Types of notification recipients."""
    CUSTOMER = "CUSTOMER"
    STAFF = "STAFF"
    ADMIN = "ADMIN"


class Frequency(str, Enum):
    """Notification frequency preferences."""
    IMMEDIATE = "IMMEDIATE"
    DIGEST_DAILY = "DIGEST_DAILY"
    DIGEST_WEEKLY = "DIGEST_WEEKLY"


# =============================================================================
# Request Schemas
# =============================================================================


class EmailContent(BaseModel):
    """Email-specific content."""
    subject: str
    body_html: str
    body_text: Optional[str] = None


class SmsContent(BaseModel):
    """SMS-specific content."""
    message: str = Field(..., max_length=160)


class PushContent(BaseModel):
    """Push notification content."""
    title: str
    body: str
    data: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None


class InAppContent(BaseModel):
    """In-app notification content."""
    title: str
    message: str
    action_url: Optional[str] = None
    icon: Optional[str] = None


class NotificationContent(BaseModel):
    """Multi-channel notification content."""
    email: Optional[EmailContent] = None
    sms: Optional[SmsContent] = None
    push: Optional[PushContent] = None
    in_app: Optional[InAppContent] = None


class NotificationCreate(BaseModel):
    """Request to send a notification."""
    venue_id: Optional[UUID] = None
    recipient_id: UUID
    recipient_type: RecipientType = RecipientType.CUSTOMER
    recipient_email: Optional[EmailStr] = None
    recipient_phone: Optional[str] = None
    notification_type: NotificationType
    channels: List[Channel]
    priority: Priority = Priority.MEDIUM
    content: NotificationContent
    template_id: Optional[UUID] = None
    template_vars: Optional[Dict[str, Any]] = None


class ScheduledNotification(NotificationCreate):
    """Request to schedule a notification for later."""
    scheduled_send_time: datetime


class SendBatchRequest(BaseModel):
    """Request to send notifications to multiple recipients."""
    venue_id: Optional[UUID] = None
    notification_type: NotificationType
    channels: List[Channel]
    priority: Priority = Priority.MEDIUM
    content: NotificationContent
    template_id: Optional[UUID] = None
    recipient_ids: List[UUID]
    recipient_type: RecipientType = RecipientType.CUSTOMER


class NotificationPreferencesUpdate(BaseModel):
    """Update notification preferences."""
    notification_type: Optional[NotificationType] = None
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    frequency: Optional[Frequency] = None
    quiet_hours_start: Optional[time] = None
    quiet_hours_end: Optional[time] = None


# =============================================================================
# Response Schemas
# =============================================================================


class NotificationResponse(BaseModel):
    """Notification status response."""
    id: UUID
    venue_id: Optional[UUID]
    recipient_id: UUID
    notification_type: NotificationType
    channel: Channel
    priority: Priority
    status: NotificationStatus
    attempts: int
    max_attempts: int
    scheduled_send_time: Optional[datetime]
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationPreferences(BaseModel):
    """User notification preferences response."""
    id: UUID
    user_id: UUID
    notification_type: NotificationType
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    in_app_enabled: bool
    frequency: Frequency
    quiet_hours_start: Optional[time]
    quiet_hours_end: Optional[time]

    model_config = {"from_attributes": True}


class TrackingResponse(BaseModel):
    """Delivery tracking response."""
    id: UUID
    notification_queue_id: UUID
    channel: Channel
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    opened_at: Optional[datetime]
    clicked_at: Optional[datetime]
    delivery_status: NotificationStatus
    provider_message_id: Optional[str]

    model_config = {"from_attributes": True}


class BatchResponse(BaseModel):
    """Batch notification response."""
    batch_id: UUID
    total_recipients: int
    queued_count: int
    failed_count: int
    status: str


class DeliveryAnalytics(BaseModel):
    """Delivery analytics response."""
    total_sent: int
    total_delivered: int
    total_failed: int
    delivery_rate: float
    average_delivery_time_seconds: float
    by_channel: Dict[str, Dict[str, int]]


class EngagementAnalytics(BaseModel):
    """Engagement analytics response."""
    total_opened: int
    total_clicked: int
    open_rate: float
    click_rate: float
    by_notification_type: Dict[str, Dict[str, int]]
