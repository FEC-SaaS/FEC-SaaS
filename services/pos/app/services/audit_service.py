"""
=============================================================================
FILE: services/audit_service.py
PURPOSE: Audit logging service for POS operations
=============================================================================

Provides comprehensive audit logging for all POS operations including
transactions, payments, refunds, cash drawers, and other entities.
Records who did what, when, and tracks both old and new values for
all changes.

Key features:
- Immutable audit trail for compliance
- Automatic context extraction from HTTP requests
- Support for create, update, delete, and status change operations
- Flexible querying and filtering of audit history
- Entity-level history tracking
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog
from fastapi import Request
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pos import AuditAction, AuditLog
from app.schemas.pos import AuditLogResponse

logger = structlog.get_logger()


@dataclass
class AuditContext:
    """
    Context information for audit logging.

    Captures information about who performed an action and from where,
    enabling full traceability of all operations.

    Attributes:
        actor_id: UUID of the user who performed the action (from JWT sub claim).
        actor_name: Display name of the user (from JWT name claim).
        ip_address: IP address of the client making the request.
        user_agent: User-Agent header from the HTTP request.
    """
    actor_id: Optional[UUID] = None
    actor_name: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


def get_audit_context(
    request: Request,
    current_user: Optional[Dict[str, Any]] = None,
) -> AuditContext:
    """
    Extract audit context from a FastAPI request.

    This helper function builds an AuditContext from the current HTTP request
    and optional user information from the JWT token.

    Args:
        request: The FastAPI Request object.
        current_user: Optional dictionary containing user claims from the JWT.
            Expected keys: "sub" (user ID), "name" (display name).

    Returns:
        AuditContext populated with available information.

    Example:
        ```python
        @router.post("/transactions")
        async def create_transaction(
            request: Request,
            current_user: dict = Depends(get_current_user),
        ):
            context = get_audit_context(request, current_user)
            await audit_service.log_create(
                venue_id=venue_id,
                entity_type="transaction",
                entity_id=transaction.id,
                new_values={"total": str(transaction.total)},
                context=context,
            )
        ```
    """
    actor_id = None
    actor_name = None

    if current_user:
        # Extract user ID from 'sub' claim (standard JWT claim for subject)
        sub = current_user.get("sub")
        if sub:
            try:
                actor_id = UUID(str(sub)) if not isinstance(sub, UUID) else sub
            except (ValueError, TypeError):
                logger.warning("invalid_actor_id_in_jwt", sub=sub)

        actor_name = current_user.get("name")

    # Extract client IP address
    ip_address = None
    if request.client:
        ip_address = request.client.host

    # Extract User-Agent header
    user_agent = request.headers.get("user-agent")

    return AuditContext(
        actor_id=actor_id,
        actor_name=actor_name,
        ip_address=ip_address,
        user_agent=user_agent,
    )


class AuditService:
    """
    Service for managing POS audit logs.

    Provides methods for logging various types of operations (create, update,
    delete, status changes) and querying audit history. All audit logs are
    immutable once created.

    Attributes:
        db: Async SQLAlchemy session for database operations.

    Example:
        ```python
        audit_service = AuditService(db)

        # Log a transaction creation
        await audit_service.log_create(
            venue_id=venue_id,
            entity_type="transaction",
            entity_id=transaction.id,
            new_values={"total": "100.00", "status": "pending"},
            context=context,
        )

        # Log a status change
        await audit_service.log_status_change(
            venue_id=venue_id,
            entity_type="transaction",
            entity_id=transaction.id,
            old_status="pending",
            new_status="completed",
            context=context,
        )
        ```
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the AuditService.

        Args:
            db: Async SQLAlchemy session for database operations.
        """
        self.db = db

    async def log(
        self,
        venue_id: UUID,
        entity_type: str,
        entity_id: UUID,
        action: AuditAction,
        context: Optional[AuditContext] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Create an audit log entry.

        This is the core logging method that all other convenience methods
        use internally. It creates an immutable audit record with all
        provided information.

        Args:
            venue_id: UUID of the venue where the action occurred.
            entity_type: Type of entity being audited (e.g., "transaction",
                "payment", "refund", "cash_drawer").
            entity_id: UUID of the specific entity instance.
            action: The type of action performed (from AuditAction enum).
            context: Optional AuditContext with actor and request information.
            old_values: Optional dictionary of values before the change.
            new_values: Optional dictionary of values after the change.
            metadata: Optional additional metadata to store with the log.

        Returns:
            The created AuditLog record.

        Example:
            ```python
            audit_log = await audit_service.log(
                venue_id=venue_id,
                entity_type="payment",
                entity_id=payment.id,
                action=AuditAction.PAYMENT_PROCESS,
                context=context,
                new_values={
                    "amount": "50.00",
                    "method": "credit_card",
                    "processor_id": "ch_xxx",
                },
                metadata={"terminal_id": "pos-001"},
            )
            ```
        """
        # Build audit log entry
        audit_log = AuditLog(
            venue_id=venue_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action.value,
            old_values=old_values,
            new_values=new_values,
            metadata_=metadata,
        )

        # Add context information if provided
        if context:
            audit_log.actor_id = context.actor_id
            audit_log.actor_name = context.actor_name
            audit_log.ip_address = context.ip_address
            audit_log.user_agent = context.user_agent

        self.db.add(audit_log)
        await self.db.commit()
        await self.db.refresh(audit_log)

        logger.info(
            "audit_log_created",
            audit_log_id=str(audit_log.id),
            venue_id=str(venue_id),
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action.value,
            actor_id=str(context.actor_id) if context and context.actor_id else None,
        )

        return audit_log

    async def log_create(
        self,
        venue_id: UUID,
        entity_type: str,
        entity_id: UUID,
        new_values: Dict[str, Any],
        context: Optional[AuditContext] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Log an entity creation.

        Convenience method for logging CREATE actions. Records the initial
        values of a newly created entity.

        Args:
            venue_id: UUID of the venue where the entity was created.
            entity_type: Type of entity being created.
            entity_id: UUID of the newly created entity.
            new_values: Dictionary of the entity's initial values.
            context: Optional AuditContext with actor and request information.
            metadata: Optional additional metadata to store.

        Returns:
            The created AuditLog record.

        Example:
            ```python
            await audit_service.log_create(
                venue_id=venue_id,
                entity_type="transaction",
                entity_id=transaction.id,
                new_values={
                    "total": str(transaction.total_amount),
                    "status": transaction.status,
                    "transaction_type": transaction.transaction_type,
                },
                context=context,
            )
            ```
        """
        return await self.log(
            venue_id=venue_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=AuditAction.CREATE,
            context=context,
            old_values=None,
            new_values=new_values,
            metadata=metadata,
        )

    async def log_update(
        self,
        venue_id: UUID,
        entity_type: str,
        entity_id: UUID,
        old_values: Dict[str, Any],
        new_values: Dict[str, Any],
        context: Optional[AuditContext] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Log an entity update.

        Convenience method for logging UPDATE actions. Records both the
        old and new values to enable full change tracking.

        Args:
            venue_id: UUID of the venue where the entity was updated.
            entity_type: Type of entity being updated.
            entity_id: UUID of the updated entity.
            old_values: Dictionary of values before the update.
            new_values: Dictionary of values after the update.
            context: Optional AuditContext with actor and request information.
            metadata: Optional additional metadata to store.

        Returns:
            The created AuditLog record.

        Example:
            ```python
            await audit_service.log_update(
                venue_id=venue_id,
                entity_type="tax_rate",
                entity_id=tax_rate.id,
                old_values={"rate": "0.0825", "name": "Sales Tax"},
                new_values={"rate": "0.0850", "name": "Sales Tax"},
                context=context,
            )
            ```
        """
        return await self.log(
            venue_id=venue_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=AuditAction.UPDATE,
            context=context,
            old_values=old_values,
            new_values=new_values,
            metadata=metadata,
        )

    async def log_delete(
        self,
        venue_id: UUID,
        entity_type: str,
        entity_id: UUID,
        old_values: Dict[str, Any],
        context: Optional[AuditContext] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Log an entity deletion.

        Convenience method for logging DELETE actions. Records the entity's
        final values before deletion for compliance and recovery purposes.

        Args:
            venue_id: UUID of the venue where the entity was deleted.
            entity_type: Type of entity being deleted.
            entity_id: UUID of the deleted entity.
            old_values: Dictionary of the entity's values before deletion.
            context: Optional AuditContext with actor and request information.
            metadata: Optional additional metadata to store.

        Returns:
            The created AuditLog record.

        Example:
            ```python
            await audit_service.log_delete(
                venue_id=venue_id,
                entity_type="discount",
                entity_id=discount.id,
                old_values={
                    "code": "SUMMER20",
                    "value": "20.00",
                    "discount_type": "percentage",
                },
                context=context,
            )
            ```
        """
        return await self.log(
            venue_id=venue_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=AuditAction.DELETE,
            context=context,
            old_values=old_values,
            new_values=None,
            metadata=metadata,
        )

    async def log_status_change(
        self,
        venue_id: UUID,
        entity_type: str,
        entity_id: UUID,
        old_status: str,
        new_status: str,
        context: Optional[AuditContext] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Log a status change on an entity.

        Convenience method for logging STATUS_CHANGE actions. This is
        commonly used for workflow state transitions (e.g., transaction
        pending -> completed, refund pending -> approved).

        Args:
            venue_id: UUID of the venue where the status changed.
            entity_type: Type of entity whose status changed.
            entity_id: UUID of the entity.
            old_status: The previous status value.
            new_status: The new status value.
            context: Optional AuditContext with actor and request information.
            metadata: Optional additional metadata to store.

        Returns:
            The created AuditLog record.

        Example:
            ```python
            await audit_service.log_status_change(
                venue_id=venue_id,
                entity_type="refund",
                entity_id=refund.id,
                old_status="pending",
                new_status="approved",
                context=context,
                metadata={"approved_by_manager": True},
            )
            ```
        """
        return await self.log(
            venue_id=venue_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=AuditAction.STATUS_CHANGE,
            context=context,
            old_values={"status": old_status},
            new_values={"status": new_status},
            metadata=metadata,
        )

    async def get_audit_logs(
        self,
        venue_id: UUID,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        action: Optional[AuditAction] = None,
        actor_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Query audit logs with flexible filtering.

        Retrieves audit logs for a venue with optional filters for entity type,
        entity ID, action type, actor, and date range. Results are ordered by
        creation time (newest first).

        Args:
            venue_id: UUID of the venue to query logs for.
            entity_type: Optional filter by entity type.
            entity_id: Optional filter by specific entity ID.
            action: Optional filter by action type (from AuditAction enum).
            actor_id: Optional filter by the user who performed the action.
            date_from: Optional filter for logs after this datetime.
            date_to: Optional filter for logs before this datetime.
            skip: Number of records to skip (for pagination). Default 0.
            limit: Maximum number of records to return. Default 100.

        Returns:
            List of AuditLog records matching the criteria.

        Example:
            ```python
            # Get all transaction audit logs for the past week
            logs = await audit_service.get_audit_logs(
                venue_id=venue_id,
                entity_type="transaction",
                date_from=datetime.utcnow() - timedelta(days=7),
            )

            # Get all actions by a specific user
            user_logs = await audit_service.get_audit_logs(
                venue_id=venue_id,
                actor_id=user_id,
            )
            ```
        """
        query = select(AuditLog).where(AuditLog.venue_id == venue_id)

        # Apply optional filters
        if entity_type:
            query = query.where(AuditLog.entity_type == entity_type)

        if entity_id:
            query = query.where(AuditLog.entity_id == entity_id)

        if action:
            query = query.where(AuditLog.action == action.value)

        if actor_id:
            query = query.where(AuditLog.actor_id == actor_id)

        if date_from:
            query = query.where(AuditLog.created_at >= date_from)

        if date_to:
            query = query.where(AuditLog.created_at <= date_to)

        # Order by newest first
        query = query.order_by(AuditLog.created_at.desc())

        # Apply pagination
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        logs = list(result.scalars().all())

        logger.info(
            "audit_logs_queried",
            venue_id=str(venue_id),
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            action=action.value if action else None,
            result_count=len(logs),
        )

        return logs

    async def get_entity_history(
        self,
        venue_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> List[AuditLog]:
        """
        Get the complete audit history for a specific entity.

        Retrieves all audit logs for a specific entity, ordered chronologically
        (oldest first) to show the complete history of changes.

        Args:
            venue_id: UUID of the venue the entity belongs to.
            entity_type: Type of the entity.
            entity_id: UUID of the specific entity.

        Returns:
            List of AuditLog records in chronological order (oldest first).

        Example:
            ```python
            # Get full history of a transaction
            history = await audit_service.get_entity_history(
                venue_id=venue_id,
                entity_type="transaction",
                entity_id=transaction_id,
            )

            for log in history:
                print(f"{log.created_at}: {log.action}")
                if log.old_values:
                    print(f"  Before: {log.old_values}")
                if log.new_values:
                    print(f"  After: {log.new_values}")
            ```
        """
        query = (
            select(AuditLog)
            .where(
                and_(
                    AuditLog.venue_id == venue_id,
                    AuditLog.entity_type == entity_type,
                    AuditLog.entity_id == entity_id,
                )
            )
            .order_by(AuditLog.created_at.asc())  # Chronological order
        )

        result = await self.db.execute(query)
        logs = list(result.scalars().all())

        logger.info(
            "entity_history_retrieved",
            venue_id=str(venue_id),
            entity_type=entity_type,
            entity_id=str(entity_id),
            log_count=len(logs),
        )

        return logs

    async def count_audit_logs(
        self,
        venue_id: UUID,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        action: Optional[AuditAction] = None,
        actor_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> int:
        """
        Count audit logs matching the given criteria.

        Useful for pagination or analytics. Accepts the same filters as
        get_audit_logs but returns only the count.

        Args:
            venue_id: UUID of the venue to count logs for.
            entity_type: Optional filter by entity type.
            entity_id: Optional filter by specific entity ID.
            action: Optional filter by action type.
            actor_id: Optional filter by actor.
            date_from: Optional filter for logs after this datetime.
            date_to: Optional filter for logs before this datetime.

        Returns:
            Integer count of matching audit logs.

        Example:
            ```python
            # Count all void operations today
            void_count = await audit_service.count_audit_logs(
                venue_id=venue_id,
                action=AuditAction.VOID,
                date_from=datetime.combine(date.today(), time.min),
            )
            ```
        """
        query = select(func.count(AuditLog.id)).where(AuditLog.venue_id == venue_id)

        if entity_type:
            query = query.where(AuditLog.entity_type == entity_type)

        if entity_id:
            query = query.where(AuditLog.entity_id == entity_id)

        if action:
            query = query.where(AuditLog.action == action.value)

        if actor_id:
            query = query.where(AuditLog.actor_id == actor_id)

        if date_from:
            query = query.where(AuditLog.created_at >= date_from)

        if date_to:
            query = query.where(AuditLog.created_at <= date_to)

        result = await self.db.execute(query)
        count = result.scalar() or 0

        return count
