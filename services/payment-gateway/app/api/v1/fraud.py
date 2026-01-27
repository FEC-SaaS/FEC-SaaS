"""
=============================================================================
FILE: api/v1/fraud.py
PURPOSE: Fraud detection and management API endpoints
=============================================================================
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user, VenueAccessChecker
from app.models.payment import FraudAlertStatus
from app.schemas.payment import (
    FraudRuleCreate,
    FraudRuleUpdate,
    FraudRuleResponse,
    FraudAlertResponse,
    FraudAlertReview,
    FraudAlertListResponse,
    PaginationParams,
)
from app.services import FraudService, EventPublisher, EventType

router = APIRouter(prefix="/fraud", tags=["Fraud Detection"])


# =============================================================================
# FRAUD RULES
# =============================================================================

@router.post(
    "/rules",
    response_model=FraudRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a fraud detection rule",
)
async def create_fraud_rule(
    data: FraudRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new fraud detection rule.

    Rules can be global (venue_id=null) or venue-specific.

    Rule types:
    - **velocity**: Transaction count/amount limits per time window
    - **amount_threshold**: Min/max transaction amounts
    - **geo_location**: Country-based restrictions
    - **card_bin**: Card BIN blacklisting
    - **device_fingerprint**: Device tracking
    - **ip_address**: IP-based restrictions
    - **custom**: Custom rule logic
    """
    # Only admins can create global rules
    if data.venue_id is None and current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for global rules",
        )

    service = FraudService(db)

    try:
        return await service.create_rule(data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/rules",
    response_model=List[FraudRuleResponse],
    summary="List fraud detection rules",
)
async def list_fraud_rules(
    venue_id: Optional[UUID] = None,
    include_global: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List fraud detection rules for a venue and/or global rules."""
    service = FraudService(db)

    return await service.list_rules(
        venue_id=venue_id,
        include_global=include_global,
    )


@router.get(
    "/rules/{rule_id}",
    response_model=FraudRuleResponse,
    summary="Get a fraud rule",
)
async def get_fraud_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get details of a specific fraud rule."""
    service = FraudService(db)

    rules = await service.list_rules()
    for rule in rules:
        if rule.id == rule_id:
            return rule

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")


@router.patch(
    "/rules/{rule_id}",
    response_model=FraudRuleResponse,
    summary="Update a fraud rule",
)
async def update_fraud_rule(
    rule_id: UUID,
    data: FraudRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a fraud detection rule."""
    service = FraudService(db)

    try:
        return await service.update_rule(rule_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a fraud rule",
)
async def delete_fraud_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a fraud detection rule."""
    service = FraudService(db)
    await service.delete_rule(rule_id)


# =============================================================================
# FRAUD ALERTS
# =============================================================================

@router.get(
    "/alerts",
    response_model=FraudAlertListResponse,
    summary="List fraud alerts",
)
async def list_fraud_alerts(
    venue_id: Optional[UUID] = None,
    status: Optional[FraudAlertStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List fraud alerts with filters and pagination."""
    # Require admin for cross-venue queries
    if venue_id is None and current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for cross-venue queries",
        )

    service = FraudService(db)

    params = PaginationParams(
        page=page,
        page_size=page_size,
    )

    return await service.list_alerts(
        venue_id=venue_id,
        status=status,
        params=params,
    )


@router.get(
    "/alerts/{alert_id}",
    response_model=FraudAlertResponse,
    summary="Get a fraud alert",
)
async def get_fraud_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get details of a specific fraud alert."""
    service = FraudService(db)

    # Get alerts and find the one we need
    alerts = await service.list_alerts(params=PaginationParams(page_size=1000))
    for alert in alerts.alerts:
        if alert.id == alert_id:
            return alert

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")


@router.post(
    "/alerts/{alert_id}/review",
    response_model=FraudAlertResponse,
    summary="Review a fraud alert",
)
async def review_fraud_alert(
    alert_id: UUID,
    review: FraudAlertReview,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Review and take action on a fraud alert.

    Actions:
    - **approved**: Transaction is legitimate, allow future similar transactions
    - **rejected**: Confirm fraud, block customer/payment method
    - **escalated**: Requires further investigation
    """
    service = FraudService(db)
    event_pub = EventPublisher()

    try:
        result = await service.review_alert(
            alert_id=alert_id,
            review=review,
            reviewer_id=UUID(current_user["user_id"]),
        )

        await event_pub.publish(
            EventType.FRAUD_ALERT_REVIEWED,
            payload={
                "alert_id": alert_id,
                "action": review.action.value,
                "reviewer_id": current_user["user_id"],
            },
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/alerts/pending/count",
    summary="Get pending alerts count",
)
async def get_pending_alerts_count(
    venue_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get count of pending fraud alerts."""
    service = FraudService(db)

    result = await service.list_alerts(
        venue_id=venue_id,
        status=FraudAlertStatus.PENDING,
        params=PaginationParams(page_size=1),
    )

    return {"pending_count": result.total}
