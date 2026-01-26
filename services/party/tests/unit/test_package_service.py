"""
=============================================================================
FILE: tests/unit/test_package_service.py
PURPOSE: Unit tests for PackageService
=============================================================================
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.party import PartyPackage, PartyAddon, PartyPackageAddon, PackageType
from app.services.package_service import PackageService
from app.schemas.party import PartyPackageCreate, PartyPackageUpdate, PaginationParams


class TestPackageServiceCreate:
    """Tests for PackageService.create_package method."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> PackageService:
        """Create PackageService instance."""
        return PackageService(db_session)

    @pytest.mark.asyncio
    async def test_create_package_success(
        self,
        service: PackageService,
        sample_venue_id: uuid.UUID,
    ):
        """Test successful package creation."""
        package_data = PartyPackageCreate(
            venue_id=sample_venue_id,
            package_name="Birthday Bash",
            package_type=PackageType.BIRTHDAY,
            description="Ultimate birthday party",
            min_guests=8,
            max_guests=25,
            base_price=Decimal("299.99"),
            price_per_additional_guest=Decimal("15.00"),
            deposit_percentage=Decimal("25.00"),
            duration_minutes=120,
            includes_food=True,
            includes_drinks=True,
            includes_cake=True,
            includes_decorations=True,
            includes_invitations=False,
            display_order=1,
            is_featured=True,
        )

        result = await service.create_package(package_data)

        assert result is not None
        assert result.id is not None
        assert result.venue_id == sample_venue_id
        assert result.package_name == "Birthday Bash"
        assert result.package_type == PackageType.BIRTHDAY
        assert result.base_price == Decimal("299.99")
        assert result.is_active is True
        assert result.includes_cake is True

    @pytest.mark.asyncio
    async def test_create_package_with_default_addons(
        self,
        service: PackageService,
        sample_venue_id: uuid.UUID,
        sample_addon: PartyAddon,
    ):
        """Test package creation with default addons."""
        package_data = PartyPackageCreate(
            venue_id=sample_venue_id,
            package_name="Premium Package",
            package_type=PackageType.VIP,
            base_price=Decimal("499.99"),
            min_guests=10,
            max_guests=30,
            default_addon_ids=[sample_addon.id],
        )

        result = await service.create_package(package_data)

        assert result is not None
        assert len(result.default_addons) == 1
        assert result.default_addons[0].addon_id == sample_addon.id

    @pytest.mark.asyncio
    async def test_create_package_minimum_fields(
        self,
        service: PackageService,
        sample_venue_id: uuid.UUID,
    ):
        """Test package creation with minimum required fields."""
        package_data = PartyPackageCreate(
            venue_id=sample_venue_id,
            package_name="Basic Package",
            base_price=Decimal("149.99"),
        )

        result = await service.create_package(package_data)

        assert result is not None
        assert result.package_name == "Basic Package"
        assert result.package_type == PackageType.BIRTHDAY  # default
        assert result.duration_minutes == 120  # default


