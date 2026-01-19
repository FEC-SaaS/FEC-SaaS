"""Audit logging service for security events."""
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import structlog
from sqlalchemy.orm import Session

from app.core.config import get_settings

settings = get_settings()

# Configure structlog for structured JSON logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("audit")


class AuditEventType(str, Enum):
    """Types of audit events."""
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REFRESH_FAILED = "token_refresh_failed"

    # Account events
    REGISTER = "register"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET_REQUEST = "password_reset_request"
    PASSWORD_RESET_COMPLETE = "password_reset_complete"
    EMAIL_VERIFICATION = "email_verification"
    PHONE_VERIFICATION = "phone_verification"
    ACCOUNT_DELETED = "account_deleted"

    # Security events
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    TOKEN_BLACKLISTED = "token_blacklisted"
    ALL_TOKENS_INVALIDATED = "all_tokens_invalidated"

    # Privacy events
    PRIVACY_CONSENT_GRANTED = "privacy_consent_granted"
    PRIVACY_CONSENT_REVOKED = "privacy_consent_revoked"
    DATA_EXPORT_REQUESTED = "data_export_requested"

    # Social auth events
    SOCIAL_AUTH_SUCCESS = "social_auth_success"
    SOCIAL_AUTH_FAILED = "social_auth_failed"
    SOCIAL_ACCOUNT_LINKED = "social_account_linked"


class AuditLogService:
    """Service for logging security and audit events."""

    _request_id: Optional[str] = None

    @classmethod
    def set_request_id(cls, request_id: str) -> None:
        """Set the current request ID for correlation."""
        cls._request_id = request_id

    @classmethod
    def get_request_id(cls) -> str:
        """Get current request ID or generate one."""
        if not cls._request_id:
            cls._request_id = str(uuid.uuid4())
        return cls._request_id

    @classmethod
    def log_event(
        cls,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        details: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Log an audit event.

        Args:
            event_type: Type of the audit event
            user_id: User ID if known
            email: Email address (for login attempts)
            ip_address: Client IP address
            user_agent: Client user agent
            success: Whether the action was successful
            details: Additional event-specific details
            error_message: Error message if action failed
        """
        log_data = {
            "event_type": event_type.value,
            "request_id": cls.get_request_id(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": success,
            "service": settings.PROJECT_NAME,
            "environment": settings.ENV,
        }

        if user_id:
            log_data["user_id"] = user_id
        if email:
            # Mask email for privacy in logs
            log_data["email"] = cls._mask_email(email)
        if ip_address:
            log_data["ip_address"] = ip_address
        if user_agent:
            log_data["user_agent"] = user_agent[:200]  # Truncate long user agents
        if details:
            log_data["details"] = details
        if error_message:
            log_data["error"] = error_message

        # Log at appropriate level
        if success:
            if event_type in (
                AuditEventType.ACCOUNT_LOCKED,
                AuditEventType.SUSPICIOUS_ACTIVITY,
                AuditEventType.ALL_TOKENS_INVALIDATED,
            ):
                logger.warning("security_event", **log_data)
            else:
                logger.info("audit_event", **log_data)
        else:
            if event_type in (
                AuditEventType.LOGIN_FAILED,
                AuditEventType.TOKEN_REFRESH_FAILED,
            ):
                logger.warning("auth_failure", **log_data)
            else:
                logger.error("audit_event_failed", **log_data)

    @staticmethod
    def _mask_email(email: str) -> str:
        """Mask email for privacy in logs."""
        if "@" not in email:
            return "***"
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            masked_local = "*" * len(local)
        else:
            masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
        return f"{masked_local}@{domain}"

    @classmethod
    def log_login_success(
        cls,
        user_id: str,
        email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Log successful login."""
        cls.log_event(
            AuditEventType.LOGIN_SUCCESS,
            user_id=user_id,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @classmethod
    def log_login_failed(
        cls,
        email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        reason: str = "invalid_credentials",
    ) -> None:
        """Log failed login attempt."""
        cls.log_event(
            AuditEventType.LOGIN_FAILED,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            error_message=reason,
        )

    @classmethod
    def log_account_locked(
        cls,
        email: str,
        ip_address: Optional[str] = None,
        lockout_duration: int = 900,
    ) -> None:
        """Log account lockout."""
        cls.log_event(
            AuditEventType.ACCOUNT_LOCKED,
            email=email,
            ip_address=ip_address,
            details={"lockout_duration_seconds": lockout_duration},
        )

    @classmethod
    def log_registration(
        cls,
        user_id: str,
        email: str,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log new user registration."""
        cls.log_event(
            AuditEventType.REGISTER,
            user_id=user_id,
            email=email,
            ip_address=ip_address,
        )

    @classmethod
    def log_password_change(
        cls,
        user_id: str,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log password change."""
        cls.log_event(
            AuditEventType.PASSWORD_CHANGE,
            user_id=user_id,
            ip_address=ip_address,
        )

    @classmethod
    def log_token_refresh(
        cls,
        user_id: str,
        ip_address: Optional[str] = None,
        rotated: bool = False,
    ) -> None:
        """Log token refresh."""
        cls.log_event(
            AuditEventType.TOKEN_REFRESH,
            user_id=user_id,
            ip_address=ip_address,
            details={"token_rotated": rotated},
        )

    @classmethod
    def log_logout(
        cls,
        user_id: str,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log logout."""
        cls.log_event(
            AuditEventType.LOGOUT,
            user_id=user_id,
            ip_address=ip_address,
        )

    @classmethod
    def log_data_export(
        cls,
        user_id: str,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log data export request (GDPR)."""
        cls.log_event(
            AuditEventType.DATA_EXPORT_REQUESTED,
            user_id=user_id,
            ip_address=ip_address,
        )
