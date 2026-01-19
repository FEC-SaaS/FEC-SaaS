"""Loyalty tier and preferences API endpoints.

Industry-leading features from Intercard/Toast/Sacoa:
- Loyalty tier progression (Bronze → Platinum)
- Personal best tracking
- Dietary preferences
- Multi-language support
- Accessibility settings
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.session import get_db
from app.middleware.rate_limit import limiter
from app.models.user import LoyaltyTier, User, UserPreference

router = APIRouter(prefix="/loyalty", tags=["loyalty"])


# =============================================================================
# Schemas
# =============================================================================


class LoyaltyStatusResponse(BaseModel):
    user_id: UUID
    loyalty_tier: LoyaltyTier
    loyalty_points: int
    lifetime_points: int
    points_to_next_tier: int
    next_tier: Optional[LoyaltyTier]
    tier_benefits: Dict[str, Any]


class AddPointsRequest(BaseModel):
    points: int
    reason: str
    venue_id: Optional[UUID] = None


class RedeemPointsRequest(BaseModel):
    points: int
    reward_type: str
    venue_id: Optional[UUID] = None


class UserPreferenceUpdate(BaseModel):
    preference_key: str
    preference_value: Any


class UserPreferencesResponse(BaseModel):
    user_id: UUID
    preferred_language: str
    preferred_currency: str
    accessibility_needs: Optional[Dict[str, Any]]
    preferences: Dict[str, Any]


# Tier thresholds and benefits
TIER_THRESHOLDS = {
    LoyaltyTier.BRONZE: 0,
    LoyaltyTier.SILVER: 1000,
    LoyaltyTier.GOLD: 5000,
    LoyaltyTier.PLATINUM: 15000,
}

TIER_BENEFITS = {
    LoyaltyTier.BRONZE: {
        "discount_percentage": 0,
        "bonus_points_multiplier": 1.0,
        "free_games_monthly": 0,
        "priority_booking": False,
        "exclusive_events": False,
    },
    LoyaltyTier.SILVER: {
        "discount_percentage": 5,
        "bonus_points_multiplier": 1.25,
        "free_games_monthly": 2,
        "priority_booking": False,
        "exclusive_events": False,
    },
    LoyaltyTier.GOLD: {
        "discount_percentage": 10,
        "bonus_points_multiplier": 1.5,
        "free_games_monthly": 5,
        "priority_booking": True,
        "exclusive_events": False,
    },
    LoyaltyTier.PLATINUM: {
        "discount_percentage": 15,
        "bonus_points_multiplier": 2.0,
        "free_games_monthly": 10,
        "priority_booking": True,
        "exclusive_events": True,
    },
}


# =============================================================================
# Loyalty Endpoints
# =============================================================================


@router.get("/status", response_model=LoyaltyStatusResponse)
@limiter.limit("30/minute")
def get_loyalty_status(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's loyalty status and tier information."""
    return _build_loyalty_response(current_user)


@router.get("/tiers")
@limiter.limit("30/minute")
def get_tier_info(request: Request):
    """Get information about all loyalty tiers and their benefits."""
    tiers = []
    for tier in LoyaltyTier:
        tiers.append({
            "tier": tier.value,
            "points_required": TIER_THRESHOLDS[tier],
            "benefits": TIER_BENEFITS[tier],
        })
    return {"tiers": tiers}


@router.post("/points/add", response_model=LoyaltyStatusResponse)
@limiter.limit("100/minute")
def add_loyalty_points(
    request: Request,
    payload: AddPointsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Add loyalty points to user account.
    Note: In production, this would be called by other services (POS, arcade).
    """
    if payload.points <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Points must be positive",
        )

    # Apply tier multiplier
    multiplier = TIER_BENEFITS[current_user.loyalty_tier]["bonus_points_multiplier"]
    actual_points = int(payload.points * multiplier)

    current_user.loyalty_points += actual_points
    current_user.lifetime_points += actual_points
    current_user.updated_at = datetime.now(timezone.utc)

    # Check for tier upgrade
    _check_tier_upgrade(current_user)

    db.commit()
    db.refresh(current_user)

    return _build_loyalty_response(current_user)


@router.post("/points/redeem", response_model=LoyaltyStatusResponse)
@limiter.limit("30/minute")
def redeem_loyalty_points(
    request: Request,
    payload: RedeemPointsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Redeem loyalty points for rewards."""
    if payload.points <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Points must be positive",
        )

    if current_user.loyalty_points < payload.points:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient points. Available: {current_user.loyalty_points}",
        )

    current_user.loyalty_points -= payload.points
    current_user.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(current_user)

    return _build_loyalty_response(current_user)


