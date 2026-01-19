"""Email provider using SendGrid."""
import structlog
from typing import Optional, Dict, Any, List
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail,
    Email,
    To,
    Content,
    Attachment,
    FileContent,
    FileName,
    FileType,
    Disposition,
)

from app.core.config import get_settings

settings = get_settings()
logger = structlog.get_logger()


class EmailProvider:
    """SendGrid email provider for notification service."""

    def __init__(self):
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.DEFAULT_FROM_EMAIL
        self.from_name = settings.DEFAULT_FROM_NAME
        self._client: Optional[SendGridAPIClient] = None

    @property
    def client(self) -> Optional[SendGridAPIClient]:
        """Lazy-load SendGrid client."""
        if self._client is None and self.api_key:
            self._client = SendGridAPIClient(api_key=self.api_key)
        return self._client

    def is_configured(self) -> bool:
        """Check if email provider is properly configured."""
        return self.api_key is not None

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        tracking_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an email via SendGrid.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body_html: HTML body content
            body_text: Plain text body (optional, auto-generated if not provided)
            from_email: Sender email (defaults to configured from_email)
            from_name: Sender name (defaults to configured from_name)
            reply_to: Reply-to email address
            attachments: List of attachment dicts with keys: content, filename, type
            tracking_id: Internal tracking ID for logging

        Returns:
            Dict with status_code, message_id, and success boolean
        """
        if not self.is_configured():
            logger.warning("email_not_configured", tracking_id=tracking_id)
            return {
                "success": False,
                "error": "Email provider not configured",
                "message_id": None,
            }

        try:
            message = Mail(
                from_email=Email(
                    email=from_email or self.from_email,
                    name=from_name or self.from_name,
                ),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", body_html),
            )

            if body_text:
                message.add_content(Content("text/plain", body_text))

            if reply_to:
                message.reply_to = Email(reply_to)

            if attachments:
                for att in attachments:
                    attachment = Attachment(
                        FileContent(att["content"]),
                        FileName(att["filename"]),
                        FileType(att.get("type", "application/octet-stream")),
                        Disposition("attachment"),
                    )
                    message.add_attachment(attachment)

            # Add custom tracking header
            if tracking_id:
                message.custom_arg = {"tracking_id": tracking_id}

            response = self.client.send(message)

            # Extract message ID from headers
            message_id = response.headers.get("X-Message-Id")

            logger.info(
                "email_sent",
                to=to_email,
                subject=subject,
                status_code=response.status_code,
                message_id=message_id,
                tracking_id=tracking_id,
            )

            return {
                "success": response.status_code in (200, 201, 202),
                "status_code": response.status_code,
                "message_id": message_id,
                "error": None,
            }

        except Exception as e:
            logger.error(
                "email_send_failed",
                to=to_email,
                subject=subject,
                error=str(e),
                tracking_id=tracking_id,
            )
            return {
                "success": False,
                "error": str(e),
                "message_id": None,
            }

    async def send_template_email(
        self,
        to_email: str,
        template_id: str,
        dynamic_data: Dict[str, Any],
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        tracking_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an email using a SendGrid dynamic template.

        Args:
            to_email: Recipient email address
            template_id: SendGrid template ID
            dynamic_data: Template variables
            from_email: Sender email (defaults to configured from_email)
            from_name: Sender name (defaults to configured from_name)
            tracking_id: Internal tracking ID for logging

        Returns:
            Dict with status_code, message_id, and success boolean
        """
        if not self.is_configured():
            logger.warning("email_not_configured", tracking_id=tracking_id)
            return {
                "success": False,
                "error": "Email provider not configured",
                "message_id": None,
            }

        try:
            message = Mail(
                from_email=Email(
                    email=from_email or self.from_email,
                    name=from_name or self.from_name,
                ),
                to_emails=To(to_email),
            )
            message.template_id = template_id
            message.dynamic_template_data = dynamic_data

            response = self.client.send(message)
            message_id = response.headers.get("X-Message-Id")

            logger.info(
                "template_email_sent",
                to=to_email,
                template_id=template_id,
                status_code=response.status_code,
                message_id=message_id,
                tracking_id=tracking_id,
            )

            return {
                "success": response.status_code in (200, 201, 202),
                "status_code": response.status_code,
                "message_id": message_id,
                "error": None,
            }

        except Exception as e:
            logger.error(
                "template_email_send_failed",
                to=to_email,
                template_id=template_id,
                error=str(e),
                tracking_id=tracking_id,
            )
            return {
                "success": False,
                "error": str(e),
                "message_id": None,
            }


# Singleton instance
email_provider = EmailProvider()
