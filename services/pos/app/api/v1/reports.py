"""
=============================================================================
FILE: api/v1/reports.py
PURPOSE: Reporting and analytics API routes for POS Integration Service
=============================================================================

Provides comprehensive reporting and analytics endpoints for sales data,
including:
- Sales summaries with configurable date ranges
- Hourly and daily sales breakdowns
- Payment method analysis
- Top-selling products
- Sales by product category
- Cashier performance metrics
- Discount usage statistics
- Transaction type breakdowns

All endpoints require authentication and filter data by venue_id to ensure
multi-tenant data isolation.
"""

import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.services.reporting_service import ReportingService

router = APIRouter(prefix="/reports")


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================


class SalesSummaryResponse(BaseModel):
    """
    Aggregated sales summary response for a date range.

    Example:
        {
            "total_transactions": 1523,
            "gross_sales": "45672.50",
            "net_sales": "43156.75",
            "total_tax": "3452.54",
            "total_tips": "4315.68",
            "total_discounts": "2515.75",
            "total_refunds": "1250.00",
            "average_transaction": "28.33"
        }
    """

    total_transactions: int = Field(
        ..., description="Number of completed transactions in the date range"
    )
    gross_sales: str = Field(
        ..., description="Total sales before discounts (subtotal sum)"
    )
    net_sales: str = Field(
        ..., description="Total sales after discounts and before refunds"
    )
    total_tax: str = Field(..., description="Total tax collected")
    total_tips: str = Field(..., description="Total tips collected")
    total_discounts: str = Field(..., description="Total discount amounts applied")
    total_refunds: str = Field(..., description="Total refund amounts processed")
    average_transaction: str = Field(..., description="Average transaction value")


class HourlySalesResponse(BaseModel):
    """
    Sales data aggregated by hour.

    Example:
        {
            "hour": 14,
            "transaction_count": 45,
            "sales_amount": "1234.50"
        }
    """

    hour: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    transaction_count: int = Field(
        ..., description="Number of transactions in this hour"
    )
    sales_amount: str = Field(..., description="Total sales amount for this hour")


class DailySalesResponse(BaseModel):
    """
    Sales data aggregated by day.

    Example:
        {
            "date": "2024-01-15",
            "transaction_count": 156,
            "gross_sales": "4567.25",
            "net_sales": "4321.50"
        }
    """

    date: datetime.date = Field(..., description="The date of sales")
    transaction_count: int = Field(
        ..., description="Number of transactions on this date"
    )
    gross_sales: str = Field(..., description="Total sales before discounts")
    net_sales: str = Field(..., description="Total sales after discounts")


class PaymentMethodResponse(BaseModel):
    """
    Sales breakdown by payment method.

    Example:
        {
            "payment_method": "credit_card",
            "transaction_count": 892,
            "total_amount": "35621.45",
            "percentage": 78.5
        }
    """

    payment_method: str = Field(
        ..., description="Payment method (cash, credit_card, debit_card, etc.)"
    )
    transaction_count: int = Field(
        ..., description="Number of transactions using this method"
    )
    total_amount: str = Field(
        ..., description="Total amount processed with this method"
    )
    percentage: float = Field(
        ..., description="Percentage of total sales using this method"
    )


class TopProductResponse(BaseModel):
    """
    Sales data for a top-selling product.

    Example:
        {
            "product_name": "Large Pizza",
            "product_category": "Food",
            "quantity_sold": 234,
            "total_revenue": "4680.00"
        }
    """

    product_name: str = Field(..., description="Name of the product")
    product_category: Optional[str] = Field(
        None, description="Category of the product"
    )
    quantity_sold: int = Field(..., description="Total quantity sold")
    total_revenue: str = Field(..., description="Total revenue from this product")


class CategorySalesResponse(BaseModel):
    """
    Sales breakdown by product category.

    Example:
        {
            "category": "Food",
            "quantity": 1523,
            "revenue": "15230.50"
        }
    """

    category: str = Field(..., description="Product category name")
    quantity: int = Field(..., description="Total quantity sold in this category")
    revenue: str = Field(..., description="Total revenue from this category")


