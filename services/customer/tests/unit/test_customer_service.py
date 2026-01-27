"""
=============================================================================
FILE: tests/unit/test_customer_service.py
PURPOSE: Unit tests for CustomerService
=============================================================================
"""

from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.customer_service import CustomerService
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerSearch,
    PaginationParams,
)
from app.models.customer import CustomerType, SegmentType, RiskLevel
from tests.conftest import CustomerFactory


class TestCustomerServiceCreate:
    """Tests for customer creation."""

    @pytest.mark.asyncio
    async def test_create_customer_success(self, db_session: AsyncSession, sample_venue_id):
        """Test successful customer creation."""
        service = CustomerService(db_session)

        customer_data = CustomerCreate(
            venue_id=sample_venue_id,
            customer_type=CustomerType.INDIVIDUAL,
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com",
            phone="+15551234567",
        )

        customer = await service.create_customer(customer_data)

        assert customer is not None
        assert customer.first_name == "Jane"
        assert customer.last_name == "Smith"
        assert customer.email == "jane.smith@example.com"
        assert customer.venue_id == sample_venue_id
        assert customer.is_active is True

    @pytest.mark.asyncio
    async def test_create_customer_corporate(self, db_session: AsyncSession, sample_venue_id):
        """Test creating corporate customer."""
        service = CustomerService(db_session)

        customer_data = CustomerCreate(
            venue_id=sample_venue_id,
            customer_type=CustomerType.CORPORATE,
            first_name="ACME",
            last_name="Corporation",
            email="contact@acme.com",
            company_name="ACME Corp",
            tax_id="12-3456789",
        )

        customer = await service.create_customer(customer_data)

        assert customer.customer_type == CustomerType.CORPORATE
        assert customer.company_name == "ACME Corp"

    @pytest.mark.asyncio
    async def test_create_customer_minimal_data(self, db_session: AsyncSession, sample_venue_id):
        """Test creating customer with minimal required data."""
        service = CustomerService(db_session)

        customer_data = CustomerCreate(
            venue_id=sample_venue_id,
            customer_type=CustomerType.INDIVIDUAL,
            first_name="Minimal",
            last_name="Customer",
        )

        customer = await service.create_customer(customer_data)

        assert customer is not None
        assert customer.first_name == "Minimal"


class TestCustomerServiceGet:
    """Tests for customer retrieval."""

    @pytest.mark.asyncio
    async def test_get_customer_by_id(self, db_session: AsyncSession, sample_customer):
        """Test getting customer by ID."""
        service = CustomerService(db_session)

        customer = await service.get_customer(sample_customer.id)

        assert customer is not None
        assert customer.id == sample_customer.id

    @pytest.mark.asyncio
    async def test_get_customer_not_found(self, db_session: AsyncSession):
        """Test getting non-existent customer."""
        service = CustomerService(db_session)

        customer = await service.get_customer(uuid4())

        assert customer is None

    @pytest.mark.asyncio
    async def test_get_customer_by_email(self, db_session: AsyncSession, sample_customer):
        """Test getting customer by email."""
        service = CustomerService(db_session)

        customer = await service.get_customer_by_email(
            sample_customer.venue_id,
            sample_customer.email
        )

        assert customer is not None
        assert customer.email == sample_customer.email

    @pytest.mark.asyncio
    async def test_get_customer_by_phone(self, db_session: AsyncSession, sample_customer):
        """Test getting customer by phone."""
        service = CustomerService(db_session)

        customer = await service.get_customer_by_phone(
            sample_customer.venue_id,
            sample_customer.phone
        )

        assert customer is not None
        assert customer.phone == sample_customer.phone


class TestCustomerServiceList:
    """Tests for customer listing."""

    @pytest.mark.asyncio
    async def test_list_customers(self, db_session: AsyncSession, sample_customers, sample_venue_id):
        """Test listing customers with pagination."""
        service = CustomerService(db_session)
        pagination = PaginationParams(page=1, page_size=10)

        customers, total = await service.list_customers(
            venue_id=sample_venue_id,
            pagination=pagination,
        )

        assert len(customers) == 5
        assert total == 5

    @pytest.mark.asyncio
    async def test_list_customers_with_filter(self, db_session: AsyncSession, sample_customers, sample_venue_id):
        """Test listing customers with type filter."""
        service = CustomerService(db_session)
        pagination = PaginationParams(page=1, page_size=10)

        customers, total = await service.list_customers(
            venue_id=sample_venue_id,
            pagination=pagination,
            customer_type=CustomerType.INDIVIDUAL,
        )

        assert all(c.customer_type == CustomerType.INDIVIDUAL for c in customers)

    @pytest.mark.asyncio
    async def test_list_customers_pagination(self, db_session: AsyncSession, sample_customers, sample_venue_id):
        """Test pagination works correctly."""
        service = CustomerService(db_session)
        pagination = PaginationParams(page=1, page_size=2)

        customers, total = await service.list_customers(
            venue_id=sample_venue_id,
            pagination=pagination,
        )

        assert len(customers) == 2
        assert total == 5


