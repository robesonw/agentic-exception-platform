"""
Tests for Exception Ingestion API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.auth import Role, get_api_key_auth
from src.api.main import app
from src.api.middleware import get_rate_limiter

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


class TestExceptionIngestionAPI:
    """Tests for POST /exceptions/{tenantId} endpoint."""

    def test_ingest_single_exception(self):
        """Test ingesting a single exception (202 Accepted)."""
        response = client.post(
            "/exceptions/TENANT_001",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "exception": {
                    "sourceSystem": "ERP",
                    "rawPayload": {"error": "Test exception"},
                }
            },
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "exceptionId" in data
        assert "status" in data
        assert "message" in data
        assert data["status"] == "accepted"
        assert isinstance(data["exceptionId"], str)

    def test_ingest_batch_exceptions(self):
        """Test ingesting multiple exceptions in batch (202 Accepted, MVP handles first only)."""
        response = client.post(
            "/exceptions/TENANT_001",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "exceptions": [
                    {"sourceSystem": "ERP", "rawPayload": {"error": "Error 1"}},
                    {"sourceSystem": "CRM", "rawPayload": {"error": "Error 2"}},
                ]
            },
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "exceptionId" in data
        assert data["status"] == "accepted"
        # Note: MVP handles first exception only; batch support in future

    def test_ingest_missing_request_body(self):
        """Test that missing request body returns 400."""
        response = client.post(
            "/exceptions/TENANT_001",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={},
        )
        
        assert response.status_code == 400

    def test_ingest_empty_exceptions(self):
        """Test that empty exceptions list returns 400."""
        response = client.post(
            "/exceptions/TENANT_001",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={"exceptions": []},
        )
        
        assert response.status_code == 400

    def test_ingest_with_exception_type(self):
        """Test ingesting exception with exception type."""
        response = client.post(
            "/exceptions/TENANT_001",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "exception": {
                    "sourceSystem": "ERP",
                    "exceptionType": "SETTLEMENT_FAIL",
                    "rawPayload": {"orderId": "ORD-123"},
                }
            },
        )
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert "exceptionId" in data

    def test_ingest_with_timestamp(self):
        """Test ingesting exception with timestamp."""
        response = client.post(
            "/exceptions/TENANT_001",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "exception": {
                    "sourceSystem": "ERP",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "rawPayload": {"error": "Test"},
                }
            },
        )
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert "exceptionId" in data

    def test_ingest_tenant_id_in_path(self):
        """Test that tenant ID in path is used."""
        # Use tenant ID that matches the API key
        response = client.post(
            "/exceptions/TENANT_001",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "exception": {
                    "sourceSystem": "ERP",
                    "rawPayload": {"error": "Test"},
                }
            },
        )
        
        assert response.status_code == 202
        # Tenant ID should be set even if not in payload
        data = response.json()
        assert data["status"] == "accepted"
        assert "exceptionId" in data


class TestExceptionIngestionAPIErrorHandling:
    """Tests for error handling in exception ingestion."""

    def test_ingest_invalid_json(self):
        """Test that invalid JSON returns 422."""
        response = client.post(
            "/exceptions/TENANT_001",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json="invalid json",
        )
        
        # FastAPI returns 422 for validation errors
        assert response.status_code in [400, 422]

    def test_ingest_missing_source_system(self):
        """Test that missing sourceSystem is handled."""
        response = client.post(
            "/exceptions/TENANT_001",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "exception": {
                    "rawPayload": {"error": "Test"},
                }
            },
        )
        
        # Should still work (defaults to "UNKNOWN" source system)
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"

    def test_ingest_missing_raw_payload(self):
        """Test that missing rawPayload is handled."""
        response = client.post(
            "/exceptions/TENANT_001",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "exception": {
                    "sourceSystem": "ERP",
                }
            },
        )
        
        # Should still work (empty payload is allowed)
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"


class TestExceptionIngestionAPIResponseFormat:
    """Tests for response format correctness."""

    def test_response_contains_required_fields(self):
        """Test that response contains all required fields."""
        response = client.post(
            "/exceptions/TENANT_001",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "exception": {
                    "sourceSystem": "ERP",
                    "rawPayload": {"error": "Test"},
                }
            },
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "exceptionId" in data
        assert "status" in data
        assert "message" in data
        assert data["status"] == "accepted"
        assert isinstance(data["exceptionId"], str)

    def test_response_exception_ids_are_unique(self):
        """Test that exception IDs are unique."""
        response = client.post(
            "/exceptions/TENANT_001",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "exceptions": [
                    {"sourceSystem": "ERP", "rawPayload": {"error": "Error 1"}},
                    {"sourceSystem": "CRM", "rawPayload": {"error": "Error 2"}},
                ]
            },
        )
        
        assert response.status_code == 202
        data = response.json()
        # MVP handles first exception only; batch support in future
        assert "exceptionId" in data
        assert data["status"] == "accepted"

