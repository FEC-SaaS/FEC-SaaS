"""Payment processing service for POS transactions."""

import random
import string
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ErrorCode,
    ServiceError,
    bad_request,
    not_found,
)
from app.models.pos import (
    Payment,
    PaymentStatus,
    Transaction,
    TransactionStatus,
)
from app.schemas.pos import PaymentCreate
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()


def _generate_approval_code() -> str:
    """Generate a random 6-character uppercase alphanumeric approval code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


class PaymentService:
    """Service for processing payments against POS transactions."""

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

    async def _sum_completed_payments(self, transaction_id: uuid.UUID) -> Decimal:
        """Return the total amount of COMPLETED payments for a transaction."""
        result = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                and_(
                    Payment.transaction_id == transaction_id,
                    Payment.status == PaymentStatus.COMPLETED.value,
                )
            )
        )
        return Decimal(str(result.scalar() or 0))

    # ─── Core Methods ────────────────────────────────────────────────────────

    async def process_payment(
        self,
        transaction_id: uuid.UUID,
        venue_id: uuid.UUID,
        data: PaymentCreate,
    ) -> Payment:
        """Process a payment against an existing transaction.

        Steps:
        1. Validate the transaction exists and is in a payable state.
        2. Create a Payment record with PENDING status.
        3. Simulate payment processing (set to COMPLETED with approval code).
        4. If the cumulative payments meet or exceed the transaction total,
           auto-complete the transaction.
        5. Publish a PAYMENT_PROCESSED event.
        """
        # 1. Validate transaction
        transaction = await self._get_transaction(transaction_id)

        if transaction.status not in (
            TransactionStatus.PENDING.value,
            TransactionStatus.COMPLETED.value,
        ):
            raise bad_request(
                ErrorCode.TRANSACTION_NOT_PAYABLE,
                f"Transaction is {transaction.status} and cannot accept payments",
            )

        # 2. Create payment record
        payment = Payment(
            transaction_id=transaction_id,
            venue_id=venue_id,
            amount=data.amount,
            payment_method=data.payment_method,
            status=PaymentStatus.PENDING.value,
            reference=data.reference,
        )
        self.db.add(payment)
        await self.db.flush()

        logger.info(
            "payment_created",
            payment_id=str(payment.id),
            transaction_id=str(transaction_id),
            amount=str(data.amount),
            method=data.payment_method,
        )

        # 3. Simulate processing -- mark as COMPLETED with an approval code
        payment.status = PaymentStatus.COMPLETED.value
        payment.approval_code = _generate_approval_code()
        payment.processed_at = datetime.utcnow()

        await self.db.flush()

        logger.info(
            "payment_processed",
            payment_id=str(payment.id),
            approval_code=payment.approval_code,
        )

        # 4. Auto-complete the transaction when fully paid
        total_paid = await self._sum_completed_payments(transaction_id)
        if transaction.total_amount is not None and total_paid >= transaction.total_amount:
            transaction.status = TransactionStatus.COMPLETED.value
            logger.info(
                "transaction_auto_completed",
                transaction_id=str(transaction_id),
                total_paid=str(total_paid),
            )

        await self.db.commit()
        await self.db.refresh(payment)

        # 5. Publish event
        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.PAYMENT_PROCESSED,
                {
                    "payment_id": str(payment.id),
                    "transaction_id": str(transaction_id),
                    "amount": str(payment.amount),
                    "payment_method": payment.payment_method,
                    "approval_code": payment.approval_code,
                },
                venue_id=venue_id,
            )

        return payment

    async def get_payment(self, payment_id: uuid.UUID) -> Payment:
        """Retrieve a single payment by ID."""
        result = await self.db.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalars().first()
        if not payment:
            raise not_found(
                ErrorCode.PAYMENT_NOT_FOUND,
                f"Payment {payment_id} not found",
            )
        return payment

    async def list_payments_for_transaction(
        self, transaction_id: uuid.UUID
    ) -> List[Payment]:
        """Return all payments associated with a transaction."""
        result = await self.db.execute(
            select(Payment)
            .where(Payment.transaction_id == transaction_id)
            .order_by(Payment.created_at.asc())
        )
        payments = list(result.scalars().all())

        logger.info(
            "payments_listed",
            transaction_id=str(transaction_id),
            count=len(payments),
        )
        return payments

    async def reverse_payment(self, payment_id: uuid.UUID) -> Payment:
        """Reverse a completed payment.

        Only payments with COMPLETED status can be reversed.
        """
        payment = await self.get_payment(payment_id)

        if payment.status != PaymentStatus.COMPLETED.value:
            raise bad_request(
                ErrorCode.PAYMENT_NOT_REVERSIBLE,
                f"Cannot reverse payment with status {payment.status}. "
                "Only COMPLETED payments can be reversed.",
            )

        payment.status = PaymentStatus.REVERSED.value
        await self.db.commit()
        await self.db.refresh(payment)

        logger.info(
            "payment_reversed",
            payment_id=str(payment_id),
            transaction_id=str(payment.transaction_id),
        )

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.PAYMENT_REVERSED,
                {
                    "payment_id": str(payment.id),
                    "transaction_id": str(payment.transaction_id),
                    "amount": str(payment.amount),
                    "payment_method": payment.payment_method,
                },
                venue_id=payment.venue_id,
            )

        return payment

    async def get_payment_summary(
        self,
        venue_id: uuid.UUID,
        date_from: datetime,
        date_to: datetime,
    ) -> Dict[str, Any]:
        """Return a payment summary grouped by payment method for a venue and date range.

        Returns:
            Dictionary mapping each payment method to its count and total amount::

                {
                    "CASH":        {"count": 12, "total": "340.50"},
                    "CREDIT_CARD": {"count": 45, "total": "2310.00"},
                    ...
                }
        """
        result = await self.db.execute(
            select(
                Payment.payment_method,
                func.count().label("count"),
                func.coalesce(func.sum(Payment.amount), 0).label("total"),
            )
            .where(
                and_(
                    Payment.venue_id == venue_id,
                    Payment.status == PaymentStatus.COMPLETED.value,
                    Payment.created_at >= date_from,
                    Payment.created_at <= date_to,
                )
            )
            .group_by(Payment.payment_method)
        )

        summary: Dict[str, Any] = {}
        for row in result.all():
            summary[row.payment_method] = {
                "count": row.count,
                "total": str(row.total),
            }

        logger.info(
            "payment_summary_generated",
            venue_id=str(venue_id),
            date_from=str(date_from),
            date_to=str(date_to),
            methods=list(summary.keys()),
        )

        return summary
