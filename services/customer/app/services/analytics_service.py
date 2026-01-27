"""
=============================================================================
FILE: services/analytics_service.py
PURPOSE: Customer analytics business logic
=============================================================================
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy import select, func, and_, case, distinct
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.customer import (
    Customer,
    CustomerVisit,
    CustomerLTV,
    CustomerChurnRisk,
    CustomerSegment,
    SegmentType,
    RiskLevel,
)

logger = structlog.get_logger()


class AnalyticsService:
    """Service for customer analytics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_customer_analytics(
        self,
        venue_id: UUID,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Get comprehensive customer analytics."""
        # Total customers
        total_result = await self.db.execute(
            select(func.count())
            .select_from(Customer)
            .where(
                and_(
                    Customer.venue_id == venue_id,
                    Customer.is_active == True,
                    Customer.gdpr_data_deleted == False,
                )
            )
        )
        total_customers = total_result.scalar() or 0

        # Active customers (with visits in period)
        active_result = await self.db.execute(
            select(func.count(distinct(CustomerVisit.customer_id)))
            .join(Customer)
            .where(
                and_(
                    Customer.venue_id == venue_id,
                    func.date(CustomerVisit.check_in_time) >= period_start,
                    func.date(CustomerVisit.check_in_time) <= period_end,
                )
            )
        )
        active_customers = active_result.scalar() or 0

        # New customers (created in period)
        new_result = await self.db.execute(
            select(func.count())
            .select_from(Customer)
            .where(
                and_(
                    Customer.venue_id == venue_id,
                    func.date(Customer.created_at) >= period_start,
                    func.date(Customer.created_at) <= period_end,
                )
            )
        )
        new_customers = new_result.scalar() or 0

        # Average LTV
        ltv_result = await self.db.execute(
            select(func.avg(CustomerLTV.calculated_ltv))
            .join(Customer)
            .where(Customer.venue_id == venue_id)
        )
        avg_ltv = ltv_result.scalar() or Decimal("0.00")

        # Total revenue in period
        revenue_result = await self.db.execute(
            select(func.sum(CustomerVisit.total_spend))
            .join(Customer)
            .where(
                and_(
                    Customer.venue_id == venue_id,
                    func.date(CustomerVisit.check_in_time) >= period_start,
                    func.date(CustomerVisit.check_in_time) <= period_end,
                )
            )
        )
        total_revenue = revenue_result.scalar() or Decimal("0.00")

        # Visit stats
        visit_stats = await self._get_visit_stats(venue_id, period_start, period_end)

        # Segment breakdown
        segment_breakdown = await self._get_segment_breakdown(venue_id)

        # Churn stats
        churn_stats = await self._get_churn_stats(venue_id, period_start, period_end)

        # Top customers
        top_customers = await self._get_top_customers(venue_id, 10)

        # Growth rate
        previous_period_start = period_start - (period_end - period_start)
        previous_new = await self.db.execute(
            select(func.count())
            .select_from(Customer)
            .where(
                and_(
                    Customer.venue_id == venue_id,
                    func.date(Customer.created_at) >= previous_period_start,
                    func.date(Customer.created_at) < period_start,
                )
            )
        )
        previous_new_count = previous_new.scalar() or 0
        growth_rate = (
            ((new_customers - previous_new_count) / previous_new_count * 100)
            if previous_new_count > 0
            else 0
        )

        return {
            "period_start": period_start,
            "period_end": period_end,
            "total_customers": total_customers,
            "active_customers": active_customers,
            "new_customers": new_customers,
            "avg_ltv": avg_ltv,
            "total_revenue": total_revenue,
            "visit_stats": visit_stats,
            "segment_breakdown": segment_breakdown,
            "churn_stats": churn_stats,
            "top_customers": top_customers,
            "growth_rate": round(growth_rate, 2),
        }

    async def _get_visit_stats(
        self,
        venue_id: UUID,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Get visit statistics."""
        # Total visits
        total_visits_result = await self.db.execute(
            select(func.count())
            .select_from(CustomerVisit)
            .join(Customer)
            .where(
                and_(
                    Customer.venue_id == venue_id,
                    func.date(CustomerVisit.check_in_time) >= period_start,
                    func.date(CustomerVisit.check_in_time) <= period_end,
                )
            )
        )
        total_visits = total_visits_result.scalar() or 0

        # Unique customers
        unique_result = await self.db.execute(
            select(func.count(distinct(CustomerVisit.customer_id)))
            .join(Customer)
            .where(
                and_(
                    Customer.venue_id == venue_id,
                    func.date(CustomerVisit.check_in_time) >= period_start,
                    func.date(CustomerVisit.check_in_time) <= period_end,
                )
            )
        )
        unique_customers = unique_result.scalar() or 0

        # Average spend
        avg_spend_result = await self.db.execute(
            select(func.avg(CustomerVisit.total_spend))
            .join(Customer)
            .where(
                and_(
                    Customer.venue_id == venue_id,
                    func.date(CustomerVisit.check_in_time) >= period_start,
                    func.date(CustomerVisit.check_in_time) <= period_end,
                )
            )
        )
        avg_spend = avg_spend_result.scalar() or Decimal("0.00")

        # Total revenue
        revenue_result = await self.db.execute(
            select(func.sum(CustomerVisit.total_spend))
            .join(Customer)
            .where(
                and_(
                    Customer.venue_id == venue_id,
                    func.date(CustomerVisit.check_in_time) >= period_start,
                    func.date(CustomerVisit.check_in_time) <= period_end,
                )
            )
        )
        total_revenue = revenue_result.scalar() or Decimal("0.00")

        # Average party size
        avg_party_result = await self.db.execute(
            select(func.avg(CustomerVisit.guest_count))
            .join(Customer)
            .where(
                and_(
                    Customer.venue_id == venue_id,
                    func.date(CustomerVisit.check_in_time) >= period_start,
                    func.date(CustomerVisit.check_in_time) <= period_end,
                )
            )
        )
        avg_party_size = avg_party_result.scalar() or 0

        return {
            "period_start": period_start,
            "period_end": period_end,
            "total_visits": total_visits,
            "unique_customers": unique_customers,
            "new_customers": 0,  # Calculated separately
            "returning_customers": unique_customers,
            "avg_visit_duration_minutes": 0,
            "avg_spend_per_visit": avg_spend,
            "total_revenue": total_revenue,
            "avg_party_size": float(avg_party_size) if avg_party_size else 0,
            "peak_days": [],
            "peak_hours": [],
        }

    async def _get_segment_breakdown(self, venue_id: UUID) -> List[Dict[str, Any]]:
        """Get customer segment distribution."""
        result = await self.db.execute(
            select(
                CustomerSegment.segment_type,
                func.count(distinct(CustomerSegment.customer_id)).label("count"),
            )
            .join(Customer)
            .where(
                and_(
                    Customer.venue_id == venue_id,
                    Customer.is_active == True,
                )
            )
            .group_by(CustomerSegment.segment_type)
        )

        total_result = await self.db.execute(
            select(func.count())
            .select_from(Customer)
            .where(
                and_(
                    Customer.venue_id == venue_id,
                    Customer.is_active == True,
                )
            )
        )
        total = total_result.scalar() or 1

        segments = []
        for row in result.fetchall():
            segments.append({
                "segment_type": row.segment_type.value,
                "customer_count": row.count,
                "percentage": round(row.count / total * 100, 2),
                "avg_ltv": Decimal("0.00"),
                "avg_visits": 0,
                "avg_spend": Decimal("0.00"),
                "trend": "stable",
            })

        return segments

    async def _get_churn_stats(
        self,
        venue_id: UUID,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Get churn statistics."""
        # At risk counts by level
        risk_counts = {}
        for level in RiskLevel:
            result = await self.db.execute(
                select(func.count())
                .select_from(CustomerChurnRisk)
                .join(Customer)
                .where(
                    and_(
                        Customer.venue_id == venue_id,
                        Customer.is_active == True,
                        CustomerChurnRisk.risk_level == level,
                    )
                )
            )
            risk_counts[level.value] = result.scalar() or 0

        total_at_risk = risk_counts.get("high", 0) + risk_counts.get("critical", 0)

        return {
            "period_start": period_start,
            "period_end": period_end,
            "total_at_risk": total_at_risk,
            "high_risk_count": risk_counts.get("high", 0),
            "medium_risk_count": risk_counts.get("medium", 0),
            "low_risk_count": risk_counts.get("low", 0),
            "churned_count": risk_counts.get("critical", 0),
            "churn_rate": 0,
            "win_back_count": 0,
            "avg_days_to_churn": 0,
        }

    async def _get_top_customers(
        self,
        venue_id: UUID,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get top customers by revenue."""
        result = await self.db.execute(
            select(
                Customer.id,
                Customer.first_name,
                Customer.last_name,
                Customer.email,
                CustomerLTV.total_revenue,
                CustomerLTV.total_visits,
            )
            .join(CustomerLTV)
            .where(
                and_(
                    Customer.venue_id == venue_id,
                    Customer.is_active == True,
                )
            )
            .order_by(CustomerLTV.total_revenue.desc())
            .limit(limit)
        )

        customers = []
        for row in result.fetchall():
            customers.append({
                "id": str(row.id),
                "name": f"{row.first_name} {row.last_name}",
                "email": row.email,
                "total_revenue": row.total_revenue,
                "total_visits": row.total_visits,
            })

        return customers

    async def get_customer_ltv(self, customer_id: UUID) -> Optional[CustomerLTV]:
        """Get LTV for a customer."""
        result = await self.db.execute(
            select(CustomerLTV).where(CustomerLTV.customer_id == customer_id)
        )
        return result.scalar_one_or_none()

    async def get_customer_churn_risk(
        self,
        customer_id: UUID,
    ) -> Optional[CustomerChurnRisk]:
        """Get churn risk for a customer."""
        result = await self.db.execute(
            select(CustomerChurnRisk).where(
                CustomerChurnRisk.customer_id == customer_id
            )
        )
        return result.scalar_one_or_none()
