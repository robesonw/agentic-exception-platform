"""
Shared pytest fixtures for repository tests.

P6-29: Provides a shared test database fixture for all repository tests.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

from src.infrastructure.db.models import (
    Base,
    Tenant,
    TenantStatus,
    Exception,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionEvent,
    ActorType,
    DomainPackVersion,
    TenantPolicyPackVersion,
    Playbook,
    PlaybookStep,
    ToolDefinition,
)

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def test_engine():
    """
    Create an in-memory SQLite test engine.
    
    This fixture creates a fresh database for each test function,
    ensuring test isolation and determinism.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Create all tables manually for SQLite compatibility
    # SQLite doesn't support all PostgreSQL features, so we create simplified schemas
    async with engine.begin() as conn:
        # Tenant table
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS tenant (
                tenant_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
            """)
        )
        
        # Exception table
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS exception (
                exception_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                type TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                source_system TEXT NOT NULL,
                entity TEXT,
                amount NUMERIC,
                sla_deadline TIMESTAMP,
                owner TEXT,
                current_playbook_id INTEGER,
                current_step INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """)
        )
        
        # Exception event table
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS exception_event (
                event_id TEXT PRIMARY KEY,
                exception_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                actor_id TEXT,
                payload TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (exception_id) REFERENCES exception(exception_id) ON DELETE CASCADE
            )
            """)
        )
        
        # Domain pack version table
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS domain_pack_version (
                domain TEXT NOT NULL,
                version INTEGER NOT NULL,
                pack_json TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (domain, version)
            )
            """)
        )
        
        # Tenant policy pack version table
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS tenant_policy_pack_version (
                tenant_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                pack_json TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tenant_id, version)
            )
            """)
        )
        
        # Playbook table
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS playbook (
                playbook_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                name TEXT NOT NULL,
                version INTEGER NOT NULL,
                conditions TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (tenant_id, name, version)
            )
            """)
        )
        
        # Playbook step table
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS playbook_step (
                step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                playbook_id INTEGER NOT NULL,
                step_order INTEGER NOT NULL,
                name TEXT NOT NULL,
                action_type TEXT NOT NULL,
                params TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (playbook_id) REFERENCES playbook(playbook_id) ON DELETE CASCADE,
                UNIQUE (playbook_id, step_order)
            )
            """)
        )
        
        # Tool definition table
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS tool_definition (
                tool_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                config TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (tenant_id, name)
            )
            """)
        )
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS tool_definition"))
        await conn.execute(text("DROP TABLE IF EXISTS playbook_step"))
        await conn.execute(text("DROP TABLE IF EXISTS playbook"))
        await conn.execute(text("DROP TABLE IF EXISTS tenant_policy_pack_version"))
        await conn.execute(text("DROP TABLE IF EXISTS domain_pack_version"))
        await conn.execute(text("DROP TABLE IF EXISTS exception_event"))
        await conn.execute(text("DROP TABLE IF EXISTS exception"))
        await conn.execute(text("DROP TABLE IF EXISTS tenant"))
    
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_session(test_engine):
    """
    Create a test database session.
    
    This fixture provides an AsyncSession for repository tests.
    Each test gets a fresh session with a clean database.
    """
    async_session = async_sessionmaker(
        test_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    
    async with async_session() as session:
        yield session


@pytest.fixture
def fixed_timestamp():
    """
    Provide a fixed timestamp for deterministic tests.
    
    Returns a datetime object that can be used consistently across tests.
    """
    return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
async def sample_tenants(test_session: AsyncSession, fixed_timestamp):
    """
    Create sample tenants for testing.
    
    Returns a list of Tenant objects with known IDs and properties.
    """
    tenants = [
        Tenant(
            tenant_id="tenant_001",
            name="Finance Tenant",
            status=TenantStatus.ACTIVE,
            created_at=fixed_timestamp,
        ),
        Tenant(
            tenant_id="tenant_002",
            name="Healthcare Tenant",
            status=TenantStatus.ACTIVE,
            created_at=datetime(2024, 1, 16, 12, 0, 0, tzinfo=timezone.utc),
        ),
        Tenant(
            tenant_id="tenant_003",
            name="Retail Tenant",
            status=TenantStatus.SUSPENDED,
            created_at=datetime(2024, 1, 17, 12, 0, 0, tzinfo=timezone.utc),
        ),
    ]
    
    test_session.add_all(tenants)
    await test_session.commit()
    
    # Refresh all tenants
    for tenant in tenants:
        await test_session.refresh(tenant)
    
    return tenants

