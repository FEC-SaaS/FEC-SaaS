"""
=============================================================================
FILE: api/v1/disputes.py
PURPOSE: Payment dispute management API endpoints
=============================================================================
"""

from datetime import date
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user, VenueAccessChecker
from app.models.payment import DisputeStatus
from app.schemas.payment import (
    DisputeResponse,
    DisputeEvidenceSubmit,
    DisputeListResponse,
    PaginationParams,
)
from app.services import DisputeService, EventPublisher, EventType

router = APIRouter(prefix="/disputes", tags=["Disputes"])


@router.get(
    "/",
    response_model=DisputeListResponse,
    summary="List disputes",
)
async def list_disputes(
    venue_id: UUID,
    status: Optional[DisputeStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(VenueAccessChecker()),
):
    """List disputes for a venue with filters and pagination."""
    service = DisputeService(db)

    params = PaginationParams(
        page=page,
        page_size=page_size,
    )

    return await service.list_disputes(
        venue_id=venue_id,
        status=status,
        params=params,
    )


@router.get(
    "/{dispute_id}",
    response_model=DisputeResponse,
    summary="Get dispute details",
)
async def get_dispute(
    dispute_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get details of a specific dispute."""
    service = DisputeService(db)

    try:
        return await service.get_dispute(dispute_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{dispute_id}/evidence",
    response_model=DisputeResponse,
    summary="Submit dispute evidence",
)
async def submit_dispute_evidence(
    dispute_id: UUID,
    data: DisputeEvidenceSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Submit evidence to contest a dispute.

    Evidence types:
    - **receipt**: Transaction receipt or invoice
    - **shipping_documentation**: Proof of delivery
    - **service_documentation**: Proof of service provided
    - **customer_signature**: Signed agreement or receipt
    - **customer_communication**: Email/chat communication
    - **refund_policy**: Terms and refund policy
    - **other**: Any other relevant documentation
    """
    service = DisputeService(db)
    event_pub = EventPublisher()

    try:
        result = await service.submit_evidence(
            dispute_id=dispute_id,
            data=data,
            user_id=UUID(current_user["user_id"]),
        )

        # Get the dispute for venue_id
        dispute = await service.get_dispute(dispute_id)
        await event_pub.publish(
            EventType.DISPUTE_EVIDENCE_SUBMITTED,
            payload={
                "dispute_id": dispute_id,
                "evidence_type": data.evidence_type,
            },
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{dispute_id}/accept",
    response_model=DisputeResponse,
    summary="Accept dispute",
)
async def accept_dispute(
    dispute_id: UUID,
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Accept a dispute and concede to the customer.

    This will result in a loss and the disputed amount will be debited.
    """
    service = DisputeService(db)
    event_pub = EventPublisher()

    try:
        result = await service.accept_dispute(
            dispute_id=dispute_id,
            notes=notes,
        )

        await event_pub.publish(
            EventType.DISPUTE_LOST,
            payload={
                "dispute_id": dispute_id,
                "accepted": True,
            },
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/metrics",
    response_model=Dict[str, Any],
    summary="Get dispute metrics",
)
async def get_dispute_metrics(
    venue_id: UUID,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(VenueAccessChecker()),
):
    """Get dispute metrics and statistics for a venue."""
    service = DisputeService(db)

    return await service.get_dispute_metrics(
        venue_id=venue_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/open/count",
    summary="Get open disputes count",
)
async def get_open_disputes_count(
    venue_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(VenueAccessChecker()),
):
    """Get count of open disputes requiring attention."""
    service = DisputeService(db)

    result = await service.list_disputes(
        venue_id=venue_id,
        status=DisputeStatus.OPEN,
        params=PaginationParams(page_size=1),
    )

    return {"open_count": result.total}
