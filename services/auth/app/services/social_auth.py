"""
=============================================================================
FILE: social_auth.py
PURPOSE: Social authentication providers (Google, Facebook, Apple Sign-In)
=============================================================================

This service handles OAuth 2.0 authentication flows for social login providers.
It supports Google, Facebook, and Apple Sign-In for user authentication.

WHAT IT DOES:
- Generates OAuth authorization URLs for each provider
- Exchanges authorization codes for access tokens
- Fetches user profile information from providers
- Links social accounts to existing user accounts
- Creates new user accounts from social profiles

SUPPORTED PROVIDERS:
1. Google OAuth 2.0
2. Facebook Login
3. Apple Sign-In (coming soon)

OAUTH FLOW:
1. Frontend redirects user to authorization URL (from get_authorization_url)
2. User authorizes the app on provider's site
3. Provider redirects back with authorization code
4. Backend exchanges code for tokens (exchange_code_for_token)
5. Backend fetches user profile (get_user_info)
6. Backend creates/links account and returns JWT tokens

CONFIGURATION (from config.py):
- GOOGLE_CLIENT_ID: Google OAuth client ID
- GOOGLE_CLIENT_SECRET: Google OAuth client secret
- GOOGLE_REDIRECT_URI: Callback URL for Google OAuth
- FACEBOOK_APP_ID: Facebook App ID
- FACEBOOK_APP_SECRET: Facebook App Secret
- FACEBOOK_REDIRECT_URI: Callback URL for Facebook OAuth

USAGE:
    from app.services.social_auth import GoogleOAuth, FacebookOAuth

    # Get authorization URL
    auth_url = GoogleOAuth.get_authorization_url(state="random_state")

    # Exchange code for token
    tokens = await GoogleOAuth.exchange_code_for_token(code)

    # Get user info
    user_info = await GoogleOAuth.get_user_info(tokens["access_token"])

=============================================================================
"""

import httpx
import structlog
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from app.core.config import get_settings

settings = get_settings()
logger = structlog.get_logger()


