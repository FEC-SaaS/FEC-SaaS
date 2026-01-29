"""
POS Discount API routes.

This module provides RESTful API endpoints for managing discounts and promotional
codes within the POS system. It supports full CRUD operations for discounts,
code validation, and discount application calculations.

Endpoints:
    POST   /pos/discounts           - Create a new discount
    GET    /pos/discounts           - List discounts for a venue
    GET    /pos/discounts/{id}      - Get discount by ID
    GET    /pos/discounts/code/{code} - Get discount by code
    PATCH  /pos/discounts/{id}      - Update a discount
    POST   /pos/discounts/{id}/deactivate - Deactivate a discount
    POST   /pos/discounts/validate  - Validate a discount code

All endpoints require authentication via JWT bearer token.
"""

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.pos import (
    DiscountCreate,
    DiscountResponse,
    DiscountUpdate,
)
from app.services.discount_service import DiscountService
from app.services.event_publisher import event_publisher

logger = structlog.get_logger(__name__)

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> DiscountService:
    """
    Dependency injection factory for DiscountService.

    Creates a new DiscountService instance with the provided database session
    and the global event publisher for broadcasting discount-related events.

    Args:
        db: SQLAlchemy async session injected by FastAPI's dependency system.

    Returns:
        A configured DiscountService instance ready for use.
    """
    return DiscountService(db, event_publisher)


