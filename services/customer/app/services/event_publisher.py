"""
=============================================================================
FILE: services/event_publisher.py
PURPOSE: Publish customer events to notification service
=============================================================================

Handles publishing of customer-related events for real-time notifications,
analytics tracking, and inter-service communication.
"""

import httpx
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from enum import Enum

import structlog

from app.config import settings

logger = structlog.get_logger()


class EventType(str, Enum):
    """Customer event types."""
    # Customer lifecycle
    CUSTOMER_CREATED = "customer.created"
    CUSTOMER_UPDATED = "customer.updated"
    CUSTOMER_DELETED = "customer.deleted"
    CUSTOMER_GDPR_DELETED = "customer.gdpr_deleted"

    # Visit events
    VISIT_CHECKED_IN = "visit.checked_in"
    VISIT_CHECKED_OUT = "visit.checked_out"
    VISIT_UPDATED = "visit.updated"

    # Segmentation events
    SEGMENT_CHANGED = "segment.changed"
    SEGMENT_UPGRADED = "segment.upgraded"
    SEGMENT_DOWNGRADED = "segment.downgraded"

    # Risk events
    CHURN_RISK_HIGH = "churn.risk_high"
    CHURN_RISK_CRITICAL = "churn.risk_critical"

    # Family events
    FAMILY_CREATED = "family.created"
    FAMILY_MEMBER_ADDED = "family.member_added"
    FAMILY_MEMBER_REMOVED = "family.member_removed"

    # Milestone events
    MILESTONE_VISIT_COUNT = "milestone.visit_count"
    MILESTONE_SPEND_AMOUNT = "milestone.spend_amount"
    MILESTONE_ANNIVERSARY = "milestone.anniversary"


