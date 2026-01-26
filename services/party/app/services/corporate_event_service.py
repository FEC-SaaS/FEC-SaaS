"""
=============================================================================
FILE: services/corporate_event_service.py
PURPOSE: Corporate event management business logic
=============================================================================
"""

from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.party import (
    CorporateEvent,
    CorporateEventType,
    CorporateEventStatus,
)
from app.schemas.party import (
    CorporateEventCreate,
    CorporateEventUpdate,
    CorporateEventStatusUpdate,
    PaginationParams,
)
from app.config import get_settings

settings = get_settings()
logger = structlog.get_logger()


class CorporateEventService:
    """Service for corporate event management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _calculate_lead_score(self, event: CorporateEvent) -> int:
        """
        Calculate AI-based lead score for a corporate event.

        Factors considered:
        - Attendee count (higher = better)
        - Budget (higher = better)
        - Company size
        - Event type
        - Lead time (days until event)
        """
        score = 50  # Base score

        # Attendee count factor
        if event.attendee_count >= 100:
            score += 20
        elif event.attendee_count >= 50:
            score += 15
        elif event.attendee_count >= 25:
            score += 10

        # Budget factor
        if event.estimated_budget:
            if event.estimated_budget >= Decimal("10000"):
                score += 20
            elif event.estimated_budget >= Decimal("5000"):
                score += 15
            elif event.estimated_budget >= Decimal("2500"):
                score += 10

        # Company size factor
        if event.company_size:
            if event.company_size.lower() == "enterprise":
                score += 10
            elif event.company_size.lower() == "mid-market":
                score += 5

        # Event type factor (recurring potential)
        if event.event_type in [
            CorporateEventType.TEAM_BUILDING,
            CorporateEventType.HAPPY_HOUR,
        ]:
            score += 5  # High recurring potential

        # Lead time factor
        days_until = (event.event_date - date.today()).days
        if days_until >= 30:
            score += 5  # Good planning lead time
        elif days_until < 7:
            score -= 5  # Last minute inquiry

        # Cap score at 100
        return min(100, max(0, score))

    async def create_event(self, event_data: CorporateEventCreate) -> CorporateEvent:
        """
        Create a new corporate event inquiry.

        Args:
            event_data: Event creation data

        Returns:
            Created event instance
        """
        event = CorporateEvent(
            venue_id=event_data.venue_id,
            company_name=event_data.company_name,
            company_industry=event_data.company_industry,
            company_size=event_data.company_size,
            contact_name=event_data.contact_name,
            contact_email=event_data.contact_email,
            contact_phone=event_data.contact_phone,
            contact_title=event_data.contact_title,
            event_type=event_data.event_type,
            event_name=event_data.event_name,
            event_date=event_data.event_date,
            start_time=event_data.start_time,
            end_time=event_data.end_time,
            attendee_count=event_data.attendee_count,
            min_attendees=event_data.min_attendees,
            max_attendees=event_data.max_attendees,
            estimated_budget=event_data.estimated_budget,
            special_requests=event_data.special_requests,
            catering_requirements=event_data.catering_requirements,
            beverage_requirements=event_data.beverage_requirements,
            av_requirements=event_data.av_requirements,
            space_requirements=event_data.space_requirements,
            status=CorporateEventStatus.INQUIRY,
        )

        self.db.add(event)
        await self.db.flush()

        # Calculate and set lead score
        event.lead_score = self._calculate_lead_score(event)
        event.lead_score_factors = {
            "attendee_count": event.attendee_count,
            "estimated_budget": float(event.estimated_budget) if event.estimated_budget else None,
            "company_size": event.company_size,
            "event_type": event.event_type.value,
            "calculated_at": datetime.utcnow().isoformat(),
        }

        await self.db.flush()
        await self.db.refresh(event)

        logger.info(
            "corporate_event_created",
            event_id=str(event.id),
            venue_id=str(event.venue_id),
            company=event.company_name,
            lead_score=event.lead_score,
        )

        return event

    async def get_event(self, event_id: UUID) -> Optional[CorporateEvent]:
        """Get event by ID."""
        result = await self.db.execute(
            select(CorporateEvent).where(
                and_(
                    CorporateEvent.id == event_id,
                    CorporateEvent.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_events(
        self,
        venue_id: UUID,
        pagination: PaginationParams,
        status: Optional[CorporateEventStatus] = None,
        event_type: Optional[CorporateEventType] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        min_lead_score: Optional[int] = None,
        assigned_rep_id: Optional[UUID] = None,
    ) -> Tuple[List[CorporateEvent], int]:
        """List corporate events with filtering and pagination."""
        query = select(CorporateEvent).where(
            and_(
                CorporateEvent.venue_id == venue_id,
                CorporateEvent.is_deleted == False,
            )
        )

        if status:
            query = query.where(CorporateEvent.status == status)

        if event_type:
            query = query.where(CorporateEvent.event_type == event_type)

        if date_from:
            query = query.where(CorporateEvent.event_date >= date_from)

        if date_to:
            query = query.where(CorporateEvent.event_date <= date_to)

        if min_lead_score is not None:
            query = query.where(CorporateEvent.lead_score >= min_lead_score)

        if assigned_rep_id:
            query = query.where(CorporateEvent.assigned_rep_id == assigned_rep_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_column = getattr(CorporateEvent, pagination.sort_by, CorporateEvent.created_at)
        if pagination.sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        offset = (pagination.page - 1) * pagination.page_size
        query = query.offset(offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        events = list(result.scalars().all())

        return events, total

    async def update_event(
        self,
        event_id: UUID,
        update_data: CorporateEventUpdate,
    ) -> Optional[CorporateEvent]:
        """Update event information."""
        event = await self.get_event(event_id)
        if not event:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(event, field, value)

        # Recalculate lead score if relevant fields changed
        score_factors = ["attendee_count", "estimated_budget", "company_size", "event_type"]
        if any(f in update_dict for f in score_factors):
            event.lead_score = self._calculate_lead_score(event)
            event.lead_score_factors = {
                "attendee_count": event.attendee_count,
                "estimated_budget": float(event.estimated_budget) if event.estimated_budget else None,
                "company_size": event.company_size,
                "event_type": event.event_type.value,
                "calculated_at": datetime.utcnow().isoformat(),
            }

        event.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(event)

        logger.info(
            "corporate_event_updated",
            event_id=str(event_id),
            fields_updated=list(update_dict.keys()),
        )

        return event

    async def update_event_status(
        self,
        event_id: UUID,
        status_update: CorporateEventStatusUpdate,
    ) -> Optional[CorporateEvent]:
        """Update event status with workflow tracking."""
        event = await self.get_event(event_id)
        if not event:
            return None

        old_status = event.status
        new_status = status_update.status

        event.status = new_status
        event.updated_at = datetime.utcnow()

        # Set timestamps based on status
        if new_status == CorporateEventStatus.PROPOSAL_SENT:
            event.proposal_sent_at = datetime.utcnow()
            if status_update.proposal_url:
                event.proposal_url = status_update.proposal_url

        elif new_status == CorporateEventStatus.CONFIRMED:
            event.confirmed_at = datetime.utcnow()

        elif new_status == CorporateEventStatus.COMPLETED:
            event.completed_at = datetime.utcnow()

        elif new_status in [CorporateEventStatus.LOST, CorporateEventStatus.CANCELLED]:
            if status_update.lost_reason:
                event.lost_reason = status_update.lost_reason

        # Update last contact date
        event.last_contact_date = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(event)

        logger.info(
            "corporate_event_status_changed",
            event_id=str(event_id),
            old_status=old_status.value,
            new_status=new_status.value,
        )

        return event

    async def assign_sales_rep(
        self,
        event_id: UUID,
        rep_id: UUID,
    ) -> Optional[CorporateEvent]:
        """Assign a sales rep to the event."""
        event = await self.get_event(event_id)
        if not event:
            return None

        event.assigned_rep_id = rep_id
        event.updated_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(event)

        return event

    async def set_follow_up(
        self,
        event_id: UUID,
        follow_up_date: datetime,
        notes: Optional[str] = None,
    ) -> Optional[CorporateEvent]:
        """Set next follow-up date and notes."""
        event = await self.get_event(event_id)
        if not event:
            return None

        event.next_follow_up_date = follow_up_date
        if notes:
            event.follow_up_notes = notes
        event.updated_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(event)

        return event

    async def delete_event(self, event_id: UUID) -> bool:
        """Soft delete an event."""
        event = await self.get_event(event_id)
        if not event:
            return False

        event.is_deleted = True
        event.updated_at = datetime.utcnow()
        await self.db.flush()

        logger.info("corporate_event_deleted", event_id=str(event_id))
        return True

    async def get_high_priority_leads(
        self,
        venue_id: UUID,
        limit: int = 10,
    ) -> List[CorporateEvent]:
        """Get high priority leads sorted by lead score."""
        result = await self.db.execute(
            select(CorporateEvent)
            .where(
                and_(
                    CorporateEvent.venue_id == venue_id,
                    CorporateEvent.is_deleted == False,
                    CorporateEvent.status.in_([
                        CorporateEventStatus.INQUIRY,
                        CorporateEventStatus.PROPOSAL_SENT,
                        CorporateEventStatus.NEGOTIATING,
                    ]),
                    CorporateEvent.lead_score >= settings.CORPORATE_LEAD_SCORE_THRESHOLD,
                )
            )
            .order_by(CorporateEvent.lead_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_follow_ups_due(
        self,
        venue_id: UUID,
        as_of_date: Optional[datetime] = None,
    ) -> List[CorporateEvent]:
        """Get events with follow-ups due."""
        if as_of_date is None:
            as_of_date = datetime.utcnow()

        result = await self.db.execute(
            select(CorporateEvent)
            .where(
                and_(
                    CorporateEvent.venue_id == venue_id,
                    CorporateEvent.is_deleted == False,
                    CorporateEvent.next_follow_up_date <= as_of_date,
                    CorporateEvent.status.not_in([
                        CorporateEventStatus.COMPLETED,
                        CorporateEventStatus.CANCELLED,
                        CorporateEventStatus.LOST,
                    ]),
                )
            )
            .order_by(CorporateEvent.next_follow_up_date)
        )
        return list(result.scalars().all())
