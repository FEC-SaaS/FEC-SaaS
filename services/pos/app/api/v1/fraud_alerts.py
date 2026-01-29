"""
Fraud Alert API routes for the POS service.

This module provides REST API endpoints for managing fraud detection and
alert handling in POS operations, including:
- Retrieving and listing fraud alerts
- Updating alert status and resolution
- Assigning alerts to investigators
- Running daily fraud analysis
- Generating fraud summary reports

The fraud detection system monitors for various types of suspicious activity
including high void rates, unusual refund patterns, after-hours transactions,
large discounts, excessive complimentary transactions, cash drawer variances,
split transactions, and repeated void patterns.

All endpoints require authentication and operate within the context of a venue.
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.pos import FraudAlertSeverity, FraudAlertStatus
from app.schemas.pos import (
    FraudAlertAssign,
    FraudAlertResponse,
    FraudAlertSummaryBySeverity,
    FraudAlertSummaryByStatus,
    FraudAlertSummaryByType,
    FraudAlertUpdate,
    FraudSummary,
)
from app.services.event_publisher import event_publisher
from app.services.fraud_detection_service import FraudDetectionService

router = APIRouter(prefix="/pos/fraud-alerts")
settings = get_settings()


def _get_service(db: AsyncSession = Depends(get_db)) -> FraudDetectionService:
    """
    Dependency to get a FraudDetectionService instance.

    Args:
        db: Database session from dependency injection.

    Returns:
        Configured FraudDetectionService instance with event publisher.
    """
    return FraudDetectionService(db, event_publisher)


# ---------------------------------------------------------------------------
# GET /pos/fraud-alerts/{alert_id} — get a fraud alert by ID
# ---------------------------------------------------------------------------
@router.get(
    "/{alert_id}",
    response_model=FraudAlertResponse,
    summary="Get a fraud alert by ID",
)
async def get_fraud_alert(
    alert_id: UUID,
    service: FraudDetectionService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> FraudAlertResponse:
    """
    Retrieve a fraud alert by its unique identifier.

    Args:
        alert_id: UUID of the fraud alert to retrieve.
        service: Injected FraudDetectionService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        The FraudAlertResponse for the requested alert.

    Raises:
        HTTPException 404: If the fraud alert is not found.
    """
    alert = await service.get_alert(alert_id)
    return FraudAlertResponse.model_validate(alert)


# ---------------------------------------------------------------------------
# GET /pos/fraud-alerts — list fraud alerts for a venue
# ---------------------------------------------------------------------------
@router.get(
    "/",
    response_model=List[FraudAlertResponse],
    summary="List fraud alerts for a venue",
)
async def list_fraud_alerts(
    venue_id: UUID = Query(..., description="Venue to list fraud alerts for"),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by alert status: 'new', 'investigating', 'confirmed', 'dismissed', 'resolved'"
    ),
    severity: Optional[str] = Query(
        None,
        description="Filter by severity: 'low', 'medium', 'high', 'critical'"
    ),
    date_from: Optional[date] = Query(
        None,
        description="Filter for alerts on or after this date"
    ),
    date_to: Optional[date] = Query(
        None,
        description="Filter for alerts on or before this date"
    ),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum records to return"),
    service: FraudDetectionService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> List[FraudAlertResponse]:
    """
    List fraud alerts for a venue with optional filtering and pagination.

    Supports filtering by status, severity, and date range, with pagination
    controls. Results are ordered by creation date descending (newest first).

    Args:
        venue_id: UUID of the venue to list alerts for.
        status_filter: Optional filter by alert status.
        severity: Optional filter by alert severity.
        date_from: Optional start date filter (inclusive).
        date_to: Optional end date filter (inclusive).
        skip: Number of records to skip for pagination.
        limit: Maximum number of records to return.
        service: Injected FraudDetectionService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        List of FraudAlertResponse objects matching the criteria.
    """
    # Convert string filters to enums if provided
    status_enum = None
    if status_filter:
        try:
            status_enum = FraudAlertStatus(status_filter)
        except ValueError:
            pass  # Invalid status, will return empty or all

    severity_enum = None
    if severity:
        try:
            severity_enum = FraudAlertSeverity(severity)
        except ValueError:
            pass  # Invalid severity, will return empty or all

    alerts = await service.list_alerts(
        venue_id=venue_id,
        status=status_enum,
        severity=severity_enum,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return [FraudAlertResponse.model_validate(a) for a in alerts]


# ---------------------------------------------------------------------------
# PATCH /pos/fraud-alerts/{alert_id}/status — update alert status
# ---------------------------------------------------------------------------
@router.patch(
    "/{alert_id}/status",
    response_model=FraudAlertResponse,
    summary="Update fraud alert status",
)
async def update_alert_status(
    alert_id: UUID,
    data: FraudAlertUpdate,
    service: FraudDetectionService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> FraudAlertResponse:
    """
    Update the status of a fraud alert.

    Handles status transitions and resolution tracking. When resolving
    an alert (status = 'resolved' or 'dismissed'), the resolved_at timestamp
    and resolved_by user are recorded.

    Status transitions:
    - 'new' -> 'investigating', 'dismissed'
    - 'investigating' -> 'confirmed', 'dismissed', 'resolved'
    - 'confirmed' -> 'resolved'

    Args:
        alert_id: UUID of the alert to update.
        data: FraudAlertUpdate schema with new status and optional notes.
        service: Injected FraudDetectionService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        The updated FraudAlertResponse.

    Raises:
        HTTPException 404: If the fraud alert is not found.
    """
    alert = await service.update_alert_status(
        alert_id=alert_id,
        status=data.status,
        notes=data.notes,
        resolved_by=data.resolved_by,
    )
    return FraudAlertResponse.model_validate(alert)


# ---------------------------------------------------------------------------
# POST /pos/fraud-alerts/{alert_id}/assign — assign alert to investigator
# ---------------------------------------------------------------------------
@router.post(
    "/{alert_id}/assign",
    response_model=FraudAlertResponse,
    summary="Assign alert to an investigator",
)
async def assign_alert(
    alert_id: UUID,
    assigned_to: UUID = Query(
        ...,
        description="UUID of the user to assign the alert to"
    ),
    service: FraudDetectionService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> FraudAlertResponse:
    """
    Assign a fraud alert to a user for investigation.

    When an alert is assigned, it automatically transitions from 'new'
    to 'investigating' status if it was in 'new' status.

    Args:
        alert_id: UUID of the alert to assign.
        assigned_to: UUID of the user to assign the alert to.
        service: Injected FraudDetectionService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        The updated FraudAlertResponse with assignment.

    Raises:
        HTTPException 404: If the fraud alert is not found.
    """
    alert = await service.assign_alert(alert_id, assigned_to)
    return FraudAlertResponse.model_validate(alert)


# ---------------------------------------------------------------------------
# POST /pos/fraud-alerts/analyze/{target_date} — run daily fraud analysis
# ---------------------------------------------------------------------------
@router.post(
    "/analyze/{target_date}",
    response_model=List[FraudAlertResponse],
    summary="Run daily fraud analysis for a venue",
)
async def run_daily_analysis(
    target_date: date,
    venue_id: UUID = Query(..., description="Venue to analyze for fraud"),
    service: FraudDetectionService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> List[FraudAlertResponse]:
    """
    Run comprehensive fraud analysis for a specific date.

    Executes all fraud detection rules and generates alerts for any
    suspicious activity detected. This is typically run as a batch
    job at the end of each business day but can also be triggered
    manually for historical analysis.

    Detection checks performed:
    - High void rates by cashier
    - Unusual refund patterns
    - Excessive complimentary transactions
    - Repeated void patterns
    - Cash drawer variances
    - Split transaction detection (structuring)

    Args:
        target_date: The date to analyze for fraud.
        venue_id: UUID of the venue to analyze.
        service: Injected FraudDetectionService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        List of FraudAlertResponse for newly generated alerts.
    """
    alerts = await service.run_daily_fraud_analysis(venue_id, target_date)
    return [FraudAlertResponse.model_validate(a) for a in alerts]


# ---------------------------------------------------------------------------
# GET /pos/fraud-alerts/summary — get fraud alert summary
# ---------------------------------------------------------------------------
@router.get(
    "/summary",
    response_model=FraudSummary,
    summary="Get fraud alert summary",
)
async def get_fraud_summary(
    venue_id: UUID = Query(..., description="Venue to summarize"),
    date_from: date = Query(..., description="Start date of range (inclusive)"),
    date_to: date = Query(..., description="End date of range (inclusive)"),
    service: FraudDetectionService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> FraudSummary:
    """
    Generate a fraud alert summary for a date range.

    Provides aggregate statistics on fraud alerts including counts
    by status, severity, and type, as well as resolution metrics.

    Args:
        venue_id: UUID of the venue to summarize.
        date_from: Start date of the range (inclusive).
        date_to: End date of the range (inclusive).
        service: Injected FraudDetectionService instance.
        current_user: Authenticated user from JWT token.

    Returns:
        FraudSummary with aggregate statistics including:
        - Total alerts and counts by status
        - Breakdowns by alert type and severity
        - Unresolved critical/high alert counts
        - Average resolution time in hours
    """
    summary_data = await service.get_fraud_summary(venue_id, date_from, date_to)

    return FraudSummary(
        venue_id=UUID(summary_data["venue_id"]),
        date_from=date.fromisoformat(summary_data["date_from"]),
        date_to=date.fromisoformat(summary_data["date_to"]),
        total_alerts=summary_data["total_alerts"],
        new_alerts=summary_data["new_alerts"],
        investigating_alerts=summary_data["investigating_alerts"],
        confirmed_alerts=summary_data["confirmed_alerts"],
        dismissed_alerts=summary_data["dismissed_alerts"],
        resolved_alerts=summary_data["resolved_alerts"],
        by_type=[
            FraudAlertSummaryByType(**item)
            for item in summary_data["by_type"]
        ],
        by_severity=[
            FraudAlertSummaryBySeverity(**item)
            for item in summary_data["by_severity"]
        ],
        by_status=[
            FraudAlertSummaryByStatus(**item)
            for item in summary_data["by_status"]
        ],
        critical_unresolved=summary_data["critical_unresolved"],
        high_unresolved=summary_data["high_unresolved"],
        average_resolution_hours=(
            Decimal(str(summary_data["average_resolution_hours"]))
            if summary_data["average_resolution_hours"] is not None
            else None
        ),
    )
