"""
=============================================================================
FILE: services/reporting_service.py
PURPOSE: Comprehensive sales analytics and reporting service for POS Integration
=============================================================================

Provides analytics endpoints for sales summaries, hourly/daily breakdowns,
payment method analysis, product performance, cashier metrics, discount usage,
and transaction type reporting.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pos import (
    Discount,
    Payment,
    PaymentStatus,
    Refund,
    RefundStatus,
    Shift,
    Transaction,
    TransactionLineItem,
    TransactionStatus,
)

logger = structlog.get_logger()


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class SalesSummary:
    """
    Aggregated sales summary for a date range.

    Attributes:
        total_transactions: Number of completed transactions.
        gross_sales: Total sales before discounts (subtotal).
        net_sales: Total sales after discounts and refunds.
        total_tax: Total tax collected.
        total_tips: Total tips collected.
        total_discounts: Total discount amounts applied.
        total_refunds: Total refund amounts processed.
        average_transaction: Average transaction value.
    """

    total_transactions: int
    gross_sales: Decimal
    net_sales: Decimal
    total_tax: Decimal
    total_tips: Decimal
    total_discounts: Decimal
    total_refunds: Decimal
    average_transaction: Decimal


@dataclass
class HourlySales:
    """
    Sales data aggregated by hour.

    Attributes:
        hour: Hour of day (0-23).
        transaction_count: Number of transactions in this hour.
        sales_amount: Total sales amount for this hour.
    """

    hour: int
    transaction_count: int
    sales_amount: Decimal


@dataclass
class PaymentMethodBreakdown:
    """
    Sales breakdown by payment method.

    Attributes:
        payment_method: The payment method (cash, credit_card, etc.).
        transaction_count: Number of transactions using this method.
        total_amount: Total amount processed with this method.
        percentage: Percentage of total sales using this method.
    """

    payment_method: str
    transaction_count: int
    total_amount: Decimal
    percentage: float


@dataclass
class ProductSales:
    """
    Sales data for individual products.

    Attributes:
        product_name: Name of the product.
        product_category: Category of the product (optional).
        quantity_sold: Total quantity sold.
        total_revenue: Total revenue from this product.
    """

    product_name: str
    product_category: Optional[str]
    quantity_sold: int
    total_revenue: Decimal


@dataclass
class CashierPerformance:
    """
    Performance metrics for a cashier.

    Attributes:
        cashier_id: UUID of the cashier.
        cashier_name: Name of the cashier.
        transaction_count: Number of transactions processed.
        total_sales: Total sales amount processed.
        average_transaction: Average transaction value.
        void_count: Number of voided transactions.
        refund_count: Number of refunds processed.
    """

    cashier_id: UUID
    cashier_name: str
    transaction_count: int
    total_sales: Decimal
    average_transaction: Decimal
    void_count: int
    refund_count: int


# =============================================================================
# REPORTING SERVICE
# =============================================================================


class ReportingService:
    """
    Comprehensive sales analytics and reporting service.

    Provides methods for generating sales summaries, hourly/daily breakdowns,
    payment method analysis, product performance metrics, cashier performance
    tracking, discount usage reports, and transaction type breakdowns.

    All methods filter by venue_id and date range to ensure multi-tenant
    data isolation and focused reporting periods.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the reporting service.

        Args:
            db: Async SQLAlchemy database session.
        """
        self.db = db

    # ─── Helper Methods ─────────────────────────────────────────────────────────

    def _build_base_transaction_filter(
        self,
        venue_id: UUID,
        date_from: date,
        date_to: date,
        transaction_type: Optional[str] = None,
        include_voided: bool = False,
    ):
        """
        Build a base filter for transaction queries.

        Args:
            venue_id: The venue to filter by.
            date_from: Start date (inclusive).
            date_to: End date (inclusive).
            transaction_type: Optional transaction type filter.
            include_voided: Whether to include voided transactions.

        Returns:
            SQLAlchemy filter condition.
        """
        # Convert dates to datetime for comparison with created_at
        start_datetime = datetime.combine(date_from, datetime.min.time())
        end_datetime = datetime.combine(date_to, datetime.max.time())

        filters = [
            Transaction.venue_id == venue_id,
            Transaction.created_at >= start_datetime,
            Transaction.created_at <= end_datetime,
        ]

        if not include_voided:
            filters.append(
                Transaction.status.in_([
                    TransactionStatus.COMPLETED.value,
                    TransactionStatus.PARTIALLY_REFUNDED.value,
                    TransactionStatus.REFUNDED.value,
                ])
            )

        if transaction_type:
            filters.append(Transaction.transaction_type == transaction_type)

        return and_(*filters)

    # ─── Sales Summary ──────────────────────────────────────────────────────────

    async def get_sales_summary(
        self,
        venue_id: UUID,
        date_from: date,
        date_to: date,
        transaction_type: Optional[str] = None,
    ) -> SalesSummary:
        """
        Get aggregated sales summary for a date range.

        Calculates total transactions, gross sales, net sales, tax, tips,
        discounts, refunds, and average transaction value for completed
        transactions within the specified date range.

        Args:
            venue_id: The venue to report on.
            date_from: Start date (inclusive).
            date_to: End date (inclusive).
            transaction_type: Optional filter by transaction type.

        Returns:
            SalesSummary dataclass with aggregated metrics.

        Example:
            >>> summary = await reporting_service.get_sales_summary(
            ...     venue_id=venue_uuid,
            ...     date_from=date(2024, 1, 1),
            ...     date_to=date(2024, 1, 31),
            ... )
            >>> print(f"Total Sales: ${summary.net_sales}")
        """
        base_filter = self._build_base_transaction_filter(
            venue_id, date_from, date_to, transaction_type
        )

        # Main aggregation query for transactions
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

        # Query for total refunds in the date range
        start_datetime = datetime.combine(date_from, datetime.min.time())
        end_datetime = datetime.combine(date_to, datetime.max.time())

        refund_query = select(
            func.coalesce(func.sum(Refund.refund_amount), Decimal("0"))
        ).where(
            and_(
                Refund.venue_id == venue_id,
                Refund.status == RefundStatus.PROCESSED.value,
                Refund.processed_at >= start_datetime,
                Refund.processed_at <= end_datetime,
            )
        )

        refund_result = await self.db.execute(refund_query)
        total_refunds = refund_result.scalar() or Decimal("0")

        # Calculate average transaction
        total_transactions = row.total_transactions or 0
        net_sales = Decimal(str(row.net_sales))
        average_transaction = (
            net_sales / total_transactions
            if total_transactions > 0
            else Decimal("0")
        )

        logger.info(
            "sales_summary_generated",
            venue_id=str(venue_id),
            date_from=str(date_from),
            date_to=str(date_to),
            transaction_type=transaction_type,
            total_transactions=total_transactions,
            net_sales=str(net_sales),
        )

        return SalesSummary(
            total_transactions=total_transactions,
            gross_sales=Decimal(str(row.gross_sales)),
            net_sales=net_sales,
            total_tax=Decimal(str(row.total_tax)),
            total_tips=Decimal(str(row.total_tips)),
            total_discounts=Decimal(str(row.total_discounts)),
            total_refunds=Decimal(str(total_refunds)),
            average_transaction=average_transaction,
        )

    # ─── Hourly Sales ───────────────────────────────────────────────────────────

    async def get_hourly_sales(
        self,
        venue_id: UUID,
        target_date: date,
    ) -> List[HourlySales]:
        """
        Get sales data aggregated by hour for a specific date.

        Returns transaction counts and sales amounts for each hour of the day,
        useful for identifying peak business hours and staffing optimization.

        Args:
            venue_id: The venue to report on.
            target_date: The date to analyze.

        Returns:
            List of HourlySales for each hour with transactions (0-23).

        Example:
            >>> hourly = await reporting_service.get_hourly_sales(
            ...     venue_id=venue_uuid,
            ...     target_date=date(2024, 1, 15),
            ... )
            >>> for h in hourly:
            ...     print(f"Hour {h.hour}: {h.transaction_count} txns, ${h.sales_amount}")
        """
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())

        base_filter = and_(
            Transaction.venue_id == venue_id,
            Transaction.created_at >= start_datetime,
            Transaction.created_at <= end_datetime,
            Transaction.status.in_([
                TransactionStatus.COMPLETED.value,
                TransactionStatus.PARTIALLY_REFUNDED.value,
                TransactionStatus.REFUNDED.value,
            ]),
        )

        # Use EXTRACT for PostgreSQL hour extraction
        hour_expr = func.extract("hour", Transaction.created_at)

        query = (
            select(
                hour_expr.label("hour"),
                func.count(Transaction.id).label("transaction_count"),
                func.coalesce(func.sum(Transaction.total_amount), Decimal("0")).label("sales_amount"),
            )
            .where(base_filter)
            .group_by(hour_expr)
            .order_by(hour_expr)
        )

        result = await self.db.execute(query)
        rows = result.all()

        hourly_sales = [
            HourlySales(
                hour=int(row.hour),
                transaction_count=row.transaction_count,
                sales_amount=Decimal(str(row.sales_amount)),
            )
            for row in rows
        ]

        logger.info(
            "hourly_sales_generated",
            venue_id=str(venue_id),
            target_date=str(target_date),
            hours_with_data=len(hourly_sales),
        )

        return hourly_sales

    # ─── Daily Sales ────────────────────────────────────────────────────────────

    async def get_daily_sales(
        self,
        venue_id: UUID,
        date_from: date,
        date_to: date,
    ) -> List[dict]:
        """
        Get sales data aggregated by day for a date range.

        Returns transaction counts, gross sales, and net sales for each day,
        useful for trend analysis and daily performance tracking.

        Args:
            venue_id: The venue to report on.
            date_from: Start date (inclusive).
            date_to: End date (inclusive).

        Returns:
            List of dicts with keys: date, transaction_count, gross_sales, net_sales.

        Example:
            >>> daily = await reporting_service.get_daily_sales(
            ...     venue_id=venue_uuid,
            ...     date_from=date(2024, 1, 1),
            ...     date_to=date(2024, 1, 7),
            ... )
            >>> for d in daily:
            ...     print(f"{d['date']}: {d['transaction_count']} txns")
        """
        start_datetime = datetime.combine(date_from, datetime.min.time())
        end_datetime = datetime.combine(date_to, datetime.max.time())

        base_filter = and_(
            Transaction.venue_id == venue_id,
            Transaction.created_at >= start_datetime,
            Transaction.created_at <= end_datetime,
            Transaction.status.in_([
                TransactionStatus.COMPLETED.value,
                TransactionStatus.PARTIALLY_REFUNDED.value,
                TransactionStatus.REFUNDED.value,
            ]),
        )

        # Use DATE_TRUNC for PostgreSQL date grouping
        date_expr = func.date_trunc("day", Transaction.created_at)

        query = (
            select(
                date_expr.label("sale_date"),
                func.count(Transaction.id).label("transaction_count"),
                func.coalesce(func.sum(Transaction.subtotal), Decimal("0")).label("gross_sales"),
                func.coalesce(func.sum(Transaction.total_amount), Decimal("0")).label("net_sales"),
            )
            .where(base_filter)
            .group_by(date_expr)
            .order_by(date_expr)
        )

        result = await self.db.execute(query)
        rows = result.all()

        daily_sales = [
            {
                "date": row.sale_date.date() if hasattr(row.sale_date, "date") else row.sale_date,
                "transaction_count": row.transaction_count,
                "gross_sales": str(row.gross_sales),
                "net_sales": str(row.net_sales),
            }
            for row in rows
        ]

        logger.info(
            "daily_sales_generated",
            venue_id=str(venue_id),
            date_from=str(date_from),
            date_to=str(date_to),
            days_with_data=len(daily_sales),
        )

        return daily_sales

    # ─── Payment Method Breakdown ───────────────────────────────────────────────

    async def get_payment_method_breakdown(
        self,
        venue_id: UUID,
        date_from: date,
        date_to: date,
    ) -> List[PaymentMethodBreakdown]:
        """
        Get sales breakdown by payment method.

        Analyzes completed payments to show distribution across payment methods
        (cash, credit card, debit card, etc.) with counts, totals, and percentages.

        Args:
            venue_id: The venue to report on.
            date_from: Start date (inclusive).
            date_to: End date (inclusive).

        Returns:
            List of PaymentMethodBreakdown for each payment method used.

        Example:
            >>> breakdown = await reporting_service.get_payment_method_breakdown(
            ...     venue_id=venue_uuid,
            ...     date_from=date(2024, 1, 1),
            ...     date_to=date(2024, 1, 31),
            ... )
            >>> for pm in breakdown:
            ...     print(f"{pm.payment_method}: {pm.percentage:.1f}%")
        """
        start_datetime = datetime.combine(date_from, datetime.min.time())
        end_datetime = datetime.combine(date_to, datetime.max.time())

        base_filter = and_(
            Payment.venue_id == venue_id,
            Payment.created_at >= start_datetime,
            Payment.created_at <= end_datetime,
            Payment.status == PaymentStatus.COMPLETED.value,
        )

        query = (
            select(
                Payment.payment_method,
                func.count(Payment.id).label("transaction_count"),
                func.coalesce(func.sum(Payment.amount), Decimal("0")).label("total_amount"),
            )
            .where(base_filter)
            .group_by(Payment.payment_method)
            .order_by(func.sum(Payment.amount).desc())
        )

        result = await self.db.execute(query)
        rows = result.all()

        # Calculate total for percentage
        total_amount = sum(Decimal(str(row.total_amount)) for row in rows)

        payment_breakdown = [
            PaymentMethodBreakdown(
                payment_method=row.payment_method,
                transaction_count=row.transaction_count,
                total_amount=Decimal(str(row.total_amount)),
                percentage=(
                    float(Decimal(str(row.total_amount)) / total_amount * 100)
                    if total_amount > 0
                    else 0.0
                ),
            )
            for row in rows
        ]

        logger.info(
            "payment_method_breakdown_generated",
            venue_id=str(venue_id),
            date_from=str(date_from),
            date_to=str(date_to),
            payment_methods_count=len(payment_breakdown),
        )

        return payment_breakdown

    # ─── Top Products ───────────────────────────────────────────────────────────

    async def get_top_products(
        self,
        venue_id: UUID,
        date_from: date,
        date_to: date,
        limit: int = 10,
    ) -> List[ProductSales]:
        """
        Get top-selling products by revenue.

        Analyzes transaction line items to identify best-selling products
        based on total revenue, including quantity sold and category information.

        Args:
            venue_id: The venue to report on.
            date_from: Start date (inclusive).
            date_to: End date (inclusive).
            limit: Maximum number of products to return (default 10).

        Returns:
            List of ProductSales for top products ordered by revenue.

        Example:
            >>> top = await reporting_service.get_top_products(
            ...     venue_id=venue_uuid,
            ...     date_from=date(2024, 1, 1),
            ...     date_to=date(2024, 1, 31),
            ...     limit=5,
            ... )
            >>> for p in top:
            ...     print(f"{p.product_name}: {p.quantity_sold} units, ${p.total_revenue}")
        """
        start_datetime = datetime.combine(date_from, datetime.min.time())
        end_datetime = datetime.combine(date_to, datetime.max.time())

        # Join line items with completed transactions
        query = (
            select(
                TransactionLineItem.product_name,
                TransactionLineItem.product_category,
                func.sum(TransactionLineItem.quantity).label("quantity_sold"),
                func.coalesce(func.sum(TransactionLineItem.total), Decimal("0")).label("total_revenue"),
            )
            .join(
                Transaction,
                TransactionLineItem.transaction_id == Transaction.id,
            )
            .where(
                and_(
                    TransactionLineItem.venue_id == venue_id,
                    Transaction.created_at >= start_datetime,
                    Transaction.created_at <= end_datetime,
                    Transaction.status.in_([
                        TransactionStatus.COMPLETED.value,
                        TransactionStatus.PARTIALLY_REFUNDED.value,
                        TransactionStatus.REFUNDED.value,
                    ]),
                )
            )
            .group_by(
                TransactionLineItem.product_name,
                TransactionLineItem.product_category,
            )
            .order_by(func.sum(TransactionLineItem.total).desc())
            .limit(limit)
        )

        result = await self.db.execute(query)
        rows = result.all()

        top_products = [
            ProductSales(
                product_name=row.product_name,
                product_category=row.product_category,
                quantity_sold=int(row.quantity_sold),
                total_revenue=Decimal(str(row.total_revenue)),
            )
            for row in rows
        ]

        logger.info(
            "top_products_generated",
            venue_id=str(venue_id),
            date_from=str(date_from),
            date_to=str(date_to),
            products_returned=len(top_products),
        )

        return top_products

    # ─── Sales by Category ──────────────────────────────────────────────────────

    async def get_sales_by_category(
        self,
        venue_id: UUID,
        date_from: date,
        date_to: date,
    ) -> List[dict]:
        """
        Get sales aggregated by product category.

        Groups transaction line items by category to show category-level
        performance including quantity sold and total revenue.

        Args:
            venue_id: The venue to report on.
            date_from: Start date (inclusive).
            date_to: End date (inclusive).

        Returns:
            List of dicts with keys: category, quantity, revenue.

        Example:
            >>> categories = await reporting_service.get_sales_by_category(
            ...     venue_id=venue_uuid,
            ...     date_from=date(2024, 1, 1),
            ...     date_to=date(2024, 1, 31),
            ... )
            >>> for c in categories:
            ...     print(f"{c['category']}: ${c['revenue']}")
        """
        start_datetime = datetime.combine(date_from, datetime.min.time())
        end_datetime = datetime.combine(date_to, datetime.max.time())

        query = (
            select(
                func.coalesce(
                    TransactionLineItem.product_category, "Uncategorized"
                ).label("category"),
                func.sum(TransactionLineItem.quantity).label("quantity"),
                func.coalesce(func.sum(TransactionLineItem.total), Decimal("0")).label("revenue"),
            )
            .join(
                Transaction,
                TransactionLineItem.transaction_id == Transaction.id,
            )
            .where(
                and_(
                    TransactionLineItem.venue_id == venue_id,
                    Transaction.created_at >= start_datetime,
                    Transaction.created_at <= end_datetime,
                    Transaction.status.in_([
                        TransactionStatus.COMPLETED.value,
                        TransactionStatus.PARTIALLY_REFUNDED.value,
                        TransactionStatus.REFUNDED.value,
                    ]),
                )
            )
            .group_by(TransactionLineItem.product_category)
            .order_by(func.sum(TransactionLineItem.total).desc())
        )

        result = await self.db.execute(query)
        rows = result.all()

        category_sales = [
            {
                "category": row.category,
                "quantity": int(row.quantity),
                "revenue": str(row.revenue),
            }
            for row in rows
        ]

        logger.info(
            "sales_by_category_generated",
            venue_id=str(venue_id),
            date_from=str(date_from),
            date_to=str(date_to),
            categories_count=len(category_sales),
        )

        return category_sales

    # ─── Cashier Performance ────────────────────────────────────────────────────

    async def get_cashier_performance(
        self,
        venue_id: UUID,
        date_from: date,
        date_to: date,
    ) -> List[CashierPerformance]:
        """
        Get performance metrics for all cashiers.

        Analyzes transactions by cashier to show transaction counts, total sales,
        average transaction values, and void/refund counts for performance tracking.

        Args:
            venue_id: The venue to report on.
            date_from: Start date (inclusive).
            date_to: End date (inclusive).

        Returns:
            List of CashierPerformance for each cashier with activity.

        Example:
            >>> cashiers = await reporting_service.get_cashier_performance(
            ...     venue_id=venue_uuid,
            ...     date_from=date(2024, 1, 1),
            ...     date_to=date(2024, 1, 31),
            ... )
            >>> for c in cashiers:
            ...     print(f"{c.cashier_name}: {c.transaction_count} txns, ${c.total_sales}")
        """
        start_datetime = datetime.combine(date_from, datetime.min.time())
        end_datetime = datetime.combine(date_to, datetime.max.time())

        # Query for completed transactions by cashier
        completed_query = (
            select(
                Transaction.cashier_id,
                func.count(Transaction.id).label("transaction_count"),
                func.coalesce(func.sum(Transaction.total_amount), Decimal("0")).label("total_sales"),
            )
            .where(
                and_(
                    Transaction.venue_id == venue_id,
                    Transaction.created_at >= start_datetime,
                    Transaction.created_at <= end_datetime,
                    Transaction.status.in_([
                        TransactionStatus.COMPLETED.value,
                        TransactionStatus.PARTIALLY_REFUNDED.value,
                        TransactionStatus.REFUNDED.value,
                    ]),
                    Transaction.cashier_id.isnot(None),
                )
            )
            .group_by(Transaction.cashier_id)
        )

        completed_result = await self.db.execute(completed_query)
        completed_rows = {row.cashier_id: row for row in completed_result.all()}

        # Query for voided transactions by cashier
        void_query = (
            select(
                Transaction.cashier_id,
                func.count(Transaction.id).label("void_count"),
            )
            .where(
                and_(
                    Transaction.venue_id == venue_id,
                    Transaction.created_at >= start_datetime,
                    Transaction.created_at <= end_datetime,
                    Transaction.status == TransactionStatus.VOIDED.value,
                    Transaction.cashier_id.isnot(None),
                )
            )
            .group_by(Transaction.cashier_id)
        )

        void_result = await self.db.execute(void_query)
        void_counts = {row.cashier_id: row.void_count for row in void_result.all()}

        # Query for refunds associated with cashier's transactions
        refund_subquery = (
            select(Transaction.cashier_id, Refund.id)
            .join(Refund, Refund.transaction_id == Transaction.id)
            .where(
                and_(
                    Transaction.venue_id == venue_id,
                    Refund.processed_at >= start_datetime,
                    Refund.processed_at <= end_datetime,
                    Refund.status == RefundStatus.PROCESSED.value,
                    Transaction.cashier_id.isnot(None),
                )
            )
        ).subquery()

        refund_query = (
            select(
                refund_subquery.c.cashier_id,
                func.count(refund_subquery.c.id).label("refund_count"),
            )
            .group_by(refund_subquery.c.cashier_id)
        )

        refund_result = await self.db.execute(refund_query)
        refund_counts = {row.cashier_id: row.refund_count for row in refund_result.all()}

        # Get cashier names from Shift records
        cashier_ids = set(completed_rows.keys()) | set(void_counts.keys())

        cashier_names = {}
        if cashier_ids:
            name_query = (
                select(Shift.employee_id, Shift.employee_name)
                .where(Shift.employee_id.in_(cashier_ids))
                .distinct()
            )
            name_result = await self.db.execute(name_query)
            cashier_names = {row.employee_id: row.employee_name for row in name_result.all()}

        # Build performance list
        performance_list = []
        for cashier_id in cashier_ids:
            completed = completed_rows.get(cashier_id)
            transaction_count = completed.transaction_count if completed else 0
            total_sales = Decimal(str(completed.total_sales)) if completed else Decimal("0")

            average_transaction = (
                total_sales / transaction_count
                if transaction_count > 0
                else Decimal("0")
            )

            performance_list.append(
                CashierPerformance(
                    cashier_id=cashier_id,
                    cashier_name=cashier_names.get(cashier_id, "Unknown"),
                    transaction_count=transaction_count,
                    total_sales=total_sales,
                    average_transaction=average_transaction,
                    void_count=void_counts.get(cashier_id, 0),
                    refund_count=refund_counts.get(cashier_id, 0),
                )
            )

        # Sort by total sales descending
        performance_list.sort(key=lambda x: x.total_sales, reverse=True)

        logger.info(
            "cashier_performance_generated",
            venue_id=str(venue_id),
            date_from=str(date_from),
            date_to=str(date_to),
            cashiers_count=len(performance_list),
        )

        return performance_list

    # ─── Discount Usage ─────────────────────────────────────────────────────────

    async def get_discount_usage(
        self,
        venue_id: UUID,
        date_from: date,
        date_to: date,
    ) -> List[dict]:
        """
        Get discount usage statistics.

        Analyzes transaction line items with applied discounts to show
        which discounts were used, how often, and total discount amounts.

        Args:
            venue_id: The venue to report on.
            date_from: Start date (inclusive).
            date_to: End date (inclusive).

        Returns:
            List of dicts with keys: discount_name, usage_count, total_discount_amount.

        Example:
            >>> discounts = await reporting_service.get_discount_usage(
            ...     venue_id=venue_uuid,
            ...     date_from=date(2024, 1, 1),
            ...     date_to=date(2024, 1, 31),
            ... )
            >>> for d in discounts:
            ...     print(f"{d['discount_name']}: used {d['usage_count']} times")
        """
        start_datetime = datetime.combine(date_from, datetime.min.time())
        end_datetime = datetime.combine(date_to, datetime.max.time())

        # Query line items with discounts applied
        query = (
            select(
                Discount.name.label("discount_name"),
                func.count(TransactionLineItem.id).label("usage_count"),
                func.coalesce(
                    func.sum(TransactionLineItem.discount_amount), Decimal("0")
                ).label("total_discount_amount"),
            )
            .join(
                TransactionLineItem,
                TransactionLineItem.discount_id == Discount.id,
            )
            .join(
                Transaction,
                TransactionLineItem.transaction_id == Transaction.id,
            )
            .where(
                and_(
                    TransactionLineItem.venue_id == venue_id,
                    Transaction.created_at >= start_datetime,
                    Transaction.created_at <= end_datetime,
                    Transaction.status.in_([
                        TransactionStatus.COMPLETED.value,
                        TransactionStatus.PARTIALLY_REFUNDED.value,
                        TransactionStatus.REFUNDED.value,
                    ]),
                    TransactionLineItem.discount_id.isnot(None),
                )
            )
            .group_by(Discount.name)
            .order_by(func.sum(TransactionLineItem.discount_amount).desc())
        )

        result = await self.db.execute(query)
        rows = result.all()

        discount_usage = [
            {
                "discount_name": row.discount_name,
                "usage_count": row.usage_count,
                "total_discount_amount": str(row.total_discount_amount),
            }
            for row in rows
        ]

        logger.info(
            "discount_usage_generated",
            venue_id=str(venue_id),
            date_from=str(date_from),
            date_to=str(date_to),
            discounts_count=len(discount_usage),
        )

        return discount_usage

    # ─── Transaction Type Breakdown ─────────────────────────────────────────────

    async def get_transaction_type_breakdown(
        self,
        venue_id: UUID,
        date_from: date,
        date_to: date,
    ) -> List[dict]:
        """
        Get sales breakdown by transaction type.

        Groups transactions by type (bowling, arcade, food, party, etc.)
        to show distribution of business across different service categories.

        Args:
            venue_id: The venue to report on.
            date_from: Start date (inclusive).
            date_to: End date (inclusive).

        Returns:
            List of dicts with keys: type, count, revenue.

        Example:
            >>> types = await reporting_service.get_transaction_type_breakdown(
            ...     venue_id=venue_uuid,
            ...     date_from=date(2024, 1, 1),
            ...     date_to=date(2024, 1, 31),
            ... )
            >>> for t in types:
            ...     print(f"{t['type']}: {t['count']} txns, ${t['revenue']}")
        """
        base_filter = self._build_base_transaction_filter(
            venue_id, date_from, date_to
        )

        query = (
            select(
                Transaction.transaction_type,
                func.count(Transaction.id).label("count"),
                func.coalesce(func.sum(Transaction.total_amount), Decimal("0")).label("revenue"),
            )
            .where(base_filter)
            .group_by(Transaction.transaction_type)
            .order_by(func.sum(Transaction.total_amount).desc())
        )

        result = await self.db.execute(query)
        rows = result.all()

        type_breakdown = [
            {
                "type": row.transaction_type,
                "count": row.count,
                "revenue": str(row.revenue),
            }
            for row in rows
        ]

        logger.info(
            "transaction_type_breakdown_generated",
            venue_id=str(venue_id),
            date_from=str(date_from),
            date_to=str(date_to),
            types_count=len(type_breakdown),
        )

        return type_breakdown
