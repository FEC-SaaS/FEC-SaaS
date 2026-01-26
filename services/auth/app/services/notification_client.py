"""
=============================================================================
FILE: notification_client.py
PURPOSE: HTTP client for communicating with the Notification microservice
=============================================================================

This module provides a client class for sending notifications (emails, SMS,
push notifications) through the centralized Notification Service.

WHAT IT DOES:
- Sends email verification links to new users
- Sends password reset emails
- Sends MFA/2FA verification codes
- Sends welcome emails after registration
- Sends login alerts for security
- Sends password change confirmations

HOW IT WORKS:
1. Creates HTTP requests to the Notification Service API
2. Formats email/SMS content with HTML templates
3. Handles errors and logs all notification attempts
4. Uses async HTTP for non-blocking operations

DEPENDENCIES:
- httpx: Async HTTP client
- structlog: Structured logging
- Notification Service running at NOTIFICATION_SERVICE_URL

USAGE:
    from app.services.notification_client import notification_client

    await notification_client.send_email_verification(
        user_id="uuid",
        email="user@example.com",
        first_name="John",
        verification_token="token123"
    )

CONFIGURATION (from config.py):
- NOTIFICATION_SERVICE_URL: Base URL of notification service
- NOTIFICATION_SERVICE_TIMEOUT: Request timeout in seconds
- FRONTEND_URL: Frontend URL for email links
- EMAIL_VERIFICATION_URL: Template for verification links
- PASSWORD_RESET_URL: Template for password reset links

=============================================================================
"""

import httpx
import structlog
from typing import Any, Dict, Optional
from enum import Enum

from app.core.config import get_settings

settings = get_settings()
logger = structlog.get_logger()


class NotificationType(str, Enum):
    """
    Notification types supported by the notification service.
    These map to notification templates and preferences.
    """
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    PASSWORD_RESET = "PASSWORD_RESET"
    WELCOME = "WELCOME"
    LOGIN_ALERT = "LOGIN_ALERT"
    MFA_CODE = "MFA_CODE"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    ACCOUNT_DELETED = "ACCOUNT_DELETED"


class NotificationChannel(str, Enum):
    """
    Notification delivery channels.
    Each notification can be sent through multiple channels.
    """
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"
    IN_APP = "IN_APP"


