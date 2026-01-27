"""
=============================================================================
FILE: api/v1/analytics.py
PURPOSE: Customer analytics API endpoints
=============================================================================
"""

from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user
from app.services.analytics_service import AnalyticsService
from app.schemas.customer import (
    LTVResponse,
    ChurnRiskResponse,
    CustomerAnalytics,
)

# OpenAPI Tags
TAGS = ["Analytics"]

router = APIRouter(tags=TAGS)


@router.get(
    "/dashboard",
    summary="Get analytics dashboard",
    description="""
    Get a comprehensive customer analytics dashboard for a venue.

    **Returns:**
    - **Customer metrics**: Total, active, new customers
    - **Segment breakdown**: Distribution across VIP, Premium, Standard, etc.
    - **Revenue metrics**: Total revenue, average LTV
    - **Visit metrics**: Total visits, unique visitors
    - **Churn stats**: At-risk and churned customer counts
    - **Top customers**: Highest LTV customers

    **Parameters:**
    - period_days: Analysis period (default 30, max 365)

    This endpoint aggregates data from multiple sources to provide
    a single comprehensive view for dashboard displays.
    """,
    responses={
        200: {"description": "Dashboard analytics data"},
        401: {"description": "Unauthorized"},
    },
)
async def get_analytics_dashboard(
    venue_id: UUID,
    period_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get comprehensive customer analytics dashboard."""
    service = AnalyticsService(db)

    period_end = date.today()
    period_start = period_end - timedelta(days=period_days)

    analytics = await service.get_customer_analytics(
        venue_id=venue_id,
        period_start=period_start,
        period_end=period_end,
    )

    return analytics


@router.get(
    "/customer/{customer_id}/ltv",
    response_model=LTVResponse,
    summary="Get customer LTV",
    description="""
    Get Lifetime Value (LTV) metrics for a specific customer.

    **Returns:**
    - **calculated_ltv**: Predicted lifetime value
    - **total_revenue**: Actual revenue to date
    - **total_visits**: Number of visits
    - **avg_spend**: Average spend per visit
    - **visit_frequency**: Visits per month
    - **first_visit_date / last_visit_date**: Visit date range

    **LTV Calculation:**
    ```
    LTV = avg_spend × visit_frequency × expected_lifespan
    ```

    Where expected_lifespan defaults to 12 months but can be
    configured per venue based on historical data.
    """,
    responses={
        200: {"description": "Customer LTV data"},
        404: {"description": "LTV data not found for customer"},
    },
)
async def get_customer_ltv(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get lifetime value for a customer."""
    service = AnalyticsService(db)
    ltv = await service.get_customer_ltv(customer_id)

    if not ltv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LTV data not found for customer",
        )

    return LTVResponse.model_validate(ltv)


