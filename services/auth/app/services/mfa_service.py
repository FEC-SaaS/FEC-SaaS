"""
=============================================================================
FILE: mfa_service.py
PURPOSE: Business logic for Multi-Factor Authentication (MFA/2FA) operations
=============================================================================

This service handles all MFA-related operations including TOTP setup,
code verification, backup code management, and MFA challenges.

WHAT IT DOES:
- Generates and validates TOTP (Time-based One-Time Password) codes
- Creates and verifies backup codes for account recovery
- Manages MFA challenges for SMS/email verification
- Generates QR codes for authenticator app setup

SUPPORTED OPERATIONS:
1. TOTP Setup: Generate secret, create QR code, verify initial code
2. TOTP Verification: Validate codes from authenticator apps
3. Backup Codes: Generate, hash, store, and verify backup codes
4. SMS/Email MFA: Create challenges, send codes, verify responses

SECURITY FEATURES:
- TOTP secrets can be encrypted before storage
- Backup codes are hashed (cannot be recovered, only verified)
- Challenges have expiration times and attempt limits
- All operations are logged for audit purposes

DEPENDENCIES:
- pyotp: TOTP/HOTP implementation
- qrcode: QR code generation for authenticator setup
- app.core.security: Password hashing utilities

USAGE:
    from app.services.mfa_service import MFAService

    # Setup TOTP for a user
    secret, qr_uri = MFAService.generate_totp_secret(user.email)

    # Verify a TOTP code
    is_valid = MFAService.verify_totp(secret, user_code)

    # Generate backup codes
    codes = MFAService.generate_backup_codes()

=============================================================================
"""

import base64
import io
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List
from hashlib import sha1
import hmac

import structlog

from app.core.config import get_settings
from app.core.security import get_password_hash, verify_password

settings = get_settings()
logger = structlog.get_logger()


