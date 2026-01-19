"""Authentication schemas for request/response models.

Uses Pydantic v2 with field_validator for validation.
"""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.user import UserPublic


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class SessionInfo(BaseModel):
    id: UUID
    created_at: datetime
    expires_at: datetime
    ip_address: Optional[str] = None
    device_info: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: UserPublic
    tokens: TokenPair


# Forgot password / Reset password
class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


# Email verification
class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


# Phone verification
class SendPhoneVerificationRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20)


class VerifyPhoneRequest(BaseModel):
    phone: str
    code: str = Field(..., min_length=4, max_length=10)


# Social auth
class SocialAuthRequest(BaseModel):
    token: str
    provider: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class FacebookAuthRequest(BaseModel):
    access_token: str


class AppleAuthRequest(BaseModel):
    id_token: str
    user_data: Optional[dict[str, Any]] = None


# Data export (GDPR)
class DataExportResponse(BaseModel):
    user: UserPublic
    sessions: list[dict[str, Any]]
    privacy_consents: list[dict[str, Any]]
    exported_at: datetime


# Delete account
class DeleteAccountRequest(BaseModel):
    password: str
    confirmation: str = Field(..., description="Must be 'DELETE' to confirm")

    @field_validator("confirmation")
    @classmethod
    def validate_confirmation(cls, v: str) -> str:
        if v != "DELETE":
            raise ValueError("Confirmation must be 'DELETE'")
        return v


# Message responses
class MessageResponse(BaseModel):
    message: str
    success: bool = True
