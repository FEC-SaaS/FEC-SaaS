"""Template rendering service using Jinja2."""
import os
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Get template directory path
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

# Initialize Jinja2 environment
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


class TemplateService:
    """Service for rendering notification templates."""

    @staticmethod
    def render_email(template_name: str, context: Dict[str, Any]) -> str:
        """
        Render an email template with context.

        Args:
            template_name: Name of template file (e.g., 'welcome.html')
            context: Dictionary of variables to pass to template

        Returns:
            Rendered HTML string
        """
        template_path = f"email/{template_name}"
        template = env.get_template(template_path)
        return template.render(**context)

    @staticmethod
    def render_sms(template_name: str, context: Dict[str, Any]) -> str:
        """
        Render an SMS template with context.

        Args:
            template_name: Name of template file (e.g., 'reservation_reminder.txt')
            context: Dictionary of variables to pass to template

        Returns:
            Rendered text string (max 160 chars for single SMS)
        """
        template_path = f"sms/{template_name}"
        template = env.get_template(template_path)
        rendered = template.render(**context)

        # Truncate to SMS length if needed
        if len(rendered) > 160:
            rendered = rendered[:157] + "..."

        return rendered

    @staticmethod
    def get_available_templates() -> Dict[str, list]:
        """Get list of available templates by type."""
        templates = {"email": [], "sms": []}

        email_dir = os.path.join(TEMPLATE_DIR, "email")
        sms_dir = os.path.join(TEMPLATE_DIR, "sms")

        if os.path.exists(email_dir):
            templates["email"] = [
                f for f in os.listdir(email_dir)
                if f.endswith(".html") and f != "base.html"
            ]

        if os.path.exists(sms_dir):
            templates["sms"] = [
                f for f in os.listdir(sms_dir)
                if f.endswith(".txt")
            ]

        return templates


# Singleton instance
template_service = TemplateService()
