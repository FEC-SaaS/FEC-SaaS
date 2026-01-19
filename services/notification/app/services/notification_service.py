"""Core notification service for queue management and delivery."""
import json
import uuid
from datetime import datetime, timezone, time
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.providers.email import email_provider
from app.providers.sms import sms_provider
from app.schemas.notification import (
    Channel,
    NotificationContent,
    NotificationCreate,
    NotificationStatus,
    NotificationType,
    Priority,
    RecipientType,
)

settings = get_settings()
logger = structlog.get_logger()


class NotificationService:
    """
    Core notification service handling:
    - Multi-channel routing
    - Priority queue management
    - Preference checking
    - Quiet hours enforcement
    - Retry logic
    """

    # Redis key prefixes
    QUEUE_KEY = "notification:queue"
    PREFERENCES_KEY = "notification:preferences"
    TRACKING_KEY = "notification:tracking"
    RATE_LIMIT_KEY = "notification:rate_limit"

    @classmethod
    def _get_priority_score(cls, priority: Priority) -> int:
        """Get numeric score for priority (higher = more urgent)."""
        scores = {
            Priority.LOW: 1,
            Priority.MEDIUM: 5,
            Priority.HIGH: 10,
            Priority.URGENT: 100,
        }
        return scores.get(priority, 5)

    @classmethod
    def _is_in_quiet_hours(
        cls,
        quiet_start: Optional[time],
        quiet_end: Optional[time],
    ) -> bool:
        """Check if current time is within quiet hours."""
        if not quiet_start or not quiet_end:
            return False

        now = datetime.now(timezone.utc).time()

        # Handle overnight quiet hours (e.g., 22:00 to 08:00)
        if quiet_start > quiet_end:
            return now >= quiet_start or now <= quiet_end
        else:
            return quiet_start <= now <= quiet_end

    @classmethod
    async def check_user_preferences(
        cls,
        user_id: UUID,
        notification_type: NotificationType,
        channel: Channel,
    ) -> Dict[str, Any]:
        """
        Check user preferences for a notification.

        Returns:
            Dict with enabled, in_quiet_hours, frequency
        """
        redis_client = get_redis_client()

        if not redis_client:
            # Default to allowing if Redis unavailable
            return {"enabled": True, "in_quiet_hours": False, "frequency": "IMMEDIATE"}

        pref_key = f"{cls.PREFERENCES_KEY}:{user_id}:{notification_type.value}"
        prefs_json = redis_client.get(pref_key)

        if not prefs_json:
            # Default preferences
            return {"enabled": True, "in_quiet_hours": False, "frequency": "IMMEDIATE"}

        prefs = json.loads(prefs_json)

        # Check if channel is enabled
        channel_key = f"{channel.value.lower()}_enabled"
        enabled = prefs.get(channel_key, True)

        # Check quiet hours
        quiet_start = prefs.get("quiet_hours_start")
        quiet_end = prefs.get("quiet_hours_end")

        if quiet_start and quiet_end:
            quiet_start = time.fromisoformat(quiet_start)
            quiet_end = time.fromisoformat(quiet_end)

        in_quiet_hours = cls._is_in_quiet_hours(quiet_start, quiet_end)

        return {
            "enabled": enabled,
            "in_quiet_hours": in_quiet_hours,
            "frequency": prefs.get("frequency", "IMMEDIATE"),
        }

    @classmethod
    async def queue_notification(
        cls,
        notification: NotificationCreate,
        recipient_email: Optional[str] = None,
        recipient_phone: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Queue a notification for delivery.

        Args:
            notification: Notification creation request
            recipient_email: Email address for EMAIL channel
            recipient_phone: Phone number for SMS channel

        Returns:
            List of queued notification records
        """
        redis_client = get_redis_client()
        queued_notifications = []

        for channel in notification.channels:
            # Check user preferences
            prefs = await cls.check_user_preferences(
                notification.recipient_id,
                notification.notification_type,
                channel,
            )

            if not prefs["enabled"]:
                logger.info(
                    "notification_skipped_preferences",
                    user_id=str(notification.recipient_id),
                    channel=channel.value,
                    notification_type=notification.notification_type.value,
                )
                continue

            # Create queue entry
            notification_id = str(uuid.uuid4())
            queue_entry = {
                "id": notification_id,
                "venue_id": str(notification.venue_id) if notification.venue_id else None,
                "recipient_id": str(notification.recipient_id),
                "recipient_type": notification.recipient_type.value,
                "recipient_email": recipient_email or notification.recipient_email,
                "recipient_phone": recipient_phone or notification.recipient_phone,
                "notification_type": notification.notification_type.value,
                "channel": channel.value,
                "priority": notification.priority.value,
                "content": notification.content.model_dump(),
                "template_id": str(notification.template_id) if notification.template_id else None,
                "template_vars": notification.template_vars,
                "status": NotificationStatus.QUEUED.value,
                "attempts": 0,
                "max_attempts": settings.MAX_RETRY_ATTEMPTS,
                "scheduled_send_time": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "in_quiet_hours": prefs["in_quiet_hours"],
            }

            # For URGENT priority, skip quiet hours
            if notification.priority == Priority.URGENT:
                queue_entry["in_quiet_hours"] = False

            if redis_client:
                # Add to sorted set with priority score
                score = cls._get_priority_score(notification.priority)
                redis_client.zadd(
                    cls.QUEUE_KEY,
                    {json.dumps(queue_entry): score},
                )

            queued_notifications.append(queue_entry)

            logger.info(
                "notification_queued",
                notification_id=notification_id,
                channel=channel.value,
                priority=notification.priority.value,
                recipient_id=str(notification.recipient_id),
            )

        return queued_notifications

    @classmethod
    async def process_queue(cls, batch_size: int = 100) -> Dict[str, int]:
        """
        Process queued notifications.

        Returns:
            Dict with sent_count, failed_count, skipped_count
        """
        redis_client = get_redis_client()

        if not redis_client:
            logger.warning("redis_not_available_for_queue_processing")
            return {"sent_count": 0, "failed_count": 0, "skipped_count": 0}

        stats = {"sent_count": 0, "failed_count": 0, "skipped_count": 0}

        # Get highest priority notifications
        entries = redis_client.zrevrange(cls.QUEUE_KEY, 0, batch_size - 1)

        for entry_json in entries:
            entry = json.loads(entry_json)

            # Skip if in quiet hours (unless URGENT)
            if entry.get("in_quiet_hours") and entry["priority"] != Priority.URGENT.value:
                stats["skipped_count"] += 1
                continue

            # Remove from queue
            redis_client.zrem(cls.QUEUE_KEY, entry_json)

            # Update status to SENDING
            entry["status"] = NotificationStatus.SENDING.value
            entry["attempts"] += 1

            # Send based on channel
            result = await cls._send_notification(entry)

            if result["success"]:
                entry["status"] = NotificationStatus.SENT.value
                entry["sent_at"] = datetime.now(timezone.utc).isoformat()
                entry["provider_message_id"] = result.get("message_id")
                stats["sent_count"] += 1

                # Store tracking info
                tracking_key = f"{cls.TRACKING_KEY}:{entry['id']}"
                redis_client.setex(
                    tracking_key,
                    86400 * 7,  # 7 days TTL
                    json.dumps(entry),
                )
            else:
                entry["status"] = NotificationStatus.FAILED.value
                entry["error_message"] = result.get("error")

                # Retry if under max attempts
                if entry["attempts"] < entry["max_attempts"]:
                    entry["status"] = NotificationStatus.QUEUED.value
                    score = cls._get_priority_score(Priority(entry["priority"])) - entry["attempts"]
                    redis_client.zadd(cls.QUEUE_KEY, {json.dumps(entry): score})
                else:
                    stats["failed_count"] += 1

        return stats

    @classmethod
    async def _send_notification(cls, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Send a single notification based on channel."""
        channel = Channel(entry["channel"])
        content = entry["content"]

        if channel == Channel.EMAIL:
            email_content = content.get("email", {})
            if not email_content or not entry.get("recipient_email"):
                return {"success": False, "error": "Missing email content or recipient"}

            return await email_provider.send_email(
                to_email=entry["recipient_email"],
                subject=email_content.get("subject", "Notification"),
                body_html=email_content.get("body_html", ""),
                body_text=email_content.get("body_text"),
                tracking_id=entry["id"],
            )

        elif channel == Channel.SMS:
            sms_content = content.get("sms", {})
            if not sms_content or not entry.get("recipient_phone"):
                return {"success": False, "error": "Missing SMS content or recipient phone"}

            return await sms_provider.send_sms(
                to_phone=entry["recipient_phone"],
                message=sms_content.get("message", ""),
                tracking_id=entry["id"],
            )

        elif channel == Channel.PUSH:
            # TODO: Implement push notifications via Firebase
            logger.warning("push_notifications_not_implemented", notification_id=entry["id"])
            return {"success": False, "error": "Push notifications not yet implemented"}

        elif channel == Channel.IN_APP:
            # In-app notifications stored for retrieval
            redis_client = get_redis_client()
            if redis_client:
                in_app_key = f"in_app:{entry['recipient_id']}"
                redis_client.lpush(in_app_key, json.dumps(entry))
                redis_client.ltrim(in_app_key, 0, 99)  # Keep last 100
                return {"success": True, "message_id": entry["id"]}
            return {"success": False, "error": "Redis not available for in-app notifications"}

        return {"success": False, "error": f"Unknown channel: {channel}"}

    @classmethod
    async def get_notification_status(cls, notification_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a notification."""
        redis_client = get_redis_client()

        if not redis_client:
            return None

        tracking_key = f"{cls.TRACKING_KEY}:{notification_id}"
        entry_json = redis_client.get(tracking_key)

        if entry_json:
            return json.loads(entry_json)

        return None

    @classmethod
    async def get_in_app_notifications(
        cls,
        user_id: UUID,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get in-app notifications for a user."""
        redis_client = get_redis_client()

        if not redis_client:
            return []

        in_app_key = f"in_app:{user_id}"
        entries = redis_client.lrange(in_app_key, 0, limit - 1)

        return [json.loads(entry) for entry in entries]

    @classmethod
    async def update_preferences(
        cls,
        user_id: UUID,
        notification_type: NotificationType,
        preferences: Dict[str, Any],
    ) -> bool:
        """Update user notification preferences."""
        redis_client = get_redis_client()

        if not redis_client:
            return False

        pref_key = f"{cls.PREFERENCES_KEY}:{user_id}:{notification_type.value}"

        # Get existing preferences
        existing_json = redis_client.get(pref_key)
        if existing_json:
            existing = json.loads(existing_json)
            existing.update(preferences)
        else:
            existing = preferences

        redis_client.set(pref_key, json.dumps(existing))
        return True

    @classmethod
    async def get_preferences(
        cls,
        user_id: UUID,
        notification_type: Optional[NotificationType] = None,
    ) -> List[Dict[str, Any]]:
        """Get user notification preferences."""
        redis_client = get_redis_client()

        if not redis_client:
            return []

        if notification_type:
            pref_key = f"{cls.PREFERENCES_KEY}:{user_id}:{notification_type.value}"
            pref_json = redis_client.get(pref_key)
            if pref_json:
                pref = json.loads(pref_json)
                pref["notification_type"] = notification_type.value
                pref["user_id"] = str(user_id)
                return [pref]
            return []

        # Get all preferences for user
        pattern = f"{cls.PREFERENCES_KEY}:{user_id}:*"
        keys = redis_client.keys(pattern)

        preferences = []
        for key in keys:
            pref_json = redis_client.get(key)
            if pref_json:
                pref = json.loads(pref_json)
                pref["notification_type"] = key.split(":")[-1]
                pref["user_id"] = str(user_id)
                preferences.append(pref)

        return preferences
