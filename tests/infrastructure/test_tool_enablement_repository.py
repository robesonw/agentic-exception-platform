"""
Unit and integration tests for ToolEnablementRepository.

Tests cover:
- CRUD operations
- Tenant isolation
- Default enablement behavior
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db.models import ToolEnablement
from src.infrastructure.repositories.tool_enablement_repository import ToolEnablementRepository


@pytest.fixture
async def test_engine():
    """Create an in-memory SQLite test engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables manually for SQLite compatibility (one statement at a time)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE IF NOT EXISTS tenant (tenant_id TEXT PRIMARY KEY, name TEXT NOT NULL);"))
        await conn.execute(text("CREATE TABLE IF NOT EXISTS tool_definition (tool_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, tenant_id TEXT, type TEXT NOT NULL, config TEXT NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE);"))
        await conn.execute(text("CREATE TABLE IF NOT EXISTS tool_enablement (tenant_id TEXT NOT NULL, tool_id INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, PRIMARY KEY (tenant_id, tool_id), FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE, FOREIGN KEY (tool_id) REFERENCES tool_definition(tool_id) ON DELETE CASCADE);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tool_enablement_tenant_id ON tool_enablement(tenant_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tool_enablement_tool_id ON tool_enablement(tool_id);"))

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS tool_enablement;"))
        await conn.execute(text("DROP TABLE IF EXISTS tool_definition;"))
        await conn.execute(text("DROP TABLE IF EXISTS tenant;"))
    await engine.dispose()


@pytest.fixture
async def setup_test_data(test_engine: AsyncSession):
    """Set up test data."""
    # Create tenants
    await test_engine.execute(
        text("INSERT INTO tenant (tenant_id, name) VALUES ('TENANT_001', 'Tenant One')")
    )
    await test_engine.execute(
        text("INSERT INTO tenant (tenant_id, name) VALUES ('TENANT_002', 'Tenant Two')")
    )
    
    # Create tool definitions
    await test_engine.execute(
        text(
            "INSERT INTO tool_definition (tool_id, tenant_id, name, type, config) "
            "VALUES (1, 'TENANT_001', 'test_tool', 'http', '{}')"
        )
    )
    await test_engine.execute(
        text(
            "INSERT INTO tool_definition (tool_id, tenant_id, name, type, config) "
            "VALUES (2, NULL, 'global_tool', 'http', '{}')"
        )
    )
    
    await test_engine.commit()


