"""
=============================================================================
FILE: models/base.py
PURPOSE: SQLAlchemy base model for Membership Service
=============================================================================
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""

    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )


class UUIDMixin:
    """Mixin for UUID primary key."""

    id: Mapped[Any] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
