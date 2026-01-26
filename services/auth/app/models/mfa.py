"""
=============================================================================
FILE: mfa.py
PURPOSE: Database models for Multi-Factor Authentication (MFA/2FA)
=============================================================================

This module defines SQLAlchemy models for storing MFA-related data including
TOTP secrets, backup codes, and temporary verification challenges.

WHAT IT DOES:
- UserMFA: Stores user's MFA settings (TOTP secret, enabled methods)
- MFABackupCode: Stores hashed backup codes for account recovery
- MFAChallenge: Temporary challenges for email/SMS code verification

SUPPORTED MFA METHODS:
1. TOTP (Time-based One-Time Password) - Google Authenticator, Authy, etc.
2. SMS verification codes
3. Email verification codes
4. Backup codes for recovery

SECURITY CONSIDERATIONS:
- TOTP secrets are stored encrypted (encryption happens in service layer)
- Backup codes are hashed (one-way, like passwords)
- Challenges expire after a short time (10 minutes default)
- Maximum attempt limits prevent brute force attacks

DATABASE TABLES CREATED:
- user_mfa: One-to-one with users table
- mfa_backup_codes: One-to-many with user_mfa
- mfa_challenges: Temporary challenges, can be cleaned up periodically

USAGE:
    from app.models.mfa import UserMFA, MFABackupCode, MFAChallenge

    # Enable TOTP for a user
    mfa = UserMFA(user_id=user.id, totp_enabled=True, totp_secret=encrypted_secret)
    db.add(mfa)

RELATED FILES:
- app/services/mfa_service.py: Business logic for MFA operations
- app/api/v1/mfa.py: API endpoints for MFA setup and verification
- alembic/versions/*_add_mfa_tables.py: Database migration

=============================================================================
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BOOLEAN,
    INTEGER,
    TIMESTAMP,
    Column,
    ForeignKey,
    String,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class UserMFA(Base):
    """
    MFA settings for a user.

    This table stores the user's MFA configuration including:
    - Which MFA methods are enabled (TOTP, SMS, Email)
    - The encrypted TOTP secret for authenticator apps
    - Timestamps for when features were enabled

    Relationship: One-to-one with User table
    """
    __tablename__ = "user_mfa"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to users table (one-to-one relationship)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # TOTP (Time-based One-Time Password) Settings
    # Used with Google Authenticator, Authy, 1Password, etc.
    totp_enabled = Column(BOOLEAN, default=False)
    totp_secret = Column(String(64), nullable=True)  # Encrypted TOTP secret key
    totp_verified_at = Column(TIMESTAMP, nullable=True)  # When user first verified TOTP

    # SMS-based MFA
    sms_enabled = Column(BOOLEAN, default=False)

    # Email-based MFA
    email_enabled = Column(BOOLEAN, default=False)

    # Backup codes for account recovery
    backup_codes_generated_at = Column(TIMESTAMP, nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    backup_codes = relationship(
        "MFABackupCode",
        back_populates="user_mfa",
        cascade="all,delete-orphan",
    )
    user = relationship("User", backref="mfa_settings")

    def has_any_mfa_enabled(self) -> bool:
        """Check if user has any MFA method enabled."""
        return self.totp_enabled or self.sms_enabled or self.email_enabled


class MFABackupCode(Base):
    """
    Backup codes for MFA recovery.

    Backup codes allow users to access their account if they lose access
    to their primary MFA method (e.g., lost phone with authenticator app).

    Security:
    - Codes are hashed using the same algorithm as passwords
    - Each code can only be used once
    - Typically 10 codes are generated at a time
    - User should store these securely offline

    Usage Flow:
    1. User enables MFA and receives 10 backup codes
    2. User stores codes securely (printed, password manager, etc.)
    3. If user loses MFA device, they can use a backup code to login
    4. Used codes are marked and cannot be reused
    5. User can regenerate new codes (invalidates old ones)
    """
    __tablename__ = "mfa_backup_codes"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to user_mfa table
    user_mfa_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_mfa.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The hashed backup code (never store plain text!)
    code_hash = Column(String(255), nullable=False)

    # Track if this code has been used
    used = Column(BOOLEAN, default=False)
    used_at = Column(TIMESTAMP, nullable=True)

    # Timestamp
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationship back to UserMFA
    user_mfa = relationship("UserMFA", back_populates="backup_codes")


class MFAChallenge(Base):
    """
    Temporary MFA challenges for verification.

    This table stores pending MFA verification attempts. When a user
    needs to verify MFA (e.g., during login), a challenge is created
    with a code that must be verified within the expiration time.

    Challenge Types:
    - TOTP: User enters code from authenticator app (no code stored here)
    - SMS: Random code sent via SMS, hash stored here
    - EMAIL: Random code sent via email, hash stored here
    - BACKUP: User enters a backup code

    Security Features:
    - Challenges expire after a short time (default 10 minutes)
    - Maximum attempt limit prevents brute force
    - IP address and user agent logged for security auditing
    - Session token returned after successful verification

    Lifecycle:
    1. Challenge created when MFA is required
    2. User receives code (SMS/email) or uses authenticator
    3. User submits code for verification
    4. On success: challenge marked verified, session token returned
    5. On failure: attempt count incremented
    6. If max attempts exceeded: challenge invalidated
    """
    __tablename__ = "mfa_challenges"

    # Indexes for efficient queries
    __table_args__ = (
        Index("ix_mfa_challenges_user_expires", "user_id", "expires_at"),
    )

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # User this challenge belongs to
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Type of MFA challenge
    challenge_type = Column(String(20), nullable=False)  # TOTP, SMS, EMAIL, BACKUP

    # Hashed code for SMS/EMAIL challenges (TOTP uses time-based algorithm)
    code_hash = Column(String(255), nullable=True)

    # Expiration and verification status
    expires_at = Column(TIMESTAMP, nullable=False, index=True)
    verified = Column(BOOLEAN, default=False)
    verified_at = Column(TIMESTAMP, nullable=True)

    # Attempt tracking for brute force protection
    attempts = Column(INTEGER, default=0)
    max_attempts = Column(INTEGER, default=5)

    # Session token returned after successful MFA verification
    # This token is used to complete the login process
    session_token = Column(String(255), nullable=True, unique=True)

    # Security logging
    ip_address = Column(String(45), nullable=True)  # Supports IPv6
    user_agent = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    def is_expired(self) -> bool:
        """Check if this challenge has expired."""
        return datetime.utcnow() > self.expires_at

    def is_locked(self) -> bool:
        """Check if this challenge is locked due to too many attempts."""
        return self.attempts >= self.max_attempts

    def can_attempt(self) -> bool:
        """Check if another verification attempt is allowed."""
        return not self.is_expired() and not self.is_locked() and not self.verified


# =============================================================================
# END OF FILE
# =============================================================================
