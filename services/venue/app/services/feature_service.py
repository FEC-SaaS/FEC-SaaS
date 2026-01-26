"""
=============================================================================
FILE: services/feature_service.py
PURPOSE: Venue feature flags management
=============================================================================

Manages which features (bowling, arcade, food, etc.) are enabled
for each venue along with feature-specific configuration.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.venue import VenueFeature, Venue, SubscriptionTier
from app.schemas.venue import VenueFeatureCreate, VenueFeatureUpdate

logger = structlog.get_logger()


# Feature availability by subscription tier
TIER_FEATURES = {
    SubscriptionTier.STARTER: {
        "bowling",
        "arcade",
        "pos",
        "reservations",
    },
    SubscriptionTier.PRO: {
        "bowling",
        "arcade",
        "pos",
        "reservations",
        "food_beverage",
        "mini_golf",
        "parties",
        "loyalty",
        "mobile_app",
        "events",
    },
    SubscriptionTier.ENTERPRISE: {
        "bowling",
        "arcade",
        "pos",
        "reservations",
        "food_beverage",
        "mini_golf",
        "parties",
        "loyalty",
        "mobile_app",
        "events",
        "laser_tag",
        "go_karts",
        "bumper_cars",
        "trampoline",
        "escape_room",
        "vr_experience",
        "redemption",
    },
}


class FeatureService:
    """Service for venue feature management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_features(self, venue_id: UUID) -> List[VenueFeature]:
        """Get all features for a venue."""
        result = await self.db.execute(
            select(VenueFeature)
            .where(VenueFeature.venue_id == venue_id)
            .order_by(VenueFeature.feature_name)
        )
        return list(result.scalars().all())

    async def get_enabled_features(self, venue_id: UUID) -> List[str]:
        """Get list of enabled feature names for a venue."""
        result = await self.db.execute(
            select(VenueFeature.feature_name)
            .where(
                VenueFeature.venue_id == venue_id,
                VenueFeature.is_enabled == True,
            )
        )
        return [row[0] for row in result.all()]

    async def get_feature(
        self,
        venue_id: UUID,
        feature_name: str,
    ) -> Optional[VenueFeature]:
        """Get a specific feature by name."""
        result = await self.db.execute(
            select(VenueFeature).where(
                VenueFeature.venue_id == venue_id,
                VenueFeature.feature_name == feature_name,
            )
        )
        return result.scalar_one_or_none()

    async def is_feature_enabled(
        self,
        venue_id: UUID,
        feature_name: str,
    ) -> bool:
        """Check if a feature is enabled for a venue."""
        feature = await self.get_feature(venue_id, feature_name)
        return feature.is_enabled if feature else False

    async def get_feature_config(
        self,
        venue_id: UUID,
        feature_name: str,
    ) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific feature."""
        feature = await self.get_feature(venue_id, feature_name)
        return feature.config if feature else None

    async def set_feature(
        self,
        venue_id: UUID,
        feature_data: VenueFeatureCreate,
    ) -> VenueFeature:
        """
        Create or update a feature.

        Args:
            venue_id: Venue UUID
            feature_data: Feature data

        Returns:
            Created/updated feature
        """
        # Check tier eligibility
        venue = await self._get_venue(venue_id)
        if venue and not self._is_feature_allowed(
            feature_data.feature_name,
            venue.subscription_tier,
        ):
            raise ValueError(
                f"Feature '{feature_data.feature_name}' is not available "
                f"for {venue.subscription_tier.value} tier"
            )

        existing = await self.get_feature(venue_id, feature_data.feature_name)

        if existing:
            # Update existing
            was_enabled = existing.is_enabled
            existing.is_enabled = feature_data.is_enabled
            existing.config = feature_data.config or existing.config
            existing.notes = feature_data.notes

            if feature_data.is_enabled and not was_enabled:
                existing.enabled_at = datetime.utcnow()
                existing.disabled_at = None
            elif not feature_data.is_enabled and was_enabled:
                existing.disabled_at = datetime.utcnow()

            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        # Create new
        feature = VenueFeature(
            venue_id=venue_id,
            feature_name=feature_data.feature_name,
            is_enabled=feature_data.is_enabled,
            config=feature_data.config or {},
            notes=feature_data.notes,
            enabled_at=datetime.utcnow() if feature_data.is_enabled else None,
        )
        self.db.add(feature)
        await self.db.flush()
        await self.db.refresh(feature)

        logger.info(
            "feature_set",
            venue_id=str(venue_id),
            feature=feature_data.feature_name,
            enabled=feature_data.is_enabled,
        )

        return feature

    async def enable_feature(
        self,
        venue_id: UUID,
        feature_name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> VenueFeature:
        """Enable a feature for a venue."""
        feature_data = VenueFeatureCreate(
            feature_name=feature_name,
            is_enabled=True,
            config=config,
        )
        return await self.set_feature(venue_id, feature_data)

    async def disable_feature(
        self,
        venue_id: UUID,
        feature_name: str,
    ) -> Optional[VenueFeature]:
        """Disable a feature for a venue."""
        feature = await self.get_feature(venue_id, feature_name)

        if not feature:
            return None

        feature.is_enabled = False
        feature.disabled_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(feature)

        logger.info(
            "feature_disabled",
            venue_id=str(venue_id),
            feature=feature_name,
        )

        return feature

    async def update_feature_config(
        self,
        venue_id: UUID,
        feature_name: str,
        config: Dict[str, Any],
    ) -> Optional[VenueFeature]:
        """Update configuration for a feature."""
        feature = await self.get_feature(venue_id, feature_name)

        if not feature:
            return None

        # Merge config
        feature.config = {**feature.config, **config} if feature.config else config

        await self.db.flush()
        await self.db.refresh(feature)

        return feature

    async def get_available_features(
        self,
        venue_id: UUID,
    ) -> List[str]:
        """Get list of features available for venue's subscription tier."""
        venue = await self._get_venue(venue_id)
        if not venue:
            return []

        return list(TIER_FEATURES.get(venue.subscription_tier, set()))

    async def bulk_enable_features(
        self,
        venue_id: UUID,
        feature_names: List[str],
    ) -> int:
        """Enable multiple features at once."""
        count = 0
        for feature_name in feature_names:
            try:
                await self.enable_feature(venue_id, feature_name)
                count += 1
            except ValueError:
                # Feature not allowed for tier
                continue

        return count

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _get_venue(self, venue_id: UUID) -> Optional[Venue]:
        """Get venue by ID."""
        result = await self.db.execute(
            select(Venue).where(Venue.id == venue_id)
        )
        return result.scalar_one_or_none()

    def _is_feature_allowed(
        self,
        feature_name: str,
        tier: SubscriptionTier,
    ) -> bool:
        """Check if feature is allowed for subscription tier."""
        allowed = TIER_FEATURES.get(tier, set())
        return feature_name in allowed
