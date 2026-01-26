"""
=============================================================================
FILE: services/performance_service.py
PURPOSE: Venue performance tracking and benchmarking
=============================================================================
"""

from datetime import date, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.venue import VenuePerformance, Venue
from app.schemas.venue import VenuePerformanceCreate

logger = structlog.get_logger()


class PerformanceService:
    """Service for venue performance tracking and benchmarking."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_performance(
        self,
        venue_id: UUID,
        data: VenuePerformanceCreate,
    ) -> VenuePerformance:
        """
        Record daily performance metrics.

        Args:
            venue_id: Venue UUID
            data: Performance data

        Returns:
            Created/updated performance record
        """
        # Check for existing record
        existing = await self.get_performance(venue_id, data.date)

        if existing:
            # Update existing record
            update_dict = data.model_dump(exclude={"date"})
            for field, value in update_dict.items():
                setattr(existing, field, value)

            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        # Create new record
        record = VenuePerformance(
            venue_id=venue_id,
            **data.model_dump(),
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)

        logger.info(
            "performance_recorded",
            venue_id=str(venue_id),
            date=str(data.date),
            revenue=data.revenue,
        )

        return record

    async def get_performance(
        self,
        venue_id: UUID,
        for_date: date,
    ) -> Optional[VenuePerformance]:
        """Get performance for a specific date."""
        result = await self.db.execute(
            select(VenuePerformance).where(
                VenuePerformance.venue_id == venue_id,
                VenuePerformance.date == for_date,
            )
        )
        return result.scalar_one_or_none()

    async def get_performance_range(
        self,
        venue_id: UUID,
        start_date: date,
        end_date: date,
    ) -> List[VenuePerformance]:
        """Get performance records for a date range."""
        result = await self.db.execute(
            select(VenuePerformance)
            .where(
                VenuePerformance.venue_id == venue_id,
                VenuePerformance.date >= start_date,
                VenuePerformance.date <= end_date,
            )
            .order_by(VenuePerformance.date)
        )
        return list(result.scalars().all())

    async def get_performance_summary(
        self,
        venue_id: UUID,
        period_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get performance summary for a period.

        Args:
            venue_id: Venue UUID
            period_days: Number of days to summarize

        Returns:
            Summary statistics
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)

        result = await self.db.execute(
            select(
                func.sum(VenuePerformance.revenue).label("total_revenue"),
                func.avg(VenuePerformance.revenue).label("avg_daily_revenue"),
                func.sum(VenuePerformance.guest_count).label("total_guests"),
                func.avg(VenuePerformance.guest_count).label("avg_daily_guests"),
                func.avg(VenuePerformance.revenue_per_guest).label("avg_revenue_per_guest"),
                func.sum(VenuePerformance.transaction_count).label("total_transactions"),
                func.avg(VenuePerformance.average_transaction).label("avg_transaction"),
                func.avg(VenuePerformance.nps_score).label("avg_nps"),
                func.avg(VenuePerformance.average_rating).label("avg_rating"),
                func.avg(VenuePerformance.labor_cost_percentage).label("avg_labor_cost_pct"),
                func.avg(VenuePerformance.food_waste_percentage).label("avg_food_waste_pct"),
                func.count().label("days_recorded"),
            )
            .where(
                VenuePerformance.venue_id == venue_id,
                VenuePerformance.date >= start_date,
                VenuePerformance.date <= end_date,
            )
        )

        row = result.one()

        return {
            "period_start": start_date,
            "period_end": end_date,
            "period_days": period_days,
            "days_recorded": row.days_recorded or 0,
            "total_revenue": float(row.total_revenue or 0),
            "avg_daily_revenue": float(row.avg_daily_revenue or 0),
            "total_guests": int(row.total_guests or 0),
            "avg_daily_guests": int(row.avg_daily_guests or 0),
            "avg_revenue_per_guest": float(row.avg_revenue_per_guest or 0),
            "total_transactions": int(row.total_transactions or 0),
            "avg_transaction": float(row.avg_transaction or 0),
            "avg_nps": float(row.avg_nps) if row.avg_nps else None,
            "avg_rating": float(row.avg_rating) if row.avg_rating else None,
            "avg_labor_cost_pct": float(row.avg_labor_cost_pct) if row.avg_labor_cost_pct else None,
            "avg_food_waste_pct": float(row.avg_food_waste_pct) if row.avg_food_waste_pct else None,
        }

    async def get_benchmarks(
        self,
        venue_ids: Optional[List[UUID]] = None,
        period_days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get benchmarks comparing venues.

        Args:
            venue_ids: Optional list of venues to compare (all if None)
            period_days: Period for comparison

        Returns:
            List of venue benchmarks with rankings
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)

        # Build query for venue aggregates
        query = (
            select(
                VenuePerformance.venue_id,
                Venue.name.label("venue_name"),
                func.sum(VenuePerformance.revenue).label("total_revenue"),
                func.sum(VenuePerformance.guest_count).label("total_guests"),
                func.avg(VenuePerformance.revenue_per_guest).label("avg_rpg"),
                func.avg(VenuePerformance.nps_score).label("avg_nps"),
            )
            .join(Venue, Venue.id == VenuePerformance.venue_id)
            .where(
                VenuePerformance.date >= start_date,
                VenuePerformance.date <= end_date,
                Venue.is_deleted == False,
            )
            .group_by(VenuePerformance.venue_id, Venue.name)
        )

        if venue_ids:
            query = query.where(VenuePerformance.venue_id.in_(venue_ids))

        query = query.order_by(func.sum(VenuePerformance.revenue).desc())

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return []

        # Calculate network averages
        total_revenue = sum(r.total_revenue or 0 for r in rows)
        total_guests = sum(r.total_guests or 0 for r in rows)
        avg_revenue = total_revenue / len(rows) if rows else 0
        avg_guests = total_guests / len(rows) if rows else 0

        # Build benchmarks with rankings
        benchmarks = []
        for rank, row in enumerate(rows, 1):
            venue_revenue = float(row.total_revenue or 0)
            venue_guests = int(row.total_guests or 0)

            benchmarks.append({
                "venue_id": row.venue_id,
                "venue_name": row.venue_name,
                "period_start": start_date,
                "period_end": end_date,
                "revenue_rank": rank,
                "total_revenue": venue_revenue,
                "total_guests": venue_guests,
                "avg_revenue_per_guest": float(row.avg_rpg or 0),
                "avg_nps": float(row.avg_nps) if row.avg_nps else None,
                "revenue_vs_average": (
                    ((venue_revenue - avg_revenue) / avg_revenue * 100)
                    if avg_revenue > 0 else 0
                ),
                "guests_vs_average": (
                    ((venue_guests - avg_guests) / avg_guests * 100)
                    if avg_guests > 0 else 0
                ),
                "revenue_percentile": (
                    (len(rows) - rank + 1) / len(rows) * 100
                ),
            })

        return benchmarks

    async def get_leaderboard(
        self,
        metric: str = "revenue",
        period_days: int = 30,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get venue leaderboard by metric.

        Args:
            metric: Metric to rank by (revenue, guests, nps, etc.)
            period_days: Period for ranking
            limit: Number of venues to return

        Returns:
            Leaderboard data
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)

        # Map metric to aggregation
        metric_map = {
            "revenue": func.sum(VenuePerformance.revenue),
            "guests": func.sum(VenuePerformance.guest_count),
            "revenue_per_guest": func.avg(VenuePerformance.revenue_per_guest),
            "nps": func.avg(VenuePerformance.nps_score),
            "rating": func.avg(VenuePerformance.average_rating),
            "transactions": func.sum(VenuePerformance.transaction_count),
        }

        agg_func = metric_map.get(metric, metric_map["revenue"])

        result = await self.db.execute(
            select(
                VenuePerformance.venue_id,
                Venue.name.label("venue_name"),
                Venue.city,
                Venue.state,
                agg_func.label("metric_value"),
            )
            .join(Venue, Venue.id == VenuePerformance.venue_id)
            .where(
                VenuePerformance.date >= start_date,
                VenuePerformance.date <= end_date,
                Venue.is_deleted == False,
            )
            .group_by(
                VenuePerformance.venue_id,
                Venue.name,
                Venue.city,
                Venue.state,
            )
            .order_by(agg_func.desc())
            .limit(limit)
        )

        rows = result.all()

        return [
            {
                "rank": i + 1,
                "venue_id": row.venue_id,
                "venue_name": row.venue_name,
                "location": f"{row.city}, {row.state}",
                "metric": metric,
                "value": float(row.metric_value) if row.metric_value else 0,
            }
            for i, row in enumerate(rows)
        ]

    async def get_trends(
        self,
        venue_id: UUID,
        metric: str = "revenue",
        period_days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get daily trend data for a metric.

        Args:
            venue_id: Venue UUID
            metric: Metric to track
            period_days: Number of days

        Returns:
            Daily trend data
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)

        records = await self.get_performance_range(venue_id, start_date, end_date)

        metric_attr_map = {
            "revenue": "revenue",
            "guests": "guest_count",
            "revenue_per_guest": "revenue_per_guest",
            "transactions": "transaction_count",
            "nps": "nps_score",
            "rating": "average_rating",
            "labor_cost": "labor_cost_percentage",
        }

        attr_name = metric_attr_map.get(metric, "revenue")

        return [
            {
                "date": record.date,
                "value": getattr(record, attr_name, 0) or 0,
            }
            for record in records
        ]
