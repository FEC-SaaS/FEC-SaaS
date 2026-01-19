"""Family account linking API endpoints.

Industry-leading feature from Embed/Sacoa:
- Family account linking
- Shared rewards pools
- Parent/child account management
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.session import get_db
from app.middleware.rate_limit import limiter
from app.models.user import FamilyGroup, FamilyMember, FamilyRole, User

router = APIRouter(prefix="/family", tags=["family"])


# =============================================================================
# Schemas
# =============================================================================


class FamilyGroupCreate(BaseModel):
    name: str
    shared_rewards_enabled: bool = False


class FamilyGroupUpdate(BaseModel):
    name: Optional[str] = None
    shared_rewards_enabled: Optional[bool] = None


class FamilyMemberAdd(BaseModel):
    user_id: UUID
    family_role: FamilyRole = FamilyRole.DEPENDENT
    nickname: Optional[str] = None
    can_manage_family: bool = False


class FamilyMemberUpdate(BaseModel):
    family_role: Optional[FamilyRole] = None
    nickname: Optional[str] = None
    can_manage_family: Optional[bool] = None


class FamilyMemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    family_role: FamilyRole
    nickname: Optional[str]
    can_manage_family: bool
    user_email: str
    user_name: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class FamilyGroupResponse(BaseModel):
    id: UUID
    name: str
    primary_contact_id: UUID
    shared_rewards_enabled: bool
    members: List[FamilyMemberResponse]
    created_at: datetime

    model_config = {"from_attributes": True}


# =============================================================================
# Family Group Endpoints
# =============================================================================


@router.post("", response_model=FamilyGroupResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_family_group(
    request: Request,
    payload: FamilyGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new family group with current user as primary contact."""
    # Check if user already has a family group as primary
    existing = db.query(FamilyGroup).filter(
        FamilyGroup.primary_contact_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a family group. You can only be primary contact of one family.",
        )

    # Create family group
    family = FamilyGroup(
        name=payload.name,
        primary_contact_id=current_user.id,
        shared_rewards_enabled=payload.shared_rewards_enabled,
    )
    db.add(family)
    db.flush()

    # Add current user as PARENT member
    member = FamilyMember(
        family_id=family.id,
        user_id=current_user.id,
        family_role=FamilyRole.PARENT,
        can_manage_family=True,
    )
    db.add(member)
    db.commit()
    db.refresh(family)

    return _build_family_response(family, db)


