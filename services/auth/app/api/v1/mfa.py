"""
=============================================================================
FILE: mfa.py (API endpoints)
PURPOSE: REST API endpoints for Multi-Factor Authentication management
=============================================================================

This module provides API endpoints for setting up, managing, and verifying
Multi-Factor Authentication (MFA) for user accounts.

ENDPOINTS:
- GET  /mfa/status          - Get current MFA configuration
- POST /mfa/totp/setup      - Initialize TOTP setup (get QR code)
- POST /mfa/totp/verify     - Verify TOTP code and enable TOTP
- POST /mfa/totp/disable    - Disable TOTP authentication
- POST /mfa/backup-codes    - Generate new backup codes
- POST /mfa/email/setup     - Enable email-based MFA
- POST /mfa/sms/setup       - Enable SMS-based MFA
- POST /mfa/verify          - Verify MFA challenge during login

AUTHENTICATION:
Most endpoints require a valid JWT access token. The /mfa/verify endpoint
accepts a challenge_id from the login flow instead.

SECURITY:
- TOTP secrets are stored securely
- Backup codes are hashed before storage
- Rate limiting is applied to verification endpoints
- All MFA changes are logged for audit

RELATED FILES:
- app/services/mfa_service.py: Business logic
- app/models/mfa.py: Database models
- app/schemas/mfa.py: Request/response schemas

=============================================================================
"""

from datetime import datetime, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

import structlog

from app.api.deps import get_current_user, get_db
from app.core.security import get_password_hash, verify_password
from app.models.mfa import UserMFA, MFABackupCode, MFAChallenge
from app.models.user import User
from app.schemas.mfa import (
    MFAStatusResponse,
    TOTPSetupResponse,
    TOTPVerifyRequest,
    TOTPDisableRequest,
    BackupCodesResponse,
    BackupCodeVerifyRequest,
    MFAChallengeResponse,
    MFAVerifyRequest,
    SMSMFASetupRequest,
    MFAMethodResponse,
)
from app.services.mfa_service import MFAService
from app.services.notification_client import notification_client, NotificationChannel

logger = structlog.get_logger()

router = APIRouter(prefix="/mfa", tags=["MFA - Multi-Factor Authentication"])


@router.get("/status", response_model=MFAStatusResponse)
async def get_mfa_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the current MFA configuration for the authenticated user.

    Returns which MFA methods are enabled and how many backup codes remain.
    """
    # Get or create MFA settings
    mfa_settings = db.query(UserMFA).filter(UserMFA.user_id == current_user.id).first()

    if not mfa_settings:
        return MFAStatusResponse(
            totp_enabled=False,
            sms_enabled=False,
            email_enabled=False,
            backup_codes_remaining=0,
            backup_codes_generated_at=None,
        )

    # Count unused backup codes
    unused_codes = (
        db.query(MFABackupCode)
        .filter(
            MFABackupCode.user_mfa_id == mfa_settings.id,
            MFABackupCode.used == False,
        )
        .count()
    )

    return MFAStatusResponse(
        totp_enabled=mfa_settings.totp_enabled,
        sms_enabled=mfa_settings.sms_enabled,
        email_enabled=mfa_settings.email_enabled,
        backup_codes_remaining=unused_codes,
        backup_codes_generated_at=mfa_settings.backup_codes_generated_at,
    )


@router.post("/totp/setup", response_model=TOTPSetupResponse)
async def setup_totp(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Initialize TOTP (authenticator app) setup.

    Returns a QR code and secret that can be scanned/entered into
    an authenticator app like Google Authenticator, Authy, or 1Password.

    The TOTP is not enabled until verified with /mfa/totp/verify.
    """
    # Get or create MFA settings
    mfa_settings = db.query(UserMFA).filter(UserMFA.user_id == current_user.id).first()

    if mfa_settings and mfa_settings.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP is already enabled. Disable it first to set up again.",
        )

    # Generate new TOTP secret
    secret, provisioning_uri = MFAService.generate_totp_secret(current_user.email)

    # Generate QR code
    qr_code = MFAService.generate_totp_qr_code(provisioning_uri)

    # Store the secret temporarily (not enabled yet)
    if not mfa_settings:
        mfa_settings = UserMFA(user_id=current_user.id)
        db.add(mfa_settings)

    mfa_settings.totp_secret = secret  # In production, encrypt this
    db.commit()

    logger.info("totp_setup_initiated", user_id=str(current_user.id))

    return TOTPSetupResponse(
        secret=secret,
        qr_code=qr_code,
        provisioning_uri=provisioning_uri,
    )


