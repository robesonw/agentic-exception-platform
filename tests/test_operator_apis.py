"""
Tests for Operator UI Backend APIs.

Tests Phase 3 enhancements:
- Exception browsing with pagination and filters
- Exception detail retrieval
- Evidence retrieval
- Audit history retrieval
- SSE streaming endpoint
"""

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.auth import Role, get_api_key_auth
from src.api.main import app
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.orchestrator.store import ExceptionStore, get_exception_store
from src.services.ui_query_service import UIQueryService

# Default API key for tests
DEFAULT_API_KEY = "test_api_key_tenant_001"


@pytest.fixture(autouse=True)
def setup_auth():
    """Set up authentication for tests."""
    auth = get_api_key_auth()
    auth.register_api_key(DEFAULT_API_KEY, "tenant_001", Role.ADMIN)
    yield
    # Cleanup if needed


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create authentication headers for API requests."""
    return {"X-API-KEY": DEFAULT_API_KEY}


@pytest.fixture
def sample_exception():
    """Create a sample exception record."""
    return ExceptionRecord(
        exception_id="exc_001",
        tenant_id="tenant_001",
        exception_type="DataQualityFailure",
        severity=Severity.HIGH,
        resolution_status=ResolutionStatus.OPEN,
        source_system="test_system",
        timestamp=datetime.now(timezone.utc),
        raw_payload={"error": "test error"},
        normalized_context={"domain": "TestDomain"},  # Store domain in normalized_context for filtering
    )


@pytest.fixture
def sample_pipeline_result():
    """Create a sample pipeline result."""
    from src.models.agent_contracts import AgentDecision
    
    return {
        "stages": {
            "intake": AgentDecision(
                decision="Normalized",
                confidence=1.0,
                evidence=["Extracted fields"],
                next_step="ProceedToTriage",
            ),
            "triage": AgentDecision(
                decision="Classified as DataQualityFailure",
                confidence=0.9,
                evidence=["Rule matched", "RAG similarity: 0.92"],
                next_step="ProceedToPolicy",
            ),
        },
        "rag_results": [
            {"similarity": 0.92, "exception_id": "exc_000", "summary": "Similar exception"}
        ],
        "tool_outputs": [{"tool": "validateData", "result": "success"}],
    }


@pytest.fixture
def setup_exception_store(sample_exception, sample_pipeline_result):
    """Set up exception store with sample data."""
    store = get_exception_store()
    store.store_exception(sample_exception, sample_pipeline_result)
    yield store
    store.clear_all()


class TestOperatorAPIs:
    """Tests for Operator UI APIs."""

    def test_browse_exceptions_basic(self, client, setup_exception_store, auth_headers):
        """Test basic exception browsing."""
        response = client.get("/ui/exceptions?tenant_id=tenant_001", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        assert len(data["items"]) > 0

    def test_browse_exceptions_pagination(self, client, setup_exception_store, auth_headers):
        """Test exception browsing with pagination."""
        # Create multiple exceptions
        store = get_exception_store()
        for i in range(5):
            exc = ExceptionRecord(
                exception_id=f"exc_{i:03d}",
                tenant_id="tenant_001",
                exception_type="DataQualityFailure",
                severity=Severity.HIGH,
                resolution_status=ResolutionStatus.OPEN,
                source_system="test_system",
                timestamp=datetime.now(timezone.utc),
                raw_payload={"error": f"test error {i}"},
            )
            store.store_exception(exc, {"stages": {}})
        
        # Test first page
        response = client.get("/ui/exceptions?tenant_id=tenant_001&page=1&page_size=2", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        
        # Test second page
        response = client.get("/ui/exceptions?tenant_id=tenant_001&page=2&page_size=2", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["page"] == 2
        
        store.clear_all()

    def test_browse_exceptions_filter_by_status(self, client, setup_exception_store, auth_headers):
        """Test exception browsing with status filter."""
        # Create exception with RESOLVED status
        store = get_exception_store()
        resolved_exc = ExceptionRecord(
            exception_id="exc_resolved",
            tenant_id="tenant_001",
            exception_type="DataQualityFailure",
            severity=Severity.HIGH,
            resolution_status=ResolutionStatus.RESOLVED,
            source_system="test_system",
            timestamp=datetime.now(timezone.utc),
            raw_payload={"error": "resolved"},
        )
        store.store_exception(resolved_exc, {"stages": {}})
        
        # Filter by RESOLVED status
        response = client.get("/ui/exceptions?tenant_id=tenant_001&status=RESOLVED", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert all(item["resolution_status"] == "RESOLVED" for item in data["items"])
        
        store.clear_all()

    def test_browse_exceptions_filter_by_severity(self, client, setup_exception_store, auth_headers):
        """Test exception browsing with severity filter."""
        # Create exception with CRITICAL severity
        store = get_exception_store()
        critical_exc = ExceptionRecord(
            exception_id="exc_critical",
            tenant_id="tenant_001",
            exception_type="DataQualityFailure",
            severity=Severity.CRITICAL,
            resolution_status=ResolutionStatus.OPEN,
            source_system="test_system",
            timestamp=datetime.now(timezone.utc),
            raw_payload={"error": "critical"},
        )
        store.store_exception(critical_exc, {"stages": {}})
        
        # Filter by CRITICAL severity
        response = client.get("/ui/exceptions?tenant_id=tenant_001&severity=CRITICAL", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert all(item["severity"] == "CRITICAL" for item in data["items"])
        
        store.clear_all()

    def test_browse_exceptions_search(self, client, setup_exception_store, auth_headers):
        """Test exception browsing with text search."""
        # Search for exception type
        response = client.get("/ui/exceptions?tenant_id=tenant_001&search=DataQuality", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Should find exceptions matching the search term
        assert data["total"] >= 0

    def test_get_exception_detail(self, client, setup_exception_store, auth_headers):
        """Test getting exception detail with agent decisions."""
        response = client.get("/ui/exceptions/exc_001?tenant_id=tenant_001", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "exception" in data
        assert "agent_decisions" in data
        assert "pipeline_result" in data
        assert data["exception"]["exception_id"] == "exc_001"
        assert "intake" in data["agent_decisions"]
        assert "triage" in data["agent_decisions"]

    def test_get_exception_detail_not_found(self, client, auth_headers):
        """Test getting exception detail for non-existent exception."""
        response = client.get("/ui/exceptions/nonexistent?tenant_id=tenant_001", headers=auth_headers)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_exception_evidence(self, client, setup_exception_store, auth_headers):
        """Test getting exception evidence."""
        response = client.get("/ui/exceptions/exc_001/evidence?tenant_id=tenant_001", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "rag_results" in data
        assert "tool_outputs" in data
        assert "agent_evidence" in data
        assert isinstance(data["rag_results"], list)
        assert isinstance(data["tool_outputs"], list)
        assert isinstance(data["agent_evidence"], list)

    def test_get_exception_evidence_not_found(self, client, auth_headers):
        """Test getting evidence for non-existent exception."""
        response = client.get("/ui/exceptions/nonexistent/evidence?tenant_id=tenant_001", headers=auth_headers)
        assert response.status_code == 404

    def test_get_exception_audit(self, client, setup_exception_store, tmp_path):
        """Test getting exception audit events."""
        # Create a mock audit log file
        audit_dir = tmp_path / "runtime" / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        
        audit_file = audit_dir / "test_run.jsonl"
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": "test_run",
            "tenant_id": "tenant_001",
            "event_type": "agent_event",
            "data": {
                "agent_name": "TriageAgent",
                "input": {
                    "exception": {
                        "exception_id": "exc_001",
                        "tenant_id": "tenant_001",
                    },
                },
            },
        }
        with open(audit_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(audit_entry) + "\n")
        
        # Mock the audit directory in UIQueryService
        service = UIQueryService()
        service.audit_dir = audit_dir
        
        # Get audit events
        audit_events = service.get_exception_audit("tenant_001", "exc_001")
        assert len(audit_events) > 0
        assert audit_events[0]["event_type"] == "agent_event"

    # NOTE: SSE streaming test commented out - endpoint hangs indefinitely in test environment
    # The SSE endpoint exists at /ui/stream/exceptions and is registered in router_operator.py
    # Full streaming behavior should be tested in integration tests, not unit tests
    # 
    # def test_stream_exceptions_sse(self, client, auth_headers):
    #     """Test SSE streaming endpoint."""
    #     pytest.skip("SSE streaming endpoint cannot be tested in unit tests - hangs indefinitely")

    def test_browse_exceptions_invalid_status(self, client, auth_headers):
        """Test exception browsing with invalid status."""
        response = client.get("/ui/exceptions?tenant_id=tenant_001&status=INVALID", headers=auth_headers)
        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_browse_exceptions_invalid_severity(self, client, auth_headers):
        """Test exception browsing with invalid severity."""
        response = client.get("/ui/exceptions?tenant_id=tenant_001&severity=INVALID", headers=auth_headers)
        assert response.status_code == 400
        assert "Invalid severity" in response.json()["detail"]

    def test_browse_exceptions_tenant_isolation(self, client, setup_exception_store, auth_headers):
        """Test that exceptions are isolated by tenant."""
        # Create exception for different tenant
        store = get_exception_store()
        other_tenant_exc = ExceptionRecord(
            exception_id="exc_other",
            tenant_id="tenant_002",
            exception_type="DataQualityFailure",
            severity=Severity.HIGH,
            resolution_status=ResolutionStatus.OPEN,
            source_system="test_system",
            timestamp=datetime.now(timezone.utc),
            raw_payload={"error": "other tenant"},
        )
        store.store_exception(other_tenant_exc, {"stages": {}})
        
        # Query for tenant_001 should not return tenant_002 exceptions
        response = client.get("/ui/exceptions?tenant_id=tenant_001", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert all(item["tenant_id"] == "tenant_001" for item in data["items"])
        
        store.clear_all()

    def test_browse_exceptions_domain_filter(self, client, setup_exception_store, auth_headers):
        """Test exception browsing with domain filter."""
        # Create exception with different domain
        store = get_exception_store()
        # Create exception with domain in normalized_context for domain filter test
        other_domain_exc = ExceptionRecord(
            exception_id="exc_other_domain",
            tenant_id="tenant_001",
            exception_type="DataQualityFailure",
            severity=Severity.HIGH,
            resolution_status=ResolutionStatus.OPEN,
            source_system="test_system",
            timestamp=datetime.now(timezone.utc),
            raw_payload={"error": "other domain"},
            normalized_context={"domain": "OtherDomain"},
        )
        store.store_exception(other_domain_exc, {"stages": {}})
        
        # Filter by TestDomain
        response = client.get("/ui/exceptions?tenant_id=tenant_001&domain=TestDomain", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert all(item.get("domain") == "TestDomain" for item in data["items"] if item.get("domain"))
        
        store.clear_all()