class TestPackageServiceGet:
    """Tests for PackageService.get_package method."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> PackageService:
        return PackageService(db_session)

    @pytest.mark.asyncio
    async def test_get_package_success(
        self,
        service: PackageService,
        sample_package: PartyPackage,
    ):
        """Test successful package retrieval."""
        result = await service.get_package(sample_package.id)

        assert result is not None
        assert result.id == sample_package.id
        assert result.package_name == sample_package.package_name

    @pytest.mark.asyncio
    async def test_get_package_not_found(self, service: PackageService):
        """Test package retrieval when not found."""
        random_id = uuid.uuid4()
        result = await service.get_package(random_id)

        assert result is None


class TestPackageServiceList:
    """Tests for PackageService.list_packages method."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> PackageService:
        return PackageService(db_session)

    @pytest.mark.asyncio
    async def test_list_packages_empty(
        self,
        service: PackageService,
        sample_venue_id: uuid.UUID,
    ):
        """Test listing packages when none exist."""
        pagination = PaginationParams(page=1, page_size=10)
        packages, total = await service.list_packages(sample_venue_id, pagination)

        assert packages == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_packages_with_data(
        self,
        service: PackageService,
        sample_package: PartyPackage,
        sample_venue_id: uuid.UUID,
    ):
        """Test listing packages with existing data."""
        pagination = PaginationParams(page=1, page_size=10)
        packages, total = await service.list_packages(sample_venue_id, pagination)

        assert total == 1
        assert len(packages) == 1
        assert packages[0].id == sample_package.id

    @pytest.mark.asyncio
    async def test_list_packages_filter_by_type(
        self,
        service: PackageService,
        db_session: AsyncSession,
        sample_venue_id: uuid.UUID,
        package_factory,
    ):
        """Test filtering packages by type."""
        # Create packages of different types
        birthday_pkg = package_factory.create(
            venue_id=sample_venue_id,
            package_type=PackageType.BIRTHDAY,
        )
        corporate_pkg = package_factory.create(
            venue_id=sample_venue_id,
            package_type=PackageType.CORPORATE,
        )
        db_session.add_all([birthday_pkg, corporate_pkg])
        await db_session.flush()

        pagination = PaginationParams(page=1, page_size=10)
        packages, total = await service.list_packages(
            sample_venue_id,
            pagination,
            package_type="birthday",
        )

        assert total == 1
        assert packages[0].package_type == PackageType.BIRTHDAY

    @pytest.mark.asyncio
    async def test_list_packages_filter_by_featured(
        self,
        service: PackageService,
        db_session: AsyncSession,
        sample_venue_id: uuid.UUID,
        package_factory,
    ):
        """Test filtering packages by featured status."""
        featured_pkg = package_factory.create(
            venue_id=sample_venue_id,
            is_featured=True,
        )
        regular_pkg = package_factory.create(
            venue_id=sample_venue_id,
            is_featured=False,
        )
        db_session.add_all([featured_pkg, regular_pkg])
        await db_session.flush()

        pagination = PaginationParams(page=1, page_size=10)
        packages, total = await service.list_packages(
            sample_venue_id,
            pagination,
            is_featured=True,
        )

        assert total == 1
        assert packages[0].is_featured is True

    @pytest.mark.asyncio
    async def test_list_packages_pagination(
        self,
        service: PackageService,
        db_session: AsyncSession,
        sample_venue_id: uuid.UUID,
        package_factory,
    ):
        """Test pagination works correctly."""
        # Create 15 packages
        for i in range(15):
            pkg = package_factory.create(venue_id=sample_venue_id)
            db_session.add(pkg)
        await db_session.flush()

        # Get first page
        pagination = PaginationParams(page=1, page_size=10)
        packages, total = await service.list_packages(sample_venue_id, pagination)

        assert total == 15
        assert len(packages) == 10

        # Get second page
        pagination = PaginationParams(page=2, page_size=10)
        packages, total = await service.list_packages(sample_venue_id, pagination)

        assert total == 15
        assert len(packages) == 5


class TestPackageServiceUpdate:
    """Tests for PackageService.update_package method."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> PackageService:
        return PackageService(db_session)

    @pytest.mark.asyncio
    async def test_update_package_success(
        self,
        service: PackageService,
        sample_package: PartyPackage,
    ):
        """Test successful package update."""
        update_data = PartyPackageUpdate(
            package_name="Updated Package Name",
            base_price=Decimal("399.99"),
            is_featured=True,
        )

        result = await service.update_package(sample_package.id, update_data)

        assert result is not None
        assert result.package_name == "Updated Package Name"
        assert result.base_price == Decimal("399.99")
        assert result.is_featured is True

    @pytest.mark.asyncio
    async def test_update_package_partial(
        self,
        service: PackageService,
        sample_package: PartyPackage,
    ):
        """Test partial package update."""
        original_name = sample_package.package_name
        update_data = PartyPackageUpdate(base_price=Decimal("199.99"))

        result = await service.update_package(sample_package.id, update_data)

        assert result is not None
        assert result.package_name == original_name
        assert result.base_price == Decimal("199.99")

    @pytest.mark.asyncio
    async def test_update_package_not_found(self, service: PackageService):
        """Test update when package doesn't exist."""
        random_id = uuid.uuid4()
        update_data = PartyPackageUpdate(package_name="New Name")

        result = await service.update_package(random_id, update_data)

        assert result is None


