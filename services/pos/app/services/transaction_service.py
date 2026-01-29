"""Core transaction service for POS Integration."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ErrorCode,
    ServiceError,
    bad_request,
    conflict,
    not_found,
)
from app.models.pos import (
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.schemas.pos import TransactionCreate
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()


class TransactionService:
    """Service for managing POS transactions."""

    def __init__(
        self,
        db: AsyncSession,
        event_publisher: Optional[EventPublisher] = None,
    ):
        self.db = db
        self.event_publisher = event_publisher

    # --- Idempotency --------------------------------------------------------

    async def _check_idempotency(
        self, idempotency_key: Optional[str], venue_id: uuid.UUID
    ) -> Optional[Transaction]:
        """Return existing transaction if the idempotency key was already used."""
        if not idempotency_key:
            return None

        result = await self.db.execute(
            select(Transaction).where(
                and_(
                    Transaction.idempotency_key == idempotency_key,
                    Transaction.venue_id == venue_id,
                )
            )
        )
        return result.scalars().first()

    # --- Validation ---------------------------------------------------------

    @staticmethod
    def _validate_amounts(data: TransactionCreate) -> None:
        """Ensure total = subtotal + tax - discount + tip."""
        expected_total = data.subtotal + data.tax - data.discount + data.tip
        if data.total != expected_total:
            raise bad_request(
                ErrorCode.TRANSACTION_AMOUNT_MISMATCH,
                (
                    f"Total ({data.total}) does not match "
                    f"subtotal ({data.subtotal}) + tax ({data.tax}) "
                    f"- discount ({data.discount}) + tip ({data.tip}) "
                    f"= {expected_total}"
                ),
            )

    # --- CRUD ---------------------------------------------------------------

    async def list_transactions(
        self,
        venue_id: uuid.UUID,
        transaction_type: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        customer_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Transaction], int]:
        """List transactions with filtering and pagination."""
        query = select(Transaction).where(Transaction.venue_id == venue_id)

        if transaction_type:
            query = query.where(Transaction.transaction_type == transaction_type)
        if status:
            query = query.where(Transaction.status == status)
        if date_from:
            query = query.where(Transaction.created_at >= date_from)
        if date_to:
            query = query.where(Transaction.created_at <= date_to)
        if customer_id:
            query = query.where(Transaction.customer_id == customer_id)

        # Total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results
        query = query.order_by(Transaction.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        transactions = list(result.scalars().all())

        logger.info(
            "transactions_listed",
            venue_id=str(venue_id),
            total=total,
            page=page,
        )
        return transactions, total

    async def get_transaction(self, transaction_id: uuid.UUID) -> Transaction:
        """Get a single transaction by ID."""
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

    async def create_transaction(
        self,
        venue_id: uuid.UUID,
        data: TransactionCreate,
        idempotency_key: Optional[str] = None,
    ) -> Transaction:
        """Create a new transaction with validation and idempotency."""

        # 1. Idempotency check
        existing = await self._check_idempotency(idempotency_key, venue_id)
        if existing:
            logger.info(
                "transaction_idempotent_return",
                transaction_id=str(existing.id),
                idempotency_key=idempotency_key,
            )
            return existing

        # 2. Validate amounts
        self._validate_amounts(data)

        # 3. Create transaction with PENDING status
        transaction = Transaction(
            venue_id=venue_id,
            customer_id=data.customer_id,
            transaction_type=data.transaction_type,
            status=TransactionStatus.PENDING.value,
            subtotal=data.subtotal,
            tax=data.tax,
            discount=data.discount,
            tip=data.tip,
            total=data.total,
            currency=data.currency,
            cashier_id=data.cashier_id,
            terminal_id=data.terminal_id,
            notes=data.notes,
            idempotency_key=idempotency_key,
        )
        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(transaction)

        logger.info(
            "transaction_created",
            transaction_id=str(transaction.id),
            venue_id=str(venue_id),
            transaction_type=data.transaction_type,
            total=str(data.total),
            idempotency_key=idempotency_key,
        )

        # 4. Publish event
        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.TRANSACTION_CREATED,
                {
                    "transaction_id": str(transaction.id),
                    "venue_id": str(venue_id),
                    "transaction_type": data.transaction_type,
                    "total": str(data.total),
                    "currency": data.currency,
                    "cashier_id": str(data.cashier_id) if data.cashier_id else None,
                },
                venue_id=venue_id,
            )

        return transaction

    async def complete_transaction(
        self, transaction_id: uuid.UUID
    ) -> Transaction:
        """Complete a pending transaction."""
        transaction = await self.get_transaction(transaction_id)

        if transaction.status != TransactionStatus.PENDING.value:
            raise bad_request(
                ErrorCode.TRANSACTION_INVALID_STATUS,
                f"Cannot complete transaction with status {transaction.status}. "
                f"Must be {TransactionStatus.PENDING.value}.",
            )

        transaction.status = TransactionStatus.COMPLETED.value
        await self.db.commit()
        await self.db.refresh(transaction)

        logger.info(
            "transaction_completed",
            transaction_id=str(transaction_id),
            venue_id=str(transaction.venue_id),
        )

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.TRANSACTION_COMPLETED,
                {
                    "transaction_id": str(transaction.id),
                    "venue_id": str(transaction.venue_id),
                    "total": str(transaction.total),
                },
                venue_id=transaction.venue_id,
            )

        return transaction

    async def void_transaction(
        self, transaction_id: uuid.UUID, cashier_id: uuid.UUID
    ) -> Transaction:
        """Void a transaction. Only PENDING or COMPLETED transactions can be voided."""
        transaction = await self.get_transaction(transaction_id)

        if transaction.status in (
            TransactionStatus.VOIDED.value,
            TransactionStatus.REFUNDED.value,
        ):
            raise bad_request(
                ErrorCode.TRANSACTION_ALREADY_FINAL,
                f"Transaction is already {transaction.status} and cannot be voided.",
            )

        if transaction.status not in (
            TransactionStatus.PENDING.value,
            TransactionStatus.COMPLETED.value,
        ):
            raise bad_request(
                ErrorCode.TRANSACTION_INVALID_STATUS,
                f"Cannot void transaction with status {transaction.status}. "
                f"Must be {TransactionStatus.PENDING.value} or {TransactionStatus.COMPLETED.value}.",
            )

        transaction.status = TransactionStatus.VOIDED.value
        transaction.voided_by = cashier_id
        transaction.voided_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(transaction)

        logger.info(
            "transaction_voided",
            transaction_id=str(transaction_id),
            venue_id=str(transaction.venue_id),
            cashier_id=str(cashier_id),
        )

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.TRANSACTION_VOIDED,
                {
                    "transaction_id": str(transaction.id),
                    "venue_id": str(transaction.venue_id),
                    "total": str(transaction.total),
                    "voided_by": str(cashier_id),
                },
                venue_id=transaction.venue_id,
            )

        return transaction

    async def get_transaction_summary(
        self,
        venue_id: uuid.UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Return aggregate transaction summary for a venue within the date range."""

        # Base filter: venue + non-voided/refunded transactions
        base_filter = and_(
            Transaction.venue_id == venue_id,
            Transaction.status == TransactionStatus.COMPLETED.value,
        )
        if date_from:
            base_filter = and_(base_filter, Transaction.created_at >= date_from)
        if date_to:
            base_filter = and_(base_filter, Transaction.created_at <= date_to)

        # Aggregate query
        agg_query = select(
            func.count(Transaction.id).label("total_transactions"),
            func.coalesce(func.sum(Transaction.subtotal), Decimal("0")).label("gross_sales"),
            func.coalesce(func.sum(Transaction.total), Decimal("0")).label("net_sales"),
            func.coalesce(func.sum(Transaction.tax), Decimal("0")).label("total_tax"),
            func.coalesce(func.sum(Transaction.tip), Decimal("0")).label("total_tips"),
            func.coalesce(func.sum(Transaction.discount), Decimal("0")).label("total_discounts"),
        ).where(base_filter)

        agg_result = await self.db.execute(agg_query)
        row = agg_result.one()

        # Breakdown by transaction type
        type_query = (
            select(
                Transaction.transaction_type,
                func.count(Transaction.id).label("count"),
                func.coalesce(func.sum(Transaction.total), Decimal("0")).label("total"),
            )
            .where(base_filter)
            .group_by(Transaction.transaction_type)
        )
        type_result = await self.db.execute(type_query)
        by_type = [
            {
                "transaction_type": r.transaction_type,
                "count": r.count,
                "total": str(r.total),
            }
            for r in type_result.all()
        ]

        summary = {
            "total_transactions": row.total_transactions,
            "gross_sales": str(row.gross_sales),
            "net_sales": str(row.net_sales),
            "total_tax": str(row.total_tax),
            "total_tips": str(row.total_tips),
            "total_discounts": str(row.total_discounts),
            "by_type": by_type,
        }

        logger.info(
            "transaction_summary_generated",
            venue_id=str(venue_id),
            total_transactions=row.total_transactions,
            date_from=str(date_from) if date_from else None,
            date_to=str(date_to) if date_to else None,
        )

        return summary
