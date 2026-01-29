"""
=============================================================================
FILE: services/currency_service.py
PURPOSE: Multi-currency management and conversion business logic
=============================================================================

Handles CRUD operations for venue-specific currency configurations and
provides currency conversion functionality for international POS operations.

Features:
- Currency creation and management for venues
- Base currency designation per venue
- Exchange rate updates and tracking
- Amount conversion between currencies
- Formatted currency display
- Batch rate updates (stub for external API integration)
"""

import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
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
from app.models.pos import Currency
from app.schemas.pos import (
    CurrencyCreate,
    CurrencyUpdate,
    CurrencyConversionRequest,
    CurrencyConversionResponse,
)

logger = structlog.get_logger()


class CurrencyService:
    """
    Service for managing multi-currency support in POS operations.

    Provides functionality for:
    - Creating and managing currency configurations per venue
    - Designating and managing base currencies
    - Updating exchange rates
    - Converting amounts between currencies
    - Formatting amounts with currency symbols

    Each venue must have exactly one base currency (is_base=True) which
    serves as the reference for all exchange rate calculations.

    Attributes:
        db: AsyncSession for database operations.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the CurrencyService.

        Args:
            db: SQLAlchemy async session for database operations.
        """
        self.db = db

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def create_currency(
        self,
        venue_id: uuid.UUID,
        code: str,
        name: str,
        symbol: str,
        decimal_places: int,
        exchange_rate: Decimal,
        is_base: bool = False,
    ) -> Currency:
        """
        Create a new currency configuration for a venue.

        If is_base is True, any existing base currency for the venue will
        be demoted (is_base set to False). The base currency's exchange
        rate is always set to 1.0.

        Args:
            venue_id: UUID of the venue.
            code: ISO 4217 currency code (3 characters, e.g., USD, EUR).
            name: Human-readable currency name (e.g., US Dollar).
            symbol: Currency symbol for display (e.g., $, EUR).
            decimal_places: Number of decimal places for this currency.
            exchange_rate: Conversion rate to the venue's base currency.
            is_base: Whether this is the venue's base currency.

        Returns:
            The newly created Currency record.

        Raises:
            ServiceError: If a currency with the same code already exists
                for this venue (CURRENCY_CODE_EXISTS).
        """
        # Normalize currency code to uppercase
        code = code.upper()

        # Check for duplicate currency code
        existing_query = select(Currency).where(
            and_(
                Currency.venue_id == venue_id,
                Currency.code == code,
            )
        )
        result = await self.db.execute(existing_query)
        if result.scalars().first():
            raise conflict(
                ErrorCode.CURRENCY_CODE_EXISTS,
                f"Currency code '{code}' already exists for this venue",
            )

        # If setting as base currency, demote any existing base
        if is_base:
            await self._demote_existing_base_currency(venue_id)
            exchange_rate = Decimal("1.000000")  # Base currency always has rate 1.0

        currency = Currency(
            venue_id=venue_id,
            code=code,
            name=name,
            symbol=symbol,
            decimal_places=decimal_places,
            exchange_rate=exchange_rate,
            is_base=is_base,
            is_active=True,
            last_rate_update=datetime.utcnow() if not is_base else None,
        )
        self.db.add(currency)
        await self.db.commit()
        await self.db.refresh(currency)

        logger.info(
            "currency_created",
            currency_id=str(currency.id),
            venue_id=str(venue_id),
            code=code,
            is_base=is_base,
            exchange_rate=str(exchange_rate),
        )
        return currency

    async def get_currency(self, currency_id: uuid.UUID) -> Currency:
        """
        Get a single currency by its ID.

        Args:
            currency_id: UUID of the currency to retrieve.

        Returns:
            The Currency record.

        Raises:
            ServiceError: If the currency is not found (CURRENCY_NOT_FOUND).
        """
        result = await self.db.execute(
            select(Currency).where(Currency.id == currency_id)
        )
        currency = result.scalars().first()
        if not currency:
            raise not_found(
                ErrorCode.CURRENCY_NOT_FOUND,
                f"Currency {currency_id} not found",
            )
        return currency

    async def get_currency_by_code(
        self,
        venue_id: uuid.UUID,
        code: str,
    ) -> Currency:
        """
        Get a currency by its ISO code for a specific venue.

        Args:
            venue_id: UUID of the venue.
            code: ISO 4217 currency code (e.g., USD, EUR).

        Returns:
            The Currency record.

        Raises:
            ServiceError: If the currency is not found (CURRENCY_NOT_FOUND).
        """
        code = code.upper()
        result = await self.db.execute(
            select(Currency).where(
                and_(
                    Currency.venue_id == venue_id,
                    Currency.code == code,
                )
            )
        )
        currency = result.scalars().first()
        if not currency:
            raise not_found(
                ErrorCode.CURRENCY_NOT_FOUND,
                f"Currency '{code}' not found for this venue",
            )
        return currency

    async def get_base_currency(self, venue_id: uuid.UUID) -> Currency:
        """
        Get the base currency for a venue.

        Args:
            venue_id: UUID of the venue.

        Returns:
            The base Currency record.

        Raises:
            ServiceError: If no base currency is configured
                (CURRENCY_BASE_REQUIRED).
        """
        result = await self.db.execute(
            select(Currency).where(
                and_(
                    Currency.venue_id == venue_id,
                    Currency.is_base == True,  # noqa: E712
                )
            )
        )
        currency = result.scalars().first()
        if not currency:
            raise bad_request(
                ErrorCode.CURRENCY_BASE_REQUIRED,
                "No base currency configured for this venue. "
                "Please create a base currency first.",
            )
        return currency

    async def list_currencies(
        self,
        venue_id: uuid.UUID,
        active_only: bool = True,
    ) -> List[Currency]:
        """
        List all currencies for a venue.

        Args:
            venue_id: UUID of the venue.
            active_only: If True, only return active currencies.
                Defaults to True.

        Returns:
            List of Currency records, ordered with base currency first,
            then alphabetically by code.
        """
        query = select(Currency).where(Currency.venue_id == venue_id)

        if active_only:
            query = query.where(Currency.is_active == True)  # noqa: E712

        # Order by is_base DESC (base first), then by code
        query = query.order_by(Currency.is_base.desc(), Currency.code)

        result = await self.db.execute(query)
        currencies = list(result.scalars().all())

        logger.info(
            "currencies_listed",
            venue_id=str(venue_id),
            count=len(currencies),
            active_only=active_only,
        )
        return currencies

    async def update_exchange_rate(
        self,
        currency_id: uuid.UUID,
        new_rate: Decimal,
    ) -> Currency:
        """
        Update the exchange rate for a currency.

        Cannot update the exchange rate of a base currency (which is
        always 1.0).

        Args:
            currency_id: UUID of the currency to update.
            new_rate: The new exchange rate to the base currency.

        Returns:
            The updated Currency record.

        Raises:
            ServiceError: If the currency is not found (CURRENCY_NOT_FOUND)
                or if trying to update a base currency rate.
        """
        currency = await self.get_currency(currency_id)

        if currency.is_base:
            raise bad_request(
                ErrorCode.CURRENCY_CONVERSION_FAILED,
                "Cannot update exchange rate of base currency. "
                "Base currency rate is always 1.0.",
            )

        old_rate = currency.exchange_rate
        currency.exchange_rate = new_rate
        currency.last_rate_update = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(currency)

        logger.info(
            "exchange_rate_updated",
            currency_id=str(currency_id),
            venue_id=str(currency.venue_id),
            code=currency.code,
            old_rate=str(old_rate),
            new_rate=str(new_rate),
        )
        return currency

    async def deactivate_currency(self, currency_id: uuid.UUID) -> Currency:
        """
        Deactivate a currency, making it unavailable for new transactions.

        Cannot deactivate the base currency.

        Args:
            currency_id: UUID of the currency to deactivate.

        Returns:
            The updated Currency record.

        Raises:
            ServiceError: If the currency is not found (CURRENCY_NOT_FOUND)
                or if trying to deactivate the base currency.
        """
        currency = await self.get_currency(currency_id)

        if currency.is_base:
            raise bad_request(
                ErrorCode.CURRENCY_BASE_REQUIRED,
                "Cannot deactivate the base currency. "
                "Set another currency as base first.",
            )

        currency.is_active = False
        await self.db.commit()
        await self.db.refresh(currency)

        logger.info(
            "currency_deactivated",
            currency_id=str(currency_id),
            venue_id=str(currency.venue_id),
            code=currency.code,
        )
        return currency

    async def update_currency(
        self,
        currency_id: uuid.UUID,
        data: CurrencyUpdate,
    ) -> Currency:
        """
        Update currency details.

        Args:
            currency_id: UUID of the currency to update.
            data: Fields to update (only non-None values are applied).

        Returns:
            The updated Currency record.

        Raises:
            ServiceError: If the currency is not found (CURRENCY_NOT_FOUND).
        """
        currency = await self.get_currency(currency_id)

        update_dict = data.model_dump(exclude_unset=True)

        # Handle exchange rate update specially
        if "exchange_rate" in update_dict:
            if currency.is_base:
                raise bad_request(
                    ErrorCode.CURRENCY_CONVERSION_FAILED,
                    "Cannot update exchange rate of base currency.",
                )
            currency.last_rate_update = datetime.utcnow()

        for field, value in update_dict.items():
            setattr(currency, field, value)

        await self.db.commit()
        await self.db.refresh(currency)

        logger.info(
            "currency_updated",
            currency_id=str(currency_id),
            venue_id=str(currency.venue_id),
            code=currency.code,
            fields_updated=list(update_dict.keys()),
        )
        return currency

    # =========================================================================
    # Currency Conversion
    # =========================================================================

    async def convert_amount(
        self,
        venue_id: uuid.UUID,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
    ) -> Decimal:
        """
        Convert an amount from one currency to another.

        Conversion is performed through the base currency:
        1. Convert from source currency to base currency
        2. Convert from base currency to target currency

        Args:
            venue_id: UUID of the venue.
            amount: The amount to convert.
            from_currency: Source currency code (e.g., USD).
            to_currency: Target currency code (e.g., EUR).

        Returns:
            The converted amount, rounded to the target currency's
            decimal places.

        Raises:
            ServiceError: If either currency is not found or conversion
                fails (CURRENCY_NOT_FOUND, CURRENCY_CONVERSION_FAILED).
        """
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        # Same currency, no conversion needed
        if from_currency == to_currency:
            return amount

        # Get both currencies
        source = await self.get_currency_by_code(venue_id, from_currency)
        target = await self.get_currency_by_code(venue_id, to_currency)

        if not source.is_active:
            raise bad_request(
                ErrorCode.CURRENCY_CONVERSION_FAILED,
                f"Source currency '{from_currency}' is not active",
            )
        if not target.is_active:
            raise bad_request(
                ErrorCode.CURRENCY_CONVERSION_FAILED,
                f"Target currency '{to_currency}' is not active",
            )

        try:
            # Convert to base currency first, then to target
            # source_rate = how many base units for 1 source unit
            # target_rate = how many base units for 1 target unit
            # converted = amount * (source_rate / target_rate)
            if target.exchange_rate == 0:
                raise bad_request(
                    ErrorCode.CURRENCY_CONVERSION_FAILED,
                    f"Target currency '{to_currency}' has invalid exchange rate",
                )

            converted = amount * (source.exchange_rate / target.exchange_rate)

            # Round to target currency's decimal places
            quantize_str = "0." + "0" * target.decimal_places if target.decimal_places > 0 else "0"
            converted = converted.quantize(
                Decimal(quantize_str),
                rounding=ROUND_HALF_UP
            )

            logger.info(
                "currency_converted",
                venue_id=str(venue_id),
                amount=str(amount),
                from_currency=from_currency,
                to_currency=to_currency,
                converted_amount=str(converted),
                exchange_rate=str(source.exchange_rate / target.exchange_rate),
            )
            return converted

        except Exception as e:
            logger.error(
                "currency_conversion_failed",
                venue_id=str(venue_id),
                amount=str(amount),
                from_currency=from_currency,
                to_currency=to_currency,
                error=str(e),
            )
            raise bad_request(
                ErrorCode.CURRENCY_CONVERSION_FAILED,
                f"Failed to convert {amount} from {from_currency} to {to_currency}",
                details={"error": str(e)},
            )

    async def format_amount(
        self,
        amount: Decimal,
        currency: Currency,
    ) -> str:
        """
        Format an amount with its currency symbol.

        Args:
            amount: The amount to format.
            currency: The Currency record containing symbol and decimal places.

        Returns:
            Formatted string (e.g., "$1,234.56", "EUR1.234,56").
        """
        # Round to the currency's decimal places
        quantize_str = "0." + "0" * currency.decimal_places if currency.decimal_places > 0 else "0"
        rounded = amount.quantize(
            Decimal(quantize_str),
            rounding=ROUND_HALF_UP
        )

        # Format with thousand separators
        if currency.decimal_places > 0:
            format_str = f"{{:,.{currency.decimal_places}f}}"
        else:
            format_str = "{:,.0f}"

        formatted_number = format_str.format(float(rounded))

        # Prefix with symbol
        return f"{currency.symbol}{formatted_number}"

    async def convert_and_format(
        self,
        venue_id: uuid.UUID,
        request: CurrencyConversionRequest,
    ) -> CurrencyConversionResponse:
        """
        Convert an amount and return full conversion details with formatting.

        Args:
            venue_id: UUID of the venue.
            request: Conversion request with amount and currency codes.

        Returns:
            CurrencyConversionResponse with converted amount and formatted strings.

        Raises:
            ServiceError: If conversion fails.
        """
        from_curr = await self.get_currency_by_code(venue_id, request.from_currency)
        to_curr = await self.get_currency_by_code(venue_id, request.to_currency)

        converted = await self.convert_amount(
            venue_id,
            request.amount,
            request.from_currency,
            request.to_currency,
        )

        # Calculate effective exchange rate
        if to_curr.exchange_rate != 0:
            effective_rate = from_curr.exchange_rate / to_curr.exchange_rate
        else:
            effective_rate = Decimal("0")

        formatted_original = await self.format_amount(request.amount, from_curr)
        formatted_converted = await self.format_amount(converted, to_curr)

        return CurrencyConversionResponse(
            original_amount=request.amount,
            converted_amount=converted,
            from_currency=request.from_currency.upper(),
            to_currency=request.to_currency.upper(),
            exchange_rate=effective_rate.quantize(Decimal("0.000001")),
            formatted_original=formatted_original,
            formatted_converted=formatted_converted,
        )

    # =========================================================================
    # Batch Operations
    # =========================================================================

    async def update_rates_from_api(
        self,
        venue_id: uuid.UUID,
    ) -> List[Currency]:
        """
        Update exchange rates from an external API.

        This is a stub implementation that demonstrates the interface for
        fetching rates from external providers. In production, this would
        integrate with services like:
        - Open Exchange Rates (https://openexchangerates.org/)
        - Fixer.io (https://fixer.io/)
        - XE Currency Data (https://www.xe.com/)

        Args:
            venue_id: UUID of the venue whose currencies to update.

        Returns:
            List of updated Currency records.

        Note:
            This is a stub implementation. To enable real rate updates:
            1. Configure API credentials in environment variables
            2. Implement HTTP client calls to chosen provider
            3. Parse response and update rates accordingly
            4. Handle rate limiting and error cases
        """
        logger.info(
            "update_rates_from_api_called",
            venue_id=str(venue_id),
            message="Stub implementation - no external API configured",
        )

        # Get all active non-base currencies for the venue
        currencies = await self.list_currencies(venue_id, active_only=True)
        non_base_currencies = [c for c in currencies if not c.is_base]

        # In a real implementation, this would:
        # 1. Get the base currency code
        # 2. Call external API with base currency as reference
        # 3. Parse response and update each currency's rate
        # 4. Update last_rate_update timestamp

        # For now, just log and return existing currencies unchanged
        logger.warning(
            "exchange_rate_api_not_configured",
            venue_id=str(venue_id),
            currencies_count=len(non_base_currencies),
            message="To enable automatic rate updates, configure an exchange rate API provider",
        )

        return currencies

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _demote_existing_base_currency(
        self,
        venue_id: uuid.UUID,
    ) -> None:
        """
        Demote any existing base currency for a venue.

        Sets is_base to False for the current base currency, if one exists.
        This is called before setting a new base currency.

        Args:
            venue_id: UUID of the venue.
        """
        result = await self.db.execute(
            select(Currency).where(
                and_(
                    Currency.venue_id == venue_id,
                    Currency.is_base == True,  # noqa: E712
                )
            )
        )
        existing_base = result.scalars().first()

        if existing_base:
            existing_base.is_base = False
            logger.info(
                "base_currency_demoted",
                venue_id=str(venue_id),
                old_base_code=existing_base.code,
                currency_id=str(existing_base.id),
            )

    async def set_base_currency(
        self,
        currency_id: uuid.UUID,
    ) -> Currency:
        """
        Set a currency as the base currency for its venue.

        Demotes any existing base currency and sets the specified
        currency as the new base. The new base currency's exchange
        rate is set to 1.0.

        Args:
            currency_id: UUID of the currency to set as base.

        Returns:
            The updated Currency record.

        Raises:
            ServiceError: If the currency is not found or is not active.
        """
        currency = await self.get_currency(currency_id)

        if not currency.is_active:
            raise bad_request(
                ErrorCode.CURRENCY_CONVERSION_FAILED,
                f"Cannot set inactive currency '{currency.code}' as base",
            )

        if currency.is_base:
            # Already base, nothing to do
            return currency

        # Demote existing base
        await self._demote_existing_base_currency(currency.venue_id)

        # Set new base
        currency.is_base = True
        currency.exchange_rate = Decimal("1.000000")
        currency.last_rate_update = None  # Base currency doesn't track rate updates

        await self.db.commit()
        await self.db.refresh(currency)

        logger.info(
            "base_currency_set",
            currency_id=str(currency_id),
            venue_id=str(currency.venue_id),
            code=currency.code,
        )
        return currency