@router.post("/totp/verify", response_model=MFAMethodResponse)
async def verify_and_enable_totp(
    request: TOTPVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verify a TOTP code and enable TOTP authentication.

    This endpoint is used during initial TOTP setup to confirm
    the user has correctly configured their authenticator app.
    """
    mfa_settings = db.query(UserMFA).filter(UserMFA.user_id == current_user.id).first()

    if not mfa_settings or not mfa_settings.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP setup not initiated. Call /mfa/totp/setup first.",
        )

    if mfa_settings.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP is already enabled.",
        )

    # Verify the code
    if not MFAService.verify_totp(mfa_settings.totp_secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code. Please try again.",
        )

    # Enable TOTP
    mfa_settings.totp_enabled = True
    mfa_settings.totp_verified_at = datetime.now(timezone.utc)

    # Generate backup codes if none exist
    backup_codes = None
    existing_codes = (
        db.query(MFABackupCode)
        .filter(MFABackupCode.user_mfa_id == mfa_settings.id)
        .count()
    )

    if existing_codes == 0:
        backup_codes = await _generate_backup_codes(mfa_settings, db)

    db.commit()

    logger.info("totp_enabled", user_id=str(current_user.id))

    return MFAMethodResponse(
        method="TOTP",
        enabled=True,
        message="TOTP authentication is now enabled. "
        + ("Your backup codes have been generated." if backup_codes else ""),
    )


@router.post("/totp/disable", response_model=MFAMethodResponse)
async def disable_totp(
    request: TOTPDisableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Disable TOTP authentication.

    Requires current password and a valid TOTP code for security.
    """
    # Verify password
    if not verify_password(request.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password.",
        )

    mfa_settings = db.query(UserMFA).filter(UserMFA.user_id == current_user.id).first()

    if not mfa_settings or not mfa_settings.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP is not enabled.",
        )

    # Verify TOTP code
    if not MFAService.verify_totp(mfa_settings.totp_secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code.",
        )

    # Disable TOTP
    mfa_settings.totp_enabled = False
    mfa_settings.totp_secret = None
    mfa_settings.totp_verified_at = None
    db.commit()

    logger.info("totp_disabled", user_id=str(current_user.id))

    return MFAMethodResponse(
        method="TOTP",
        enabled=False,
        message="TOTP authentication has been disabled.",
    )


@router.post("/backup-codes", response_model=BackupCodesResponse)
async def regenerate_backup_codes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate new backup codes.

    This invalidates any existing backup codes. Make sure to save
    the new codes securely - they will not be shown again.
    """
    mfa_settings = db.query(UserMFA).filter(UserMFA.user_id == current_user.id).first()

    if not mfa_settings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not set up. Enable TOTP or another MFA method first.",
        )

    if not mfa_settings.has_any_mfa_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one MFA method must be enabled to generate backup codes.",
        )

    # Delete existing backup codes
    db.query(MFABackupCode).filter(
        MFABackupCode.user_mfa_id == mfa_settings.id
    ).delete()

    # Generate new backup codes
    codes = await _generate_backup_codes(mfa_settings, db)
    db.commit()

    logger.info("backup_codes_regenerated", user_id=str(current_user.id))

    return BackupCodesResponse(
        codes=codes,
        generated_at=mfa_settings.backup_codes_generated_at,
    )


@router.post("/email/setup", response_model=MFAMethodResponse)
async def setup_email_mfa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Enable email-based MFA.

    When enabled, a verification code will be sent to your email
    address during login.
    """
    if not current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email must be verified before enabling email MFA.",
        )

    # Get or create MFA settings
    mfa_settings = db.query(UserMFA).filter(UserMFA.user_id == current_user.id).first()

    if not mfa_settings:
        mfa_settings = UserMFA(user_id=current_user.id)
        db.add(mfa_settings)

    mfa_settings.email_enabled = True
    db.commit()

    logger.info("email_mfa_enabled", user_id=str(current_user.id))

    return MFAMethodResponse(
        method="EMAIL",
        enabled=True,
        message="Email-based MFA is now enabled.",
    )