class CashierPerformanceResponse(BaseModel):
    """
    Performance metrics for a cashier.

    Example:
        {
            "cashier_id": "550e8400-e29b-41d4-a716-446655440000",
            "cashier_name": "John Smith",
            "transaction_count": 145,
            "total_sales": "4352.75",
            "average_transaction": "30.02",
            "void_count": 3,
            "refund_count": 5
        }
    """

    cashier_id: UUID = Field(..., description="UUID of the cashier")
    cashier_name: str = Field(..., description="Name of the cashier")
    transaction_count: int = Field(
        ..., description="Number of transactions processed"
    )
    total_sales: str = Field(..., description="Total sales amount processed")
    average_transaction: str = Field(..., description="Average transaction value")
    void_count: int = Field(..., description="Number of voided transactions")
    refund_count: int = Field(..., description="Number of refunds processed")


class DiscountUsageResponse(BaseModel):
    """
    Discount usage statistics.

    Example:
        {
            "discount_name": "Summer Sale 20%",
            "usage_count": 156,
            "total_discount_amount": "2340.50"
        }
    """

    discount_name: str = Field(..., description="Name of the discount")
    usage_count: int = Field(..., description="Number of times the discount was used")
    total_discount_amount: str = Field(
        ..., description="Total discount amount applied"
    )


class TransactionTypeResponse(BaseModel):
    """
    Sales breakdown by transaction type.

    Example:
        {
            "type": "bowling",
            "count": 523,
            "revenue": "15690.00"
        }
    """

    type: str = Field(
        ..., description="Transaction type (bowling, arcade, food, party, etc.)"
    )
    count: int = Field(..., description="Number of transactions of this type")
    revenue: str = Field(..., description="Total revenue from this transaction type")


# =============================================================================
# HELPER FUNCTION
# =============================================================================


def _get_reporting_service(db: AsyncSession = Depends(get_db)) -> ReportingService:
    """Create a ReportingService instance with the database session."""
    return ReportingService(db)


# =============================================================================
# ROUTES
# =============================================================================


@router.get(
    "/sales-summary",
    response_model=SalesSummaryResponse,
    summary="Get sales summary",
    responses={
        200: {
            "description": "Sales summary retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "total_transactions": 1523,
                        "gross_sales": "45672.50",
                        "net_sales": "43156.75",
                        "total_tax": "3452.54",
                        "total_tips": "4315.68",
                        "total_discounts": "2515.75",
                        "total_refunds": "1250.00",
                        "average_transaction": "28.33",
                    }
                }
            },
        }
    },
)
async def get_sales_summary(
    venue_id: UUID = Query(..., description="UUID of the venue to report on"),
    date_from: datetime.date = Query(..., description="Start date (inclusive) for the report"),
    date_to: datetime.date = Query(..., description="End date (inclusive) for the report"),
    transaction_type: Optional[str] = Query(
        None,
        description="Optional filter by transaction type (bowling, arcade, food, party, membership, retail, other)",
    ),
    current_user: dict = Depends(get_current_user),
    service: ReportingService = Depends(_get_reporting_service),
) -> SalesSummaryResponse:
    """
    Get aggregated sales summary for a date range.

    Returns comprehensive sales metrics including total transactions, gross and net
    sales, tax collected, tips, discounts applied, refunds processed, and average
    transaction value.

    **Parameters:**
    - **venue_id**: UUID of the venue to generate the report for
    - **date_from**: Start date of the reporting period (inclusive)
    - **date_to**: End date of the reporting period (inclusive)
    - **transaction_type**: Optional filter to limit results to a specific transaction type

    **Example Request:**
    ```
    GET /api/v1/reports/sales-summary?venue_id=550e8400-e29b-41d4-a716-446655440000&date_from=2024-01-01&date_to=2024-01-31
    ```

    **Example Response:**
    ```json
    {
        "total_transactions": 1523,
        "gross_sales": "45672.50",
        "net_sales": "43156.75",
        "total_tax": "3452.54",
        "total_tips": "4315.68",
        "total_discounts": "2515.75",
        "total_refunds": "1250.00",
        "average_transaction": "28.33"
    }
    ```
    """
    summary = await service.get_sales_summary(
        venue_id=venue_id,
        date_from=date_from,
        date_to=date_to,
        transaction_type=transaction_type,
    )

    return SalesSummaryResponse(
        total_transactions=summary.total_transactions,
        gross_sales=str(summary.gross_sales),
        net_sales=str(summary.net_sales),
        total_tax=str(summary.total_tax),
        total_tips=str(summary.total_tips),
        total_discounts=str(summary.total_discounts),
        total_refunds=str(summary.total_refunds),
        average_transaction=str(summary.average_transaction),
    )


