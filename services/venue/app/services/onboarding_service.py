"""
=============================================================================
FILE: services/onboarding_service.py
PURPOSE: Venue onboarding workflow management
=============================================================================

Manages the streamlined onboarding process for new venues,
targeting <4 hours to go live.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.venue import Venue, VenueStatus, OnboardingStatus
from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


# Onboarding steps in order
ONBOARDING_STEPS = [
    "basic_info",       # Step 1: Name, legal entity, address
    "equipment",        # Step 2: Equipment configuration
    "operating_hours",  # Step 3: Set operating hours
    "features",         # Step 4: Select features to enable
    "ai_config",        # Step 5: Configure AI services
    "integrations",     # Step 6: Connect POS, payments, etc.
    "launch_prep",      # Step 7: Training, checklists
]


class OnboardingService:
    """Service for venue onboarding workflow."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_onboarding(self, venue_id: UUID) -> Dict[str, Any]:
        """
        Start the onboarding process for a venue.

        Args:
            venue_id: Venue UUID

        Returns:
            Onboarding status
        """
        venue = await self._get_venue(venue_id)
        if not venue:
            raise ValueError("Venue not found")

        if venue.onboarding_status == OnboardingStatus.COMPLETED:
            raise ValueError("Venue onboarding already completed")

        # Update venue status
        venue.onboarding_status = OnboardingStatus.IN_PROGRESS
        venue.onboarding_started_at = datetime.utcnow()

        # Initialize onboarding metadata
        venue.metadata = venue.metadata or {}
        venue.metadata["onboarding"] = {
            "started_at": datetime.utcnow().isoformat(),
            "steps_completed": [],
            "current_step": ONBOARDING_STEPS[0],
        }

        await self.db.flush()
        await self.db.refresh(venue)

        logger.info(
            "onboarding_started",
            venue_id=str(venue_id),
        )

        return await self.get_status(venue_id)

    async def complete_step(
        self,
        venue_id: UUID,
        step_name: str,
        step_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Mark an onboarding step as complete.

        Args:
            venue_id: Venue UUID
            step_name: Name of the completed step
            step_data: Optional data from the step

        Returns:
            Updated onboarding status
        """
        venue = await self._get_venue(venue_id)
        if not venue:
            raise ValueError("Venue not found")

        if venue.onboarding_status != OnboardingStatus.IN_PROGRESS:
            raise ValueError("Onboarding not in progress")

        if step_name not in ONBOARDING_STEPS:
            raise ValueError(f"Invalid step: {step_name}")

        # Get onboarding metadata
        onboarding = venue.metadata.get("onboarding", {})
        steps_completed = onboarding.get("steps_completed", [])

        # Mark step as complete
        if step_name not in steps_completed:
            steps_completed.append(step_name)

        # Store step data if provided
        if step_data:
            onboarding[f"step_{step_name}_data"] = step_data
            onboarding[f"step_{step_name}_completed_at"] = datetime.utcnow().isoformat()

        # Determine next step
        current_index = ONBOARDING_STEPS.index(step_name)
        if current_index < len(ONBOARDING_STEPS) - 1:
            onboarding["current_step"] = ONBOARDING_STEPS[current_index + 1]
        else:
            onboarding["current_step"] = None

        onboarding["steps_completed"] = steps_completed

        # Update venue metadata
        venue.metadata["onboarding"] = onboarding

        await self.db.flush()
        await self.db.refresh(venue)

        logger.info(
            "onboarding_step_completed",
            venue_id=str(venue_id),
            step=step_name,
            steps_remaining=len(ONBOARDING_STEPS) - len(steps_completed),
        )

        return await self.get_status(venue_id)

    async def complete_onboarding(self, venue_id: UUID) -> Dict[str, Any]:
        """
        Complete the onboarding process and mark venue as ready.

        Args:
            venue_id: Venue UUID

        Returns:
            Final onboarding status
        """
        venue = await self._get_venue(venue_id)
        if not venue:
            raise ValueError("Venue not found")

        # Check all steps completed
        onboarding = venue.metadata.get("onboarding", {})
        steps_completed = set(onboarding.get("steps_completed", []))
        required_steps = set(ONBOARDING_STEPS)

        if not required_steps.issubset(steps_completed):
            missing = required_steps - steps_completed
            raise ValueError(f"Incomplete steps: {', '.join(missing)}")

        # Update venue
        venue.onboarding_status = OnboardingStatus.COMPLETED
        venue.onboarding_completed_at = datetime.utcnow()
        venue.status = VenueStatus.ACTIVE

        onboarding["completed_at"] = datetime.utcnow().isoformat()
        venue.metadata["onboarding"] = onboarding

        await self.db.flush()
        await self.db.refresh(venue)

        # Calculate onboarding time
        started = venue.onboarding_started_at
        completed = venue.onboarding_completed_at
        duration = completed - started if started and completed else None

        logger.info(
            "onboarding_completed",
            venue_id=str(venue_id),
            duration_hours=duration.total_seconds() / 3600 if duration else None,
        )

        return await self.get_status(venue_id)

    async def go_live(
        self,
        venue_id: UUID,
        go_live_date: Optional[datetime] = None,
    ) -> Venue:
        """
        Mark venue as live and ready for business.

        Args:
            venue_id: Venue UUID
            go_live_date: Optional scheduled go-live date

        Returns:
            Updated venue
        """
        venue = await self._get_venue(venue_id)
        if not venue:
            raise ValueError("Venue not found")

        if venue.onboarding_status != OnboardingStatus.COMPLETED:
            raise ValueError("Onboarding not completed")

        venue.status = VenueStatus.ACTIVE
        venue.go_live_date = (go_live_date or datetime.utcnow()).date()

        await self.db.flush()
        await self.db.refresh(venue)

        logger.info(
            "venue_go_live",
            venue_id=str(venue_id),
            go_live_date=str(venue.go_live_date),
        )

        return venue

    async def get_status(self, venue_id: UUID) -> Dict[str, Any]:
        """
        Get current onboarding status.

        Args:
            venue_id: Venue UUID

        Returns:
            Onboarding status details
        """
        venue = await self._get_venue(venue_id)
        if not venue:
            raise ValueError("Venue not found")

        onboarding = venue.metadata.get("onboarding", {})
        steps_completed = onboarding.get("steps_completed", [])
        steps_remaining = [s for s in ONBOARDING_STEPS if s not in steps_completed]

        # Calculate expiration
        expires_at = None
        if venue.onboarding_started_at and venue.onboarding_status == OnboardingStatus.IN_PROGRESS:
            expires_at = venue.onboarding_started_at + timedelta(
                hours=settings.ONBOARDING_TIMEOUT_HOURS
            )

        progress = len(steps_completed) / len(ONBOARDING_STEPS) * 100 if ONBOARDING_STEPS else 0

        return {
            "venue_id": venue_id,
            "status": venue.onboarding_status,
            "started_at": venue.onboarding_started_at,
            "completed_at": venue.onboarding_completed_at,
            "steps_completed": steps_completed,
            "steps_remaining": steps_remaining,
            "current_step": onboarding.get("current_step"),
            "progress_percentage": round(progress, 1),
            "expires_at": expires_at,
            "go_live_date": venue.go_live_date,
        }

    async def expire_stale_onboardings(self) -> int:
        """
        Expire onboardings that have exceeded the timeout.

        Returns:
            Number of expired onboardings
        """
        cutoff = datetime.utcnow() - timedelta(hours=settings.ONBOARDING_TIMEOUT_HOURS)

        result = await self.db.execute(
            select(Venue).where(
                Venue.onboarding_status == OnboardingStatus.IN_PROGRESS,
                Venue.onboarding_started_at < cutoff,
            )
        )
        venues = result.scalars().all()

        for venue in venues:
            venue.onboarding_status = OnboardingStatus.EXPIRED

        await self.db.flush()

        if venues:
            logger.info(
                "onboardings_expired",
                count=len(venues),
            )

        return len(venues)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _get_venue(self, venue_id: UUID) -> Optional[Venue]:
        """Get venue by ID."""
        result = await self.db.execute(
            select(Venue).where(
                Venue.id == venue_id,
                Venue.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()
