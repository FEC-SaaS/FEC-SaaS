"""
=============================================================================
FILE: services/customer_service.py
PURPOSE: Customer management business logic
=============================================================================
"""

from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.models.customer import (
    Customer,
    CustomerLTV,
    CustomerChurnRisk,
    CustomerSegment,
    CustomerPreference,
    CustomerVisit,
    CustomerType,
    SegmentType,
    RiskLevel,
)
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerSearch,
    PaginationParams,
)
from app.services.event_publisher import event_publisher

logger = structlog.get_logger()


class CustomerService:
    """Service for customer management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_customer(self, customer_data: CustomerCreate) -> Customer:
        """
        Create a new customer.

        Args:
            customer_data: Customer creation data

        Returns:
            Created customer instance
        """
        customer = Customer(
            venue_id=customer_data.venue_id,
            first_name=customer_data.first_name,
            last_name=customer_data.last_name,
            email=customer_data.email,
            phone=customer_data.phone,
            date_of_birth=customer_data.date_of_birth,
            gender=customer_data.gender,
            customer_type=customer_data.customer_type,
            company_name=customer_data.company_name,
            job_title=customer_data.job_title,
            address_line1=customer_data.address_line1,
            address_line2=customer_data.address_line2,
            city=customer_data.city,
            state=customer_data.state,
            postal_code=customer_data.postal_code,
            country=customer_data.country,
            marketing_opt_in=customer_data.marketing_opt_in,
            sms_opt_in=customer_data.sms_opt_in,
            email_opt_in=customer_data.email_opt_in,
            notes=customer_data.notes,
            tags=customer_data.tags or [],
            acquisition_source=customer_data.acquisition_source,
            acquisition_campaign=customer_data.acquisition_campaign,
            is_active=True,
        )

        self.db.add(customer)
        await self.db.flush()

        # Create initial segment as NEW
        initial_segment = CustomerSegment(
            customer_id=customer.id,
            segment_type=SegmentType.NEW,
            score=Decimal("100.00"),
        )
        self.db.add(initial_segment)

        # Initialize LTV record
        ltv = CustomerLTV(
            customer_id=customer.id,
            calculated_ltv=Decimal("0.00"),
            visit_frequency=Decimal("0.00"),
            avg_spend=Decimal("0.00"),
            total_visits=0,
            total_revenue=Decimal("0.00"),
        )
        self.db.add(ltv)

        # Initialize churn risk
        churn_risk = CustomerChurnRisk(
            customer_id=customer.id,
            risk_score=Decimal("0.00"),
            risk_level=RiskLevel.LOW,
            days_since_last_visit=0,
        )
        self.db.add(churn_risk)

        await self.db.flush()
        await self.db.refresh(customer)

        logger.info(
            "customer_created",
            customer_id=str(customer.id),
            venue_id=str(customer.venue_id),
            email=customer.email,
        )

        # Publish event
        await event_publisher.publish_customer_created(
            customer_id=customer.id,
            venue_id=customer.venue_id,
            email=customer.email,
            first_name=customer.first_name,
            last_name=customer.last_name,
            acquisition_source=customer.acquisition_source,
        )

        return customer

    async def get_customer(self, customer_id: UUID) -> Optional[Customer]:
        """Get customer by ID with related data."""
        result = await self.db.execute(
            select(Customer)
            .options(
                selectinload(Customer.segments),
                selectinload(Customer.ltv),
                selectinload(Customer.churn_risk),
                selectinload(Customer.preferences),
            )
            .where(
                and_(
                    Customer.id == customer_id,
                    Customer.gdpr_data_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_customer_by_email(
        self,
        venue_id: UUID,
        email: str,
    ) -> Optional[Customer]:
        """Get customer by email within a venue."""
        result = await self.db.execute(
            select(Customer).where(
                and_(
                    Customer.venue_id == venue_id,
                    Customer.email == email,
                    Customer.gdpr_data_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_customer_by_phone(
        self,
        venue_id: UUID,
        phone: str,
    ) -> Optional[Customer]:
        """Get customer by phone within a venue."""
        result = await self.db.execute(
            select(Customer).where(
                and_(
                    Customer.venue_id == venue_id,
                    Customer.phone == phone,
                    Customer.gdpr_data_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_customers(
        self,
        venue_id: UUID,
        pagination: PaginationParams,
        customer_type: Optional[CustomerType] = None,
        is_active: Optional[bool] = True,
        segment: Optional[SegmentType] = None,
    ) -> Tuple[List[Customer], int]:
        """
        List customers with filtering and pagination.

        Returns:
            Tuple of (customers list, total count)
        """
        query = select(Customer).where(
            and_(
                Customer.venue_id == venue_id,
                Customer.gdpr_data_deleted == False,
            )
        )

        if is_active is not None:
            query = query.where(Customer.is_active == is_active)

        if customer_type:
            query = query.where(Customer.customer_type == customer_type)

        if segment:
            query = query.join(Customer.segments).where(
                CustomerSegment.segment_type == segment
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_column = getattr(Customer, pagination.sort_by, Customer.created_at)
        if pagination.sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        offset = (pagination.page - 1) * pagination.page_size
        query = query.offset(offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        customers = list(result.scalars().all())

        return customers, total

    async def search_customers(
        self,
        search: CustomerSearch,
        pagination: PaginationParams,
    ) -> Tuple[List[Customer], int]:
        """Search customers by various criteria."""
        query = select(Customer).where(Customer.gdpr_data_deleted == False)

        if search.venue_id:
            query = query.where(Customer.venue_id == search.venue_id)

        if search.query:
            search_term = f"%{search.query}%"
            query = query.where(
                or_(
                    Customer.first_name.ilike(search_term),
                    Customer.last_name.ilike(search_term),
                    Customer.email.ilike(search_term),
                    Customer.phone.ilike(search_term),
                    Customer.company_name.ilike(search_term),
                )
            )

        if search.customer_type:
            query = query.where(Customer.customer_type == search.customer_type)

        if search.is_active is not None:
            query = query.where(Customer.is_active == search.is_active)

        if search.has_email is not None:
            if search.has_email:
                query = query.where(Customer.email.isnot(None))
            else:
                query = query.where(Customer.email.is_(None))

        if search.has_phone is not None:
            if search.has_phone:
                query = query.where(Customer.phone.isnot(None))
            else:
                query = query.where(Customer.phone.is_(None))

        if search.segment:
            query = query.join(Customer.segments).where(
                CustomerSegment.segment_type == search.segment
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting and pagination
        sort_column = getattr(Customer, pagination.sort_by, Customer.created_at)
        if pagination.sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        offset = (pagination.page - 1) * pagination.page_size
        query = query.offset(offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        customers = list(result.scalars().all())

        return customers, total

    async def update_customer(
        self,
        customer_id: UUID,
        update_data: CustomerUpdate,
    ) -> Optional[Customer]:
        """Update customer information."""
        customer = await self.get_customer(customer_id)
        if not customer:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(customer, field, value)

        customer.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(customer)

        logger.info(
            "customer_updated",
            customer_id=str(customer_id),
            fields_updated=list(update_dict.keys()),
        )

        # Publish event
        await event_publisher.publish_customer_updated(
            customer_id=customer.id,
            venue_id=customer.venue_id,
            updated_fields=list(update_dict.keys()),
        )

        return customer

    async def delete_customer(
        self,
        customer_id: UUID,
        gdpr_delete: bool = False,
    ) -> bool:
        """
        Delete a customer.

        Args:
            customer_id: Customer ID
            gdpr_delete: If True, perform GDPR-compliant deletion

        Returns:
            True if deleted
        """
        customer = await self.get_customer(customer_id)
        if not customer:
            return False

        venue_id = customer.venue_id

        if gdpr_delete:
            # GDPR compliant deletion - anonymize data
            customer.first_name = "DELETED"
            customer.last_name = "USER"
            customer.email = None
            customer.phone = None
            customer.date_of_birth = None
            customer.address_line1 = None
            customer.address_line2 = None
            customer.city = None
            customer.state = None
            customer.postal_code = None
            customer.notes = None
            customer.tags = []
            customer.meta_data = {}
            customer.gdpr_data_deleted = True
            customer.is_active = False

            logger.info("customer_gdpr_deleted", customer_id=str(customer_id))
        else:
            # Soft delete
            customer.is_active = False

            logger.info("customer_deactivated", customer_id=str(customer_id))

        await self.db.flush()

        # Publish event
        await event_publisher.publish_customer_deleted(
            customer_id=customer_id,
            venue_id=venue_id,
            gdpr_delete=gdpr_delete,
        )

        return True

    async def get_customer_visits_count(self, customer_id: UUID) -> int:
        """Get total visit count for a customer."""
        result = await self.db.execute(
            select(func.count())
            .select_from(CustomerVisit)
            .where(CustomerVisit.customer_id == customer_id)
        )
        return result.scalar() or 0

    async def get_customer_total_spend(self, customer_id: UUID) -> Decimal:
        """Get total spend for a customer."""
        result = await self.db.execute(
            select(func.sum(CustomerVisit.total_spend))
            .where(CustomerVisit.customer_id == customer_id)
        )
        return result.scalar() or Decimal("0.00")

    async def add_customer_preference(
        self,
        customer_id: UUID,
        preference_type: str,
        preference_value: str,
        confidence_score: Decimal = Decimal("50.00"),
        is_stated: bool = False,
    ) -> CustomerPreference:
        """Add or update a customer preference."""
        # Check if preference exists
        result = await self.db.execute(
            select(CustomerPreference).where(
                and_(
                    CustomerPreference.customer_id == customer_id,
                    CustomerPreference.preference_type == preference_type,
                    CustomerPreference.preference_value == preference_value,
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.confidence_score = confidence_score
            existing.is_stated = is_stated
            existing.updated_at = datetime.utcnow()
            await self.db.flush()
            return existing

        preference = CustomerPreference(
            customer_id=customer_id,
            preference_type=preference_type,
            preference_value=preference_value,
            confidence_score=confidence_score,
            is_stated=is_stated,
            is_inferred=not is_stated,
        )
        self.db.add(preference)
        await self.db.flush()
        await self.db.refresh(preference)

        return preference

    async def get_customer_preferences(
        self,
        customer_id: UUID,
    ) -> List[CustomerPreference]:
        """Get all preferences for a customer."""
        result = await self.db.execute(
            select(CustomerPreference)
            .where(CustomerPreference.customer_id == customer_id)
            .order_by(CustomerPreference.confidence_score.desc())
        )
        return list(result.scalars().all())

    async def get_at_risk_customers(
        self,
        venue_id: UUID,
        risk_level: Optional[RiskLevel] = None,
        limit: int = 100,
    ) -> List[Customer]:
        """Get customers at risk of churning."""
        query = (
            select(Customer)
            .join(Customer.churn_risk)
            .where(
                and_(
                    Customer.venue_id == venue_id,
                    Customer.is_active == True,
                    Customer.gdpr_data_deleted == False,
                )
            )
        )

        if risk_level:
            query = query.where(CustomerChurnRisk.risk_level == risk_level)
        else:
            # Default to high and critical risk
            query = query.where(
                CustomerChurnRisk.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL])
            )

        query = query.order_by(CustomerChurnRisk.risk_score.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_venue_customer_count(self, venue_id: UUID) -> int:
        """Get count of active customers for a venue."""
        result = await self.db.execute(
            select(func.count())
            .select_from(Customer)
            .where(
                and_(
                    Customer.venue_id == venue_id,
                    Customer.is_active == True,
                    Customer.gdpr_data_deleted == False,
                )
            )
        )
        return result.scalar() or 0
