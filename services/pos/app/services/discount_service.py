"""Discount service for POS Integration."""

from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple
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
from app.models.pos import Discount, DiscountType
from app.schemas.pos import DiscountCreate, DiscountUpdate
from app.services.event_publisher import EventPublisher, EventType

logger = structlog.get_logger()


class DiscountService:
    """
    Service for managing venue discounts and promotional codes.

    This service handles the full lifecycle of discounts including creation,
    validation, application, and usage tracking. It supports multiple discount
    types including percentage-based, fixed amount, BOGO, member discounts,
    and promotional codes.

    Attributes:
        db: AsyncSession for database operations.
        event_publisher: Optional event publisher for broadcasting discount events.
    """

    def __init__(
        self,
        db: AsyncSession,
        event_publisher: Optional[EventPublisher] = None,
    ):
        """
        Initialize the DiscountService.

        Args:
            db: SQLAlchemy async session for database operations.
            event_publisher: Optional RabbitMQ event publisher for broadcasting events.
        """
        self.db = db
        self.event_publisher = event_publisher

    async def create_discount(
        self,
        venue_id: UUID,
        data: DiscountCreate,
    ) -> Discount:
        """
        Create a new discount for a venue.

        Creates a discount configuration with the specified parameters. If a code
        is provided, it must be unique within the venue.

        Args:
            venue_id: UUID of the venue creating the discount.
            data: DiscountCreate schema with discount configuration.

        Returns:
            The newly created Discount object.

        Raises:
            ServiceError: If a discount with the same code already exists for the venue.
        """
        # Check for duplicate code if provided
        if data.code:
            existing = await self._get_discount_by_code_internal(venue_id, data.code)
            if existing:
                logger.warning(
                    "discount_code_exists",
                    venue_id=str(venue_id),
                    code=data.code,
                )
                raise conflict(
                    ErrorCode.DISCOUNT_CODE_EXISTS,
                    f"Discount code '{data.code}' already exists for this venue",
                )

        discount = Discount(
            venue_id=venue_id,
            code=data.code,
            name=data.name,
            description=data.description,
            discount_type=data.discount_type.value,
            value=data.value,
            min_purchase_amount=data.min_purchase_amount,
            max_discount_amount=data.max_discount_amount,
            applies_to=data.applies_to,
            start_date=data.start_date,
            end_date=data.end_date,
            max_uses=data.max_uses,
            current_uses=0,
            is_active=data.is_active,
            requires_member=data.requires_member,
        )
        self.db.add(discount)
        await self.db.commit()
        await self.db.refresh(discount)

        logger.info(
            "discount_created",
            discount_id=str(discount.id),
            venue_id=str(venue_id),
            code=data.code,
            discount_type=data.discount_type.value,
        )

        return discount

    async def get_discount(self, discount_id: UUID) -> Discount:
        """
        Retrieve a discount by its ID.

        Args:
            discount_id: UUID of the discount to retrieve.

        Returns:
            The Discount object if found.

        Raises:
            ServiceError: If the discount is not found (404).
        """
        result = await self.db.execute(
            select(Discount).where(Discount.id == discount_id)
        )
        discount = result.scalars().first()
        if not discount:
            raise not_found(
                ErrorCode.DISCOUNT_NOT_FOUND,
                f"Discount {discount_id} not found",
            )
        return discount

    async def _get_discount_by_code_internal(
        self,
        venue_id: UUID,
        code: str,
    ) -> Optional[Discount]:
        """
        Internal helper to get discount by code without raising an error.

        Args:
            venue_id: UUID of the venue.
            code: Discount code to search for.

        Returns:
            Discount object if found, None otherwise.
        """
        result = await self.db.execute(
            select(Discount).where(
                and_(
                    Discount.venue_id == venue_id,
                    Discount.code == code,
                )
            )
        )
        return result.scalars().first()

    async def get_discount_by_code(
        self,
        venue_id: UUID,
        code: str,
    ) -> Discount:
        """
        Retrieve a discount by its code within a venue.

        Args:
            venue_id: UUID of the venue.
            code: Discount code to search for.

        Returns:
            The Discount object if found.

        Raises:
            ServiceError: If the discount code is not found (404).
        """
        discount = await self._get_discount_by_code_internal(venue_id, code)
        if not discount:
            raise not_found(
                ErrorCode.DISCOUNT_NOT_FOUND,
                f"Discount code '{code}' not found",
            )
        return discount

    async def list_discounts(
        self,
        venue_id: UUID,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Discount]:
        """
        List discounts for a venue with optional filtering.

        Args:
            venue_id: UUID of the venue.
            active_only: If True, only return active discounts (default: True).
            skip: Number of records to skip for pagination (default: 0).
            limit: Maximum number of records to return (default: 50).

        Returns:
            List of Discount objects matching the criteria.
        """
        query = select(Discount).where(Discount.venue_id == venue_id)

        if active_only:
            query = query.where(Discount.is_active == True)  # noqa: E712

        query = query.order_by(Discount.created_at.desc())
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        discounts = list(result.scalars().all())

        logger.info(
            "discounts_listed",
            venue_id=str(venue_id),
            active_only=active_only,
            count=len(discounts),
        )

        return discounts

    async def update_discount(
        self,
        discount_id: UUID,
        data: DiscountUpdate,
    ) -> Discount:
        """
        Update an existing discount.

        Updates the discount with the provided fields. Only non-None fields
        in the update data will be modified.

        Args:
            discount_id: UUID of the discount to update.
            data: DiscountUpdate schema with fields to update.

        Returns:
            The updated Discount object.

        Raises:
            ServiceError: If the discount is not found (404).
            ServiceError: If updating code to one that already exists (409).
        """
        discount = await self.get_discount(discount_id)

        # Check for duplicate code if code is being updated
        if data.code is not None and data.code != discount.code:
            existing = await self._get_discount_by_code_internal(
                discount.venue_id, data.code
            )
            if existing and existing.id != discount_id:
                raise conflict(
                    ErrorCode.DISCOUNT_CODE_EXISTS,
                    f"Discount code '{data.code}' already exists for this venue",
                )

        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "discount_type" and value is not None:
                setattr(discount, field, value.value)
            else:
                setattr(discount, field, value)

        await self.db.commit()
        await self.db.refresh(discount)

        logger.info(
            "discount_updated",
            discount_id=str(discount_id),
            venue_id=str(discount.venue_id),
            updated_fields=list(update_data.keys()),
        )

        return discount

    async def deactivate_discount(self, discount_id: UUID) -> Discount:
        """
        Deactivate a discount.

        Sets the discount's is_active flag to False, preventing it from
        being used in future transactions.

        Args:
            discount_id: UUID of the discount to deactivate.

        Returns:
            The deactivated Discount object.

        Raises:
            ServiceError: If the discount is not found (404).
        """
        discount = await self.get_discount(discount_id)
        discount.is_active = False
        await self.db.commit()
        await self.db.refresh(discount)

        logger.info(
            "discount_deactivated",
            discount_id=str(discount_id),
            venue_id=str(discount.venue_id),
        )

        return discount

    async def validate_discount(
        self,
        venue_id: UUID,
        code: str,
        subtotal: Decimal,
        is_member: bool = False,
    ) -> Tuple[bool, str, Optional[Discount]]:
        """
        Validate a discount code for a transaction.

        Checks if a discount code is valid for use, considering:
        - Whether the code exists and belongs to the venue
        - Whether the discount is active
        - Whether the discount is within its validity period
        - Whether the discount has reached its maximum uses
        - Whether the minimum purchase requirement is met
        - Whether membership is required

        Args:
            venue_id: UUID of the venue.
            code: Discount code to validate.
            subtotal: Transaction subtotal to check against minimum purchase.
            is_member: Whether the customer is a member (default: False).

        Returns:
            Tuple of (is_valid: bool, message: str, discount: Optional[Discount]).
            - If valid: (True, success message, Discount object)
            - If invalid: (False, error message, None)
        """
        # Try to find the discount
        discount = await self._get_discount_by_code_internal(venue_id, code)
        if not discount:
            return (False, f"Discount code '{code}' not found", None)

        # Check if active
        if not discount.is_active:
            return (False, "This discount is no longer active", None)

        # Check validity period
        today = date.today()
        if discount.start_date > today:
            return (False, "This discount is not yet valid", None)
        if discount.end_date and discount.end_date < today:
            return (False, "This discount has expired", None)

        # Check max uses
        if discount.max_uses is not None and discount.current_uses >= discount.max_uses:
            return (False, "This discount has reached its maximum uses", None)

        # Check minimum purchase
        if (
            discount.min_purchase_amount is not None
            and subtotal < discount.min_purchase_amount
        ):
            return (
                False,
                f"Minimum purchase of ${discount.min_purchase_amount} required",
                None,
            )

        # Check member requirement
        if discount.requires_member and not is_member:
            return (False, "This discount is only available for members", None)

        logger.info(
            "discount_validated",
            venue_id=str(venue_id),
            code=code,
            discount_id=str(discount.id),
        )

        return (True, "Discount is valid", discount)

    async def apply_discount(
        self,
        discount: Discount,
        subtotal: Decimal,
    ) -> Decimal:
        """
        Calculate the discount amount to apply to a transaction.

        Calculates the discount based on the discount type:
        - PERCENTAGE: Applies percentage to subtotal
        - FIXED_AMOUNT: Returns the fixed discount value
        - BOGO: Assumes 50% off (buy one get one)
        - MEMBER_DISCOUNT: Applies percentage to subtotal
        - PROMO_CODE: Can be percentage or fixed amount based on value

        The calculated discount is capped at max_discount_amount if specified.

        Args:
            discount: The Discount object to apply.
            subtotal: The transaction subtotal.

        Returns:
            The calculated discount amount (Decimal).
        """
        discount_amount = Decimal("0")

        if discount.discount_type == DiscountType.PERCENTAGE.value:
            # Value is a percentage (e.g., 10 = 10%)
            discount_amount = subtotal * (discount.value / Decimal("100"))
        elif discount.discount_type == DiscountType.FIXED_AMOUNT.value:
            # Value is a fixed dollar amount
            discount_amount = min(discount.value, subtotal)
        elif discount.discount_type == DiscountType.BOGO.value:
            # Buy one get one - assume 50% off
            discount_amount = subtotal * Decimal("0.5")
        elif discount.discount_type == DiscountType.MEMBER_DISCOUNT.value:
            # Member discount is percentage-based
            discount_amount = subtotal * (discount.value / Decimal("100"))
        elif discount.discount_type == DiscountType.PROMO_CODE.value:
            # Promo codes can be percentage or fixed - check value
            if discount.value <= Decimal("100"):
                # Treat as percentage
                discount_amount = subtotal * (discount.value / Decimal("100"))
            else:
                # Treat as fixed amount
                discount_amount = min(discount.value, subtotal)

        # Apply maximum discount cap if set
        if discount.max_discount_amount is not None:
            discount_amount = min(discount_amount, discount.max_discount_amount)

        # Ensure discount doesn't exceed subtotal
        discount_amount = min(discount_amount, subtotal)

        # Round to 2 decimal places
        discount_amount = discount_amount.quantize(Decimal("0.01"))

        logger.info(
            "discount_applied",
            discount_id=str(discount.id),
            discount_type=discount.discount_type,
            subtotal=str(subtotal),
            discount_amount=str(discount_amount),
        )

        return discount_amount

    async def increment_usage(self, discount_id: UUID) -> None:
        """
        Increment the usage counter for a discount.

        Should be called after a discount is successfully applied to a transaction.
        This helps track usage against the max_uses limit.

        Args:
            discount_id: UUID of the discount to increment.

        Raises:
            ServiceError: If the discount is not found (404).
        """
        discount = await self.get_discount(discount_id)
        discount.current_uses += 1
        await self.db.commit()

        logger.info(
            "discount_usage_incremented",
            discount_id=str(discount_id),
            current_uses=discount.current_uses,
            max_uses=discount.max_uses,
        )

        # Publish event if max uses reached
        if (
            self.event_publisher
            and discount.max_uses is not None
            and discount.current_uses >= discount.max_uses
        ):
            await self.event_publisher.publish(
                EventType.POS_SYNC_COMPLETED,  # Consider adding DISCOUNT_MAX_USES_REACHED event
                {
                    "discount_id": str(discount.id),
                    "venue_id": str(discount.venue_id),
                    "code": discount.code,
                    "current_uses": discount.current_uses,
                    "max_uses": discount.max_uses,
                },
                venue_id=discount.venue_id,
            )
