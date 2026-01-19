"""Notification template management API endpoints.

CRUD operations for notification templates that can be customized per venue.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.notification import NotificationTemplate

router = APIRouter(prefix="/templates", tags=["templates"])


# =============================================================================
# Schemas
# =============================================================================


class TemplateContent(BaseModel):
    """Content for different channels."""
    email: Optional[Dict[str, str]] = None  # {subject, body_html, body_text}
    sms: Optional[Dict[str, str]] = None  # {message}
    push: Optional[Dict[str, str]] = None  # {title, body, image_url}
    in_app: Optional[Dict[str, str]] = None  # {title, message, action_url}


class TemplateCreate(BaseModel):
    venue_id: Optional[UUID] = None
    template_name: str
    notification_type: str
    channels: List[str]
    priority: str = "MEDIUM"
    content: TemplateContent
    variables: Optional[List[str]] = None


class TemplateUpdate(BaseModel):
    template_name: Optional[str] = None
    channels: Optional[List[str]] = None
    priority: Optional[str] = None
    content: Optional[TemplateContent] = None
    variables: Optional[List[str]] = None
    is_active: Optional[bool] = None


class TemplateResponse(BaseModel):
    id: UUID
    venue_id: Optional[UUID]
    template_name: str
    notification_type: str
    channels: List[str]
    priority: str
    content: Dict[str, Any]
    variables: Optional[List[str]]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: TemplateCreate,
    db: Session = Depends(get_db),
):
    """Create a new notification template."""
    # Check for duplicate
    existing = db.query(NotificationTemplate).filter(
        NotificationTemplate.venue_id == payload.venue_id,
        NotificationTemplate.notification_type == payload.notification_type,
        NotificationTemplate.template_name == payload.template_name,
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template with this name already exists for this venue and type",
        )

    template = NotificationTemplate(
        venue_id=payload.venue_id,
        template_name=payload.template_name,
        notification_type=payload.notification_type,
        channels=payload.channels,
        priority=payload.priority,
        content=payload.content.model_dump(exclude_none=True),
        variables=payload.variables,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    return template


@router.get("", response_model=List[TemplateResponse])
def list_templates(
    venue_id: Optional[UUID] = Query(None, description="Filter by venue"),
    notification_type: Optional[str] = Query(None, description="Filter by notification type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
):
    """List all notification templates with optional filters."""
    query = db.query(NotificationTemplate)

    if venue_id is not None:
        # Include global templates (venue_id=NULL) and venue-specific
        query = query.filter(
            (NotificationTemplate.venue_id == venue_id) |
            (NotificationTemplate.venue_id.is_(None))
        )

    if notification_type:
        query = query.filter(NotificationTemplate.notification_type == notification_type)

    if is_active is not None:
        query = query.filter(NotificationTemplate.is_active == is_active)

    templates = query.order_by(NotificationTemplate.created_at.desc()).all()
    return templates


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(
    template_id: UUID,
    db: Session = Depends(get_db),
):
    """Get a specific notification template."""
    template = db.query(NotificationTemplate).filter(
        NotificationTemplate.id == template_id
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return template


@router.put("/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: UUID,
    payload: TemplateUpdate,
    db: Session = Depends(get_db),
):
    """Update a notification template."""
    template = db.query(NotificationTemplate).filter(
        NotificationTemplate.id == template_id
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    if "content" in update_data and update_data["content"]:
        update_data["content"] = update_data["content"].model_dump(exclude_none=True) if hasattr(update_data["content"], "model_dump") else update_data["content"]

    for field, value in update_data.items():
        setattr(template, field, value)

    template.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(template)

    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete a notification template."""
    template = db.query(NotificationTemplate).filter(
        NotificationTemplate.id == template_id
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    db.delete(template)
    db.commit()
    return None


@router.post("/{template_id}/preview")
def preview_template(
    template_id: UUID,
    variables: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """Preview a template with sample variables."""
    template = db.query(NotificationTemplate).filter(
        NotificationTemplate.id == template_id
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    from jinja2 import Template as JinjaTemplate

    rendered = {}
    content = template.content

    for channel, channel_content in content.items():
        if channel_content:
            rendered[channel] = {}
            for key, value in channel_content.items():
                if isinstance(value, str):
                    try:
                        jinja_template = JinjaTemplate(value)
                        rendered[channel][key] = jinja_template.render(**variables)
                    except Exception as e:
                        rendered[channel][key] = f"Error rendering: {str(e)}"
                else:
                    rendered[channel][key] = value

    return {
        "template_id": str(template_id),
        "template_name": template.template_name,
        "variables_used": variables,
        "rendered_content": rendered,
    }
