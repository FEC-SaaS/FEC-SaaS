"""
=============================================================================
FILE: services/settings_service.py
PURPOSE: Venue settings (key-value configuration) management
=============================================================================
"""

import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.venue import VenueSetting, SettingType
from app.schemas.venue import VenueSettingCreate, VenueSettingUpdate

logger = structlog.get_logger()


class SettingsService:
    """Service for venue settings management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_settings(
        self,
        venue_id: UUID,
        category: Optional[str] = None,
        include_sensitive: bool = False,
    ) -> List[VenueSetting]:
        """
        Get all settings for a venue.

        Args:
            venue_id: Venue UUID
            category: Optional category filter
            include_sensitive: Include sensitive settings

        Returns:
            List of settings
        """
        query = select(VenueSetting).where(VenueSetting.venue_id == venue_id)

        if category:
            query = query.where(VenueSetting.category == category)

        if not include_sensitive:
            query = query.where(VenueSetting.is_sensitive == False)

        query = query.order_by(VenueSetting.category, VenueSetting.setting_key)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_setting(
        self,
        venue_id: UUID,
        setting_key: str,
    ) -> Optional[VenueSetting]:
        """Get a specific setting by key."""
        result = await self.db.execute(
            select(VenueSetting).where(
                VenueSetting.venue_id == venue_id,
                VenueSetting.setting_key == setting_key,
            )
        )
        return result.scalar_one_or_none()

    async def get_setting_value(
        self,
        venue_id: UUID,
        setting_key: str,
        default: Any = None,
    ) -> Any:
        """
        Get a setting value with type conversion.

        Args:
            venue_id: Venue UUID
            setting_key: Setting key
            default: Default value if not found

        Returns:
            Typed setting value
        """
        setting = await self.get_setting(venue_id, setting_key)

        if not setting:
            return default

        return self._convert_value(setting.setting_value, setting.setting_type)

    async def set_setting(
        self,
        venue_id: UUID,
        setting_data: VenueSettingCreate,
    ) -> VenueSetting:
        """
        Create or update a setting.

        Args:
            venue_id: Venue UUID
            setting_data: Setting data

        Returns:
            Created/updated setting
        """
        existing = await self.get_setting(venue_id, setting_data.setting_key)

        if existing:
            # Update existing
            existing.setting_value = self._serialize_value(
                setting_data.setting_value,
                setting_data.setting_type,
            )
            existing.setting_type = setting_data.setting_type
            existing.description = setting_data.description
            existing.is_sensitive = setting_data.is_sensitive
            existing.category = setting_data.category

            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        # Create new
        setting = VenueSetting(
            venue_id=venue_id,
            setting_key=setting_data.setting_key,
            setting_value=self._serialize_value(
                setting_data.setting_value,
                setting_data.setting_type,
            ),
            setting_type=setting_data.setting_type,
            description=setting_data.description,
            is_sensitive=setting_data.is_sensitive,
            category=setting_data.category,
        )
        self.db.add(setting)
        await self.db.flush()
        await self.db.refresh(setting)

        logger.info(
            "setting_created",
            venue_id=str(venue_id),
            key=setting_data.setting_key,
        )

        return setting

    async def update_setting(
        self,
        venue_id: UUID,
        setting_key: str,
        update_data: VenueSettingUpdate,
    ) -> Optional[VenueSetting]:
        """Update an existing setting."""
        setting = await self.get_setting(venue_id, setting_key)

        if not setting:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(setting, field, value)

        await self.db.flush()
        await self.db.refresh(setting)

        return setting

    async def delete_setting(
        self,
        venue_id: UUID,
        setting_key: str,
    ) -> bool:
        """Delete a setting."""
        result = await self.db.execute(
            delete(VenueSetting).where(
                VenueSetting.venue_id == venue_id,
                VenueSetting.setting_key == setting_key,
            )
        )
        return result.rowcount > 0

    async def bulk_set_settings(
        self,
        venue_id: UUID,
        settings: Dict[str, Any],
        category: Optional[str] = None,
    ) -> int:
        """
        Bulk create/update settings.

        Args:
            venue_id: Venue UUID
            settings: Key-value pairs to set
            category: Optional category for new settings

        Returns:
            Number of settings updated
        """
        count = 0

        for key, value in settings.items():
            setting_type = self._infer_type(value)
            setting_data = VenueSettingCreate(
                setting_key=key,
                setting_value=self._serialize_value(value, setting_type),
                setting_type=setting_type,
                category=category,
            )
            await self.set_setting(venue_id, setting_data)
            count += 1

        logger.info(
            "bulk_settings_updated",
            venue_id=str(venue_id),
            count=count,
        )

        return count

    async def get_settings_as_dict(
        self,
        venue_id: UUID,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get all settings as a dictionary with typed values."""
        settings = await self.get_all_settings(venue_id, category)

        return {
            s.setting_key: self._convert_value(s.setting_value, s.setting_type)
            for s in settings
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _infer_type(self, value: Any) -> SettingType:
        """Infer setting type from value."""
        if isinstance(value, bool):
            return SettingType.BOOLEAN
        if isinstance(value, (int, float)):
            return SettingType.NUMBER
        if isinstance(value, (dict, list)):
            return SettingType.JSON
        return SettingType.STRING

    def _serialize_value(self, value: Any, setting_type: SettingType) -> str:
        """Serialize value to string for storage."""
        if setting_type == SettingType.JSON:
            return json.dumps(value)
        if setting_type == SettingType.BOOLEAN:
            return "true" if value else "false"
        return str(value)

    def _convert_value(self, value: str, setting_type: SettingType) -> Any:
        """Convert stored string to typed value."""
        if setting_type == SettingType.BOOLEAN:
            return value.lower() in ("true", "1", "yes")
        if setting_type == SettingType.NUMBER:
            try:
                if "." in value:
                    return float(value)
                return int(value)
            except ValueError:
                return 0
        if setting_type == SettingType.JSON:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return {}
        return value
