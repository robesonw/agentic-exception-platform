"""
Unit tests for TenantPolicyPackRepository.

Tests cover:
- Version creation
- Listing by tenant
- Retrieving latest version
- Tenant isolation enforcement
"""

import pytest
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from src.infrastructure.db.models import TenantPolicyPackVersion
from src.infrastructure.repositories.tenant_policy_pack_repository import TenantPolicyPackRepository

# Create test base
TestBase = declarative_base()


# Define minimal models for SQLite testing
class TestTenant(TestBase):
    __tablename__ = "tenant"
    tenant_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class TestTenantPolicyPackVersion(TestBase):
    __tablename__ = "tenant_policy_pack_version"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.tenant_id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    pack_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    
    tenant = relationship("TestTenant", backref="tenant_policy_packs")


@pytest.fixture
async def test_engine():
    """Create an in-memory SQLite test engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables manually for SQLite compatibility
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS tenant (
                tenant_id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tenant_policy_pack_version (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                pack_json TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                UNIQUE(tenant_id, version),
                FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS ix_tenant_policy_pack_version_tenant_id ON tenant_policy_pack_version(tenant_id);
            """
            )
        )
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS tenant_policy_pack_version;"))
        await conn.execute(text("DROP TABLE IF EXISTS tenant;"))
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create an async session for tests."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest.fixture
async def setup_tenants(test_session: AsyncSession):
    """Set up sample tenants for testing."""
    from sqlalchemy import text
    await test_session.execute(
        text("INSERT INTO tenant (tenant_id, name) VALUES ('tenant_001', 'Finance Tenant')")
    )
    await test_session.execute(
        text("INSERT INTO tenant (tenant_id, name) VALUES ('tenant_002', 'Healthcare Tenant')")
    )
    await test_session.commit()


@pytest.fixture
async def tenant_policy_pack_repo(test_session: AsyncSession) -> TenantPolicyPackRepository:
    """Provide a TenantPolicyPackRepository instance for tests."""
    return TenantPolicyPackRepository(test_session)


@pytest.fixture
async def setup_tenant_policy_packs(tenant_policy_pack_repo: TenantPolicyPackRepository, setup_tenants):
    """Set up sample tenant policy packs for testing."""
    # Tenant 001 packs
    pack1 = TenantPolicyPackVersion(
        tenant_id="tenant_001",
        version=1,
        pack_json={"tenantId": "tenant_001", "version": "1.0.0", "policies": {}},
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )
    pack2 = TenantPolicyPackVersion(
        tenant_id="tenant_001",
        version=2,
        pack_json={"tenantId": "tenant_001", "version": "2.0.0", "policies": {}},
        created_at=datetime(2023, 2, 1, tzinfo=timezone.utc),
    )
    pack3 = TenantPolicyPackVersion(
        tenant_id="tenant_001",
        version=3,
        pack_json={"tenantId": "tenant_001", "version": "3.0.0", "policies": {}},
        created_at=datetime(2023, 3, 1, tzinfo=timezone.utc),
    )
    
    # Tenant 002 packs
    pack4 = TenantPolicyPackVersion(
        tenant_id="tenant_002",
        version=1,
        pack_json={"tenantId": "tenant_002", "version": "1.0.0", "policies": {}},
        created_at=datetime(2023, 1, 15, tzinfo=timezone.utc),
    )
    pack5 = TenantPolicyPackVersion(
        tenant_id="tenant_002",
        version=2,
        pack_json={"tenantId": "tenant_002", "version": "2.0.0", "policies": {}},
        created_at=datetime(2023, 2, 15, tzinfo=timezone.utc),
    )
    
    tenant_policy_pack_repo.session.add_all([pack1, pack2, pack3, pack4, pack5])
    await tenant_policy_pack_repo.session.commit()
    
    # Refresh all packs to ensure they're loaded
    for pack in [pack1, pack2, pack3, pack4, pack5]:
        await tenant_policy_pack_repo.session.refresh(pack)


