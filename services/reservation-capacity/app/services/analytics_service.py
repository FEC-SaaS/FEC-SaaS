"""Reservation analytics service."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog
from sqlalchemy import select, func, case, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import (
    NoShowHistory,
    Reservation,
    ReservationItem,
    ReservationStatus,
)

logger = structlog.get_logger()


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_utilization_analytics(
        self, venue_id: UUID, period_start: date, period_end: date,
        resource_type: Optional[str] = None,
    ) -> dict:
        base_query = select(Reservation).where(
            Reservation.venue_id == venue_id,
            Reservation.reservation_date >= period_start,
            Reservation.reservation_date <= period_end,
            Reservation.status.in_([
                ReservationStatus.CONFIRMED.value,
                ReservationStatus.CHECKED_IN.value,
                ReservationStatus.COMPLETED.value,
            ]),
        )
        if resource_type:
            base_query = base_query.where(Reservation.reservation_type == resource_type)

        count_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total_reservations = count_result.scalar() or 0

        # Daily breakdown
        daily_query = (
            select(
                Reservation.reservation_date,
                func.count(Reservation.id).label("count"),
            )
            .where(
                Reservation.venue_id == venue_id,
                Reservation.reservation_date >= period_start,
                Reservation.reservation_date <= period_end,
                Reservation.status.in_([
                    ReservationStatus.CONFIRMED.value,
                    ReservationStatus.CHECKED_IN.value,
                    ReservationStatus.COMPLETED.value,
                ]),
            )
            .group_by(Reservation.reservation_date)
            .order_by(Reservation.reservation_date)
        )
        if resource_type:
            daily_query = daily_query.where(Reservation.reservation_type == resource_type)
        daily_result = await self.db.execute(daily_query)
        daily_breakdown = [
            {"date": str(row.reservation_date), "reservations": row.count}
            for row in daily_result.all()
        ]

        num_days = max((period_end - period_start).days + 1, 1)
        avg_per_day = total_reservations / num_days if num_days > 0 else 0

        return {
            "venue_id": venue_id,
            "period_start": period_start,
            "period_end": period_end,
            "resource_type": resource_type,
            "avg_utilization_percentage": Decimal(str(round(avg_per_day * 10, 2))),
            "peak_utilization_percentage": Decimal(str(round(max((r["reservations"] for r in daily_breakdown), default=0) * 10, 2))),
            "total_reservations": total_reservations,
            "total_capacity_hours": Decimal("0"),
            "utilized_hours": Decimal("0"),
            "daily_breakdown": daily_breakdown,
        }

    async def get_no_show_analytics(
        self, venue_id: UUID, period_start: date, period_end: date,
    ) -> dict:
        # Total no-shows
        no_show_count_result = await self.db.execute(
            select(func.count(NoShowHistory.id))
            .join(Reservation, NoShowHistory.reservation_id == Reservation.id)
            .where(
                Reservation.venue_id == venue_id,
                NoShowHistory.no_show_date >= period_start,
                NoShowHistory.no_show_date <= period_end,
            )
        )
        total_no_shows = no_show_count_result.scalar() or 0

        # Total reservations in period
        total_res_result = await self.db.execute(
            select(func.count(Reservation.id)).where(
                Reservation.venue_id == venue_id,
                Reservation.reservation_date >= period_start,
                Reservation.reservation_date <= period_end,
            )
        )
        total_reservations = total_res_result.scalar() or 0
        no_show_rate = Decimal(str(round(total_no_shows / total_reservations * 100, 2))) if total_reservations > 0 else Decimal("0")

        # Lost revenue
        lost_revenue_result = await self.db.execute(
            select(func.coalesce(func.sum(NoShowHistory.reservation_value), 0))
            .join(Reservation, NoShowHistory.reservation_id == Reservation.id)
            .where(
                Reservation.venue_id == venue_id,
                NoShowHistory.no_show_date >= period_start,
                NoShowHistory.no_show_date <= period_end,
            )
        )
        estimated_lost_revenue = Decimal(str(lost_revenue_result.scalar() or 0))

        # By reason
        reason_result = await self.db.execute(
            select(NoShowHistory.reason, func.count(NoShowHistory.id).label("count"))
            .join(Reservation, NoShowHistory.reservation_id == Reservation.id)
            .where(
                Reservation.venue_id == venue_id,
                NoShowHistory.no_show_date >= period_start,
                NoShowHistory.no_show_date <= period_end,
                NoShowHistory.reason.isnot(None),
            )
            .group_by(NoShowHistory.reason)
        )
        no_shows_by_reason = {row.reason: row.count for row in reason_result.all()}

        return {
            "venue_id": venue_id,
            "period_start": period_start,
            "period_end": period_end,
            "total_no_shows": total_no_shows,
            "no_show_rate": no_show_rate,
            "estimated_lost_revenue": estimated_lost_revenue,
            "no_shows_by_reason": no_shows_by_reason,
            "no_shows_by_day": {},
            "top_no_show_customers": [],
        }

    async def get_revenue_analytics(
        self, venue_id: UUID, period_start: date, period_end: date,
    ) -> dict:
        # Revenue from reservation items
        revenue_result = await self.db.execute(
            select(
                func.coalesce(func.sum(ReservationItem.dynamic_price), func.sum(ReservationItem.base_price), 0).label("total"),
            )
            .join(Reservation, ReservationItem.reservation_id == Reservation.id)
            .where(
                Reservation.venue_id == venue_id,
                Reservation.reservation_date >= period_start,
                Reservation.reservation_date <= period_end,
                Reservation.status.in_([
                    ReservationStatus.COMPLETED.value,
                    ReservationStatus.CHECKED_IN.value,
                ]),
            )
        )
        total_revenue = Decimal(str(revenue_result.scalar() or 0))

        # Count
        count_result = await self.db.execute(
            select(func.count(Reservation.id)).where(
                Reservation.venue_id == venue_id,
                Reservation.reservation_date >= period_start,
                Reservation.reservation_date <= period_end,
                Reservation.status.in_([ReservationStatus.COMPLETED.value, ReservationStatus.CHECKED_IN.value]),
            )
        )
        total_count = count_result.scalar() or 0
        avg_revenue = total_revenue / total_count if total_count > 0 else Decimal("0")

        # Revenue by type
        type_result = await self.db.execute(
            select(
                Reservation.reservation_type,
                func.coalesce(func.sum(ReservationItem.dynamic_price), func.sum(ReservationItem.base_price), 0).label("revenue"),
            )
            .join(ReservationItem, Reservation.id == ReservationItem.reservation_id)
            .where(
                Reservation.venue_id == venue_id,
                Reservation.reservation_date >= period_start,
                Reservation.reservation_date <= period_end,
                Reservation.status.in_([ReservationStatus.COMPLETED.value, ReservationStatus.CHECKED_IN.value]),
            )
            .group_by(Reservation.reservation_type)
        )
        revenue_by_type = {row.reservation_type: Decimal(str(row.revenue)) for row in type_result.all()}

        # Revenue by channel
        channel_result = await self.db.execute(
            select(
                Reservation.booking_channel,
                func.count(Reservation.id).label("count"),
            )
            .where(
                Reservation.venue_id == venue_id,
                Reservation.reservation_date >= period_start,
                Reservation.reservation_date <= period_end,
                Reservation.booking_channel.isnot(None),
            )
            .group_by(Reservation.booking_channel)
        )
        revenue_by_channel = {row.booking_channel: Decimal(str(row.count)) for row in channel_result.all()}

        return {
            "venue_id": venue_id,
            "period_start": period_start,
            "period_end": period_end,
            "total_reservation_revenue": total_revenue,
            "avg_revenue_per_reservation": avg_revenue,
            "revenue_by_type": revenue_by_type,
            "revenue_by_channel": revenue_by_channel,
            "daily_revenue": [],
        }

    async def get_channel_analytics(
        self, venue_id: UUID, period_start: date, period_end: date,
    ) -> dict:
        total_result = await self.db.execute(
            select(func.count(Reservation.id)).where(
                Reservation.venue_id == venue_id,
                Reservation.reservation_date >= period_start,
                Reservation.reservation_date <= period_end,
            )
        )
        total_bookings = total_result.scalar() or 0

        channel_result = await self.db.execute(
            select(
                Reservation.booking_channel,
                func.count(Reservation.id).label("count"),
            )
            .where(
                Reservation.venue_id == venue_id,
                Reservation.reservation_date >= period_start,
                Reservation.reservation_date <= period_end,
                Reservation.booking_channel.isnot(None),
            )
            .group_by(Reservation.booking_channel)
        )
        bookings_by_channel = {row.booking_channel: row.count for row in channel_result.all()}

        return {
            "venue_id": venue_id,
            "period_start": period_start,
            "period_end": period_end,
            "total_bookings": total_bookings,
            "bookings_by_channel": bookings_by_channel,
            "conversion_rates": {},
            "avg_lead_time_by_channel": {},
        }