class NotificationPriority(str, Enum):
    """
    Notification priority levels.
    URGENT bypasses quiet hours and is delivered immediately.
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class NotificationClient:
    """
    Async HTTP client for the Notification microservice.

    This client handles all communication with the notification service,
    including email templates, SMS formatting, and error handling.

    Attributes:
        base_url: Base URL of the notification service
        timeout: Request timeout in seconds
    """

    def __init__(self):
        self.base_url = settings.NOTIFICATION_SERVICE_URL
        self.timeout = settings.NOTIFICATION_SERVICE_TIMEOUT
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-load async HTTP client to avoid creating connections at import time."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def close(self):
        """Close the HTTP client connection. Call this on application shutdown."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def send_notification(
        self,
        recipient_id: str,
        recipient_email: Optional[str],
        recipient_phone: Optional[str],
        notification_type: NotificationType,
        channels: list[NotificationChannel],
        content: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        template_vars: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send a notification via the notification service.

        Args:
            recipient_id: User ID of the recipient
            recipient_email: Email address for EMAIL channel
            recipient_phone: Phone number for SMS channel
            notification_type: Type of notification (affects templates/preferences)
            channels: List of channels to send through
            content: Notification content with channel-specific data
            priority: Priority level (URGENT bypasses quiet hours)
            template_vars: Variables for template substitution

        Returns:
            Dict with success status and notification IDs

        Example:
            result = await client.send_notification(
                recipient_id="user-123",
                recipient_email="user@example.com",
                recipient_phone=None,
                notification_type=NotificationType.WELCOME,
                channels=[NotificationChannel.EMAIL],
                content={"email": {"subject": "Welcome!", "body_html": "<p>Hi!</p>"}},
            )
        """
        payload = {
            "recipient_id": recipient_id,
            "recipient_email": recipient_email,
            "recipient_phone": recipient_phone,
            "recipient_type": "CUSTOMER",
            "notification_type": notification_type.value,
            "channels": [ch.value for ch in channels],
            "priority": priority.value,
            "content": content,
            "template_vars": template_vars or {},
        }

        try:
            response = await self.client.post(
                "/api/v1/notifications/send",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

            logger.info(
                "notification_sent",
                recipient_id=recipient_id,
                notification_type=notification_type.value,
                channels=[ch.value for ch in channels],
            )

            return result

        except httpx.HTTPStatusError as e:
            logger.error(
                "notification_failed",
                recipient_id=recipient_id,
                notification_type=notification_type.value,
                status_code=e.response.status_code,
                error=str(e),
            )
            return {"success": False, "error": str(e)}

        except httpx.RequestError as e:
            logger.error(
                "notification_request_error",
                recipient_id=recipient_id,
                notification_type=notification_type.value,
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    async def send_email_verification(
        self,
        user_id: str,
        email: str,
        first_name: str,
        verification_token: str,
    ) -> Dict[str, Any]:
        """
        Send email verification link to a new user.

        Called after user registration to verify email ownership.
        The token is included in a clickable link that expires in 48 hours.
        """
        verification_url = settings.EMAIL_VERIFICATION_URL.format(
            frontend_url=settings.FRONTEND_URL,
            token=verification_token,
        )

        content = {
            "email": {
                "subject": "Verify Your Email - FEC SaaS",
                "body_html": f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h1 style="color: #6366f1;">Welcome to FEC SaaS!</h1>
                        <p>Hi {first_name or 'there'},</p>
                        <p>Thank you for signing up. Please verify your email address by clicking the button below:</p>
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{verification_url}"
                               style="background-color: #6366f1; color: white; padding: 12px 30px;
                                      text-decoration: none; border-radius: 6px; display: inline-block;">
                                Verify Email
                            </a>
                        </div>
                        <p>Or copy and paste this link into your browser:</p>
                        <p style="color: #6366f1; word-break: break-all;">{verification_url}</p>
                        <p>This link will expire in 48 hours.</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                        <p style="color: #666; font-size: 12px;">
                            If you didn't create an account, you can safely ignore this email.
                        </p>
                    </div>
                """,
                "body_text": f"Hi {first_name or 'there'}, verify your email by visiting: {verification_url}",
            }
        }

        return await self.send_notification(
            recipient_id=user_id,
            recipient_email=email,
            recipient_phone=None,
            notification_type=NotificationType.EMAIL_VERIFICATION,
            channels=[NotificationChannel.EMAIL],
            content=content,
            priority=NotificationPriority.HIGH,
        )

    async def send_password_reset(
        self,
        user_id: str,
        email: str,
        first_name: str,
        reset_token: str,
    ) -> Dict[str, Any]:
        """
        Send password reset email with secure token link.

        Called when user requests password reset via forgot-password endpoint.
        The token expires in 24 hours for security.
        """
        reset_url = settings.PASSWORD_RESET_URL.format(
            frontend_url=settings.FRONTEND_URL,
            token=reset_token,
        )

        content = {
            "email": {
                "subject": "Reset Your Password - FEC SaaS",
                "body_html": f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h1 style="color: #6366f1;">Password Reset Request</h1>
                        <p>Hi {first_name or 'there'},</p>
                        <p>We received a request to reset your password. Click the button below to create a new password:</p>
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{reset_url}"
                               style="background-color: #6366f1; color: white; padding: 12px 30px;
                                      text-decoration: none; border-radius: 6px; display: inline-block;">
                                Reset Password
                            </a>
                        </div>
                        <p>Or copy and paste this link into your browser:</p>
                        <p style="color: #6366f1; word-break: break-all;">{reset_url}</p>
                        <p>This link will expire in 24 hours.</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                        <p style="color: #666; font-size: 12px;">
                            If you didn't request a password reset, you can safely ignore this email.
                            Your password will remain unchanged.
                        </p>
                    </div>
                """,
                "body_text": f"Hi {first_name or 'there'}, reset your password by visiting: {reset_url}",
            }
        }

        return await self.send_notification(
            recipient_id=user_id,
            recipient_email=email,
            recipient_phone=None,
            notification_type=NotificationType.PASSWORD_RESET,
            channels=[NotificationChannel.EMAIL],
            content=content,
            priority=NotificationPriority.URGENT,
        )

    async def send_welcome_email(
        self,
        user_id: str,
        email: str,
        first_name: str,
    ) -> Dict[str, Any]:
        """
        Send welcome email after successful registration and email verification.

        This is a marketing/onboarding email with next steps for the user.
        Sent with LOW priority as it's not time-sensitive.
        """
        content = {
            "email": {
                "subject": "Welcome to FEC SaaS!",
                "body_html": f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h1 style="color: #6366f1;">Welcome Aboard!</h1>
                        <p>Hi {first_name or 'there'},</p>
                        <p>We're thrilled to have you join the FEC SaaS family!</p>
                        <p>Here's what you can do next:</p>
                        <ul>
                            <li>Complete your profile</li>
                            <li>Explore our venues</li>
                            <li>Book your first party</li>
                            <li>Join our loyalty program</li>
                        </ul>
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{settings.FRONTEND_URL}/dashboard"
                               style="background-color: #6366f1; color: white; padding: 12px 30px;
                                      text-decoration: none; border-radius: 6px; display: inline-block;">
                                Get Started
                            </a>
                        </div>
                        <p>If you have any questions, our support team is here to help!</p>
                    </div>
                """,
                "body_text": f"Hi {first_name or 'there'}, welcome to FEC SaaS! Get started at {settings.FRONTEND_URL}/dashboard",
            }
        }

        return await self.send_notification(
            recipient_id=user_id,
            recipient_email=email,
            recipient_phone=None,
            notification_type=NotificationType.WELCOME,
            channels=[NotificationChannel.EMAIL],
            content=content,
            priority=NotificationPriority.LOW,
        )

    async def send_mfa_code(
        self,
        user_id: str,
        email: Optional[str],
        phone: Optional[str],
        code: str,
        channel: NotificationChannel = NotificationChannel.EMAIL,
    ) -> Dict[str, Any]:
        """
        Send MFA verification code via email or SMS.

        Used for email/SMS-based two-factor authentication.
        Code expires in 10 minutes. Sent with URGENT priority.
        """
        if channel == NotificationChannel.EMAIL:
            content = {
                "email": {
                    "subject": "Your Verification Code - FEC SaaS",
                    "body_html": f"""
                        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                            <h1 style="color: #6366f1;">Verification Code</h1>
                            <p>Your verification code is:</p>
                            <div style="text-align: center; margin: 30px 0;">
                                <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px;
                                             background: #f3f4f6; padding: 15px 30px; border-radius: 8px;">
                                    {code}
                                </span>
                            </div>
                            <p>This code will expire in 10 minutes.</p>
                            <p style="color: #666; font-size: 12px;">
                                If you didn't request this code, please secure your account immediately.
                            </p>
                        </div>
                    """,
                    "body_text": f"Your FEC SaaS verification code is: {code}. It expires in 10 minutes.",
                }
            }
        else:
            content = {
                "sms": {
                    "message": f"Your FEC SaaS verification code is: {code}. It expires in 10 minutes.",
                }
            }

        return await self.send_notification(
            recipient_id=user_id,
            recipient_email=email,
            recipient_phone=phone,
            notification_type=NotificationType.MFA_CODE,
            channels=[channel],
            content=content,
            priority=NotificationPriority.URGENT,
        )

    async def send_login_alert(
        self,
        user_id: str,
        email: str,
        first_name: str,
        ip_address: str,
        user_agent: str,
        location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send security alert for login from new device/location.

        Helps users detect unauthorized access to their account.
        Includes IP address and device information.
        """
        content = {
            "email": {
                "subject": "New Login Detected - FEC SaaS",
                "body_html": f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h1 style="color: #6366f1;">New Login Detected</h1>
                        <p>Hi {first_name or 'there'},</p>
                        <p>We detected a new login to your account:</p>
                        <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                            <p><strong>IP Address:</strong> {ip_address}</p>
                            <p><strong>Device:</strong> {user_agent[:100]}...</p>
                            {f'<p><strong>Location:</strong> {location}</p>' if location else ''}
                        </div>
                        <p>If this was you, no action is needed.</p>
                        <p style="color: #ef4444;">
                            If you don't recognize this login, please change your password immediately.
                        </p>
                    </div>
                """,
                "body_text": f"New login detected from {ip_address}. If this wasn't you, please secure your account.",
            }
        }

        return await self.send_notification(
            recipient_id=user_id,
            recipient_email=email,
            recipient_phone=None,
            notification_type=NotificationType.LOGIN_ALERT,
            channels=[NotificationChannel.EMAIL],
            content=content,
            priority=NotificationPriority.HIGH,
        )

    async def send_password_changed(
        self,
        user_id: str,
        email: str,
        first_name: str,
    ) -> Dict[str, Any]:
        """
        Send confirmation email when password is changed.

        Security notification to alert user of password change.
        Helps detect unauthorized password changes.
        """
        content = {
            "email": {
                "subject": "Password Changed - FEC SaaS",
                "body_html": f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h1 style="color: #6366f1;">Password Changed</h1>
                        <p>Hi {first_name or 'there'},</p>
                        <p>Your password has been successfully changed.</p>
                        <p style="color: #ef4444;">
                            If you didn't make this change, please contact support immediately.
                        </p>
                    </div>
                """,
                "body_text": f"Your password has been changed. If you didn't do this, contact support immediately.",
            }
        }

        return await self.send_notification(
            recipient_id=user_id,
            recipient_email=email,
            recipient_phone=None,
            notification_type=NotificationType.PASSWORD_CHANGED,
            channels=[NotificationChannel.EMAIL],
            content=content,
            priority=NotificationPriority.HIGH,
        )


# Singleton instance - use this throughout the application
notification_client = NotificationClient()


# =============================================================================
# END OF FILE
# =============================================================================