class TestTenantPolicyPackRepository:
    @pytest.mark.asyncio
    async def test_get_tenant_policy_pack(self, tenant_policy_pack_repo: TenantPolicyPackRepository, setup_tenant_policy_packs):
        """Test retrieving a tenant policy pack by tenant_id and version."""
        pack = await tenant_policy_pack_repo.get_tenant_policy_pack("tenant_001", 2)
        assert pack is not None
        assert pack.tenant_id == "tenant_001"
        assert pack.version == 2
        assert pack.pack_json["version"] == "2.0.0"

        not_found = await tenant_policy_pack_repo.get_tenant_policy_pack("tenant_001", 99)
        assert not_found is None

        with pytest.raises(ValueError, match="tenant_id is required"):
            await tenant_policy_pack_repo.get_tenant_policy_pack("", 1)

        with pytest.raises(ValueError, match="version must be >= 1"):
            await tenant_policy_pack_repo.get_tenant_policy_pack("tenant_001", 0)

    @pytest.mark.asyncio
    async def test_get_latest_tenant_policy_pack(self, tenant_policy_pack_repo: TenantPolicyPackRepository, setup_tenant_policy_packs):
        """Test retrieving the latest tenant policy pack for a tenant."""
        latest = await tenant_policy_pack_repo.get_latest_tenant_policy_pack("tenant_001")
        assert latest is not None
        assert latest.tenant_id == "tenant_001"
        assert latest.version == 3  # Highest version
        assert latest.pack_json["version"] == "3.0.0"

        latest_tenant2 = await tenant_policy_pack_repo.get_latest_tenant_policy_pack("tenant_002")
        assert latest_tenant2 is not None
        assert latest_tenant2.tenant_id == "tenant_002"
        assert latest_tenant2.version == 2

        not_found = await tenant_policy_pack_repo.get_latest_tenant_policy_pack("non_existent_tenant")
        assert not_found is None

        with pytest.raises(ValueError, match="tenant_id is required"):
            await tenant_policy_pack_repo.get_latest_tenant_policy_pack("")

    @pytest.mark.asyncio
    async def test_get_latest_tenant_policy_pack_version_ordering(self, tenant_policy_pack_repo: TenantPolicyPackRepository, setup_tenants):
        """Test that latest pack uses highest version number (not created_at)."""
        # Create packs with same version but different created_at
        pack1 = TenantPolicyPackVersion(
            tenant_id="tenant_001",
            version=1,
            pack_json={"tenantId": "tenant_001", "version": "1.0.0"},
            created_at=datetime(2023, 3, 1, tzinfo=timezone.utc),
        )
        pack2 = TenantPolicyPackVersion(
            tenant_id="tenant_001",
            version=2,
            pack_json={"tenantId": "tenant_001", "version": "2.0.0"},
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),  # Older than pack1
        )
        
        tenant_policy_pack_repo.session.add_all([pack1, pack2])
        await tenant_policy_pack_repo.session.commit()

        # Latest should be version 2 (higher version), not version 1 (newer created_at)
        latest = await tenant_policy_pack_repo.get_latest_tenant_policy_pack("tenant_001")
        assert latest is not None
        assert latest.version == 2

    @pytest.mark.asyncio
    async def test_create_tenant_policy_pack_version(self, tenant_policy_pack_repo: TenantPolicyPackRepository, setup_tenants):
        """Test creating a new tenant policy pack version."""
        pack_json = {
            "tenantId": "tenant_001",
            "version": "1.0.0",
            "policies": {"retention": {"dataTTL": 90}},
        }
        
        created = await tenant_policy_pack_repo.create_tenant_policy_pack_version(
            tenant_id="tenant_001",
            version=1,
            pack_json=pack_json,
        )
        
        assert created is not None
        assert created.tenant_id == "tenant_001"
        assert created.version == 1
        assert created.pack_json == pack_json
        assert created.id is not None

        # Verify it can be retrieved
        retrieved = await tenant_policy_pack_repo.get_tenant_policy_pack("tenant_001", 1)
        assert retrieved is not None
        assert retrieved.pack_json == pack_json

    @pytest.mark.asyncio
    async def test_create_tenant_policy_pack_version_duplicate(self, tenant_policy_pack_repo: TenantPolicyPackRepository, setup_tenant_policy_packs):
        """Test that creating a duplicate version raises an error."""
        pack_json = {"tenantId": "tenant_001", "version": "2.0.0"}

        with pytest.raises(ValueError, match="already exists"):
            await tenant_policy_pack_repo.create_tenant_policy_pack_version(
                tenant_id="tenant_001",
                version=2,  # Already exists
                pack_json=pack_json,
            )

    @pytest.mark.asyncio
    async def test_create_tenant_policy_pack_version_validation(self, tenant_policy_pack_repo: TenantPolicyPackRepository):
        """Test validation errors when creating tenant policy pack version."""
        with pytest.raises(ValueError, match="tenant_id is required"):
            await tenant_policy_pack_repo.create_tenant_policy_pack_version("", 1, {})

        with pytest.raises(ValueError, match="version must be >= 1"):
            await tenant_policy_pack_repo.create_tenant_policy_pack_version("tenant_001", 0, {})

        with pytest.raises(ValueError, match="pack_json is required"):
            await tenant_policy_pack_repo.create_tenant_policy_pack_version("tenant_001", 1, {})

    @pytest.mark.asyncio
    async def test_list_tenant_policy_packs(self, tenant_policy_pack_repo: TenantPolicyPackRepository, setup_tenant_policy_packs):
        """Test listing tenant policy packs for a tenant."""
        tenant1_packs = await tenant_policy_pack_repo.list_tenant_policy_packs("tenant_001")
        
        assert len(tenant1_packs) == 3
        assert all(pack.tenant_id == "tenant_001" for pack in tenant1_packs)
        # Should be ordered by version (descending)
        assert tenant1_packs[0].version == 3
        assert tenant1_packs[1].version == 2
        assert tenant1_packs[2].version == 1

        tenant2_packs = await tenant_policy_pack_repo.list_tenant_policy_packs("tenant_002")
        assert len(tenant2_packs) == 2
        assert all(pack.tenant_id == "tenant_002" for pack in tenant2_packs)

        non_existent = await tenant_policy_pack_repo.list_tenant_policy_packs("non_existent_tenant")
        assert len(non_existent) == 0

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, tenant_policy_pack_repo: TenantPolicyPackRepository, setup_tenant_policy_packs):
        """Test that tenant isolation is enforced - tenants cannot access each other's packs."""
        # Tenant 001 should only see their own packs
        tenant1_packs = await tenant_policy_pack_repo.list_tenant_policy_packs("tenant_001")
        assert len(tenant1_packs) == 3
        assert all(pack.tenant_id == "tenant_001" for pack in tenant1_packs)
        
        # Tenant 002 should only see their own packs
        tenant2_packs = await tenant_policy_pack_repo.list_tenant_policy_packs("tenant_002")
        assert len(tenant2_packs) == 2
        assert all(pack.tenant_id == "tenant_002" for pack in tenant2_packs)
        
        # Tenant 001 should not be able to retrieve Tenant 002's packs
        tenant2_pack = await tenant_policy_pack_repo.get_tenant_policy_pack("tenant_001", 1)
        assert tenant2_pack is not None
        assert tenant2_pack.tenant_id == "tenant_001"  # Their own pack, not tenant_002's
        
        # Try to get tenant_002's pack with tenant_001's ID - should return None
        # (This tests that get_by_id enforces tenant isolation)
        tenant2_pack_id = None
        for pack in tenant2_packs:
            tenant2_pack_id = pack.id
            break
        
        if tenant2_pack_id:
            # Should return None because tenant_id doesn't match
            retrieved = await tenant_policy_pack_repo.get_by_id(str(tenant2_pack_id), tenant_id="tenant_001")
            assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_by_id(self, tenant_policy_pack_repo: TenantPolicyPackRepository, setup_tenant_policy_packs):
        """Test get_by_id method with tenant isolation."""
        # Get a pack to find its ID
        pack = await tenant_policy_pack_repo.get_tenant_policy_pack("tenant_001", 1)
        assert pack is not None
        pack_id = pack.id

        # Should retrieve with correct tenant_id
        retrieved = await tenant_policy_pack_repo.get_by_id(str(pack_id), tenant_id="tenant_001")
        assert retrieved is not None
        assert retrieved.id == pack_id
        assert retrieved.tenant_id == "tenant_001"
        assert retrieved.version == 1

        # Should return None with wrong tenant_id (tenant isolation)
        retrieved_wrong_tenant = await tenant_policy_pack_repo.get_by_id(str(pack_id), tenant_id="tenant_002")
        assert retrieved_wrong_tenant is None

        not_found = await tenant_policy_pack_repo.get_by_id("99999", tenant_id="tenant_001")
        assert not_found is None

        invalid_id = await tenant_policy_pack_repo.get_by_id("not_a_number", tenant_id="tenant_001")
        assert invalid_id is None

        with pytest.raises(ValueError, match="tenant_id is required"):
            await tenant_policy_pack_repo.get_by_id("1", tenant_id="")

    @pytest.mark.asyncio
    async def test_list_by_tenant(self, tenant_policy_pack_repo: TenantPolicyPackRepository, setup_tenant_policy_packs):
        """Test list_by_tenant method with pagination and tenant isolation."""
        # Test pagination
        result = await tenant_policy_pack_repo.list_by_tenant(
            tenant_id="tenant_001",
            page=1,
            page_size=2,
        )
        
        assert result.total == 3
        assert len(result.items) == 2
        assert result.page == 1
        assert result.page_size == 2
        assert result.total_pages == 2
        assert all(pack.tenant_id == "tenant_001" for pack in result.items)

        # Test second page
        result_page2 = await tenant_policy_pack_repo.list_by_tenant(
            tenant_id="tenant_001",
            page=2,
            page_size=2,
        )
        
        assert result_page2.total == 3
        assert len(result_page2.items) == 1
        assert result_page2.page == 2
        assert result_page2.page_size == 2
        assert result_page2.total_pages == 2

        # Test tenant isolation - tenant_002 should only see their own packs
        result_tenant2 = await tenant_policy_pack_repo.list_by_tenant(
            tenant_id="tenant_002",
            page=1,
            page_size=10,
        )
        
        assert result_tenant2.total == 2
        assert all(pack.tenant_id == "tenant_002" for pack in result_tenant2.items)

        with pytest.raises(ValueError, match="tenant_id is required"):
            await tenant_policy_pack_repo.list_by_tenant("", page=1, page_size=10)

    @pytest.mark.asyncio
    async def test_create_multiple_versions(self, tenant_policy_pack_repo: TenantPolicyPackRepository, setup_tenants):
        """Test creating multiple versions for the same tenant."""
        # Create version 1
        pack1 = await tenant_policy_pack_repo.create_tenant_policy_pack_version(
            tenant_id="tenant_001",
            version=1,
            pack_json={"tenantId": "tenant_001", "version": "1.0.0"},
        )
        assert pack1.version == 1

        # Create version 2
        pack2 = await tenant_policy_pack_repo.create_tenant_policy_pack_version(
            tenant_id="tenant_001",
            version=2,
            pack_json={"tenantId": "tenant_001", "version": "2.0.0"},
        )
        assert pack2.version == 2

        # Create version 3
        pack3 = await tenant_policy_pack_repo.create_tenant_policy_pack_version(
            tenant_id="tenant_001",
            version=3,
            pack_json={"tenantId": "tenant_001", "version": "3.0.0"},
        )
        assert pack3.version == 3

        # List all versions
        all_packs = await tenant_policy_pack_repo.list_tenant_policy_packs("tenant_001")
        assert len(all_packs) == 3
        assert all_packs[0].version == 3  # Latest first
        assert all_packs[1].version == 2
        assert all_packs[2].version == 1

        # Latest should be version 3
        latest = await tenant_policy_pack_repo.get_latest_tenant_policy_pack("tenant_001")
        assert latest is not None
        assert latest.version == 3


