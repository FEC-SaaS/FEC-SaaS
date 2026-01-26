"""
=============================================================================
FILE: tests/unit/test_ai_config_service.py
PURPOSE: Unit tests for AIConfigService class
=============================================================================
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.venue import Venue, VenueAIConfig, SubscriptionTier, VenueStatus, OnboardingStatus, AIStrategy
from app.schemas.venue import VenueAIConfigUpdate
from app.services.ai_config_service import AIConfigService, TIER_AI_SERVICES, DEFAULT_AI_PARAMS


class TestAIConfigService:
    """Tests for AIConfigService class."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        session.delete = AsyncMock()
        return session

    @pytest.fixture
    def ai_config_service(self, mock_db_session):
        """Create AIConfigService instance with mock session."""
        return AIConfigService(mock_db_session)

    @pytest.fixture
    def venue_id(self):
        """Generate test venue ID."""
        return uuid.uuid4()

    @pytest.fixture
    def starter_venue(self, venue_id):
        """Create starter tier venue."""
        return Venue(
            id=venue_id,
            name="Starter FEC",
            slug="starter-fec",
            subscription_tier=SubscriptionTier.STARTER,
            status=VenueStatus.ACTIVE,
            onboarding_status=OnboardingStatus.COMPLETED,
            address_line1="123 Main St",
            city="Dallas",
            state="Texas",
            postal_code="75001",
            country="USA",
            timezone="America/Chicago",
            phone="+1-214-555-0100",
            email="test@fec.com",
        )

    @pytest.fixture
    def pro_venue(self, venue_id):
        """Create pro tier venue."""
        return Venue(
            id=venue_id,
            name="Pro FEC",
            slug="pro-fec",
            subscription_tier=SubscriptionTier.PRO,
            status=VenueStatus.ACTIVE,
            onboarding_status=OnboardingStatus.COMPLETED,
            address_line1="123 Main St",
            city="Dallas",
            state="Texas",
            postal_code="75001",
            country="USA",
            timezone="America/Chicago",
            phone="+1-214-555-0100",
            email="test@fec.com",
        )

    @pytest.fixture
    def enterprise_venue(self, venue_id):
        """Create enterprise tier venue."""
        return Venue(
            id=venue_id,
            name="Enterprise FEC",
            slug="enterprise-fec",
            subscription_tier=SubscriptionTier.ENTERPRISE,
            status=VenueStatus.ACTIVE,
            onboarding_status=OnboardingStatus.COMPLETED,
            address_line1="123 Main St",
            city="Dallas",
            state="Texas",
            postal_code="75001",
            country="USA",
            timezone="America/Chicago",
            phone="+1-214-555-0100",
            email="test@fec.com",
        )

    # -------------------------------------------------------------------------
    # Tier AI Services Configuration Tests
    # -------------------------------------------------------------------------

    def test_tier_ai_services_defined(self):
        """Test that AI services are properly defined for each tier."""
        assert SubscriptionTier.STARTER in TIER_AI_SERVICES
        assert SubscriptionTier.PRO in TIER_AI_SERVICES
        assert SubscriptionTier.ENTERPRISE in TIER_AI_SERVICES

    def test_starter_tier_no_ai(self):
        """Test starter tier has no AI services."""
        starter_ai = TIER_AI_SERVICES[SubscriptionTier.STARTER]
        assert len(starter_ai) == 0

    def test_pro_tier_has_basic_ai(self):
        """Test pro tier includes basic AI services."""
        pro_ai = TIER_AI_SERVICES[SubscriptionTier.PRO]
        assert "dynamic_pricing" in pro_ai

    def test_enterprise_tier_has_all_ai(self):
        """Test enterprise tier includes all AI services."""
        enterprise_ai = TIER_AI_SERVICES[SubscriptionTier.ENTERPRISE]
        assert "dynamic_pricing" in enterprise_ai
        assert "smart_staff" in enterprise_ai
        assert "churn_prediction" in enterprise_ai

    def test_default_params_defined(self):
        """Test default AI parameters are defined."""
        assert "dynamic_pricing" in DEFAULT_AI_PARAMS
        assert "min_price_multiplier" in DEFAULT_AI_PARAMS["dynamic_pricing"]

    # -------------------------------------------------------------------------
    # Get Available AI Services Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_available_ai_services_starter(self, ai_config_service, mock_db_session, starter_venue):
        """Test getting available AI services for starter tier."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = starter_venue
        mock_db_session.execute.return_value = mock_result

        result = await ai_config_service.get_available_ai_services(starter_venue.id)

        assert result == set()  # No AI for starter

    @pytest.mark.asyncio
    async def test_get_available_ai_services_pro(self, ai_config_service, mock_db_session, pro_venue):
        """Test getting available AI services for pro tier."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pro_venue
        mock_db_session.execute.return_value = mock_result

        result = await ai_config_service.get_available_ai_services(pro_venue.id)

        assert "dynamic_pricing" in result

    @pytest.mark.asyncio
    async def test_get_available_ai_services_enterprise(self, ai_config_service, mock_db_session, enterprise_venue):
        """Test getting available AI services for enterprise tier."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = enterprise_venue
        mock_db_session.execute.return_value = mock_result

        result = await ai_config_service.get_available_ai_services(enterprise_venue.id)

        assert len(result) > len(TIER_AI_SERVICES[SubscriptionTier.PRO])

    # -------------------------------------------------------------------------
    # Enable AI Service Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_enable_ai_service_allowed(self, ai_config_service, mock_db_session, pro_venue):
        """Test enabling AI service allowed for tier."""
        mock_venue_result = MagicMock()
        mock_venue_result.scalar_one_or_none.return_value = pro_venue

        mock_config_result = MagicMock()
        mock_config_result.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [mock_venue_result, mock_config_result]

        result = await ai_config_service.enable_ai_service(
            pro_venue.id,
            "dynamic_pricing",
        )

        assert result is not None
        assert result.is_enabled is True
        mock_db_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_enable_ai_service_not_allowed(self, ai_config_service, mock_db_session, starter_venue):
        """Test enabling AI service not allowed for tier."""
        mock_venue_result = MagicMock()
        mock_venue_result.scalar_one_or_none.return_value = starter_venue
        mock_db_session.execute.return_value = mock_venue_result

        result = await ai_config_service.enable_ai_service(
            starter_venue.id,
            "dynamic_pricing",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_enable_ai_service_with_params(self, ai_config_service, mock_db_session, enterprise_venue):
        """Test enabling AI service with custom parameters."""
        mock_venue_result = MagicMock()
        mock_venue_result.scalar_one_or_none.return_value = enterprise_venue

        mock_config_result = MagicMock()
        mock_config_result.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [mock_venue_result, mock_config_result]

        custom_params = {
            "min_price_multiplier": 0.9,
            "max_price_multiplier": 1.3,
        }

        result = await ai_config_service.enable_ai_service(
            enterprise_venue.id,
            "dynamic_pricing",
            parameters=custom_params,
        )

        assert result is not None
        assert result.params["min_price_multiplier"] == 0.9

    @pytest.mark.asyncio
    async def test_enable_ai_service_uses_defaults(self, ai_config_service, mock_db_session, pro_venue):
        """Test enabling AI service uses default params if none provided."""
        mock_venue_result = MagicMock()
        mock_venue_result.scalar_one_or_none.return_value = pro_venue

        mock_config_result = MagicMock()
        mock_config_result.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [mock_venue_result, mock_config_result]

        result = await ai_config_service.enable_ai_service(
            pro_venue.id,
            "dynamic_pricing",
        )

        assert result is not None
        # Should use default params
        assert result.params == DEFAULT_AI_PARAMS.get("dynamic_pricing", {})

    # -------------------------------------------------------------------------
    # Update AI Config Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_ai_config(self, ai_config_service, mock_db_session, venue_id):
        """Test updating AI configuration."""
        existing_config = VenueAIConfig(
            id=uuid.uuid4(),
            venue_id=venue_id,
            ai_service="dynamic_pricing",
            is_enabled=True,
            strategy=AIStrategy.MODERATE,
            params={"min_price_multiplier": 0.8},
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_config
        mock_db_session.execute.return_value = mock_result

        update_data = VenueAIConfigUpdate(
            strategy=AIStrategy.AGGRESSIVE,
            params={"min_price_multiplier": 0.7},
        )

        result = await ai_config_service.update_ai_config(venue_id, "dynamic_pricing", update_data)

        assert result is not None
        assert result.strategy == AIStrategy.AGGRESSIVE
        assert result.params["min_price_multiplier"] == 0.7

    @pytest.mark.asyncio
    async def test_update_ai_config_not_found(self, ai_config_service, mock_db_session, venue_id):
        """Test updating non-existent AI config."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        update_data = VenueAIConfigUpdate(strategy=AIStrategy.CONSERVATIVE)

        result = await ai_config_service.update_ai_config(venue_id, "dynamic_pricing", update_data)

        assert result is None

    # -------------------------------------------------------------------------
    # Disable AI Service Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_disable_ai_service(self, ai_config_service, mock_db_session, venue_id):
        """Test disabling AI service."""
        existing_config = VenueAIConfig(
            id=uuid.uuid4(),
            venue_id=venue_id,
            ai_service="dynamic_pricing",
            is_enabled=True,
            enabled_at=datetime.utcnow(),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_config
        mock_db_session.execute.return_value = mock_result

        result = await ai_config_service.disable_ai_service(venue_id, "dynamic_pricing")

        assert result is True
        assert existing_config.is_enabled is False
        assert existing_config.disabled_at is not None

    @pytest.mark.asyncio
    async def test_disable_ai_service_not_found(self, ai_config_service, mock_db_session, venue_id):
        """Test disabling non-existent AI service."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await ai_config_service.disable_ai_service(venue_id, "dynamic_pricing")

        assert result is False

    # -------------------------------------------------------------------------
    # Reset to Defaults Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_reset_to_defaults(self, ai_config_service, mock_db_session, venue_id):
        """Test resetting AI config to defaults."""
        existing_config = VenueAIConfig(
            id=uuid.uuid4(),
            venue_id=venue_id,
            ai_service="dynamic_pricing",
            is_enabled=True,
            strategy=AIStrategy.AGGRESSIVE,
            params={"custom": "params"},
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_config
        mock_db_session.execute.return_value = mock_result

        result = await ai_config_service.reset_to_defaults(venue_id, "dynamic_pricing")

        assert result is not None
        assert result.strategy == AIStrategy.MODERATE
        assert result.params == DEFAULT_AI_PARAMS.get("dynamic_pricing", {})

    # -------------------------------------------------------------------------
    # Get AI Configs Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_ai_configs(self, ai_config_service, mock_db_session, venue_id):
        """Test getting all AI configs for venue."""
        configs = [
            VenueAIConfig(
                id=uuid.uuid4(),
                venue_id=venue_id,
                ai_service="dynamic_pricing",
                is_enabled=True,
            ),
            VenueAIConfig(
                id=uuid.uuid4(),
                venue_id=venue_id,
                ai_service="smart_staff",
                is_enabled=True,
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = configs
        mock_db_session.execute.return_value = mock_result

        result = await ai_config_service.get_ai_configs(venue_id)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_ai_config_single(self, ai_config_service, mock_db_session, venue_id):
        """Test getting single AI config."""
        config = VenueAIConfig(
            id=uuid.uuid4(),
            venue_id=venue_id,
            ai_service="dynamic_pricing",
            is_enabled=True,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = config
        mock_db_session.execute.return_value = mock_result

        result = await ai_config_service.get_ai_config(venue_id, "dynamic_pricing")

        assert result is not None
        assert result.ai_service == "dynamic_pricing"
