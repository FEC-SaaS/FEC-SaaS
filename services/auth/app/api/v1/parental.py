"""Parental controls API endpoints.

Industry-leading feature from Embed:
- Spending limits (daily/hourly)
- Time controls
- Content restrictions
- Activity monitoring
"""
from datetime import datetime, time, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.session import get_db
from app.middleware.rate_limit import limiter
from app.models.user import ParentalControl, User

router = APIRouter(prefix="/parental-controls", tags=["parental-controls"])


# =============================================================================
# Schemas
# =============================================================================


class ParentalControlCreate(BaseModel):
    child_id: UUID
    daily_spend_limit: Optional[Decimal] = Field(None, ge=0)
    hourly_spend_limit: Optional[Decimal] = Field(None, ge=0)
    total_balance_limit: Optional[Decimal] = Field(None, ge=0)
    allowed_play_start: Optional[time] = None
    allowed_play_end: Optional[time] = None
    blackout_dates: Optional[List[str]] = None
    restricted_game_types: Optional[List[str]] = None
    activity_notifications: bool = True
    low_balance_alerts: bool = True
    spend_alerts: bool = True


class ParentalControlUpdate(BaseModel):
    daily_spend_limit: Optional[Decimal] = Field(None, ge=0)
    hourly_spend_limit: Optional[Decimal] = Field(None, ge=0)
    total_balance_limit: Optional[Decimal] = Field(None, ge=0)
    allowed_play_start: Optional[time] = None
    allowed_play_end: Optional[time] = None
    blackout_dates: Optional[List[str]] = None
    restricted_game_types: Optional[List[str]] = None
    activity_notifications: Optional[bool] = None
    low_balance_alerts: Optional[bool] = None
    spend_alerts: Optional[bool] = None
    is_active: Optional[bool] = None


class ParentalControlResponse(BaseModel):
    id: UUID
    parent_id: UUID
    child_id: UUID
    child_email: str
    child_name: str
    daily_spend_limit: Optional[Decimal]
    hourly_spend_limit: Optional[Decimal]
    total_balance_limit: Optional[Decimal]
    allowed_play_start: Optional[time]
    allowed_play_end: Optional[time]
    blackout_dates: Optional[List[str]]
    restricted_game_types: Optional[List[str]]
    activity_notifications: bool
    low_balance_alerts: bool
    spend_alerts: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SpendCheckRequest(BaseModel):
    """Check if a spend is allowed under parental controls."""
    child_id: UUID
    amount: Decimal
    game_type: Optional[str] = None


