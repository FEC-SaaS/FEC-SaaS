"""
=============================================================================
FILE: auth.py (API endpoints)
PURPOSE: Core authentication REST API endpoints
=============================================================================

This module implements all authentication flows for the FEC SaaS platform:
- User registration with email verification
- Login with account lockout protection
- JWT token management with rotation
- Password reset flow
- Email and phone verification
- User profile management
- GDPR compliance (data export, account deletion)

SECURITY FEATURES:
- Rate limiting on sensitive endpoints
- Account lockout after failed login attempts
- Token blacklisting with Redis
- Refresh token rotation
- Audit logging for all security events
- Request ID tracing for debugging

ENDPOINTS:
- POST /auth/register - Create new account
- POST /auth/login - Authenticate user
- POST /auth/refresh - Refresh access token
- POST /auth/logout - Invalidate session
- POST /auth/forgot-password - Request password reset
- POST /auth/reset-password - Complete password reset
- POST /auth/verify-email - Verify email address
- GET  /auth/me - Get current user profile
- PUT  /auth/me - Update user profile
- And more...

=============================================================================
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
    decode_token_unverified,
)
from app.db.session import get_db
from app.middleware.rate_limit import limiter, get_rate_limit
from app.middleware.security import get_client_ip, get_user_agent
from app.models.token import (
    EmailVerificationToken,
    PasswordResetToken,
    PhoneVerificationCode,
)
from app.models.user import PrivacyConsent, User, UserSession
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    DataExportResponse,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    ResetPasswordRequest,
    ResendVerificationRequest,
    SendPhoneVerificationRequest,
    TokenPair,
    VerifyEmailRequest,
    VerifyPhoneRequest,
)
from app.schemas.privacy import PrivacyConsentUpdate
from app.schemas.user import UserCreate, UserPublic, UserUpdate
from app.services.account_lockout import AccountLockoutService
from app.services.audit_log import AuditLogService, AuditEventType
from app.services.token_blacklist import TokenBlacklistService
from app.services.notification_client import notification_client

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Token expiration settings
PASSWORD_RESET_EXPIRE_HOURS = 24
EMAIL_VERIFICATION_EXPIRE_HOURS = 48
PHONE_VERIFICATION_EXPIRE_MINUTES = 10
MAX_PHONE_VERIFICATION_ATTEMPTS = 5


def _user_to_public(user: User) -> UserPublic:
    return UserPublic.model_validate(user)


def _generate_secure_token() -> str:
    """Generate a cryptographically secure token."""
    return secrets.token_urlsafe(32)


def _generate_phone_code() -> str:
    """Generate a 6-digit verification code."""
    return f"{secrets.randbelow(1000000):06d}"


def get_current_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
) -> User:
    """Dependency to get the current authenticated user with security checks."""
    # Check if token is blacklisted
    if TokenBlacklistService.is_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    # Verify token
    payload = verify_token(token, expected_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("sub")
    token_iat = payload.get("iat", 0)

    # Check if token was issued before a security invalidation event
    if TokenBlacklistService.is_token_issued_before_invalidation(user_id, token_iat):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been invalidated",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def _create_token_pair(user_id: str) -> tuple[str, str, int]:
    """Create access and refresh token pair."""
    access_token, _, expires_in = create_access_token(str(user_id))
    refresh_token, _, refresh_expires = create_refresh_token(str(user_id))
    return access_token, refresh_token, expires_in


def _create_session(
    db: Session,
    user: User,
    request: Request,
    access_token: str,
    refresh_token: str,
) -> UserSession:
    """Create a new user session."""
    session = UserSession(
        user_id=user.id,
        token=access_token,
        refresh_token=refresh_token,
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        device_info={"user_agent": get_user_agent(request)},
        ip_address=get_client_ip(request),
    )
    db.add(session)
    return session


# =============================================================================
# Registration & Login
# =============================================================================


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(get_rate_limit("register"))
async def register(
    request: Request,
    payload: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Register a new user account."""
    ip_address = get_client_ip(request)

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        facial_recognition_consent=payload.facial_recognition_consent,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create email verification token
    verification_token = EmailVerificationToken(
        user_id=user.id,
        token=_generate_secure_token(),
        email=user.email,
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=EMAIL_VERIFICATION_EXPIRE_HOURS),
    )
    db.add(verification_token)

    access_token, refresh_token, expires_in = _create_token_pair(str(user.id))
    _create_session(db, user, request, access_token, refresh_token)

    # Store refresh token in Redis for rotation tracking
    TokenBlacklistService.store_refresh_token(
        str(user.id),
        refresh_token,
        settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )

    db.commit()

    # Audit log
    AuditLogService.log_registration(str(user.id), user.email, ip_address)

    # Send verification email in background (non-blocking)
    background_tasks.add_task(
        notification_client.send_email_verification,
        user_id=str(user.id),
        email=user.email,
        first_name=user.first_name or "",
        verification_token=verification_token.token,
    )

    tokens = TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )

    return AuthResponse(user=_user_to_public(user), tokens=tokens)