@router.get(
    "/hourly-sales",
    response_model=List[HourlySalesResponse],
    summary="Get hourly sales breakdown",
    responses={
        200: {
            "description": "Hourly sales breakdown retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {"hour": 10, "transaction_count": 12, "sales_amount": "345.50"},
                        {"hour": 11, "transaction_count": 28, "sales_amount": "756.25"},
                        {"hour": 12, "transaction_count": 45, "sales_amount": "1234.50"},
                        {"hour": 13, "transaction_count": 52, "sales_amount": "1456.75"},
                        {"hour": 14, "transaction_count": 38, "sales_amount": "1089.00"},
                    ]
                }
            },
        }
    },
)
async def get_hourly_sales(
    venue_id: UUID = Query(..., description="UUID of the venue to report on"),
    target_date: datetime.date = Query(..., description="The specific date to analyze"),
    current_user: dict = Depends(get_current_user),
    service: ReportingService = Depends(_get_reporting_service),
) -> List[HourlySalesResponse]:
    """
    Get hourly sales breakdown for a specific date.

    Returns transaction counts and sales amounts for each hour of the day that had
    sales activity. Useful for identifying peak business hours and optimizing staffing.

    **Parameters:**
    - **venue_id**: UUID of the venue to generate the report for
    - **target_date**: The specific date to analyze

    **Example Request:**
    ```
    GET /api/v1/reports/hourly-sales?venue_id=550e8400-e29b-41d4-a716-446655440000&target_date=2024-01-15
    ```

    **Example Response:**
    ```json
    [
        {"hour": 10, "transaction_count": 12, "sales_amount": "345.50"},
        {"hour": 11, "transaction_count": 28, "sales_amount": "756.25"},
        {"hour": 12, "transaction_count": 45, "sales_amount": "1234.50"},
        {"hour": 13, "transaction_count": 52, "sales_amount": "1456.75"},
        {"hour": 14, "transaction_count": 38, "sales_amount": "1089.00"}
    ]
    ```

    **Notes:**
    - Only hours with transactions are returned
    - Hours are in 24-hour format (0-23)
    - Results are ordered by hour ascending
    """
    hourly_data = await service.get_hourly_sales(
        venue_id=venue_id,
        target_date=target_date,
    )

    return [
        HourlySalesResponse(
            hour=item.hour,
            transaction_count=item.transaction_count,
            sales_amount=str(item.sales_amount),
        )
        for item in hourly_data
    ]


@router.get(
    "/daily-sales",
    response_model=List[DailySalesResponse],
    summary="Get daily sales breakdown",
    responses={
        200: {
            "description": "Daily sales breakdown retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "date": "2024-01-15",
                            "transaction_count": 156,
                            "gross_sales": "4567.25",
                            "net_sales": "4321.50",
                        },
                        {
                            "date": "2024-01-16",
                            "transaction_count": 178,
                            "gross_sales": "5234.75",
                            "net_sales": "4987.00",
                        },
                        {
                            "date": "2024-01-17",
                            "transaction_count": 142,
                            "gross_sales": "4123.50",
                            "net_sales": "3890.25",
                        },
                    ]
                }
            },
        }
    },
)
async def get_daily_sales(
    venue_id: UUID = Query(..., description="UUID of the venue to report on"),
    date_from: datetime.date = Query(..., description="Start date (inclusive) for the report"),
    date_to: datetime.date = Query(..., description="End date (inclusive) for the report"),
    current_user: dict = Depends(get_current_user),
    service: ReportingService = Depends(_get_reporting_service),
) -> List[DailySalesResponse]:
    """
    Get daily sales breakdown for a date range.

    Returns transaction counts, gross sales, and net sales for each day in the
    specified date range. Useful for trend analysis and daily performance tracking.

    **Parameters:**
    - **venue_id**: UUID of the venue to generate the report for
    - **date_from**: Start date of the reporting period (inclusive)
    - **date_to**: End date of the reporting period (inclusive)

    **Example Request:**
    ```
    GET /api/v1/reports/daily-sales?venue_id=550e8400-e29b-41d4-a716-446655440000&date_from=2024-01-15&date_to=2024-01-21
    ```

    **Example Response:**
    ```json
    [
        {"date": "2024-01-15", "transaction_count": 156, "gross_sales": "4567.25", "net_sales": "4321.50"},
        {"date": "2024-01-16", "transaction_count": 178, "gross_sales": "5234.75", "net_sales": "4987.00"},
        {"date": "2024-01-17", "transaction_count": 142, "gross_sales": "4123.50", "net_sales": "3890.25"}
    ]
    ```

    **Notes:**
    - Only days with transactions are returned
    - Results are ordered by date ascending
    - Gross sales represents totals before discounts
    - Net sales represents totals after discounts
    """
    daily_data = await service.get_daily_sales(
        venue_id=venue_id,
        date_from=date_from,
        date_to=date_to,
    )

    return [
        DailySalesResponse(
            date=item["date"],
            transaction_count=item["transaction_count"],
            gross_sales=item["gross_sales"],
            net_sales=item["net_sales"],
        )
        for item in daily_data
    ]


