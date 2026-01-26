"""
=============================================================================
FILE: mfa.py (schemas)
PURPOSE: Pydantic schemas for MFA API request/response validation
=============================================================================

This module defines the data structures used for MFA-related API endpoints.
These schemas handle validation, serialization, and documentation.

WHAT IT DOES:
- Validates incoming MFA setup and verification requests
- Structures MFA response data
- Documents API contracts for OpenAPI/Swagger

SCHEMAS DEFINED:
- MFAStatusResponse: Current MFA configuration status
- TOTPSetupResponse: Data needed to set up TOTP (QR code, secret)
- TOTPVerifyRequest: Code verification request
- BackupCodesResponse: Generated backup codes
- MFAChallengeResponse: Pending MFA challenge info
- MFAVerifyRequest: MFA challenge verification

USAGE:
    from app.schemas.mfa import TOTPSetupResponse, TOTPVerifyRequest

    # In API endpoint
    @router.post("/mfa/totp/setup", response_model=TOTPSetupResponse)
    async def setup_totp(...):
        ...

=============================================================================
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MFAStatusResponse(BaseModel):
    """
    Response showing user's current MFA configuration.

    Returned by GET /mfa/status endpoint.
    """
    totp_enabled: bool = Field(description="Whether TOTP (authenticator app) is enabled")
    sms_enabled: bool = Field(description="Whether SMS verification is enabled")
    email_enabled: bool = Field(description="Whether email verification is enabled")
    backup_codes_remaining: int = Field(description="Number of unused backup codes")
    backup_codes_generated_at: Optional[datetime] = Field(
        description="When backup codes were last generated"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "totp_enabled": True,
                "sms_enabled": False,
                "email_enabled": True,
                "backup_codes_remaining": 8,
                "backup_codes_generated_at": "2024-01-15T10:30:00Z",
            }
        }


class TOTPSetupRequest(BaseModel):
    """Request to initiate TOTP setup."""
    pass  # No parameters needed, user context comes from JWT


class TOTPSetupResponse(BaseModel):
    """
    Response containing TOTP setup information.

    Includes everything needed to configure an authenticator app:
    - QR code image (base64 encoded)
    - Secret key (for manual entry)
    - Provisioning URI
    """
    secret: str = Field(description="Base32-encoded TOTP secret for manual entry")
    qr_code: str = Field(description="Base64-encoded PNG image of QR code")
    provisioning_uri: str = Field(description="otpauth:// URI for authenticator apps")
    backup_codes: Optional[List[str]] = Field(
        default=None,
        description="Backup codes generated with TOTP setup (only shown once)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "secret": "JBSWY3DPEHPK3PXP",
                "qr_code": "iVBORw0KGgoAAAANSUhEUgAA...",
                "provisioning_uri": "otpauth://totp/FEC%20SaaS:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=FEC%20SaaS",
                "backup_codes": ["ABCD-1234", "EFGH-5678", "..."],
            }
        }


class TOTPVerifyRequest(BaseModel):
    """
    Request to verify a TOTP code and enable TOTP.

    Used both for initial setup verification and login MFA.
    """
    code: str = Field(
        min_length=6,
        max_length=6,
        description="6-digit TOTP code from authenticator app",
    )

    class Config:
        json_schema_extra = {"example": {"code": "123456"}}


class TOTPDisableRequest(BaseModel):
    """
    Request to disable TOTP.

    Requires current password for security.
    """
    password: str = Field(description="Current account password for verification")
    code: str = Field(
        min_length=6,
        max_length=6,
        description="Current TOTP code to confirm access",
    )


class BackupCodesResponse(BaseModel):
    """
    Response containing newly generated backup codes.

    IMPORTANT: These codes are only shown once and cannot be retrieved again.
    User must save them securely.
    """
    codes: List[str] = Field(description="List of backup codes (save these securely!)")
    generated_at: datetime = Field(description="When these codes were generated")
    warning: str = Field(
        default="Save these codes securely. They will not be shown again.",
        description="Warning message for user",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "codes": [
                    "ABCD-1234",
                    "EFGH-5678",
                    "IJKL-9012",
                    "MNOP-3456",
                    "QRST-7890",
                    "UVWX-1234",
                    "YZAB-5678",
                    "CDEF-9012",
                    "GHIJ-3456",
                    "KLMN-7890",
                ],
                "generated_at": "2024-01-15T10:30:00Z",
                "warning": "Save these codes securely. They will not be shown again.",
            }
        }


class BackupCodeVerifyRequest(BaseModel):
    """Request to verify a backup code during login."""
    code: str = Field(
        min_length=8,
        max_length=10,
        description="Backup code (format: XXXX-XXXX)",
    )


class MFAChallengeResponse(BaseModel):
    """
    Response when MFA is required during login.

    Contains challenge ID and available MFA methods.
    """
    challenge_id: UUID = Field(description="ID of the MFA challenge")
    challenge_type: str = Field(description="Type of MFA required (TOTP, SMS, EMAIL)")
    expires_at: datetime = Field(description="When this challenge expires")
    available_methods: List[str] = Field(
        description="List of MFA methods available for this user"
    )
    message: str = Field(description="User-friendly message about what to do")

    class Config:
        json_schema_extra = {
            "example": {
                "challenge_id": "550e8400-e29b-41d4-a716-446655440000",
                "challenge_type": "TOTP",
                "expires_at": "2024-01-15T10:40:00Z",
                "available_methods": ["TOTP", "EMAIL", "BACKUP"],
                "message": "Enter the code from your authenticator app",
            }
        }


class MFAVerifyRequest(BaseModel):
    """
    Request to verify an MFA challenge.

    Used during login when MFA is required.
    """
    challenge_id: UUID = Field(description="ID of the MFA challenge")
    code: str = Field(
        min_length=6,
        max_length=10,
        description="Verification code (TOTP, SMS, email, or backup code)",
    )
    method: Optional[str] = Field(
        default=None,
        description="MFA method being used (TOTP, SMS, EMAIL, BACKUP)",
    )


class SMSMFASetupRequest(BaseModel):
    """Request to enable SMS-based MFA."""
    phone_number: str = Field(
        min_length=10,
        max_length=20,
        description="Phone number for SMS verification",
    )


class EmailMFASetupRequest(BaseModel):
    """Request to enable email-based MFA."""
    pass  # Uses account email, no additional input needed


class SendMFACodeRequest(BaseModel):
    """Request to send an MFA code via SMS or email."""
    method: str = Field(
        description="Method to send code (SMS or EMAIL)",
        pattern="^(SMS|EMAIL)$",
    )


class MFAMethodResponse(BaseModel):
    """Response confirming MFA method setup."""
    method: str = Field(description="The MFA method that was set up")
    enabled: bool = Field(description="Whether the method is now enabled")
    message: str = Field(description="Confirmation message")


# =============================================================================
# END OF FILE
# =============================================================================
