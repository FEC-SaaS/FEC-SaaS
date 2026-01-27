"""
=============================================================================
FILE: services/refund_service.py
PURPOSE: Refund processing service
=============================================================================
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import (
    PaymentTransaction,
    PaymentRefund,
    TransactionStatus,
    RefundType,
    RefundStatus,
)
from app.schemas.payment import (
    RefundRequest,
    RefundResponse,
    RefundListResponse,
)
from app.services.payment_service import PaymentService

logger = structlog.get_logger()


class RefundService:
    """Service for processing refunds."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.payment_service = PaymentService(db)

    async def create_refund(
        self,
        transaction_id: UUID,
        request: RefundRequest,
        user_id: Optional[UUID] = None,
    ) -> RefundResponse:
        """Process a refund for a transaction."""
        # Get original transaction
        transaction = await self._get_transaction(transaction_id)

        # Validate transaction can be refunded
        if transaction.status not in [TransactionStatus.COMPLETED, TransactionStatus.CAPTURED]:
            raise ValueError(
                f"Transaction {transaction_id} cannot be refunded (status: {transaction.status.value})"
            )

        # Calculate refund amount
        refund_amount = request.amount or transaction.amount

        # Check available refund amount
        existing_refunds = await self._get_existing_refunds(transaction_id)
        total_refunded = sum(r.refund_amount for r in existing_refunds if r.status == RefundStatus.COMPLETED)
        available_amount = transaction.amount - total_refunded

        if refund_amount > available_amount:
            raise ValueError(
                f"Refund amount ({refund_amount}) exceeds available amount ({available_amount})"
            )

        # Determine refund type
        refund_type = RefundType.FULL if refund_amount == available_amount else RefundType.PARTIAL

        # Create refund record
        refund = PaymentRefund(
            id=uuid4(),
            original_payment_id=transaction_id,
            refund_amount=refund_amount,
            refund_reason=request.reason,
            refund_type=refund_type,
            status=RefundStatus.PENDING,
            notes=request.notes,
            extra_metadata=request.metadata,
            initiated_by=user_id,
        )
        self.db.add(refund)
        await self.db.flush()

        # Process refund with payment processor
        processor, _ = await self.payment_service.get_processor(transaction.venue_id)

        result = await processor.refund(
            transaction_id=transaction.processor_transaction_id,
            amount=refund_amount,
            reason=request.reason,
        )

        # Update refund status
        if result.success:
            refund.status = RefundStatus.COMPLETED
            refund.processor_refund_id = result.refund_id
            refund.processed_at = datetime.utcnow()

            # Update original transaction status if fully refunded
            if total_refunded + refund_amount >= transaction.amount:
                transaction.status = TransactionStatus.REFUNDED
                transaction.refunded_amount = transaction.amount
            else:
                transaction.status = TransactionStatus.PARTIALLY_REFUNDED
                transaction.refunded_amount = total_refunded + refund_amount
        else:
            refund.status = RefundStatus.FAILED
            refund.failure_reason = result.error_message

        await self.db.flush()

        logger.info(
            "refund_processed",
            refund_id=str(refund.id),
            transaction_id=str(transaction_id),
            amount=float(refund_amount),
            success=result.success,
        )

        return RefundResponse.model_validate(refund)

    async def get_refund(self, refund_id: UUID) -> RefundResponse:
        """Get a refund by ID."""
        result = await self.db.execute(
            select(PaymentRefund).where(PaymentRefund.id == refund_id)
        )
        refund = result.scalar_one_or_none()
        if not refund:
            raise ValueError(f"Refund {refund_id} not found")
        return RefundResponse.model_validate(refund)

    async def list_refunds(
        self,
        venue_id: UUID,
        transaction_id: Optional[UUID] = None,
    ) -> RefundListResponse:
        """List refunds for a venue or transaction."""
        query = (
            select(PaymentRefund)
            .join(PaymentTransaction)
            .where(PaymentTransaction.venue_id == venue_id)
        )

        if transaction_id:
            query = query.where(PaymentRefund.original_payment_id == transaction_id)

        query = query.order_by(PaymentRefund.created_at.desc())

        result = await self.db.execute(query)
        refunds = result.scalars().all()

        return RefundListResponse(
            refunds=[RefundResponse.model_validate(r) for r in refunds],
            total=len(refunds),
        )

    async def _get_transaction(self, transaction_id: UUID) -> PaymentTransaction:
        """Get a transaction by ID."""
        result = await self.db.execute(
            select(PaymentTransaction).where(PaymentTransaction.id == transaction_id)
        )
        transaction = result.scalar_one_or_none()
        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found")
        return transaction

    async def _get_existing_refunds(self, transaction_id: UUID) -> List[PaymentRefund]:
        """Get existing refunds for a transaction."""
        result = await self.db.execute(
            select(PaymentRefund).where(
                PaymentRefund.original_payment_id == transaction_id
            )
        )
        return list(result.scalars().all())