# ---------------------------------------------------------------------------
# POST /pos/discounts - Create a new discount
# ---------------------------------------------------------------------------
@router.post(
    "/pos/discounts",
    response_model=DiscountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new discount",
    responses={
        201: {"description": "Discount created successfully"},
        400: {"description": "Invalid request data"},
        401: {"description": "Authentication required"},
        409: {"description": "Discount code already exists for this venue"},
    },
)
async def create_discount(
    data: DiscountCreate,
    venue_id: UUID = Query(
        ...,
        description="UUID of the venue creating the discount",
    ),
    service: DiscountService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> DiscountResponse:
    """
    Create a new discount configuration for a venue.

    Creates a discount with the specified parameters including discount type,
    value, validity period, and usage limits. If a discount code is provided,
    it must be unique within the venue.

    Supported discount types:
        - PERCENTAGE: Percentage off the subtotal (e.g., 10% off)
        - FIXED_AMOUNT: Fixed dollar amount off (e.g., $5 off)
        - BOGO: Buy one get one (typically 50% off)
        - MEMBER_DISCOUNT: Special discount for members
        - PROMO_CODE: Promotional code (can be percentage or fixed)

    Args:
        data: DiscountCreate schema containing discount configuration.
        venue_id: UUID of the venue creating the discount.
        service: Injected DiscountService instance.
        current_user: Authenticated user information from JWT token.

    Returns:
        DiscountResponse containing the newly created discount details.

    Raises:
        HTTPException 409: If a discount with the same code already exists.
    """
    logger.info(
        "create_discount_request",
        venue_id=str(venue_id),
        discount_name=data.name,
        discount_type=data.discount_type.value if data.discount_type else None,
        code=data.code,
        user_id=str(current_user.get("user_id")),
    )

    discount = await service.create_discount(venue_id, data)

    logger.info(
        "create_discount_success",
        discount_id=str(discount.id),
        venue_id=str(venue_id),
    )

    return DiscountResponse.model_validate(discount)


# ---------------------------------------------------------------------------
# GET /pos/discounts/{discount_id} - Get discount by ID
# ---------------------------------------------------------------------------
@router.get(
    "/pos/discounts/{discount_id}",
    response_model=DiscountResponse,
    summary="Get discount by ID",
    responses={
        200: {"description": "Discount retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Discount not found"},
    },
)
async def get_discount(
    discount_id: UUID = Path(
        ...,
        description="UUID of the discount to retrieve",
    ),
    service: DiscountService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> DiscountResponse:
    """
    Retrieve a discount by its unique identifier.

    Fetches the complete discount configuration including current usage
    statistics and active status.

    Args:
        discount_id: UUID of the discount to retrieve.
        service: Injected DiscountService instance.
        current_user: Authenticated user information from JWT token.

    Returns:
        DiscountResponse containing the discount details.

    Raises:
        HTTPException 404: If no discount exists with the given ID.
    """
    logger.info(
        "get_discount_request",
        discount_id=str(discount_id),
        user_id=str(current_user.get("user_id")),
    )

    discount = await service.get_discount(discount_id)

    return DiscountResponse.model_validate(discount)


# ---------------------------------------------------------------------------
# GET /pos/discounts - List discounts for a venue
# ---------------------------------------------------------------------------
@router.get(
    "/pos/discounts",
    response_model=List[DiscountResponse],
    summary="List discounts for a venue",
    responses={
        200: {"description": "Discounts retrieved successfully"},
        401: {"description": "Authentication required"},
    },
)
async def list_discounts(
    venue_id: UUID = Query(
        ...,
        description="UUID of the venue to list discounts for",
    ),
    active_only: bool = Query(
        True,
        description="If true, only return active discounts",
    ),
    skip: int = Query(
        0,
        ge=0,
        description="Number of records to skip for pagination",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=100,
        description="Maximum number of records to return (1-100)",
    ),
    service: DiscountService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> List[DiscountResponse]:
    """
    List all discounts configured for a venue.

    Returns a paginated list of discounts, optionally filtered to show only
    active discounts. Results are ordered by creation date (newest first).

    Args:
        venue_id: UUID of the venue to list discounts for.
        active_only: If True, only return active discounts (default: True).
        skip: Number of records to skip for pagination (default: 0).
        limit: Maximum number of records to return, between 1-100 (default: 50).
        service: Injected DiscountService instance.
        current_user: Authenticated user information from JWT token.

    Returns:
        List of DiscountResponse objects matching the filter criteria.
    """
    logger.info(
        "list_discounts_request",
        venue_id=str(venue_id),
        active_only=active_only,
        skip=skip,
        limit=limit,
        user_id=str(current_user.get("user_id")),
    )

    discounts = await service.list_discounts(
        venue_id=venue_id,
        active_only=active_only,
        skip=skip,
        limit=limit,
    )

    logger.info(
        "list_discounts_success",
        venue_id=str(venue_id),
        count=len(discounts),
    )

    return [DiscountResponse.model_validate(d) for d in discounts]


# ---------------------------------------------------------------------------
# GET /pos/discounts/code/{code} - Get discount by code
# ---------------------------------------------------------------------------
@router.get(
    "/pos/discounts/code/{code}",
    response_model=DiscountResponse,
    summary="Get discount by code",
    responses={
        200: {"description": "Discount retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Discount code not found"},
    },
)
async def get_discount_by_code(
    code: str = Path(
        ...,
        description="Discount code to look up",
        min_length=1,
        max_length=50,
    ),
    venue_id: UUID = Query(
        ...,
        description="UUID of the venue to search within",
    ),
    service: DiscountService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> DiscountResponse:
    """
    Retrieve a discount by its code within a specific venue.

    Looks up a discount using its promotional code. Discount codes are
    case-sensitive and unique within a venue but may be reused across
    different venues.

    Args:
        code: The discount code to look up.
        venue_id: UUID of the venue to search within.
        service: Injected DiscountService instance.
        current_user: Authenticated user information from JWT token.

    Returns:
        DiscountResponse containing the discount details.

    Raises:
        HTTPException 404: If no discount exists with the given code in the venue.
    """
    logger.info(
        "get_discount_by_code_request",
        venue_id=str(venue_id),
        code=code,
        user_id=str(current_user.get("user_id")),
    )

    discount = await service.get_discount_by_code(venue_id, code)

    return DiscountResponse.model_validate(discount)


# ---------------------------------------------------------------------------
# PATCH /pos/discounts/{discount_id} - Update a discount
# ---------------------------------------------------------------------------
@router.patch(
    "/pos/discounts/{discount_id}",
    response_model=DiscountResponse,
    summary="Update a discount",
    responses={
        200: {"description": "Discount updated successfully"},
        400: {"description": "Invalid request data"},
        401: {"description": "Authentication required"},
        404: {"description": "Discount not found"},
        409: {"description": "Discount code already exists for this venue"},
    },
)
async def update_discount(
    data: DiscountUpdate,
    discount_id: UUID = Path(
        ...,
        description="UUID of the discount to update",
    ),
    service: DiscountService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> DiscountResponse:
    """
    Update an existing discount configuration.

    Allows partial updates to a discount. Only the fields provided in the
    request body will be modified; all other fields remain unchanged.

    If updating the discount code, it must be unique within the venue.
    Updates to usage limits do not affect the current usage count.

    Args:
        data: DiscountUpdate schema with fields to update.
        discount_id: UUID of the discount to update.
        service: Injected DiscountService instance.
        current_user: Authenticated user information from JWT token.

    Returns:
        DiscountResponse containing the updated discount details.

    Raises:
        HTTPException 404: If no discount exists with the given ID.
        HTTPException 409: If updating code to one that already exists.
    """
    logger.info(
        "update_discount_request",
        discount_id=str(discount_id),
        update_fields=list(data.model_dump(exclude_unset=True).keys()),
        user_id=str(current_user.get("user_id")),
    )

    discount = await service.update_discount(discount_id, data)

    logger.info(
        "update_discount_success",
        discount_id=str(discount_id),
        venue_id=str(discount.venue_id),
    )

    return DiscountResponse.model_validate(discount)


# ---------------------------------------------------------------------------
# POST /pos/discounts/{discount_id}/deactivate - Deactivate a discount
# ---------------------------------------------------------------------------
@router.post(
    "/pos/discounts/{discount_id}/deactivate",
    response_model=DiscountResponse,
    summary="Deactivate a discount",
    responses={
        200: {"description": "Discount deactivated successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Discount not found"},
    },
)
async def deactivate_discount(
    discount_id: UUID = Path(
        ...,
        description="UUID of the discount to deactivate",
    ),
    service: DiscountService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> DiscountResponse:
    """
    Deactivate a discount, preventing further use.

    Sets the discount's active status to False. Deactivated discounts cannot
    be used in new transactions but remain in the system for historical
    reporting purposes.

    This operation is idempotent - deactivating an already inactive discount
    will succeed without error.

    Args:
        discount_id: UUID of the discount to deactivate.
        service: Injected DiscountService instance.
        current_user: Authenticated user information from JWT token.

    Returns:
        DiscountResponse containing the deactivated discount details.

    Raises:
        HTTPException 404: If no discount exists with the given ID.
    """
    logger.info(
        "deactivate_discount_request",
        discount_id=str(discount_id),
        user_id=str(current_user.get("user_id")),
    )

    discount = await service.deactivate_discount(discount_id)

    logger.info(
        "deactivate_discount_success",
        discount_id=str(discount_id),
        venue_id=str(discount.venue_id),
    )

    return DiscountResponse.model_validate(discount)


# ---------------------------------------------------------------------------
# POST /pos/discounts/validate - Validate a discount code
# ---------------------------------------------------------------------------
@router.post(
    "/pos/discounts/validate",
    summary="Validate a discount code",
    responses={
        200: {"description": "Validation result returned"},
        401: {"description": "Authentication required"},
    },
)
async def validate_discount(
    venue_id: UUID = Query(
        ...,
        description="UUID of the venue to validate the discount for",
    ),
    code: str = Query(
        ...,
        description="Discount code to validate",
        min_length=1,
        max_length=50,
    ),
    subtotal: Decimal = Query(
        ...,
        description="Transaction subtotal for minimum purchase validation",
        gt=0,
    ),
    is_member: bool = Query(
        False,
        description="Whether the customer is a member (for member-only discounts)",
    ),
    service: DiscountService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Validate a discount code and calculate the discount amount.

    Performs comprehensive validation of a discount code including:
        - Code existence within the venue
        - Active status check
        - Validity period (start_date and end_date)
        - Maximum usage limit
        - Minimum purchase requirement
        - Member requirement

    If the discount is valid, calculates and returns the discount amount
    based on the provided subtotal.

    Args:
        venue_id: UUID of the venue to validate the discount for.
        code: The discount code to validate.
        subtotal: The transaction subtotal to validate against minimum
            purchase requirements and to calculate the discount amount.
        is_member: Whether the customer is a member (default: False).
        service: Injected DiscountService instance.
        current_user: Authenticated user information from JWT token.

    Returns:
        Dictionary containing validation results:
            - valid (bool): Whether the discount code is valid
            - message (str): Human-readable validation result message
            - discount_id (UUID | None): ID of the discount if valid
            - discount_type (str | None): Type of discount if valid
            - discount_value (Decimal | None): Configured discount value if valid
            - discount_amount (Decimal | None): Calculated discount amount if valid

    Example Response (valid):
        {
            "valid": true,
            "message": "Discount is valid",
            "discount_id": "550e8400-e29b-41d4-a716-446655440000",
            "discount_type": "percentage",
            "discount_value": "10.00",
            "discount_amount": "5.00"
        }

    Example Response (invalid):
        {
            "valid": false,
            "message": "This discount has expired",
            "discount_id": null,
            "discount_type": null,
            "discount_value": null,
            "discount_amount": null
        }
    """
    logger.info(
        "validate_discount_request",
        venue_id=str(venue_id),
        code=code,
        subtotal=str(subtotal),
        is_member=is_member,
        user_id=str(current_user.get("user_id")),
    )

    is_valid, message, discount = await service.validate_discount(
        venue_id=venue_id,
        code=code,
        subtotal=subtotal,
        is_member=is_member,
    )

    # Calculate discount amount if valid
    discount_amount = None
    if is_valid and discount:
        discount_amount = await service.apply_discount(discount, subtotal)

    logger.info(
        "validate_discount_result",
        venue_id=str(venue_id),
        code=code,
        is_valid=is_valid,
        discount_amount=str(discount_amount) if discount_amount else None,
    )

    return {
        "valid": is_valid,
        "message": message,
        "discount_id": str(discount.id) if discount else None,
        "discount_type": discount.discount_type if discount else None,
        "discount_value": str(discount.value) if discount else None,
        "discount_amount": str(discount_amount) if discount_amount else None,
    }
