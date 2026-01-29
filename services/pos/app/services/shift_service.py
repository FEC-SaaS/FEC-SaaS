"""Shift service for POS Integration."""

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ErrorCode,
    ServiceError,
    bad_request,
    conflict,
    not_found,
)
from app.models.pos import Shift, ShiftStatus
from app.schemas.pos import ShiftCreate, ShiftUpdate
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()


class ShiftService:
    """
    Service for managing employee shifts at POS venues.

    This service handles the full lifecycle of employee shifts including
    scheduling, clock-in/clock-out, break tracking, and status management.
    Shifts can be scheduled in advance and then started/ended when employees
    actually work.

    Attributes:
        db: AsyncSession for database operations.
        event_publisher: Optional event publisher for broadcasting shift events.
    """

    def __init__(
        self,
        db: AsyncSession,
        event_publisher: Optional[EventPublisher] = None,
    ):
        """
        Initialize the ShiftService.

        Args:
            db: SQLAlchemy async session for database operations.
            event_publisher: Optional RabbitMQ event publisher for broadcasting events.
        """
        self.db = db
        self.event_publisher = event_publisher

    async def create_shift(
        self,
        venue_id: UUID,
        data: ShiftCreate,
    ) -> Shift:
        """
        Create a new shift for an employee.

        Creates a scheduled shift with the specified start and end times.
        The shift starts in SCHEDULED status and must be explicitly started
        when the employee clocks in.

        Args:
            venue_id: UUID of the venue where the shift will occur.
            data: ShiftCreate schema with shift details.

        Returns:
            The newly created Shift object.
        """
        shift = Shift(
            venue_id=venue_id,
            employee_id=data.employee_id,
            employee_name=data.employee_name,
            scheduled_start=data.scheduled_start,
            scheduled_end=data.scheduled_end,
            status=ShiftStatus.SCHEDULED.value,
            break_minutes=0,
            notes=data.notes,
        )
        self.db.add(shift)
        await self.db.commit()
        await self.db.refresh(shift)

        logger.info(
            "shift_created",
            shift_id=str(shift.id),
            venue_id=str(venue_id),
            employee_id=str(data.employee_id),
            scheduled_start=str(data.scheduled_start),
            scheduled_end=str(data.scheduled_end),
        )

        return shift

    async def get_shift(self, shift_id: UUID) -> Shift:
        """
        Retrieve a shift by its ID.

        Args:
            shift_id: UUID of the shift to retrieve.

        Returns:
            The Shift object if found.

        Raises:
            ServiceError: If the shift is not found (404).
        """
        result = await self.db.execute(
            select(Shift).where(Shift.id == shift_id)
        )
        shift = result.scalars().first()
        if not shift:
            raise not_found(
                ErrorCode.SHIFT_NOT_FOUND,
                f"Shift {shift_id} not found",
            )
        return shift

    async def list_shifts(
        self,
        venue_id: UUID,
        employee_id: Optional[UUID] = None,
        status: Optional[ShiftStatus] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Shift]:
        """
        List shifts for a venue with optional filtering.

        Args:
            venue_id: UUID of the venue.
            employee_id: Optional employee UUID to filter by.
            status: Optional ShiftStatus to filter by.
            date_from: Optional start date to filter shifts (inclusive).
            date_to: Optional end date to filter shifts (inclusive).
            skip: Number of records to skip for pagination (default: 0).
            limit: Maximum number of records to return (default: 50).

        Returns:
            List of Shift objects matching the criteria.
        """
        query = select(Shift).where(Shift.venue_id == venue_id)

        if employee_id is not None:
            query = query.where(Shift.employee_id == employee_id)

        if status is not None:
            query = query.where(Shift.status == status.value)

        if date_from is not None:
            # Filter by scheduled_start date >= date_from
            start_of_day = datetime.combine(date_from, datetime.min.time())
            query = query.where(Shift.scheduled_start >= start_of_day)

        if date_to is not None:
            # Filter by scheduled_start date <= date_to (end of day)
            end_of_day = datetime.combine(date_to, datetime.max.time())
            query = query.where(Shift.scheduled_start <= end_of_day)

        query = query.order_by(Shift.scheduled_start.desc())
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        shifts = list(result.scalars().all())

        logger.info(
            "shifts_listed",
            venue_id=str(venue_id),
            employee_id=str(employee_id) if employee_id else None,
            status=status.value if status else None,
            count=len(shifts),
        )

        return shifts

    async def start_shift(self, shift_id: UUID) -> Shift:
        """
        Start a scheduled shift (employee clock-in).

        Sets the actual_start time to now and changes status to ACTIVE.
        Only SCHEDULED shifts can be started.

        Args:
            shift_id: UUID of the shift to start.

        Returns:
            The updated Shift object with ACTIVE status.

        Raises:
            ServiceError: If the shift is not found (404).
            ServiceError: If the shift is not in SCHEDULED status (400).
            ServiceError: If the employee already has an active shift (409).
        """
        shift = await self.get_shift(shift_id)

        # Validate current status
        if shift.status == ShiftStatus.ACTIVE.value:
            raise bad_request(
                ErrorCode.SHIFT_ALREADY_ACTIVE,
                f"Shift {shift_id} is already active",
            )
        if shift.status == ShiftStatus.COMPLETED.value:
            raise bad_request(
                ErrorCode.SHIFT_ALREADY_COMPLETED,
                f"Shift {shift_id} is already completed",
            )
        if shift.status == ShiftStatus.CANCELLED.value:
            raise bad_request(
                ErrorCode.SHIFT_ALREADY_CANCELLED,
                f"Shift {shift_id} has been cancelled",
            )

        # Check if employee already has an active shift
        existing_active = await self.get_active_shift(
            shift.venue_id, shift.employee_id
        )
        if existing_active and existing_active.id != shift_id:
            raise conflict(
                ErrorCode.SHIFT_ALREADY_ACTIVE,
                f"Employee {shift.employee_id} already has an active shift",
                {"active_shift_id": str(existing_active.id)},
            )

        # Start the shift
        shift.actual_start = datetime.utcnow()
        shift.status = ShiftStatus.ACTIVE.value
        await self.db.commit()
        await self.db.refresh(shift)

        logger.info(
            "shift_started",
            shift_id=str(shift_id),
            venue_id=str(shift.venue_id),
            employee_id=str(shift.employee_id),
            actual_start=str(shift.actual_start),
        )

        # Publish event
        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.DRAWER_OPENED,  # Consider adding SHIFT_STARTED event
                {
                    "shift_id": str(shift.id),
                    "venue_id": str(shift.venue_id),
                    "employee_id": str(shift.employee_id),
                    "employee_name": shift.employee_name,
                    "actual_start": shift.actual_start.isoformat(),
                },
                venue_id=shift.venue_id,
            )

        return shift

    async def end_shift(
        self,
        shift_id: UUID,
        break_minutes: int = 0,
    ) -> Shift:
        """
        End an active shift (employee clock-out).

        Sets the actual_end time to now, records break minutes, and changes
        status to COMPLETED. Only ACTIVE shifts can be ended.

        Args:
            shift_id: UUID of the shift to end.
            break_minutes: Total break time in minutes (default: 0).

        Returns:
            The updated Shift object with COMPLETED status.

        Raises:
            ServiceError: If the shift is not found (404).
            ServiceError: If the shift is not in ACTIVE status (400).
        """
        shift = await self.get_shift(shift_id)

        # Validate current status
        if shift.status == ShiftStatus.SCHEDULED.value:
            raise bad_request(
                ErrorCode.SHIFT_NOT_ACTIVE,
                f"Shift {shift_id} has not been started yet",
            )
        if shift.status == ShiftStatus.COMPLETED.value:
            raise bad_request(
                ErrorCode.SHIFT_ALREADY_COMPLETED,
                f"Shift {shift_id} is already completed",
            )
        if shift.status == ShiftStatus.CANCELLED.value:
            raise bad_request(
                ErrorCode.SHIFT_ALREADY_CANCELLED,
                f"Shift {shift_id} has been cancelled",
            )

        # End the shift
        shift.actual_end = datetime.utcnow()
        shift.status = ShiftStatus.COMPLETED.value
        shift.break_minutes = break_minutes
        await self.db.commit()
        await self.db.refresh(shift)

        # Calculate worked hours for logging
        if shift.actual_start:
            worked_seconds = (shift.actual_end - shift.actual_start).total_seconds()
            worked_hours = (worked_seconds - (break_minutes * 60)) / 3600
        else:
            worked_hours = 0

        logger.info(
            "shift_ended",
            shift_id=str(shift_id),
            venue_id=str(shift.venue_id),
            employee_id=str(shift.employee_id),
            actual_end=str(shift.actual_end),
            break_minutes=break_minutes,
            worked_hours=round(worked_hours, 2),
        )

        # Publish event
        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.DRAWER_CLOSED,  # Consider adding SHIFT_ENDED event
                {
                    "shift_id": str(shift.id),
                    "venue_id": str(shift.venue_id),
                    "employee_id": str(shift.employee_id),
                    "employee_name": shift.employee_name,
                    "actual_start": shift.actual_start.isoformat() if shift.actual_start else None,
                    "actual_end": shift.actual_end.isoformat(),
                    "break_minutes": break_minutes,
                    "worked_hours": round(worked_hours, 2),
                },
                venue_id=shift.venue_id,
            )

        return shift

    async def cancel_shift(
        self,
        shift_id: UUID,
        reason: Optional[str] = None,
    ) -> Shift:
        """
        Cancel a shift.

        Sets the status to CANCELLED and optionally records the cancellation
        reason in notes. Only SCHEDULED shifts can be cancelled; active shifts
        must be ended instead.

        Args:
            shift_id: UUID of the shift to cancel.
            reason: Optional reason for cancellation.

        Returns:
            The updated Shift object with CANCELLED status.

        Raises:
            ServiceError: If the shift is not found (404).
            ServiceError: If the shift is ACTIVE (must be ended instead) (400).
            ServiceError: If the shift is already COMPLETED or CANCELLED (400).
        """
        shift = await self.get_shift(shift_id)

        # Validate current status
        if shift.status == ShiftStatus.ACTIVE.value:
            raise bad_request(
                ErrorCode.SHIFT_ALREADY_ACTIVE,
                f"Shift {shift_id} is active and cannot be cancelled. End the shift instead.",
            )
        if shift.status == ShiftStatus.COMPLETED.value:
            raise bad_request(
                ErrorCode.SHIFT_ALREADY_COMPLETED,
                f"Shift {shift_id} is already completed and cannot be cancelled",
            )
        if shift.status == ShiftStatus.CANCELLED.value:
            raise bad_request(
                ErrorCode.SHIFT_ALREADY_CANCELLED,
                f"Shift {shift_id} is already cancelled",
            )

        # Cancel the shift
        shift.status = ShiftStatus.CANCELLED.value
        if reason:
            existing_notes = shift.notes or ""
            shift.notes = f"{existing_notes}\nCancellation reason: {reason}".strip()
        await self.db.commit()
        await self.db.refresh(shift)

        logger.info(
            "shift_cancelled",
            shift_id=str(shift_id),
            venue_id=str(shift.venue_id),
            employee_id=str(shift.employee_id),
            reason=reason,
        )

        return shift

    async def update_shift(
        self,
        shift_id: UUID,
        data: ShiftUpdate,
    ) -> Shift:
        """
        Update an existing shift.

        Updates the shift with the provided fields. Only non-None fields
        in the update data will be modified. Note that some fields may only
        be updatable when the shift is in certain statuses.

        Args:
            shift_id: UUID of the shift to update.
            data: ShiftUpdate schema with fields to update.

        Returns:
            The updated Shift object.

        Raises:
            ServiceError: If the shift is not found (404).
        """
        shift = await self.get_shift(shift_id)

        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "status" and value is not None:
                setattr(shift, field, value.value)
            else:
                setattr(shift, field, value)

        await self.db.commit()
        await self.db.refresh(shift)

        logger.info(
            "shift_updated",
            shift_id=str(shift_id),
            venue_id=str(shift.venue_id),
            updated_fields=list(update_data.keys()),
        )

        return shift

    async def get_active_shift(
        self,
        venue_id: UUID,
        employee_id: UUID,
    ) -> Optional[Shift]:
        """
        Get the currently active shift for an employee at a venue.

        An employee can only have one active shift at a time. This method
        returns the active shift if one exists, or None otherwise.

        Args:
            venue_id: UUID of the venue.
            employee_id: UUID of the employee.

        Returns:
            The active Shift object if one exists, None otherwise.
        """
        result = await self.db.execute(
            select(Shift).where(
                and_(
                    Shift.venue_id == venue_id,
                    Shift.employee_id == employee_id,
                    Shift.status == ShiftStatus.ACTIVE.value,
                )
            )
        )
        shift = result.scalars().first()

        if shift:
            logger.debug(
                "active_shift_found",
                shift_id=str(shift.id),
                venue_id=str(venue_id),
                employee_id=str(employee_id),
            )
        else:
            logger.debug(
                "no_active_shift_found",
                venue_id=str(venue_id),
                employee_id=str(employee_id),
            )

        return shift
