"""
=============================================================================
FILE: services/segmentation_service.py
PURPOSE: Customer segmentation business logic
=============================================================================
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.customer import (
    Customer,
    CustomerSegment,
    CustomerLTV,
    CustomerChurnRisk,
    CustomerVisit,
    SegmentType,
    RiskLevel,
)
from app.schemas.customer import PaginationParams
from app.config import get_settings

settings = get_settings()
logger = structlog.get_logger()


class SegmentationService:
    """Service for customer segmentation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def assign_segment(
        self,
        customer_id: UUID,
        segment_type: SegmentType,
        score: Decimal = Decimal("0.00"),
        expires_at: Optional[datetime] = None,
        factors: Optional[dict] = None,
    ) -> CustomerSegment:
        """Assign a segment to a customer."""
        # Remove existing segment of same type
        await self.db.execute(
            delete(CustomerSegment).where(
                and_(
                    CustomerSegment.customer_id == customer_id,
                    CustomerSegment.segment_type == segment_type,
                )
            )
        )

        # Set default expiry
        if expires_at is None:
            expires_at = datetime.utcnow() + timedelta(
                days=settings.DEFAULT_SEGMENT_EXPIRY_DAYS
            )

        segment = CustomerSegment(
            customer_id=customer_id,
            segment_type=segment_type,
            score=score,
            expires_at=expires_at,
            calculation_factors=factors or {},
        )

        self.db.add(segment)
        await self.db.flush()
        await self.db.refresh(segment)

        logger.info(
            "segment_assigned",
            customer_id=str(customer_id),
            segment_type=segment_type.value,
            score=str(score),
        )

        return segment

    async def get_customer_segment(
        self,
        customer_id: UUID,
    ) -> Optional[CustomerSegment]:
        """Get the current primary segment for a customer."""
        result = await self.db.execute(
            select(CustomerSegment)
            .where(
                and_(
                    CustomerSegment.customer_id == customer_id,
                    CustomerSegment.segment_type.not_in([
                        SegmentType.NEW,
                        SegmentType.CHURNED,
                    ]),
                )
            )
            .order_by(CustomerSegment.score.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_customers_by_segment(
        self,
        venue_id: UUID,
        segment_type: SegmentType,
        pagination: PaginationParams,
    ) -> Tuple[List[Customer], int]:
        """Get customers in a specific segment."""
        query = (
            select(Customer)
            .join(CustomerSegment)
            .where(
                and_(
                    Customer.venue_id == venue_id,
                    Customer.is_active == True,
                    CustomerSegment.segment_type == segment_type,
                )
            )
        )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (pagination.page - 1) * pagination.page_size
        query = query.offset(offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        customers = list(result.scalars().all())

        return customers, total

    async def recalculate_customer_segment(
        self,
        customer_id: UUID,
    ) -> CustomerSegment:
        """Recalculate and assign segment for a customer."""
        # Get LTV data
        ltv_result = await self.db.execute(
            select(CustomerLTV).where(CustomerLTV.customer_id == customer_id)
        )
        ltv = ltv_result.scalar_one_or_none()

        # Get churn risk
        churn_result = await self.db.execute(
            select(CustomerChurnRisk).where(
                CustomerChurnRisk.customer_id == customer_id
            )
        )
        churn = churn_result.scalar_one_or_none()

        # Determine segment based on metrics
        if ltv is None or ltv.total_visits == 0:
            segment_type = SegmentType.NEW
            score = Decimal("100.00")
        elif churn and churn.risk_level == RiskLevel.CRITICAL:
            segment_type = SegmentType.CHURNED
            score = churn.risk_score
        elif churn and churn.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            segment_type = SegmentType.AT_RISK
            score = churn.risk_score
        elif (
            ltv.total_visits >= settings.VIP_THRESHOLD_VISITS
            or ltv.total_revenue >= settings.VIP_THRESHOLD_SPEND
        ):
            segment_type = SegmentType.VIP
            score = min(
                Decimal("100.00"),
                Decimal(str(ltv.total_visits * 5 + float(ltv.total_revenue) / 100)),
            )
        elif (
            ltv.total_visits >= settings.PREMIUM_THRESHOLD_VISITS
            or ltv.total_revenue >= settings.PREMIUM_THRESHOLD_SPEND
        ):
            segment_type = SegmentType.PREMIUM
            score = min(
                Decimal("100.00"),
                Decimal(str(ltv.total_visits * 5 + float(ltv.total_revenue) / 100)),
            )
        else:
            segment_type = SegmentType.STANDARD
            score = Decimal(str(min(100, ltv.total_visits * 10)))

        factors = {
            "total_visits": ltv.total_visits if ltv else 0,
            "total_revenue": str(ltv.total_revenue) if ltv else "0",
            "churn_risk": churn.risk_level.value if churn else "unknown",
            "days_since_last_visit": churn.days_since_last_visit if churn else 0,
        }

        return await self.assign_segment(
            customer_id=customer_id,
            segment_type=segment_type,
            score=score,
            factors=factors,
        )

    async def recalculate_all_segments(self, venue_id: UUID) -> int:
        """Recalculate segments for all customers in a venue."""
        result = await self.db.execute(
            select(Customer.id).where(
                and_(
                    Customer.venue_id == venue_id,
                    Customer.is_active == True,
                    Customer.gdpr_data_deleted == False,
                )
            )
        )
        customer_ids = [row[0] for row in result.fetchall()]

        for customer_id in customer_ids:
            await self.recalculate_customer_segment(customer_id)

        await self.db.flush()

        logger.info(
            "segments_recalculated",
            venue_id=str(venue_id),
            customer_count=len(customer_ids),
        )

        return len(customer_ids)

    async def get_segment_stats(self, venue_id: UUID) -> List[dict]:
        """Get segment distribution statistics."""
        result = await self.db.execute(
            select(
                CustomerSegment.segment_type,
                func.count(func.distinct(CustomerSegment.customer_id)).label("count"),
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

        stats = []
        for row in result.fetchall():
            stats.append({
                "segment_type": row.segment_type.value,
                "customer_count": row.count,
            })

        return stats