@router.get(
    "/customer/{customer_id}/churn-risk",
    response_model=ChurnRiskResponse,
    summary="Get customer churn risk",
    description="""
    Get churn risk assessment for a specific customer.

    **Returns:**
    - **risk_score**: Numeric score (0-100, higher = more risk)
    - **risk_level**: LOW, MEDIUM, HIGH, or CRITICAL
    - **days_since_last_visit**: Days since customer's last visit
    - **calculated_at**: When the risk was last calculated

    **Risk Level Thresholds:**
    - LOW: Last visit within 30 days (score 0-30)
    - MEDIUM: 31-60 days since last visit (score 31-60)
    - HIGH: 61-90 days since last visit (score 61-90)
    - CRITICAL: 90+ days since last visit (score 90-100)

    **Events published:** `churn.risk_high` when risk becomes HIGH or CRITICAL

    Use this to identify customers needing win-back campaigns.
    """,
    responses={
        200: {"description": "Customer churn risk data"},
        404: {"description": "Churn risk data not found for customer"},
    },
)
async def get_customer_churn_risk(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get churn risk for a customer."""
    service = AnalyticsService(db)
    churn_risk = await service.get_customer_churn_risk(customer_id)

    if not churn_risk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Churn risk data not found for customer",
        )

    return ChurnRiskResponse.model_validate(churn_risk)


@router.get(
    "/customer/{customer_id}/next-visit",
    summary="Predict next visit",
    description="""
    Get AI-powered next visit prediction for a customer.

    **Returns (when available):**
    - **predicted_date**: Expected next visit date
    - **confidence**: Prediction confidence (0-100%)
    - **factors**: Contributing factors to the prediction

    **Note**: This endpoint requires the AI/ML prediction service
    to be enabled and trained on historical data. If not available,
    returns a placeholder response.

    Predictions are based on:
    - Historical visit patterns
    - Day-of-week preferences
    - Seasonal trends
    - Time since last visit
    """,
    responses={
        200: {"description": "Next visit prediction"},
    },
)
async def get_next_visit_prediction(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get next visit prediction for a customer."""
    # This would be populated by AI/ML predictions
    return {
        "customer_id": str(customer_id),
        "predicted_date": None,
        "confidence": 0,
        "message": "Prediction not yet available",
    }


@router.get(
    "/revenue",
    summary="Get revenue analytics",
    description="""
    Get revenue-focused analytics for a venue.

    **Returns:**
    - **total_revenue**: Total revenue for the period
    - **avg_ltv**: Average customer lifetime value
    - **active_customers**: Number of customers who visited
    - **top_customers**: Highest revenue customers

    **Use cases:**
    - Revenue dashboards
    - Financial reporting
    - Top customer identification
    - Revenue trend analysis
    """,
    responses={
        200: {"description": "Revenue analytics data"},
    },
)
async def get_revenue_analytics(
    venue_id: UUID,
    period_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get revenue analytics."""
    service = AnalyticsService(db)

    period_end = date.today()
    period_start = period_end - timedelta(days=period_days)

    analytics = await service.get_customer_analytics(
        venue_id=venue_id,
        period_start=period_start,
        period_end=period_end,
    )

    return {
        "period_start": period_start,
        "period_end": period_end,
        "total_revenue": analytics["total_revenue"],
        "avg_ltv": analytics["avg_ltv"],
        "active_customers": analytics["active_customers"],
        "top_customers": analytics["top_customers"],
    }


@router.get(
    "/churn",
    summary="Get churn analytics",
    description="""
    Get churn-focused analytics for customer retention.

    **Returns:**
    - **at_risk_count**: Customers at risk of churning
    - **churned_count**: Customers who have churned
    - **churn_rate**: Percentage of customers lost
    - **risk_distribution**: Breakdown by risk level

    **Use cases:**
    - Churn prevention dashboards
    - Win-back campaign targeting
    - Retention strategy planning
    - Customer health monitoring
    """,
    responses={
        200: {"description": "Churn analytics data"},
    },
)
async def get_churn_analytics(
    venue_id: UUID,
    period_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get churn analytics."""
    service = AnalyticsService(db)

    period_end = date.today()
    period_start = period_end - timedelta(days=period_days)

    analytics = await service.get_customer_analytics(
        venue_id=venue_id,
        period_start=period_start,
        period_end=period_end,
    )

    return analytics["churn_stats"]


@router.get(
    "/segments",
    summary="Get segment analytics",
    description="""
    Get segment distribution analytics for a venue.

    **Returns:**
    - **total_customers**: Total customer count
    - **segments**: Breakdown by segment type with counts and percentages

    **Segment types tracked:**
    - VIP, Premium, Standard (engagement tiers)
    - New (recent acquisitions)
    - At-Risk, Churned, Inactive (retention risk)

    **Use cases:**
    - Segment health monitoring
    - Marketing campaign targeting
    - Customer base composition analysis
    """,
    responses={
        200: {"description": "Segment analytics data"},
    },
)
async def get_segment_analytics(
    venue_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get segment distribution analytics."""
    service = AnalyticsService(db)

    period_end = date.today()
    period_start = period_end - timedelta(days=30)

    analytics = await service.get_customer_analytics(
        venue_id=venue_id,
        period_start=period_start,
        period_end=period_end,
    )

    return {
        "total_customers": analytics["total_customers"],
        "segments": analytics["segment_breakdown"],
    }