class MFAService:
    """
    Service class for Multi-Factor Authentication operations.

    This class provides static methods for all MFA-related operations.
    It handles TOTP generation/verification, backup codes, and MFA challenges.
    """

    # TOTP Configuration
    TOTP_DIGITS = 6  # Number of digits in TOTP code
    TOTP_INTERVAL = 30  # Time step in seconds
    TOTP_ALGORITHM = "SHA1"  # Algorithm for TOTP

    # Backup codes configuration
    BACKUP_CODE_LENGTH = 8  # Length of each backup code
    BACKUP_CODE_COUNT = 10  # Number of backup codes to generate

    # Challenge configuration
    CHALLENGE_CODE_LENGTH = 6  # Length of SMS/email verification codes
    CHALLENGE_EXPIRY_MINUTES = 10  # How long challenges are valid

    @classmethod
    def generate_totp_secret(cls, email: str) -> Tuple[str, str]:
        """
        Generate a new TOTP secret and provisioning URI for authenticator apps.

        Args:
            email: User's email address (used as account name in authenticator)

        Returns:
            Tuple of (base32_secret, otpauth_uri)

        The URI can be encoded as a QR code for easy setup with authenticator apps.
        """
        # Generate a random 20-byte secret
        secret_bytes = secrets.token_bytes(20)
        secret_base32 = base64.b32encode(secret_bytes).decode("utf-8").rstrip("=")

        # Create the otpauth URI for authenticator apps
        # Format: otpauth://totp/ISSUER:ACCOUNT?secret=SECRET&issuer=ISSUER&algorithm=SHA1&digits=6&period=30
        issuer = settings.MFA_ISSUER_NAME.replace(" ", "%20")
        account = email.replace("@", "%40")

        uri = (
            f"otpauth://totp/{issuer}:{account}"
            f"?secret={secret_base32}"
            f"&issuer={issuer}"
            f"&algorithm={cls.TOTP_ALGORITHM}"
            f"&digits={cls.TOTP_DIGITS}"
            f"&period={cls.TOTP_INTERVAL}"
        )

        logger.info("totp_secret_generated", email=email)

        return secret_base32, uri

    @classmethod
    def generate_totp_qr_code(cls, otpauth_uri: str) -> str:
        """
        Generate a QR code image for the TOTP setup URI.

        Args:
            otpauth_uri: The otpauth:// URI for the TOTP setup

        Returns:
            Base64-encoded PNG image of the QR code

        The returned string can be used directly in an <img> tag:
        <img src="data:image/png;base64,{returned_string}" />
        """
        try:
            import qrcode
            from qrcode.image.pure import PyPNGImage

            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(otpauth_uri)
            qr.make(fit=True)

            # Create image
            img = qr.make_image(fill_color="black", back_color="white")

            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

            return base64_image

        except ImportError:
            logger.warning("qrcode_library_not_installed")
            # Return empty string if qrcode library not installed
            return ""

    @classmethod
    def _compute_totp(cls, secret_base32: str, time_step: int) -> str:
        """
        Compute a TOTP code for a given time step.

        This is a pure Python implementation of TOTP (RFC 6238).
        """
        # Decode the base32 secret
        # Add padding if needed
        padding = 8 - (len(secret_base32) % 8)
        if padding != 8:
            secret_base32 += "=" * padding
        secret_bytes = base64.b32decode(secret_base32.upper())

        # Convert time step to bytes (8-byte big-endian)
        time_bytes = struct.pack(">Q", time_step)

        # Compute HMAC-SHA1
        hmac_result = hmac.new(secret_bytes, time_bytes, sha1).digest()

        # Dynamic truncation
        offset = hmac_result[-1] & 0x0F
        code_int = struct.unpack(">I", hmac_result[offset : offset + 4])[0]
        code_int &= 0x7FFFFFFF  # Clear the most significant bit

        # Get the last N digits
        code = code_int % (10**cls.TOTP_DIGITS)

        return str(code).zfill(cls.TOTP_DIGITS)

    @classmethod
    def get_current_totp(cls, secret_base32: str) -> str:
        """
        Get the current TOTP code for a secret.

        Args:
            secret_base32: The base32-encoded TOTP secret

        Returns:
            The current 6-digit TOTP code
        """
        current_time = int(time.time())
        time_step = current_time // cls.TOTP_INTERVAL
        return cls._compute_totp(secret_base32, time_step)

    @classmethod
    def verify_totp(
        cls,
        secret_base32: str,
        code: str,
        window: int = 1,
    ) -> bool:
        """
        Verify a TOTP code against a secret.

        Args:
            secret_base32: The base32-encoded TOTP secret
            code: The 6-digit code to verify
            window: Number of time steps to check before/after current (default 1)

        Returns:
            True if the code is valid, False otherwise

        The window parameter allows for clock drift between the server and
        the user's device. A window of 1 means we check the current time step,
        plus one step before and one step after (90 seconds total).
        """
        if not code or len(code) != cls.TOTP_DIGITS:
            return False

        # Clean the code (remove spaces, dashes)
        code = code.replace(" ", "").replace("-", "")

        current_time = int(time.time())
        current_step = current_time // cls.TOTP_INTERVAL

        # Check the current step and adjacent steps within the window
        for offset in range(-window, window + 1):
            time_step = current_step + offset
            expected_code = cls._compute_totp(secret_base32, time_step)
            if hmac.compare_digest(code, expected_code):
                logger.info("totp_verified", offset=offset)
                return True

        logger.warning("totp_verification_failed")
        return False

    @classmethod
    def generate_backup_codes(cls) -> List[str]:
        """
        Generate a set of backup codes for account recovery.

        Returns:
            List of plain-text backup codes (display to user once, then hash for storage)

        Backup codes are formatted as XXXX-XXXX for readability.
        """
        codes = []
        for _ in range(cls.BACKUP_CODE_COUNT):
            # Generate random alphanumeric code
            code = secrets.token_hex(cls.BACKUP_CODE_LENGTH // 2).upper()
            # Format as XXXX-XXXX
            formatted_code = f"{code[:4]}-{code[4:]}"
            codes.append(formatted_code)

        logger.info("backup_codes_generated", count=len(codes))
        return codes

    @classmethod
    def hash_backup_code(cls, code: str) -> str:
        """
        Hash a backup code for secure storage.

        Args:
            code: The plain-text backup code

        Returns:
            Hashed code suitable for database storage
        """
        # Remove formatting (dashes, spaces)
        clean_code = code.replace("-", "").replace(" ", "").upper()
        return get_password_hash(clean_code)

    @classmethod
    def verify_backup_code(cls, code: str, code_hash: str) -> bool:
        """
        Verify a backup code against its hash.

        Args:
            code: The plain-text backup code from user
            code_hash: The stored hash

        Returns:
            True if the code matches, False otherwise
        """
        # Remove formatting
        clean_code = code.replace("-", "").replace(" ", "").upper()
        return verify_password(clean_code, code_hash)

    @classmethod
    def generate_challenge_code(cls) -> str:
        """
        Generate a random code for SMS/email MFA challenges.

        Returns:
            A 6-digit numeric code
        """
        code = "".join(
            str(secrets.randbelow(10)) for _ in range(cls.CHALLENGE_CODE_LENGTH)
        )
        return code

    @classmethod
    def get_challenge_expiry(cls) -> datetime:
        """
        Get the expiration time for a new MFA challenge.

        Returns:
            datetime when the challenge expires
        """
        return datetime.now(timezone.utc) + timedelta(
            minutes=cls.CHALLENGE_EXPIRY_MINUTES
        )

    @classmethod
    def generate_session_token(cls) -> str:
        """
        Generate a secure session token for post-MFA authentication.

        Returns:
            A secure random token string
        """
        return secrets.token_urlsafe(32)


# =============================================================================
# END OF FILE
# =============================================================================
