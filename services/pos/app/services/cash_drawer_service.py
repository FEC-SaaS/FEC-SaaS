"""
=============================================================================
FILE: services/cash_drawer_service.py
PURPOSE: Cash drawer session management business logic
=============================================================================

Handles the full lifecycle of cash drawer sessions including opening,
closing, cash drops, variance calculation, and alerting.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ErrorCode,
    bad_request,
    conflict,
    not_found,
)
from app.models.pos import (
    CashDrawer,
    CashDrawerStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Transaction,
    TransactionStatus,
)
from app.schemas.pos import (
    CashDropRequest,
    DrawerCloseRequest,
    DrawerOpenRequest,
)
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()

# Maximum acceptable variance (absolute value) before an alert is raised
VARIANCE_THRESHOLD = Decimal("5.00")


class CashDrawerService:
    """Service for managing cash drawer sessions."""

    def __init__(
        self,
        db: AsyncSession,
        event_publisher: Optional[EventPublisher] = None,
    ):
        self.db = db
        self.event_publisher = event_publisher

    # =========================================================================
    # Open / Close / Cash Drop
    # =========================================================================

    async def open_drawer(
        self,
        venue_id: uuid.UUID,
        cashier_id: uuid.UUID,
        data: DrawerOpenRequest,
    ) -> CashDrawer:
        """
        Open a new cash drawer session.

        Validates that no drawer is already open for the given terminal,
        creates the session with OPEN status, and publishes an event.

        Args:
            venue_id: Venue this drawer belongs to.
            cashier_id: Cashier opening the drawer.
            data: Request payload containing terminal_id and opening_cash.

        Returns:
            The newly created CashDrawer record.

        Raises:
            ServiceError: If a drawer is already open on this terminal.
        """
        # Ensure no open drawer exists for this terminal
        existing = await self.get_open_drawer(venue_id, data.terminal_id)
        if existing:
            raise conflict(
                ErrorCode.DRAWER_ALREADY_OPEN,
                f"A drawer is already open on terminal {data.terminal_id}",
            )

        drawer = CashDrawer(
            venue_id=venue_id,
            terminal_id=data.terminal_id,
            cashier_id=cashier_id,
            status=CashDrawerStatus.OPEN.value,
            opened_at=datetime.utcnow(),
            opening_cash=data.opening_cash,
            cash_drops_total=Decimal("0"),
            drawer_transactions=[],
        )
        self.db.add(drawer)
        await self.db.commit()
        await self.db.refresh(drawer)

        logger.info(
            "drawer_opened",
            drawer_id=str(drawer.id),
            venue_id=str(venue_id),
            terminal_id=data.terminal_id,
            cashier_id=str(cashier_id),
            opening_cash=str(data.opening_cash),
        )

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.DRAWER_OPENED,
                {
                    "drawer_id": str(drawer.id),
                    "venue_id": str(venue_id),
                    "terminal_id": data.terminal_id,
                    "cashier_id": str(cashier_id),
                    "opening_cash": str(data.opening_cash),
                },
                venue_id=venue_id,
            )

        return drawer

    async def close_drawer(
        self,
        drawer_id: uuid.UUID,
        data: DrawerCloseRequest,
    ) -> CashDrawer:
        """
        Close an open cash drawer session.

        Calculates expected cash from transactions, computes variance,
        and publishes a DRAWER_CLOSED event.  If the variance exceeds
        the threshold a DRAWER_VARIANCE_ALERT is also published.

        Args:
            drawer_id: ID of the drawer to close.
            data: Closing cash amount and optional notes.

        Returns:
            The updated CashDrawer record.

        Raises:
            ServiceError: If the drawer is not found or not OPEN.
        """
        drawer = await self.get_drawer(drawer_id)

        if drawer.status != CashDrawerStatus.OPEN.value:
            raise bad_request(
                ErrorCode.DRAWER_NOT_OPEN,
                f"Drawer {drawer_id} is not open (current status: {drawer.status})",
            )

        # Calculate expected cash from cash payments on completed transactions
        expected_cash = await self._calculate_expected_cash(drawer)

        variance = data.closing_cash - expected_cash

        drawer.closing_cash = data.closing_cash
        drawer.expected_cash = expected_cash
        drawer.variance = variance
        drawer.status = CashDrawerStatus.CLOSED.value
        drawer.closed_at = datetime.utcnow()
        if data.notes:
            drawer.notes = data.notes

        await self.db.commit()
        await self.db.refresh(drawer)

        logger.info(
            "drawer_closed",
            drawer_id=str(drawer_id),
            venue_id=str(drawer.venue_id),
            closing_cash=str(data.closing_cash),
            expected_cash=str(expected_cash),
            variance=str(variance),
        )

        if self.event_publisher:
            # Publish variance alert if threshold exceeded
            if abs(variance) > VARIANCE_THRESHOLD:
                await self.event_publisher.publish(
                    EventType.DRAWER_VARIANCE_ALERT,
                    {
                        "drawer_id": str(drawer.id),
                        "venue_id": str(drawer.venue_id),
                        "terminal_id": drawer.terminal_id,
                        "cashier_id": str(drawer.cashier_id),
                        "expected_cash": str(expected_cash),
                        "closing_cash": str(data.closing_cash),
                        "variance": str(variance),
                    },
                    venue_id=drawer.venue_id,
                )

            await self.event_publisher.publish(
                EventType.DRAWER_CLOSED,
                {
                    "drawer_id": str(drawer.id),
                    "venue_id": str(drawer.venue_id),
                    "terminal_id": drawer.terminal_id,
                    "cashier_id": str(drawer.cashier_id),
                    "closing_cash": str(data.closing_cash),
                    "expected_cash": str(expected_cash),
                    "variance": str(variance),
                },
                venue_id=drawer.venue_id,
            )

        return drawer

    async def cash_drop(
        self,
        drawer_id: uuid.UUID,
        data: CashDropRequest,
    ) -> CashDrawer:
        """
        Record a cash drop for an open drawer.

        Adds the drop amount to cash_drops_total and appends a record
        to the drawer_transactions JSONB column.

        Args:
            drawer_id: ID of the drawer.
            data: Drop amount and optional notes.

        Returns:
            The updated CashDrawer record.

        Raises:
            ServiceError: If the drawer is not found or not OPEN.
        """
        drawer = await self.get_drawer(drawer_id)

        if drawer.status != CashDrawerStatus.OPEN.value:
            raise bad_request(
                ErrorCode.DRAWER_NOT_OPEN,
                f"Drawer {drawer_id} is not open (current status: {drawer.status})",
            )

        # Update totals
        drawer.cash_drops_total = (drawer.cash_drops_total or Decimal("0")) + data.amount

        # Append to drawer_transactions JSONB
        transactions_log = list(drawer.drawer_transactions or [])
        transactions_log.append(
            {
                "type": "cash_drop",
                "amount": str(data.amount),
                "notes": data.notes,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        drawer.drawer_transactions = transactions_log

        await self.db.commit()
        await self.db.refresh(drawer)

        logger.info(
            "drawer_cash_drop",
            drawer_id=str(drawer_id),
            venue_id=str(drawer.venue_id),
            amount=str(data.amount),
            cash_drops_total=str(drawer.cash_drops_total),
        )

        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.DRAWER_CASH_DROP,
                {
                    "drawer_id": str(drawer.id),
                    "venue_id": str(drawer.venue_id),
                    "terminal_id": drawer.terminal_id,
                    "cashier_id": str(drawer.cashier_id),
                    "drop_amount": str(data.amount),
                    "cash_drops_total": str(drawer.cash_drops_total),
                },
                venue_id=drawer.venue_id,
            )

        return drawer

    # =========================================================================
    # Read helpers
    # =========================================================================

    async def get_drawer(self, drawer_id: uuid.UUID) -> CashDrawer:
        """
        Get a cash drawer by ID.

        Args:
            drawer_id: UUID of the drawer.

        Returns:
            CashDrawer instance.

        Raises:
            ServiceError: If not found.
        """
        result = await self.db.execute(
            select(CashDrawer).where(CashDrawer.id == drawer_id)
        )
        drawer = result.scalars().first()
        if not drawer:
            raise not_found(
                ErrorCode.DRAWER_NOT_FOUND,
                f"Cash drawer {drawer_id} not found",
            )
        return drawer

    async def get_open_drawer(
        self,
        venue_id: uuid.UUID,
        terminal_id: str,
    ) -> Optional[CashDrawer]:
        """
        Get the currently-open drawer for a venue + terminal.

        Args:
            venue_id: Venue UUID.
            terminal_id: Terminal identifier string.

        Returns:
            CashDrawer if one is open, otherwise None.
        """
        result = await self.db.execute(
            select(CashDrawer).where(
                and_(
                    CashDrawer.venue_id == venue_id,
                    CashDrawer.terminal_id == terminal_id,
                    CashDrawer.status == CashDrawerStatus.OPEN.value,
                )
            )
        )
        return result.scalars().first()

    async def list_drawers(
        self,
        venue_id: uuid.UUID,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[CashDrawer], int]:
        """
        List cash drawers with filtering and pagination.

        Args:
            venue_id: Venue UUID.
            status: Optional drawer status filter.
            date_from: Optional start date filter.
            date_to: Optional end date filter.
            page: Page number (1-based).
            page_size: Items per page.

        Returns:
            Tuple of (drawers list, total count).
        """
        query = select(CashDrawer).where(CashDrawer.venue_id == venue_id)

        if status:
            query = query.where(CashDrawer.status == status)
        if date_from:
            query = query.where(CashDrawer.opened_at >= date_from)
        if date_to:
            query = query.where(CashDrawer.opened_at <= date_to)

        # Total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results
        query = query.order_by(CashDrawer.opened_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        drawers = list(result.scalars().all())

        logger.info(
            "drawers_listed",
            venue_id=str(venue_id),
            total=total,
            page=page,
        )
        return drawers, total

    # =========================================================================
    # Internal helpers
    # =========================================================================

    async def _calculate_expected_cash(self, drawer: CashDrawer) -> Decimal:
        """
        Calculate expected cash in drawer based on cash payments received
        during the session, the opening cash, and any cash drops removed.

        expected = opening_cash
                 + cash_payments_received (completed transactions)
                 - cash_drops_total
        """
        # Sum of cash payments made while this drawer was open
        cash_payments_query = (
            select(func.coalesce(func.sum(Payment.amount), Decimal("0")))
            .select_from(Payment)
            .join(Transaction, Transaction.id == Payment.transaction_id)
            .where(
                and_(
                    Transaction.venue_id == drawer.venue_id,
                    Transaction.status == TransactionStatus.COMPLETED.value,
                    Transaction.created_at >= drawer.opened_at,
                    Payment.payment_method == PaymentMethod.CASH.value,
                    Payment.status == PaymentStatus.COMPLETED.value,
                )
            )
        )

        result = await self.db.execute(cash_payments_query)
        cash_received = result.scalar() or Decimal("0")

        expected = (
            drawer.opening_cash
            + cash_received
            - (drawer.cash_drops_total or Decimal("0"))
        )
        return expected
