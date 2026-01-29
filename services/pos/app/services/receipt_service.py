"""Receipt generation and delivery service for POS transactions."""

import random
import string
import uuid
from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy import select
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
    Receipt,
    Transaction,
    TransactionStatus,
)
from app.schemas.pos import ReceiptEmailRequest, ReceiptGenerateRequest
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()


def _generate_receipt_number() -> str:
    """Generate a unique receipt number in the format FEC-YYYYMMDD-6CHARS."""
    date_part = datetime.utcnow().strftime("%Y%m%d")
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"FEC-{date_part}-{random_part}"


class ReceiptService:
    """Service for generating, retrieving, and delivering POS receipts."""

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

    async def _get_receipt(self, receipt_id: uuid.UUID) -> Receipt:
        """Fetch a receipt by ID or raise NOT_FOUND."""
        result = await self.db.execute(
            select(Receipt).where(Receipt.id == receipt_id)
        )
        receipt = result.scalars().first()
        if not receipt:
            raise not_found(
                ErrorCode.RECEIPT_NOT_FOUND,
                f"Receipt {receipt_id} not found",
            )
        return receipt

    async def _get_payments_for_transaction(
        self, transaction_id: uuid.UUID
    ) -> list:
        """Return completed payments for a transaction."""
        result = await self.db.execute(
            select(Payment)
            .where(
                Payment.transaction_id == transaction_id,
                Payment.status == PaymentStatus.COMPLETED.value,
            )
            .order_by(Payment.created_at.asc())
        )
        return list(result.scalars().all())

    def _build_receipt_data(
        self, transaction: Transaction, payments: list
    ) -> dict:
        """Build the JSONB receipt_data payload from a transaction and its payments."""
        return {
            "transaction_id": str(transaction.id),
            "venue_id": str(transaction.venue_id),
            "transaction_type": transaction.transaction_type,
            "status": transaction.status,
            "subtotal": str(transaction.subtotal),
            "tax_amount": str(transaction.tax_amount),
            "tip_amount": str(transaction.tip_amount),
            "discount_amount": str(transaction.discount_amount),
            "total_amount": str(transaction.total_amount),
            "currency": transaction.currency,
            "created_at": transaction.created_at.isoformat(),
            "payments": [
                {
                    "payment_id": str(p.id),
                    "payment_method": p.payment_method,
                    "amount": str(p.amount),
                    "card_last_four": p.card_last_four,
                    "card_brand": p.card_brand,
                    "approval_code": p.approval_code,
                }
                for p in payments
            ],
        }

    # ─── Core Methods ────────────────────────────────────────────────────────

    async def generate_receipt(
        self,
        transaction_id: uuid.UUID,
        venue_id: uuid.UUID,
        data: ReceiptGenerateRequest,
    ) -> Receipt:
        """Generate a receipt for a transaction.

        Steps:
        1. Validate the transaction exists.
        2. Generate a unique receipt number (FEC-YYYYMMDD-6CHARS).
        3. Build receipt_data JSONB from transaction and completed payments.
        4. Create the Receipt record.
        5. Publish a RECEIPT_GENERATED event.
        """
        # 1. Validate transaction
        transaction = await self._get_transaction(transaction_id)

        # 2. Generate unique receipt number
        receipt_number = _generate_receipt_number()

        # 3. Build receipt data from transaction + payments
        payments = await self._get_payments_for_transaction(transaction_id)
        receipt_data = self._build_receipt_data(transaction, payments)

        # 4. Create receipt record
        receipt = Receipt(
            transaction_id=transaction_id,
            venue_id=venue_id,
            receipt_number=receipt_number,
            receipt_type=data.receipt_type.value if hasattr(data.receipt_type, "value") else data.receipt_type,
            receipt_data=receipt_data,
        )
        self.db.add(receipt)
        await self.db.commit()
        await self.db.refresh(receipt)

        logger.info(
            "receipt_generated",
            receipt_id=str(receipt.id),
            receipt_number=receipt_number,
            transaction_id=str(transaction_id),
            venue_id=str(venue_id),
            receipt_type=receipt.receipt_type,
        )

        # 5. Publish event
        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.RECEIPT_GENERATED,
                {
                    "receipt_id": str(receipt.id),
                    "receipt_number": receipt_number,
                    "transaction_id": str(transaction_id),
                    "venue_id": str(venue_id),
                    "receipt_type": receipt.receipt_type,
                },
                venue_id=venue_id,
            )

        return receipt

    # ─── Read Methods ────────────────────────────────────────────────────────

    async def get_receipt(self, receipt_id: uuid.UUID) -> Receipt:
        """Retrieve a single receipt by ID."""
        return await self._get_receipt(receipt_id)

    async def get_receipt_by_number(self, receipt_number: str) -> Receipt:
        """Retrieve a receipt by its unique receipt number."""
        result = await self.db.execute(
            select(Receipt).where(Receipt.receipt_number == receipt_number)
        )
        receipt = result.scalars().first()
        if not receipt:
            raise not_found(
                ErrorCode.RECEIPT_NOT_FOUND,
                f"Receipt with number {receipt_number} not found",
            )
        return receipt

    # ─── Delivery Methods ────────────────────────────────────────────────────

    async def email_receipt(
        self,
        receipt_id: uuid.UUID,
        data: ReceiptEmailRequest,
    ) -> Receipt:
        """Record that a receipt was emailed to a customer.

        Updates emailed_to and emailed_at fields and publishes
        a RECEIPT_EMAILED event.
        """
        receipt = await self._get_receipt(receipt_id)

        receipt.emailed_to = data.email
        receipt.emailed_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(receipt)

        logger.info(
            "receipt_emailed",
            receipt_id=str(receipt_id),
            receipt_number=receipt.receipt_number,
            emailed_to=data.email,
        )

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.RECEIPT_EMAILED,
                {
                    "receipt_id": str(receipt.id),
                    "receipt_number": receipt.receipt_number,
                    "transaction_id": str(receipt.transaction_id),
                    "venue_id": str(receipt.venue_id),
                    "emailed_to": data.email,
                },
                venue_id=receipt.venue_id,
            )

        return receipt

    async def mark_printed(self, receipt_id: uuid.UUID) -> Receipt:
        """Mark a receipt as printed by setting the printed_at timestamp."""
        receipt = await self._get_receipt(receipt_id)

        receipt.printed_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(receipt)

        logger.info(
            "receipt_printed",
            receipt_id=str(receipt_id),
            receipt_number=receipt.receipt_number,
        )

        return receipt
