"""
Tests for Exception Ingestion API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

# Default API key for tests
DEFAULT_API_KEY = "test_api_key_tenant_001"


class TestExceptionIngestionAPI:
    """Tests for POST /exceptions/{tenantId} endpoint."""

    def test_ingest_single_exception(self):
        """Test ingesting a single exception."""
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
        
        assert response.status_code == 200
        data = response.json()
        assert "exceptionIds" in data
        assert "count" in data
        assert data["count"] == 1
        assert len(data["exceptionIds"]) == 1
        assert isinstance(data["exceptionIds"][0], str)

    def test_ingest_batch_exceptions(self):
        """Test ingesting multiple exceptions in batch."""
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
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["exceptionIds"]) == 2

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
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1

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
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1

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
        
        assert response.status_code == 200
        # Tenant ID should be set even if not in payload
        data = response.json()
        assert data["count"] == 1


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
        
        # Should still work (IntakeAgent uses "UNKNOWN" as default)
        assert response.status_code == 200

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
        
        # Should still work (IntakeAgent uses exception dict as payload)
        assert response.status_code == 200


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
        
        assert response.status_code == 200
        data = response.json()
        assert "exceptionIds" in data
        assert "count" in data
        assert isinstance(data["exceptionIds"], list)
        assert isinstance(data["count"], int)

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
        
        assert response.status_code == 200
        data = response.json()
        exception_ids = data["exceptionIds"]
        assert len(exception_ids) == len(set(exception_ids))  # All unique

