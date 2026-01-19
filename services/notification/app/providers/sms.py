"""SMS provider using Twilio."""
import structlog
from typing import Optional, Dict, Any
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from app.core.config import get_settings

settings = get_settings()
logger = structlog.get_logger()


class SmsProvider:
    """Twilio SMS provider for notification service."""

    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_FROM_NUMBER
        self._client: Optional[Client] = None

    @property
    def client(self) -> Optional[Client]:
        """Lazy-load Twilio client."""
        if self._client is None and self.account_sid and self.auth_token:
            self._client = Client(self.account_sid, self.auth_token)
        return self._client

    def is_configured(self) -> bool:
        """Check if SMS provider is properly configured."""
        return all([
            self.account_sid,
            self.auth_token,
            self.from_number,
        ])

    def _format_phone_number(self, phone: str) -> str:
        """
        Format phone number to E.164 format.

        Args:
            phone: Phone number in various formats

        Returns:
            Phone number in E.164 format (+1XXXXXXXXXX)
        """
        # Remove all non-digit characters
        digits = "".join(c for c in phone if c.isdigit())

        # Add US country code if not present
        if len(digits) == 10:
            digits = "1" + digits

        # Add + prefix
        if not digits.startswith("+"):
            digits = "+" + digits

        return digits

    async def send_sms(
        self,
        to_phone: str,
        message: str,
        from_number: Optional[str] = None,
        tracking_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an SMS via Twilio.

        Args:
            to_phone: Recipient phone number
            message: SMS message content (max 160 chars for single SMS)
            from_number: Sender phone number (defaults to configured from_number)
            tracking_id: Internal tracking ID for logging

        Returns:
            Dict with success, message_sid, status, and error
        """
        if not self.is_configured():
            logger.warning("sms_not_configured", tracking_id=tracking_id)
            return {
                "success": False,
                "error": "SMS provider not configured",
                "message_sid": None,
                "status": None,
            }

        try:
            formatted_to = self._format_phone_number(to_phone)
            formatted_from = from_number or self.from_number

            twilio_message = self.client.messages.create(
                body=message,
                from_=formatted_from,
                to=formatted_to,
            )

            logger.info(
                "sms_sent",
                to=formatted_to,
                message_sid=twilio_message.sid,
                status=twilio_message.status,
                tracking_id=tracking_id,
            )

            return {
                "success": True,
                "message_sid": twilio_message.sid,
                "status": twilio_message.status,
                "error": None,
            }

        except TwilioRestException as e:
            logger.error(
                "sms_send_failed",
                to=to_phone,
                error_code=e.code,
                error_message=e.msg,
                tracking_id=tracking_id,
            )
            return {
                "success": False,
                "error": f"Twilio error {e.code}: {e.msg}",
                "message_sid": None,
                "status": "failed",
            }

        except Exception as e:
            logger.error(
                "sms_send_failed",
                to=to_phone,
                error=str(e),
                tracking_id=tracking_id,
            )
            return {
                "success": False,
                "error": str(e),
                "message_sid": None,
                "status": "failed",
            }

    async def get_message_status(self, message_sid: str) -> Dict[str, Any]:
        """
        Get the status of a sent SMS message.

        Args:
            message_sid: Twilio message SID

        Returns:
            Dict with status, error_code, error_message
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "SMS provider not configured",
            }

        try:
            message = self.client.messages(message_sid).fetch()

            return {
                "success": True,
                "status": message.status,
                "error_code": message.error_code,
                "error_message": message.error_message,
                "date_sent": message.date_sent,
                "date_updated": message.date_updated,
            }

        except TwilioRestException as e:
            return {
                "success": False,
                "error": f"Twilio error {e.code}: {e.msg}",
            }


# Singleton instance
sms_provider = SmsProvider()
