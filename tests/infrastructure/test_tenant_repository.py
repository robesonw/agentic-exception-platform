"""
Unit tests for TenantRepository.

Tests:
- Get tenant by ID
- List tenants with various filter combinations
- Update tenant status workflow
- Tenant isolation enforcement
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.infrastructure.db.models import Base, Tenant, TenantStatus
from src.infrastructure.repositories.tenant_repository import TenantRepository
from src.repository.dto import TenantFilter

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_session():
    """Create a test database session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Create tenant table manually for SQLite compatibility
    async with engine.begin() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tenant (
                tenant_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
            """
        )
    
    # Create session factory
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with async_session() as session:
        yield session
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.execute("DROP TABLE IF EXISTS tenant")
    
    await engine.dispose()


@pytest.fixture
async def sample_tenants(test_session: AsyncSession):
    """Create sample tenants for testing."""
    tenants = [
        Tenant(
            tenant_id="tenant_001",
            name="Finance Tenant",
            status=TenantStatus.ACTIVE,
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        ),
        Tenant(
            tenant_id="tenant_002",
            name="Healthcare Tenant",
            status=TenantStatus.ACTIVE,
            created_at=datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
        ),
        Tenant(
            tenant_id="tenant_003",
            name="Retail Tenant",
            status=TenantStatus.SUSPENDED,
            created_at=datetime(2024, 1, 3, 12, 0, 0, tzinfo=timezone.utc),
        ),
        Tenant(
            tenant_id="tenant_004",
            name="Finance Corp",
            status=TenantStatus.ARCHIVED,
            created_at=datetime(2024, 1, 4, 12, 0, 0, tzinfo=timezone.utc),
        ),
    ]
    
    test_session.add_all(tenants)
    await test_session.commit()
    
    # Refresh all tenants
    for tenant in tenants:
        await test_session.refresh(tenant)
    
    return tenants


class TestTenantRepositoryGetTenant:
    """Test get_tenant method."""

    @pytest.mark.asyncio
    async def test_get_existing_tenant(self, test_session: AsyncSession, sample_tenants):
        """Test getting an existing tenant."""
        repo = TenantRepository(test_session)
        
        tenant = await repo.get_tenant("tenant_001")
        
        assert tenant is not None
        assert tenant.tenant_id == "tenant_001"
        assert tenant.name == "Finance Tenant"
        assert tenant.status == TenantStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_nonexistent_tenant(self, test_session: AsyncSession):
        """Test getting a non-existent tenant returns None."""
        repo = TenantRepository(test_session)
        
        tenant = await repo.get_tenant("nonexistent")
        
        assert tenant is None

    @pytest.mark.asyncio
    async def test_get_tenant_empty_id(self, test_session: AsyncSession):
        """Test that empty tenant_id raises ValueError."""
        repo = TenantRepository(test_session)
        
        with pytest.raises(ValueError, match="tenant_id is required"):
            await repo.get_tenant("")


class TestTenantRepositoryListTenants:
    """Test list_tenants method."""

    @pytest.mark.asyncio
    async def test_list_all_tenants(self, test_session: AsyncSession, sample_tenants):
        """Test listing all tenants."""
        repo = TenantRepository(test_session)
        
        tenants = await repo.list_tenants()
        
        assert len(tenants) == 4
        # Should be ordered by created_at descending (newest first)
        assert tenants[0].tenant_id == "tenant_004"
        assert tenants[3].tenant_id == "tenant_001"

    @pytest.mark.asyncio
    async def test_list_tenants_filter_by_name(self, test_session: AsyncSession, sample_tenants):
        """Test filtering tenants by name."""
        repo = TenantRepository(test_session)
        
        # Filter by partial name match
        filters = TenantFilter(name="Finance")
        tenants = await repo.list_tenants(filters)
        
        assert len(tenants) == 2
        assert all("Finance" in tenant.name for tenant in tenants)
        assert "tenant_001" in [t.tenant_id for t in tenants]
        assert "tenant_004" in [t.tenant_id for t in tenants]

    @pytest.mark.asyncio
    async def test_list_tenants_filter_by_status(self, test_session: AsyncSession, sample_tenants):
        """Test filtering tenants by status."""
        repo = TenantRepository(test_session)
        
        # Filter by ACTIVE status
        filters = TenantFilter(status=TenantStatus.ACTIVE)
        tenants = await repo.list_tenants(filters)
        
        assert len(tenants) == 2
        assert all(tenant.status == TenantStatus.ACTIVE for tenant in tenants)
        assert "tenant_001" in [t.tenant_id for t in tenants]
        assert "tenant_002" in [t.tenant_id for t in tenants]

    @pytest.mark.asyncio
    async def test_list_tenants_filter_by_created_from(self, test_session: AsyncSession, sample_tenants):
        """Test filtering tenants by created_from date."""
        repo = TenantRepository(test_session)
        
        # Filter by created_from (should include tenants created on or after this date)
        filters = TenantFilter(created_from=datetime(2024, 1, 3, 0, 0, 0, tzinfo=timezone.utc))
        tenants = await repo.list_tenants(filters)
        
        assert len(tenants) == 2
        assert "tenant_003" in [t.tenant_id for t in tenants]
        assert "tenant_004" in [t.tenant_id for t in tenants]

    @pytest.mark.asyncio
    async def test_list_tenants_filter_by_created_to(self, test_session: AsyncSession, sample_tenants):
        """Test filtering tenants by created_to date."""
        repo = TenantRepository(test_session)
        
        # Filter by created_to (should include tenants created on or before this date)
        filters = TenantFilter(created_to=datetime(2024, 1, 2, 23, 59, 59, tzinfo=timezone.utc))
        tenants = await repo.list_tenants(filters)
        
        assert len(tenants) == 2
        assert "tenant_001" in [t.tenant_id for t in tenants]
        assert "tenant_002" in [t.tenant_id for t in tenants]

    @pytest.mark.asyncio
    async def test_list_tenants_filter_combinations(self, test_session: AsyncSession, sample_tenants):
        """Test combining multiple filters."""
        repo = TenantRepository(test_session)
        
        # Filter by name AND status
        filters = TenantFilter(name="Finance", status=TenantStatus.ACTIVE)
        tenants = await repo.list_tenants(filters)
        
        assert len(tenants) == 1
        assert tenants[0].tenant_id == "tenant_001"
        assert tenants[0].name == "Finance Tenant"
        assert tenants[0].status == TenantStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_list_tenants_no_matches(self, test_session: AsyncSession, sample_tenants):
        """Test filtering with no matches."""
        repo = TenantRepository(test_session)
        
        # Filter that matches nothing
        filters = TenantFilter(name="Nonexistent", status=TenantStatus.ACTIVE)
        tenants = await repo.list_tenants(filters)
        
        assert len(tenants) == 0


class TestTenantRepositoryUpdateStatus:
    """Test update_tenant_status method."""

    @pytest.mark.asyncio
    async def test_update_status_active_to_suspended(self, test_session: AsyncSession, sample_tenants):
        """Test updating tenant status from ACTIVE to SUSPENDED."""
        repo = TenantRepository(test_session)
        
        tenant = await repo.update_tenant_status("tenant_001", TenantStatus.SUSPENDED)
        
        assert tenant.tenant_id == "tenant_001"
        assert tenant.status == TenantStatus.SUSPENDED
        
        # Verify in database
        updated = await repo.get_tenant("tenant_001")
        assert updated.status == TenantStatus.SUSPENDED

    @pytest.mark.asyncio
    async def test_update_status_suspended_to_archived(self, test_session: AsyncSession, sample_tenants):
        """Test updating tenant status from SUSPENDED to ARCHIVED."""
        repo = TenantRepository(test_session)
        
        tenant = await repo.update_tenant_status("tenant_003", TenantStatus.ARCHIVED)
        
        assert tenant.tenant_id == "tenant_003"
        assert tenant.status == TenantStatus.ARCHIVED

    @pytest.mark.asyncio
    async def test_update_status_archived_to_active(self, test_session: AsyncSession, sample_tenants):
        """Test updating tenant status from ARCHIVED to ACTIVE."""
        repo = TenantRepository(test_session)
        
        tenant = await repo.update_tenant_status("tenant_004", TenantStatus.ACTIVE)
        
        assert tenant.tenant_id == "tenant_004"
        assert tenant.status == TenantStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_update_status_nonexistent_tenant(self, test_session: AsyncSession):
        """Test updating status for non-existent tenant raises ValueError."""
        repo = TenantRepository(test_session)
        
        with pytest.raises(ValueError, match="Tenant not found"):
            await repo.update_tenant_status("nonexistent", TenantStatus.ACTIVE)

    @pytest.mark.asyncio
    async def test_update_status_empty_id(self, test_session: AsyncSession):
        """Test that empty tenant_id raises ValueError."""
        repo = TenantRepository(test_session)
        
        with pytest.raises(ValueError, match="tenant_id is required"):
            await repo.update_tenant_status("", TenantStatus.ACTIVE)


class TestTenantRepositoryAbstractBase:
    """Test AbstractBaseRepository interface implementations."""

    @pytest.mark.asyncio
    async def test_get_by_id(self, test_session: AsyncSession, sample_tenants):
        """Test get_by_id method (implements AbstractBaseRepository)."""
        repo = TenantRepository(test_session)
        
        # For TenantRepository, id is the tenant_id itself
        tenant = await repo.get_by_id("tenant_001", tenant_id="ignored")
        
        assert tenant is not None
        assert tenant.tenant_id == "tenant_001"

    @pytest.mark.asyncio
    async def test_list_by_tenant(self, test_session: AsyncSession, sample_tenants):
        """Test list_by_tenant method (implements AbstractBaseRepository)."""
        repo = TenantRepository(test_session)
        
        # For TenantRepository, tenant_id parameter is ignored
        result = await repo.list_by_tenant(tenant_id="ignored", page=1, page_size=2)
        
        assert result.total == 4
        assert len(result.items) == 2
        assert result.page == 1
        assert result.page_size == 2

