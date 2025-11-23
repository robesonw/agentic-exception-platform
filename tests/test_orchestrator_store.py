"""
Tests for ExceptionStore.
Tests per-tenant exception storage and retrieval with tenant isolation.
"""

import pytest

from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.orchestrator.store import ExceptionStore, get_exception_store


@pytest.fixture
def sample_exception_1():
    """Sample exception for tenant 1."""
    return ExceptionRecord(
        exceptionId="exc_001",
        tenantId="TENANT_001",
        sourceSystem="ERP",
        exceptionType="DataQualityFailure",
        severity=Severity.HIGH,
        timestamp="2024-01-15T10:30:00Z",
        rawPayload={"error": "Invalid data"},
        resolutionStatus=ResolutionStatus.OPEN,
    )


@pytest.fixture
def sample_exception_2():
    """Sample exception for tenant 2."""
    return ExceptionRecord(
        exceptionId="exc_002",
        tenantId="TENANT_002",
        sourceSystem="CRM",
        exceptionType="DataQualityFailure",
        severity=Severity.MEDIUM,
        timestamp="2024-01-15T11:00:00Z",
        rawPayload={"error": "Missing field"},
        resolutionStatus=ResolutionStatus.IN_PROGRESS,
    )


@pytest.fixture
def sample_pipeline_result():
    """Sample pipeline result."""
    return {
        "exceptionId": "exc_001",
        "status": "OPEN",
        "stages": {
            "intake": {"decision": "normalized"},
            "triage": {"decision": "classified"},
        },
        "evidence": ["Evidence 1"],
    }


@pytest.fixture(autouse=True)
def reset_store():
    """Reset exception store before each test."""
    store = get_exception_store()
    store.clear_all()
    yield
    store.clear_all()


class TestExceptionStore:
    """Tests for ExceptionStore class."""

    def test_store_exception(self, sample_exception_1, sample_pipeline_result):
        """Test storing an exception."""
        store = ExceptionStore()
        store.store_exception(sample_exception_1, sample_pipeline_result)
        
        # Verify exception can be retrieved
        retrieved = store.get_exception("TENANT_001", "exc_001")
        assert retrieved is not None
        exception, result = retrieved
        assert exception.exception_id == "exc_001"
        assert result["status"] == "OPEN"

    def test_get_exception_not_found(self):
        """Test retrieving non-existent exception."""
        store = ExceptionStore()
        retrieved = store.get_exception("TENANT_001", "nonexistent")
        assert retrieved is None

    def test_get_tenant_exceptions(self, sample_exception_1, sample_exception_2, sample_pipeline_result):
        """Test getting all exceptions for a tenant."""
        store = ExceptionStore()
        
        # Store exceptions for different tenants
        store.store_exception(sample_exception_1, sample_pipeline_result)
        
        result_2 = sample_pipeline_result.copy()
        result_2["exceptionId"] = "exc_002"
        store.store_exception(sample_exception_2, result_2)
        
        # Get exceptions for tenant 1
        tenant_1_exceptions = store.get_tenant_exceptions("TENANT_001")
        assert len(tenant_1_exceptions) == 1
        assert tenant_1_exceptions[0][0].exception_id == "exc_001"
        
        # Get exceptions for tenant 2
        tenant_2_exceptions = store.get_tenant_exceptions("TENANT_002")
        assert len(tenant_2_exceptions) == 1
        assert tenant_2_exceptions[0][0].exception_id == "exc_002"

    def test_clear_tenant(self, sample_exception_1, sample_exception_2, sample_pipeline_result):
        """Test clearing exceptions for a tenant."""
        store = ExceptionStore()
        
        store.store_exception(sample_exception_1, sample_pipeline_result)
        
        result_2 = sample_pipeline_result.copy()
        result_2["exceptionId"] = "exc_002"
        store.store_exception(sample_exception_2, result_2)
        
        # Clear tenant 1
        store.clear_tenant("TENANT_001")
        
        # Verify tenant 1 exceptions are gone
        assert store.get_exception("TENANT_001", "exc_001") is None
        
        # Verify tenant 2 exceptions still exist
        assert store.get_exception("TENANT_002", "exc_002") is not None

    def test_clear_all(self, sample_exception_1, sample_exception_2, sample_pipeline_result):
        """Test clearing all exceptions."""
        store = ExceptionStore()
        
        store.store_exception(sample_exception_1, sample_pipeline_result)
        
        result_2 = sample_pipeline_result.copy()
        result_2["exceptionId"] = "exc_002"
        store.store_exception(sample_exception_2, result_2)
        
        # Clear all
        store.clear_all()
        
        # Verify all exceptions are gone
        assert store.get_exception("TENANT_001", "exc_001") is None
        assert store.get_exception("TENANT_002", "exc_002") is None


