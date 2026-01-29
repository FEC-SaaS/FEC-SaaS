"""Notification service client for sending reservation reminders."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class NotificationClient:
    """HTTP client for the notification microservice."""

    def __init__(self) -> None:
        self._base_url = settings.NOTIFICATION_SERVICE_URL

    async def send_reservation_confirmation(
        self,
        customer_id: UUID,
        email: Optional[str],
        confirmation_code: str,
        reservation_date: str,
        start_time: str,
        venue_name: str = "FEC Venue",
        party_size: int = 1,
    ) -> Optional[str]:
        """Send reservation confirmation notification. Returns notification_id or None."""
        return await self._send_notification(
            template="reservation_confirmation",
            recipient_id=customer_id,
            email=email,
            channel="EMAIL",
            data={
                "confirmation_code": confirmation_code,
                "reservation_date": reservation_date,
                "start_time": start_time,
                "venue_name": venue_name,
                "party_size": party_size,
            },
        )

    async def send_reservation_reminder(
        self,
        customer_id: UUID,
        email: Optional[str],
        confirmation_code: str,
        reservation_date: str,
        start_time: str,
        reminder_type: str = "24_HOUR",
        channel: str = "EMAIL",
        venue_name: str = "FEC Venue",
    ) -> Optional[str]:
        """Send reservation reminder. Returns notification_id or None."""
        return await self._send_notification(
            template=f"reservation_reminder_{reminder_type.lower()}",
            recipient_id=customer_id,
            email=email,
            channel=channel,
            data={
                "confirmation_code": confirmation_code,
                "reservation_date": reservation_date,
                "start_time": start_time,
                "venue_name": venue_name,
                "reminder_type": reminder_type,
            },
        )

    async def send_cancellation_notice(
        self,
        customer_id: UUID,
        email: Optional[str],
        confirmation_code: str,
        reservation_date: str,
        refund_amount: Optional[str] = None,
    ) -> Optional[str]:
        """Send cancellation notification."""
        data = {
            "confirmation_code": confirmation_code,
            "reservation_date": reservation_date,
        }
        if refund_amount:
            data["refund_amount"] = refund_amount
        return await self._send_notification(
            template="reservation_cancellation",
            recipient_id=customer_id,
            email=email,
            channel="EMAIL",
            data=data,
        )

    async def send_waitlist_notification(
        self,
        customer_id: UUID,
        email: Optional[str],
        desired_date: str,
        desired_time: str,
        venue_name: str = "FEC Venue",
    ) -> Optional[str]:
        """Notify waitlisted customer that a slot is available."""
        return await self._send_notification(
            template="waitlist_slot_available",
            recipient_id=customer_id,
            email=email,
            channel="EMAIL",
            data={
                "desired_date": desired_date,
                "desired_time": desired_time,
                "venue_name": venue_name,
            },
        )

    async def send_no_show_notice(
        self,
        customer_id: UUID,
        email: Optional[str],
        confirmation_code: str,
        reservation_date: str,
        deposit_forfeited: bool = False,
        deposit_amount: Optional[str] = None,
    ) -> Optional[str]:
        """Send no-show notification to customer."""
        data = {
            "confirmation_code": confirmation_code,
            "reservation_date": reservation_date,
            "deposit_forfeited": deposit_forfeited,
        }
        if deposit_amount:
            data["deposit_amount"] = deposit_amount
        return await self._send_notification(
            template="reservation_no_show",
            recipient_id=customer_id,
            email=email,
            channel="EMAIL",
            data=data,
        )

    async def _send_notification(
        self,
        template: str,
        recipient_id: UUID,
        email: Optional[str],
        channel: str,
        data: dict,
    ) -> Optional[str]:
        """Send notification via the notification service. Returns notification_id or None on failure."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                payload = {
                    "template": template,
                    "recipient_id": str(recipient_id),
                    "channel": channel,
                    "data": data,
                }
                if email:
                    payload["email"] = email

                response = await client.post(
                    f"{self._base_url}/api/v1/notifications",
                    json=payload,
                )
                if response.status_code in (200, 201):
                    result = response.json()
                    notification_id = result.get("id") or result.get("notification_id")
                    logger.info(
                        "notification_sent",
                        template=template,
                        recipient_id=str(recipient_id),
                        notification_id=notification_id,
                    )
                    return str(notification_id) if notification_id else None
                else:
                    logger.warning(
                        "notification_send_failed",
                        template=template,
                        recipient_id=str(recipient_id),
                        status=response.status_code,
                        body=response.text[:200],
                    )
                    return None
        except httpx.RequestError as e:
            logger.warning(
                "notification_service_unavailable",
                template=template,
                recipient_id=str(recipient_id),
                error=str(e),
            )
            return None
