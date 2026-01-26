"""
=============================================================================
FILE: services/ai_config_service.py
PURPOSE: AI service configuration per venue
=============================================================================

Controls which AI services (dynamic pricing, smart staff, etc.) are enabled
for each venue and their optimization strategy.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.venue import VenueAIConfig, Venue, SubscriptionTier, AIStrategy
from app.schemas.venue import VenueAIConfigCreate, VenueAIConfigUpdate

logger = structlog.get_logger()


# AI services available by tier
TIER_AI_SERVICES = {
    SubscriptionTier.STARTER: set(),  # No AI for starter
    SubscriptionTier.PRO: {
        "dynamic_pricing",
    },
    SubscriptionTier.ENTERPRISE: {
        "dynamic_pricing",
        "smart_staff",
        "churn_prediction",
        "party_flow",
        "game_floor",
        "food_waste",
        "sentiment",
        "recommendation",
    },
}

# Default parameters for each AI service
DEFAULT_AI_PARAMS = {
    "dynamic_pricing": {
        "price_floor_percentage": 80,
        "price_ceiling_percentage": 150,
        "demand_threshold_high": 0.8,
        "demand_threshold_low": 0.3,
        "update_interval_minutes": 15,
    },
    "smart_staff": {
        "min_staff_ratio": 0.1,
        "max_overtime_hours": 4,
        "skill_matching_weight": 0.7,
        "availability_weight": 0.3,
    },
    "churn_prediction": {
        "risk_threshold_high": 0.7,
        "risk_threshold_medium": 0.4,
        "lookback_days": 90,
        "trigger_intervention_at": 0.6,
    },
    "party_flow": {
        "buffer_minutes": 15,
        "upsell_threshold_percentage": 20,
        "auto_assign_staff": True,
    },
    "game_floor": {
        "difficulty_auto_adjust": True,
        "prize_optimization": True,
        "rotation_interval_hours": 4,
    },
    "food_waste": {
        "waste_target_percentage": 3,
        "prep_forecast_days": 7,
        "min_stock_days": 2,
    },
    "sentiment": {
        "response_trigger_rating": 3,
        "escalation_keywords": ["refund", "manager", "complaint"],
        "auto_response_enabled": False,
    },
    "recommendation": {
        "personalization_depth": "medium",
        "cross_sell_aggressiveness": "moderate",
        "min_confidence_score": 0.6,
    },
}


class AIConfigService:
    """Service for AI configuration management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_configs(self, venue_id: UUID) -> List[VenueAIConfig]:
        """Get all AI configurations for a venue."""
        result = await self.db.execute(
            select(VenueAIConfig)
            .where(VenueAIConfig.venue_id == venue_id)
            .order_by(VenueAIConfig.ai_service)
        )
        return list(result.scalars().all())

    async def get_enabled_services(self, venue_id: UUID) -> List[str]:
        """Get list of enabled AI service names."""
        result = await self.db.execute(
            select(VenueAIConfig.ai_service)
            .where(
                VenueAIConfig.venue_id == venue_id,
                VenueAIConfig.is_enabled == True,
            )
        )
        return [row[0] for row in result.all()]

    async def get_config(
        self,
        venue_id: UUID,
        ai_service: str,
    ) -> Optional[VenueAIConfig]:
        """Get configuration for a specific AI service."""
        result = await self.db.execute(
            select(VenueAIConfig).where(
                VenueAIConfig.venue_id == venue_id,
                VenueAIConfig.ai_service == ai_service,
            )
        )
        return result.scalar_one_or_none()

    async def is_service_enabled(
        self,
        venue_id: UUID,
        ai_service: str,
    ) -> bool:
        """Check if an AI service is enabled for a venue."""
        config = await self.get_config(venue_id, ai_service)
        return config.is_enabled if config else False

    async def get_service_params(
        self,
        venue_id: UUID,
        ai_service: str,
    ) -> Dict[str, Any]:
        """Get parameters for an AI service (merged with defaults)."""
        config = await self.get_config(venue_id, ai_service)
        defaults = DEFAULT_AI_PARAMS.get(ai_service, {})

        if not config:
            return defaults

        # Merge defaults with custom params
        return {**defaults, **(config.params or {})}

    async def set_config(
        self,
        venue_id: UUID,
        config_data: VenueAIConfigCreate,
    ) -> VenueAIConfig:
        """
        Create or update AI configuration.

        Args:
            venue_id: Venue UUID
            config_data: AI config data

        Returns:
            Created/updated config
        """
        # Check tier eligibility
        venue = await self._get_venue(venue_id)
        if venue and not self._is_service_allowed(
            config_data.ai_service,
            venue.subscription_tier,
        ):
            raise ValueError(
                f"AI service '{config_data.ai_service}' is not available "
                f"for {venue.subscription_tier.value} tier"
            )

        existing = await self.get_config(venue_id, config_data.ai_service)

        if existing:
            # Update existing
            was_enabled = existing.is_enabled
            existing.is_enabled = config_data.is_enabled
            existing.strategy = config_data.strategy
            existing.params = config_data.params or existing.params
            existing.notes = config_data.notes

            if config_data.is_enabled and not was_enabled:
                existing.enabled_at = datetime.utcnow()
                existing.disabled_at = None
            elif not config_data.is_enabled and was_enabled:
                existing.disabled_at = datetime.utcnow()

            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        # Create new with default params
        default_params = DEFAULT_AI_PARAMS.get(config_data.ai_service, {})
        merged_params = {**default_params, **(config_data.params or {})}

        config = VenueAIConfig(
            venue_id=venue_id,
            ai_service=config_data.ai_service,
            is_enabled=config_data.is_enabled,
            strategy=config_data.strategy,
            params=merged_params,
            notes=config_data.notes,
            enabled_at=datetime.utcnow() if config_data.is_enabled else None,
        )
        self.db.add(config)
        await self.db.flush()
        await self.db.refresh(config)

        logger.info(
            "ai_config_set",
            venue_id=str(venue_id),
            service=config_data.ai_service,
            enabled=config_data.is_enabled,
            strategy=config_data.strategy.value,
        )

        return config

    async def enable_service(
        self,
        venue_id: UUID,
        ai_service: str,
        strategy: AIStrategy = AIStrategy.MODERATE,
        params: Optional[Dict[str, Any]] = None,
    ) -> VenueAIConfig:
        """Enable an AI service for a venue."""
        config_data = VenueAIConfigCreate(
            ai_service=ai_service,
            is_enabled=True,
            strategy=strategy,
            params=params,
        )
        return await self.set_config(venue_id, config_data)

    async def disable_service(
        self,
        venue_id: UUID,
        ai_service: str,
    ) -> Optional[VenueAIConfig]:
        """Disable an AI service for a venue."""
        config = await self.get_config(venue_id, ai_service)

        if not config:
            return None

        config.is_enabled = False
        config.disabled_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(config)

        logger.info(
            "ai_service_disabled",
            venue_id=str(venue_id),
            service=ai_service,
        )

        return config

    async def update_strategy(
        self,
        venue_id: UUID,
        ai_service: str,
        strategy: AIStrategy,
    ) -> Optional[VenueAIConfig]:
        """Update the strategy for an AI service."""
        config = await self.get_config(venue_id, ai_service)

        if not config:
            return None

        config.strategy = strategy

        await self.db.flush()
        await self.db.refresh(config)

        logger.info(
            "ai_strategy_updated",
            venue_id=str(venue_id),
            service=ai_service,
            strategy=strategy.value,
        )

        return config

    async def update_params(
        self,
        venue_id: UUID,
        ai_service: str,
        params: Dict[str, Any],
    ) -> Optional[VenueAIConfig]:
        """Update parameters for an AI service."""
        config = await self.get_config(venue_id, ai_service)

        if not config:
            return None

        # Merge with existing params
        config.params = {**(config.params or {}), **params}

        await self.db.flush()
        await self.db.refresh(config)

        return config

    async def get_available_services(
        self,
        venue_id: UUID,
    ) -> List[str]:
        """Get list of AI services available for venue's subscription tier."""
        venue = await self._get_venue(venue_id)
        if not venue:
            return []

        return list(TIER_AI_SERVICES.get(venue.subscription_tier, set()))

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _get_venue(self, venue_id: UUID) -> Optional[Venue]:
        """Get venue by ID."""
        result = await self.db.execute(
            select(Venue).where(Venue.id == venue_id)
        )
        return result.scalar_one_or_none()

    def _is_service_allowed(
        self,
        ai_service: str,
        tier: SubscriptionTier,
    ) -> bool:
        """Check if AI service is allowed for subscription tier."""
        allowed = TIER_AI_SERVICES.get(tier, set())
        return ai_service in allowed
