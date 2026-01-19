"""Admin user management API endpoints.

Provides CRUD operations for user management by administrators.
Includes role assignment for multi-tenant RBAC.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.core.security import get_password_hash
from app.db.session import get_db
from app.middleware.rate_limit import limiter
from app.middleware.security import get_client_ip
from app.models.user import Role, User, UserVenueRole
from app.schemas.user import UserPublic
from app.services.audit_log import AuditLogService, AuditEventType
from app.services.token_blacklist import TokenBlacklistService

router = APIRouter(prefix="/users", tags=["users"])


# =============================================================================
# Schemas
# =============================================================================


class UserListResponse(BaseModel):
    users: List[UserPublic]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserCreateAdmin(BaseModel):
    """Admin user creation - can set email_verified."""
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email_verified: bool = False
    phone_verified: bool = False


class UserUpdateAdmin(BaseModel):
    """Admin user update - can modify verification status."""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email_verified: Optional[bool] = None
    phone_verified: Optional[bool] = None
    avatar_url: Optional[str] = None


class UserVenueRoleAssign(BaseModel):
    """Assign a role to a user for a specific venue."""
    venue_id: UUID
    role_id: UUID


class UserVenueRoleResponse(BaseModel):
    id: UUID
    user_id: UUID
    venue_id: UUID
    role_id: UUID
    role_name: str
    assigned_at: datetime

    model_config = {"from_attributes": True}


class PasswordResetAdmin(BaseModel):
    """Admin password reset (no current password required)."""
    new_password: str


# =============================================================================
# Helper Functions
# =============================================================================


def check_admin_permission(current_user: User, db: Session) -> bool:
    """Check if user has admin permissions.

    For now, checks if user has Super Admin or Venue Owner role.
    TODO: Implement proper permission checking via user_venue_roles.
    """
    # Get user's roles across all venues
    user_roles = db.query(UserVenueRole).filter(
        UserVenueRole.user_id == current_user.id
    ).all()

    admin_role_names = ["Super Admin", "Venue Owner", "Manager"]

    for uvr in user_roles:
        role = db.query(Role).filter(Role.id == uvr.role_id).first()
        if role and role.name in admin_role_names:
            return True

    # For development: allow if no roles exist yet
    total_roles = db.query(UserVenueRole).count()
    if total_roles == 0:
        return True  # No RBAC configured yet

    return False


def require_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Dependency that requires admin permissions."""
    if not check_admin_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required",
        )
    return current_user


# =============================================================================
# User CRUD Endpoints
# =============================================================================


