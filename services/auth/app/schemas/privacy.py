"""Privacy consent schemas for GDPR compliance.

Uses Pydantic v2 syntax.
"""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class PrivacyConsentBase(BaseModel):
    id: UUID
    consent_type: str
    granted: bool
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    consent_metadata: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}


class PrivacyConsentUpdate(BaseModel):
    consent_type: str
    granted: bool
    consent_metadata: Optional[dict[str, Any]] = None