class EventPublisher:
    """
    Publish events to notification service and other subscribers.

    Supports both synchronous HTTP calls and async Redis pub/sub.
    """

    def __init__(self):
        self.notification_url = f"{settings.NOTIFICATION_SERVICE_URL}/api/v1/events"
        self.enabled = settings.ENABLE_EVENT_PUBLISHING
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def publish(
        self,
        event_type: EventType,
        payload: Dict[str, Any],
        venue_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None,
    ) -> bool:
        """
        Publish an event to the notification service.

        Args:
            event_type: Type of event
            payload: Event data
            venue_id: Associated venue ID
            customer_id: Associated customer ID

        Returns:
            True if published successfully
        """
        if not self.enabled:
            logger.debug("event_publishing_disabled", event_type=event_type.value)
            return False

        event = {
            "event_type": event_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "customer-service",
            "payload": payload,
        }

        if venue_id:
            event["venue_id"] = str(venue_id)
        if customer_id:
            event["customer_id"] = str(customer_id)

        try:
            client = await self._get_client()
            response = await client.post(
                self.notification_url,
                json=event,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code in (200, 201, 202):
                logger.info(
                    "event_published",
                    event_type=event_type.value,
                    customer_id=str(customer_id) if customer_id else None,
                )
                return True
            else:
                logger.warning(
                    "event_publish_failed",
                    event_type=event_type.value,
                    status_code=response.status_code,
                )
                return False

        except httpx.RequestError as e:
            logger.error(
                "event_publish_error",
                event_type=event_type.value,
                error=str(e),
            )
            return False

    # ==========================================================================
    # Customer Events
    # ==========================================================================

    async def publish_customer_created(
        self,
        customer_id: UUID,
        venue_id: UUID,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        acquisition_source: Optional[str] = None,
    ) -> bool:
        """Publish customer created event."""
        return await self.publish(
            event_type=EventType.CUSTOMER_CREATED,
            venue_id=venue_id,
            customer_id=customer_id,
            payload={
                "customer_id": str(customer_id),
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "acquisition_source": acquisition_source,
            },
        )

    async def publish_customer_updated(
        self,
        customer_id: UUID,
        venue_id: UUID,
        updated_fields: list,
    ) -> bool:
        """Publish customer updated event."""
        return await self.publish(
            event_type=EventType.CUSTOMER_UPDATED,
            venue_id=venue_id,
            customer_id=customer_id,
            payload={
                "customer_id": str(customer_id),
                "updated_fields": updated_fields,
            },
        )

    async def publish_customer_deleted(
        self,
        customer_id: UUID,
        venue_id: UUID,
        gdpr_delete: bool = False,
    ) -> bool:
        """Publish customer deleted event."""
        event_type = EventType.CUSTOMER_GDPR_DELETED if gdpr_delete else EventType.CUSTOMER_DELETED
        return await self.publish(
            event_type=event_type,
            venue_id=venue_id,
            customer_id=customer_id,
            payload={
                "customer_id": str(customer_id),
                "gdpr_delete": gdpr_delete,
            },
        )

    # ==========================================================================
    # Visit Events
    # ==========================================================================

    async def publish_visit_checked_in(
        self,
        visit_id: UUID,
        customer_id: UUID,
        venue_id: UUID,
        source: str,
        guest_count: int,
    ) -> bool:
        """Publish visit check-in event."""
        return await self.publish(
            event_type=EventType.VISIT_CHECKED_IN,
            venue_id=venue_id,
            customer_id=customer_id,
            payload={
                "visit_id": str(visit_id),
                "customer_id": str(customer_id),
                "source": source,
                "guest_count": guest_count,
            },
        )

    async def publish_visit_checked_out(
        self,
        visit_id: UUID,
        customer_id: UUID,
        venue_id: UUID,
        total_spend: float,
        duration_minutes: Optional[int] = None,
        satisfaction_rating: Optional[int] = None,
    ) -> bool:
        """Publish visit checkout event."""
        return await self.publish(
            event_type=EventType.VISIT_CHECKED_OUT,
            venue_id=venue_id,
            customer_id=customer_id,
            payload={
                "visit_id": str(visit_id),
                "customer_id": str(customer_id),
                "total_spend": total_spend,
                "duration_minutes": duration_minutes,
                "satisfaction_rating": satisfaction_rating,
            },
        )

    # ==========================================================================
    # Segment Events
    # ==========================================================================

    async def publish_segment_changed(
        self,
        customer_id: UUID,
        venue_id: UUID,
        old_segment: Optional[str],
        new_segment: str,
        score: float,
    ) -> bool:
        """Publish segment change event."""
        # Determine if upgrade or downgrade
        segment_order = ["churned", "inactive", "at_risk", "new", "standard", "premium", "vip"]

        event_type = EventType.SEGMENT_CHANGED
        if old_segment and new_segment:
            old_idx = segment_order.index(old_segment) if old_segment in segment_order else 0
            new_idx = segment_order.index(new_segment) if new_segment in segment_order else 0
            if new_idx > old_idx:
                event_type = EventType.SEGMENT_UPGRADED
            elif new_idx < old_idx:
                event_type = EventType.SEGMENT_DOWNGRADED

        return await self.publish(
            event_type=event_type,
            venue_id=venue_id,
            customer_id=customer_id,
            payload={
                "customer_id": str(customer_id),
                "old_segment": old_segment,
                "new_segment": new_segment,
                "score": score,
            },
        )

    # ==========================================================================
    # Risk Events
    # ==========================================================================

    async def publish_churn_risk_alert(
        self,
        customer_id: UUID,
        venue_id: UUID,
        risk_level: str,
        risk_score: float,
        days_since_last_visit: int,
    ) -> bool:
        """Publish churn risk alert event."""
        event_type = (
            EventType.CHURN_RISK_CRITICAL
            if risk_level == "critical"
            else EventType.CHURN_RISK_HIGH
        )

        return await self.publish(
            event_type=event_type,
            venue_id=venue_id,
            customer_id=customer_id,
            payload={
                "customer_id": str(customer_id),
                "risk_level": risk_level,
                "risk_score": risk_score,
                "days_since_last_visit": days_since_last_visit,
            },
        )

    # ==========================================================================
    # Family Events
    # ==========================================================================

    async def publish_family_created(
        self,
        family_id: UUID,
        venue_id: UUID,
        family_name: str,
        primary_customer_id: UUID,
    ) -> bool:
        """Publish family created event."""
        return await self.publish(
            event_type=EventType.FAMILY_CREATED,
            venue_id=venue_id,
            customer_id=primary_customer_id,
            payload={
                "family_id": str(family_id),
                "family_name": family_name,
                "primary_customer_id": str(primary_customer_id),
            },
        )

    async def publish_family_member_added(
        self,
        family_id: UUID,
        venue_id: UUID,
        customer_id: UUID,
        relation_type: str,
    ) -> bool:
        """Publish family member added event."""
        return await self.publish(
            event_type=EventType.FAMILY_MEMBER_ADDED,
            venue_id=venue_id,
            customer_id=customer_id,
            payload={
                "family_id": str(family_id),
                "customer_id": str(customer_id),
                "relation_type": relation_type,
            },
        )

    # ==========================================================================
    # Milestone Events
    # ==========================================================================

    async def publish_milestone_reached(
        self,
        customer_id: UUID,
        venue_id: UUID,
        milestone_type: str,
        milestone_value: Any,
        milestone_label: str,
    ) -> bool:
        """Publish customer milestone event."""
        if milestone_type == "visit_count":
            event_type = EventType.MILESTONE_VISIT_COUNT
        elif milestone_type == "spend_amount":
            event_type = EventType.MILESTONE_SPEND_AMOUNT
        else:
            event_type = EventType.MILESTONE_ANNIVERSARY

        return await self.publish(
            event_type=event_type,
            venue_id=venue_id,
            customer_id=customer_id,
            payload={
                "customer_id": str(customer_id),
                "milestone_type": milestone_type,
                "milestone_value": milestone_value,
                "milestone_label": milestone_label,
            },
        )


# Global event publisher instance
event_publisher = EventPublisher()
