"""
=============================================================================
FILE: tests/unit/test_settings_service.py
PURPOSE: Unit tests for SettingsService class
=============================================================================
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.venue import VenueSetting, SettingType
from app.schemas.venue import VenueSettingCreate, VenueSettingUpdate
from app.services.settings_service import SettingsService


class TestSettingsService:
    """Tests for SettingsService class."""

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
    def settings_service(self, mock_db_session):
        """Create SettingsService instance with mock session."""
        return SettingsService(mock_db_session)

    @pytest.fixture
    def venue_id(self):
        """Generate test venue ID."""
        return uuid.uuid4()

    @pytest.fixture
    def sample_setting(self, venue_id):
        """Create sample setting object."""
        return VenueSetting(
            id=uuid.uuid4(),
            venue_id=venue_id,
            setting_key="max_party_size",
            setting_value="50",
            setting_type=SettingType.NUMBER,
            description="Maximum party size",
            category="parties",
        )

    # -------------------------------------------------------------------------
    # Get Settings Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_all_settings(self, settings_service, mock_db_session, venue_id, sample_setting):
        """Test getting all settings for venue."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_setting]
        mock_db_session.execute.return_value = mock_result

        result = await settings_service.get_all_settings(venue_id)

        assert len(result) == 1
        assert result[0].setting_key == "max_party_size"

    @pytest.mark.asyncio
    async def test_get_settings_by_category(self, settings_service, mock_db_session, venue_id, sample_setting):
        """Test getting settings filtered by category."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_setting]
        mock_db_session.execute.return_value = mock_result

        result = await settings_service.get_all_settings(venue_id, category="parties")

        assert len(result) == 1
        assert result[0].category == "parties"

    @pytest.mark.asyncio
    async def test_get_settings_exclude_sensitive(self, settings_service, mock_db_session, venue_id):
        """Test that sensitive settings are excluded by default."""
        regular_setting = VenueSetting(
            id=uuid.uuid4(),
            venue_id=venue_id,
            setting_key="timezone",
            setting_value="America/Chicago",
            setting_type=SettingType.STRING,
            is_sensitive=False,
        )
        sensitive_setting = VenueSetting(
            id=uuid.uuid4(),
            venue_id=venue_id,
            setting_key="api_key",
            setting_value="secret123",
            setting_type=SettingType.STRING,
            is_sensitive=True,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [regular_setting]
        mock_db_session.execute.return_value = mock_result

        result = await settings_service.get_all_settings(venue_id, include_sensitive=False)

        # Should only return non-sensitive settings
        assert all(not s.is_sensitive for s in result)

    @pytest.mark.asyncio
    async def test_get_settings_include_sensitive(self, settings_service, mock_db_session, venue_id):
        """Test including sensitive settings when requested."""
        settings = [
            VenueSetting(
                id=uuid.uuid4(),
                venue_id=venue_id,
                setting_key="timezone",
                setting_value="America/Chicago",
                setting_type=SettingType.STRING,
                is_sensitive=False,
            ),
            VenueSetting(
                id=uuid.uuid4(),
                venue_id=venue_id,
                setting_key="api_key",
                setting_value="secret123",
                setting_type=SettingType.STRING,
                is_sensitive=True,
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = settings
        mock_db_session.execute.return_value = mock_result

        result = await settings_service.get_all_settings(venue_id, include_sensitive=True)

        assert len(result) == 2

    # -------------------------------------------------------------------------
    # Get Single Setting Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_setting_found(self, settings_service, mock_db_session, venue_id, sample_setting):
        """Test getting single setting by key."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_setting
        mock_db_session.execute.return_value = mock_result

        result = await settings_service.get_setting(venue_id, "max_party_size")

        assert result is not None
        assert result.setting_key == "max_party_size"

    @pytest.mark.asyncio
    async def test_get_setting_not_found(self, settings_service, mock_db_session, venue_id):
        """Test getting non-existent setting."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await settings_service.get_setting(venue_id, "nonexistent")

        assert result is None

    # -------------------------------------------------------------------------
    # Get Settings as Dict Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_settings_as_dict(self, settings_service, mock_db_session, venue_id):
        """Test getting settings as key-value dictionary."""
        settings = [
            VenueSetting(
                id=uuid.uuid4(),
                venue_id=venue_id,
                setting_key="max_party_size",
                setting_value="50",
                setting_type=SettingType.NUMBER,
            ),
            VenueSetting(
                id=uuid.uuid4(),
                venue_id=venue_id,
                setting_key="allow_walk_ins",
                setting_value="true",
                setting_type=SettingType.BOOLEAN,
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = settings
        mock_db_session.execute.return_value = mock_result

        result = await settings_service.get_settings_as_dict(venue_id)

        assert "max_party_size" in result
        assert "allow_walk_ins" in result

    # -------------------------------------------------------------------------
    # Set Setting Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_set_setting_create_new(self, settings_service, mock_db_session, venue_id):
        """Test creating new setting."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        setting_data = VenueSettingCreate(
            setting_key="new_setting",
            setting_value="value",
            setting_type=SettingType.STRING,
        )

        result = await settings_service.set_setting(venue_id, setting_data)

        assert result is not None
        assert result.setting_key == "new_setting"
        mock_db_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_setting_update_existing(self, settings_service, mock_db_session, venue_id, sample_setting):
        """Test updating existing setting."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_setting
        mock_db_session.execute.return_value = mock_result

        setting_data = VenueSettingCreate(
            setting_key="max_party_size",
            setting_value="75",
            setting_type=SettingType.NUMBER,
        )

        result = await settings_service.set_setting(venue_id, setting_data)

        assert result is not None
        assert result.setting_value == "75"
        mock_db_session.add.assert_not_called()  # Should update, not add

    # -------------------------------------------------------------------------
    # Update Setting Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_setting_success(self, settings_service, mock_db_session, venue_id, sample_setting):
        """Test updating setting."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_setting
        mock_db_session.execute.return_value = mock_result

        update_data = VenueSettingUpdate(
            setting_value="100",
            description="Updated max party size",
        )

        result = await settings_service.update_setting(venue_id, "max_party_size", update_data)

        assert result is not None
        assert result.setting_value == "100"
        assert result.description == "Updated max party size"

    @pytest.mark.asyncio
    async def test_update_setting_not_found(self, settings_service, mock_db_session, venue_id):
        """Test updating non-existent setting."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        update_data = VenueSettingUpdate(setting_value="value")

        result = await settings_service.update_setting(venue_id, "nonexistent", update_data)

        assert result is None

    # -------------------------------------------------------------------------
    # Delete Setting Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_setting_success(self, settings_service, mock_db_session, venue_id, sample_setting):
        """Test deleting setting."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_setting
        mock_db_session.execute.return_value = mock_result

        result = await settings_service.delete_setting(venue_id, "max_party_size")

        assert result is True
        mock_db_session.delete.assert_called_once_with(sample_setting)

    @pytest.mark.asyncio
    async def test_delete_setting_not_found(self, settings_service, mock_db_session, venue_id):
        """Test deleting non-existent setting."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await settings_service.delete_setting(venue_id, "nonexistent")

        assert result is False

    # -------------------------------------------------------------------------
    # Bulk Set Settings Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_bulk_set_settings(self, settings_service, mock_db_session, venue_id):
        """Test bulk setting multiple settings."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        settings_dict = {
            "setting1": "value1",
            "setting2": "value2",
            "setting3": "value3",
        }

        result = await settings_service.bulk_set_settings(venue_id, settings_dict)

        assert result == 3

    @pytest.mark.asyncio
    async def test_bulk_set_settings_with_category(self, settings_service, mock_db_session, venue_id):
        """Test bulk setting with category."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        settings_dict = {
            "setting1": "value1",
        }

        await settings_service.bulk_set_settings(venue_id, settings_dict, category="test_category")

        # Verify the setting was created with the category
        mock_db_session.add.assert_called()
