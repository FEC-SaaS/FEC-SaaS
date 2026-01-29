"""
=============================================================================
FILE: api/v1/audit_logs.py
PURPOSE: API routes for accessing POS audit logs
=============================================================================

Provides read-only RESTful endpoints for querying the POS audit trail.
Audit logs are created automatically by the system during operations
and cannot be modified or deleted through the API, ensuring an immutable
compliance record.

Endpoints:
    GET /pos/audit-logs              - List audit logs with filtering
    GET /pos/audit-logs/entity/{type}/{id} - Get complete history for an entity

Key Features:
    - Immutable audit trail for compliance and security
    - Flexible filtering by entity type, action, actor, and date range
    - Complete entity history tracking for forensic analysis
    - Pagination support for large result sets
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.pos import AuditAction
from app.schemas.pos import AuditLogResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/pos/audit-logs")


def _get_service(db: AsyncSession = Depends(get_db)) -> AuditService:
    """
    Dependency injection for AuditService.

    Creates a new AuditService instance with the current database session
    for querying audit log records.

    Args:
        db: Async database session from dependency injection.

    Returns:
        Configured AuditService instance.
    """
    return AuditService(db)


# ---------------------------------------------------------------------------
# GET /pos/audit-logs - List audit logs with filtering
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=List[AuditLogResponse],
    summary="List audit logs with filtering",
    responses={
        200: {"description": "List of audit logs matching criteria"},
        401: {"description": "Authentication required"},
    },
)
async def list_audit_logs(
    venue_id: UUID = Query(
        ...,
        description="UUID of the venue to query audit logs for",
    ),
    entity_type: Optional[str] = Query(
        None,
        description=(
            "Filter by entity type (e.g., 'transaction', 'payment', "
            "'refund', 'cash_drawer', 'shift', 'tax_rate', 'discount')"
        ),
    ),
    entity_id: Optional[UUID] = Query(
        None,
        description="Filter by specific entity UUID",
    ),
    action: Optional[str] = Query(
        None,
        description=(
            "Filter by action type: create, update, delete, void, refund, "
            "approve, reject, status_change, payment_process, drawer_open, drawer_close"
        ),
    ),
    actor_id: Optional[UUID] = Query(
        None,
        description="Filter by the user who performed the action (from JWT sub claim)",
    ),
    date_from: Optional[datetime] = Query(
        None,
        description="Filter logs created on or after this datetime (inclusive)",
    ),
    date_to: Optional[datetime] = Query(
        None,
        description="Filter logs created on or before this datetime (inclusive)",
    ),
    skip: int = Query(
        0,
        ge=0,
        description="Number of records to skip for pagination",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=500,
        description="Maximum number of records to return (max 500)",
    ),
    current_user: dict = Depends(get_current_user),
    service: AuditService = Depends(_get_service),
) -> List[AuditLogResponse]:
    """
    List audit logs for a venue with optional filtering.

    Retrieves audit log entries matching the specified criteria, ordered by
    creation time (newest first). Supports flexible filtering for compliance
    reporting, security investigations, and operational analysis.

    Args:
        venue_id: UUID of the venue to query logs for. Required to scope
            results to a specific venue.
        entity_type: Optional filter by the type of entity being audited.
            Common values include:
            - "transaction": POS transactions
            - "payment": Payment records
            - "refund": Refund requests
            - "cash_drawer": Cash drawer sessions
            - "shift": Employee shifts
            - "tax_rate": Tax configurations
            - "discount": Discount rules
        entity_id: Optional filter by a specific entity's UUID. Use with
            entity_type for targeted lookups.
        action: Optional filter by the action performed. Valid values:
            - "create": Entity was created
            - "update": Entity was modified
            - "delete": Entity was deleted
            - "void": Transaction was voided
            - "refund": Refund was processed
            - "approve": Action was approved (e.g., refund approval)
            - "reject": Action was rejected
            - "status_change": Entity status changed
            - "payment_process": Payment was processed
            - "drawer_open": Cash drawer was opened
            - "drawer_close": Cash drawer was closed
        actor_id: Optional filter by the user who performed the action.
            Useful for user activity audits.
        date_from: Optional start of date range (inclusive).
        date_to: Optional end of date range (inclusive).
        skip: Pagination offset (default: 0).
        limit: Maximum results to return (default: 100, max: 500).
        current_user: Authenticated user from JWT token.
        service: Injected AuditService instance.

    Returns:
        List of AuditLogResponse objects containing:
        - id: Unique audit log identifier
        - venue_id: Associated venue
        - entity_type: Type of entity audited
        - entity_id: Specific entity UUID
        - action: Action that was performed
        - actor_id: User who performed action (if known)
        - actor_name: Display name of actor (if known)
        - old_values: Previous values before change (for updates)
        - new_values: New values after change
        - ip_address: Client IP address
        - user_agent: Client user agent
        - metadata: Additional context data
        - created_at: When the action occurred

    Example Request:
        GET /pos/audit-logs?venue_id=...&entity_type=transaction&action=void

    Example Response:
        [
            {
                "id": "...",
                "venue_id": "...",
                "entity_type": "transaction",
                "entity_id": "...",
                "action": "void",
                "actor_id": "...",
                "actor_name": "John Manager",
                "old_values": {"status": "completed"},
                "new_values": {"status": "voided"},
                "ip_address": "192.168.1.100",
                "created_at": "2024-01-15T14:32:00Z"
            }
        ]

    Use Cases:
        1. Compliance audit: List all actions for a date range
        2. Security review: Find all actions by a specific user
        3. Troubleshooting: Track all changes to a specific entity
        4. Fraud detection: Monitor void and refund patterns
    """
    # Convert string action to enum if provided
    audit_action = None
    if action:
        try:
            audit_action = AuditAction(action)
        except ValueError:
            # Invalid action, will return empty results
            pass

    logs = await service.get_audit_logs(
        venue_id=venue_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=audit_action,
        actor_id=actor_id,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return [AuditLogResponse.model_validate(log) for log in logs]


# ---------------------------------------------------------------------------
# GET /pos/audit-logs/entity/{entity_type}/{entity_id} - Entity history
# ---------------------------------------------------------------------------
@router.get(
    "/entity/{entity_type}/{entity_id}",
    response_model=List[AuditLogResponse],
    summary="Get complete audit history for a specific entity",
    responses={
        200: {"description": "Complete audit history for the entity"},
        401: {"description": "Authentication required"},
    },
)
async def get_entity_history(
    venue_id: UUID = Query(
        ...,
        description="UUID of the venue the entity belongs to",
    ),
    entity_type: str = Path(
        ...,
        description=(
            "Type of entity to retrieve history for (e.g., 'transaction', "
            "'payment', 'refund', 'cash_drawer', 'shift')"
        ),
    ),
    entity_id: UUID = Path(
        ...,
        description="UUID of the specific entity to retrieve history for",
    ),
    current_user: dict = Depends(get_current_user),
    service: AuditService = Depends(_get_service),
) -> List[AuditLogResponse]:
    """
    Get the complete audit history for a specific entity.

    Retrieves all audit log entries for a particular entity in chronological
    order (oldest first), providing a complete timeline of all changes made
    to that entity from creation through all subsequent modifications.

    This endpoint is particularly useful for:
    - Investigating issues with a specific record
    - Compliance audits requiring full change history
    - Debugging data discrepancies
    - Understanding the lifecycle of an entity

    Args:
        venue_id: UUID of the venue the entity belongs to. Required for
            security scoping.
        entity_type: Type of the entity being queried. Common values:
            - "transaction": POS transaction records
            - "payment": Payment records
            - "refund": Refund requests
            - "cash_drawer": Cash drawer sessions
            - "shift": Employee shifts
            - "tax_rate": Tax rate configurations
            - "discount": Discount rules
            - "line_item": Transaction line items
            - "reconciliation": Daily reconciliations
        entity_id: UUID of the specific entity to retrieve history for.
        current_user: Authenticated user from JWT token.
        service: Injected AuditService instance.

    Returns:
        List of AuditLogResponse objects in chronological order (oldest first),
        showing the complete history of changes to the entity.

    Example Request:
        GET /pos/audit-logs/entity/transaction/550e8400-e29b-41d4-a716-446655440000?venue_id=...

    Example Response:
        [
            {
                "id": "...",
                "entity_type": "transaction",
                "entity_id": "550e8400-e29b-41d4-a716-446655440000",
                "action": "create",
                "new_values": {"total": "45.00", "status": "pending"},
                "created_at": "2024-01-15T10:00:00Z"
            },
            {
                "id": "...",
                "entity_type": "transaction",
                "entity_id": "550e8400-e29b-41d4-a716-446655440000",
                "action": "status_change",
                "old_values": {"status": "pending"},
                "new_values": {"status": "completed"},
                "created_at": "2024-01-15T10:05:00Z"
            },
            {
                "id": "...",
                "entity_type": "transaction",
                "entity_id": "550e8400-e29b-41d4-a716-446655440000",
                "action": "void",
                "old_values": {"status": "completed"},
                "new_values": {"status": "voided"},
                "actor_name": "Manager Smith",
                "created_at": "2024-01-15T10:30:00Z"
            }
        ]

    Note:
        Results are returned in chronological order (oldest to newest) to
        facilitate reading the entity's history as a timeline. This differs
        from the list_audit_logs endpoint which returns newest first.
    """
    logs = await service.get_entity_history(
        venue_id=venue_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    return [AuditLogResponse.model_validate(log) for log in logs]
