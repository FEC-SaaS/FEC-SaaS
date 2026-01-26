"""
=============================================================================
FILE: services/analytics_service.py
PURPOSE: Party analytics and reporting business logic
=============================================================================
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
from uuid import UUID

from sqlalchemy import select, func, and_, case, extract
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.party import (
    PartyBooking,
    PartyBookingAddon,
    PartyPackage,
    PartyAddon,
    PartyTimeline,
    CorporateEvent,
    BookingStatus,
    BookingType,
    PackageType,
    TimelineStatus,
    CorporateEventStatus,
)
from app.schemas.party import (
    PartyRevenueStats,
    PartyPerformanceMetrics,
    UpsellConversionStats,
)

logger = structlog.get_logger()


class AnalyticsService:
    """Service for party analytics and reporting."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_revenue_stats(
        self,
        venue_id: UUID,
        start_date: date,
        end_date: date,
        include_comparison: bool = True,
    ) -> PartyRevenueStats:
        """
        Get party revenue statistics for a date range.

        Args:
            venue_id: Venue UUID
            start_date: Start of period
            end_date: End of period
            include_comparison: Include comparison to previous period

        Returns:
            PartyRevenueStats with revenue breakdown
        """
        # Main query for bookings in period
        result = await self.db.execute(
            select(
                func.sum(PartyBooking.total_price).label("total_revenue"),
                func.count(PartyBooking.id).label("total_bookings"),
                func.avg(PartyBooking.total_price).label("avg_booking_value"),
                func.sum(PartyBooking.addons_total).label("addons_revenue"),
                func.sum(PartyBooking.deposit_amount).label("deposit_revenue"),
            )
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date >= start_date,
                    PartyBooking.party_date <= end_date,
                    PartyBooking.is_deleted == False,
                    PartyBooking.status.in_([
                        BookingStatus.COMPLETED,
                        BookingStatus.FULLY_PAID,
                    ]),
                )
            )
        )
        row = result.first()

        total_revenue = Decimal(str(row.total_revenue or 0))
        total_bookings = row.total_bookings or 0
        avg_booking_value = Decimal(str(row.avg_booking_value or 0))
        addons_revenue = Decimal(str(row.addons_revenue or 0))
        deposit_revenue = Decimal(str(row.deposit_revenue or 0))

        # Revenue by package type
        package_type_result = await self.db.execute(
            select(
                PartyPackage.package_type,
                func.sum(PartyBooking.total_price).label("revenue"),
            )
            .join(PartyPackage)
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date >= start_date,
                    PartyBooking.party_date <= end_date,
                    PartyBooking.is_deleted == False,
                    PartyBooking.status.in_([
                        BookingStatus.COMPLETED,
                        BookingStatus.FULLY_PAID,
                    ]),
                )
            )
            .group_by(PartyPackage.package_type)
        )
        revenue_by_package_type = {
            str(row.package_type.value): Decimal(str(row.revenue or 0))
            for row in package_type_result
        }

        # Revenue by booking type
        booking_type_result = await self.db.execute(
            select(
                PartyBooking.booking_type,
                func.sum(PartyBooking.total_price).label("revenue"),
            )
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date >= start_date,
                    PartyBooking.party_date <= end_date,
                    PartyBooking.is_deleted == False,
                    PartyBooking.status.in_([
                        BookingStatus.COMPLETED,
                        BookingStatus.FULLY_PAID,
                    ]),
                )
            )
            .group_by(PartyBooking.booking_type)
        )
        revenue_by_booking_type = {
            str(row.booking_type.value): Decimal(str(row.revenue or 0))
            for row in booking_type_result
        }

        # Top packages
        top_packages_result = await self.db.execute(
            select(
                PartyPackage.id,
                PartyPackage.package_name,
                func.count(PartyBooking.id).label("booking_count"),
                func.sum(PartyBooking.total_price).label("revenue"),
            )
            .join(PartyPackage)
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date >= start_date,
                    PartyBooking.party_date <= end_date,
                    PartyBooking.is_deleted == False,
                )
            )
            .group_by(PartyPackage.id, PartyPackage.package_name)
            .order_by(func.sum(PartyBooking.total_price).desc())
            .limit(5)
        )
        top_packages = [
            {
                "package_id": str(row.id),
                "package_name": row.package_name,
                "booking_count": row.booking_count,
                "revenue": float(row.revenue or 0),
            }
            for row in top_packages_result
        ]

        # Top addons
        top_addons_result = await self.db.execute(
            select(
                PartyAddon.id,
                PartyAddon.addon_name,
                func.sum(PartyBookingAddon.quantity).label("quantity_sold"),
                func.sum(PartyBookingAddon.total_price).label("revenue"),
            )
            .join(PartyAddon)
            .join(PartyBooking)
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date >= start_date,
                    PartyBooking.party_date <= end_date,
                    PartyBooking.is_deleted == False,
                )
            )
            .group_by(PartyAddon.id, PartyAddon.addon_name)
            .order_by(func.sum(PartyBookingAddon.total_price).desc())
            .limit(5)
        )
        top_addons = [
            {
                "addon_id": str(row.id),
                "addon_name": row.addon_name,
                "quantity_sold": row.quantity_sold or 0,
                "revenue": float(row.revenue or 0),
            }
            for row in top_addons_result
        ]

        # Comparison to previous period
        comparison = None
        if include_comparison:
            period_days = (end_date - start_date).days + 1
            prev_end = start_date - timedelta(days=1)
            prev_start = prev_end - timedelta(days=period_days - 1)

            prev_result = await self.db.execute(
                select(
                    func.sum(PartyBooking.total_price).label("prev_revenue"),
                    func.count(PartyBooking.id).label("prev_bookings"),
                )
                .where(
                    and_(
                        PartyBooking.venue_id == venue_id,
                        PartyBooking.party_date >= prev_start,
                        PartyBooking.party_date <= prev_end,
                        PartyBooking.is_deleted == False,
                        PartyBooking.status.in_([
                            BookingStatus.COMPLETED,
                            BookingStatus.FULLY_PAID,
                        ]),
                    )
                )
            )
            prev_row = prev_result.first()
            prev_revenue = Decimal(str(prev_row.prev_revenue or 0))
            prev_bookings = prev_row.prev_bookings or 0

            if prev_revenue > 0:
                revenue_change = float((total_revenue - prev_revenue) / prev_revenue * 100)
            else:
                revenue_change = 100.0 if total_revenue > 0 else 0.0

            if prev_bookings > 0:
                bookings_change = float((total_bookings - prev_bookings) / prev_bookings * 100)
            else:
                bookings_change = 100.0 if total_bookings > 0 else 0.0

            comparison = {
                "revenue_change_pct": round(revenue_change, 1),
                "bookings_change_pct": round(bookings_change, 1),
            }

        return PartyRevenueStats(
            period_start=start_date,
            period_end=end_date,
            total_revenue=total_revenue,
            total_bookings=total_bookings,
            average_booking_value=avg_booking_value,
            total_addons_revenue=addons_revenue,
            deposit_revenue=deposit_revenue,
            revenue_by_package_type=revenue_by_package_type,
            revenue_by_booking_type=revenue_by_booking_type,
            top_packages=top_packages,
            top_addons=top_addons,
            comparison_to_previous=comparison,
        )

    async def get_performance_metrics(
        self,
        venue_id: UUID,
        start_date: date,
        end_date: date,
    ) -> PartyPerformanceMetrics:
        """
        Get party performance metrics for a date range.

        Returns metrics like completion rate, average party size, on-time performance, etc.
        """
        # Booking counts by status
        status_result = await self.db.execute(
            select(
                PartyBooking.status,
                func.count(PartyBooking.id).label("count"),
            )
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date >= start_date,
                    PartyBooking.party_date <= end_date,
                    PartyBooking.is_deleted == False,
                )
            )
            .group_by(PartyBooking.status)
        )

        status_counts = {row.status: row.count for row in status_result}
        total_parties = sum(status_counts.values())
        completed = status_counts.get(BookingStatus.COMPLETED, 0)
        cancelled = status_counts.get(BookingStatus.CANCELLED, 0)
        no_shows = status_counts.get(BookingStatus.NO_SHOW, 0)

        completion_rate = (completed / total_parties * 100) if total_parties > 0 else 0.0
        cancellation_rate = (cancelled / total_parties * 100) if total_parties > 0 else 0.0

        # Average party size
        size_result = await self.db.execute(
            select(func.avg(PartyBooking.guest_count))
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date >= start_date,
                    PartyBooking.party_date <= end_date,
                    PartyBooking.is_deleted == False,
                )
            )
        )
        avg_party_size = float(size_result.scalar() or 0)

        # Average duration
        duration_result = await self.db.execute(
            select(func.avg(PartyPackage.duration_minutes))
            .join(PartyBooking)
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date >= start_date,
                    PartyBooking.party_date <= end_date,
                    PartyBooking.is_deleted == False,
                )
            )
        )
        avg_duration = float(duration_result.scalar() or 0)

        # Timeline performance
        timeline_result = await self.db.execute(
            select(
                func.count(PartyTimeline.id).label("total"),
                func.sum(case((PartyTimeline.status == TimelineStatus.COMPLETED, 1), else_=0)).label("completed"),
                func.sum(case((PartyTimeline.actual_time <= PartyTimeline.scheduled_time, 1), else_=0)).label("on_time"),
            )
            .join(PartyBooking)
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date >= start_date,
                    PartyBooking.party_date <= end_date,
                    PartyBooking.is_deleted == False,
                )
            )
        )
        timeline_row = timeline_result.first()
        timeline_total = timeline_row.total or 0
        timeline_completed = timeline_row.completed or 0
        on_time_count = timeline_row.on_time or 0

        on_time_rate = (on_time_count / timeline_completed * 100) if timeline_completed > 0 else 0.0
        timeline_completion_rate = (timeline_completed / timeline_total * 100) if timeline_total > 0 else 0.0

        # Busiest days
        day_result = await self.db.execute(
            select(
                extract("dow", PartyBooking.party_date).label("day_of_week"),
                func.count(PartyBooking.id).label("count"),
            )
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date >= start_date,
                    PartyBooking.party_date <= end_date,
                    PartyBooking.is_deleted == False,
                )
            )
            .group_by(extract("dow", PartyBooking.party_date))
            .order_by(func.count(PartyBooking.id).desc())
            .limit(3)
        )
        day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        busiest_days = [
            {"day": day_names[int(row.day_of_week)], "count": row.count}
            for row in day_result
        ]

        # Busiest times
        time_result = await self.db.execute(
            select(
                extract("hour", PartyBooking.start_time).label("hour"),
                func.count(PartyBooking.id).label("count"),
            )
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date >= start_date,
                    PartyBooking.party_date <= end_date,
                    PartyBooking.is_deleted == False,
                )
            )
            .group_by(extract("hour", PartyBooking.start_time))
            .order_by(func.count(PartyBooking.id).desc())
            .limit(3)
        )
        busiest_times = [
            {"hour": f"{int(row.hour):02d}:00", "count": row.count}
            for row in time_result
        ]

        return PartyPerformanceMetrics(
            period_start=start_date,
            period_end=end_date,
            total_parties=total_parties,
            completed_parties=completed,
            cancelled_parties=cancelled,
            no_show_parties=no_shows,
            completion_rate=round(completion_rate, 1),
            cancellation_rate=round(cancellation_rate, 1),
            average_party_size=round(avg_party_size, 1),
            average_duration_minutes=round(avg_duration, 0),
            on_time_start_rate=round(on_time_rate, 1),
            timeline_completion_rate=round(timeline_completion_rate, 1),
            busiest_days=busiest_days,
            busiest_times=busiest_times,
        )

    async def get_upsell_stats(
        self,
        venue_id: UUID,
        start_date: date,
        end_date: date,
    ) -> UpsellConversionStats:
        """
        Get upsell conversion statistics for a date range.

        Returns metrics on addon attachment rates and AI upsell performance.
        """
        # Total bookings and bookings with addons
        booking_result = await self.db.execute(
            select(
                func.count(PartyBooking.id).label("total"),
                func.count(case((PartyBooking.addons_total > 0, 1))).label("with_addons"),
                func.sum(PartyBooking.addons_total).label("addon_revenue"),
            )
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date >= start_date,
                    PartyBooking.party_date <= end_date,
                    PartyBooking.is_deleted == False,
                )
            )
        )
        row = booking_result.first()
        total_bookings = row.total or 0
        bookings_with_upsells = row.with_addons or 0
        total_upsell_revenue = Decimal(str(row.addon_revenue or 0))

        upsell_conversion_rate = (bookings_with_upsells / total_bookings * 100) if total_bookings > 0 else 0.0
        avg_upsell_value = (total_upsell_revenue / bookings_with_upsells) if bookings_with_upsells > 0 else Decimal("0.00")

        # Top converting addons
        addon_result = await self.db.execute(
            select(
                PartyAddon.id,
                PartyAddon.addon_name,
                func.count(PartyBookingAddon.id).label("times_added"),
                func.sum(PartyBookingAddon.total_price).label("revenue"),
            )
            .join(PartyAddon)
            .join(PartyBooking)
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date >= start_date,
                    PartyBooking.party_date <= end_date,
                    PartyBooking.is_deleted == False,
                )
            )
            .group_by(PartyAddon.id, PartyAddon.addon_name)
            .order_by(func.count(PartyBookingAddon.id).desc())
            .limit(5)
        )
        top_converting_addons = [
            {
                "addon_id": str(row.id),
                "addon_name": row.addon_name,
                "times_added": row.times_added,
                "revenue": float(row.revenue or 0),
                "conversion_rate": round(row.times_added / total_bookings * 100, 1) if total_bookings > 0 else 0,
            }
            for row in addon_result
        ]

        # Upsell by booking source
        source_result = await self.db.execute(
            select(
                PartyBooking.booking_source,
                func.count(PartyBooking.id).label("total"),
                func.count(case((PartyBooking.addons_total > 0, 1))).label("with_addons"),
            )
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date >= start_date,
                    PartyBooking.party_date <= end_date,
                    PartyBooking.is_deleted == False,
                    PartyBooking.booking_source != None,
                )
            )
            .group_by(PartyBooking.booking_source)
        )
        upsell_by_source = {
            row.booking_source: round(row.with_addons / row.total * 100, 1) if row.total > 0 else 0
            for row in source_result
        }

        # AI-suggested upsell acceptance
        ai_result = await self.db.execute(
            select(
                func.count(PartyBookingAddon.id).label("total_ai"),
                func.count(case((PartyBookingAddon.was_upsell_suggestion == True, 1))).label("ai_suggested"),
            )
            .join(PartyBooking)
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date >= start_date,
                    PartyBooking.party_date <= end_date,
                    PartyBooking.is_deleted == False,
                )
            )
        )
        ai_row = ai_result.first()
        total_ai_addons = ai_row.total_ai or 0
        ai_suggested = ai_row.ai_suggested or 0
        ai_acceptance_rate = (ai_suggested / total_ai_addons * 100) if total_ai_addons > 0 else None

        return UpsellConversionStats(
            period_start=start_date,
            period_end=end_date,
            total_bookings=total_bookings,
            bookings_with_upsells=bookings_with_upsells,
            upsell_conversion_rate=round(upsell_conversion_rate, 1),
            total_upsell_revenue=total_upsell_revenue,
            average_upsell_value=avg_upsell_value,
            top_converting_addons=top_converting_addons,
            upsell_acceptance_by_source=upsell_by_source,
            ai_suggested_acceptance_rate=round(ai_acceptance_rate, 1) if ai_acceptance_rate else None,
        )

    async def get_dashboard_summary(
        self,
        venue_id: UUID,
    ) -> Dict[str, Any]:
        """Get quick dashboard summary for today and this week."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        # Today's parties
        today_result = await self.db.execute(
            select(func.count(PartyBooking.id))
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date == today,
                    PartyBooking.is_deleted == False,
                    PartyBooking.status.not_in([
                        BookingStatus.CANCELLED,
                        BookingStatus.NO_SHOW,
                    ]),
                )
            )
        )
        today_parties = today_result.scalar() or 0

        # This week's bookings
        week_result = await self.db.execute(
            select(
                func.count(PartyBooking.id).label("count"),
                func.sum(PartyBooking.total_price).label("revenue"),
            )
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.party_date >= week_start,
                    PartyBooking.party_date <= week_end,
                    PartyBooking.is_deleted == False,
                )
            )
        )
        week_row = week_result.first()

        # Pending confirmations
        pending_result = await self.db.execute(
            select(func.count(PartyBooking.id))
            .where(
                and_(
                    PartyBooking.venue_id == venue_id,
                    PartyBooking.status == BookingStatus.PENDING,
                    PartyBooking.is_deleted == False,
                )
            )
        )
        pending_count = pending_result.scalar() or 0

        # Corporate leads
        leads_result = await self.db.execute(
            select(func.count(CorporateEvent.id))
            .where(
                and_(
                    CorporateEvent.venue_id == venue_id,
                    CorporateEvent.status.in_([
                        CorporateEventStatus.INQUIRY,
                        CorporateEventStatus.PROPOSAL_SENT,
                    ]),
                    CorporateEvent.is_deleted == False,
                )
            )
        )
        active_leads = leads_result.scalar() or 0

        return {
            "today_parties": today_parties,
            "week_bookings": week_row.count or 0,
            "week_revenue": float(week_row.revenue or 0),
            "pending_confirmations": pending_count,
            "active_corporate_leads": active_leads,
            "date": today.isoformat(),
        }
