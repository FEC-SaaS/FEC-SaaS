"""
=============================================================================
FILE: api/v1/loyalty.py
PURPOSE: Loyalty points program API endpoints
=============================================================================
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, require_venue_access
from app.services import LoyaltyService
from app.services.event_publisher import event_publisher
from app.models import LoyaltyTransactionType
from app.schemas.membership import (
    LoyaltyProgramCreate,
    LoyaltyProgramUpdate,
    LoyaltyProgramResponse,
    LoyaltyAccountResponse,
    EarnPointsRequest,
    RedeemPointsRequest,
    LoyaltyTransactionResponse,
    TierProgressResponse,
)

router = APIRouter(prefix="/loyalty", tags=["Loyalty"])


# =============================================================================
# LOYALTY PROGRAMS
# =============================================================================


@router.post("/programs", response_model=LoyaltyProgramResponse, status_code=status.HTTP_201_CREATED)
async def create_loyalty_program(
    venue_id: UUID,
    program_data: LoyaltyProgramCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new loyalty program for a venue."""
    await require_venue_access(current_user, venue_id, "admin")
    service = LoyaltyService(db)
    program = await service.create_program(venue_id, program_data)
    return program


@router.get("/programs/{program_id}", response_model=LoyaltyProgramResponse)
async def get_loyalty_program(
    program_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a loyalty program by ID."""
    service = LoyaltyService(db)
    program = await service.get_program(program_id)
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loyalty program not found",
        )
    return program


@router.get("/programs/venue/{venue_id}", response_model=LoyaltyProgramResponse)
async def get_venue_loyalty_program(
    venue_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the active loyalty program for a venue."""
    service = LoyaltyService(db)
    program = await service.get_venue_program(venue_id)
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active loyalty program found for this venue",
        )
    return program


@router.patch("/programs/{program_id}", response_model=LoyaltyProgramResponse)
async def update_loyalty_program(
    program_id: UUID,
    program_data: LoyaltyProgramUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a loyalty program."""
    service = LoyaltyService(db)
    program = await service.get_program(program_id)
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loyalty program not found",
        )
    await require_venue_access(current_user, program.venue_id, "admin")
    updated = await service.update_program(program_id, program_data)
    return updated


@router.delete("/programs/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_loyalty_program(
    program_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Deactivate a loyalty program."""
    service = LoyaltyService(db)
    program = await service.get_program(program_id)
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loyalty program not found",
        )
    await require_venue_access(current_user, program.venue_id, "admin")
    await service.deactivate_program(program_id)


# =============================================================================
# LOYALTY ACCOUNTS
# =============================================================================


@router.post("/accounts/enroll", response_model=LoyaltyAccountResponse)
async def enroll_in_loyalty_program(
    program_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Enroll the current customer in a loyalty program."""
    service = LoyaltyService(db)
    program = await service.get_program(program_id)
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loyalty program not found",
        )

    account = await service.get_or_create_account(
        customer_id=current_user["customer_id"],
        program_id=program_id,
    )
    return account


@router.get("/accounts", response_model=List[LoyaltyAccountResponse])
async def list_my_loyalty_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all loyalty accounts for the current customer."""
    service = LoyaltyService(db)
    accounts = await service.get_customer_accounts(
        customer_id=current_user["customer_id"]
    )
    return accounts


@router.get("/accounts/{account_id}", response_model=LoyaltyAccountResponse)
async def get_loyalty_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a loyalty account by ID."""
    service = LoyaltyService(db)
    account = await service.get_account(account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loyalty account not found",
        )
    if account.customer_id != current_user["customer_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this account",
        )
    return account


@router.get("/accounts/{account_id}/tier-progress", response_model=TierProgressResponse)
async def get_tier_progress(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get tier progress information for an account."""
    service = LoyaltyService(db)
    account = await service.get_account(account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loyalty account not found",
        )
    if account.customer_id != current_user["customer_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    try:
        progress = await service.get_tier_progress(account_id)
        return progress
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/accounts/{account_id}/expiring")
async def get_expiring_points(
    account_id: UUID,
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get points expiring soon for an account."""
    service = LoyaltyService(db)
    account = await service.get_account(account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loyalty account not found",
        )
    if account.customer_id != current_user["customer_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    expiring = await service.get_expiring_soon(account_id, days)
    return expiring


# =============================================================================
# POINTS TRANSACTIONS
# =============================================================================


@router.post("/accounts/{account_id}/earn", response_model=LoyaltyTransactionResponse)
async def earn_points(
    account_id: UUID,
    request: EarnPointsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Earn points to a loyalty account."""
    service = LoyaltyService(db)
    account = await service.get_account(account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loyalty account not found",
        )

    # This endpoint might be called by internal services or staff
    # Check for appropriate permissions

    try:
        transaction = await service.earn_points(account_id, request)

        # Publish event
        await event_publisher.publish_points_earned(
            account_id=account_id,
            customer_id=account.customer_id,
            points=transaction.points,
            new_balance=account.points_balance,
            source=request.reference_type,
        )

        return transaction
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/accounts/{account_id}/redeem", response_model=LoyaltyTransactionResponse)
async def redeem_points(
    account_id: UUID,
    request: RedeemPointsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Redeem points from a loyalty account."""
    service = LoyaltyService(db)
    account = await service.get_account(account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loyalty account not found",
        )
    if account.customer_id != current_user["customer_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    try:
        transaction = await service.redeem_points(account_id, request)

        # Publish event
        await event_publisher.publish_points_redeemed(
            account_id=account_id,
            customer_id=account.customer_id,
            points=abs(transaction.points),
            new_balance=account.points_balance,
            redemption_type=request.reference_type,
        )

        return transaction
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/accounts/{account_id}/adjust", response_model=LoyaltyTransactionResponse)
async def adjust_points(
    account_id: UUID,
    points: int,
    reason: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Manually adjust points (admin action)."""
    # This should require admin/staff permissions
    service = LoyaltyService(db)
    account = await service.get_account(account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loyalty account not found",
        )

    program = await service.get_program(account.program_id)
    if program:
        await require_venue_access(current_user, program.venue_id, "staff")

    try:
        transaction = await service.adjust_points(
            account_id=account_id,
            points=points,
            reason=reason,
            admin_id=current_user.get("user_id"),
        )
        return transaction
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/accounts/{from_account_id}/transfer")
async def transfer_points(
    from_account_id: UUID,
    to_account_id: UUID,
    points: int,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Transfer points between accounts."""
    service = LoyaltyService(db)

    # Verify ownership of source account
    from_account = await service.get_account(from_account_id)
    if not from_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source account not found",
        )
    if from_account.customer_id != current_user["customer_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to transfer from this account",
        )

    try:
        debit_txn, credit_txn = await service.transfer_points(
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            points=points,
            reason=reason,
        )
        return {
            "transferred": points,
            "debit_transaction_id": debit_txn.id,
            "credit_transaction_id": credit_txn.id,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/accounts/{account_id}/transactions", response_model=List[LoyaltyTransactionResponse])
async def get_transaction_history(
    account_id: UUID,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    transaction_type: Optional[LoyaltyTransactionType] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get transaction history for a loyalty account."""
    service = LoyaltyService(db)
    account = await service.get_account(account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loyalty account not found",
        )
    if account.customer_id != current_user["customer_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    transactions = await service.get_transaction_history(
        account_id=account_id,
        limit=limit,
        offset=offset,
        transaction_type=transaction_type,
    )
    return transactions
