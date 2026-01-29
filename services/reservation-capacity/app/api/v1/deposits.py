"""Deposit management API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.reservation import DepositCollectRequest, DepositResponse
from app.services.deposit_service import DepositService

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> DepositService:
    return DepositService(db)


@router.post(
    "/reservations/{reservation_id}/deposit/collect",
    response_model=DepositResponse,
)
async def collect_deposit(
    reservation_id: UUID,
    data: DepositCollectRequest,
    current_user: dict = Depends(get_current_user),
    service: DepositService = Depends(_get_service),
):
    """Collect deposit for a reservation via the payment service."""
    result = await service.collect_deposit(
        reservation_id=reservation_id,
        amount=data.amount,
        customer_id=data.customer_id,
        payment_method_id=data.payment_method_id,
    )
    return result


@router.post(
    "/reservations/{reservation_id}/deposit/refund",
    response_model=DepositResponse,
)
async def refund_deposit(
    reservation_id: UUID,
    reason: str = Query("customer_request"),
    current_user: dict = Depends(get_current_user),
    service: DepositService = Depends(_get_service),
):
    """Refund a collected deposit."""
    return await service.refund_deposit(reservation_id, reason=reason)


@router.post(
    "/reservations/{reservation_id}/deposit/forfeit",
    response_model=DepositResponse,
)
async def forfeit_deposit(
    reservation_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: DepositService = Depends(_get_service),
):
    """Forfeit a deposit (e.g., for no-shows)."""
    return await service.forfeit_deposit(reservation_id)