class TestToolEnablementRepository:
    """Tests for ToolEnablementRepository."""

    @pytest.mark.asyncio
    async def test_get_enablement_not_found(self, test_engine, setup_test_data):
        """Test getting enablement when record doesn't exist."""
        repo = ToolEnablementRepository(test_engine)
        
        enablement = await repo.get_enablement("TENANT_001", 1)
        assert enablement is None

    @pytest.mark.asyncio
    async def test_is_enabled_default(self, test_engine, setup_test_data):
        """Test that tools are enabled by default."""
        repo = ToolEnablementRepository(test_engine)
        
        # No record exists, should default to enabled
        is_enabled = await repo.is_enabled("TENANT_001", 1)
        assert is_enabled is True

    @pytest.mark.asyncio
    async def test_set_enablement_create(self, test_engine, setup_test_data):
        """Test creating a new enablement record."""
        repo = ToolEnablementRepository(test_engine)
        
        enablement = await repo.set_enablement("TENANT_001", 1, enabled=False)
        
        assert enablement.tenant_id == "TENANT_001"
        assert enablement.tool_id == 1
        assert enablement.enabled is False
        assert enablement.created_at is not None

    @pytest.mark.asyncio
    async def test_set_enablement_update(self, test_engine, setup_test_data):
        """Test updating an existing enablement record."""
        repo = ToolEnablementRepository(test_engine)
        
        # Create record
        await repo.set_enablement("TENANT_001", 1, enabled=False)
        await test_engine.commit()
        
        # Update record
        enablement = await repo.set_enablement("TENANT_001", 1, enabled=True)
        
        assert enablement.enabled is True
        assert enablement.updated_at is not None

    @pytest.mark.asyncio
    async def test_is_enabled_after_set(self, test_engine, setup_test_data):
        """Test is_enabled after setting enablement."""
        repo = ToolEnablementRepository(test_engine)
        
        # Set to disabled
        await repo.set_enablement("TENANT_001", 1, enabled=False)
        await test_engine.commit()
        
        is_enabled = await repo.is_enabled("TENANT_001", 1)
        assert is_enabled is False
        
        # Set to enabled
        await repo.set_enablement("TENANT_001", 1, enabled=True)
        await test_engine.commit()
        
        is_enabled = await repo.is_enabled("TENANT_001", 1)
        assert is_enabled is True

    @pytest.mark.asyncio
    async def test_delete_enablement(self, test_engine, setup_test_data):
        """Test deleting an enablement record."""
        repo = ToolEnablementRepository(test_engine)
        
        # Create record
        await repo.set_enablement("TENANT_001", 1, enabled=False)
        await test_engine.commit()
        
        # Delete record
        deleted = await repo.delete_enablement("TENANT_001", 1)
        assert deleted is True
        await test_engine.commit()
        
        # Should default to enabled after deletion
        is_enabled = await repo.is_enabled("TENANT_001", 1)
        assert is_enabled is True

    @pytest.mark.asyncio
    async def test_delete_enablement_not_found(self, test_engine, setup_test_data):
        """Test deleting a non-existent enablement record."""
        repo = ToolEnablementRepository(test_engine)
        
        deleted = await repo.delete_enablement("TENANT_001", 1)
        assert deleted is False

    @pytest.mark.asyncio
    async def test_list_enablements_all(self, test_engine, setup_test_data):
        """Test listing all enablements for a tenant."""
        repo = ToolEnablementRepository(test_engine)
        
        # Create multiple enablements
        await repo.set_enablement("TENANT_001", 1, enabled=True)
        await repo.set_enablement("TENANT_001", 2, enabled=False)
        await test_engine.commit()
        
        enablements = await repo.list_enablements("TENANT_001")
        assert len(enablements) == 2

    @pytest.mark.asyncio
    async def test_list_enablements_enabled_only(self, test_engine, setup_test_data):
        """Test listing only enabled tools."""
        repo = ToolEnablementRepository(test_engine)
        
        # Create multiple enablements
        await repo.set_enablement("TENANT_001", 1, enabled=True)
        await repo.set_enablement("TENANT_001", 2, enabled=False)
        await test_engine.commit()
        
        enablements = await repo.list_enablements("TENANT_001", enabled_only=True)
        assert len(enablements) == 1
        assert enablements[0].tool_id == 1
        assert enablements[0].enabled is True

    @pytest.mark.asyncio
    async def test_list_enablements_disabled_only(self, test_engine, setup_test_data):
        """Test listing only disabled tools."""
        repo = ToolEnablementRepository(test_engine)
        
        # Create multiple enablements
        await repo.set_enablement("TENANT_001", 1, enabled=True)
        await repo.set_enablement("TENANT_001", 2, enabled=False)
        await test_engine.commit()
        
        enablements = await repo.list_enablements("TENANT_001", enabled_only=False)
        assert len(enablements) == 1
        assert enablements[0].tool_id == 2
        assert enablements[0].enabled is False

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, test_engine, setup_test_data):
        """Test that tenants can only see their own enablements."""
        repo = ToolEnablementRepository(test_engine)
        
        # Create enablements for different tenants
        await repo.set_enablement("TENANT_001", 1, enabled=False)
        await repo.set_enablement("TENANT_002", 1, enabled=True)
        await test_engine.commit()
        
        # TENANT_001 should only see their own
        enablements_001 = await repo.list_enablements("TENANT_001")
        assert len(enablements_001) == 1
        assert enablements_001[0].tenant_id == "TENANT_001"
        
        # TENANT_002 should only see their own
        enablements_002 = await repo.list_enablements("TENANT_002")
        assert len(enablements_002) == 1
        assert enablements_002[0].tenant_id == "TENANT_002"

    @pytest.mark.asyncio
    async def test_get_enablement_invalid_tenant_id(self, test_engine, setup_test_data):
        """Test error when tenant_id is empty."""
        repo = ToolEnablementRepository(test_engine)
        
        with pytest.raises(ValueError) as exc_info:
            await repo.get_enablement("", 1)
        
        assert "tenant_id is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_set_enablement_invalid_tool_id(self, test_engine, setup_test_data):
        """Test error when tool_id is invalid."""
        repo = ToolEnablementRepository(test_engine)
        
        with pytest.raises(ValueError) as exc_info:
            await repo.set_enablement("TENANT_001", 0, enabled=True)
        
        assert "Invalid tool_id" in str(exc_info.value)








