"""
=============================================================================
FILE: services/visit_service.py
PURPOSE: Visit tracking business logic
=============================================================================
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.models.customer import (
    CustomerVisit,
    CustomerActivity,
    CustomerLTV,
    CustomerChurnRisk,
    VisitSource,
    ActivityType,
    RiskLevel,
)
from app.schemas.customer import (
    VisitCreate,
    VisitUpdate,
    VisitCheckout,
    ActivityCreate,
    PaginationParams,
)
from app.services.event_publisher import event_publisher

logger = structlog.get_logger()


class VisitService:
    """Service for visit tracking."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_visit(self, visit_data: VisitCreate) -> CustomerVisit:
        """Create a new visit record."""
        visit = CustomerVisit(
            customer_id=visit_data.customer_id,
            venue_id=visit_data.venue_id,
            check_in_time=visit_data.check_in_time,
            source=visit_data.source,
            guest_count=visit_data.guest_count,
            child_count=visit_data.child_count,
            adult_count=visit_data.adult_count,
            booking_id=visit_data.booking_id,
            notes=visit_data.notes,
            total_spend=Decimal("0.00"),
        )

        self.db.add(visit)
        await self.db.flush()

        # Add activities if provided
        if visit_data.activities:
            for activity_data in visit_data.activities:
                activity = CustomerActivity(
                    visit_id=visit.id,
                    activity_type=activity_data.activity_type,
                    activity_id=activity_data.activity_id,
                    activity_name=activity_data.activity_name,
                    start_time=activity_data.start_time,
                    end_time=activity_data.end_time,
                    duration_minutes=activity_data.duration_minutes,
                    amount_spent=activity_data.amount_spent,
                    satisfaction_score=activity_data.satisfaction_score,
                )
                self.db.add(activity)

        await self.db.flush()
        await self.db.refresh(visit)

        # Update customer LTV metrics
        await self._update_customer_metrics(visit_data.customer_id)

        logger.info(
            "visit_created",
            visit_id=str(visit.id),
            customer_id=str(visit.customer_id),
            source=visit.source.value,
        )

        # Publish event
        await event_publisher.publish_visit_checked_in(
            visit_id=visit.id,
            customer_id=visit.customer_id,
            venue_id=visit.venue_id,
            source=visit.source.value,
            guest_count=visit.guest_count,
        )

        return visit

    async def get_visit(self, visit_id: UUID) -> Optional[CustomerVisit]:
        """Get visit by ID with activities."""
        result = await self.db.execute(
            select(CustomerVisit)
            .options(selectinload(CustomerVisit.activities))
            .where(CustomerVisit.id == visit_id)
        )
        return result.scalar_one_or_none()

    async def list_visits(
        self,
        venue_id: UUID,
        pagination: PaginationParams,
        customer_id: Optional[UUID] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        source: Optional[VisitSource] = None,
    ) -> Tuple[List[CustomerVisit], int]:
        """List visits with filtering and pagination."""
        query = select(CustomerVisit).where(CustomerVisit.venue_id == venue_id)

        if customer_id:
            query = query.where(CustomerVisit.customer_id == customer_id)

        if date_from:
            query = query.where(
                func.date(CustomerVisit.check_in_time) >= date_from
            )

        if date_to:
            query = query.where(
                func.date(CustomerVisit.check_in_time) <= date_to
            )

        if source:
            query = query.where(CustomerVisit.source == source)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_column = getattr(
            CustomerVisit,
            pagination.sort_by,
            CustomerVisit.check_in_time,
        )
        if pagination.sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        offset = (pagination.page - 1) * pagination.page_size
        query = query.offset(offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        visits = list(result.scalars().all())

        return visits, total

    async def get_customer_visits(
        self,
        customer_id: UUID,
        limit: int = 10,
    ) -> List[CustomerVisit]:
        """Get recent visits for a customer."""
        result = await self.db.execute(
            select(CustomerVisit)
            .options(selectinload(CustomerVisit.activities))
            .where(CustomerVisit.customer_id == customer_id)
            .order_by(CustomerVisit.check_in_time.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_visit(
        self,
        visit_id: UUID,
        update_data: VisitUpdate,
    ) -> Optional[CustomerVisit]:
        """Update visit information."""
        visit = await self.get_visit(visit_id)
        if not visit:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(visit, field, value)

        visit.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(visit)

        # Update customer metrics
        await self._update_customer_metrics(visit.customer_id)

        return visit

    async def checkout_visit(
        self,
        visit_id: UUID,
        checkout_data: VisitCheckout,
    ) -> Optional[CustomerVisit]:
        """Check out a visit."""
        visit = await self.get_visit(visit_id)
        if not visit:
            return None

        visit.check_out_time = checkout_data.check_out_time or datetime.utcnow()

        if checkout_data.total_spend is not None:
            visit.total_spend = checkout_data.total_spend

        if checkout_data.satisfaction_score is not None:
            visit.satisfaction_score = checkout_data.satisfaction_score

        if checkout_data.feedback:
            visit.feedback = checkout_data.feedback

        visit.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(visit)

        # Update customer metrics
        await self._update_customer_metrics(visit.customer_id)

        logger.info(
            "visit_checked_out",
            visit_id=str(visit_id),
            duration_minutes=visit.duration_minutes,
            total_spend=str(visit.total_spend),
        )

        # Publish event
        await event_publisher.publish_visit_checked_out(
            visit_id=visit.id,
            customer_id=visit.customer_id,
            venue_id=visit.venue_id,
            total_spend=float(visit.total_spend),
            duration_minutes=visit.duration_minutes,
            satisfaction_rating=visit.satisfaction_score,
        )

        return visit

    async def add_activity(
        self,
        activity_data: ActivityCreate,
    ) -> CustomerActivity:
        """Add an activity to a visit."""
        activity = CustomerActivity(
            visit_id=activity_data.visit_id,
            activity_type=activity_data.activity_type,
            activity_id=activity_data.activity_id,
            activity_name=activity_data.activity_name,
            start_time=activity_data.start_time,
            end_time=activity_data.end_time,
            duration_minutes=activity_data.duration_minutes,
            amount_spent=activity_data.amount_spent,
            satisfaction_score=activity_data.satisfaction_score,
        )

        self.db.add(activity)
        await self.db.flush()

        # Update visit total spend
        visit = await self.get_visit(activity_data.visit_id)
        if visit:
            visit.total_spend += activity_data.amount_spent
            await self.db.flush()

        await self.db.refresh(activity)
        return activity

    async def _update_customer_metrics(self, customer_id: UUID) -> None:
        """Update customer LTV and churn risk metrics."""
        # Get all visits for the customer
        visits_result = await self.db.execute(
            select(CustomerVisit)
            .where(CustomerVisit.customer_id == customer_id)
            .order_by(CustomerVisit.check_in_time.desc())
        )
        visits = list(visits_result.scalars().all())

        if not visits:
            return

        # Calculate metrics
        total_visits = len(visits)
        total_spend = sum(v.total_spend for v in visits)
        avg_spend = total_spend / total_visits if total_visits > 0 else Decimal("0.00")

        first_visit = visits[-1].check_in_time.date()
        last_visit = visits[0].check_in_time.date()

        # Calculate visit frequency (visits per month)
        days_active = (last_visit - first_visit).days or 1
        months_active = days_active / 30 or 1
        visit_frequency = Decimal(str(total_visits / months_active))

        # Calculate expected LTV
        expected_lifespan = 12  # months
        calculated_ltv = avg_spend * visit_frequency * expected_lifespan

        # Update LTV record
        ltv_result = await self.db.execute(
            select(CustomerLTV).where(CustomerLTV.customer_id == customer_id)
        )
        ltv = ltv_result.scalar_one_or_none()

        if ltv:
            ltv.calculated_ltv = calculated_ltv
            ltv.visit_frequency = visit_frequency
            ltv.avg_spend = avg_spend
            ltv.total_visits = total_visits
            ltv.total_revenue = total_spend
            ltv.first_visit_date = first_visit
            ltv.last_visit_date = last_visit
            ltv.last_updated = datetime.utcnow()

        # Calculate churn risk
        days_since_last = (date.today() - last_visit).days

        if days_since_last <= 30:
            risk_level = RiskLevel.LOW
            risk_score = Decimal(str(min(days_since_last, 30)))
        elif days_since_last <= 60:
            risk_level = RiskLevel.MEDIUM
            risk_score = Decimal(str(30 + (days_since_last - 30)))
        elif days_since_last <= 90:
            risk_level = RiskLevel.HIGH
            risk_score = Decimal(str(60 + (days_since_last - 60)))
        else:
            risk_level = RiskLevel.CRITICAL
            risk_score = Decimal("100.00")

        # Update churn risk record
        churn_result = await self.db.execute(
            select(CustomerChurnRisk).where(
                CustomerChurnRisk.customer_id == customer_id
            )
        )
        churn = churn_result.scalar_one_or_none()

        if churn:
            churn.risk_score = risk_score
            churn.risk_level = risk_level
            churn.days_since_last_visit = days_since_last
            churn.calculated_at = datetime.utcnow()

        await self.db.flush()

    async def get_visit_stats(
        self,
        venue_id: UUID,
        date_from: date,
        date_to: date,
    ) -> dict:
        """Get visit statistics for a period."""
        # Total visits
        total_result = await self.db.execute(
            select(func.count())
            .select_from(CustomerVisit)
            .where(
                and_(
                    CustomerVisit.venue_id == venue_id,
                    func.date(CustomerVisit.check_in_time) >= date_from,
                    func.date(CustomerVisit.check_in_time) <= date_to,
                )
            )
        )
        total_visits = total_result.scalar() or 0

        # Unique customers
        unique_result = await self.db.execute(
            select(func.count(func.distinct(CustomerVisit.customer_id)))
            .where(
                and_(
                    CustomerVisit.venue_id == venue_id,
                    func.date(CustomerVisit.check_in_time) >= date_from,
                    func.date(CustomerVisit.check_in_time) <= date_to,
                )
            )
        )
        unique_customers = unique_result.scalar() or 0

        # Total revenue
        revenue_result = await self.db.execute(
            select(func.sum(CustomerVisit.total_spend))
            .where(
                and_(
                    CustomerVisit.venue_id == venue_id,
                    func.date(CustomerVisit.check_in_time) >= date_from,
                    func.date(CustomerVisit.check_in_time) <= date_to,
                )
            )
        )
        total_revenue = revenue_result.scalar() or Decimal("0.00")

        return {
            "total_visits": total_visits,
            "unique_customers": unique_customers,
            "total_revenue": total_revenue,
            "avg_spend_per_visit": (
                total_revenue / total_visits if total_visits > 0 else Decimal("0.00")
            ),
        }