@router.get("", response_model=List[FamilyGroupResponse])
@limiter.limit("30/minute")
def get_my_families(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all family groups the current user belongs to."""
    memberships = db.query(FamilyMember).filter(
        FamilyMember.user_id == current_user.id
    ).all()

    families = []
    for membership in memberships:
        family = db.query(FamilyGroup).filter(FamilyGroup.id == membership.family_id).first()
        if family:
            families.append(_build_family_response(family, db))

    return families


@router.get("/{family_id}", response_model=FamilyGroupResponse)
@limiter.limit("30/minute")
def get_family_group(
    request: Request,
    family_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific family group (must be a member)."""
    family = db.query(FamilyGroup).filter(FamilyGroup.id == family_id).first()
    if not family:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family group not found")

    # Check membership
    membership = db.query(FamilyMember).filter(
        FamilyMember.family_id == family_id,
        FamilyMember.user_id == current_user.id,
    ).first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this family")

    return _build_family_response(family, db)


@router.put("/{family_id}", response_model=FamilyGroupResponse)
@limiter.limit("10/minute")
def update_family_group(
    request: Request,
    family_id: UUID,
    payload: FamilyGroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update family group settings (requires manage permission)."""
    family = db.query(FamilyGroup).filter(FamilyGroup.id == family_id).first()
    if not family:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family group not found")

    # Check permission
    _require_family_manager(current_user.id, family_id, db)

    if payload.name is not None:
        family.name = payload.name
    if payload.shared_rewards_enabled is not None:
        family.shared_rewards_enabled = payload.shared_rewards_enabled

    family.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(family)

    return _build_family_response(family, db)


@router.delete("/{family_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/minute")
def delete_family_group(
    request: Request,
    family_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete family group (only primary contact can delete)."""
    family = db.query(FamilyGroup).filter(FamilyGroup.id == family_id).first()
    if not family:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family group not found")

    if family.primary_contact_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the primary contact can delete the family group",
        )

    db.delete(family)
    db.commit()
    return None


# =============================================================================
# Family Member Endpoints
# =============================================================================


@router.post("/{family_id}/members", response_model=FamilyMemberResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def add_family_member(
    request: Request,
    family_id: UUID,
    payload: FamilyMemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a member to the family group."""
    family = db.query(FamilyGroup).filter(FamilyGroup.id == family_id).first()
    if not family:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family group not found")

    _require_family_manager(current_user.id, family_id, db)

    # Check user exists
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Check not already a member
    existing = db.query(FamilyMember).filter(
        FamilyMember.family_id == family_id,
        FamilyMember.user_id == payload.user_id,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already a family member")

    member = FamilyMember(
        family_id=family_id,
        user_id=payload.user_id,
        family_role=payload.family_role,
        nickname=payload.nickname,
        can_manage_family=payload.can_manage_family,
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    return _build_member_response(member, db)


@router.put("/{family_id}/members/{member_id}", response_model=FamilyMemberResponse)
@limiter.limit("10/minute")
def update_family_member(
    request: Request,
    family_id: UUID,
    member_id: UUID,
    payload: FamilyMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a family member's role or settings."""
    _require_family_manager(current_user.id, family_id, db)

    member = db.query(FamilyMember).filter(
        FamilyMember.id == member_id,
        FamilyMember.family_id == family_id,
    ).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family member not found")

    if payload.family_role is not None:
        member.family_role = payload.family_role
    if payload.nickname is not None:
        member.nickname = payload.nickname
    if payload.can_manage_family is not None:
        member.can_manage_family = payload.can_manage_family

    db.commit()
    db.refresh(member)

    return _build_member_response(member, db)


@router.delete("/{family_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def remove_family_member(
    request: Request,
    family_id: UUID,
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a member from the family group."""
    family = db.query(FamilyGroup).filter(FamilyGroup.id == family_id).first()
    if not family:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family group not found")

    _require_family_manager(current_user.id, family_id, db)

    member = db.query(FamilyMember).filter(
        FamilyMember.id == member_id,
        FamilyMember.family_id == family_id,
    ).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family member not found")

    # Cannot remove primary contact
    if member.user_id == family.primary_contact_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the primary contact from the family",
        )

    db.delete(member)
    db.commit()
    return None


# =============================================================================
# Helper Functions
# =============================================================================


def _require_family_manager(user_id: UUID, family_id: UUID, db: Session) -> FamilyMember:
    """Require user to have family management permission."""
    membership = db.query(FamilyMember).filter(
        FamilyMember.family_id == family_id,
        FamilyMember.user_id == user_id,
    ).first()

    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this family")

    if not membership.can_manage_family:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage this family",
        )

    return membership


def _build_member_response(member: FamilyMember, db: Session) -> FamilyMemberResponse:
    """Build member response with user details."""
    user = db.query(User).filter(User.id == member.user_id).first()
    return FamilyMemberResponse(
        id=member.id,
        user_id=member.user_id,
        family_role=member.family_role,
        nickname=member.nickname,
        can_manage_family=member.can_manage_family,
        user_email=user.email if user else "",
        user_name=f"{user.first_name or ''} {user.last_name or ''}".strip() if user else "",
        joined_at=member.joined_at,
    )


def _build_family_response(family: FamilyGroup, db: Session) -> FamilyGroupResponse:
    """Build family response with all members."""
    members = db.query(FamilyMember).filter(FamilyMember.family_id == family.id).all()
    return FamilyGroupResponse(
        id=family.id,
        name=family.name,
        primary_contact_id=family.primary_contact_id,
        shared_rewards_enabled=family.shared_rewards_enabled,
        members=[_build_member_response(m, db) for m in members],
        created_at=family.created_at,
    )
