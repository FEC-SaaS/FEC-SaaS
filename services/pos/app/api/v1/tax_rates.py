"""Tax rate API routes for the POS service."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.pos import (
    TaxCalculationRequest,
    TaxCalculationResponse,
    TaxRateCreate,
    TaxRateResponse,
    TaxRateUpdate,
)
from app.services.tax_service import TaxService

router = APIRouter()
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> TaxService:
    return TaxService(db)


# ---------------------------------------------------------------------------
# GET /pos/tax-rates — list tax rates
# ---------------------------------------------------------------------------
@router.get(
    "/pos/tax-rates",
    response_model=List[TaxRateResponse],
    summary="List tax rates",
)
async def list_tax_rates(
    venue_id: UUID = Query(..., description="Venue to list tax rates for"),
    tax_type: Optional[str] = Query(None, description="Filter by tax type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    service: TaxService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> List[TaxRateResponse]:
    """Return all tax rates for a venue, optionally filtered by type and active status."""
    rates = await service.list_tax_rates(
        venue_id=venue_id,
        tax_type=tax_type,
        is_active=is_active,
    )
    return [TaxRateResponse.model_validate(r) for r in rates]


# ---------------------------------------------------------------------------
# POST /pos/tax-rates — create a tax rate
# ---------------------------------------------------------------------------
@router.post(
    "/pos/tax-rates",
    response_model=TaxRateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tax rate",
)
async def create_tax_rate(
    body: TaxRateCreate,
    venue_id: UUID = Query(..., description="Venue to create the tax rate for"),
    service: TaxService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> TaxRateResponse:
    """Create a new tax rate configuration for a venue."""
    rate = await service.create_tax_rate(venue_id, body)
    return TaxRateResponse.model_validate(rate)


# ---------------------------------------------------------------------------
# GET /pos/tax-rates/{tax_rate_id} — get a tax rate
# ---------------------------------------------------------------------------
@router.get(
    "/pos/tax-rates/{tax_rate_id}",
    response_model=TaxRateResponse,
    summary="Get tax rate details",
)
async def get_tax_rate(
    tax_rate_id: UUID,
    service: TaxService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> TaxRateResponse:
    """Retrieve a single tax rate by its ID."""
    rate = await service.get_tax_rate(tax_rate_id)
    if not rate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tax rate not found",
        )
    return TaxRateResponse.model_validate(rate)


# ---------------------------------------------------------------------------
# PUT /pos/tax-rates/{tax_rate_id} — update a tax rate
# ---------------------------------------------------------------------------
@router.put(
    "/pos/tax-rates/{tax_rate_id}",
    response_model=TaxRateResponse,
    summary="Update a tax rate",
)
async def update_tax_rate(
    tax_rate_id: UUID,
    body: TaxRateUpdate,
    service: TaxService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> TaxRateResponse:
    """Update an existing tax rate configuration."""
    rate = await service.update_tax_rate(tax_rate_id, body)
    if not rate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tax rate not found",
        )
    return TaxRateResponse.model_validate(rate)


# ---------------------------------------------------------------------------
# POST /pos/calculate-tax — calculate tax for a transaction
# ---------------------------------------------------------------------------
@router.post(
    "/pos/calculate-tax",
    response_model=TaxCalculationResponse,
    summary="Calculate tax",
)
async def calculate_tax(
    body: TaxCalculationRequest,
    venue_id: UUID = Query(..., description="Venue to calculate tax for"),
    service: TaxService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> TaxCalculationResponse:
    """Calculate applicable taxes for a given transaction type and subtotal."""
    result = await service.calculate_tax(venue_id, body)
    return TaxCalculationResponse.model_validate(result)
