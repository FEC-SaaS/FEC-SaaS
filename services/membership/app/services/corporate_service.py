"""
=============================================================================
FILE: services/corporate_service.py
PURPOSE: Corporate subscription management service
=============================================================================
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    CorporateSubscription,
    CorporateSubscriptionEmployee,
    CustomerSubscription,
    SubscriptionPlan,
    SubscriptionStatus,
)
from app.schemas.membership import (
    CorporateSubscriptionCreate,
    CorporateEmployeeRequest,
)


class CorporateService:
    """Service for managing corporate subscriptions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # CORPORATE SUBSCRIPTIONS
    # =========================================================================

    async def create_corporate_subscription(
        self,
        request: CorporateSubscriptionCreate,
    ) -> CorporateSubscription:
        """Create a new corporate subscription."""
        # Calculate pricing
        total_price = self._calculate_corporate_price(
            request.base_price,
            request.employee_count,
            request.discount_percent,
        )

        corporate = CorporateSubscription(
            plan_id=request.plan_id,
            company_name=request.company_name,
            company_email=request.company_email,
            billing_contact_name=request.billing_contact_name,
            billing_contact_email=request.billing_contact_email,
            tax_id=request.tax_id,
            employee_count=request.employee_count,
            discount_percent=request.discount_percent,
            negotiated_price=total_price,
            contract_start=request.contract_start or datetime.utcnow(),
            contract_end=request.contract_end,
            auto_renew=request.auto_renew if request.auto_renew is not None else True,
            status=SubscriptionStatus.ACTIVE,
        )
        self.db.add(corporate)
        await self.db.commit()
        await self.db.refresh(corporate)
        return corporate

    async def get_corporate_subscription(
        self, corporate_id: UUID
    ) -> Optional[CorporateSubscription]:
        """Get a corporate subscription by ID."""
        result = await self.db.execute(
            select(CorporateSubscription)
            .where(CorporateSubscription.id == corporate_id)
            .options(
                selectinload(CorporateSubscription.employees),
                selectinload(CorporateSubscription.plan),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_company_email(
        self, company_email: str
    ) -> Optional[CorporateSubscription]:
        """Get a corporate subscription by company email."""
        result = await self.db.execute(
            select(CorporateSubscription).where(
                CorporateSubscription.company_email == company_email
            )
        )
        return result.scalar_one_or_none()

    async def list_corporate_subscriptions(
        self,
        plan_id: Optional[UUID] = None,
        status: Optional[SubscriptionStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[CorporateSubscription]:
        """List corporate subscriptions."""
        query = select(CorporateSubscription)

        if plan_id:
            query = query.where(CorporateSubscription.plan_id == plan_id)
        if status:
            query = query.where(CorporateSubscription.status == status)

        query = query.order_by(CorporateSubscription.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_corporate_subscription(
        self,
        corporate_id: UUID,
        company_name: Optional[str] = None,
        billing_contact_name: Optional[str] = None,
        billing_contact_email: Optional[str] = None,
        employee_count: Optional[int] = None,
        discount_percent: Optional[Decimal] = None,
        auto_renew: Optional[bool] = None,
    ) -> Optional[CorporateSubscription]:
        """Update corporate subscription details."""
        corporate = await self.get_corporate_subscription(corporate_id)
        if not corporate:
            return None

        if company_name is not None:
            corporate.company_name = company_name
        if billing_contact_name is not None:
            corporate.billing_contact_name = billing_contact_name
        if billing_contact_email is not None:
            corporate.billing_contact_email = billing_contact_email
        if auto_renew is not None:
            corporate.auto_renew = auto_renew

        # Recalculate price if count or discount changes
        if employee_count is not None or discount_percent is not None:
            if employee_count is not None:
                corporate.employee_count = employee_count
            if discount_percent is not None:
                corporate.discount_percent = discount_percent

            # Get base price from plan
            result = await self.db.execute(
                select(SubscriptionPlan).where(
                    SubscriptionPlan.id == corporate.plan_id
                )
            )
            plan = result.scalar_one_or_none()
            if plan:
                corporate.negotiated_price = self._calculate_corporate_price(
                    plan.price,
                    corporate.employee_count,
                    corporate.discount_percent,
                )

        await self.db.commit()
        await self.db.refresh(corporate)
        return corporate

    async def cancel_corporate_subscription(
        self,
        corporate_id: UUID,
        reason: Optional[str] = None,
        immediate: bool = False,
    ) -> Optional[CorporateSubscription]:
        """Cancel a corporate subscription."""
        corporate = await self.get_corporate_subscription(corporate_id)
        if not corporate:
            return None

        if immediate:
            corporate.status = SubscriptionStatus.CANCELLED
            # Deactivate all employee access
            for employee in corporate.employees:
                if employee.is_active:
                    employee.is_active = False
                    employee.deactivated_at = datetime.utcnow()
        else:
            corporate.status = SubscriptionStatus.PENDING_CANCELLATION
            corporate.auto_renew = False

        await self.db.commit()
        await self.db.refresh(corporate)
        return corporate

    async def renew_contract(
        self,
        corporate_id: UUID,
        new_end_date: datetime,
        new_employee_count: Optional[int] = None,
        new_discount_percent: Optional[Decimal] = None,
    ) -> Optional[CorporateSubscription]:
        """Renew a corporate contract."""
        corporate = await self.get_corporate_subscription(corporate_id)
        if not corporate:
            return None

        corporate.contract_end = new_end_date
        corporate.status = SubscriptionStatus.ACTIVE

        if new_employee_count is not None:
            corporate.employee_count = new_employee_count
        if new_discount_percent is not None:
            corporate.discount_percent = new_discount_percent

        # Recalculate price
        result = await self.db.execute(
            select(SubscriptionPlan).where(
                SubscriptionPlan.id == corporate.plan_id
            )
        )
        plan = result.scalar_one_or_none()
        if plan:
            corporate.negotiated_price = self._calculate_corporate_price(
                plan.price,
                corporate.employee_count,
                corporate.discount_percent,
            )

        await self.db.commit()
        await self.db.refresh(corporate)
        return corporate

    # =========================================================================
    # EMPLOYEE MANAGEMENT
    # =========================================================================

    async def add_employee(
        self,
        corporate_id: UUID,
        request: CorporateEmployeeRequest,
    ) -> CorporateSubscriptionEmployee:
        """Add an employee to corporate subscription."""
        corporate = await self.get_corporate_subscription(corporate_id)
        if not corporate:
            raise ValueError("Corporate subscription not found")

        # Check employee limit
        active_employees = len([e for e in corporate.employees if e.is_active])
        if active_employees >= corporate.employee_count:
            raise ValueError("Employee limit reached for this corporate subscription")

        # Check if employee already exists
        existing = await self._get_employee_by_email(
            corporate_id, request.employee_email
        )
        if existing and existing.is_active:
            raise ValueError("Employee already added to this subscription")

        # Reactivate or create employee
        if existing:
            existing.is_active = True
            existing.employee_name = request.employee_name
            existing.department = request.department
            existing.activated_at = datetime.utcnow()
            existing.deactivated_at = None
            employee = existing
        else:
            employee = CorporateSubscriptionEmployee(
                corporate_subscription_id=corporate_id,
                customer_id=request.customer_id,
                employee_email=request.employee_email,
                employee_name=request.employee_name,
                department=request.department,
                is_active=True,
                activated_at=datetime.utcnow(),
            )
            self.db.add(employee)

        await self.db.commit()
        await self.db.refresh(employee)
        return employee

    async def remove_employee(
        self,
        corporate_id: UUID,
        employee_id: UUID,
    ) -> bool:
        """Remove an employee from corporate subscription."""
        result = await self.db.execute(
            select(CorporateSubscriptionEmployee).where(
                and_(
                    CorporateSubscriptionEmployee.id == employee_id,
                    CorporateSubscriptionEmployee.corporate_subscription_id == corporate_id,
                )
            )
        )
        employee = result.scalar_one_or_none()
        if not employee or not employee.is_active:
            return False

        employee.is_active = False
        employee.deactivated_at = datetime.utcnow()

        await self.db.commit()
        return True

    async def get_employee(
        self, employee_id: UUID
    ) -> Optional[CorporateSubscriptionEmployee]:
        """Get an employee by ID."""
        result = await self.db.execute(
            select(CorporateSubscriptionEmployee).where(
                CorporateSubscriptionEmployee.id == employee_id
            )
        )
        return result.scalar_one_or_none()

    async def get_employees(
        self,
        corporate_id: UUID,
        active_only: bool = True,
        department: Optional[str] = None,
    ) -> List[CorporateSubscriptionEmployee]:
        """Get all employees for a corporate subscription."""
        query = select(CorporateSubscriptionEmployee).where(
            CorporateSubscriptionEmployee.corporate_subscription_id == corporate_id
        )
        if active_only:
            query = query.where(CorporateSubscriptionEmployee.is_active == True)
        if department:
            query = query.where(
                CorporateSubscriptionEmployee.department == department
            )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_employee(
        self,
        employee_id: UUID,
        employee_name: Optional[str] = None,
        department: Optional[str] = None,
    ) -> Optional[CorporateSubscriptionEmployee]:
        """Update employee details."""
        employee = await self.get_employee(employee_id)
        if not employee:
            return None

        if employee_name is not None:
            employee.employee_name = employee_name
        if department is not None:
            employee.department = department

        await self.db.commit()
        await self.db.refresh(employee)
        return employee

    async def bulk_add_employees(
        self,
        corporate_id: UUID,
        employees: List[CorporateEmployeeRequest],
    ) -> Dict[str, Any]:
        """Add multiple employees at once."""
        corporate = await self.get_corporate_subscription(corporate_id)
        if not corporate:
            raise ValueError("Corporate subscription not found")

        active_employees = len([e for e in corporate.employees if e.is_active])
        available_slots = corporate.employee_count - active_employees

        added = []
        failed = []

        for emp_request in employees[:available_slots]:
            try:
                employee = await self.add_employee(corporate_id, emp_request)
                added.append({
                    "email": emp_request.employee_email,
                    "id": str(employee.id),
                })
            except ValueError as e:
                failed.append({
                    "email": emp_request.employee_email,
                    "error": str(e),
                })

        # Mark remaining as failed due to limit
        for emp_request in employees[available_slots:]:
            failed.append({
                "email": emp_request.employee_email,
                "error": "Employee limit reached",
            })

        return {
            "added": added,
            "failed": failed,
            "total_added": len(added),
            "total_failed": len(failed),
        }

    async def check_employee_access(
        self, employee_email: str
    ) -> Optional[Dict[str, Any]]:
        """Check if an employee has active corporate access."""
        result = await self.db.execute(
            select(CorporateSubscriptionEmployee)
            .where(
                and_(
                    CorporateSubscriptionEmployee.employee_email == employee_email,
                    CorporateSubscriptionEmployee.is_active == True,
                )
            )
            .options(
                selectinload(
                    CorporateSubscriptionEmployee.corporate_subscription
                )
            )
        )
        employee = result.scalar_one_or_none()

        if not employee:
            return None

        corporate = employee.corporate_subscription
        if corporate.status not in [
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIAL,
        ]:
            return None

        return {
            "has_access": True,
            "employee_id": employee.id,
            "corporate_id": corporate.id,
            "company_name": corporate.company_name,
            "plan_id": corporate.plan_id,
        }

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    async def get_corporate_stats(
        self, corporate_id: UUID
    ) -> Dict[str, Any]:
        """Get statistics for a corporate subscription."""
        corporate = await self.get_corporate_subscription(corporate_id)
        if not corporate:
            raise ValueError("Corporate subscription not found")

        active_employees = len([e for e in corporate.employees if e.is_active])
        inactive_employees = len([e for e in corporate.employees if not e.is_active])

        # Group by department
        departments = {}
        for emp in corporate.employees:
            if emp.is_active:
                dept = emp.department or "Unassigned"
                departments[dept] = departments.get(dept, 0) + 1

        return {
            "company_name": corporate.company_name,
            "plan_id": corporate.plan_id,
            "status": corporate.status.value,
            "employee_limit": corporate.employee_count,
            "active_employees": active_employees,
            "inactive_employees": inactive_employees,
            "utilization_percent": (
                (active_employees / corporate.employee_count) * 100
                if corporate.employee_count > 0
                else 0
            ),
            "departments": departments,
            "contract_start": corporate.contract_start,
            "contract_end": corporate.contract_end,
            "negotiated_price": float(corporate.negotiated_price),
            "price_per_employee": (
                float(corporate.negotiated_price) / corporate.employee_count
                if corporate.employee_count > 0
                else 0
            ),
        }

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _calculate_corporate_price(
        self,
        base_price: Decimal,
        employee_count: int,
        discount_percent: Optional[Decimal] = None,
    ) -> Decimal:
        """Calculate total corporate subscription price."""
        total = base_price * employee_count

        if discount_percent:
            discount = total * (discount_percent / Decimal("100"))
            total = total - discount

        return total

    async def _get_employee_by_email(
        self, corporate_id: UUID, email: str
    ) -> Optional[CorporateSubscriptionEmployee]:
        """Get employee by email for a specific corporate subscription."""
        result = await self.db.execute(
            select(CorporateSubscriptionEmployee).where(
                and_(
                    CorporateSubscriptionEmployee.corporate_subscription_id == corporate_id,
                    CorporateSubscriptionEmployee.employee_email == email,
                )
            )
        )
        return result.scalar_one_or_none()
