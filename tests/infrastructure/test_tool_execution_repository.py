"""
Unit tests for ToolExecutionRepository.

Tests cover:
- Creating execution records
- Getting execution by ID with tenant isolation
- Listing executions with filtering
- Updating execution status and results
- Tenant isolation enforcement
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from src.infrastructure.db.models import ActorType, ToolExecutionStatus
from src.infrastructure.repositories.tool_execution_repository import ToolExecutionRepository
from src.repository.dto import (
    ToolExecutionCreateDTO,
    ToolExecutionFilter,
    ToolExecutionUpdateDTO,
)

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
    tenant_id = Column(String, ForeignKey("tenant.tenant_id", ondelete="CASCADE"), nullable=True)
    type = Column(String, nullable=False)
    config = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    
    tenant = relationship("TestTenant", backref="tool_definitions")


class TestException(TestBase):
    __tablename__ = "exception"
    exception_id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenant.tenant_id", ondelete="CASCADE"), nullable=False)
    domain = Column(String, nullable=False)
    type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    status = Column(String, nullable=False)
    source_system = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    
    tenant = relationship("TestTenant", backref="exceptions")


class TestToolExecution(TestBase):
    __tablename__ = "tool_execution"
    id = Column(String, primary_key=True)  # SQLite doesn't support UUID, use string
    tenant_id = Column(String, ForeignKey("tenant.tenant_id", ondelete="CASCADE"), nullable=False)
    tool_id = Column(Integer, ForeignKey("tool_definition.tool_id", ondelete="CASCADE"), nullable=False)
    exception_id = Column(String, ForeignKey("exception.exception_id", ondelete="SET NULL"), nullable=True)
    status = Column(String, nullable=False, default="requested")
    requested_by_actor_type = Column(String, nullable=False)
    requested_by_actor_id = Column(String, nullable=False)
    input_payload = Column(JSON, nullable=False)
    output_payload = Column(JSON, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    
    tenant = relationship("TestTenant", backref="tool_executions")
    tool_definition = relationship("TestToolDefinition")
    exception = relationship("TestException")


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
        await conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS tool_definition (
                tool_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                tenant_id TEXT,
                type TEXT NOT NULL,
                config TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE
            )
            """
            )
        )
        await conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS exception (
                exception_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                type TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                source_system TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE
            )
            """
            )
        )
        await conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS tool_execution (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                tool_id INTEGER NOT NULL,
                exception_id TEXT,
                status TEXT NOT NULL DEFAULT 'requested',
                requested_by_actor_type TEXT NOT NULL,
                requested_by_actor_id TEXT NOT NULL,
                input_payload TEXT NOT NULL,
                output_payload TEXT,
                error_message TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE,
                FOREIGN KEY (tool_id) REFERENCES tool_definition(tool_id) ON DELETE CASCADE,
                FOREIGN KEY (exception_id) REFERENCES exception(exception_id) ON DELETE SET NULL
            )
            """
            )
        )
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tool_execution_tenant_id ON tool_execution(tenant_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tool_execution_tool_id ON tool_execution(tool_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tool_execution_exception_id ON tool_execution(exception_id);"))
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS tool_execution;"))
        await conn.execute(text("DROP TABLE IF EXISTS exception;"))
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
async def setup_test_data(test_session: AsyncSession):
    """Set up sample data for testing."""
    from sqlalchemy import text
    import json
    
    # Create tenants
    await test_session.execute(
        text("INSERT INTO tenant (tenant_id, name) VALUES ('TENANT_001', 'Tenant One')")
    )
    await test_session.execute(
        text("INSERT INTO tenant (tenant_id, name) VALUES ('TENANT_002', 'Tenant Two')")
    )
    
    # Create tool definitions
    await test_session.execute(
        text(
            """
        INSERT INTO tool_definition (tool_id, name, tenant_id, type, config)
        VALUES (1, 'Tool 1', 'TENANT_001', 'http', :config)
        """
        ),
        {"config": json.dumps({"endpoint": "https://api.example.com/tool1"})},
    )
    await test_session.execute(
        text(
            """
        INSERT INTO tool_definition (tool_id, name, tenant_id, type, config)
        VALUES (2, 'Tool 2', 'TENANT_001', 'http', :config)
        """
        ),
        {"config": json.dumps({"endpoint": "https://api.example.com/tool2"})},
    )
    await test_session.execute(
        text(
            """
        INSERT INTO tool_definition (tool_id, name, tenant_id, type, config)
        VALUES (3, 'Global Tool', NULL, 'http', :config)
        """
        ),
        {"config": json.dumps({"endpoint": "https://api.example.com/global"})},
    )
    
    # Create exceptions
    await test_session.execute(
        text(
            """
        INSERT INTO exception (exception_id, tenant_id, domain, type, severity, status, source_system)
        VALUES ('EXC_001', 'TENANT_001', 'TestDomain', 'TestType', 'high', 'open', 'TestSystem')
        """
        )
    )
    
    await test_session.commit()


class TestToolExecutionRepository:
    """Tests for ToolExecutionRepository."""

    @pytest.mark.asyncio
    async def test_create_execution(self, test_session, setup_test_data):
        """Test creating a tool execution record."""
        repo = ToolExecutionRepository(test_session)
        
        create_dto = ToolExecutionCreateDTO(
            tenant_id="TENANT_001",
            tool_id=1,
            exception_id="EXC_001",
            status=ToolExecutionStatus.REQUESTED,
            requested_by_actor_type=ActorType.AGENT,
            requested_by_actor_id="ResolutionAgent",
            input_payload={"param1": "value1"},
        )
        
        execution = await repo.create_execution(create_dto)
        
        assert execution is not None
        assert execution.tenant_id == "TENANT_001"
        assert execution.tool_id == 1
        assert execution.exception_id == "EXC_001"
        assert execution.status == ToolExecutionStatus.REQUESTED
        assert execution.requested_by_actor_type == ActorType.AGENT
        assert execution.requested_by_actor_id == "ResolutionAgent"
        assert execution.input_payload == {"param1": "value1"}
        assert execution.id is not None

    @pytest.mark.asyncio
    async def test_create_execution_without_exception(self, test_session, setup_test_data):
        """Test creating a tool execution without exception_id."""
        repo = ToolExecutionRepository(test_session)
        
        create_dto = ToolExecutionCreateDTO(
            tenant_id="TENANT_001",
            tool_id=1,
            exception_id=None,
            status=ToolExecutionStatus.REQUESTED,
            requested_by_actor_type=ActorType.USER,
            requested_by_actor_id="user123",
            input_payload={"param": "value"},
        )
        
        execution = await repo.create_execution(create_dto)
        
        assert execution is not None
        assert execution.exception_id is None

    @pytest.mark.asyncio
    async def test_get_execution(self, test_session, setup_test_data):
        """Test getting a tool execution by ID."""
        repo = ToolExecutionRepository(test_session)
        
        # Create execution
        create_dto = ToolExecutionCreateDTO(
            tenant_id="TENANT_001",
            tool_id=1,
            status=ToolExecutionStatus.REQUESTED,
            requested_by_actor_type=ActorType.AGENT,
            requested_by_actor_id="Agent1",
            input_payload={"param": "value"},
        )
        execution = await repo.create_execution(create_dto)
        await test_session.commit()
        
        # Get execution
        retrieved = await repo.get_execution(execution.id, "TENANT_001")
        
        assert retrieved is not None
        assert retrieved.id == execution.id
        assert retrieved.tenant_id == "TENANT_001"

    @pytest.mark.asyncio
    async def test_get_execution_tenant_isolation(self, test_session, setup_test_data):
        """Test that tenant isolation is enforced when getting execution."""
        repo = ToolExecutionRepository(test_session)
        
        # Create execution for TENANT_001
        create_dto = ToolExecutionCreateDTO(
            tenant_id="TENANT_001",
            tool_id=1,
            status=ToolExecutionStatus.REQUESTED,
            requested_by_actor_type=ActorType.AGENT,
            requested_by_actor_id="Agent1",
            input_payload={"param": "value"},
        )
        execution = await repo.create_execution(create_dto)
        await test_session.commit()
        
        # Try to get with wrong tenant - should return None
        retrieved = await repo.get_execution(execution.id, "TENANT_002")
        
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_execution_not_found(self, test_session, setup_test_data):
        """Test getting a non-existent execution."""
        repo = ToolExecutionRepository(test_session)
        
        from uuid import uuid4
        fake_id = uuid4()
        
        retrieved = await repo.get_execution(fake_id, "TENANT_001")
        
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_list_executions_basic(self, test_session, setup_test_data):
        """Test listing executions for a tenant."""
        repo = ToolExecutionRepository(test_session)
        
        # Create multiple executions
        for i in range(3):
            create_dto = ToolExecutionCreateDTO(
                tenant_id="TENANT_001",
                tool_id=1,
                status=ToolExecutionStatus.REQUESTED,
                requested_by_actor_type=ActorType.AGENT,
                requested_by_actor_id=f"Agent{i}",
                input_payload={"param": f"value{i}"},
            )
            await repo.create_execution(create_dto)
        await test_session.commit()
        
        # List executions
        result = await repo.list_executions("TENANT_001", page=1, page_size=10)
        
        assert result.total == 3
        assert len(result.items) == 3
        assert all(item.tenant_id == "TENANT_001" for item in result.items)

    @pytest.mark.asyncio
    async def test_list_executions_tenant_isolation(self, test_session, setup_test_data):
        """Test that tenant isolation is enforced when listing executions."""
        repo = ToolExecutionRepository(test_session)
        
        # Create executions for both tenants
        for tenant_id in ["TENANT_001", "TENANT_002"]:
            create_dto = ToolExecutionCreateDTO(
                tenant_id=tenant_id,
                tool_id=1,
                status=ToolExecutionStatus.REQUESTED,
                requested_by_actor_type=ActorType.AGENT,
                requested_by_actor_id="Agent1",
                input_payload={"param": "value"},
            )
            await repo.create_execution(create_dto)
        await test_session.commit()
        
        # List for TENANT_001 - should only see TENANT_001's executions
        result = await repo.list_executions("TENANT_001", page=1, page_size=10)
        
        assert result.total == 1
        assert all(item.tenant_id == "TENANT_001" for item in result.items)

    @pytest.mark.asyncio
    async def test_list_executions_filter_by_tool_id(self, test_session, setup_test_data):
        """Test filtering executions by tool_id."""
        repo = ToolExecutionRepository(test_session)
        
        # Create executions with different tool_ids
        for tool_id in [1, 2]:
            create_dto = ToolExecutionCreateDTO(
                tenant_id="TENANT_001",
                tool_id=tool_id,
                status=ToolExecutionStatus.REQUESTED,
                requested_by_actor_type=ActorType.AGENT,
                requested_by_actor_id="Agent1",
                input_payload={"param": "value"},
            )
            await repo.create_execution(create_dto)
        await test_session.commit()
        
        # Filter by tool_id=1
        filters = ToolExecutionFilter(tool_id=1)
        result = await repo.list_executions("TENANT_001", filters=filters, page=1, page_size=10)
        
        assert result.total == 1
        assert result.items[0].tool_id == 1

    @pytest.mark.asyncio
    async def test_list_executions_filter_by_exception_id(self, test_session, setup_test_data):
        """Test filtering executions by exception_id."""
        repo = ToolExecutionRepository(test_session)
        
        # Create executions with and without exception_id
        create_dto1 = ToolExecutionCreateDTO(
            tenant_id="TENANT_001",
            tool_id=1,
            exception_id="EXC_001",
            status=ToolExecutionStatus.REQUESTED,
            requested_by_actor_type=ActorType.AGENT,
            requested_by_actor_id="Agent1",
            input_payload={"param": "value"},
        )
        await repo.create_execution(create_dto1)
        
        create_dto2 = ToolExecutionCreateDTO(
            tenant_id="TENANT_001",
            tool_id=1,
            exception_id=None,
            status=ToolExecutionStatus.REQUESTED,
            requested_by_actor_type=ActorType.AGENT,
            requested_by_actor_id="Agent1",
            input_payload={"param": "value"},
        )
        await repo.create_execution(create_dto2)
        await test_session.commit()
        
        # Filter by exception_id
        filters = ToolExecutionFilter(exception_id="EXC_001")
        result = await repo.list_executions("TENANT_001", filters=filters, page=1, page_size=10)
        
        assert result.total == 1
        assert result.items[0].exception_id == "EXC_001"

    @pytest.mark.asyncio
    async def test_list_executions_filter_by_status(self, test_session, setup_test_data):
        """Test filtering executions by status."""
        repo = ToolExecutionRepository(test_session)
        
        # Create executions with different statuses
        for status in [ToolExecutionStatus.REQUESTED, ToolExecutionStatus.SUCCEEDED]:
            create_dto = ToolExecutionCreateDTO(
                tenant_id="TENANT_001",
                tool_id=1,
                status=status,
                requested_by_actor_type=ActorType.AGENT,
                requested_by_actor_id="Agent1",
                input_payload={"param": "value"},
            )
            await repo.create_execution(create_dto)
        await test_session.commit()
        
        # Filter by status=SUCCEEDED
        filters = ToolExecutionFilter(status=ToolExecutionStatus.SUCCEEDED)
        result = await repo.list_executions("TENANT_001", filters=filters, page=1, page_size=10)
        
        assert result.total == 1
        assert result.items[0].status == ToolExecutionStatus.SUCCEEDED

    @pytest.mark.asyncio
    async def test_list_executions_filter_by_actor_type(self, test_session, setup_test_data):
        """Test filtering executions by actor_type."""
        repo = ToolExecutionRepository(test_session)
        
        # Create executions with different actor types
        for actor_type in [ActorType.AGENT, ActorType.USER]:
            create_dto = ToolExecutionCreateDTO(
                tenant_id="TENANT_001",
                tool_id=1,
                status=ToolExecutionStatus.REQUESTED,
                requested_by_actor_type=actor_type,
                requested_by_actor_id="actor1",
                input_payload={"param": "value"},
            )
            await repo.create_execution(create_dto)
        await test_session.commit()
        
        # Filter by actor_type=USER
        filters = ToolExecutionFilter(actor_type=ActorType.USER)
        result = await repo.list_executions("TENANT_001", filters=filters, page=1, page_size=10)
        
        assert result.total == 1
        assert result.items[0].requested_by_actor_type == ActorType.USER

    @pytest.mark.asyncio
    async def test_list_executions_pagination(self, test_session, setup_test_data):
        """Test pagination when listing executions."""
        repo = ToolExecutionRepository(test_session)
        
        # Create 5 executions
        for i in range(5):
            create_dto = ToolExecutionCreateDTO(
                tenant_id="TENANT_001",
                tool_id=1,
                status=ToolExecutionStatus.REQUESTED,
                requested_by_actor_type=ActorType.AGENT,
                requested_by_actor_id=f"Agent{i}",
                input_payload={"param": f"value{i}"},
            )
            await repo.create_execution(create_dto)
        await test_session.commit()
        
        # Get first page (2 items)
        result = await repo.list_executions("TENANT_001", page=1, page_size=2)
        
        assert result.total == 5
        assert len(result.items) == 2
        assert result.page == 1
        assert result.page_size == 2
        assert result.total_pages == 3
        
        # Get second page
        result2 = await repo.list_executions("TENANT_001", page=2, page_size=2)
        
        assert result2.total == 5
        assert len(result2.items) == 2
        assert result2.page == 2

    @pytest.mark.asyncio
    async def test_update_execution_status(self, test_session, setup_test_data):
        """Test updating execution status."""
        repo = ToolExecutionRepository(test_session)
        
        # Create execution
        create_dto = ToolExecutionCreateDTO(
            tenant_id="TENANT_001",
            tool_id=1,
            status=ToolExecutionStatus.REQUESTED,
            requested_by_actor_type=ActorType.AGENT,
            requested_by_actor_id="Agent1",
            input_payload={"param": "value"},
        )
        execution = await repo.create_execution(create_dto)
        await test_session.commit()
        
        # Update status
        update_dto = ToolExecutionUpdateDTO(status=ToolExecutionStatus.RUNNING)
        updated = await repo.update_execution(execution.id, "TENANT_001", update_dto)
        await test_session.commit()
        
        assert updated is not None
        assert updated.status == ToolExecutionStatus.RUNNING

    @pytest.mark.asyncio
    async def test_update_execution_output(self, test_session, setup_test_data):
        """Test updating execution output_payload."""
        repo = ToolExecutionRepository(test_session)
        
        # Create execution
        create_dto = ToolExecutionCreateDTO(
            tenant_id="TENANT_001",
            tool_id=1,
            status=ToolExecutionStatus.RUNNING,
            requested_by_actor_type=ActorType.AGENT,
            requested_by_actor_id="Agent1",
            input_payload={"param": "value"},
        )
        execution = await repo.create_execution(create_dto)
        await test_session.commit()
        
        # Update output
        update_dto = ToolExecutionUpdateDTO(
            status=ToolExecutionStatus.SUCCEEDED,
            output_payload={"result": "success", "data": {"key": "value"}},
        )
        updated = await repo.update_execution(execution.id, "TENANT_001", update_dto)
        await test_session.commit()
        
        assert updated is not None
        assert updated.status == ToolExecutionStatus.SUCCEEDED
        assert updated.output_payload == {"result": "success", "data": {"key": "value"}}

    @pytest.mark.asyncio
    async def test_update_execution_error(self, test_session, setup_test_data):
        """Test updating execution with error message."""
        repo = ToolExecutionRepository(test_session)
        
        # Create execution
        create_dto = ToolExecutionCreateDTO(
            tenant_id="TENANT_001",
            tool_id=1,
            status=ToolExecutionStatus.RUNNING,
            requested_by_actor_type=ActorType.AGENT,
            requested_by_actor_id="Agent1",
            input_payload={"param": "value"},
        )
        execution = await repo.create_execution(create_dto)
        await test_session.commit()
        
        # Update with error
        update_dto = ToolExecutionUpdateDTO(
            status=ToolExecutionStatus.FAILED,
            error_message="Tool execution timeout",
        )
        updated = await repo.update_execution(execution.id, "TENANT_001", update_dto)
        await test_session.commit()
        
        assert updated is not None
        assert updated.status == ToolExecutionStatus.FAILED
        assert updated.error_message == "Tool execution timeout"

    @pytest.mark.asyncio
    async def test_update_execution_tenant_isolation(self, test_session, setup_test_data):
        """Test that tenant isolation is enforced when updating execution."""
        repo = ToolExecutionRepository(test_session)
        
        # Create execution for TENANT_001
        create_dto = ToolExecutionCreateDTO(
            tenant_id="TENANT_001",
            tool_id=1,
            status=ToolExecutionStatus.REQUESTED,
            requested_by_actor_type=ActorType.AGENT,
            requested_by_actor_id="Agent1",
            input_payload={"param": "value"},
        )
        execution = await repo.create_execution(create_dto)
        await test_session.commit()
        
        # Try to update with wrong tenant - should return None
        update_dto = ToolExecutionUpdateDTO(status=ToolExecutionStatus.RUNNING)
        updated = await repo.update_execution(execution.id, "TENANT_002", update_dto)
        
        assert updated is None

    @pytest.mark.asyncio
    async def test_update_execution_not_found(self, test_session, setup_test_data):
        """Test updating a non-existent execution."""
        repo = ToolExecutionRepository(test_session)
        
        from uuid import uuid4
        fake_id = uuid4()
        
        update_dto = ToolExecutionUpdateDTO(status=ToolExecutionStatus.RUNNING)
        updated = await repo.update_execution(fake_id, "TENANT_001", update_dto)
        
        assert updated is None

    @pytest.mark.asyncio
    async def test_list_executions_empty_tenant_id(self, test_session, setup_test_data):
        """Test that empty tenant_id raises ValueError."""
        repo = ToolExecutionRepository(test_session)
        
        with pytest.raises(ValueError) as exc_info:
            await repo.list_executions("", page=1, page_size=10)
        assert "tenant_id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_execution_empty_tenant_id(self, test_session, setup_test_data):
        """Test that empty tenant_id raises ValueError."""
        repo = ToolExecutionRepository(test_session)
        
        from uuid import uuid4
        fake_id = uuid4()
        
        with pytest.raises(ValueError) as exc_info:
            await repo.get_execution(fake_id, "")
        assert "tenant_id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_list_executions_invalid_pagination(self, test_session, setup_test_data):
        """Test that invalid pagination parameters raise ValueError."""
        repo = ToolExecutionRepository(test_session)
        
        with pytest.raises(ValueError) as exc_info:
            await repo.list_executions("TENANT_001", page=0, page_size=10)
        assert "page" in str(exc_info.value).lower()
        
        with pytest.raises(ValueError) as exc_info:
            await repo.list_executions("TENANT_001", page=1, page_size=0)
        assert "page_size" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_by_id_interface(self, test_session, setup_test_data):
        """Test get_by_id interface method."""
        repo = ToolExecutionRepository(test_session)
        
        # Create execution
        create_dto = ToolExecutionCreateDTO(
            tenant_id="TENANT_001",
            tool_id=1,
            status=ToolExecutionStatus.REQUESTED,
            requested_by_actor_type=ActorType.AGENT,
            requested_by_actor_id="Agent1",
            input_payload={"param": "value"},
        )
        execution = await repo.create_execution(create_dto)
        await test_session.commit()
        
        # Get via interface
        retrieved = await repo.get_by_id(str(execution.id), "TENANT_001")
        
        assert retrieved is not None
        assert retrieved.id == execution.id

    @pytest.mark.asyncio
    async def test_list_by_tenant_interface(self, test_session, setup_test_data):
        """Test list_by_tenant interface method."""
        repo = ToolExecutionRepository(test_session)
        
        # Create executions
        for i in range(2):
            create_dto = ToolExecutionCreateDTO(
                tenant_id="TENANT_001",
                tool_id=1,
                status=ToolExecutionStatus.REQUESTED,
                requested_by_actor_type=ActorType.AGENT,
                requested_by_actor_id=f"Agent{i}",
                input_payload={"param": f"value{i}"},
            )
            await repo.create_execution(create_dto)
        await test_session.commit()
        
        # List via interface
        result = await repo.list_by_tenant("TENANT_001", page=1, page_size=10)
        
        assert result.total == 2
        assert len(result.items) == 2

