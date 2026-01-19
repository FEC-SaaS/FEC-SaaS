"""Roles and permissions API endpoints.

Provides CRUD operations for roles and permissions management.
Only accessible by users with appropriate admin permissions.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.session import get_db
from app.models.user import Permission, Role, RolePermission, User

router = APIRouter(prefix="/roles", tags=["roles"])


# =============================================================================
# Schemas
# =============================================================================


class PermissionBase(BaseModel):
    name: str
    resource: str
    action: str
    description: Optional[str] = None


class PermissionResponse(PermissionBase):
    id: UUID

    model_config = {"from_attributes": True}


class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    permission_ids: Optional[List[UUID]] = None


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class RoleResponse(RoleBase):
    id: UUID
    permissions: List[PermissionResponse] = []

    model_config = {"from_attributes": True}


class AssignPermissionsRequest(BaseModel):
    permission_ids: List[UUID]


# =============================================================================
# Permission Endpoints
# =============================================================================


@router.get("/permissions", response_model=List[PermissionResponse])
def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all available permissions."""
    # TODO: Check user has permission to view roles
    permissions = db.query(Permission).all()
    return permissions


@router.post("/permissions", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
def create_permission(
    payload: PermissionBase,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new permission."""
    # TODO: Check user has admin:system permission
    existing = db.query(Permission).filter(Permission.name == payload.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permission with this name already exists",
        )

    permission = Permission(
        name=payload.name,
        resource=payload.resource,
        action=payload.action,
        description=payload.description,
    )
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return permission


# =============================================================================
# Role Endpoints
# =============================================================================


@router.get("", response_model=List[RoleResponse])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all roles with their permissions."""
    # TODO: Check user has permission to view roles
    roles = db.query(Role).all()
    result = []
    for role in roles:
        role_perms = [rp.permission for rp in role.permissions]
        result.append(
            RoleResponse(
                id=role.id,
                name=role.name,
                description=role.description,
                permissions=role_perms,
            )
        )
    return result


@router.get("/{role_id}", response_model=RoleResponse)
def get_role(
    role_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific role with its permissions."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    role_perms = [rp.permission for rp in role.permissions]
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=role_perms,
    )


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new role."""
    # TODO: Check user has roles:create permission
    existing = db.query(Role).filter(Role.name == payload.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role with this name already exists",
        )

    role = Role(
        name=payload.name,
        description=payload.description,
    )
    db.add(role)
    db.commit()
    db.refresh(role)

    # Assign permissions if provided
    if payload.permission_ids:
        for perm_id in payload.permission_ids:
            permission = db.query(Permission).filter(Permission.id == perm_id).first()
            if permission:
                rp = RolePermission(role_id=role.id, permission_id=permission.id)
                db.add(rp)
        db.commit()

    role_perms = [rp.permission for rp in role.permissions]
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=role_perms,
    )


@router.put("/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: UUID,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a role."""
    # TODO: Check user has roles:update permission
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    if payload.name is not None:
        existing = db.query(Role).filter(Role.name == payload.name, Role.id != role_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role with this name already exists",
            )
        role.name = payload.name

    if payload.description is not None:
        role.description = payload.description

    db.commit()
    db.refresh(role)

    role_perms = [rp.permission for rp in role.permissions]
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=role_perms,
    )


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a role."""
    # TODO: Check user has roles:delete permission
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    # Prevent deletion of system roles
    system_roles = ["Super Admin", "Venue Owner", "Manager", "Staff", "Customer"]
    if role.name in system_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete system roles",
        )

    db.delete(role)
    db.commit()
    return None


@router.post("/{role_id}/permissions", response_model=RoleResponse)
def assign_permissions(
    role_id: UUID,
    payload: AssignPermissionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign permissions to a role (replaces existing permissions)."""
    # TODO: Check user has roles:update permission
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    # Remove existing role permissions
    db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()

    # Add new permissions
    for perm_id in payload.permission_ids:
        permission = db.query(Permission).filter(Permission.id == perm_id).first()
        if permission:
            rp = RolePermission(role_id=role.id, permission_id=permission.id)
            db.add(rp)

    db.commit()
    db.refresh(role)

    role_perms = [rp.permission for rp in role.permissions]
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=role_perms,
    )