@router.get(
    "/payment-methods",
    response_model=List[PaymentMethodResponse],
    summary="Get payment method breakdown",
    responses={
        200: {
            "description": "Payment method breakdown retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "payment_method": "credit_card",
                            "transaction_count": 892,
                            "total_amount": "35621.45",
                            "percentage": 78.5,
                        },
                        {
                            "payment_method": "cash",
                            "transaction_count": 234,
                            "total_amount": "6543.25",
                            "percentage": 14.4,
                        },
                        {
                            "payment_method": "debit_card",
                            "transaction_count": 89,
                            "total_amount": "2345.30",
                            "percentage": 5.2,
                        },
                        {
                            "payment_method": "gift_card",
                            "transaction_count": 45,
                            "total_amount": "892.00",
                            "percentage": 1.9,
                        },
                    ]
                }
            },
        }
    },
)
async def get_payment_method_breakdown(
    venue_id: UUID = Query(..., description="UUID of the venue to report on"),
    date_from: datetime.date = Query(..., description="Start date (inclusive) for the report"),
    date_to: datetime.date = Query(..., description="End date (inclusive) for the report"),
    current_user: dict = Depends(get_current_user),
    service: ReportingService = Depends(_get_reporting_service),
) -> List[PaymentMethodResponse]:
    """
    Get payment method breakdown for a date range.

    Analyzes completed payments to show distribution across payment methods
    including transaction counts, total amounts, and percentage of total sales.

    **Parameters:**
    - **venue_id**: UUID of the venue to generate the report for
    - **date_from**: Start date of the reporting period (inclusive)
    - **date_to**: End date of the reporting period (inclusive)

    **Example Request:**
    ```
    GET /api/v1/reports/payment-methods?venue_id=550e8400-e29b-41d4-a716-446655440000&date_from=2024-01-01&date_to=2024-01-31
    ```

    **Example Response:**
    ```json
    [
        {"payment_method": "credit_card", "transaction_count": 892, "total_amount": "35621.45", "percentage": 78.5},
        {"payment_method": "cash", "transaction_count": 234, "total_amount": "6543.25", "percentage": 14.4},
        {"payment_method": "debit_card", "transaction_count": 89, "total_amount": "2345.30", "percentage": 5.2},
        {"payment_method": "gift_card", "transaction_count": 45, "total_amount": "892.00", "percentage": 1.9}
    ]
    ```

    **Payment Methods:**
    - cash
    - credit_card
    - debit_card
    - game_card
    - comp
    - gift_card
    - mobile_pay
    """
    breakdown = await service.get_payment_method_breakdown(
        venue_id=venue_id,
        date_from=date_from,
        date_to=date_to,
    )

    return [
        PaymentMethodResponse(
            payment_method=item.payment_method,
            transaction_count=item.transaction_count,
            total_amount=str(item.total_amount),
            percentage=item.percentage,
        )
        for item in breakdown
    ]