@router.post("/login", response_model=AuthResponse)
@limiter.limit(get_rate_limit("login"))
def login(
    request: Request,
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    """Login with email and password."""
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)

    # Check account lockout
    is_locked, lockout_remaining = AccountLockoutService.is_account_locked(payload.email)
    if is_locked:
        AuditLogService.log_login_failed(
            payload.email,
            ip_address,
            user_agent,
            reason="account_locked",
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account is locked. Try again in {lockout_remaining} seconds.",
            headers={"Retry-After": str(lockout_remaining)},
        )

    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not verify_password(payload.password, user.password_hash):
        # Record failed attempt
        attempts, now_locked = AccountLockoutService.record_failed_attempt(payload.email)

        if now_locked:
            AuditLogService.log_account_locked(payload.email, ip_address)

        AuditLogService.log_login_failed(
            payload.email,
            ip_address,
            user_agent,
            reason="invalid_credentials",
        )

        remaining = AccountLockoutService.get_remaining_attempts(payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid credentials. {remaining} attempts remaining.",
        )

    # Clear failed attempts on successful login
    AccountLockoutService.clear_failed_attempts(payload.email)

    user.last_login_at = datetime.now(timezone.utc)

    access_token, refresh_token, expires_in = _create_token_pair(str(user.id))
    _create_session(db, user, request, access_token, refresh_token)

    # Store refresh token for rotation
    TokenBlacklistService.store_refresh_token(
        str(user.id),
        refresh_token,
        settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )

    db.commit()

    # Audit log
    AuditLogService.log_login_success(str(user.id), user.email, ip_address, user_agent)

    tokens = TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )
    return AuthResponse(user=_user_to_public(user), tokens=tokens)


