"""Social authentication endpoints for OAuth providers.

Supports:
- Google OAuth
- Facebook OAuth
- Apple Sign In
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, get_password_hash
from app.db.session import get_db
from app.models.token import SocialAuthProvider
from app.models.user import User, UserSession
from app.schemas.auth import (
    AppleAuthRequest,
    AuthResponse,
    FacebookAuthRequest,
    GoogleAuthRequest,
    TokenPair,
)
from app.schemas.user import UserPublic

router = APIRouter(prefix="/auth/social", tags=["social-auth"])
settings = get_settings()


def _user_to_public(user: User) -> UserPublic:
    return UserPublic.model_validate(user)


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
        device_info={"user_agent": request.headers.get("user-agent")},
        ip_address=request.client.host if request.client else None,
    )
    db.add(session)
    return session


def _generate_random_password() -> str:
    """Generate a random password for social auth users."""
    import secrets
    return secrets.token_urlsafe(32)


def _get_or_create_social_user(
    db: Session,
    provider: str,
    provider_user_id: str,
    email: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
    provider_data: Optional[dict],
) -> User:
    """Get existing user or create new user from social auth."""
    # Check if social provider link already exists
    social_link = (
        db.query(SocialAuthProvider)
        .filter(
            SocialAuthProvider.provider == provider,
            SocialAuthProvider.provider_user_id == provider_user_id,
        )
        .first()
    )

    if social_link:
        # Existing social link - return the user
        return social_link.user

    # Check if user with this email already exists
    user = None
    if email:
        user = db.query(User).filter(User.email == email).first()

    if not user:
        # Create new user
        user = User(
            email=email or f"{provider}_{provider_user_id}@social.auth",
            password_hash=get_password_hash(_generate_random_password()),
            first_name=first_name,
            last_name=last_name,
            email_verified=True if email else False,  # Social emails are pre-verified
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Create social provider link
    social_link = SocialAuthProvider(
        user_id=user.id,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_email=email,
        provider_data=provider_data,
    )
    db.add(social_link)
    db.commit()

    return user


def _create_auth_response(
    db: Session,
    user: User,
    request: Request,
) -> AuthResponse:
    """Create auth response with tokens."""
    user.last_login_at = datetime.now(timezone.utc)

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    _create_session(db, user, request, access_token, refresh_token)
    db.commit()

    tokens = TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return AuthResponse(user=_user_to_public(user), tokens=tokens)


@router.post("/google", response_model=AuthResponse)
async def google_auth(
    payload: GoogleAuthRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate with Google OAuth.

    The client should obtain an ID token from Google's OAuth flow
    and send it to this endpoint for verification.
    """
    # TODO: Verify Google ID token
    # In production, use google-auth library to verify the token:
    # from google.oauth2 import id_token
    # from google.auth.transport import requests
    # idinfo = id_token.verify_oauth2_token(payload.id_token, requests.Request(), GOOGLE_CLIENT_ID)

    # For now, return an error indicating this needs implementation
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Google OAuth verification not yet configured. Set up GOOGLE_CLIENT_ID in settings.",
    )

    # Example implementation once configured:
    # user = _get_or_create_social_user(
    #     db=db,
    #     provider="google",
    #     provider_user_id=idinfo["sub"],
    #     email=idinfo.get("email"),
    #     first_name=idinfo.get("given_name"),
    #     last_name=idinfo.get("family_name"),
    #     provider_data=idinfo,
    # )
    # return _create_auth_response(db, user, request)


@router.post("/facebook", response_model=AuthResponse)
async def facebook_auth(
    payload: FacebookAuthRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate with Facebook OAuth.

    The client should obtain an access token from Facebook's OAuth flow
    and send it to this endpoint for verification.
    """
    # TODO: Verify Facebook access token
    # In production, make a request to Facebook's Graph API:
    # response = httpx.get(
    #     "https://graph.facebook.com/me",
    #     params={"fields": "id,email,first_name,last_name", "access_token": payload.access_token}
    # )
    # user_data = response.json()

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Facebook OAuth verification not yet configured. Set up FACEBOOK_APP_ID in settings.",
    )

    # Example implementation once configured:
    # user = _get_or_create_social_user(
    #     db=db,
    #     provider="facebook",
    #     provider_user_id=user_data["id"],
    #     email=user_data.get("email"),
    #     first_name=user_data.get("first_name"),
    #     last_name=user_data.get("last_name"),
    #     provider_data=user_data,
    # )
    # return _create_auth_response(db, user, request)


@router.post("/apple", response_model=AuthResponse)
async def apple_auth(
    payload: AppleAuthRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate with Apple Sign In.

    The client should obtain an ID token from Apple's Sign In flow
    and send it to this endpoint for verification.

    Note: Apple only provides email on first sign-in, so we store it
    in the user_data field for subsequent logins.
    """
    # TODO: Verify Apple ID token
    # In production, verify the JWT token using Apple's public keys

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Apple Sign In verification not yet configured. Set up APPLE_CLIENT_ID in settings.",
    )

    # Example implementation once configured:
    # decoded = jwt.decode(payload.id_token, options={"verify_signature": False})  # Verify in production!
    # user = _get_or_create_social_user(
    #     db=db,
    #     provider="apple",
    #     provider_user_id=decoded["sub"],
    #     email=decoded.get("email") or (payload.user_data or {}).get("email"),
    #     first_name=(payload.user_data or {}).get("name", {}).get("firstName"),
    #     last_name=(payload.user_data or {}).get("name", {}).get("lastName"),
    #     provider_data={"decoded_token": decoded, "user_data": payload.user_data},
    # )
    # return _create_auth_response(db, user, request)
