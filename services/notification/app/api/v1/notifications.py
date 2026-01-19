"""Notification API endpoints.

Provides endpoints for:
- Sending notifications (single and batch)
- Scheduling notifications
- Managing user preferences
- Tracking delivery status
- Analytics
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.schemas.notification import (
    BatchResponse,
    Channel,
    DeliveryAnalytics,
    EngagementAnalytics,
    NotificationCreate,
    NotificationPreferences,
    NotificationPreferencesUpdate,
    NotificationResponse,
    NotificationStatus,
    NotificationType,
    Priority,
    ScheduledNotification,
    SendBatchRequest,
    TrackingResponse,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


# =============================================================================
# Send Endpoints
# =============================================================================


class SendResponse(BaseModel):
    """Response for send notification."""
    success: bool
    notifications: List[dict]
    message: str


@router.post("/send", response_model=SendResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_notification(payload: NotificationCreate):
    """
    Send a notification through specified channels.

    The notification will be queued for delivery based on priority.
    URGENT priority notifications are delivered immediately.
    """
    queued = await NotificationService.queue_notification(
        notification=payload,
        recipient_email=payload.recipient_email,
        recipient_phone=payload.recipient_phone,
    )

    if not queued:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to queue notification. Check recipient preferences.",
        )

    return SendResponse(
        success=True,
        notifications=queued,
        message=f"Queued {len(queued)} notification(s) for delivery",
    )


@router.post("/send-batch", response_model=BatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_batch_notification(payload: SendBatchRequest):
    """
    Send notifications to multiple recipients.

    All recipients will receive the same notification content.
    Individual preferences are respected for each recipient.
    """
    import uuid

    batch_id = uuid.uuid4()
    queued_count = 0
    failed_count = 0

    for recipient_id in payload.recipient_ids:
        notification = NotificationCreate(
            venue_id=payload.venue_id,
            recipient_id=recipient_id,
            recipient_type=payload.recipient_type,
            notification_type=payload.notification_type,
            channels=payload.channels,
            priority=payload.priority,
            content=payload.content,
            template_id=payload.template_id,
        )

        queued = await NotificationService.queue_notification(notification)
        if queued:
            queued_count += len(queued)
        else:
            failed_count += 1

    return BatchResponse(
        batch_id=batch_id,
        total_recipients=len(payload.recipient_ids),
        queued_count=queued_count,
        failed_count=failed_count,
        status="QUEUED",
    )


@router.post("/schedule", response_model=SendResponse, status_code=status.HTTP_202_ACCEPTED)
async def schedule_notification(payload: ScheduledNotification):
    """
    Schedule a notification for future delivery.

    The notification will be held in queue until the scheduled time.
    """
    if payload.scheduled_send_time <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scheduled time must be in the future",
        )

    queued = await NotificationService.queue_notification(
        notification=payload,
        recipient_email=payload.recipient_email,
        recipient_phone=payload.recipient_phone,
    )

    # Update with scheduled time
    for q in queued:
        q["scheduled_send_time"] = payload.scheduled_send_time.isoformat()

    return SendResponse(
        success=True,
        notifications=queued,
        message=f"Scheduled {len(queued)} notification(s) for {payload.scheduled_send_time}",
    )


# =============================================================================
# Preference Endpoints
# =============================================================================


@router.get("/preferences", response_model=List[dict])
async def get_preferences(
    user_id: UUID = Query(..., description="User ID to get preferences for"),
    notification_type: Optional[NotificationType] = Query(
        None, description="Filter by notification type"
    ),
):
    """
    Get notification preferences for a user.

    Returns all preferences if no notification_type is specified.
    """
    preferences = await NotificationService.get_preferences(
        user_id=user_id,
        notification_type=notification_type,
    )

    # Return default preferences if none found
    if not preferences and notification_type:
        return [{
            "user_id": str(user_id),
            "notification_type": notification_type.value,
            "email_enabled": True,
            "sms_enabled": True,
            "push_enabled": True,
            "in_app_enabled": True,
            "frequency": "IMMEDIATE",
            "quiet_hours_start": None,
            "quiet_hours_end": None,
        }]

    return preferences


@router.put("/preferences", status_code=status.HTTP_200_OK)
async def update_preferences(
    user_id: UUID = Query(..., description="User ID to update preferences for"),
    notification_type: NotificationType = Query(..., description="Notification type"),
    payload: NotificationPreferencesUpdate = None,
):
    """
    Update notification preferences for a user.

    Only provided fields will be updated.
    """
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No preferences provided",
        )

    prefs_dict = payload.model_dump(exclude_unset=True, exclude_none=True)

    # Convert time objects to string
    if "quiet_hours_start" in prefs_dict and prefs_dict["quiet_hours_start"]:
        prefs_dict["quiet_hours_start"] = prefs_dict["quiet_hours_start"].isoformat()
    if "quiet_hours_end" in prefs_dict and prefs_dict["quiet_hours_end"]:
        prefs_dict["quiet_hours_end"] = prefs_dict["quiet_hours_end"].isoformat()

    success = await NotificationService.update_preferences(
        user_id=user_id,
        notification_type=notification_type,
        preferences=prefs_dict,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences",
        )

    return {"success": True, "message": "Preferences updated"}


# =============================================================================
# Status & Tracking Endpoints
# =============================================================================


@router.get("/{notification_id}/status")
async def get_notification_status(notification_id: str):
    """
    Get the current status of a notification.

    Returns queued, sending, sent, delivered, or failed status.
    """
    status_info = await NotificationService.get_notification_status(notification_id)

    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return status_info


@router.get("/{notification_id}/tracking")
async def get_tracking_info(notification_id: str):
    """
    Get detailed delivery tracking for a notification.

    Includes sent, delivered, opened, and clicked timestamps.
    """
    tracking = await NotificationService.get_notification_status(notification_id)

    if not tracking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracking information not found",
        )

    return {
        "id": tracking.get("id"),
        "notification_queue_id": tracking.get("id"),
        "channel": tracking.get("channel"),
        "sent_at": tracking.get("sent_at"),
        "delivered_at": tracking.get("delivered_at"),
        "opened_at": tracking.get("opened_at"),
        "clicked_at": tracking.get("clicked_at"),
        "delivery_status": tracking.get("status"),
        "provider_message_id": tracking.get("provider_message_id"),
    }


# =============================================================================
# In-App Notifications
# =============================================================================


@router.get("/in-app")
async def get_in_app_notifications(
    user_id: UUID = Query(..., description="User ID"),
    limit: int = Query(20, ge=1, le=100, description="Number of notifications to return"),
):
    """
    Get in-app notifications for a user.

    Returns the most recent notifications, newest first.
    """
    notifications = await NotificationService.get_in_app_notifications(
        user_id=user_id,
        limit=limit,
    )

    return {
        "user_id": str(user_id),
        "notifications": notifications,
        "count": len(notifications),
    }


# =============================================================================
# Analytics Endpoints
# =============================================================================


@router.get("/analytics/delivery", response_model=DeliveryAnalytics)
async def get_delivery_analytics(
    venue_id: Optional[UUID] = Query(None, description="Filter by venue"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
):
    """
    Get notification delivery analytics.

    Includes delivery rates, average delivery time, and breakdown by channel.
    """
    # TODO: Implement with database queries
    # For now, return mock data structure
    return DeliveryAnalytics(
        total_sent=0,
        total_delivered=0,
        total_failed=0,
        delivery_rate=0.0,
        average_delivery_time_seconds=0.0,
        by_channel={
            "EMAIL": {"sent": 0, "delivered": 0, "failed": 0},
            "SMS": {"sent": 0, "delivered": 0, "failed": 0},
            "PUSH": {"sent": 0, "delivered": 0, "failed": 0},
            "IN_APP": {"sent": 0, "delivered": 0, "failed": 0},
        },
    )


@router.get("/analytics/engagement", response_model=EngagementAnalytics)
async def get_engagement_analytics(
    venue_id: Optional[UUID] = Query(None, description="Filter by venue"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
):
    """
    Get notification engagement analytics.

    Includes open rates, click rates, and breakdown by notification type.
    """
    # TODO: Implement with database queries
    # For now, return mock data structure
    return EngagementAnalytics(
        total_opened=0,
        total_clicked=0,
        open_rate=0.0,
        click_rate=0.0,
        by_notification_type={},
    )


# =============================================================================
# Health Check
# =============================================================================


@router.get("/health")
async def health_check():
    """Check notification service health."""
    from app.core.redis import get_redis_client
    from app.providers.email import email_provider
    from app.providers.sms import sms_provider

    redis_client = get_redis_client()

    return {
        "status": "healthy",
        "redis": "connected" if redis_client else "not_configured",
        "email_provider": "configured" if email_provider.is_configured() else "not_configured",
        "sms_provider": "configured" if sms_provider.is_configured() else "not_configured",
    }
