"""
=============================================================================
FILE: core/events.py
PURPOSE: Event publishing for cross-service communication
=============================================================================

Provides event publishing capabilities for:
- Venue lifecycle events (created, updated, deleted)
- Feature toggle events
- Onboarding events
- Performance milestone events

Events are published to Redis pub/sub and can be consumed by other services.
"""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

import redis.asyncio as redis
import structlog

from app.config import get_settings

logger = structlog.get_logger()


class EventType(str, Enum):
    """Event types for venue service."""
    # Venue lifecycle
    VENUE_CREATED = "venue.created"
    VENUE_UPDATED = "venue.updated"
    VENUE_DELETED = "venue.deleted"
    VENUE_STATUS_CHANGED = "venue.status_changed"

    # Onboarding
    ONBOARDING_STARTED = "venue.onboarding.started"
    ONBOARDING_STEP_COMPLETED = "venue.onboarding.step_completed"
    ONBOARDING_COMPLETED = "venue.onboarding.completed"

    # Features
    FEATURE_ENABLED = "venue.feature.enabled"
    FEATURE_DISABLED = "venue.feature.disabled"

    # AI Config
    AI_SERVICE_ENABLED = "venue.ai.enabled"
    AI_SERVICE_DISABLED = "venue.ai.disabled"
    AI_CONFIG_UPDATED = "venue.ai.config_updated"

    # Performance
    PERFORMANCE_RECORDED = "venue.performance.recorded"
    PERFORMANCE_MILESTONE = "venue.performance.milestone"

    # Settings
    SETTINGS_UPDATED = "venue.settings.updated"


class Event:
    """Event object for publishing."""

    def __init__(
        self,
        event_type: EventType,
        venue_id: UUID,
        data: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
    ):
        self.event_type = event_type
        self.venue_id = venue_id
        self.data = data or {}
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
        self.service = "venue-service"

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_type": self.event_type.value,
            "venue_id": str(self.venue_id),
            "data": self.data,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "service": self.service,
        }

    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class EventPublisher:
    """Publisher for venue service events."""

    CHANNEL_PREFIX = "fec:events"

    def __init__(self, redis_url: str = None):
        settings = get_settings()
        self.redis_url = redis_url or settings.redis_url
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Initialize Redis connection."""
        if self._client is None and self.redis_url:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("event_publisher_connected", url=self.redis_url)

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("event_publisher_disconnected")

    def _get_channel(self, event_type: EventType) -> str:
        """Get Redis channel for event type."""
        # Use event type hierarchy for channel (e.g., fec:events:venue:created)
        event_parts = event_type.value.split(".")
        return f"{self.CHANNEL_PREFIX}:{':'.join(event_parts)}"

    async def publish(self, event: Event) -> bool:
        """Publish an event to Redis."""
        if not self._client:
            logger.warning("event_publish_skipped", reason="no_redis_connection")
            return False

        try:
            channel = self._get_channel(event.event_type)
            message = event.to_json()

            # Publish to specific channel
            await self._client.publish(channel, message)

            # Also publish to general venue channel for subscribers wanting all events
            general_channel = f"{self.CHANNEL_PREFIX}:venue"
            await self._client.publish(general_channel, message)

            logger.info(
                "event_published",
                event_type=event.event_type.value,
                venue_id=str(event.venue_id),
                channel=channel,
            )
            return True

        except Exception as e:
            logger.error(
                "event_publish_error",
                event_type=event.event_type.value,
                venue_id=str(event.venue_id),
                error=str(e),
            )
            return False

    # -------------------------------------------------------------------------
    # Convenience methods for common events
    # -------------------------------------------------------------------------

    async def venue_created(self, venue_id: UUID, venue_data: Dict[str, Any]) -> bool:
        """Publish venue created event."""
        event = Event(
            event_type=EventType.VENUE_CREATED,
            venue_id=venue_id,
            data={
                "name": venue_data.get("name"),
                "subscription_tier": venue_data.get("subscription_tier"),
                "franchise_id": venue_data.get("franchise_id"),
            },
        )
        return await self.publish(event)

    async def venue_updated(self, venue_id: UUID, changes: Dict[str, Any]) -> bool:
        """Publish venue updated event."""
        event = Event(
            event_type=EventType.VENUE_UPDATED,
            venue_id=venue_id,
            data={"changes": changes},
        )
        return await self.publish(event)

    async def venue_deleted(self, venue_id: UUID, hard_delete: bool = False) -> bool:
        """Publish venue deleted event."""
        event = Event(
            event_type=EventType.VENUE_DELETED,
            venue_id=venue_id,
            data={"hard_delete": hard_delete},
        )
        return await self.publish(event)

    async def venue_status_changed(
        self,
        venue_id: UUID,
        old_status: str,
        new_status: str,
    ) -> bool:
        """Publish venue status changed event."""
        event = Event(
            event_type=EventType.VENUE_STATUS_CHANGED,
            venue_id=venue_id,
            data={
                "old_status": old_status,
                "new_status": new_status,
            },
        )
        return await self.publish(event)

    async def onboarding_started(self, venue_id: UUID) -> bool:
        """Publish onboarding started event."""
        event = Event(
            event_type=EventType.ONBOARDING_STARTED,
            venue_id=venue_id,
        )
        return await self.publish(event)

    async def onboarding_completed(self, venue_id: UUID, go_live_date: str = None) -> bool:
        """Publish onboarding completed event."""
        event = Event(
            event_type=EventType.ONBOARDING_COMPLETED,
            venue_id=venue_id,
            data={"go_live_date": go_live_date},
        )
        return await self.publish(event)

    async def feature_toggled(
        self,
        venue_id: UUID,
        feature_name: str,
        enabled: bool,
    ) -> bool:
        """Publish feature toggled event."""
        event_type = EventType.FEATURE_ENABLED if enabled else EventType.FEATURE_DISABLED
        event = Event(
            event_type=event_type,
            venue_id=venue_id,
            data={"feature_name": feature_name},
        )
        return await self.publish(event)

    async def ai_service_toggled(
        self,
        venue_id: UUID,
        service_name: str,
        enabled: bool,
        config: Dict[str, Any] = None,
    ) -> bool:
        """Publish AI service toggled event."""
        event_type = EventType.AI_SERVICE_ENABLED if enabled else EventType.AI_SERVICE_DISABLED
        event = Event(
            event_type=event_type,
            venue_id=venue_id,
            data={
                "service_name": service_name,
                "config": config,
            },
        )
        return await self.publish(event)

    async def performance_milestone(
        self,
        venue_id: UUID,
        milestone: str,
        value: float,
    ) -> bool:
        """Publish performance milestone event."""
        event = Event(
            event_type=EventType.PERFORMANCE_MILESTONE,
            venue_id=venue_id,
            data={
                "milestone": milestone,
                "value": value,
            },
        )
        return await self.publish(event)


# Global event publisher instance
event_publisher = EventPublisher()