class OAuthProvider:
    """Base class for OAuth providers."""

    # Override these in subclasses
    PROVIDER_NAME: str = "base"
    AUTHORIZATION_URL: str = ""
    TOKEN_URL: str = ""
    USER_INFO_URL: str = ""
    SCOPES: list[str] = []

    @classmethod
    def is_configured(cls) -> bool:
        """Check if this provider is properly configured."""
        raise NotImplementedError

    @classmethod
    def get_authorization_url(cls, state: str, redirect_uri: Optional[str] = None) -> str:
        """Generate the OAuth authorization URL."""
        raise NotImplementedError

    @classmethod
    async def exchange_code_for_token(
        cls, code: str, redirect_uri: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        raise NotImplementedError

    @classmethod
    async def get_user_info(cls, access_token: str) -> Dict[str, Any]:
        """Get user profile information from the provider."""
        raise NotImplementedError


class GoogleOAuth(OAuthProvider):
    """
    Google OAuth 2.0 implementation.

    Google provides email, name, and profile picture.
    Requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in config.
    """

    PROVIDER_NAME = "google"
    AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USER_INFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    SCOPES = ["openid", "email", "profile"]

    @classmethod
    def is_configured(cls) -> bool:
        """Check if Google OAuth is configured."""
        return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)

    @classmethod
    def get_authorization_url(cls, state: str, redirect_uri: Optional[str] = None) -> str:
        """
        Generate Google OAuth authorization URL.

        Args:
            state: Random state parameter for CSRF protection
            redirect_uri: Override default redirect URI

        Returns:
            Full authorization URL to redirect user to
        """
        if not cls.is_configured():
            raise ValueError("Google OAuth is not configured")

        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": redirect_uri or settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(cls.SCOPES),
            "state": state,
            "access_type": "offline",  # Get refresh token
            "prompt": "consent",  # Always show consent screen
        }

        return f"{cls.AUTHORIZATION_URL}?{urlencode(params)}"

    @classmethod
    async def exchange_code_for_token(
        cls, code: str, redirect_uri: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from callback
            redirect_uri: Must match the URI used in authorization

        Returns:
            Dict containing access_token, refresh_token, expires_in, etc.

        Raises:
            httpx.HTTPStatusError: If token exchange fails
        """
        if not cls.is_configured():
            raise ValueError("Google OAuth is not configured")

        payload = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri or settings.GOOGLE_REDIRECT_URI,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(cls.TOKEN_URL, data=payload)
            response.raise_for_status()
            tokens = response.json()

            logger.info("google_token_exchanged")
            return tokens

    @classmethod
    async def get_user_info(cls, access_token: str) -> Dict[str, Any]:
        """
        Get user profile from Google.

        Args:
            access_token: OAuth access token

        Returns:
            Dict with user info:
            - id: Google user ID
            - email: Email address
            - verified_email: Whether email is verified
            - name: Full name
            - given_name: First name
            - family_name: Last name
            - picture: Profile picture URL
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                cls.USER_INFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            user_info = response.json()

            logger.info("google_user_info_fetched", email=user_info.get("email"))
            return {
                "provider": cls.PROVIDER_NAME,
                "provider_user_id": user_info.get("id"),
                "email": user_info.get("email"),
                "email_verified": user_info.get("verified_email", False),
                "first_name": user_info.get("given_name"),
                "last_name": user_info.get("family_name"),
                "full_name": user_info.get("name"),
                "picture_url": user_info.get("picture"),
            }

    @classmethod
    async def refresh_access_token(cls, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an expired access token.

        Args:
            refresh_token: OAuth refresh token

        Returns:
            Dict containing new access_token, expires_in, etc.
        """
        if not cls.is_configured():
            raise ValueError("Google OAuth is not configured")

        payload = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(cls.TOKEN_URL, data=payload)
            response.raise_for_status()
            tokens = response.json()

            logger.info("google_token_refreshed")
            return tokens


class FacebookOAuth(OAuthProvider):
    """
    Facebook Login implementation.

    Facebook provides email, name, and profile picture.
    Requires FACEBOOK_APP_ID and FACEBOOK_APP_SECRET in config.
    """

    PROVIDER_NAME = "facebook"
    AUTHORIZATION_URL = "https://www.facebook.com/v18.0/dialog/oauth"
    TOKEN_URL = "https://graph.facebook.com/v18.0/oauth/access_token"
    USER_INFO_URL = "https://graph.facebook.com/v18.0/me"
    SCOPES = ["email", "public_profile"]

    @classmethod
    def is_configured(cls) -> bool:
        """Check if Facebook OAuth is configured."""
        return bool(settings.FACEBOOK_APP_ID and settings.FACEBOOK_APP_SECRET)

    @classmethod
    def get_authorization_url(cls, state: str, redirect_uri: Optional[str] = None) -> str:
        """
        Generate Facebook OAuth authorization URL.

        Args:
            state: Random state parameter for CSRF protection
            redirect_uri: Override default redirect URI

        Returns:
            Full authorization URL to redirect user to
        """
        if not cls.is_configured():
            raise ValueError("Facebook OAuth is not configured")

        params = {
            "client_id": settings.FACEBOOK_APP_ID,
            "redirect_uri": redirect_uri or settings.FACEBOOK_REDIRECT_URI,
            "state": state,
            "scope": ",".join(cls.SCOPES),
            "response_type": "code",
        }

        return f"{cls.AUTHORIZATION_URL}?{urlencode(params)}"

    @classmethod
    async def exchange_code_for_token(
        cls, code: str, redirect_uri: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from callback
            redirect_uri: Must match the URI used in authorization

        Returns:
            Dict containing access_token, expires_in, etc.

        Raises:
            httpx.HTTPStatusError: If token exchange fails
        """
        if not cls.is_configured():
            raise ValueError("Facebook OAuth is not configured")

        params = {
            "client_id": settings.FACEBOOK_APP_ID,
            "client_secret": settings.FACEBOOK_APP_SECRET,
            "code": code,
            "redirect_uri": redirect_uri or settings.FACEBOOK_REDIRECT_URI,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(cls.TOKEN_URL, params=params)
            response.raise_for_status()
            tokens = response.json()

            logger.info("facebook_token_exchanged")
            return tokens

    @classmethod
    async def get_user_info(cls, access_token: str) -> Dict[str, Any]:
        """
        Get user profile from Facebook.

        Args:
            access_token: OAuth access token

        Returns:
            Dict with user info:
            - id: Facebook user ID
            - email: Email address
            - name: Full name
            - first_name: First name
            - last_name: Last name
            - picture: Profile picture URL
        """
        params = {
            "access_token": access_token,
            "fields": "id,email,name,first_name,last_name,picture.width(200).height(200)",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(cls.USER_INFO_URL, params=params)
            response.raise_for_status()
            user_info = response.json()

            # Extract picture URL from nested structure
            picture_url = None
            if "picture" in user_info and "data" in user_info["picture"]:
                picture_url = user_info["picture"]["data"].get("url")

            logger.info("facebook_user_info_fetched", email=user_info.get("email"))
            return {
                "provider": cls.PROVIDER_NAME,
                "provider_user_id": user_info.get("id"),
                "email": user_info.get("email"),
                "email_verified": True,  # Facebook emails are verified
                "first_name": user_info.get("first_name"),
                "last_name": user_info.get("last_name"),
                "full_name": user_info.get("name"),
                "picture_url": picture_url,
            }


class AppleOAuth(OAuthProvider):
    """
    Apple Sign-In implementation.

    Apple provides email (can be private relay), name (only on first login).
    Requires APPLE_CLIENT_ID, APPLE_TEAM_ID, APPLE_KEY_ID, APPLE_PRIVATE_KEY.

    Note: Apple Sign-In is more complex as it requires JWT for client secret.
    """

    PROVIDER_NAME = "apple"
    AUTHORIZATION_URL = "https://appleid.apple.com/auth/authorize"
    TOKEN_URL = "https://appleid.apple.com/auth/token"
    SCOPES = ["name", "email"]

    @classmethod
    def is_configured(cls) -> bool:
        """Check if Apple Sign-In is configured."""
        return bool(
            settings.APPLE_CLIENT_ID
            and settings.APPLE_TEAM_ID
            and settings.APPLE_KEY_ID
            and settings.APPLE_PRIVATE_KEY
        )

    @classmethod
    def get_authorization_url(cls, state: str, redirect_uri: Optional[str] = None) -> str:
        """Generate Apple Sign-In authorization URL."""
        if not cls.is_configured():
            raise ValueError("Apple Sign-In is not configured")

        # Apple Sign-In requires additional implementation
        # This is a placeholder - full implementation requires JWT generation
        raise NotImplementedError("Apple Sign-In is not yet implemented")

    @classmethod
    async def exchange_code_for_token(
        cls, code: str, redirect_uri: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        raise NotImplementedError("Apple Sign-In is not yet implemented")

    @classmethod
    async def get_user_info(cls, access_token: str) -> Dict[str, Any]:
        """Get user info from Apple ID token."""
        raise NotImplementedError("Apple Sign-In is not yet implemented")


# Provider registry for easy lookup
OAUTH_PROVIDERS: Dict[str, type[OAuthProvider]] = {
    "google": GoogleOAuth,
    "facebook": FacebookOAuth,
    "apple": AppleOAuth,
}


def get_oauth_provider(provider_name: str) -> type[OAuthProvider]:
    """
    Get an OAuth provider class by name.

    Args:
        provider_name: Name of the provider (google, facebook, apple)

    Returns:
        The provider class

    Raises:
        ValueError: If provider is not supported
    """
    provider = OAUTH_PROVIDERS.get(provider_name.lower())
    if not provider:
        raise ValueError(f"Unknown OAuth provider: {provider_name}")
    return provider


def get_configured_providers() -> list[str]:
    """
    Get list of configured OAuth providers.

    Returns:
        List of provider names that are properly configured
    """
    return [name for name, provider in OAUTH_PROVIDERS.items() if provider.is_configured()]


# =============================================================================
# END OF FILE
# =============================================================================
