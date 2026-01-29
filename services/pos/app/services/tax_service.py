"""
=============================================================================
FILE: services/tax_service.py
PURPOSE: Tax rate management and calculation business logic
=============================================================================

Handles CRUD operations for venue-specific tax rates and provides
tax calculation for transactions based on active rates.
"""

import uuid
from datetime import date as date_type
from decimal import Decimal
from typing import List, Optional

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ErrorCode,
    bad_request,
    conflict,
    not_found,
)
from app.models.pos import TaxRate, TaxType
from app.schemas.pos import (
    TaxCalculationRequest,
    TaxCalculationResponse,
    TaxRateCreate,
    TaxRateUpdate,
)

logger = structlog.get_logger()


class TaxService:
    """Service for managing tax rates and performing tax calculations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def list_tax_rates(
        self,
        venue_id: uuid.UUID,
        tax_type: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[TaxRate]:
        """
        List tax rates for a venue with optional filtering.

        Args:
            venue_id: Venue UUID.
            tax_type: Optional tax type filter (e.g. 'sales_tax').
            is_active: Optional active-status filter.

        Returns:
            List of matching TaxRate records.
        """
        query = select(TaxRate).where(TaxRate.venue_id == venue_id)

        if tax_type:
            query = query.where(TaxRate.tax_type == tax_type)
        if is_active is not None:
            query = query.where(TaxRate.is_active == is_active)

        query = query.order_by(TaxRate.tax_type, TaxRate.effective_date.desc())

        result = await self.db.execute(query)
        rates = list(result.scalars().all())

        logger.info(
            "tax_rates_listed",
            venue_id=str(venue_id),
            count=len(rates),
        )
        return rates

    async def get_tax_rate(self, tax_rate_id: uuid.UUID) -> TaxRate:
        """
        Get a single tax rate by ID.

        Args:
            tax_rate_id: UUID of the tax rate.

        Returns:
            TaxRate instance.

        Raises:
            ServiceError: If not found.
        """
        result = await self.db.execute(
            select(TaxRate).where(TaxRate.id == tax_rate_id)
        )
        rate = result.scalars().first()
        if not rate:
            raise not_found(
                ErrorCode.TAX_RATE_NOT_FOUND,
                f"Tax rate {tax_rate_id} not found",
            )
        return rate

    async def create_tax_rate(
        self,
        venue_id: uuid.UUID,
        data: TaxRateCreate,
    ) -> TaxRate:
        """
        Create a new tax rate for a venue.

        Checks for duplicate active tax rates of the same type and
        jurisdiction before creating.

        Args:
            venue_id: Venue UUID.
            data: Tax rate creation payload.

        Returns:
            The newly created TaxRate record.

        Raises:
            ServiceError: If a duplicate active rate exists.
        """
        # Check for duplicate active rate of the same type & jurisdiction
        duplicate_query = select(TaxRate).where(
            and_(
                TaxRate.venue_id == venue_id,
                TaxRate.tax_type == data.tax_type.value,
                TaxRate.is_active == True,  # noqa: E712
                TaxRate.jurisdiction == data.jurisdiction,
            )
        )
        dup_result = await self.db.execute(duplicate_query)
        if dup_result.scalars().first():
            raise conflict(
                ErrorCode.TAX_RATE_DUPLICATE,
                f"An active {data.tax_type.value} tax rate already exists "
                f"for this venue and jurisdiction ({data.jurisdiction})",
            )

        rate = TaxRate(
            venue_id=venue_id,
            tax_type=data.tax_type.value,
            name=data.name,
            rate=data.rate,
            applies_to=data.applies_to,
            is_active=True,
            effective_date=data.effective_date,
            end_date=data.end_date,
            jurisdiction=data.jurisdiction,
        )
        self.db.add(rate)
        await self.db.commit()
        await self.db.refresh(rate)

        logger.info(
            "tax_rate_created",
            tax_rate_id=str(rate.id),
            venue_id=str(venue_id),
            tax_type=data.tax_type.value,
            rate=str(data.rate),
        )
        return rate

    async def update_tax_rate(
        self,
        tax_rate_id: uuid.UUID,
        data: TaxRateUpdate,
    ) -> TaxRate:
        """
        Update an existing tax rate.

        Args:
            tax_rate_id: UUID of the tax rate to update.
            data: Fields to update (only non-None values are applied).

        Returns:
            The updated TaxRate record.

        Raises:
            ServiceError: If not found.
        """
        rate = await self.get_tax_rate(tax_rate_id)

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(rate, field, value)

        await self.db.commit()
        await self.db.refresh(rate)

        logger.info(
            "tax_rate_updated",
            tax_rate_id=str(tax_rate_id),
            venue_id=str(rate.venue_id),
            fields_updated=list(update_dict.keys()),
        )
        return rate

    # =========================================================================
    # Tax Calculation
    # =========================================================================

    async def calculate_tax(
        self,
        venue_id: uuid.UUID,
        data: TaxCalculationRequest,
    ) -> TaxCalculationResponse:
        """
        Calculate applicable taxes for a transaction.

        Finds all active tax rates for the venue that apply to the given
        transaction type and returns a breakdown per rate together with
        the combined totals.

        Args:
            venue_id: Venue UUID.
            data: Request containing transaction_type and subtotal.

        Returns:
            TaxCalculationResponse with per-rate breakdown and totals.
        """
        today = date_type.today()

        # Fetch all active, currently effective tax rates for this venue
        query = select(TaxRate).where(
            and_(
                TaxRate.venue_id == venue_id,
                TaxRate.is_active == True,  # noqa: E712
                TaxRate.effective_date <= today,
            )
        )
        result = await self.db.execute(query)
        all_rates = list(result.scalars().all())

        # Filter to rates that have not expired and apply to this transaction type
        applicable_rates: List[TaxRate] = []
        for rate in all_rates:
            # Skip expired rates
            if rate.end_date and rate.end_date < today:
                continue

            # If applies_to is set, check that the transaction type is listed
            if rate.applies_to:
                if data.transaction_type.value not in rate.applies_to:
                    continue

            applicable_rates.append(rate)

        # Calculate tax for each applicable rate
        total_tax = Decimal("0")
        tax_rates_breakdown = []

        for rate in applicable_rates:
            tax_amount = (data.subtotal * rate.rate).quantize(Decimal("0.01"))
            total_tax += tax_amount
            tax_rates_breakdown.append(
                {
                    "tax_rate_id": str(rate.id),
                    "tax_type": rate.tax_type,
                    "name": rate.name,
                    "rate": str(rate.rate),
                    "tax_amount": str(tax_amount),
                }
            )

        total_with_tax = data.subtotal + total_tax

        logger.info(
            "tax_calculated",
            venue_id=str(venue_id),
            transaction_type=data.transaction_type.value,
            subtotal=str(data.subtotal),
            total_tax=str(total_tax),
            rates_applied=len(applicable_rates),
        )

        return TaxCalculationResponse(
            transaction_type=data.transaction_type.value,
            subtotal=data.subtotal,
            tax_rates=tax_rates_breakdown,
            total_tax=total_tax,
            total_with_tax=total_with_tax,
        )
