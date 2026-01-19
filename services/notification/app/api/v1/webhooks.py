"""Webhook endpoints for delivery status callbacks.

Handles callbacks from SendGrid and Twilio for delivery tracking.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.notification import NotificationDeliveryTracking, NotificationQueue

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# =============================================================================
# SendGrid Webhook
# =============================================================================


class SendGridEvent(BaseModel):
    """SendGrid event webhook payload."""
    email: str
    timestamp: int
    event: str  # delivered, bounce, dropped, open, click, etc.
    sg_message_id: Optional[str] = None
    reason: Optional[str] = None
    url: Optional[str] = None  # For click events


@router.post("/sendgrid")
async def sendgrid_webhook(
    events: List[SendGridEvent],
    db: Session = Depends(get_db),
):
    """
    Handle SendGrid delivery status webhooks.

    Events: processed, dropped, delivered, deferred, bounce, open, click, etc.
    """
    processed = 0

    for event in events:
        if not event.sg_message_id:
            continue

        # Find notification by provider message ID
        notification = db.query(NotificationQueue).filter(
            NotificationQueue.provider_message_id == event.sg_message_id
        ).first()

        if not notification:
            continue

        # Update notification status
        event_time = datetime.fromtimestamp(event.timestamp, tz=timezone.utc)

        if event.event == "delivered":
            notification.status = "DELIVERED"
            notification.delivered_at = event_time
        elif event.event in ("bounce", "dropped"):
            notification.status = "FAILED"
            notification.error_message = event.reason
        elif event.event == "open":
            notification.read_at = event_time

        # Update or create tracking record
        tracking = notification.tracking
        if not tracking:
            tracking = NotificationDeliveryTracking(
                notification_queue_id=notification.id,
                channel="EMAIL",
                provider_message_id=event.sg_message_id,
            )
            db.add(tracking)

        tracking.delivery_status = event.event.upper()
        tracking.updated_at = datetime.now(timezone.utc)

        if event.event == "delivered":
            tracking.delivered_at = event_time
        elif event.event == "open":
            tracking.opened_at = event_time
        elif event.event == "click":
            tracking.clicked_at = event_time
        elif event.event == "bounce":
            tracking.bounced_at = event_time

        processed += 1

    db.commit()

    return {"processed": processed, "total": len(events)}


# =============================================================================
# Twilio Webhook
# =============================================================================


@router.post("/twilio/status")
async def twilio_status_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Handle Twilio SMS delivery status callbacks.

    Status values: queued, sent, delivered, undelivered, failed
    """
    form_data = await request.form()

    message_sid = form_data.get("MessageSid")
    message_status = form_data.get("MessageStatus")
    error_code = form_data.get("ErrorCode")
    error_message = form_data.get("ErrorMessage")

    if not message_sid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing MessageSid",
        )

    # Find notification by provider message ID
    notification = db.query(NotificationQueue).filter(
        NotificationQueue.provider_message_id == message_sid
    ).first()

    if not notification:
        return {"status": "notification_not_found"}

    # Map Twilio status to our status
    status_map = {
        "queued": "QUEUED",
        "sent": "SENT",
        "delivered": "DELIVERED",
        "undelivered": "FAILED",
        "failed": "FAILED",
    }

    notification.status = status_map.get(message_status, notification.status)

    if message_status == "delivered":
        notification.delivered_at = datetime.now(timezone.utc)
    elif message_status in ("undelivered", "failed"):
        notification.error_message = f"{error_code}: {error_message}" if error_code else error_message

    # Update tracking
    tracking = notification.tracking
    if not tracking:
        tracking = NotificationDeliveryTracking(
            notification_queue_id=notification.id,
            channel="SMS",
            provider_message_id=message_sid,
        )
        db.add(tracking)

    tracking.delivery_status = message_status.upper()
    tracking.updated_at = datetime.now(timezone.utc)

    if message_status == "delivered":
        tracking.delivered_at = datetime.now(timezone.utc)

    db.commit()

    return {"status": "processed"}


# =============================================================================
# In-App Notification Events
# =============================================================================


class InAppEvent(BaseModel):
    """In-app notification event."""
    notification_id: str
    event: str  # read, clicked, dismissed
    user_id: str


@router.post("/in-app/event")
async def in_app_event(
    payload: InAppEvent,
    db: Session = Depends(get_db),
):
    """
    Track in-app notification events (read, click, dismiss).

    Called by the frontend when user interacts with notifications.
    """
    notification = db.query(NotificationQueue).filter(
        NotificationQueue.id == payload.notification_id,
        NotificationQueue.channel == "IN_APP",
    ).first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    now = datetime.now(timezone.utc)

    if payload.event == "read":
        notification.read_at = now
        notification.status = "DELIVERED"
    elif payload.event == "clicked":
        notification.read_at = notification.read_at or now

    # Update tracking
    tracking = notification.tracking
    if not tracking:
        tracking = NotificationDeliveryTracking(
            notification_queue_id=notification.id,
            channel="IN_APP",
        )
        db.add(tracking)

    if payload.event == "read":
        tracking.opened_at = now
        tracking.delivery_status = "OPENED"
    elif payload.event == "clicked":
        tracking.clicked_at = now
        tracking.delivery_status = "CLICKED"

    tracking.updated_at = now
    db.commit()

    return {"status": "processed"}
