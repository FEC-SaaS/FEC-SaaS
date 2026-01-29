"""Refund processing service for POS transactions."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import (
    ErrorCode,
    ServiceError,
    bad_request,
    not_found,
)
from app.models.pos import (
    Refund,
    RefundStatus,
    Transaction,
    TransactionStatus,
)
from app.schemas.pos import RefundApprove, RefundCreate
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()


class RefundService:
    """Service for processing and managing refunds against POS transactions."""

    def __init__(
        self,
        db: AsyncSession,
        event_publisher: Optional[EventPublisher] = None,
    ):
        self.db = db
        self.event_publisher = event_publisher

    # ─── Helpers ─────────────────────────────────────────────────────────────

    async def _get_transaction(self, transaction_id: uuid.UUID) -> Transaction:
        """Fetch a transaction by ID or raise NOT_FOUND."""
        result = await self.db.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        transaction = result.scalars().first()
        if not transaction:
            raise not_found(
                ErrorCode.TRANSACTION_NOT_FOUND,
                f"Transaction {transaction_id} not found",
            )
        return transaction

    async def _get_refund(self, refund_id: uuid.UUID) -> Refund:
        """Fetch a refund by ID or raise NOT_FOUND."""
        result = await self.db.execute(
            select(Refund).where(Refund.id == refund_id)
        )
        refund = result.scalars().first()
        if not refund:
            raise not_found(
                ErrorCode.REFUND_NOT_FOUND,
                f"Refund {refund_id} not found",
            )
        return refund

    async def _sum_existing_refunds(self, transaction_id: uuid.UUID) -> Decimal:
        """Return total refund amount for non-rejected refunds on a transaction."""
        result = await self.db.execute(
            select(func.coalesce(func.sum(Refund.refund_amount), 0)).where(
                and_(
                    Refund.transaction_id == transaction_id,
                    Refund.status != RefundStatus.REJECTED.value,
                )
            )
        )
        return Decimal(str(result.scalar() or 0))

    # ─── Core Methods ────────────────────────────────────────────────────────

    async def issue_refund(
        self,
        transaction_id: uuid.UUID,
        venue_id: uuid.UUID,
        data: RefundCreate,
    ) -> Refund:
        """Issue a refund against an existing transaction.

        Steps:
        1. Validate the transaction exists and is COMPLETED.
        2. Validate the refund amount does not exceed the original total
           minus any existing refunds.
        3. Check the refund period has not expired (MAX_REFUND_DAYS).
        4. Create a Refund record with PENDING status.
        5. Publish a REFUND_ISSUED event.
        """
        settings = get_settings()

        # 1. Validate transaction exists and is completed
        transaction = await self._get_transaction(transaction_id)

        if transaction.status != TransactionStatus.COMPLETED.value:
            raise bad_request(
                ErrorCode.TRANSACTION_INVALID_STATUS,
                f"Cannot refund transaction with status {transaction.status}. "
                f"Must be {TransactionStatus.COMPLETED.value}.",
            )

        # 2. Validate refund amount does not exceed remaining refundable amount
        existing_refunds_total = await self._sum_existing_refunds(transaction_id)
        remaining = transaction.total_amount - existing_refunds_total

        if data.refund_amount > remaining:
            raise bad_request(
                ErrorCode.REFUND_EXCEEDS_ORIGINAL,
                f"Refund amount ({data.refund_amount}) exceeds remaining "
                f"refundable amount ({remaining}). Original total: "
                f"{transaction.total_amount}, already refunded: {existing_refunds_total}.",
            )

        # 3. Check refund period
        refund_deadline = transaction.created_at + timedelta(days=settings.MAX_REFUND_DAYS)
        if datetime.utcnow() > refund_deadline:
            raise bad_request(
                ErrorCode.REFUND_PERIOD_EXPIRED,
                f"Refund period of {settings.MAX_REFUND_DAYS} days has expired. "
                f"Transaction was created on {transaction.created_at.isoformat()}.",
            )

        # 4. Create refund record with PENDING status
        refund = Refund(
            transaction_id=transaction_id,
            venue_id=venue_id,
            refund_amount=data.refund_amount,
            refund_reason=data.refund_reason.value if hasattr(data.refund_reason, "value") else data.refund_reason,
            refund_method=data.refund_method.value if hasattr(data.refund_method, "value") else data.refund_method,
            status=RefundStatus.PENDING.value,
            notes=data.notes,
        )
        self.db.add(refund)
        await self.db.commit()
        await self.db.refresh(refund)

        logger.info(
            "refund_issued",
            refund_id=str(refund.id),
            transaction_id=str(transaction_id),
            venue_id=str(venue_id),
            amount=str(data.refund_amount),
            reason=refund.refund_reason,
        )

        # 5. Publish event
        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.REFUND_ISSUED,
                {
                    "refund_id": str(refund.id),
                    "transaction_id": str(transaction_id),
                    "venue_id": str(venue_id),
                    "refund_amount": str(refund.refund_amount),
                    "refund_reason": refund.refund_reason,
                    "refund_method": refund.refund_method,
                },
                venue_id=venue_id,
            )

        return refund

    async def approve_refund(
        self,
        refund_id: uuid.UUID,
        data: RefundApprove,
    ) -> Refund:
        """Approve a pending refund.

        Sets approved_by and transitions status from PENDING to APPROVED.
        """
        refund = await self._get_refund(refund_id)

        if refund.status != RefundStatus.PENDING.value:
            raise bad_request(
                ErrorCode.REFUND_ALREADY_PROCESSED,
                f"Cannot approve refund with status {refund.status}. "
                f"Must be {RefundStatus.PENDING.value}.",
            )

        refund.status = RefundStatus.APPROVED.value
        refund.approved_by = data.approved_by
        await self.db.commit()
        await self.db.refresh(refund)

        logger.info(
            "refund_approved",
            refund_id=str(refund_id),
            transaction_id=str(refund.transaction_id),
            approved_by=str(data.approved_by),
        )

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.REFUND_APPROVED,
                {
                    "refund_id": str(refund.id),
                    "transaction_id": str(refund.transaction_id),
                    "venue_id": str(refund.venue_id),
                    "refund_amount": str(refund.refund_amount),
                    "approved_by": str(data.approved_by),
                },
                venue_id=refund.venue_id,
            )

        return refund

    async def process_refund(self, refund_id: uuid.UUID) -> Refund:
        """Process an approved refund.

        Steps:
        1. Validate the refund is APPROVED.
        2. Set status to PROCESSED and record processed_at timestamp.
        3. Update the parent transaction status to REFUNDED or
           PARTIALLY_REFUNDED based on total refunds vs original amount.
        4. Publish event.
        """
        refund = await self._get_refund(refund_id)

        if refund.status != RefundStatus.APPROVED.value:
            raise bad_request(
                ErrorCode.REFUND_ALREADY_PROCESSED,
                f"Cannot process refund with status {refund.status}. "
                f"Must be {RefundStatus.APPROVED.value}.",
            )

        # 1. Mark refund as processed
        refund.status = RefundStatus.PROCESSED.value
        refund.processed_at = datetime.utcnow()
        await self.db.flush()

        # 2. Update transaction status based on total refunds
        transaction = await self._get_transaction(refund.transaction_id)
        total_processed_refunds = await self._sum_processed_refunds(refund.transaction_id)

        if total_processed_refunds >= transaction.total_amount:
            transaction.status = TransactionStatus.REFUNDED.value
        else:
            transaction.status = TransactionStatus.PARTIALLY_REFUNDED.value

        await self.db.commit()
        await self.db.refresh(refund)

        logger.info(
            "refund_processed",
            refund_id=str(refund_id),
            transaction_id=str(refund.transaction_id),
            venue_id=str(refund.venue_id),
            transaction_status=transaction.status,
            total_refunded=str(total_processed_refunds),
        )

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.REFUND_APPROVED,
                {
                    "refund_id": str(refund.id),
                    "transaction_id": str(refund.transaction_id),
                    "venue_id": str(refund.venue_id),
                    "refund_amount": str(refund.refund_amount),
                    "transaction_status": transaction.status,
                },
                venue_id=refund.venue_id,
            )

        return refund

    async def _sum_processed_refunds(self, transaction_id: uuid.UUID) -> Decimal:
        """Return total amount of PROCESSED refunds for a transaction."""
        result = await self.db.execute(
            select(func.coalesce(func.sum(Refund.refund_amount), 0)).where(
                and_(
                    Refund.transaction_id == transaction_id,
                    Refund.status == RefundStatus.PROCESSED.value,
                )
            )
        )
        return Decimal(str(result.scalar() or 0))

    # ─── Read Methods ────────────────────────────────────────────────────────

    async def get_refund(self, refund_id: uuid.UUID) -> Refund:
        """Retrieve a single refund by ID."""
        return await self._get_refund(refund_id)

    async def list_refunds(
        self,
        venue_id: uuid.UUID,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Refund], int]:
        """List refunds for a venue with optional filtering and pagination."""
        query = select(Refund).where(Refund.venue_id == venue_id)

        if status:
            query = query.where(Refund.status == status)
        if date_from:
            query = query.where(Refund.created_at >= date_from)
        if date_to:
            query = query.where(Refund.created_at <= date_to)

        # Total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results
        query = query.order_by(Refund.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        refunds = list(result.scalars().all())

        logger.info(
            "refunds_listed",
            venue_id=str(venue_id),
            total=total,
            page=page,
        )
        return refunds, total