@router.get("", response_model=UserListResponse)
@limiter.limit("30/minute")
def list_users(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by email or name"),
    email_verified: Optional[bool] = Query(None, description="Filter by email verification"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all users with pagination and filtering."""
    query = db.query(User)

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.email.ilike(search_term),
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term),
            )
        )

    # Apply email_verified filter
    if email_verified is not None:
        query = query.filter(User.email_verified == email_verified)

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    users = query.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()

    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size

    return UserListResponse(
        users=[UserPublic.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{user_id}", response_model=UserPublic)
@limiter.limit("30/minute")
def get_user(
    request: Request,
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get a specific user by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserPublic.model_validate(user)


@router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_user(
    request: Request,
    payload: UserCreateAdmin,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new user (admin action)."""
    ip_address = get_client_ip(request)

    # Check for existing email
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
        email_verified=payload.email_verified,
        phone_verified=payload.phone_verified,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Audit log
    AuditLogService.log_event(
        AuditEventType.REGISTER,
        user_id=str(user.id),
        email=user.email,
        ip_address=ip_address,
        details={"created_by_admin": str(current_user.id)},
    )

    return UserPublic.model_validate(user)


@router.put("/{user_id}", response_model=UserPublic)
@limiter.limit("20/minute")
def update_user(
    request: Request,
    user_id: UUID,
    payload: UserUpdateAdmin,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update a user (admin action)."""
    ip_address = get_client_ip(request)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check for email conflict if changing email
    if payload.email and payload.email != user.email:
        existing = db.query(User).filter(
            User.email == payload.email,
            User.id != user_id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use",
            )

    # Apply updates
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    return UserPublic.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
def delete_user(
    request: Request,
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete a user (admin action)."""
    ip_address = get_client_ip(request)

    # Prevent self-deletion
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account via admin endpoint",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user_email = user.email

    # Invalidate all user tokens
    TokenBlacklistService.blacklist_all_user_tokens(str(user_id))

    # Delete user
    db.delete(user)
    db.commit()

    # Audit log
    AuditLogService.log_event(
        AuditEventType.ACCOUNT_DELETED,
        user_id=str(user_id),
        email=user_email,
        ip_address=ip_address,
        details={"deleted_by_admin": str(current_user.id)},
    )

    return None


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
def admin_reset_password(
    request: Request,
    user_id: UUID,
    payload: PasswordResetAdmin,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Reset a user's password (admin action, no current password required)."""
    ip_address = get_client_ip(request)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update password
    user.password_hash = get_password_hash(payload.new_password)
    user.updated_at = datetime.now(timezone.utc)

    # Invalidate all user tokens
    TokenBlacklistService.blacklist_all_user_tokens(str(user_id))

    db.commit()

    # Audit log
    AuditLogService.log_event(
        AuditEventType.PASSWORD_CHANGE,
        user_id=str(user_id),
        ip_address=ip_address,
        details={"reset_by_admin": str(current_user.id)},
    )

    return None


# =============================================================================
# Role Assignment Endpoints
# =============================================================================


@router.get("/{user_id}/roles", response_model=List[UserVenueRoleResponse])
@limiter.limit("30/minute")
def get_user_roles(
    request: Request,
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get all roles assigned to a user across venues."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user_venue_roles = db.query(UserVenueRole).filter(
        UserVenueRole.user_id == user_id
    ).all()

    result = []
    for uvr in user_venue_roles:
        role = db.query(Role).filter(Role.id == uvr.role_id).first()
        result.append(UserVenueRoleResponse(
            id=uvr.id,
            user_id=uvr.user_id,
            venue_id=uvr.venue_id,
            role_id=uvr.role_id,
            role_name=role.name if role else "Unknown",
            assigned_at=uvr.assigned_at,
        ))

    return result


@router.post("/{user_id}/roles", response_model=UserVenueRoleResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def assign_role(
    request: Request,
    user_id: UUID,
    payload: UserVenueRoleAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Assign a role to a user for a specific venue."""
    ip_address = get_client_ip(request)

    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify role exists
    role = db.query(Role).filter(Role.id == payload.role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    # Check if assignment already exists
    existing = db.query(UserVenueRole).filter(
        UserVenueRole.user_id == user_id,
        UserVenueRole.venue_id == payload.venue_id,
    ).first()

    if existing:
        # Update existing assignment
        existing.role_id = payload.role_id
        existing.assigned_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)

        return UserVenueRoleResponse(
            id=existing.id,
            user_id=existing.user_id,
            venue_id=existing.venue_id,
            role_id=existing.role_id,
            role_name=role.name,
            assigned_at=existing.assigned_at,
        )

    # Create new assignment
    uvr = UserVenueRole(
        user_id=user_id,
        venue_id=payload.venue_id,
        role_id=payload.role_id,
    )
    db.add(uvr)
    db.commit()
    db.refresh(uvr)

    # Audit log
    AuditLogService.log_event(
        AuditEventType.PRIVACY_CONSENT_GRANTED,  # Placeholder for role assignment
        user_id=str(user_id),
        ip_address=ip_address,
        details={
            "action": "role_assigned",
            "role_name": role.name,
            "venue_id": str(payload.venue_id),
            "assigned_by": str(current_user.id),
        },
    )

    return UserVenueRoleResponse(
        id=uvr.id,
        user_id=uvr.user_id,
        venue_id=uvr.venue_id,
        role_id=uvr.role_id,
        role_name=role.name,
        assigned_at=uvr.assigned_at,
    )


@router.delete("/{user_id}/roles/{venue_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def remove_role(
    request: Request,
    user_id: UUID,
    venue_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Remove a user's role for a specific venue."""
    ip_address = get_client_ip(request)

    uvr = db.query(UserVenueRole).filter(
        UserVenueRole.user_id == user_id,
        UserVenueRole.venue_id == venue_id,
    ).first()

    if not uvr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role assignment not found",
        )

    db.delete(uvr)
    db.commit()

    return None
