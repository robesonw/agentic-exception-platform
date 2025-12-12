"""
Tests for Exception API endpoints using DB-backed repositories (P6-22).

Tests verify:
- Pagination works correctly
- Status/domain/severity filtering works
- Invalid tenant returns empty results
- Update endpoint works correctly
"""

import pytest

pytestmark = pytest.mark.phase6
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.api.auth import Role, get_api_key_auth
from src.api.main import app
from src.api.middleware import get_rate_limiter
from src.infrastructure.db.session import get_db_session_context
from src.repository.exceptions_repository import ExceptionRepository
from src.repository.dto import ExceptionCreateDTO
from src.infrastructure.db.models import ExceptionSeverity, ExceptionStatus

client = TestClient(app)

# Default API key for tests
DEFAULT_API_KEY = "test_api_key_tenant_001"


@pytest.fixture(autouse=True)
def setup_api_keys():
    """Set up API keys for tests."""
    auth = get_api_key_auth()
    limiter = get_rate_limiter()
    # Ensure DEFAULT_API_KEY is registered to TENANT_001
    auth.register_api_key(DEFAULT_API_KEY, "TENANT_001", Role.ADMIN)
    yield
    # Reset rate limiter after each test
    limiter._request_timestamps.clear()


@pytest.fixture
async def test_db_session():
    """Create a test database session."""
    # Use in-memory SQLite for testing
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
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
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
                sla_deadline TIMESTAMP WITH TIME ZONE,
                owner TEXT,
                current_playbook_id INTEGER,
                current_step INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS ix_exception_tenant_id ON exception(tenant_id);
            """
            )
        )
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS exception;"))
        await conn.execute(text("DROP TABLE IF EXISTS tenant;"))
    await engine.dispose()


@pytest.fixture
async def setup_test_data(test_db_session: AsyncSession):
    """Set up test data in the database."""
    from sqlalchemy import text
    
    # Create tenants
    await test_db_session.execute(
        text("INSERT INTO tenant (tenant_id, name, status) VALUES ('TENANT_001', 'Tenant One', 'active')")
    )
    await test_db_session.execute(
        text("INSERT INTO tenant (tenant_id, name, status) VALUES ('TENANT_002', 'Tenant Two', 'active')")
    )
    
    # Create exceptions for TENANT_001
    now = datetime.now(timezone.utc)
    exceptions_data = [
        ("EXC-001", "TENANT_001", "Finance", "PaymentFailure", "high", "open", "PaymentGateway", None, None, now),
        ("EXC-002", "TENANT_001", "Finance", "PaymentFailure", "high", "open", "PaymentGateway", "ACC-001", None, now - timedelta(hours=1)),
        ("EXC-003", "TENANT_001", "Finance", "FraudAlert", "critical", "analyzing", "FraudDetection", "ACC-002", 1000.0, now - timedelta(hours=2)),
        ("EXC-004", "TENANT_001", "Healthcare", "PatientDataMismatch", "medium", "resolved", "EMR", "PAT-001", None, now - timedelta(hours=3)),
        ("EXC-005", "TENANT_001", "Finance", "ReconciliationMismatch", "low", "open", "AccountingSystem", None, 50.0, now - timedelta(hours=4)),
    ]
    
    for exc_data in exceptions_data:
        await test_db_session.execute(
            text(
                """
            INSERT INTO exception (exception_id, tenant_id, domain, type, severity, status,
                                  source_system, entity, amount, sla_deadline, created_at)
            VALUES (:exception_id, :tenant_id, :domain, :type, :severity, :status,
                    :source_system, :entity, :amount, :sla_deadline, :created_at)
            """
            ),
            {
                "exception_id": exc_data[0],
                "tenant_id": exc_data[1],
                "domain": exc_data[2],
                "type": exc_data[3],
                "severity": exc_data[4],
                "status": exc_data[5],
                "source_system": exc_data[6],
                "entity": exc_data[7],
                "amount": exc_data[8],
                "sla_deadline": exc_data[9],
                "created_at": exc_data[9],
            },
        )
    
    # Create exceptions for TENANT_002
    await test_db_session.execute(
        text(
            """
        INSERT INTO exception (exception_id, tenant_id, domain, type, severity, status,
                              source_system, entity, amount, sla_deadline, created_at)
        VALUES ('HC-EXC-001', 'TENANT_002', 'Healthcare', 'PatientDataMismatch', 'high', 'open',
                'EMR', 'PAT-002', NULL, NULL, :created_at)
        """
        ),
        {"created_at": now},
    )
    
    await test_db_session.commit()


class TestListExceptionsAPI:
    """Tests for GET /exceptions/{tenant_id} endpoint."""

    @pytest.mark.asyncio
    async def test_list_exceptions_basic(self, test_db_session, setup_test_data):
        """Test basic listing of exceptions."""
        # Mock the database session context
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            response = client.get(
                "/exceptions/TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "page" in data
            assert "page_size" in data
            assert "total_pages" in data
            assert data["total"] == 5
            assert len(data["items"]) == 5
            assert data["page"] == 1
            assert data["page_size"] == 50
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_exceptions_pagination(self, test_db_session, setup_test_data):
        """Test pagination works correctly."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            # First page
            response = client.get(
                "/exceptions/TENANT_001?page=1&page_size=2",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            assert data["page"] == 1
            assert data["page_size"] == 2
            assert data["total"] == 5
            assert data["total_pages"] == 3
            
            # Second page
            response = client.get(
                "/exceptions/TENANT_001?page=2&page_size=2",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            assert data["page"] == 2
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_exceptions_filter_by_domain(self, test_db_session, setup_test_data):
        """Test filtering by domain."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            response = client.get(
                "/exceptions/TENANT_001?domain=Finance",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 4  # 4 Finance exceptions
            assert all(item["normalizedContext"]["domain"] == "Finance" for item in data["items"])
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_exceptions_filter_by_status(self, test_db_session, setup_test_data):
        """Test filtering by status."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            response = client.get(
                "/exceptions/TENANT_001?status=open",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 3  # 3 open exceptions
            assert all(item["resolutionStatus"] == "OPEN" for item in data["items"])
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_exceptions_filter_by_severity(self, test_db_session, setup_test_data):
        """Test filtering by severity."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            response = client.get(
                "/exceptions/TENANT_001?severity=high",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2  # 2 high severity exceptions
            assert all(item["severity"] == "HIGH" for item in data["items"])
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_exceptions_invalid_tenant(self, test_db_session, setup_test_data):
        """Test that invalid tenant returns empty results."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            response = client.get(
                "/exceptions/INVALID_TENANT",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert len(data["items"]) == 0
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_exceptions_tenant_isolation(self, test_db_session, setup_test_data):
        """Test that tenant isolation is enforced."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            # TENANT_001 should only see their own exceptions
            response = client.get(
                "/exceptions/TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 5
            assert all(item["tenantId"] == "TENANT_001" for item in data["items"])
        finally:
            session_module.get_db_session_context = original_get_context


class TestUpdateExceptionAPI:
    """Tests for PUT /exceptions/{tenant_id}/{exception_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_exception_status(self, test_db_session, setup_test_data):
        """Test updating exception status."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            response = client.put(
                "/exceptions/TENANT_001/EXC-001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
                json={"status": "resolved"},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["resolutionStatus"] == "RESOLVED"
            assert data["exceptionId"] == "EXC-001"
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_update_exception_severity(self, test_db_session, setup_test_data):
        """Test updating exception severity."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            response = client.put(
                "/exceptions/TENANT_001/EXC-005",
                headers={"X-API-KEY": DEFAULT_API_KEY},
                json={"severity": "critical"},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["severity"] == "CRITICAL"
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_update_exception_not_found(self, test_db_session, setup_test_data):
        """Test updating non-existent exception returns 404."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            response = client.put(
                "/exceptions/TENANT_001/NON-EXISTENT",
                headers={"X-API-KEY": DEFAULT_API_KEY},
                json={"status": "resolved"},
            )
            
            assert response.status_code == 404
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_update_exception_invalid_status(self, test_db_session, setup_test_data):
        """Test updating with invalid status returns 400."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            response = client.put(
                "/exceptions/TENANT_001/EXC-001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
                json={"status": "invalid_status"},
            )
            
            assert response.status_code == 400
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_update_exception_tenant_isolation(self, test_db_session, setup_test_data):
        """Test that tenant isolation is enforced in updates."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            # Try to update TENANT_002's exception from TENANT_001
            response = client.put(
                "/exceptions/TENANT_001/HC-EXC-001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
                json={"status": "resolved"},
            )
            
            # Should return 404 because exception doesn't belong to TENANT_001
            assert response.status_code == 404
        finally:
            session_module.get_db_session_context = original_get_context


