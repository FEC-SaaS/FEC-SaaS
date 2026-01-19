"""Token models for password reset, email verification, and social auth."""
import uuid
from datetime import datetime

from sqlalchemy import BOOLEAN, TIMESTAMP, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class PasswordResetToken(Base):
    """Token for password reset requests."""

    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(TIMESTAMP, nullable=False)
    used = Column(BOOLEAN, default=False)
    used_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    user = relationship("User", backref="password_reset_tokens")


class EmailVerificationToken(Base):
    """Token for email verification."""

    __tablename__ = "email_verification_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token = Column(String(255), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=False)
    expires_at = Column(TIMESTAMP, nullable=False)
    verified = Column(BOOLEAN, default=False)
    verified_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    user = relationship("User", backref="email_verification_tokens")


class PhoneVerificationCode(Base):
    """Code for phone number verification (SMS OTP)."""

    __tablename__ = "phone_verification_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    phone = Column(String(20), nullable=False)
    code = Column(String(10), nullable=False)
    expires_at = Column(TIMESTAMP, nullable=False)
    verified = Column(BOOLEAN, default=False)
    verified_at = Column(TIMESTAMP, nullable=True)
    attempts = Column(String(10), default="0")
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    user = relationship("User", backref="phone_verification_codes")


class SocialAuthProvider(Base):
    """Social authentication provider links (Google, Facebook, Apple)."""

    __tablename__ = "social_auth_providers"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_provider_user"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider = Column(String(50), nullable=False)  # google, facebook, apple
    provider_user_id = Column(String(255), nullable=False)
    provider_email = Column(String(255), nullable=True)
    provider_data = Column(JSON, nullable=True)  # Store raw provider response
    access_token = Column(String(500), nullable=True)
    refresh_token = Column(String(500), nullable=True)
    token_expires_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref="social_auth_providers")