class TestCustomerServiceUpdate:
    """Tests for customer updates."""

    @pytest.mark.asyncio
    async def test_update_customer_success(self, db_session: AsyncSession, sample_customer):
        """Test successful customer update."""
        service = CustomerService(db_session)

        update_data = CustomerUpdate(
            first_name="Updated",
            last_name="Name",
        )

        updated = await service.update_customer(sample_customer.id, update_data)

        assert updated is not None
        assert updated.first_name == "Updated"
        assert updated.last_name == "Name"

    @pytest.mark.asyncio
    async def test_update_customer_partial(self, db_session: AsyncSession, sample_customer):
        """Test partial customer update."""
        service = CustomerService(db_session)
        original_email = sample_customer.email

        update_data = CustomerUpdate(first_name="OnlyFirst")

        updated = await service.update_customer(sample_customer.id, update_data)

        assert updated.first_name == "OnlyFirst"
        assert updated.email == original_email

    @pytest.mark.asyncio
    async def test_update_customer_not_found(self, db_session: AsyncSession):
        """Test updating non-existent customer."""
        service = CustomerService(db_session)

        update_data = CustomerUpdate(first_name="Test")

        updated = await service.update_customer(uuid4(), update_data)

        assert updated is None


class TestCustomerServiceDelete:
    """Tests for customer deletion."""

    @pytest.mark.asyncio
    async def test_soft_delete_customer(self, db_session: AsyncSession, sample_customer):
        """Test soft delete customer."""
        service = CustomerService(db_session)

        deleted = await service.delete_customer(sample_customer.id, gdpr_delete=False)

        assert deleted is True

        # Customer should be soft deleted (is_active = False)
        customer = await service.get_customer(sample_customer.id)
        assert customer is not None
        assert customer.is_active is False

    @pytest.mark.asyncio
    async def test_delete_customer_not_found(self, db_session: AsyncSession):
        """Test deleting non-existent customer."""
        service = CustomerService(db_session)

        deleted = await service.delete_customer(uuid4(), gdpr_delete=False)

        assert deleted is False


class TestCustomerServiceSearch:
    """Tests for customer search."""

    @pytest.mark.asyncio
    async def test_search_by_query(self, db_session: AsyncSession, sample_customers, sample_venue_id):
        """Test searching customers by query string."""
        service = CustomerService(db_session)
        pagination = PaginationParams(page=1, page_size=10)

        search = CustomerSearch(
            query="Customer",
            venue_id=sample_venue_id,
        )

        customers, total = await service.search_customers(search, pagination)

        assert len(customers) > 0

    @pytest.mark.asyncio
    async def test_search_by_segment(self, db_session: AsyncSession, sample_venue_id):
        """Test searching by segment."""
        service = CustomerService(db_session)
        pagination = PaginationParams(page=1, page_size=10)

        search = CustomerSearch(
            venue_id=sample_venue_id,
            segment=SegmentType.VIP,
        )

        customers, total = await service.search_customers(search, pagination)

        # Empty result is expected if no VIP customers exist
        assert isinstance(customers, list)


class TestCustomerServicePreferences:
    """Tests for customer preferences."""

    @pytest.mark.asyncio
    async def test_add_preference(self, db_session: AsyncSession, sample_customer):
        """Test adding customer preference."""
        service = CustomerService(db_session)

        preference = await service.add_customer_preference(
            customer_id=sample_customer.id,
            preference_type="favorite_activity",
            preference_value="Laser Tag",
            is_stated=True,
        )

        assert preference is not None
        assert preference.preference_value == "Laser Tag"
        assert preference.is_stated is True

    @pytest.mark.asyncio
    async def test_get_preferences(self, db_session: AsyncSession, sample_customer):
        """Test getting customer preferences."""
        service = CustomerService(db_session)

        # Add a preference first
        await service.add_customer_preference(
            customer_id=sample_customer.id,
            preference_type="favorite_food",
            preference_value="Pizza",
        )

        preferences = await service.get_customer_preferences(sample_customer.id)

        assert len(preferences) >= 1


class TestCustomerServiceStats:
    """Tests for customer statistics."""

    @pytest.mark.asyncio
    async def test_get_visits_count(self, db_session: AsyncSession, sample_customer, sample_visit):
        """Test getting customer visit count."""
        service = CustomerService(db_session)

        count = await service.get_customer_visits_count(sample_customer.id)

        assert count >= 1

    @pytest.mark.asyncio
    async def test_get_total_spend(self, db_session: AsyncSession, sample_customer, sample_visit):
        """Test getting customer total spend."""
        service = CustomerService(db_session)

        total = await service.get_customer_total_spend(sample_customer.id)

        assert total >= Decimal("0")


class TestCustomerServiceAtRisk:
    """Tests for at-risk customer identification."""

    @pytest.mark.asyncio
    async def test_get_at_risk_customers(self, db_session: AsyncSession, sample_venue_id):
        """Test getting at-risk customers."""
        service = CustomerService(db_session)

        customers = await service.get_at_risk_customers(
            venue_id=sample_venue_id,
            risk_level=RiskLevel.HIGH,
            limit=10,
        )

        assert isinstance(customers, list)

    @pytest.mark.asyncio
    async def test_get_at_risk_customers_no_level(self, db_session: AsyncSession, sample_venue_id):
        """Test getting all at-risk customers without specific level."""
        service = CustomerService(db_session)

        customers = await service.get_at_risk_customers(
            venue_id=sample_venue_id,
            risk_level=None,
            limit=50,
        )

        assert isinstance(customers, list)
