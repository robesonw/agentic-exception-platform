"""
Unit tests for ToolDefinitionRepository.

Tests cover:
- Global vs tenant-specific retrieval
- Filtering (name, type)
- Creating global and tenant-scoped tools
- Tenant isolation
"""

import pytest
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from src.infrastructure.db.models import ToolDefinition
from src.infrastructure.repositories.tool_definition_repository import ToolDefinitionRepository
from src.repository.dto import ToolDefinitionCreateDTO, ToolDefinitionFilter

# Create test base
TestBase = declarative_base()


# Define minimal models for SQLite testing
class TestTenant(TestBase):
    __tablename__ = "tenant"
    tenant_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class TestToolDefinition(TestBase):
    __tablename__ = "tool_definition"
    tool_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    tenant_id = Column(String, ForeignKey("tenant.tenant_id", ondelete="CASCADE"), nullable=True, index=True)
    type = Column(String, nullable=False)
    config = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    
    tenant = relationship("TestTenant", backref="tool_definitions")


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
            CREATE TABLE IF NOT EXISTS tool_definition (
                tool_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                tenant_id TEXT,
                type TEXT NOT NULL,
                config TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS ix_tool_definition_tenant_id ON tool_definition(tenant_id);
            """
            )
        )
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS tool_definition;"))
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
async def tool_repo(test_session: AsyncSession) -> ToolDefinitionRepository:
    """Provide a ToolDefinitionRepository instance for tests."""
    return ToolDefinitionRepository(test_session)


@pytest.fixture
async def setup_tools(tool_repo: ToolDefinitionRepository, setup_tenants):
    """Set up sample tools for testing."""
    # Global tools
    global_tool1 = ToolDefinition(
        name="GlobalWebhook",
        tenant_id=None,
        type="webhook",
        config={"endpoint": "https://global.example.com/webhook"},
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )
    global_tool2 = ToolDefinition(
        name="GlobalEmail",
        tenant_id=None,
        type="email",
        config={"smtp_server": "smtp.example.com"},
        created_at=datetime(2023, 2, 1, tzinfo=timezone.utc),
    )
    
    # Tenant 001 tools
    tenant1_tool1 = ToolDefinition(
        name="Tenant1REST",
        tenant_id="tenant_001",
        type="rest",
        config={"endpoint": "https://tenant1.example.com/api"},
        created_at=datetime(2023, 1, 15, tzinfo=timezone.utc),
    )
    tenant1_tool2 = ToolDefinition(
        name="Tenant1Workflow",
        tenant_id="tenant_001",
        type="workflow",
        config={"workflow_id": "wf-001"},
        created_at=datetime(2023, 2, 15, tzinfo=timezone.utc),
    )
    
    # Tenant 002 tools
    tenant2_tool1 = ToolDefinition(
        name="Tenant2REST",
        tenant_id="tenant_002",
        type="rest",
        config={"endpoint": "https://tenant2.example.com/api"},
        created_at=datetime(2023, 1, 20, tzinfo=timezone.utc),
    )
    
    tool_repo.session.add_all([global_tool1, global_tool2, tenant1_tool1, tenant1_tool2, tenant2_tool1])
    await tool_repo.session.commit()
    
    # Refresh all tools
    for tool in [global_tool1, global_tool2, tenant1_tool1, tenant1_tool2, tenant2_tool1]:
        await tool_repo.session.refresh(tool)


class TestToolDefinitionRepositoryGlobalVsTenant:
    """Test global vs tenant-specific retrieval."""

    @pytest.mark.asyncio
    async def test_list_tools_global_only(self, tool_repo: ToolDefinitionRepository, setup_tools):
        """Test listing only global tools when tenant_id is None."""
        tools = await tool_repo.list_tools(tenant_id=None)
        
        assert len(tools) == 2
        assert all(tool.tenant_id is None for tool in tools)
        assert any(tool.name == "GlobalWebhook" for tool in tools)
        assert any(tool.name == "GlobalEmail" for tool in tools)

    @pytest.mark.asyncio
    async def test_list_tools_tenant_with_global(self, tool_repo: ToolDefinitionRepository, setup_tools):
        """Test listing tools for a tenant (global + tenant-scoped)."""
        tools = await tool_repo.list_tools(tenant_id="tenant_001")
        
        # Should include global tools + tenant_001 tools
        assert len(tools) == 4
        global_tools = [t for t in tools if t.tenant_id is None]
        tenant_tools = [t for t in tools if t.tenant_id == "tenant_001"]
        assert len(global_tools) == 2
        assert len(tenant_tools) == 2
        assert any(t.name == "Tenant1REST" for t in tenant_tools)
        assert any(t.name == "Tenant1Workflow" for t in tenant_tools)

    @pytest.mark.asyncio
    async def test_list_tools_tenant_isolation(self, tool_repo: ToolDefinitionRepository, setup_tools):
        """Test that tenants only see their own tools plus global tools."""
        # Tenant 001 should see global + tenant_001 tools
        tenant1_tools = await tool_repo.list_tools(tenant_id="tenant_001")
        tenant1_names = {t.name for t in tenant1_tools}
        assert "GlobalWebhook" in tenant1_names
        assert "GlobalEmail" in tenant1_names
        assert "Tenant1REST" in tenant1_names
        assert "Tenant1Workflow" in tenant1_names
        assert "Tenant2REST" not in tenant1_names  # Should not see tenant_002's tools
        
        # Tenant 002 should see global + tenant_002 tools
        tenant2_tools = await tool_repo.list_tools(tenant_id="tenant_002")
        tenant2_names = {t.name for t in tenant2_tools}
        assert "GlobalWebhook" in tenant2_names
        assert "GlobalEmail" in tenant2_names
        assert "Tenant2REST" in tenant2_names
        assert "Tenant1REST" not in tenant2_names  # Should not see tenant_001's tools

    @pytest.mark.asyncio
    async def test_get_tool_global(self, tool_repo: ToolDefinitionRepository, setup_tools):
        """Test getting a global tool."""
        # Get a global tool
        all_tools = await tool_repo.list_tools(tenant_id=None)
        global_tool = all_tools[0]
        
        # Should be accessible with any tenant_id
        retrieved = await tool_repo.get_tool(global_tool.tool_id, tenant_id="tenant_001")
        assert retrieved is not None
        assert retrieved.tool_id == global_tool.tool_id
        assert retrieved.tenant_id is None
        
        # Should also be accessible with None tenant_id
        retrieved = await tool_repo.get_tool(global_tool.tool_id, tenant_id=None)
        assert retrieved is not None
        assert retrieved.tool_id == global_tool.tool_id

    @pytest.mark.asyncio
    async def test_get_tool_tenant_scoped(self, tool_repo: ToolDefinitionRepository, setup_tools):
        """Test getting a tenant-scoped tool."""
        # Get a tenant_001 tool
        tenant1_tools = await tool_repo.list_tools(tenant_id="tenant_001")
        tenant_tool = [t for t in tenant1_tools if t.tenant_id == "tenant_001"][0]
        
        # Should be accessible by tenant_001
        retrieved = await tool_repo.get_tool(tenant_tool.tool_id, tenant_id="tenant_001")
        assert retrieved is not None
        assert retrieved.tool_id == tenant_tool.tool_id
        assert retrieved.tenant_id == "tenant_001"
        
        # Should NOT be accessible by tenant_002
        retrieved = await tool_repo.get_tool(tenant_tool.tool_id, tenant_id="tenant_002")
        assert retrieved is None  # Should return None due to tenant isolation
        
        # Should NOT be accessible with None tenant_id
        retrieved = await tool_repo.get_tool(tenant_tool.tool_id, tenant_id=None)
        assert retrieved is None


class TestToolDefinitionRepositoryFiltering:
    """Test filtering capabilities."""

    @pytest.mark.asyncio
    async def test_filter_by_name(self, tool_repo: ToolDefinitionRepository, setup_tools):
        """Test filtering tools by name."""
        filters = ToolDefinitionFilter(name="Global")
        tools = await tool_repo.list_tools(tenant_id="tenant_001", filters=filters)
        
        assert len(tools) == 2
        assert all("Global" in tool.name for tool in tools)
        
        filters = ToolDefinitionFilter(name="Tenant1")
        tools = await tool_repo.list_tools(tenant_id="tenant_001", filters=filters)
        
        assert len(tools) == 2
        assert all("Tenant1" in tool.name for tool in tools)
        assert all(tool.tenant_id == "tenant_001" for tool in tools)

    @pytest.mark.asyncio
    async def test_filter_by_type(self, tool_repo: ToolDefinitionRepository, setup_tools):
        """Test filtering tools by type."""
        filters = ToolDefinitionFilter(type="webhook")
        tools = await tool_repo.list_tools(tenant_id="tenant_001", filters=filters)
        
        assert len(tools) == 1
        assert tools[0].type == "webhook"
        assert tools[0].name == "GlobalWebhook"
        
        filters = ToolDefinitionFilter(type="rest")
        tools = await tool_repo.list_tools(tenant_id="tenant_001", filters=filters)
        
        assert len(tools) == 1
        assert tools[0].type == "rest"
        assert tools[0].name == "Tenant1REST"

    @pytest.mark.asyncio
    async def test_filter_combined(self, tool_repo: ToolDefinitionRepository, setup_tools):
        """Test combining multiple filters."""
        filters = ToolDefinitionFilter(name="Global", type="email")
        tools = await tool_repo.list_tools(tenant_id="tenant_001", filters=filters)
        
        assert len(tools) == 1
        assert tools[0].name == "GlobalEmail"
        assert tools[0].type == "email"
        assert tools[0].tenant_id is None
        
        filters = ToolDefinitionFilter(name="Tenant1", type="workflow")
        tools = await tool_repo.list_tools(tenant_id="tenant_001", filters=filters)
        
        assert len(tools) == 1
        assert tools[0].name == "Tenant1Workflow"
        assert tools[0].type == "workflow"
        assert tools[0].tenant_id == "tenant_001"


class TestToolDefinitionRepositoryCreate:
    """Test tool creation."""

    @pytest.mark.asyncio
    async def test_create_global_tool(self, tool_repo: ToolDefinitionRepository, setup_tenants):
        """Test creating a global tool."""
        tool_data = ToolDefinitionCreateDTO(
            name="NewGlobalTool",
            type="webhook",
            config={"endpoint": "https://new.example.com/webhook"},
        )
        
        created = await tool_repo.create_tool(tenant_id=None, tool_data=tool_data)
        
        assert created is not None
        assert created.tenant_id is None
        assert created.name == "NewGlobalTool"
        assert created.type == "webhook"
        assert created.config == {"endpoint": "https://new.example.com/webhook"}
        assert created.tool_id is not None

    @pytest.mark.asyncio
    async def test_create_tenant_scoped_tool(self, tool_repo: ToolDefinitionRepository, setup_tenants):
        """Test creating a tenant-scoped tool."""
        tool_data = ToolDefinitionCreateDTO(
            name="NewTenantTool",
            type="rest",
            config={"endpoint": "https://tenant.example.com/api"},
        )
        
        created = await tool_repo.create_tool(tenant_id="tenant_001", tool_data=tool_data)
        
        assert created is not None
        assert created.tenant_id == "tenant_001"
        assert created.name == "NewTenantTool"
        assert created.type == "rest"
        assert created.config == {"endpoint": "https://tenant.example.com/api"}
        assert created.tool_id is not None
        
        # Verify it's only accessible by tenant_001
        retrieved = await tool_repo.get_tool(created.tool_id, tenant_id="tenant_001")
        assert retrieved is not None
        
        retrieved = await tool_repo.get_tool(created.tool_id, tenant_id="tenant_002")
        assert retrieved is None  # Should not be accessible by tenant_002

    @pytest.mark.asyncio
    async def test_create_tool_validation(self, tool_repo: ToolDefinitionRepository):
        """Test validation errors when creating tools."""
        with pytest.raises(Exception):  # Pydantic validation error
            ToolDefinitionCreateDTO(
                name="",  # Empty name should fail
                type="webhook",
                config={},
            )


class TestToolDefinitionRepositoryAbstractMethods:
    """Test AbstractBaseRepository interface methods."""

    @pytest.mark.asyncio
    async def test_get_by_id(self, tool_repo: ToolDefinitionRepository, setup_tools):
        """Test get_by_id method."""
        # Get a global tool
        all_tools = await tool_repo.list_tools(tenant_id=None)
        global_tool = all_tools[0]
        
        retrieved = await tool_repo.get_by_id(str(global_tool.tool_id), tenant_id="tenant_001")
        assert retrieved is not None
        assert retrieved.tool_id == global_tool.tool_id
        
        # Get a tenant-scoped tool
        tenant_tools = await tool_repo.list_tools(tenant_id="tenant_001")
        tenant_tool = [t for t in tenant_tools if t.tenant_id == "tenant_001"][0]
        
        retrieved = await tool_repo.get_by_id(str(tenant_tool.tool_id), tenant_id="tenant_001")
        assert retrieved is not None
        assert retrieved.tool_id == tenant_tool.tool_id
        
        # Should not be accessible by other tenant
        retrieved = await tool_repo.get_by_id(str(tenant_tool.tool_id), tenant_id="tenant_002")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_list_by_tenant(self, tool_repo: ToolDefinitionRepository, setup_tools):
        """Test list_by_tenant method with pagination."""
        result = await tool_repo.list_by_tenant(
            tenant_id="tenant_001",
            page=1,
            page_size=2,
        )
        
        # Should include global + tenant_001 tools
        assert result.total >= 4  # At least 2 global + 2 tenant_001
        assert len(result.items) == 2
        assert result.page == 1
        assert result.page_size == 2
        
        # Verify all returned tools are accessible by tenant_001
        for tool in result.items:
            assert tool.tenant_id is None or tool.tenant_id == "tenant_001"