# =============================================================================
# Preferences Endpoints
# =============================================================================


@router.get("/preferences", response_model=UserPreferencesResponse)
@limiter.limit("30/minute")
def get_user_preferences(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all user preferences including language, accessibility, dietary, etc."""
    prefs = db.query(UserPreference).filter(
        UserPreference.user_id == current_user.id
    ).all()

    preferences_dict = {}
    for pref in prefs:
        preferences_dict[pref.preference_key] = pref.preference_value

    return UserPreferencesResponse(
        user_id=current_user.id,
        preferred_language=current_user.preferred_language,
        preferred_currency=current_user.preferred_currency,
        accessibility_needs=current_user.accessibility_needs,
        preferences=preferences_dict,
    )


@router.put("/preferences", response_model=UserPreferencesResponse)
@limiter.limit("20/minute")
def update_user_preference(
    request: Request,
    payload: UserPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a specific user preference."""
    # Handle built-in user fields
    if payload.preference_key == "preferred_language":
        current_user.preferred_language = payload.preference_value
        db.commit()
    elif payload.preference_key == "preferred_currency":
        current_user.preferred_currency = payload.preference_value
        db.commit()
    elif payload.preference_key == "accessibility_needs":
        current_user.accessibility_needs = payload.preference_value
        db.commit()
    else:
        # Handle extended preferences
        existing = db.query(UserPreference).filter(
            UserPreference.user_id == current_user.id,
            UserPreference.preference_key == payload.preference_key,
        ).first()

        if existing:
            existing.preference_value = payload.preference_value
            existing.updated_at = datetime.now(timezone.utc)
        else:
            pref = UserPreference(
                user_id=current_user.id,
                preference_key=payload.preference_key,
                preference_value=payload.preference_value,
            )
            db.add(pref)

        db.commit()

    # Return updated preferences
    return get_user_preferences(request, db, current_user)


@router.delete("/preferences/{preference_key}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def delete_user_preference(
    request: Request,
    preference_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a user preference."""
    # Cannot delete built-in fields
    if preference_key in ["preferred_language", "preferred_currency", "accessibility_needs"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete built-in preferences. Use PUT to reset to default.",
        )

    pref = db.query(UserPreference).filter(
        UserPreference.user_id == current_user.id,
        UserPreference.preference_key == preference_key,
    ).first()

    if not pref:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preference not found")

    db.delete(pref)
    db.commit()
    return None


# =============================================================================
# Common Preference Keys
# =============================================================================


@router.get("/preferences/keys")
@limiter.limit("30/minute")
def get_preference_keys(request: Request):
    """Get list of common preference keys and their descriptions."""
    return {
        "built_in": {
            "preferred_language": "ISO language code (e.g., 'en', 'es', 'fr')",
            "preferred_currency": "ISO currency code (e.g., 'USD', 'EUR')",
            "accessibility_needs": "Object with visual, audio, motor boolean flags",
        },
        "extended": {
            "dietary_restrictions": "Array of dietary restrictions (e.g., ['vegan', 'gluten_free'])",
            "notification_preferences": "Object with email, sms, push boolean flags",
            "favorite_games": "Array of favorite game types",
            "marketing_preferences": "Object with birthday_offers, weekly_deals booleans",
            "theme_preference": "UI theme preference ('light', 'dark', 'auto')",
        },
    }


# =============================================================================
# Helper Functions
# =============================================================================


def _build_loyalty_response(user: User) -> LoyaltyStatusResponse:
    """Build loyalty status response."""
    # Calculate next tier
    next_tier = None
    points_to_next = 0

    tiers = list(LoyaltyTier)
    current_index = tiers.index(user.loyalty_tier)

    if current_index < len(tiers) - 1:
        next_tier = tiers[current_index + 1]
        points_to_next = TIER_THRESHOLDS[next_tier] - user.lifetime_points
        if points_to_next < 0:
            points_to_next = 0

    return LoyaltyStatusResponse(
        user_id=user.id,
        loyalty_tier=user.loyalty_tier,
        loyalty_points=user.loyalty_points,
        lifetime_points=user.lifetime_points,
        points_to_next_tier=points_to_next,
        next_tier=next_tier,
        tier_benefits=TIER_BENEFITS[user.loyalty_tier],
    )


def _check_tier_upgrade(user: User) -> None:
    """Check if user qualifies for tier upgrade based on lifetime points."""
    for tier in reversed(list(LoyaltyTier)):
        if user.lifetime_points >= TIER_THRESHOLDS[tier]:
            if tier != user.loyalty_tier:
                user.loyalty_tier = tier
            break