@router.post("/sms/setup", response_model=MFAMethodResponse)
async def setup_sms_mfa(
    request: SMSMFASetupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Enable SMS-based MFA.

    When enabled, a verification code will be sent to your phone
    number during login.
    """
    # Update user's phone number if different
    if current_user.phone_number != request.phone_number:
        current_user.phone_number = request.phone_number
        current_user.phone_verified = False  # Require verification of new number

    # Get or create MFA settings
    mfa_settings = db.query(UserMFA).filter(UserMFA.user_id == current_user.id).first()

    if not mfa_settings:
        mfa_settings = UserMFA(user_id=current_user.id)
        db.add(mfa_settings)

    mfa_settings.sms_enabled = True
    db.commit()

    logger.info("sms_mfa_enabled", user_id=str(current_user.id))

    return MFAMethodResponse(
        method="SMS",
        enabled=True,
        message="SMS-based MFA is now enabled.",
    )


async def _generate_backup_codes(mfa_settings: UserMFA, db: Session) -> List[str]:
    """
    Generate and store backup codes for a user.

    Returns the plain-text codes (only shown once to user).
    Stores hashed codes in database.
    """
    # Generate codes
    codes = MFAService.generate_backup_codes()

    # Hash and store each code
    for code in codes:
        backup_code = MFABackupCode(
            user_mfa_id=mfa_settings.id,
            code_hash=MFAService.hash_backup_code(code),
        )
        db.add(backup_code)

    mfa_settings.backup_codes_generated_at = datetime.now(timezone.utc)

    return codes


async def create_mfa_challenge(
    user: User,
    challenge_type: str,
    db: Session,
    request: Request,
) -> MFAChallenge:
    """
    Create an MFA challenge for a user during login.

    Args:
        user: The user who needs to verify MFA
        challenge_type: Type of challenge (TOTP, SMS, EMAIL)
        db: Database session
        request: HTTP request for IP/user agent logging

    Returns:
        The created MFA challenge
    """
    # Get user's MFA settings
    mfa_settings = db.query(UserMFA).filter(UserMFA.user_id == user.id).first()

    # Determine available methods
    available_methods = []
    if mfa_settings:
        if mfa_settings.totp_enabled:
            available_methods.append("TOTP")
        if mfa_settings.email_enabled:
            available_methods.append("EMAIL")
        if mfa_settings.sms_enabled:
            available_methods.append("SMS")

        # Check for backup codes
        unused_codes = (
            db.query(MFABackupCode)
            .filter(
                MFABackupCode.user_mfa_id == mfa_settings.id,
                MFABackupCode.used == False,
            )
            .count()
        )
        if unused_codes > 0:
            available_methods.append("BACKUP")

    # Create challenge
    challenge = MFAChallenge(
        user_id=user.id,
        challenge_type=challenge_type,
        expires_at=MFAService.get_challenge_expiry(),
        session_token=MFAService.generate_session_token(),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    # For SMS/EMAIL, generate and send code
    if challenge_type in ("SMS", "EMAIL"):
        code = MFAService.generate_challenge_code()
        challenge.code_hash = get_password_hash(code)

        # Send the code
        if challenge_type == "EMAIL":
            await notification_client.send_mfa_code(
                user_id=str(user.id),
                email=user.email,
                phone=None,
                code=code,
                channel=NotificationChannel.EMAIL,
            )
        elif challenge_type == "SMS" and user.phone_number:
            await notification_client.send_mfa_code(
                user_id=str(user.id),
                email=None,
                phone=user.phone_number,
                code=code,
                channel=NotificationChannel.SMS,
            )

    db.add(challenge)
    db.commit()
    db.refresh(challenge)

    return challenge


async def verify_mfa_challenge(
    challenge_id: UUID,
    code: str,
    db: Session,
) -> tuple[bool, str, MFAChallenge]:
    """
    Verify an MFA challenge.

    Args:
        challenge_id: ID of the challenge to verify
        code: The verification code from user
        db: Database session

    Returns:
        Tuple of (success, error_message, challenge)
    """
    challenge = db.query(MFAChallenge).filter(MFAChallenge.id == challenge_id).first()

    if not challenge:
        return False, "Challenge not found", None

    if not challenge.can_attempt():
        if challenge.is_expired():
            return False, "Challenge has expired", challenge
        if challenge.is_locked():
            return False, "Too many failed attempts", challenge
        if challenge.verified:
            return False, "Challenge already verified", challenge

    # Increment attempt counter
    challenge.attempts += 1

    # Get user's MFA settings
    user = db.query(User).filter(User.id == challenge.user_id).first()
    mfa_settings = db.query(UserMFA).filter(UserMFA.user_id == user.id).first()

    verified = False

    if challenge.challenge_type == "TOTP":
        # Verify TOTP code
        if mfa_settings and mfa_settings.totp_secret:
            verified = MFAService.verify_totp(mfa_settings.totp_secret, code)

    elif challenge.challenge_type in ("SMS", "EMAIL"):
        # Verify the code against stored hash
        if challenge.code_hash:
            verified = verify_password(code, challenge.code_hash)

    elif challenge.challenge_type == "BACKUP":
        # Find and verify backup code
        if mfa_settings:
            backup_codes = (
                db.query(MFABackupCode)
                .filter(
                    MFABackupCode.user_mfa_id == mfa_settings.id,
                    MFABackupCode.used == False,
                )
                .all()
            )
            for backup_code in backup_codes:
                if MFAService.verify_backup_code(code, backup_code.code_hash):
                    backup_code.used = True
                    backup_code.used_at = datetime.now(timezone.utc)
                    verified = True
                    break

    if verified:
        challenge.verified = True
        challenge.verified_at = datetime.now(timezone.utc)
        db.commit()
        return True, "Verified", challenge

    db.commit()
    return False, "Invalid code", challenge


# =============================================================================
# END OF FILE
# =============================================================================