@router.get(
    "/top-products",
    response_model=List[TopProductResponse],
    summary="Get top-selling products",
    responses={
        200: {
            "description": "Top products retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "product_name": "Large Pizza",
                            "product_category": "Food",
                            "quantity_sold": 234,
                            "total_revenue": "4680.00",
                        },
                        {
                            "product_name": "Bowling Lane Hour",
                            "product_category": "Bowling",
                            "quantity_sold": 189,
                            "total_revenue": "4725.00",
                        },
                        {
                            "product_name": "Arcade Game Card $20",
                            "product_category": "Arcade",
                            "quantity_sold": 156,
                            "total_revenue": "3120.00",
                        },
                    ]
                }
            },
        }
    },
)
async def get_top_products(
    venue_id: UUID = Query(..., description="UUID of the venue to report on"),
    date_from: datetime.date = Query(..., description="Start date (inclusive) for the report"),
    date_to: datetime.date = Query(..., description="End date (inclusive) for the report"),
    limit: int = Query(
        10,
        ge=1,
        le=100,
        description="Maximum number of products to return (1-100)",
    ),
    current_user: dict = Depends(get_current_user),
    service: ReportingService = Depends(_get_reporting_service),
) -> List[TopProductResponse]:
    """
    Get top-selling products by revenue.

    Analyzes transaction line items to identify best-selling products based on
    total revenue, including quantity sold and category information.

    **Parameters:**
    - **venue_id**: UUID of the venue to generate the report for
    - **date_from**: Start date of the reporting period (inclusive)
    - **date_to**: End date of the reporting period (inclusive)
    - **limit**: Maximum number of products to return (default: 10, max: 100)

    **Example Request:**
    ```
    GET /api/v1/reports/top-products?venue_id=550e8400-e29b-41d4-a716-446655440000&date_from=2024-01-01&date_to=2024-01-31&limit=5
    ```

    **Example Response:**
    ```json
    [
        {"product_name": "Large Pizza", "product_category": "Food", "quantity_sold": 234, "total_revenue": "4680.00"},
        {"product_name": "Bowling Lane Hour", "product_category": "Bowling", "quantity_sold": 189, "total_revenue": "4725.00"},
        {"product_name": "Arcade Game Card $20", "product_category": "Arcade", "quantity_sold": 156, "total_revenue": "3120.00"}
    ]
    ```

    **Notes:**
    - Products are ranked by total revenue (descending)
    - Products without a category will have product_category as null
    """
    top_products = await service.get_top_products(
        venue_id=venue_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )

    return [
        TopProductResponse(
            product_name=item.product_name,
            product_category=item.product_category,
            quantity_sold=item.quantity_sold,
            total_revenue=str(item.total_revenue),
        )
        for item in top_products
    ]


@router.get(
    "/sales-by-category",
    response_model=List[CategorySalesResponse],
    summary="Get sales by category",
    responses={
        200: {
            "description": "Category sales breakdown retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {"category": "Food", "quantity": 1523, "revenue": "15230.50"},
                        {"category": "Bowling", "quantity": 892, "revenue": "22300.00"},
                        {"category": "Arcade", "quantity": 2345, "revenue": "9380.00"},
                        {"category": "Retail", "quantity": 234, "revenue": "2340.00"},
                    ]
                }
            },
        }
    },
)
async def get_sales_by_category(
    venue_id: UUID = Query(..., description="UUID of the venue to report on"),
    date_from: datetime.date = Query(..., description="Start date (inclusive) for the report"),
    date_to: datetime.date = Query(..., description="End date (inclusive) for the report"),
    current_user: dict = Depends(get_current_user),
    service: ReportingService = Depends(_get_reporting_service),
) -> List[CategorySalesResponse]:
    """
    Get sales breakdown by product category.

    Groups transaction line items by category to show category-level performance
    including quantity sold and total revenue.

    **Parameters:**
    - **venue_id**: UUID of the venue to generate the report for
    - **date_from**: Start date of the reporting period (inclusive)
    - **date_to**: End date of the reporting period (inclusive)

    **Example Request:**
    ```
    GET /api/v1/reports/sales-by-category?venue_id=550e8400-e29b-41d4-a716-446655440000&date_from=2024-01-01&date_to=2024-01-31
    ```

    **Example Response:**
    ```json
    [
        {"category": "Food", "quantity": 1523, "revenue": "15230.50"},
        {"category": "Bowling", "quantity": 892, "revenue": "22300.00"},
        {"category": "Arcade", "quantity": 2345, "revenue": "9380.00"},
        {"category": "Retail", "quantity": 234, "revenue": "2340.00"}
    ]
    ```

    **Notes:**
    - Categories are ranked by revenue (descending)
    - Products without a category are grouped under "Uncategorized"
    """
    category_sales = await service.get_sales_by_category(
        venue_id=venue_id,
        date_from=date_from,
        date_to=date_to,
    )

    return [
        CategorySalesResponse(
            category=item["category"],
            quantity=item["quantity"],
            revenue=item["revenue"],
        )
        for item in category_sales
    ]