class SpendCheckResponse(BaseModel):
    allowed: bool
    reason: Optional[str] = None
    daily_remaining: Optional[Decimal] = None
    hourly_remaining: Optional[Decimal] = None


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=ParentalControlResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_parental_control(
    request: Request,
    payload: ParentalControlCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set up parental controls for a child account."""
    # Check child exists
    child = db.query(User).filter(User.id == payload.child_id).first()
    if not child:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child user not found")

    # Check not already controlled
    existing = db.query(ParentalControl).filter(
        ParentalControl.parent_id == current_user.id,
        ParentalControl.child_id == payload.child_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parental controls already exist for this child",
        )

    # Cannot set controls on yourself
    if payload.child_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot set parental controls on your own account",
        )

    control = ParentalControl(
        parent_id=current_user.id,
        child_id=payload.child_id,
        daily_spend_limit=payload.daily_spend_limit,
        hourly_spend_limit=payload.hourly_spend_limit,
        total_balance_limit=payload.total_balance_limit,
        allowed_play_start=payload.allowed_play_start,
        allowed_play_end=payload.allowed_play_end,
        blackout_dates=payload.blackout_dates,
        restricted_game_types=payload.restricted_game_types,
        activity_notifications=payload.activity_notifications,
        low_balance_alerts=payload.low_balance_alerts,
        spend_alerts=payload.spend_alerts,
    )
    db.add(control)
    db.commit()
    db.refresh(control)

    return _build_control_response(control, db)


@router.get("", response_model=List[ParentalControlResponse])
@limiter.limit("30/minute")
def get_my_parental_controls(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all parental controls set by the current user."""
    controls = db.query(ParentalControl).filter(
        ParentalControl.parent_id == current_user.id
    ).all()
    return [_build_control_response(c, db) for c in controls]


@router.get("/my-restrictions", response_model=List[ParentalControlResponse])
@limiter.limit("30/minute")
def get_my_restrictions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get parental controls applied to the current user (as a child)."""
    controls = db.query(ParentalControl).filter(
        ParentalControl.child_id == current_user.id,
        ParentalControl.is_active == True,
    ).all()
    return [_build_control_response(c, db) for c in controls]


@router.get("/{control_id}", response_model=ParentalControlResponse)
@limiter.limit("30/minute")
def get_parental_control(
    request: Request,
    control_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific parental control setting."""
    control = db.query(ParentalControl).filter(ParentalControl.id == control_id).first()
    if not control:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parental control not found")

    # Only parent can view
    if control.parent_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return _build_control_response(control, db)


@router.put("/{control_id}", response_model=ParentalControlResponse)
@limiter.limit("10/minute")
def update_parental_control(
    request: Request,
    control_id: UUID,
    payload: ParentalControlUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update parental control settings."""
    control = db.query(ParentalControl).filter(ParentalControl.id == control_id).first()
    if not control:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parental control not found")

    if control.parent_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Update fields
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(control, field, value)

    control.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(control)

    return _build_control_response(control, db)


@router.delete("/{control_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
def delete_parental_control(
    request: Request,
    control_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove parental controls from a child account."""
    control = db.query(ParentalControl).filter(ParentalControl.id == control_id).first()
    if not control:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parental control not found")

    if control.parent_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    db.delete(control)
    db.commit()
    return None


@router.post("/check-spend", response_model=SpendCheckResponse)
@limiter.limit("100/minute")
def check_spend_allowed(
    request: Request,
    payload: SpendCheckRequest,
    db: Session = Depends(get_db),
):
    """
    Check if a spend is allowed under parental controls.
    Used by other services (arcade, POS) to validate purchases.
    """
    controls = db.query(ParentalControl).filter(
        ParentalControl.child_id == payload.child_id,
        ParentalControl.is_active == True,
    ).all()

    if not controls:
        return SpendCheckResponse(allowed=True, reason="No parental controls configured")

    for control in controls:
        # Check game type restrictions
        if payload.game_type and control.restricted_game_types:
            if payload.game_type in control.restricted_game_types:
                return SpendCheckResponse(
                    allowed=False,
                    reason=f"Game type '{payload.game_type}' is restricted",
                )

        # Check time restrictions
        if control.allowed_play_start and control.allowed_play_end:
            now = datetime.now(timezone.utc).time()
            if control.allowed_play_start < control.allowed_play_end:
                if not (control.allowed_play_start <= now <= control.allowed_play_end):
                    return SpendCheckResponse(
                        allowed=False,
                        reason=f"Play only allowed between {control.allowed_play_start} and {control.allowed_play_end}",
                    )
            else:  # Overnight range
                if control.allowed_play_end < now < control.allowed_play_start:
                    return SpendCheckResponse(
                        allowed=False,
                        reason=f"Play only allowed between {control.allowed_play_start} and {control.allowed_play_end}",
                    )

        # Note: Actual spend tracking would require integration with transaction service
        # This is a placeholder for the spend limit check logic

    return SpendCheckResponse(allowed=True)


# =============================================================================
# Helper Functions
# =============================================================================


def _build_control_response(control: ParentalControl, db: Session) -> ParentalControlResponse:
    """Build control response with child details."""
    child = db.query(User).filter(User.id == control.child_id).first()
    return ParentalControlResponse(
        id=control.id,
        parent_id=control.parent_id,
        child_id=control.child_id,
        child_email=child.email if child else "",
        child_name=f"{child.first_name or ''} {child.last_name or ''}".strip() if child else "",
        daily_spend_limit=control.daily_spend_limit,
        hourly_spend_limit=control.hourly_spend_limit,
        total_balance_limit=control.total_balance_limit,
        allowed_play_start=control.allowed_play_start,
        allowed_play_end=control.allowed_play_end,
        blackout_dates=control.blackout_dates,
        restricted_game_types=control.restricted_game_types,
        activity_notifications=control.activity_notifications,
        low_balance_alerts=control.low_balance_alerts,
        spend_alerts=control.spend_alerts,
        is_active=control.is_active,
        created_at=control.created_at,
    )
