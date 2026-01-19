"""Background worker for processing notification queue.

Run with: python -m app.worker
"""
import asyncio
import signal
import sys
from datetime import datetime, timezone

import structlog

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.services.notification_service import NotificationService

settings = get_settings()
logger = structlog.get_logger()

# Graceful shutdown flag
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global shutdown_requested
    logger.info("shutdown_signal_received", signal=signum)
    shutdown_requested = True


async def process_queue_loop():
    """Main worker loop to process notification queue."""
    logger.info("worker_started", batch_size=settings.BATCH_SIZE)

    while not shutdown_requested:
        try:
            # Process a batch of notifications
            stats = await NotificationService.process_queue(batch_size=settings.BATCH_SIZE)

            if stats["sent_count"] > 0 or stats["failed_count"] > 0:
                logger.info(
                    "batch_processed",
                    sent=stats["sent_count"],
                    failed=stats["failed_count"],
                    skipped=stats["skipped_count"],
                )

            # Sleep between batches (shorter if queue is active)
            if stats["sent_count"] == 0 and stats["failed_count"] == 0:
                await asyncio.sleep(5)  # Longer sleep when idle
            else:
                await asyncio.sleep(0.5)  # Short sleep when processing

        except Exception as e:
            logger.error("worker_error", error=str(e))
            await asyncio.sleep(10)  # Back off on errors

    logger.info("worker_stopped")


async def process_scheduled_notifications():
    """Check and activate scheduled notifications."""
    redis_client = get_redis_client()
    if not redis_client:
        return

    while not shutdown_requested:
        try:
            # This would check for scheduled notifications that are due
            # and move them to the active queue
            # Implementation depends on how scheduled notifications are stored
            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            logger.error("scheduled_processor_error", error=str(e))
            await asyncio.sleep(60)


async def main():
    """Main entry point for worker."""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Check Redis connection
    redis_client = get_redis_client()
    if not redis_client:
        logger.error("redis_not_available", message="Worker requires Redis to be configured")
        sys.exit(1)

    logger.info(
        "notification_worker_starting",
        redis_url=settings.REDIS_URL.split("@")[-1] if "@" in settings.REDIS_URL else settings.REDIS_URL,
    )

    # Run worker tasks
    await asyncio.gather(
        process_queue_loop(),
        process_scheduled_notifications(),
    )


if __name__ == "__main__":
    asyncio.run(main())