class TestPackageServiceDelete:
    """Tests for PackageService.delete_package method."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> PackageService:
        return PackageService(db_session)

    @pytest.mark.asyncio
    async def test_delete_package_soft(
        self,
        service: PackageService,
        sample_package: PartyPackage,
    ):
        """Test soft delete (deactivate) package."""
        result = await service.delete_package(sample_package.id)

        assert result is True

        # Verify package is deactivated
        package = await service.get_package(sample_package.id)
        assert package.is_active is False

    @pytest.mark.asyncio
    async def test_delete_package_hard(
        self,
        service: PackageService,
        sample_package: PartyPackage,
    ):
        """Test hard delete package."""
        result = await service.delete_package(sample_package.id, hard_delete=True)

        assert result is True

        # Verify package is gone
        package = await service.get_package(sample_package.id)
        assert package is None

    @pytest.mark.asyncio
    async def test_delete_package_not_found(self, service: PackageService):
        """Test delete when package doesn't exist."""
        random_id = uuid.uuid4()
        result = await service.delete_package(random_id)

        assert result is False


class TestPackageServiceAddons:
    """Tests for PackageService addon management methods."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> PackageService:
        return PackageService(db_session)

    @pytest.mark.asyncio
    async def test_add_default_addon(
        self,
        service: PackageService,
        sample_package: PartyPackage,
        sample_addon: PartyAddon,
    ):
        """Test adding a default addon to a package."""
        result = await service.add_default_addon(
            package_id=sample_package.id,
            addon_id=sample_addon.id,
            quantity=2,
            is_included_free=True,
        )

        assert result is not None
        assert result.package_id == sample_package.id
        assert result.addon_id == sample_addon.id
        assert result.quantity == 2
        assert result.is_included_free is True

    @pytest.mark.asyncio
    async def test_add_default_addon_with_discount(
        self,
        service: PackageService,
        sample_package: PartyPackage,
        sample_addon: PartyAddon,
    ):
        """Test adding a discounted addon to a package."""
        result = await service.add_default_addon(
            package_id=sample_package.id,
            addon_id=sample_addon.id,
            is_included_free=False,
            discount_percentage=20.0,
        )

        assert result is not None
        assert result.is_included_free is False
        assert float(result.discount_percentage) == 20.0

    @pytest.mark.asyncio
    async def test_add_default_addon_package_not_found(
        self,
        service: PackageService,
        sample_addon: PartyAddon,
    ):
        """Test adding addon when package doesn't exist."""
        random_id = uuid.uuid4()
        result = await service.add_default_addon(
            package_id=random_id,
            addon_id=sample_addon.id,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_remove_default_addon(
        self,
        service: PackageService,
        sample_package: PartyPackage,
        sample_addon: PartyAddon,
    ):
        """Test removing a default addon from a package."""
        # First add the addon
        await service.add_default_addon(
            package_id=sample_package.id,
            addon_id=sample_addon.id,
        )

        # Then remove it
        result = await service.remove_default_addon(
            package_id=sample_package.id,
            addon_id=sample_addon.id,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_remove_default_addon_not_found(
        self,
        service: PackageService,
        sample_package: PartyPackage,
    ):
        """Test removing addon that doesn't exist."""
        random_id = uuid.uuid4()
        result = await service.remove_default_addon(
            package_id=sample_package.id,
            addon_id=random_id,
        )

        assert result is False


class TestPackageServiceCount:
    """Tests for PackageService.get_venue_package_count method."""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> PackageService:
        return PackageService(db_session)

    @pytest.mark.asyncio
    async def test_get_venue_package_count_empty(
        self,
        service: PackageService,
        sample_venue_id: uuid.UUID,
    ):
        """Test count when no packages exist."""
        count = await service.get_venue_package_count(sample_venue_id)
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_venue_package_count_with_data(
        self,
        service: PackageService,
        sample_package: PartyPackage,
        sample_venue_id: uuid.UUID,
    ):
        """Test count with existing packages."""
        count = await service.get_venue_package_count(sample_venue_id)
        assert count == 1

    @pytest.mark.asyncio
    async def test_get_venue_package_count_only_active(
        self,
        service: PackageService,
        db_session: AsyncSession,
        sample_venue_id: uuid.UUID,
        package_factory,
    ):
        """Test count only includes active packages."""
        active_pkg = package_factory.create(venue_id=sample_venue_id, is_active=True)
        inactive_pkg = package_factory.create(venue_id=sample_venue_id, is_active=False)
        db_session.add_all([active_pkg, inactive_pkg])
        await db_session.flush()

        count = await service.get_venue_package_count(sample_venue_id)
        assert count == 1
