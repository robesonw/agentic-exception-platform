"""
Comprehensive tests for UI Status API endpoints.

Tests:
- GET /ui/exceptions/{tenantId}
- Recent exceptions with statuses
- Status filtering
- Pagination
- UI-friendly output format
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.orchestrator.store import ExceptionStore, get_exception_store


@pytest.fixture
def exception_store():
    """Exception store for testing."""
    store = ExceptionStore()
    return store


@pytest.fixture
def client(exception_store):
    """Test client with mocked exception store."""
    # Patch get_exception_store to return our test store
    with patch("src.api.routes.ui_status.get_exception_store", return_value=exception_store):
        yield TestClient(app)


@pytest.fixture
def sample_exceptions():
    """Sample exceptions for testing."""
    base_time = datetime.now(timezone.utc)
    
    exceptions = []
    for i in range(5):
        exc = ExceptionRecord(
            exceptionId=f"exc_{i}",
            tenantId="TENANT_A",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH if i % 2 == 0 else Severity.MEDIUM,
            timestamp=base_time.replace(second=i),
            rawPayload={"orderId": f"ORD-{i:03d}"},
            resolutionStatus=ResolutionStatus.RESOLVED if i < 3 else ResolutionStatus.IN_PROGRESS,
        )
        
        pipeline_result = {
            "exceptionId": exc.exception_id,
            "status": exc.resolution_status.value,
            "stages": {
                "intake": {"status": "completed"},
                "triage": {"status": "completed"},
                "policy": {"status": "completed"},
                "resolution": {"status": "completed"},
                "feedback": {"status": "completed"},
            },
        }
        
        exceptions.append((exc, pipeline_result))
    
    return exceptions


DEFAULT_API_KEY = "test_api_key_tenant_001"  # Valid API key from auth.py


@pytest.fixture
def setup_api_key():
    """Setup API key for testing."""
    from src.api.auth import get_api_key_auth
    auth = get_api_key_auth()
    yield auth


class TestUIStatusAPI:
    """Tests for UI Status API endpoints."""

    def test_get_recent_exceptions_success(self, client, exception_store, sample_exceptions, setup_api_key):
        """Test successful retrieval of recent exceptions."""
        # Store exceptions
        tenant_id = "TENANT_A"
        for exception, pipeline_result in sample_exceptions:
            exception_store.store_exception(exception, pipeline_result)
        
        # Register API key for tenant
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        # Get exceptions via UI API
        response = client.get(
            f"/ui/exceptions/{tenant_id}",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["tenantId"] == tenant_id
        assert data["total"] == 5
        assert len(data["exceptions"]) == 5
        assert data["offset"] == 0
        assert data["limit"] == 50  # Default limit
        
        # Verify UI-friendly format
        exception = data["exceptions"][0]
        assert "exceptionId" in exception
        assert "exceptionType" in exception
        assert "severity" in exception
        assert "status" in exception
        assert "timestamp" in exception
        assert "sourceSystem" in exception
        assert "summary" in exception
        assert "lastUpdated" in exception

    def test_get_recent_exceptions_with_status_filter(self, client, exception_store, sample_exceptions, setup_api_key):
        """Test filtering exceptions by status."""
        # Store exceptions
        tenant_id = "TENANT_A"
        for exception, pipeline_result in sample_exceptions:
            exception_store.store_exception(exception, pipeline_result)
        
        # Register API key for tenant
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        # Get only RESOLVED exceptions
        response = client.get(
            f"/ui/exceptions/{tenant_id}",
            params={"status": "RESOLVED"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 3  # 3 resolved exceptions
        assert all(exc["status"] == "RESOLVED" for exc in data["exceptions"])

    def test_get_recent_exceptions_with_pagination(self, client, exception_store, sample_exceptions, setup_api_key):
        """Test pagination of exceptions."""
        # Store exceptions
        tenant_id = "TENANT_A"
        for exception, pipeline_result in sample_exceptions:
            exception_store.store_exception(exception, pipeline_result)
        
        # Register API key for tenant
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        # Get with limit and offset
        response = client.get(
            f"/ui/exceptions/{tenant_id}",
            params={"limit": 2, "offset": 1},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 5  # Total in store
        assert len(data["exceptions"]) == 2  # Limited to 2
        assert data["offset"] == 1
        assert data["limit"] == 2

    def test_get_recent_exceptions_invalid_status(self, client, exception_store, setup_api_key):
        """Test that invalid status filter returns 400."""
        tenant_id = "TENANT_A"
        
        # Register API key for tenant
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/ui/exceptions/{tenant_id}",
            params={"status": "INVALID_STATUS"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_get_recent_exceptions_empty_store(self, client, exception_store, setup_api_key):
        """Test getting exceptions from empty store."""
        tenant_id = "TENANT_A"
        
        # Register API key for tenant
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/ui/exceptions/{tenant_id}",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["tenantId"] == tenant_id
        assert data["total"] == 0
        assert len(data["exceptions"]) == 0

    def test_get_recent_exceptions_sorted_by_timestamp(self, client, exception_store, sample_exceptions, setup_api_key):
        """Test that exceptions are sorted by timestamp (most recent first)."""
        # Store exceptions
        tenant_id = "TENANT_A"
        for exception, pipeline_result in sample_exceptions:
            exception_store.store_exception(exception, pipeline_result)
        
        # Register API key for tenant
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/ui/exceptions/{tenant_id}",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify sorted by timestamp (most recent first)
        timestamps = [exc["timestamp"] for exc in data["exceptions"] if exc["timestamp"]]
        if len(timestamps) > 1:
            # Should be in descending order
            for i in range(len(timestamps) - 1):
                assert timestamps[i] >= timestamps[i + 1]

    def test_get_recent_exceptions_includes_stages(self, client, exception_store, sample_exceptions, setup_api_key):
        """Test that exceptions include stage information."""
        # Store exceptions
        tenant_id = "TENANT_A"
        for exception, pipeline_result in sample_exceptions:
            exception_store.store_exception(exception, pipeline_result)
        
        # Register API key for tenant
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/ui/exceptions/{tenant_id}",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify stages are included
        exception = data["exceptions"][0]
        assert "stages" in exception
        assert isinstance(exception["stages"], dict)
        
        # Verify stage structure
        for stage_name, stage_info in exception["stages"].items():
            assert "status" in stage_info
            assert "hasError" in stage_info

    def test_get_recent_exceptions_ui_friendly_format(self, client, exception_store, sample_exceptions, setup_api_key):
        """Test that output is UI-friendly format."""
        # Store exceptions
        tenant_id = "TENANT_A"
        for exception, pipeline_result in sample_exceptions:
            exception_store.store_exception(exception, pipeline_result)
        
        # Register API key for tenant
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/ui/exceptions/{tenant_id}",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify UI-friendly structure
        assert "tenantId" in data
        assert "exceptions" in data
        assert "total" in data
        assert "offset" in data
        assert "limit" in data
        
        exception = data["exceptions"][0]
        # Verify all required UI fields
        assert "exceptionId" in exception
        assert "exceptionType" in exception
        assert "severity" in exception
        assert "status" in exception
        assert "timestamp" in exception
        assert "sourceSystem" in exception
        assert "summary" in exception
        assert "lastUpdated" in exception
        
        # Verify timestamps are ISO format strings
        assert isinstance(exception["timestamp"], str)
        assert isinstance(exception["lastUpdated"], str)

    def test_get_recent_exceptions_summary_generation(self, client, exception_store, setup_api_key):
        """Test that summary is generated correctly."""
        # Store exception
        tenant_id = "TENANT_A"
        exception = ExceptionRecord(
            exceptionId="exc_1",
            tenantId=tenant_id,
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.RESOLVED,
        )
        
        pipeline_result = {
            "stages": {
                "intake": {"status": "completed"},
                "triage": {"status": "completed"},
            },
        }
        
        exception_store.store_exception(exception, pipeline_result)
        
        # Register API key for tenant
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/ui/exceptions/{tenant_id}",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        exception_data = data["exceptions"][0]
        assert "summary" in exception_data
        assert isinstance(exception_data["summary"], str)
        assert "SETTLEMENT_FAIL" in exception_data["summary"]
        assert "HIGH" in exception_data["summary"]
        assert "RESOLVED" in exception_data["summary"]
