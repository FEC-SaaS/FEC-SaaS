"""
Currency API routes for the POS service.

This module provides REST API endpoints for managing multi-currency support
in POS operations, including:
- Creating and managing currency configurations per venue
- Setting and retrieving base currencies
- Updating exchange rates
- Converting amounts between currencies

Each venue must have exactly one base currency (is_base=True) which serves
as the reference for all exchange rate calculations.

All endpoints require authentication and operate within the context of a venue.
"""

from decimal import Decimal
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.pos import (
    CurrencyCreate,
    CurrencyConversionRequest,
    CurrencyConversionResponse,
    CurrencyResponse,
)
from app.services.currency_service import CurrencyService

router = APIRouter(prefix="/pos/currencies")
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> CurrencyService:
    """
    Dependency to get a CurrencyService instance.

    Args:
        db: Database session from dependency injection.

    Returns:
        Configured CurrencyService instance.
    """
    return CurrencyService(db)


# ---------------------------------------------------------------------------
# POST /pos/currencies — create a new currency
# ---------------------------------------------------------------------------
@router.post(
    "/",
    response_model=CurrencyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new currency",
)
async def create_currency(
    data: CurrencyCreate,
    venue_id: UUID = Query(..., description="Venue to create the currency for"),
    service: CurrencyService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> CurrencyResponse:
    """
    Create a new currency configuration for a venue.

    If is_base is True, any existing base currency for the venue will
    be demoted (is_base set to False). The base currency's exchange
    rate is always set to 1.0.

    Args:
        data: CurrencyCreate schema with currency details.
        venue_id: UUID of the venue to create the currency for.
        service: Injected CurrencyService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        The newly created CurrencyResponse.

    Raises:
        HTTPException 409: If a currency with the same code already exists
            for this venue.
    """
    currency = await service.create_currency(
        venue_id=venue_id,
        code=data.code,
        name=data.name,
        symbol=data.symbol,
        decimal_places=data.decimal_places,
        exchange_rate=data.exchange_rate,
        is_base=data.is_base,
    )
    return CurrencyResponse.model_validate(currency)


# ---------------------------------------------------------------------------
# GET /pos/currencies/{currency_id} — get a currency by ID
# ---------------------------------------------------------------------------
@router.get(
    "/{currency_id}",
    response_model=CurrencyResponse,
    summary="Get a currency by ID",
)
async def get_currency(
    currency_id: UUID,
    service: CurrencyService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> CurrencyResponse:
    """
    Retrieve a currency by its unique identifier.

    Args:
        currency_id: UUID of the currency to retrieve.
        service: Injected CurrencyService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        The CurrencyResponse for the requested currency.

    Raises:
        HTTPException 404: If the currency is not found.
    """
    currency = await service.get_currency(currency_id)
    return CurrencyResponse.model_validate(currency)


# ---------------------------------------------------------------------------
# GET /pos/currencies — list currencies for a venue
# ---------------------------------------------------------------------------
@router.get(
    "/",
    response_model=List[CurrencyResponse],
    summary="List currencies for a venue",
)
async def list_currencies(
    venue_id: UUID = Query(..., description="Venue to list currencies for"),
    active_only: bool = Query(
        True,
        description="If True, only return active currencies"
    ),
    service: CurrencyService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> List[CurrencyResponse]:
    """
    List all currencies for a venue.

    Returns currencies ordered with the base currency first, then
    alphabetically by code.

    Args:
        venue_id: UUID of the venue to list currencies for.
        active_only: If True, only return active currencies. Defaults to True.
        service: Injected CurrencyService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        List of CurrencyResponse objects for the venue.
    """
    currencies = await service.list_currencies(venue_id, active_only)
    return [CurrencyResponse.model_validate(c) for c in currencies]


# ---------------------------------------------------------------------------
# GET /pos/currencies/base — get the base currency for a venue
# ---------------------------------------------------------------------------
@router.get(
    "/base",
    response_model=CurrencyResponse,
    summary="Get the base currency for a venue",
)
async def get_base_currency(
    venue_id: UUID = Query(..., description="Venue to get base currency for"),
    service: CurrencyService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> CurrencyResponse:
    """
    Get the base currency for a venue.

    The base currency is the reference currency for all exchange rate
    calculations. Each venue must have exactly one base currency.

    Args:
        venue_id: UUID of the venue to get the base currency for.
        service: Injected CurrencyService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        The base CurrencyResponse for the venue.

    Raises:
        HTTPException 400: If no base currency is configured for the venue.
    """
    currency = await service.get_base_currency(venue_id)
    return CurrencyResponse.model_validate(currency)


# ---------------------------------------------------------------------------
# PATCH /pos/currencies/{currency_id}/rate — update exchange rate
# ---------------------------------------------------------------------------
@router.patch(
    "/{currency_id}/rate",
    response_model=CurrencyResponse,
    summary="Update currency exchange rate",
)
async def update_exchange_rate(
    currency_id: UUID,
    new_rate: Decimal = Query(
        ...,
        gt=0,
        description="The new exchange rate to the base currency"
    ),
    service: CurrencyService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> CurrencyResponse:
    """
    Update the exchange rate for a currency.

    Cannot update the exchange rate of a base currency (which is always 1.0).
    Exchange rates represent the conversion rate to the venue's base currency.

    Args:
        currency_id: UUID of the currency to update.
        new_rate: The new exchange rate to the base currency (must be positive).
        service: Injected CurrencyService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        The updated CurrencyResponse with the new exchange rate.

    Raises:
        HTTPException 404: If the currency is not found.
        HTTPException 400: If attempting to update a base currency's rate.
    """
    currency = await service.update_exchange_rate(currency_id, new_rate)
    return CurrencyResponse.model_validate(currency)


# ---------------------------------------------------------------------------
# POST /pos/currencies/convert — convert amount between currencies
# ---------------------------------------------------------------------------
@router.post(
    "/convert",
    response_model=CurrencyConversionResponse,
    summary="Convert amount between currencies",
)
async def convert_currency(
    data: CurrencyConversionRequest,
    venue_id: UUID = Query(..., description="Venue for currency conversion"),
    service: CurrencyService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> CurrencyConversionResponse:
    """
    Convert an amount from one currency to another.

    Conversion is performed through the base currency:
    1. Convert from source currency to base currency
    2. Convert from base currency to target currency

    The response includes both the converted amount and formatted strings
    with currency symbols.

    Args:
        data: CurrencyConversionRequest with amount and currency codes.
        venue_id: UUID of the venue for the conversion.
        service: Injected CurrencyService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        CurrencyConversionResponse with converted amount and formatting.

    Raises:
        HTTPException 404: If either currency is not found.
        HTTPException 400: If conversion fails (e.g., inactive currency).
    """
    return await service.convert_and_format(venue_id, data)
