"""
=============================================================================
FILE: tests/unit/test_feature_service.py
PURPOSE: Unit tests for FeatureService class
=============================================================================
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.venue import Venue, VenueFeature, SubscriptionTier, VenueStatus, OnboardingStatus
from app.services.feature_service import FeatureService, TIER_FEATURES


class TestFeatureService:
    """Tests for FeatureService class."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def feature_service(self, mock_db_session):
        """Create FeatureService instance with mock session."""
        return FeatureService(mock_db_session)

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
    # Tier Features Configuration Tests
    # -------------------------------------------------------------------------

    def test_tier_features_defined(self):
        """Test that tier features are properly defined."""
        assert SubscriptionTier.STARTER in TIER_FEATURES
        assert SubscriptionTier.PRO in TIER_FEATURES
        assert SubscriptionTier.ENTERPRISE in TIER_FEATURES

    def test_starter_tier_has_basic_features(self):
        """Test starter tier includes basic features."""
        starter_features = TIER_FEATURES[SubscriptionTier.STARTER]
        assert "bowling" in starter_features
        assert "arcade" in starter_features
        assert "pos" in starter_features
        assert "reservations" in starter_features

    def test_pro_tier_includes_starter_features(self):
        """Test pro tier includes all starter features."""
        starter_features = TIER_FEATURES[SubscriptionTier.STARTER]
        pro_features = TIER_FEATURES[SubscriptionTier.PRO]

        for feature in starter_features:
            assert feature in pro_features

    def test_enterprise_tier_includes_all_features(self):
        """Test enterprise tier includes all features."""
        enterprise_features = TIER_FEATURES[SubscriptionTier.ENTERPRISE]

        # Should have all pro features
        for feature in TIER_FEATURES[SubscriptionTier.PRO]:
            assert feature in enterprise_features

    # -------------------------------------------------------------------------
    # Get Available Features Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_available_features_starter(self, feature_service, mock_db_session, starter_venue):
        """Test getting available features for starter tier."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = starter_venue
        mock_db_session.execute.return_value = mock_result

        result = await feature_service.get_available_features(starter_venue.id)

        assert result == TIER_FEATURES[SubscriptionTier.STARTER]

    @pytest.mark.asyncio
    async def test_get_available_features_pro(self, feature_service, mock_db_session, pro_venue):
        """Test getting available features for pro tier."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pro_venue
        mock_db_session.execute.return_value = mock_result

        result = await feature_service.get_available_features(pro_venue.id)

        assert result == TIER_FEATURES[SubscriptionTier.PRO]
        assert "food_beverage" in result
        assert "parties" in result

    @pytest.mark.asyncio
    async def test_get_available_features_enterprise(self, feature_service, mock_db_session, enterprise_venue):
        """Test getting available features for enterprise tier."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = enterprise_venue
        mock_db_session.execute.return_value = mock_result

        result = await feature_service.get_available_features(enterprise_venue.id)

        assert result == TIER_FEATURES[SubscriptionTier.ENTERPRISE]
        assert "escape_rooms" in result
        assert "vr" in result

    # -------------------------------------------------------------------------
    # Toggle Feature Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_toggle_feature_enable_allowed(self, feature_service, mock_db_session, pro_venue):
        """Test enabling a feature allowed for tier."""
        mock_venue_result = MagicMock()
        mock_venue_result.scalar_one_or_none.return_value = pro_venue

        mock_feature_result = MagicMock()
        mock_feature_result.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [mock_venue_result, mock_feature_result]

        result = await feature_service.toggle_feature(
            pro_venue.id,
            "food_beverage",
            enabled=True,
        )

        assert result is not None
        assert result.is_enabled is True
        mock_db_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_toggle_feature_enable_not_allowed(self, feature_service, mock_db_session, starter_venue):
        """Test enabling a feature not allowed for tier."""
        mock_venue_result = MagicMock()
        mock_venue_result.scalar_one_or_none.return_value = starter_venue
        mock_db_session.execute.return_value = mock_venue_result

        # Try to enable enterprise feature on starter
        result = await feature_service.toggle_feature(
            starter_venue.id,
            "escape_rooms",
            enabled=True,
        )

        assert result is None  # Should not be allowed

    @pytest.mark.asyncio
    async def test_toggle_feature_disable(self, feature_service, mock_db_session, pro_venue):
        """Test disabling a feature."""
        existing_feature = VenueFeature(
            id=uuid.uuid4(),
            venue_id=pro_venue.id,
            feature_name="bowling",
            is_enabled=True,
            enabled_at=datetime.utcnow(),
        )

        mock_venue_result = MagicMock()
        mock_venue_result.scalar_one_or_none.return_value = pro_venue

        mock_feature_result = MagicMock()
        mock_feature_result.scalar_one_or_none.return_value = existing_feature

        mock_db_session.execute.side_effect = [mock_venue_result, mock_feature_result]

        result = await feature_service.toggle_feature(
            pro_venue.id,
            "bowling",
            enabled=False,
        )

        assert result is not None
        assert result.is_enabled is False
        assert result.disabled_at is not None

    @pytest.mark.asyncio
    async def test_toggle_feature_with_config(self, feature_service, mock_db_session, pro_venue):
        """Test toggling feature with configuration."""
        mock_venue_result = MagicMock()
        mock_venue_result.scalar_one_or_none.return_value = pro_venue

        mock_feature_result = MagicMock()
        mock_feature_result.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [mock_venue_result, mock_feature_result]

        config = {"lanes": 24, "max_players_per_lane": 6}

        result = await feature_service.toggle_feature(
            pro_venue.id,
            "bowling",
            enabled=True,
            config=config,
        )

        assert result is not None
        assert result.config == config

    # -------------------------------------------------------------------------
    # Get Features Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_features(self, feature_service, mock_db_session, venue_id):
        """Test getting all features for venue."""
        features = [
            VenueFeature(
                id=uuid.uuid4(),
                venue_id=venue_id,
                feature_name="bowling",
                is_enabled=True,
            ),
            VenueFeature(
                id=uuid.uuid4(),
                venue_id=venue_id,
                feature_name="arcade",
                is_enabled=True,
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = features
        mock_db_session.execute.return_value = mock_result

        result = await feature_service.get_features(venue_id)

        assert len(result) == 2

    # -------------------------------------------------------------------------
    # Bulk Toggle Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_bulk_toggle_features(self, feature_service, mock_db_session, pro_venue):
        """Test bulk toggling multiple features."""
        mock_venue_result = MagicMock()
        mock_venue_result.scalar_one_or_none.return_value = pro_venue

        mock_feature_result = MagicMock()
        mock_feature_result.scalar_one_or_none.return_value = None

        mock_db_session.execute.return_value = mock_venue_result

        features_dict = {
            "bowling": True,
            "arcade": True,
            "food_beverage": False,
        }

        result = await feature_service.bulk_toggle_features(pro_venue.id, features_dict)

        assert "success" in result
        assert "failed" in result

    # -------------------------------------------------------------------------
    # Update Feature Config Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_feature_config(self, feature_service, mock_db_session, venue_id):
        """Test updating feature configuration."""
        existing_feature = VenueFeature(
            id=uuid.uuid4(),
            venue_id=venue_id,
            feature_name="bowling",
            is_enabled=True,
            config={"lanes": 20},
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_feature
        mock_db_session.execute.return_value = mock_result

        new_config = {"lanes": 24, "max_players_per_lane": 8}

        result = await feature_service.update_feature_config(venue_id, "bowling", new_config)

        assert result is not None
        assert result.config == new_config

    @pytest.mark.asyncio
    async def test_update_feature_config_not_enabled(self, feature_service, mock_db_session, venue_id):
        """Test updating config for non-enabled feature."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await feature_service.update_feature_config(venue_id, "bowling", {})

        assert result is None