@router.get(
    "/cashier-performance",
    response_model=List[CashierPerformanceResponse],
    summary="Get cashier performance metrics",
    responses={
        200: {
            "description": "Cashier performance data retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "cashier_id": "550e8400-e29b-41d4-a716-446655440000",
                            "cashier_name": "John Smith",
                            "transaction_count": 145,
                            "total_sales": "4352.75",
                            "average_transaction": "30.02",
                            "void_count": 3,
                            "refund_count": 5,
                        },
                        {
                            "cashier_id": "660e8400-e29b-41d4-a716-446655440001",
                            "cashier_name": "Jane Doe",
                            "transaction_count": 132,
                            "total_sales": "3967.50",
                            "average_transaction": "30.06",
                            "void_count": 1,
                            "refund_count": 2,
                        },
                    ]
                }
            },
        }
    },
)
async def get_cashier_performance(
    venue_id: UUID = Query(..., description="UUID of the venue to report on"),
    date_from: datetime.date = Query(..., description="Start date (inclusive) for the report"),
    date_to: datetime.date = Query(..., description="End date (inclusive) for the report"),
    current_user: dict = Depends(get_current_user),
    service: ReportingService = Depends(_get_reporting_service),
) -> List[CashierPerformanceResponse]:
    """
    Get cashier performance metrics.

    Analyzes transactions by cashier to show transaction counts, total sales,
    average transaction values, and void/refund counts for performance tracking.

    **Parameters:**
    - **venue_id**: UUID of the venue to generate the report for
    - **date_from**: Start date of the reporting period (inclusive)
    - **date_to**: End date of the reporting period (inclusive)

    **Example Request:**
    ```
    GET /api/v1/reports/cashier-performance?venue_id=550e8400-e29b-41d4-a716-446655440000&date_from=2024-01-01&date_to=2024-01-31
    ```

    **Example Response:**
    ```json
    [
        {
            "cashier_id": "550e8400-e29b-41d4-a716-446655440000",
            "cashier_name": "John Smith",
            "transaction_count": 145,
            "total_sales": "4352.75",
            "average_transaction": "30.02",
            "void_count": 3,
            "refund_count": 5
        },
        {
            "cashier_id": "660e8400-e29b-41d4-a716-446655440001",
            "cashier_name": "Jane Doe",
            "transaction_count": 132,
            "total_sales": "3967.50",
            "average_transaction": "30.06",
            "void_count": 1,
            "refund_count": 2
        }
    ]
    ```

    **Notes:**
    - Cashiers are ranked by total sales (descending)
    - Void counts include transactions marked as voided
    - Refund counts include processed refunds on transactions handled by the cashier
    """
    performance = await service.get_cashier_performance(
        venue_id=venue_id,
        date_from=date_from,
        date_to=date_to,
    )

    return [
        CashierPerformanceResponse(
            cashier_id=item.cashier_id,
            cashier_name=item.cashier_name,
            transaction_count=item.transaction_count,
            total_sales=str(item.total_sales),
            average_transaction=str(item.average_transaction),
            void_count=item.void_count,
            refund_count=item.refund_count,
        )
        for item in performance
    ]


