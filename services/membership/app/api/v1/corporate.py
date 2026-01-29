"""
=============================================================================
FILE: api/v1/corporate.py
PURPOSE: Corporate subscription API endpoints
=============================================================================
"""

from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, require_venue_access
from app.services import CorporateService
from app.services.event_publisher import event_publisher
from app.models import SubscriptionStatus
from app.schemas.membership import (
    CorporateSubscriptionCreate,
    CorporateSubscriptionResponse,
    CorporateEmployeeRequest,
    CorporateEmployeeResponse,
)

router = APIRouter(prefix="/corporate", tags=["Corporate Subscriptions"])


# =============================================================================
# CORPORATE SUBSCRIPTIONS
# =============================================================================


@router.post("", response_model=CorporateSubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_corporate_subscription(
    request: CorporateSubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new corporate subscription."""
    # Requires admin permission
    service = CorporateService(db)

    try:
        corporate = await service.create_corporate_subscription(request)

        await event_publisher.publish(
            event_publisher.EVENT_CORPORATE_CREATED,
            {
                "corporate_id": corporate.id,
                "company_name": corporate.company_name,
                "plan_id": corporate.plan_id,
                "employee_count": corporate.employee_count,
            },
        )

        return corporate
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=List[CorporateSubscriptionResponse])
async def list_corporate_subscriptions(
    plan_id: Optional[UUID] = None,
    status: Optional[SubscriptionStatus] = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List corporate subscriptions."""
    # Requires admin permission
    service = CorporateService(db)
    subscriptions = await service.list_corporate_subscriptions(
        plan_id=plan_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return subscriptions


@router.get("/{corporate_id}", response_model=CorporateSubscriptionResponse)
async def get_corporate_subscription(
    corporate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a corporate subscription by ID."""
    service = CorporateService(db)
    corporate = await service.get_corporate_subscription(corporate_id)
    if not corporate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corporate subscription not found",
        )
    return corporate


@router.patch("/{corporate_id}", response_model=CorporateSubscriptionResponse)
async def update_corporate_subscription(
    corporate_id: UUID,
    company_name: Optional[str] = None,
    billing_contact_name: Optional[str] = None,
    billing_contact_email: Optional[str] = None,
    employee_count: Optional[int] = None,
    discount_percent: Optional[Decimal] = None,
    auto_renew: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update corporate subscription details."""
    service = CorporateService(db)

    try:
        updated = await service.update_corporate_subscription(
            corporate_id=corporate_id,
            company_name=company_name,
            billing_contact_name=billing_contact_name,
            billing_contact_email=billing_contact_email,
            employee_count=employee_count,
            discount_percent=discount_percent,
            auto_renew=auto_renew,
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Corporate subscription not found",
            )
        return updated
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{corporate_id}/cancel", response_model=CorporateSubscriptionResponse)
async def cancel_corporate_subscription(
    corporate_id: UUID,
    reason: Optional[str] = None,
    immediate: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Cancel a corporate subscription."""
    service = CorporateService(db)

    cancelled = await service.cancel_corporate_subscription(
        corporate_id=corporate_id,
        reason=reason,
        immediate=immediate,
    )
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corporate subscription not found",
        )
    return cancelled


@router.post("/{corporate_id}/renew", response_model=CorporateSubscriptionResponse)
async def renew_corporate_contract(
    corporate_id: UUID,
    new_end_date: datetime,
    new_employee_count: Optional[int] = None,
    new_discount_percent: Optional[Decimal] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Renew a corporate contract."""
    service = CorporateService(db)

    renewed = await service.renew_contract(
        corporate_id=corporate_id,
        new_end_date=new_end_date,
        new_employee_count=new_employee_count,
        new_discount_percent=new_discount_percent,
    )
    if not renewed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corporate subscription not found",
        )
    return renewed


@router.get("/{corporate_id}/stats")
async def get_corporate_stats(
    corporate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get statistics for a corporate subscription."""
    service = CorporateService(db)

    try:
        stats = await service.get_corporate_stats(corporate_id)
        return stats
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# =============================================================================
# EMPLOYEE MANAGEMENT
# =============================================================================


@router.post("/{corporate_id}/employees", response_model=CorporateEmployeeResponse, status_code=status.HTTP_201_CREATED)
async def add_employee(
    corporate_id: UUID,
    request: CorporateEmployeeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add an employee to a corporate subscription."""
    service = CorporateService(db)

    try:
        employee = await service.add_employee(corporate_id, request)

        await event_publisher.publish(
            event_publisher.EVENT_CORPORATE_EMPLOYEE_ADDED,
            {
                "corporate_id": corporate_id,
                "employee_id": employee.id,
                "employee_email": employee.employee_email,
            },
        )

        return employee
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{corporate_id}/employees/bulk")
async def bulk_add_employees(
    corporate_id: UUID,
    employees: List[CorporateEmployeeRequest],
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add multiple employees at once."""
    service = CorporateService(db)

    try:
        result = await service.bulk_add_employees(corporate_id, employees)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{corporate_id}/employees", response_model=List[CorporateEmployeeResponse])
async def list_employees(
    corporate_id: UUID,
    active_only: bool = True,
    department: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all employees for a corporate subscription."""
    service = CorporateService(db)
    employees = await service.get_employees(
        corporate_id=corporate_id,
        active_only=active_only,
        department=department,
    )
    return employees


@router.get("/{corporate_id}/employees/{employee_id}", response_model=CorporateEmployeeResponse)
async def get_employee(
    corporate_id: UUID,
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a specific employee."""
    service = CorporateService(db)
    employee = await service.get_employee(employee_id)
    if not employee or employee.corporate_subscription_id != corporate_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
    return employee


@router.patch("/{corporate_id}/employees/{employee_id}", response_model=CorporateEmployeeResponse)
async def update_employee(
    corporate_id: UUID,
    employee_id: UUID,
    employee_name: Optional[str] = None,
    department: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update employee details."""
    service = CorporateService(db)

    # Verify employee belongs to this corporate subscription
    employee = await service.get_employee(employee_id)
    if not employee or employee.corporate_subscription_id != corporate_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )

    updated = await service.update_employee(
        employee_id=employee_id,
        employee_name=employee_name,
        department=department,
    )
    return updated


@router.delete("/{corporate_id}/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_employee(
    corporate_id: UUID,
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Remove an employee from a corporate subscription."""
    service = CorporateService(db)

    success = await service.remove_employee(corporate_id, employee_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )

    await event_publisher.publish(
        event_publisher.EVENT_CORPORATE_EMPLOYEE_REMOVED,
        {
            "corporate_id": corporate_id,
            "employee_id": employee_id,
        },
    )


@router.get("/check-access/{employee_email}")
async def check_employee_access(
    employee_email: str,
    db: AsyncSession = Depends(get_db),
):
    """Check if an employee has active corporate access."""
    service = CorporateService(db)
    access_info = await service.check_employee_access(employee_email)
    if not access_info:
        return {"has_access": False}
    return access_info
