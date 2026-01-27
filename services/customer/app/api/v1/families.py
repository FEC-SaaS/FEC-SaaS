"""
=============================================================================
FILE: api/v1/families.py
PURPOSE: Family management API endpoints
=============================================================================
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user
from app.services.family_service import FamilyService
from app.schemas.customer import (
    FamilyCreate,
    FamilyUpdate,
    FamilyResponse,
    FamilyMemberCreate,
    FamilyMemberResponse,
)

# OpenAPI Tags
TAGS = ["Families"]

router = APIRouter(tags=TAGS)


@router.get(
    "/",
    summary="List families",
    description="""
    Retrieve a list of families for a venue.

    Families allow grouping related customers together (e.g., parents with children).
    This enables:
    - **Family billing**: Combined receipts and statements
    - **Group bookings**: Reserve activities for the whole family
    - **Marketing**: Target families with relevant promotions
    """,
    responses={
        200: {"description": "List of families"},
        401: {"description": "Unauthorized - Invalid or missing authentication"},
    },
)
async def list_families(
    venue_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List families for a venue."""
    service = FamilyService(db)
    families = await service.list_families(venue_id, limit, offset)
    return [FamilyResponse.model_validate(f) for f in families]


@router.post(
    "/",
    response_model=FamilyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new family",
    description="""
    Create a new family group.

    **Required fields:**
    - venue_id: The venue this family belongs to
    - family_name: Display name for the family group

    **Optional:**
    - primary_contact_id: Customer ID of the primary contact (usually a parent/adult)
    - notes: Additional notes about the family

    After creation, add members using the `/families/{family_id}/members` endpoint.
    """,
    responses={
        201: {"description": "Family created successfully"},
        401: {"description": "Unauthorized"},
        422: {"description": "Validation error"},
    },
)
async def create_family(
    family_data: FamilyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new family."""
    service = FamilyService(db)
    family = await service.create_family(family_data)
    return FamilyResponse.model_validate(family)


@router.get(
    "/{family_id}",
    response_model=FamilyResponse,
    summary="Get family details",
    description="""
    Retrieve detailed information about a family including all members.

    Returns:
    - Family metadata (name, primary contact, notes)
    - List of all family members with their relationships
    """,
    responses={
        200: {"description": "Family details"},
        404: {"description": "Family not found"},
    },
)
async def get_family(
    family_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get family details by ID."""
    service = FamilyService(db)
    family = await service.get_family(family_id)

    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found",
        )

    return FamilyResponse.model_validate(family)


@router.put(
    "/{family_id}",
    response_model=FamilyResponse,
    summary="Update family",
    description="""
    Update family information such as name, primary contact, or notes.

    Only provided fields will be updated.
    """,
    responses={
        200: {"description": "Family updated successfully"},
        404: {"description": "Family not found"},
        422: {"description": "Validation error"},
    },
)
async def update_family(
    family_id: UUID,
    update_data: FamilyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update family information."""
    service = FamilyService(db)
    family = await service.update_family(family_id, update_data)

    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found",
        )

    return FamilyResponse.model_validate(family)


@router.delete(
    "/{family_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete family",
    description="""
    Delete a family group.

    **Note**: This removes the family association but does NOT delete the customer records.
    Individual customers will remain in the system.
    """,
    responses={
        204: {"description": "Family deleted successfully"},
        404: {"description": "Family not found"},
    },
)
async def delete_family(
    family_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a family."""
    service = FamilyService(db)
    deleted = await service.delete_family(family_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found",
        )


@router.post(
    "/{family_id}/members",
    response_model=FamilyMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add family member",
    description="""
    Add an existing customer as a member of a family.

    **Required:**
    - customer_id: The customer to add to the family

    **Optional:**
    - relation_type: The relationship type (PARENT, CHILD, SPOUSE, SIBLING, GUARDIAN, OTHER)
    - is_primary_contact: Whether this member is the primary contact

    **Note**: A customer can only belong to one family at a time.
    """,
    responses={
        201: {"description": "Member added successfully"},
        400: {"description": "Could not add member (e.g., already in another family)"},
        404: {"description": "Family or customer not found"},
    },
)
async def add_family_member(
    family_id: UUID,
    member_data: FamilyMemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add a member to a family."""
    service = FamilyService(db)
    member = await service.add_family_member(family_id, member_data)

    if not member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not add member to family",
        )

    return FamilyMemberResponse.model_validate(member)


@router.delete(
    "/{family_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove family member",
    description="""
    Remove a customer from a family.

    **Note**: This removes the family association but does NOT delete the customer record.
    The customer will remain in the system as an individual.
    """,
    responses={
        204: {"description": "Member removed successfully"},
        404: {"description": "Family member not found"},
    },
)
async def remove_family_member(
    family_id: UUID,
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Remove a member from a family."""
    service = FamilyService(db)
    removed = await service.remove_family_member(family_id, member_id)

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family member not found",
        )
