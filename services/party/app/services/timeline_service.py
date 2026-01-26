"""
=============================================================================
FILE: services/timeline_service.py
PURPOSE: Party timeline and host assignment management
=============================================================================
"""

from datetime import datetime, time
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.party import (
    PartyTimeline,
    PartyHostAssignment,
    PartyBooking,
    TimelineStatus,
    HostRole,
)
from app.schemas.party import (
    PartyTimelineCreate,
    PartyTimelineUpdate,
    TimelineItemComplete,
    HostAssignmentCreate,
    HostAssignmentUpdate,
)

logger = structlog.get_logger()


class TimelineService:
    """Service for party timeline and host assignment management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Timeline Operations
    # =========================================================================

    async def create_timeline_item(
        self,
        item_data: PartyTimelineCreate,
    ) -> PartyTimeline:
        """Create a new timeline item for a booking."""
        item = PartyTimeline(
            booking_id=item_data.booking_id,
            item_name=item_data.item_name,
            item_description=item_data.item_description,
            item_category=item_data.item_category,
            scheduled_time=item_data.scheduled_time,
            duration_minutes=item_data.duration_minutes,
            assigned_staff_id=item_data.assigned_staff_id,
            sequence_order=item_data.sequence_order,
            status=TimelineStatus.PENDING,
        )

        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)

        logger.info(
            "timeline_item_created",
            item_id=str(item.id),
            booking_id=str(item.booking_id),
            name=item.item_name,
        )

        return item

    async def get_timeline_item(self, item_id: UUID) -> Optional[PartyTimeline]:
        """Get timeline item by ID."""
        result = await self.db.execute(
            select(PartyTimeline).where(PartyTimeline.id == item_id)
        )
        return result.scalar_one_or_none()

    async def get_booking_timeline(self, booking_id: UUID) -> List[PartyTimeline]:
        """Get all timeline items for a booking in order."""
        result = await self.db.execute(
            select(PartyTimeline)
            .where(PartyTimeline.booking_id == booking_id)
            .order_by(PartyTimeline.sequence_order)
        )
        return list(result.scalars().all())

    async def update_timeline_item(
        self,
        item_id: UUID,
        update_data: PartyTimelineUpdate,
    ) -> Optional[PartyTimeline]:
        """Update a timeline item."""
        item = await self.get_timeline_item(item_id)
        if not item:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(item, field, value)

        item.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(item)

        return item

    async def complete_timeline_item(
        self,
        item_id: UUID,
        completion_data: TimelineItemComplete,
        completed_by_id: UUID,
    ) -> Optional[PartyTimeline]:
        """Mark a timeline item as completed."""
        item = await self.get_timeline_item(item_id)
        if not item:
            return None

        item.status = TimelineStatus.COMPLETED
        item.completed_at = datetime.utcnow()
        item.completed_by_id = completed_by_id

        if completion_data.actual_time:
            item.actual_time = completion_data.actual_time
        else:
            item.actual_time = datetime.utcnow().time()

        if completion_data.notes:
            item.notes = completion_data.notes

        if completion_data.delay_reason:
            item.delay_reason = completion_data.delay_reason
            # Check if item was delayed
            if item.actual_time > item.scheduled_time:
                item.status = TimelineStatus.DELAYED

        item.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(item)

        logger.info(
            "timeline_item_completed",
            item_id=str(item_id),
            status=item.status.value,
            on_time=item.actual_time <= item.scheduled_time if item.actual_time else None,
        )

        return item

    async def skip_timeline_item(
        self,
        item_id: UUID,
        reason: Optional[str] = None,
    ) -> Optional[PartyTimeline]:
        """Skip a timeline item."""
        item = await self.get_timeline_item(item_id)
        if not item:
            return None

        item.status = TimelineStatus.SKIPPED
        if reason:
            item.notes = reason
        item.updated_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(item)

        return item

    async def start_timeline_item(self, item_id: UUID) -> Optional[PartyTimeline]:
        """Mark a timeline item as in progress."""
        item = await self.get_timeline_item(item_id)
        if not item:
            return None

        item.status = TimelineStatus.IN_PROGRESS
        item.actual_time = datetime.utcnow().time()
        item.updated_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(item)

        return item

    async def delete_timeline_item(self, item_id: UUID) -> bool:
        """Delete a timeline item."""
        item = await self.get_timeline_item(item_id)
        if not item:
            return False

        await self.db.delete(item)
        await self.db.flush()

        return True

    async def get_timeline_progress(self, booking_id: UUID) -> dict:
        """Get timeline completion progress for a booking."""
        items = await self.get_booking_timeline(booking_id)

        if not items:
            return {
                "total_items": 0,
                "completed": 0,
                "in_progress": 0,
                "pending": 0,
                "skipped": 0,
                "delayed": 0,
                "completion_rate": 0.0,
            }

        completed = sum(1 for i in items if i.status == TimelineStatus.COMPLETED)
        in_progress = sum(1 for i in items if i.status == TimelineStatus.IN_PROGRESS)
        pending = sum(1 for i in items if i.status == TimelineStatus.PENDING)
        skipped = sum(1 for i in items if i.status == TimelineStatus.SKIPPED)
        delayed = sum(1 for i in items if i.status == TimelineStatus.DELAYED)

        total = len(items)
        completion_rate = ((completed + delayed) / total * 100) if total > 0 else 0.0

        return {
            "total_items": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "skipped": skipped,
            "delayed": delayed,
            "completion_rate": round(completion_rate, 1),
        }

    # =========================================================================
    # Host Assignment Operations
    # =========================================================================

    async def create_host_assignment(
        self,
        assignment_data: HostAssignmentCreate,
    ) -> PartyHostAssignment:
        """Assign a staff member to a party."""
        assignment = PartyHostAssignment(
            booking_id=assignment_data.booking_id,
            staff_id=assignment_data.staff_id,
            role=assignment_data.role,
            start_time=assignment_data.start_time,
            end_time=assignment_data.end_time,
            notes=assignment_data.notes,
            confirmed=False,
            checked_in=False,
        )

        self.db.add(assignment)
        await self.db.flush()
        await self.db.refresh(assignment)

        logger.info(
            "host_assigned",
            assignment_id=str(assignment.id),
            booking_id=str(assignment.booking_id),
            staff_id=str(assignment.staff_id),
            role=assignment.role.value,
        )

        return assignment

    async def get_host_assignment(
        self,
        assignment_id: UUID,
    ) -> Optional[PartyHostAssignment]:
        """Get host assignment by ID."""
        result = await self.db.execute(
            select(PartyHostAssignment).where(PartyHostAssignment.id == assignment_id)
        )
        return result.scalar_one_or_none()

    async def get_booking_assignments(
        self,
        booking_id: UUID,
    ) -> List[PartyHostAssignment]:
        """Get all host assignments for a booking."""
        result = await self.db.execute(
            select(PartyHostAssignment)
            .where(PartyHostAssignment.booking_id == booking_id)
            .order_by(PartyHostAssignment.role)
        )
        return list(result.scalars().all())

    async def get_staff_assignments(
        self,
        staff_id: UUID,
        party_date: Optional[datetime] = None,
    ) -> List[PartyHostAssignment]:
        """Get all assignments for a staff member."""
        query = select(PartyHostAssignment).where(
            PartyHostAssignment.staff_id == staff_id
        )

        if party_date:
            # Join with booking to filter by date
            query = (
                query
                .join(PartyBooking)
                .where(PartyBooking.party_date == party_date.date())
            )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_host_assignment(
        self,
        assignment_id: UUID,
        update_data: HostAssignmentUpdate,
    ) -> Optional[PartyHostAssignment]:
        """Update a host assignment."""
        assignment = await self.get_host_assignment(assignment_id)
        if not assignment:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(assignment, field, value)

        assignment.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(assignment)

        return assignment

    async def confirm_assignment(
        self,
        assignment_id: UUID,
    ) -> Optional[PartyHostAssignment]:
        """Confirm a host assignment."""
        assignment = await self.get_host_assignment(assignment_id)
        if not assignment:
            return None

        assignment.confirmed = True
        assignment.updated_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(assignment)

        return assignment

    async def check_in_host(
        self,
        assignment_id: UUID,
    ) -> Optional[PartyHostAssignment]:
        """Check in a host for their assignment."""
        assignment = await self.get_host_assignment(assignment_id)
        if not assignment:
            return None

        assignment.checked_in = True
        assignment.checked_in_at = datetime.utcnow()
        assignment.updated_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(assignment)

        logger.info(
            "host_checked_in",
            assignment_id=str(assignment_id),
            staff_id=str(assignment.staff_id),
        )

        return assignment

    async def delete_host_assignment(self, assignment_id: UUID) -> bool:
        """Remove a host assignment."""
        assignment = await self.get_host_assignment(assignment_id)
        if not assignment:
            return False

        await self.db.delete(assignment)
        await self.db.flush()

        return True

    async def get_primary_host(
        self,
        booking_id: UUID,
    ) -> Optional[PartyHostAssignment]:
        """Get the primary host for a booking."""
        result = await self.db.execute(
            select(PartyHostAssignment).where(
                and_(
                    PartyHostAssignment.booking_id == booking_id,
                    PartyHostAssignment.role == HostRole.PRIMARY_HOST,
                )
            )
        )
        return result.scalar_one_or_none()
