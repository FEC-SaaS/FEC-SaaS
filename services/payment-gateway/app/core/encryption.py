"""
=============================================================================
FILE: core/encryption.py
PURPOSE: Encryption utilities for sensitive payment data
=============================================================================
"""

import base64
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import settings


def _get_encryption_key() -> bytes:
    """Derive encryption key from settings."""
    key = settings.encryption_key.encode()
    salt = b"payment_gateway_salt"
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    
    return base64.urlsafe_b64encode(kdf.derive(key))


_fernet: Optional[Fernet] = None


def get_fernet() -> Fernet:
    """Get Fernet encryption instance."""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_get_encryption_key())
    return _fernet


def encrypt_sensitive_data(data: str) -> str:
    """Encrypt sensitive data like API credentials."""
    if not data:
        return data
    fernet = get_fernet()
    encrypted = fernet.encrypt(data.encode())
    return encrypted.decode()


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """Decrypt sensitive data."""
    if not encrypted_data:
        return encrypted_data
    fernet = get_fernet()
    decrypted = fernet.decrypt(encrypted_data.encode())
    return decrypted.decode()


def mask_card_number(card_number: str) -> str:
    """Mask card number showing only last 4 digits."""
    if not card_number or len(card_number) < 4:
        return "****"
    return "*" * (len(card_number) - 4) + card_number[-4:]


def mask_sensitive_string(value: str, visible_chars: int = 4) -> str:
    """Mask a sensitive string showing only last N characters."""
    if not value or len(value) <= visible_chars:
        return "*" * len(value) if value else ""
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]
