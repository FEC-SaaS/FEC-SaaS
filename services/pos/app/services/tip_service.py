"""
=============================================================================
FILE: services/tip_service.py
PURPOSE: Tip pooling and distribution service for the POS Integration Service
=============================================================================

Service for managing tip pools and distributing tips among employees.
Supports multiple distribution methods (equal, hours-based, sales-based)
and tracks the complete lifecycle of tip pools from creation through
distribution.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ErrorCode,
    bad_request,
    conflict,
    not_found,
)
from app.models.pos import (
    TipDistribution,
    TipPool,
    TipPoolStatus,
)
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()


class TipService:
    """
    Service for managing tip pools and distributions.

    Provides functionality for:
    - Creating and managing tip pools for specific shift dates
    - Adding tips and participants to pools
    - Calculating and distributing tips using various methods
    - Tracking employee tip earnings over time

    Attributes:
        db: Async database session for database operations.
        event_publisher: Optional publisher for emitting tip-related events.
    """

    def __init__(
        self,
        db: AsyncSession,
        event_publisher: Optional[EventPublisher] = None,
    ) -> None:
        """
        Initialize the TipService.

        Args:
            db: Async database session for database operations.
            event_publisher: Optional event publisher for emitting events.
        """
        self.db = db
        self.event_publisher = event_publisher

    # -------------------------------------------------------------------------
    # Tip Pool CRUD Operations
    # -------------------------------------------------------------------------

    async def create_tip_pool(
        self,
        venue_id: uuid.UUID,
        shift_date: date,
        distribution_method: str = "hours_based",
        notes: Optional[str] = None,
    ) -> TipPool:
        """
        Create a new tip pool for a specific shift date.

        Creates a tip pool in OPEN status that can accept tips and participants.
        Only one pool can exist per venue per shift date.

        Args:
            venue_id: The venue ID for this tip pool.
            shift_date: The shift date this pool covers.
            distribution_method: How tips will be distributed:
                - "equal": Split evenly among all participants
                - "hours_based": Distribute proportionally by hours worked
                - "sales_based": Distribute proportionally by sales (requires external data)
            notes: Optional notes about the pool.

        Returns:
            The newly created TipPool instance.

        Raises:
            ServiceError: If a pool already exists for this venue and date.
        """
        # Check if pool already exists for this date
        existing = await self.get_tip_pool_by_date(venue_id, shift_date)
        if existing:
            logger.warning(
                "tip_pool_already_exists",
                venue_id=str(venue_id),
                shift_date=str(shift_date),
            )
            raise conflict(
                ErrorCode.TIP_POOL_ALREADY_EXISTS,
                f"Tip pool already exists for venue {venue_id} on {shift_date}",
            )

        # Create new pool
        tip_pool = TipPool(
            venue_id=venue_id,
            shift_date=shift_date,
            status=TipPoolStatus.OPEN.value,
            total_tips=Decimal("0"),
            distributed_amount=Decimal("0"),
            pool_participants=[],
            distribution_method=distribution_method,
            notes=notes,
        )

        self.db.add(tip_pool)
        await self.db.commit()
        await self.db.refresh(tip_pool)

        logger.info(
            "tip_pool_created",
            pool_id=str(tip_pool.id),
            venue_id=str(venue_id),
            shift_date=str(shift_date),
            distribution_method=distribution_method,
        )

        # Publish event
        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.TIP_POOL_CREATED,
                {
                    "pool_id": str(tip_pool.id),
                    "venue_id": str(venue_id),
                    "shift_date": str(shift_date),
                    "distribution_method": distribution_method,
                },
                venue_id=venue_id,
            )

        return tip_pool

    async def get_tip_pool(self, pool_id: uuid.UUID) -> TipPool:
        """
        Get a tip pool by its ID.

        Args:
            pool_id: The unique identifier of the tip pool.

        Returns:
            The TipPool instance.

        Raises:
            ServiceError: If the pool is not found.
        """
        result = await self.db.execute(
            select(TipPool).where(TipPool.id == pool_id)
        )
        tip_pool = result.scalars().first()

        if not tip_pool:
            raise not_found(
                ErrorCode.TIP_POOL_NOT_FOUND,
                f"Tip pool {pool_id} not found",
            )

        return tip_pool

    async def get_tip_pool_by_date(
        self,
        venue_id: uuid.UUID,
        shift_date: date,
    ) -> Optional[TipPool]:
        """
        Get a tip pool for a specific venue and shift date.

        Args:
            venue_id: The venue ID to search for.
            shift_date: The shift date to search for.

        Returns:
            The TipPool instance if found, None otherwise.
        """
        result = await self.db.execute(
            select(TipPool).where(
                and_(
                    TipPool.venue_id == venue_id,
                    TipPool.shift_date == shift_date,
                )
            )
        )
        return result.scalars().first()

    async def list_tip_pools(
        self,
        venue_id: uuid.UUID,
        status: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[TipPool], int]:
        """
        List tip pools with filtering and pagination.

        Args:
            venue_id: Filter by venue ID.
            status: Optional filter by pool status.
            date_from: Optional filter for pools on or after this date.
            date_to: Optional filter for pools on or before this date.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            Tuple of (list of TipPool instances, total count).
        """
        query = select(TipPool).where(TipPool.venue_id == venue_id)

        if status:
            query = query.where(TipPool.status == status)
        if date_from:
            query = query.where(TipPool.shift_date >= date_from)
        if date_to:
            query = query.where(TipPool.shift_date <= date_to)

        # Total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results
        query = query.order_by(TipPool.shift_date.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        pools = list(result.scalars().all())

        logger.info(
            "tip_pools_listed",
            venue_id=str(venue_id),
            total=total,
            page=page,
        )

        return pools, total

    # -------------------------------------------------------------------------
    # Tip Pool Operations
    # -------------------------------------------------------------------------

    async def add_tips_to_pool(
        self,
        pool_id: uuid.UUID,
        amount: Decimal,
    ) -> TipPool:
        """
        Add tips to an open tip pool.

        Args:
            pool_id: The ID of the tip pool.
            amount: The amount of tips to add (must be positive).

        Returns:
            The updated TipPool instance.

        Raises:
            ServiceError: If the pool is not found, already closed, or already distributed.
        """
        tip_pool = await self.get_tip_pool(pool_id)

        if tip_pool.status != TipPoolStatus.OPEN.value:
            if tip_pool.status == TipPoolStatus.CLOSED.value:
                raise bad_request(
                    ErrorCode.TIP_POOL_ALREADY_CLOSED,
                    f"Tip pool {pool_id} is already closed",
                )
            raise bad_request(
                ErrorCode.TIP_POOL_ALREADY_DISTRIBUTED,
                f"Tip pool {pool_id} has already been distributed",
            )

        # Add tips
        tip_pool.total_tips = tip_pool.total_tips + amount
        await self.db.commit()
        await self.db.refresh(tip_pool)

        logger.info(
            "tips_added_to_pool",
            pool_id=str(pool_id),
            amount=str(amount),
            new_total=str(tip_pool.total_tips),
        )

        # Publish event
        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.TIP_POOL_TIPS_ADDED,
                {
                    "pool_id": str(pool_id),
                    "venue_id": str(tip_pool.venue_id),
                    "amount_added": str(amount),
                    "total_tips": str(tip_pool.total_tips),
                },
                venue_id=tip_pool.venue_id,
            )

        return tip_pool

    async def add_participant(
        self,
        pool_id: uuid.UUID,
        employee_id: uuid.UUID,
        employee_name: str,
        hours_worked: Decimal,
    ) -> TipPool:
        """
        Add or update a participant in the tip pool.

        If the employee is already in the pool, their hours are updated.
        Otherwise, they are added as a new participant.

        Args:
            pool_id: The ID of the tip pool.
            employee_id: The employee's unique identifier.
            employee_name: The employee's display name.
            hours_worked: The number of hours worked during the shift.

        Returns:
            The updated TipPool instance.

        Raises:
            ServiceError: If the pool is not found, already closed, or already distributed.
        """
        tip_pool = await self.get_tip_pool(pool_id)

        if tip_pool.status != TipPoolStatus.OPEN.value:
            if tip_pool.status == TipPoolStatus.CLOSED.value:
                raise bad_request(
                    ErrorCode.TIP_POOL_ALREADY_CLOSED,
                    f"Tip pool {pool_id} is already closed",
                )
            raise bad_request(
                ErrorCode.TIP_POOL_ALREADY_DISTRIBUTED,
                f"Tip pool {pool_id} has already been distributed",
            )

        # Get current participants or initialize empty list
        participants = tip_pool.pool_participants or []

        # Check if employee already exists in pool
        employee_id_str = str(employee_id)
        existing_idx = None
        for idx, p in enumerate(participants):
            if p.get("employee_id") == employee_id_str:
                existing_idx = idx
                break

        participant_data = {
            "employee_id": employee_id_str,
            "employee_name": employee_name,
            "hours_worked": str(hours_worked),
            "tip_share": None,
        }

        if existing_idx is not None:
            # Update existing participant
            participants[existing_idx] = participant_data
            logger.info(
                "tip_pool_participant_updated",
                pool_id=str(pool_id),
                employee_id=employee_id_str,
                hours_worked=str(hours_worked),
            )
        else:
            # Add new participant
            participants.append(participant_data)
            logger.info(
                "tip_pool_participant_added",
                pool_id=str(pool_id),
                employee_id=employee_id_str,
                hours_worked=str(hours_worked),
            )

        tip_pool.pool_participants = participants
        await self.db.commit()
        await self.db.refresh(tip_pool)

        # Publish event
        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.TIP_POOL_PARTICIPANT_ADDED,
                {
                    "pool_id": str(pool_id),
                    "venue_id": str(tip_pool.venue_id),
                    "employee_id": employee_id_str,
                    "employee_name": employee_name,
                    "hours_worked": str(hours_worked),
                    "total_participants": len(participants),
                },
                venue_id=tip_pool.venue_id,
            )

        return tip_pool

    async def remove_participant(
        self,
        pool_id: uuid.UUID,
        employee_id: uuid.UUID,
    ) -> TipPool:
        """
        Remove a participant from the tip pool.

        Args:
            pool_id: The ID of the tip pool.
            employee_id: The employee's unique identifier.

        Returns:
            The updated TipPool instance.

        Raises:
            ServiceError: If the pool is not found, already closed, or already distributed.
        """
        tip_pool = await self.get_tip_pool(pool_id)

        if tip_pool.status != TipPoolStatus.OPEN.value:
            if tip_pool.status == TipPoolStatus.CLOSED.value:
                raise bad_request(
                    ErrorCode.TIP_POOL_ALREADY_CLOSED,
                    f"Tip pool {pool_id} is already closed",
                )
            raise bad_request(
                ErrorCode.TIP_POOL_ALREADY_DISTRIBUTED,
                f"Tip pool {pool_id} has already been distributed",
            )

        # Get current participants
        participants = tip_pool.pool_participants or []
        employee_id_str = str(employee_id)

        # Filter out the employee
        new_participants = [
            p for p in participants if p.get("employee_id") != employee_id_str
        ]

        if len(new_participants) == len(participants):
            logger.warning(
                "tip_pool_participant_not_found",
                pool_id=str(pool_id),
                employee_id=employee_id_str,
            )
            # Participant not found, but don't raise an error
            return tip_pool

        tip_pool.pool_participants = new_participants
        await self.db.commit()
        await self.db.refresh(tip_pool)

        logger.info(
            "tip_pool_participant_removed",
            pool_id=str(pool_id),
            employee_id=employee_id_str,
        )

        return tip_pool

    async def close_pool(self, pool_id: uuid.UUID) -> TipPool:
        """
        Close a tip pool, preventing further modifications.

        A closed pool can still be distributed but cannot accept new tips
        or participants.

        Args:
            pool_id: The ID of the tip pool to close.

        Returns:
            The updated TipPool instance.

        Raises:
            ServiceError: If the pool is not found, already closed, or already distributed.
        """
        tip_pool = await self.get_tip_pool(pool_id)

        if tip_pool.status == TipPoolStatus.CLOSED.value:
            raise bad_request(
                ErrorCode.TIP_POOL_ALREADY_CLOSED,
                f"Tip pool {pool_id} is already closed",
            )

        if tip_pool.status == TipPoolStatus.DISTRIBUTED.value:
            raise bad_request(
                ErrorCode.TIP_POOL_ALREADY_DISTRIBUTED,
                f"Tip pool {pool_id} has already been distributed",
            )

        tip_pool.status = TipPoolStatus.CLOSED.value
        tip_pool.closed_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(tip_pool)

        logger.info(
            "tip_pool_closed",
            pool_id=str(pool_id),
            venue_id=str(tip_pool.venue_id),
            total_tips=str(tip_pool.total_tips),
        )

        # Publish event
        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.TIP_POOL_CLOSED,
                {
                    "pool_id": str(pool_id),
                    "venue_id": str(tip_pool.venue_id),
                    "total_tips": str(tip_pool.total_tips),
                    "participant_count": len(tip_pool.pool_participants or []),
                },
                venue_id=tip_pool.venue_id,
            )

        return tip_pool

    # -------------------------------------------------------------------------
    # Tip Distribution
    # -------------------------------------------------------------------------

    async def calculate_distribution(
        self,
        pool_id: uuid.UUID,
    ) -> List[Dict[str, Any]]:
        """
        Calculate and preview tip distribution without committing.

        This method calculates how tips would be distributed based on the
        pool's distribution method, allowing managers to review before
        finalizing.

        Args:
            pool_id: The ID of the tip pool.

        Returns:
            List of distribution previews with employee_id, employee_name,
            hours_worked, tip_amount, and percentage.

        Raises:
            ServiceError: If the pool has no participants or has already been distributed.
        """
        tip_pool = await self.get_tip_pool(pool_id)

        if tip_pool.status == TipPoolStatus.DISTRIBUTED.value:
            raise bad_request(
                ErrorCode.TIP_POOL_ALREADY_DISTRIBUTED,
                f"Tip pool {pool_id} has already been distributed",
            )

        participants = tip_pool.pool_participants or []
        if not participants:
            raise bad_request(
                ErrorCode.TIP_POOL_NO_PARTICIPANTS,
                f"Tip pool {pool_id} has no participants",
            )

        total_tips = tip_pool.total_tips
        distribution_method = tip_pool.distribution_method

        distributions = []

        if distribution_method == "equal":
            # Equal distribution
            tip_per_person = (total_tips / len(participants)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            percentage = (Decimal("100") / len(participants)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            for p in participants:
                distributions.append({
                    "employee_id": p["employee_id"],
                    "employee_name": p["employee_name"],
                    "hours_worked": Decimal(p["hours_worked"]),
                    "tip_amount": tip_per_person,
                    "percentage": percentage,
                })

        elif distribution_method == "hours_based":
            # Hours-based distribution
            total_hours = sum(
                Decimal(p["hours_worked"]) for p in participants
            )

            if total_hours == 0:
                # If no hours recorded, fall back to equal distribution
                tip_per_person = (total_tips / len(participants)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                percentage = (Decimal("100") / len(participants)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

                for p in participants:
                    distributions.append({
                        "employee_id": p["employee_id"],
                        "employee_name": p["employee_name"],
                        "hours_worked": Decimal(p["hours_worked"]),
                        "tip_amount": tip_per_person,
                        "percentage": percentage,
                    })
            else:
                for p in participants:
                    hours = Decimal(p["hours_worked"])
                    percentage = ((hours / total_hours) * 100).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    tip_amount = ((hours / total_hours) * total_tips).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    distributions.append({
                        "employee_id": p["employee_id"],
                        "employee_name": p["employee_name"],
                        "hours_worked": hours,
                        "tip_amount": tip_amount,
                        "percentage": percentage,
                    })

        elif distribution_method == "sales_based":
            # Sales-based distribution - requires sales data in participant records
            # For now, fall back to equal if no sales data
            # This can be extended to pull sales data from transactions
            tip_per_person = (total_tips / len(participants)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            percentage = (Decimal("100") / len(participants)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            for p in participants:
                distributions.append({
                    "employee_id": p["employee_id"],
                    "employee_name": p["employee_name"],
                    "hours_worked": Decimal(p["hours_worked"]),
                    "tip_amount": tip_per_person,
                    "percentage": percentage,
                })

        # Adjust for rounding differences
        total_distributed = sum(d["tip_amount"] for d in distributions)
        if distributions and total_distributed != total_tips:
            difference = total_tips - total_distributed
            # Add the difference to the first participant
            distributions[0]["tip_amount"] += difference

        logger.info(
            "tip_distribution_calculated",
            pool_id=str(pool_id),
            distribution_method=distribution_method,
            participant_count=len(participants),
            total_tips=str(total_tips),
        )

        return distributions

    async def distribute_tips(
        self,
        pool_id: uuid.UUID,
        distributed_by: uuid.UUID,
    ) -> List[TipDistribution]:
        """
        Finalize and execute tip distribution.

        Calculates the distribution, creates TipDistribution records for each
        participant, and marks the pool as distributed.

        Args:
            pool_id: The ID of the tip pool to distribute.
            distributed_by: The user ID of the person authorizing the distribution.

        Returns:
            List of created TipDistribution records.

        Raises:
            ServiceError: If the pool has no participants or has already been distributed.
        """
        tip_pool = await self.get_tip_pool(pool_id)

        if tip_pool.status == TipPoolStatus.DISTRIBUTED.value:
            raise bad_request(
                ErrorCode.TIP_POOL_ALREADY_DISTRIBUTED,
                f"Tip pool {pool_id} has already been distributed",
            )

        # Calculate distribution
        distribution_preview = await self.calculate_distribution(pool_id)

        # Create distribution records
        distributions: List[TipDistribution] = []
        total_distributed = Decimal("0")

        for dist in distribution_preview:
            distribution = TipDistribution(
                tip_pool_id=pool_id,
                venue_id=tip_pool.venue_id,
                employee_id=uuid.UUID(dist["employee_id"]),
                employee_name=dist["employee_name"],
                hours_worked=dist["hours_worked"],
                tip_amount=dist["tip_amount"],
            )
            self.db.add(distribution)
            distributions.append(distribution)
            total_distributed += dist["tip_amount"]

        # Update pool participants with their tip shares
        participants = tip_pool.pool_participants or []
        for p in participants:
            for dist in distribution_preview:
                if p["employee_id"] == dist["employee_id"]:
                    p["tip_share"] = str(dist["tip_amount"])
                    break

        # Update pool status
        tip_pool.status = TipPoolStatus.DISTRIBUTED.value
        tip_pool.distributed_amount = total_distributed
        tip_pool.distributed_at = datetime.utcnow()
        tip_pool.distributed_by = distributed_by
        tip_pool.pool_participants = participants

        await self.db.commit()

        # Refresh all distribution records
        for dist in distributions:
            await self.db.refresh(dist)

        logger.info(
            "tips_distributed",
            pool_id=str(pool_id),
            venue_id=str(tip_pool.venue_id),
            total_distributed=str(total_distributed),
            participant_count=len(distributions),
            distributed_by=str(distributed_by),
        )

        # Publish event
        if self.event_publisher:
            await self.event_publisher.publish(
                EventType.TIP_POOL_DISTRIBUTED,
                {
                    "pool_id": str(pool_id),
                    "venue_id": str(tip_pool.venue_id),
                    "total_distributed": str(total_distributed),
                    "participant_count": len(distributions),
                    "distributed_by": str(distributed_by),
                    "distribution_method": tip_pool.distribution_method,
                },
                venue_id=tip_pool.venue_id,
            )

        return distributions

    # -------------------------------------------------------------------------
    # Reporting
    # -------------------------------------------------------------------------

    async def get_employee_tips(
        self,
        venue_id: uuid.UUID,
        employee_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> List[TipDistribution]:
        """
        Get tip distributions for a specific employee within a date range.

        Args:
            venue_id: The venue ID to filter by.
            employee_id: The employee ID to filter by.
            date_from: Start date of the range (inclusive).
            date_to: End date of the range (inclusive).

        Returns:
            List of TipDistribution records for the employee.
        """
        result = await self.db.execute(
            select(TipDistribution)
            .join(TipPool)
            .where(
                and_(
                    TipDistribution.venue_id == venue_id,
                    TipDistribution.employee_id == employee_id,
                    TipPool.shift_date >= date_from,
                    TipPool.shift_date <= date_to,
                )
            )
            .order_by(TipPool.shift_date.desc())
        )
        distributions = list(result.scalars().all())

        logger.info(
            "employee_tips_retrieved",
            venue_id=str(venue_id),
            employee_id=str(employee_id),
            date_from=str(date_from),
            date_to=str(date_to),
            count=len(distributions),
        )

        return distributions

    async def get_tip_summary(
        self,
        venue_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> Dict[str, Any]:
        """
        Get a summary of tip activity for a venue within a date range.

        Args:
            venue_id: The venue ID to summarize.
            date_from: Start date of the range (inclusive).
            date_to: End date of the range (inclusive).

        Returns:
            Dictionary containing:
            - venue_id: The venue ID
            - date_from: Start date
            - date_to: End date
            - total_pools: Number of tip pools
            - total_tips_collected: Total tips collected
            - total_tips_distributed: Total tips distributed
            - total_participants: Total unique participants
            - pools_by_status: Counts by pool status
            - average_tip_per_pool: Average tips per pool
            - average_tip_per_employee: Average tips per employee
        """
        # Get pool statistics
        pools_query = select(
            func.count(TipPool.id).label("total_pools"),
            func.coalesce(func.sum(TipPool.total_tips), Decimal("0")).label(
                "total_tips_collected"
            ),
            func.coalesce(func.sum(TipPool.distributed_amount), Decimal("0")).label(
                "total_tips_distributed"
            ),
            TipPool.status,
        ).where(
            and_(
                TipPool.venue_id == venue_id,
                TipPool.shift_date >= date_from,
                TipPool.shift_date <= date_to,
            )
        ).group_by(TipPool.status)

        pools_result = await self.db.execute(pools_query)
        pools_rows = pools_result.all()

        total_pools = 0
        total_tips_collected = Decimal("0")
        total_tips_distributed = Decimal("0")
        pools_by_status: Dict[str, int] = {}

        for row in pools_rows:
            total_pools += row.total_pools
            total_tips_collected += row.total_tips_collected
            total_tips_distributed += row.total_tips_distributed
            pools_by_status[row.status] = row.total_pools

        # Get participant count
        participants_query = select(
            func.count(func.distinct(TipDistribution.employee_id))
        ).where(
            and_(
                TipDistribution.venue_id == venue_id,
                TipDistribution.created_at >= datetime.combine(date_from, datetime.min.time()),
                TipDistribution.created_at <= datetime.combine(date_to, datetime.max.time()),
            )
        )

        participants_result = await self.db.execute(participants_query)
        total_participants = participants_result.scalar() or 0

        # Calculate averages
        average_tip_per_pool = (
            (total_tips_collected / total_pools).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if total_pools > 0
            else Decimal("0")
        )

        average_tip_per_employee = (
            (total_tips_distributed / total_participants).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if total_participants > 0
            else Decimal("0")
        )

        summary = {
            "venue_id": str(venue_id),
            "date_from": str(date_from),
            "date_to": str(date_to),
            "total_pools": total_pools,
            "total_tips_collected": str(total_tips_collected),
            "total_tips_distributed": str(total_tips_distributed),
            "total_participants": total_participants,
            "pools_by_status": pools_by_status,
            "average_tip_per_pool": str(average_tip_per_pool),
            "average_tip_per_employee": str(average_tip_per_employee),
        }

        logger.info(
            "tip_summary_generated",
            venue_id=str(venue_id),
            date_from=str(date_from),
            date_to=str(date_to),
            total_pools=total_pools,
            total_tips_collected=str(total_tips_collected),
        )

        return summary
