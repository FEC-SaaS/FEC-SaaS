"""
=============================================================================
FILE: core/audit.py
PURPOSE: Audit logging for venue service operations
=============================================================================

Provides comprehensive audit logging for:
- CRUD operations on venues
- Configuration changes
- Feature toggles
- AI service changes
- Access logging

Audit logs are stored in PostgreSQL and can be forwarded to external systems.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

import structlog
from sqlalchemy import String, Text, Enum as SAEnum, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

logger = structlog.get_logger()


class AuditAction(str, Enum):
    """Audit action types."""
    # Venue actions
    VENUE_CREATE = "venue.create"
    VENUE_READ = "venue.read"
    VENUE_UPDATE = "venue.update"
    VENUE_DELETE = "venue.delete"
    VENUE_STATUS_CHANGE = "venue.status_change"

    # Hours actions
    HOURS_SET = "hours.set"
    HOURS_UPDATE = "hours.update"
    SPECIAL_HOURS_CREATE = "special_hours.create"
    SPECIAL_HOURS_DELETE = "special_hours.delete"

    # Settings actions
    SETTING_CREATE = "setting.create"
    SETTING_UPDATE = "setting.update"
    SETTING_DELETE = "setting.delete"
    SETTINGS_BULK_UPDATE = "settings.bulk_update"

    # Feature actions
    FEATURE_ENABLE = "feature.enable"
    FEATURE_DISABLE = "feature.disable"
    FEATURE_CONFIG_UPDATE = "feature.config_update"

    # AI Config actions
    AI_SERVICE_ENABLE = "ai_service.enable"
    AI_SERVICE_DISABLE = "ai_service.disable"
    AI_CONFIG_UPDATE = "ai_config.update"
    AI_CONFIG_RESET = "ai_config.reset"

    # Onboarding actions
    ONBOARDING_START = "onboarding.start"
    ONBOARDING_STEP_COMPLETE = "onboarding.step_complete"
    ONBOARDING_COMPLETE = "onboarding.complete"
    ONBOARDING_RESET = "onboarding.reset"

    # Performance actions
    PERFORMANCE_RECORD = "performance.record"
    PERFORMANCE_DELETE = "performance.delete"

    # Access actions
    ACCESS_GRANTED = "access.granted"
    ACCESS_DENIED = "access.denied"


class AuditLog(Base):
    """Audit log database model."""
    __tablename__ = "audit_logs"

    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), index=True)
    actor_email: Mapped[Optional[str]] = mapped_column(String(255))
    actor_ip: Mapped[Optional[str]] = mapped_column(String(45))  # IPv6 max length

    venue_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True))

    old_value: Mapped[Optional[dict]] = mapped_column(JSONB)
    new_value: Mapped[Optional[dict]] = mapped_column(JSONB)
    changes: Mapped[Optional[dict]] = mapped_column(JSONB)

    metadata: Mapped[Optional[dict]] = mapped_column(JSONB)
    request_id: Mapped[Optional[str]] = mapped_column(String(36))

    __table_args__ = (
        Index("idx_audit_logs_venue_action", "venue_id", "action"),
        Index("idx_audit_logs_actor", "actor_id", "created_at"),
        Index("idx_audit_logs_created_at", "created_at"),
    )


class AuditLogger:
    """Service for creating audit log entries."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def log(
        self,
        action: AuditAction,
        actor_id: UUID = None,
        actor_email: str = None,
        actor_ip: str = None,
        venue_id: UUID = None,
        resource_type: str = None,
        resource_id: UUID = None,
        old_value: Dict[str, Any] = None,
        new_value: Dict[str, Any] = None,
        changes: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
        request_id: str = None,
    ) -> AuditLog:
        """Create an audit log entry."""
        audit_log = AuditLog(
            id=uuid.uuid4(),
            action=action.value,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_ip=actor_ip,
            venue_id=venue_id,
            resource_type=resource_type or action.value.split(".")[0],
            resource_id=resource_id,
            old_value=old_value,
            new_value=new_value,
            changes=changes,
            metadata=metadata,
            request_id=request_id,
        )

        self.db.add(audit_log)
        await self.db.commit()

        logger.info(
            "audit_logged",
            action=action.value,
            actor_id=str(actor_id) if actor_id else None,
            venue_id=str(venue_id) if venue_id else None,
            resource_type=resource_type,
        )

        return audit_log

    # -------------------------------------------------------------------------
    # Convenience methods for common actions
    # -------------------------------------------------------------------------

    async def log_venue_create(
        self,
        venue_id: UUID,
        venue_data: Dict[str, Any],
        actor_id: UUID = None,
        actor_email: str = None,
        actor_ip: str = None,
    ) -> AuditLog:
        """Log venue creation."""
        return await self.log(
            action=AuditAction.VENUE_CREATE,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_ip=actor_ip,
            venue_id=venue_id,
            resource_type="venue",
            resource_id=venue_id,
            new_value=venue_data,
        )

    async def log_venue_update(
        self,
        venue_id: UUID,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        changes: Dict[str, Any],
        actor_id: UUID = None,
        actor_email: str = None,
        actor_ip: str = None,
    ) -> AuditLog:
        """Log venue update."""
        return await self.log(
            action=AuditAction.VENUE_UPDATE,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_ip=actor_ip,
            venue_id=venue_id,
            resource_type="venue",
            resource_id=venue_id,
            old_value=old_data,
            new_value=new_data,
            changes=changes,
        )

    async def log_venue_delete(
        self,
        venue_id: UUID,
        venue_data: Dict[str, Any],
        hard_delete: bool = False,
        actor_id: UUID = None,
        actor_email: str = None,
        actor_ip: str = None,
    ) -> AuditLog:
        """Log venue deletion."""
        return await self.log(
            action=AuditAction.VENUE_DELETE,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_ip=actor_ip,
            venue_id=venue_id,
            resource_type="venue",
            resource_id=venue_id,
            old_value=venue_data,
            metadata={"hard_delete": hard_delete},
        )

    async def log_status_change(
        self,
        venue_id: UUID,
        old_status: str,
        new_status: str,
        actor_id: UUID = None,
        actor_email: str = None,
        actor_ip: str = None,
    ) -> AuditLog:
        """Log venue status change."""
        return await self.log(
            action=AuditAction.VENUE_STATUS_CHANGE,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_ip=actor_ip,
            venue_id=venue_id,
            resource_type="venue",
            resource_id=venue_id,
            changes={
                "status": {"old": old_status, "new": new_status},
            },
        )

    async def log_feature_toggle(
        self,
        venue_id: UUID,
        feature_name: str,
        enabled: bool,
        config: Dict[str, Any] = None,
        actor_id: UUID = None,
        actor_email: str = None,
        actor_ip: str = None,
    ) -> AuditLog:
        """Log feature toggle."""
        action = AuditAction.FEATURE_ENABLE if enabled else AuditAction.FEATURE_DISABLE
        return await self.log(
            action=action,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_ip=actor_ip,
            venue_id=venue_id,
            resource_type="feature",
            new_value={
                "feature_name": feature_name,
                "enabled": enabled,
                "config": config,
            },
        )

    async def log_setting_change(
        self,
        venue_id: UUID,
        setting_key: str,
        old_value: str = None,
        new_value: str = None,
        action: AuditAction = AuditAction.SETTING_UPDATE,
        actor_id: UUID = None,
        actor_email: str = None,
        actor_ip: str = None,
    ) -> AuditLog:
        """Log setting change."""
        # Mask sensitive values
        masked_old = "***" if old_value and "secret" in setting_key.lower() else old_value
        masked_new = "***" if new_value and "secret" in setting_key.lower() else new_value

        return await self.log(
            action=action,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_ip=actor_ip,
            venue_id=venue_id,
            resource_type="setting",
            changes={
                "setting_key": setting_key,
                "old_value": masked_old,
                "new_value": masked_new,
            },
        )

    async def log_ai_config_change(
        self,
        venue_id: UUID,
        service_name: str,
        action: AuditAction,
        old_config: Dict[str, Any] = None,
        new_config: Dict[str, Any] = None,
        actor_id: UUID = None,
        actor_email: str = None,
        actor_ip: str = None,
    ) -> AuditLog:
        """Log AI config change."""
        return await self.log(
            action=action,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_ip=actor_ip,
            venue_id=venue_id,
            resource_type="ai_config",
            old_value=old_config,
            new_value=new_config,
            metadata={"service_name": service_name},
        )

    async def log_access(
        self,
        venue_id: UUID,
        granted: bool,
        reason: str = None,
        actor_id: UUID = None,
        actor_email: str = None,
        actor_ip: str = None,
    ) -> AuditLog:
        """Log access attempt."""
        action = AuditAction.ACCESS_GRANTED if granted else AuditAction.ACCESS_DENIED
        return await self.log(
            action=action,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_ip=actor_ip,
            venue_id=venue_id,
            resource_type="access",
            metadata={"reason": reason},
        )


def get_audit_logger(db_session: AsyncSession) -> AuditLogger:
    """Get audit logger instance."""
    return AuditLogger(db_session)