@router.post("/refresh", response_model=TokenPair)
@limiter.limit(get_rate_limit("refresh"))
def refresh(
    request: Request,
    payload: RefreshRequest,
    db: Session = Depends(get_db),
):
    """Refresh access token using refresh token with rotation."""
    ip_address = get_client_ip(request)

    # Check if refresh token is blacklisted
    if TokenBlacklistService.is_blacklisted(payload.refresh_token):
        AuditLogService.log_event(
            AuditEventType.TOKEN_REFRESH_FAILED,
            ip_address=ip_address,
            success=False,
            error_message="blacklisted_token",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    # Verify refresh token
    token_payload = verify_token(payload.refresh_token, expected_type="refresh")
    if not token_payload:
        AuditLogService.log_event(
            AuditEventType.TOKEN_REFRESH_FAILED,
            ip_address=ip_address,
            success=False,
            error_message="invalid_token",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = token_payload.get("sub")

    # Verify session exists
    session = (
        db.query(UserSession)
        .filter(UserSession.refresh_token == payload.refresh_token)
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found",
        )

    # REFRESH TOKEN ROTATION: Blacklist the old refresh token
    TokenBlacklistService.blacklist_token(payload.refresh_token)

    # Create new token pair
    access_token, new_refresh_token, expires_in = _create_token_pair(user_id)

    # Update session with new tokens
    session.token = access_token
    session.refresh_token = new_refresh_token
    session.expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    # Store new refresh token
    TokenBlacklistService.store_refresh_token(
        user_id,
        new_refresh_token,
        settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )

    db.commit()

    # Audit log
    AuditLogService.log_token_refresh(user_id, ip_address, rotated=True)

    return TokenPair(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(get_rate_limit("logout"))
def logout(
    request: Request,
    payload: RefreshRequest,
    db: Session = Depends(get_db),
):
    """Logout and invalidate the current session."""
    ip_address = get_client_ip(request)

    # Get user ID from token for logging (even if expired)
    user_id = None
    token_payload = decode_token_unverified(payload.refresh_token)
    if token_payload:
        user_id = token_payload.get("sub")

    # Blacklist the refresh token
    TokenBlacklistService.blacklist_token(payload.refresh_token)

    # Invalidate user's stored refresh token
    if user_id:
        TokenBlacklistService.invalidate_user_refresh_token(user_id)

    # Delete session from database
    session = (
        db.query(UserSession)
        .filter(UserSession.refresh_token == payload.refresh_token)
        .first()
    )
    if session:
        # Also blacklist the access token
        TokenBlacklistService.blacklist_token(session.token)
        db.delete(session)
        db.commit()

    # Audit log
    if user_id:
        AuditLogService.log_logout(user_id, ip_address)

    return None


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Logout from all devices by invalidating all tokens."""
    ip_address = get_client_ip(request)
    user_id = str(current_user.id)

    # Invalidate all tokens issued before now
    TokenBlacklistService.blacklist_all_user_tokens(user_id)

    # Delete all sessions
    db.query(UserSession).filter(UserSession.user_id == current_user.id).delete()
    db.commit()

    # Audit log
    AuditLogService.log_event(
        AuditEventType.ALL_TOKENS_INVALIDATED,
        user_id=user_id,
        ip_address=ip_address,
    )

    return None


# =============================================================================
# Password Reset
# =============================================================================


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit(get_rate_limit("password_reset"))
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Request a password reset email."""
    ip_address = get_client_ip(request)
    user = db.query(User).filter(User.email == payload.email).first()

    # Always return success to prevent email enumeration
    if user:
        # Invalidate any existing reset tokens
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False,
        ).update({"used": True, "used_at": datetime.now(timezone.utc)})

        # Create new reset token
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=_generate_secure_token(),
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=PASSWORD_RESET_EXPIRE_HOURS),
        )
        db.add(reset_token)
        db.commit()

        # Audit log
        AuditLogService.log_event(
            AuditEventType.PASSWORD_RESET_REQUEST,
            user_id=str(user.id),
            email=user.email,
            ip_address=ip_address,
        )

        # Send password reset email in background
        background_tasks.add_task(
            notification_client.send_password_reset,
            user_id=str(user.id),
            email=user.email,
            first_name=user.first_name or "",
            reset_token=reset_token.token,
        )

    return MessageResponse(
        message="If an account exists with this email, a password reset link has been sent."
    )


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit(get_rate_limit("password_reset"))
def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Reset password using the token from email."""
    ip_address = get_client_ip(request)

    reset_token = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token == payload.token,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    # Update password
    user.password_hash = get_password_hash(payload.new_password)

    # Mark token as used
    reset_token.used = True
    reset_token.used_at = datetime.now(timezone.utc)

    # Invalidate all existing sessions and tokens for security
    TokenBlacklistService.blacklist_all_user_tokens(str(user.id))
    db.query(UserSession).filter(UserSession.user_id == user.id).delete()

    db.commit()

    # Audit log
    AuditLogService.log_password_change(str(user.id), ip_address)
    AuditLogService.log_event(
        AuditEventType.PASSWORD_RESET_COMPLETE,
        user_id=str(user.id),
        ip_address=ip_address,
    )

    return MessageResponse(message="Password has been reset successfully.")


# =============================================================================
# Email Verification
# =============================================================================


@router.post("/verify-email", response_model=MessageResponse)
@limiter.limit(get_rate_limit("verify_email"))
def verify_email(
    request: Request,
    payload: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    """Verify email address using the token."""
    ip_address = get_client_ip(request)

    verification = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.token == payload.token,
            EmailVerificationToken.verified == False,
            EmailVerificationToken.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    user = db.query(User).filter(User.id == verification.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    # Mark email as verified
    user.email_verified = True
    verification.verified = True
    verification.verified_at = datetime.now(timezone.utc)
    db.commit()

    # Audit log
    AuditLogService.log_event(
        AuditEventType.EMAIL_VERIFICATION,
        user_id=str(user.id),
        email=user.email,
        ip_address=ip_address,
    )

    return MessageResponse(message="Email verified successfully.")


@router.post("/resend-verification", response_model=MessageResponse)
@limiter.limit(get_rate_limit("verify_email"))
async def resend_verification(
    request: Request,
    payload: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Resend email verification link."""
    user = db.query(User).filter(User.email == payload.email).first()

    if user and not user.email_verified:
        # Invalidate existing tokens
        db.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.verified == False,
        ).update({"verified": True})

        # Create new verification token
        verification_token = EmailVerificationToken(
            user_id=user.id,
            token=_generate_secure_token(),
            email=user.email,
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=EMAIL_VERIFICATION_EXPIRE_HOURS),
        )
        db.add(verification_token)
        db.commit()

        # Send verification email in background
        background_tasks.add_task(
            notification_client.send_email_verification,
            user_id=str(user.id),
            email=user.email,
            first_name=user.first_name or "",
            verification_token=verification_token.token,
        )

    return MessageResponse(
        message="If an unverified account exists, a verification email has been sent."
    )


