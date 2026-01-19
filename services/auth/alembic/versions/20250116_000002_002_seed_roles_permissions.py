"""Seed default roles and permissions.

Creates the 5 core roles defined in the auth-user-management plan:
- Super Admin: Full system access
- Venue Owner: Full venue management
- Manager: Day-to-day operations
- Staff: Limited operational access
- Customer: Guest/customer access

Revision ID: 002
Revises: 001
Create Date: 2025-01-16 00:00:02
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define tables for data insertion
roles_table = table(
    "roles",
    column("id", postgresql.UUID),
    column("name", sa.String),
    column("description", sa.Text),
)

permissions_table = table(
    "permissions",
    column("id", postgresql.UUID),
    column("name", sa.String),
    column("resource", sa.String),
    column("action", sa.String),
    column("description", sa.Text),
)

role_permissions_table = table(
    "role_permissions",
    column("role_id", postgresql.UUID),
    column("permission_id", postgresql.UUID),
)

# Role UUIDs (deterministic for repeatability)
ROLE_IDS = {
    "super_admin": uuid.UUID("10000000-0000-0000-0000-000000000001"),
    "venue_owner": uuid.UUID("10000000-0000-0000-0000-000000000002"),
    "manager": uuid.UUID("10000000-0000-0000-0000-000000000003"),
    "staff": uuid.UUID("10000000-0000-0000-0000-000000000004"),
    "customer": uuid.UUID("10000000-0000-0000-0000-000000000005"),
}

# Permission UUIDs
PERMISSION_IDS = {
    # User management
    "users:create": uuid.UUID("20000000-0000-0000-0000-000000000001"),
    "users:read": uuid.UUID("20000000-0000-0000-0000-000000000002"),
    "users:update": uuid.UUID("20000000-0000-0000-0000-000000000003"),
    "users:delete": uuid.UUID("20000000-0000-0000-0000-000000000004"),
    "users:list": uuid.UUID("20000000-0000-0000-0000-000000000005"),
    # Role management
    "roles:create": uuid.UUID("20000000-0000-0000-0000-000000000006"),
    "roles:read": uuid.UUID("20000000-0000-0000-0000-000000000007"),
    "roles:update": uuid.UUID("20000000-0000-0000-0000-000000000008"),
    "roles:delete": uuid.UUID("20000000-0000-0000-0000-000000000009"),
    "roles:assign": uuid.UUID("20000000-0000-0000-0000-000000000010"),
    # Venue management
    "venues:create": uuid.UUID("20000000-0000-0000-0000-000000000011"),
    "venues:read": uuid.UUID("20000000-0000-0000-0000-000000000012"),
    "venues:update": uuid.UUID("20000000-0000-0000-0000-000000000013"),
    "venues:delete": uuid.UUID("20000000-0000-0000-0000-000000000014"),
    "venues:list": uuid.UUID("20000000-0000-0000-0000-000000000015"),
    # Privacy/GDPR
    "privacy:read": uuid.UUID("20000000-0000-0000-0000-000000000016"),
    "privacy:update": uuid.UUID("20000000-0000-0000-0000-000000000017"),
    "privacy:export": uuid.UUID("20000000-0000-0000-0000-000000000018"),
    "privacy:delete": uuid.UUID("20000000-0000-0000-0000-000000000019"),
    # Sessions
    "sessions:read": uuid.UUID("20000000-0000-0000-0000-000000000020"),
    "sessions:delete": uuid.UUID("20000000-0000-0000-0000-000000000021"),
    # Admin operations
    "admin:system": uuid.UUID("20000000-0000-0000-0000-000000000022"),
    "admin:audit": uuid.UUID("20000000-0000-0000-0000-000000000023"),
    # Customer operations
    "profile:read": uuid.UUID("20000000-0000-0000-0000-000000000024"),
    "profile:update": uuid.UUID("20000000-0000-0000-0000-000000000025"),
    # Staff operations
    "orders:read": uuid.UUID("20000000-0000-0000-0000-000000000026"),
    "orders:create": uuid.UUID("20000000-0000-0000-0000-000000000027"),
    "orders:update": uuid.UUID("20000000-0000-0000-0000-000000000028"),
    "reservations:read": uuid.UUID("20000000-0000-0000-0000-000000000029"),
    "reservations:create": uuid.UUID("20000000-0000-0000-0000-000000000030"),
    "reservations:update": uuid.UUID("20000000-0000-0000-0000-000000000031"),
}

# Role definitions
ROLES = [
    {
        "id": ROLE_IDS["super_admin"],
        "name": "Super Admin",
        "description": "Full system access across all venues and services. Can manage all users, roles, and system settings.",
    },
    {
        "id": ROLE_IDS["venue_owner"],
        "name": "Venue Owner",
        "description": "Full management access to owned venues. Can manage staff, settings, and view analytics.",
    },
    {
        "id": ROLE_IDS["manager"],
        "name": "Manager",
        "description": "Day-to-day operational management. Can manage staff schedules, orders, and basic venue settings.",
    },
    {
        "id": ROLE_IDS["staff"],
        "name": "Staff",
        "description": "Limited operational access for handling orders, reservations, and customer interactions.",
    },
    {
        "id": ROLE_IDS["customer"],
        "name": "Customer",
        "description": "Guest and customer access. Can view profile, make reservations, and manage preferences.",
    },
]

# Permission definitions
PERMISSIONS = [
    # User management
    {"id": PERMISSION_IDS["users:create"], "name": "users:create", "resource": "users", "action": "create", "description": "Create new users"},
    {"id": PERMISSION_IDS["users:read"], "name": "users:read", "resource": "users", "action": "read", "description": "View user details"},
    {"id": PERMISSION_IDS["users:update"], "name": "users:update", "resource": "users", "action": "update", "description": "Update user information"},
    {"id": PERMISSION_IDS["users:delete"], "name": "users:delete", "resource": "users", "action": "delete", "description": "Delete users"},
    {"id": PERMISSION_IDS["users:list"], "name": "users:list", "resource": "users", "action": "list", "description": "List all users"},
    # Role management
    {"id": PERMISSION_IDS["roles:create"], "name": "roles:create", "resource": "roles", "action": "create", "description": "Create new roles"},
    {"id": PERMISSION_IDS["roles:read"], "name": "roles:read", "resource": "roles", "action": "read", "description": "View role details"},
    {"id": PERMISSION_IDS["roles:update"], "name": "roles:update", "resource": "roles", "action": "update", "description": "Update roles"},
    {"id": PERMISSION_IDS["roles:delete"], "name": "roles:delete", "resource": "roles", "action": "delete", "description": "Delete roles"},
    {"id": PERMISSION_IDS["roles:assign"], "name": "roles:assign", "resource": "roles", "action": "assign", "description": "Assign roles to users"},
    # Venue management
    {"id": PERMISSION_IDS["venues:create"], "name": "venues:create", "resource": "venues", "action": "create", "description": "Create new venues"},
    {"id": PERMISSION_IDS["venues:read"], "name": "venues:read", "resource": "venues", "action": "read", "description": "View venue details"},
    {"id": PERMISSION_IDS["venues:update"], "name": "venues:update", "resource": "venues", "action": "update", "description": "Update venue settings"},
    {"id": PERMISSION_IDS["venues:delete"], "name": "venues:delete", "resource": "venues", "action": "delete", "description": "Delete venues"},
    {"id": PERMISSION_IDS["venues:list"], "name": "venues:list", "resource": "venues", "action": "list", "description": "List all venues"},
    # Privacy/GDPR
    {"id": PERMISSION_IDS["privacy:read"], "name": "privacy:read", "resource": "privacy", "action": "read", "description": "View privacy consents"},
    {"id": PERMISSION_IDS["privacy:update"], "name": "privacy:update", "resource": "privacy", "action": "update", "description": "Update privacy consents"},
    {"id": PERMISSION_IDS["privacy:export"], "name": "privacy:export", "resource": "privacy", "action": "export", "description": "Export user data (GDPR)"},
    {"id": PERMISSION_IDS["privacy:delete"], "name": "privacy:delete", "resource": "privacy", "action": "delete", "description": "Delete user data (GDPR right to be forgotten)"},
    # Sessions
    {"id": PERMISSION_IDS["sessions:read"], "name": "sessions:read", "resource": "sessions", "action": "read", "description": "View active sessions"},
    {"id": PERMISSION_IDS["sessions:delete"], "name": "sessions:delete", "resource": "sessions", "action": "delete", "description": "Terminate sessions"},
    # Admin operations
    {"id": PERMISSION_IDS["admin:system"], "name": "admin:system", "resource": "admin", "action": "system", "description": "System-level administrative operations"},
    {"id": PERMISSION_IDS["admin:audit"], "name": "admin:audit", "resource": "admin", "action": "audit", "description": "View audit logs"},
    # Customer operations
    {"id": PERMISSION_IDS["profile:read"], "name": "profile:read", "resource": "profile", "action": "read", "description": "View own profile"},
    {"id": PERMISSION_IDS["profile:update"], "name": "profile:update", "resource": "profile", "action": "update", "description": "Update own profile"},
    # Staff operations
    {"id": PERMISSION_IDS["orders:read"], "name": "orders:read", "resource": "orders", "action": "read", "description": "View orders"},
    {"id": PERMISSION_IDS["orders:create"], "name": "orders:create", "resource": "orders", "action": "create", "description": "Create orders"},
    {"id": PERMISSION_IDS["orders:update"], "name": "orders:update", "resource": "orders", "action": "update", "description": "Update orders"},
    {"id": PERMISSION_IDS["reservations:read"], "name": "reservations:read", "resource": "reservations", "action": "read", "description": "View reservations"},
    {"id": PERMISSION_IDS["reservations:create"], "name": "reservations:create", "resource": "reservations", "action": "create", "description": "Create reservations"},
    {"id": PERMISSION_IDS["reservations:update"], "name": "reservations:update", "resource": "reservations", "action": "update", "description": "Update reservations"},
]

# Role-permission mappings
ROLE_PERMISSION_MAPPINGS = {
    # Super Admin - all permissions
    "super_admin": list(PERMISSION_IDS.keys()),
    # Venue Owner - venue management, user management (limited), staff operations
    "venue_owner": [
        "users:create", "users:read", "users:update", "users:list",
        "roles:read", "roles:assign",
        "venues:read", "venues:update", "venues:list",
        "privacy:read", "privacy:export",
        "sessions:read", "sessions:delete",
        "admin:audit",
        "profile:read", "profile:update",
        "orders:read", "orders:create", "orders:update",
        "reservations:read", "reservations:create", "reservations:update",
    ],
    # Manager - operations management
    "manager": [
        "users:read", "users:list",
        "roles:read",
        "venues:read",
        "sessions:read",
        "profile:read", "profile:update",
        "orders:read", "orders:create", "orders:update",
        "reservations:read", "reservations:create", "reservations:update",
    ],
    # Staff - limited operations
    "staff": [
        "venues:read",
        "profile:read", "profile:update",
        "orders:read", "orders:create", "orders:update",
        "reservations:read", "reservations:create", "reservations:update",
    ],
    # Customer - self-service only
    "customer": [
        "profile:read", "profile:update",
        "privacy:read", "privacy:update", "privacy:export", "privacy:delete",
        "sessions:read",
        "reservations:read", "reservations:create",
    ],
}


def upgrade() -> None:
    # Insert roles
    op.bulk_insert(roles_table, ROLES)

    # Insert permissions
    op.bulk_insert(permissions_table, PERMISSIONS)

    # Insert role-permission mappings
    role_permissions = []
    for role_key, permission_keys in ROLE_PERMISSION_MAPPINGS.items():
        role_id = ROLE_IDS[role_key]
        for perm_key in permission_keys:
            role_permissions.append({
                "role_id": role_id,
                "permission_id": PERMISSION_IDS[perm_key],
            })

    op.bulk_insert(role_permissions_table, role_permissions)


def downgrade() -> None:
    # Delete role-permission mappings
    op.execute(role_permissions_table.delete())

    # Delete permissions
    op.execute(permissions_table.delete())

    # Delete roles
    op.execute(roles_table.delete())