@router.get(
    "/discount-usage",
    response_model=List[DiscountUsageResponse],
    summary="Get discount usage statistics",
    responses={
        200: {
            "description": "Discount usage data retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "discount_name": "Summer Sale 20%",
                            "usage_count": 156,
                            "total_discount_amount": "2340.50",
                        },
                        {
                            "discount_name": "Member 10% Off",
                            "usage_count": 234,
                            "total_discount_amount": "1872.00",
                        },
                        {
                            "discount_name": "Happy Hour Special",
                            "usage_count": 89,
                            "total_discount_amount": "445.00",
                        },
                    ]
                }
            },
        }
    },
)
async def get_discount_usage(
    venue_id: UUID = Query(..., description="UUID of the venue to report on"),
    date_from: datetime.date = Query(..., description="Start date (inclusive) for the report"),
    date_to: datetime.date = Query(..., description="End date (inclusive) for the report"),
    current_user: dict = Depends(get_current_user),
    service: ReportingService = Depends(_get_reporting_service),
) -> List[DiscountUsageResponse]:
    """
    Get discount usage statistics.

    Analyzes transaction line items with applied discounts to show which discounts
    were used, how often, and total discount amounts.

    **Parameters:**
    - **venue_id**: UUID of the venue to generate the report for
    - **date_from**: Start date of the reporting period (inclusive)
    - **date_to**: End date of the reporting period (inclusive)

    **Example Request:**
    ```
    GET /api/v1/reports/discount-usage?venue_id=550e8400-e29b-41d4-a716-446655440000&date_from=2024-01-01&date_to=2024-01-31
    ```

    **Example Response:**
    ```json
    [
        {"discount_name": "Summer Sale 20%", "usage_count": 156, "total_discount_amount": "2340.50"},
        {"discount_name": "Member 10% Off", "usage_count": 234, "total_discount_amount": "1872.00"},
        {"discount_name": "Happy Hour Special", "usage_count": 89, "total_discount_amount": "445.00"}
    ]
    ```

    **Notes:**
    - Discounts are ranked by total discount amount (descending)
    - Only discounts that were actually applied to transactions are included
    """
    usage = await service.get_discount_usage(
        venue_id=venue_id,
        date_from=date_from,
        date_to=date_to,
    )

    return [
        DiscountUsageResponse(
            discount_name=item["discount_name"],
            usage_count=item["usage_count"],
            total_discount_amount=item["total_discount_amount"],
        )
        for item in usage
    ]


@router.get(
    "/transaction-types",
    response_model=List[TransactionTypeResponse],
    summary="Get transaction type breakdown",
    responses={
        200: {
            "description": "Transaction type breakdown retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {"type": "bowling", "count": 523, "revenue": "15690.00"},
                        {"type": "food", "count": 892, "revenue": "13380.00"},
                        {"type": "arcade", "count": 1234, "revenue": "12340.00"},
                        {"type": "party", "count": 45, "revenue": "9000.00"},
                        {"type": "retail", "count": 234, "revenue": "4680.00"},
                    ]
                }
            },
        }
    },
)
async def get_transaction_type_breakdown(
    venue_id: UUID = Query(..., description="UUID of the venue to report on"),
    date_from: datetime.date = Query(..., description="Start date (inclusive) for the report"),
    date_to: datetime.date = Query(..., description="End date (inclusive) for the report"),
    current_user: dict = Depends(get_current_user),
    service: ReportingService = Depends(_get_reporting_service),
) -> List[TransactionTypeResponse]:
    """
    Get transaction type breakdown.

    Groups transactions by type (bowling, arcade, food, party, etc.) to show
    distribution of business across different service categories.

    **Parameters:**
    - **venue_id**: UUID of the venue to generate the report for
    - **date_from**: Start date of the reporting period (inclusive)
    - **date_to**: End date of the reporting period (inclusive)

    **Example Request:**
    ```
    GET /api/v1/reports/transaction-types?venue_id=550e8400-e29b-41d4-a716-446655440000&date_from=2024-01-01&date_to=2024-01-31
    ```

    **Example Response:**
    ```json
    [
        {"type": "bowling", "count": 523, "revenue": "15690.00"},
        {"type": "food", "count": 892, "revenue": "13380.00"},
        {"type": "arcade", "count": 1234, "revenue": "12340.00"},
        {"type": "party", "count": 45, "revenue": "9000.00"},
        {"type": "retail", "count": 234, "revenue": "4680.00"}
    ]
    ```

    **Transaction Types:**
    - bowling
    - arcade
    - food
    - party
    - membership
    - retail
    - other
    """
    breakdown = await service.get_transaction_type_breakdown(
        venue_id=venue_id,
        date_from=date_from,
        date_to=date_to,
    )

    return [
        TransactionTypeResponse(
            type=item["type"],
            count=item["count"],
            revenue=item["revenue"],
        )
        for item in breakdown
    ]
