"""
=============================================================================
FILE: services/reconciliation_service.py
PURPOSE: Daily financial reconciliation business logic
=============================================================================

Handles creation, completion, and querying of end-of-day reconciliation
records. Aggregates completed transactions, breaks down totals by payment
method, and publishes events for downstream consumption.
"""

import uuid
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import List, Optional, Tuple

import structlog
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ErrorCode,
    bad_request,
    conflict,
    not_found,
)
from app.models.pos import (
    DailyReconciliation,
    Payment,
    PaymentMethod,
    PaymentStatus,
    ReconciliationStatus,
    Refund,
    RefundStatus,
    Transaction,
    TransactionStatus,
)
from app.schemas.pos import ReconciliationCreate
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()

# Variance threshold (absolute value) for discrepancy alerts
RECONCILIATION_VARIANCE_THRESHOLD = Decimal("10.00")


class ReconciliationService:
    """Service for daily financial reconciliation."""

    def __init__(
        self,
        db: AsyncSession,
        event_publisher: Optional[EventPublisher] = None,
    ):
        self.db = db
        self.event_publisher = event_publisher

    # =========================================================================
    # Create & Complete
    # =========================================================================

    async def create_daily_reconciliation(
        self,
        venue_id: uuid.UUID,
        data: ReconciliationCreate,
    ) -> DailyReconciliation:
        """
        Create a daily reconciliation for a venue and date.

        Aggregates all completed transactions for the requested date,
        calculates financial totals, and breaks them down by payment
        method.

        Args:
            venue_id: Venue UUID.
            data: Payload containing the reconciliation_date.

        Returns:
            The newly created DailyReconciliation record.

        Raises:
            ServiceError: If a reconciliation already exists for this date.
        """
        # Ensure no duplicate reconciliation for this date
        existing = await self.get_reconciliation_by_date(venue_id, data.reconciliation_date)
        if existing:
            raise conflict(
                ErrorCode.RECONCILIATION_ALREADY_EXISTS,
                f"Reconciliation already exists for venue {venue_id} "
                f"on {data.reconciliation_date}",
            )

        # Aggregate completed transactions for the date
        recon_date = data.reconciliation_date
        summary = await self._aggregate_transactions(venue_id, recon_date)
        payment_breakdown = await self._aggregate_payments_by_method(venue_id, recon_date)
        total_refunds = await self._aggregate_refunds(venue_id, recon_date)

        reconciliation = DailyReconciliation(
            venue_id=venue_id,
            reconciliation_date=recon_date,
            status=ReconciliationStatus.PENDING.value,
            total_transactions=summary["total_transactions"],
            gross_sales=summary["gross_sales"],
            net_sales=summary["net_sales"],
            total_tax=summary["total_tax"],
            total_tips=summary["total_tips"],
            total_discounts=summary["total_discounts"],
            total_refunds=total_refunds,
            cash_total=payment_breakdown.get("cash", Decimal("0")),
            card_total=payment_breakdown.get("card", Decimal("0")),
            other_total=payment_breakdown.get("other", Decimal("0")),
            variance_amount=Decimal("0"),
        )
        self.db.add(reconciliation)
        await self.db.commit()
        await self.db.refresh(reconciliation)

        logger.info(
            "reconciliation_created",
            reconciliation_id=str(reconciliation.id),
            venue_id=str(venue_id),
            reconciliation_date=str(recon_date),
            total_transactions=summary["total_transactions"],
            gross_sales=str(summary["gross_sales"]),
        )

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.RECONCILIATION_CREATED,
                {
                    "reconciliation_id": str(reconciliation.id),
                    "venue_id": str(venue_id),
                    "reconciliation_date": str(recon_date),
                    "total_transactions": summary["total_transactions"],
                    "gross_sales": str(summary["gross_sales"]),
                    "net_sales": str(summary["net_sales"]),
                },
                venue_id=venue_id,
            )

        return reconciliation

    async def complete_reconciliation(
        self,
        reconciliation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> DailyReconciliation:
        """
        Mark a reconciliation as completed (manager sign-off).

        Sets reconciled_by, reconciled_at, and status. If the variance
        exceeds the threshold a discrepancy event is published.

        Args:
            reconciliation_id: UUID of the reconciliation.
            user_id: UUID of the user completing the reconciliation.

        Returns:
            The updated DailyReconciliation record.

        Raises:
            ServiceError: If not found or not in PENDING status.
        """
        reconciliation = await self.get_reconciliation(reconciliation_id)

        if reconciliation.status != ReconciliationStatus.PENDING.value:
            raise bad_request(
                ErrorCode.RECONCILIATION_ALREADY_COMPLETED,
                f"Reconciliation {reconciliation_id} is not pending "
                f"(current status: {reconciliation.status})",
            )

        reconciliation.reconciled_by = user_id
        reconciliation.reconciled_at = datetime.utcnow()
        reconciliation.status = ReconciliationStatus.COMPLETED.value

        await self.db.commit()
        await self.db.refresh(reconciliation)

        logger.info(
            "reconciliation_completed",
            reconciliation_id=str(reconciliation_id),
            venue_id=str(reconciliation.venue_id),
            reconciled_by=str(user_id),
        )

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.RECONCILIATION_COMPLETED,
                {
                    "reconciliation_id": str(reconciliation.id),
                    "venue_id": str(reconciliation.venue_id),
                    "reconciliation_date": str(reconciliation.reconciliation_date),
                    "reconciled_by": str(user_id),
                },
                venue_id=reconciliation.venue_id,
            )

            # Publish discrepancy alert if variance exceeds threshold
            if abs(reconciliation.variance_amount) > RECONCILIATION_VARIANCE_THRESHOLD:
                await self.event_publisher.publish(
                    EventType.RECONCILIATION_DISCREPANCY,
                    {
                        "reconciliation_id": str(reconciliation.id),
                        "venue_id": str(reconciliation.venue_id),
                        "reconciliation_date": str(reconciliation.reconciliation_date),
                        "variance_amount": str(reconciliation.variance_amount),
                        "variance_details": reconciliation.variance_details,
                    },
                    venue_id=reconciliation.venue_id,
                )

        return reconciliation

    # =========================================================================
    # Read helpers
    # =========================================================================

    async def get_reconciliation(
        self,
        reconciliation_id: uuid.UUID,
    ) -> DailyReconciliation:
        """
        Get a reconciliation by ID.

        Args:
            reconciliation_id: UUID of the reconciliation.

        Returns:
            DailyReconciliation instance.

        Raises:
            ServiceError: If not found.
        """
        result = await self.db.execute(
            select(DailyReconciliation).where(
                DailyReconciliation.id == reconciliation_id
            )
        )
        reconciliation = result.scalars().first()
        if not reconciliation:
            raise not_found(
                ErrorCode.RECONCILIATION_NOT_FOUND,
                f"Reconciliation {reconciliation_id} not found",
            )
        return reconciliation

    async def get_reconciliation_by_date(
        self,
        venue_id: uuid.UUID,
        recon_date: date_type,
    ) -> Optional[DailyReconciliation]:
        """
        Get a reconciliation for a specific venue and date.

        Args:
            venue_id: Venue UUID.
            recon_date: The reconciliation date.

        Returns:
            DailyReconciliation if one exists, otherwise None.
        """
        result = await self.db.execute(
            select(DailyReconciliation).where(
                and_(
                    DailyReconciliation.venue_id == venue_id,
                    DailyReconciliation.reconciliation_date == recon_date,
                )
            )
        )
        return result.scalars().first()

    async def list_reconciliations(
        self,
        venue_id: uuid.UUID,
        status: Optional[str] = None,
        date_from: Optional[date_type] = None,
        date_to: Optional[date_type] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[DailyReconciliation], int]:
        """
        List reconciliations with filtering and pagination.

        Args:
            venue_id: Venue UUID.
            status: Optional reconciliation status filter.
            date_from: Optional start date filter.
            date_to: Optional end date filter.
            page: Page number (1-based).
            page_size: Items per page.

        Returns:
            Tuple of (reconciliations list, total count).
        """
        query = select(DailyReconciliation).where(
            DailyReconciliation.venue_id == venue_id
        )

        if status:
            query = query.where(DailyReconciliation.status == status)
        if date_from:
            query = query.where(DailyReconciliation.reconciliation_date >= date_from)
        if date_to:
            query = query.where(DailyReconciliation.reconciliation_date <= date_to)

        # Total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results
        query = query.order_by(DailyReconciliation.reconciliation_date.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        reconciliations = list(result.scalars().all())

        logger.info(
            "reconciliations_listed",
            venue_id=str(venue_id),
            total=total,
            page=page,
        )
        return reconciliations, total

    # =========================================================================
    # Internal aggregation helpers
    # =========================================================================

    async def _aggregate_transactions(
        self,
        venue_id: uuid.UUID,
        recon_date: date_type,
    ) -> dict:
        """
        Aggregate completed transaction totals for a venue on a given date.

        Returns a dict with keys: total_transactions, gross_sales,
        net_sales, total_tax, total_tips, total_discounts.
        """
        base_filter = and_(
            Transaction.venue_id == venue_id,
            Transaction.status == TransactionStatus.COMPLETED.value,
            func.date(Transaction.created_at) == recon_date,
        )

        agg_query = select(
            func.count(Transaction.id).label("total_transactions"),
            func.coalesce(func.sum(Transaction.subtotal), Decimal("0")).label("gross_sales"),
            func.coalesce(func.sum(Transaction.total_amount), Decimal("0")).label("net_sales"),
            func.coalesce(func.sum(Transaction.tax_amount), Decimal("0")).label("total_tax"),
            func.coalesce(func.sum(Transaction.tip_amount), Decimal("0")).label("total_tips"),
            func.coalesce(func.sum(Transaction.discount_amount), Decimal("0")).label("total_discounts"),
        ).where(base_filter)

        result = await self.db.execute(agg_query)
        row = result.one()

        return {
            "total_transactions": row.total_transactions,
            "gross_sales": row.gross_sales,
            "net_sales": row.net_sales,
            "total_tax": row.total_tax,
            "total_tips": row.total_tips,
            "total_discounts": row.total_discounts,
        }

    async def _aggregate_payments_by_method(
        self,
        venue_id: uuid.UUID,
        recon_date: date_type,
    ) -> dict:
        """
        Break down completed payments by method category (cash, card, other).

        Returns a dict with keys: cash, card, other.
        """
        card_methods = {
            PaymentMethod.CREDIT_CARD.value,
            PaymentMethod.DEBIT_CARD.value,
        }

        payment_query = (
            select(
                Payment.payment_method,
                func.coalesce(func.sum(Payment.amount), Decimal("0")).label("total"),
            )
            .join(Transaction, Transaction.id == Payment.transaction_id)
            .where(
                and_(
                    Transaction.venue_id == venue_id,
                    Transaction.status == TransactionStatus.COMPLETED.value,
                    func.date(Transaction.created_at) == recon_date,
                    Payment.status == PaymentStatus.COMPLETED.value,
                )
            )
            .group_by(Payment.payment_method)
        )

        result = await self.db.execute(payment_query)
        rows = result.all()

        cash = Decimal("0")
        card = Decimal("0")
        other = Decimal("0")

        for row in rows:
            if row.payment_method == PaymentMethod.CASH.value:
                cash += row.total
            elif row.payment_method in card_methods:
                card += row.total
            else:
                other += row.total

        return {"cash": cash, "card": card, "other": other}

    async def _aggregate_refunds(
        self,
        venue_id: uuid.UUID,
        recon_date: date_type,
    ) -> Decimal:
        """
        Sum all processed refunds for a venue on a given date.
        """
        refund_query = select(
            func.coalesce(func.sum(Refund.refund_amount), Decimal("0"))
        ).where(
            and_(
                Refund.venue_id == venue_id,
                Refund.status == RefundStatus.PROCESSED.value,
                func.date(Refund.processed_at) == recon_date,
            )
        )

        result = await self.db.execute(refund_query)
        return result.scalar() or Decimal("0")