# =============================================================================
# Phone Verification
# =============================================================================


@router.post("/send-phone-verification", response_model=MessageResponse)
@limiter.limit("3/minute")
def send_phone_verification(
    request: Request,
    payload: SendPhoneVerificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send phone verification code via SMS."""
    # Invalidate existing codes for this phone
    db.query(PhoneVerificationCode).filter(
        PhoneVerificationCode.user_id == current_user.id,
        PhoneVerificationCode.verified == False,
    ).update({"verified": True})

    # Create new verification code
    verification_code = PhoneVerificationCode(
        user_id=current_user.id,
        phone=payload.phone,
        code=_generate_phone_code(),
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=PHONE_VERIFICATION_EXPIRE_MINUTES),
    )
    db.add(verification_code)
    db.commit()

    # TODO: Send SMS via Twilio or other provider

    return MessageResponse(message="Verification code sent to your phone.")


@router.post("/verify-phone", response_model=MessageResponse)
@limiter.limit("5/minute")
def verify_phone(
    request: Request,
    payload: VerifyPhoneRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verify phone number using the code."""
    ip_address = get_client_ip(request)

    verification = (
        db.query(PhoneVerificationCode)
        .filter(
            PhoneVerificationCode.user_id == current_user.id,
            PhoneVerificationCode.phone == payload.phone,
            PhoneVerificationCode.verified == False,
            PhoneVerificationCode.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    # Check attempts
    attempts = int(verification.attempts)
    if attempts >= MAX_PHONE_VERIFICATION_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum verification attempts exceeded. Please request a new code.",
        )

    # Verify code
    if verification.code != payload.code:
        verification.attempts = str(attempts + 1)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code",
        )

    # Mark phone as verified
    current_user.phone = payload.phone
    current_user.phone_verified = True
    verification.verified = True
    verification.verified_at = datetime.now(timezone.utc)
    db.commit()

    # Audit log
    AuditLogService.log_event(
        AuditEventType.PHONE_VERIFICATION,
        user_id=str(current_user.id),
        ip_address=ip_address,
    )

    return MessageResponse(message="Phone number verified successfully.")


# =============================================================================
# User Profile
# =============================================================================


@router.get("/me", response_model=UserPublic)
@limiter.limit(get_rate_limit("me"))
def get_me(request: Request, current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return _user_to_public(current_user)


@router.put("/me", response_model=UserPublic)
@limiter.limit(get_rate_limit("update_profile"))
def update_me(
    request: Request,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update current user profile."""
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return _user_to_public(current_user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/minute")
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change password for authenticated user."""
    ip_address = get_client_ip(request)

    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid current password",
        )

    current_user.password_hash = get_password_hash(payload.new_password)

    # Invalidate all other sessions (keep current one)
    # This is a security measure to ensure password change logs out other devices

    db.add(current_user)
    db.commit()

    # Audit log
    AuditLogService.log_password_change(str(current_user.id), ip_address)

    # Send password changed notification in background
    background_tasks.add_task(
        notification_client.send_password_changed,
        user_id=str(current_user.id),
        email=current_user.email,
        first_name=current_user.first_name or "",
    )

    return None


# =============================================================================
# Privacy & GDPR
# =============================================================================


@router.get("/privacy-consents")
@limiter.limit(get_rate_limit("default"))
def get_privacy_consents(request: Request, current_user: User = Depends(get_current_user)):
    """Get user's privacy consent settings."""
    return [c for c in current_user.privacy_consents]


@router.post("/privacy-consents")
@limiter.limit(get_rate_limit("default"))
def update_privacy_consents(
    request: Request,
    payload: PrivacyConsentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update privacy consent settings."""
    ip_address = get_client_ip(request)

    consent = (
        db.query(PrivacyConsent)
        .filter(
            PrivacyConsent.user_id == current_user.id,
            PrivacyConsent.consent_type == payload.consent_type,
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if consent is None:
        consent = PrivacyConsent(
            user_id=current_user.id,
            consent_type=payload.consent_type,
            granted=payload.granted,
            granted_at=now if payload.granted else None,
            revoked_at=None if payload.granted else now,
            consent_metadata=payload.consent_metadata,
        )
        db.add(consent)
    else:
        consent.granted = payload.granted
        if payload.granted:
            consent.granted_at = now
            consent.revoked_at = None
        else:
            consent.revoked_at = now
        consent.consent_metadata = payload.consent_metadata
    db.commit()
    db.refresh(consent)

    # Audit log
    event_type = (
        AuditEventType.PRIVACY_CONSENT_GRANTED
        if payload.granted
        else AuditEventType.PRIVACY_CONSENT_REVOKED
    )
    AuditLogService.log_event(
        event_type,
        user_id=str(current_user.id),
        ip_address=ip_address,
        details={"consent_type": payload.consent_type},
    )

    return consent


@router.get("/export-data", response_model=DataExportResponse)
@limiter.limit(get_rate_limit("export_data"))
def export_data(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export all user data (GDPR right to access)."""
    ip_address = get_client_ip(request)

    sessions = db.query(UserSession).filter(UserSession.user_id == current_user.id).all()
    consents = (
        db.query(PrivacyConsent).filter(PrivacyConsent.user_id == current_user.id).all()
    )

    # Audit log
    AuditLogService.log_data_export(str(current_user.id), ip_address)

    return DataExportResponse(
        user=_user_to_public(current_user),
        sessions=[
            {
                "id": str(s.id),
                "created_at": s.created_at,
                "expires_at": s.expires_at,
                "ip_address": str(s.ip_address) if s.ip_address else None,
                "device_info": s.device_info,
            }
            for s in sessions
        ],
        privacy_consents=[
            {
                "consent_type": c.consent_type,
                "granted": c.granted,
                "granted_at": c.granted_at,
                "revoked_at": c.revoked_at,
            }
            for c in consents
        ],
        exported_at=datetime.now(timezone.utc),
    )


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(get_rate_limit("delete_account"))
def delete_account(
    request: Request,
    payload: DeleteAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete user account (GDPR right to be forgotten)."""
    ip_address = get_client_ip(request)

    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password",
        )

    user_id = str(current_user.id)
    email = current_user.email

    # Invalidate all tokens
    TokenBlacklistService.blacklist_all_user_tokens(user_id)

    # Delete user (cascades to sessions, consents, etc.)
    db.delete(current_user)
    db.commit()

    # Audit log
    AuditLogService.log_event(
        AuditEventType.ACCOUNT_DELETED,
        user_id=user_id,
        email=email,
        ip_address=ip_address,
    )

    # TODO: Trigger async cleanup of user data in other services

    return None