class TestExceptionStoreTenantIsolation:
    """Tests for tenant isolation in ExceptionStore."""

    def test_tenant_isolation_separate_storage(
        self, sample_exception_1, sample_exception_2, sample_pipeline_result
    ):
        """Test that tenants have separate storage."""
        store = ExceptionStore()
        
        store.store_exception(sample_exception_1, sample_pipeline_result)
        
        result_2 = sample_pipeline_result.copy()
        result_2["exceptionId"] = "exc_002"
        store.store_exception(sample_exception_2, result_2)
        
        # Verify tenant 1 cannot access tenant 2's exception
        tenant_1_result = store.get_exception("TENANT_001", "exc_002")
        assert tenant_1_result is None
        
        # Verify tenant 2 cannot access tenant 1's exception
        tenant_2_result = store.get_exception("TENANT_002", "exc_001")
        assert tenant_2_result is None

    def test_tenant_isolation_same_exception_id(
        self, sample_exception_1, sample_pipeline_result
    ):
        """Test that same exception ID can exist for different tenants."""
        store = ExceptionStore()
        
        # Store exception for tenant 1
        store.store_exception(sample_exception_1, sample_pipeline_result)
        
        # Create exception with same ID for tenant 2
        exception_2 = ExceptionRecord(
            exceptionId="exc_001",  # Same ID
            tenantId="TENANT_002",  # Different tenant
            sourceSystem="CRM",
            timestamp="2024-01-15T11:00:00Z",
            rawPayload={"error": "Different error"},
        )
        
        result_2 = sample_pipeline_result.copy()
        store.store_exception(exception_2, result_2)
        
        # Verify both can be retrieved independently
        tenant_1_result = store.get_exception("TENANT_001", "exc_001")
        assert tenant_1_result is not None
        assert tenant_1_result[0].tenant_id == "TENANT_001"
        
        tenant_2_result = store.get_exception("TENANT_002", "exc_001")
        assert tenant_2_result is not None
        assert tenant_2_result[0].tenant_id == "TENANT_002"

    def test_tenant_isolation_get_tenant_exceptions(
        self, sample_exception_1, sample_exception_2, sample_pipeline_result
    ):
        """Test that get_tenant_exceptions only returns that tenant's exceptions."""
        store = ExceptionStore()
        
        store.store_exception(sample_exception_1, sample_pipeline_result)
        
        result_2 = sample_pipeline_result.copy()
        result_2["exceptionId"] = "exc_002"
        store.store_exception(sample_exception_2, result_2)
        
        # Get tenant 1 exceptions
        tenant_1_exceptions = store.get_tenant_exceptions("TENANT_001")
        assert len(tenant_1_exceptions) == 1
        assert all(exc[0].tenant_id == "TENANT_001" for exc in tenant_1_exceptions)
        
        # Get tenant 2 exceptions
        tenant_2_exceptions = store.get_tenant_exceptions("TENANT_002")
        assert len(tenant_2_exceptions) == 1
        assert all(exc[0].tenant_id == "TENANT_002" for exc in tenant_2_exceptions)


class TestExceptionStoreSingleton:
    """Tests for get_exception_store singleton."""

    def test_get_exception_store_returns_singleton(self):
        """Test that get_exception_store returns the same instance."""
        store1 = get_exception_store()
        store2 = get_exception_store()
        
        assert store1 is store2

    def test_singleton_persistence(self, sample_exception_1, sample_pipeline_result):
        """Test that singleton persists data across calls."""
        store1 = get_exception_store()
        store1.store_exception(sample_exception_1, sample_pipeline_result)
        
        store2 = get_exception_store()
        retrieved = store2.get_exception("TENANT_001", "exc_001")
        
        assert retrieved is not None
        assert retrieved[0].exception_id == "exc_001"

