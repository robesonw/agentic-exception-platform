"""
Tests for Status API endpoint.
Tests GET /exceptions/{tenantId}/{exceptionId} endpoint.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.auth import get_api_key_auth
from src.api.main import app
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.orchestrator.store import ExceptionStore, get_exception_store

client = TestClient(app)

# Default API key for tests
DEFAULT_API_KEY = "test_api_key_tenant_001"

# Additional API keys for multi-tenant tests
TENANT_A_API_KEY = "test_api_key_tenant_a"
TENANT_B_API_KEY = "test_api_key_tenant_b"


@pytest.fixture(autouse=True)
def reset_store():
    """Reset exception store before each test."""
    store = get_exception_store()
    store.clear_all()
    
    # Register API keys for multi-tenant tests
    auth = get_api_key_auth()
    auth.register_api_key(TENANT_A_API_KEY, "TENANT_A")
    auth.register_api_key(TENANT_B_API_KEY, "TENANT_B")
    
    yield
    
    store.clear_all()


class TestStatusAPISuccess:
    """Tests for successful status API retrieval."""

    def test_get_exception_status_returns_canonical_schema(self):
        """Test that GET endpoint returns canonical exception schema."""
        store = get_exception_store()
        
        # Create and store an exception
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_001",
            sourceSystem="ERP",
            exceptionType="DataQualityFailure",
            severity=Severity.HIGH,
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"error": "Invalid data format"},
            normalizedContext={"field": "value"},
            detectedRules=["rule1", "rule2"],
            suggestedActions=["action1"],
            resolutionStatus=ResolutionStatus.IN_PROGRESS,
        )
        
        pipeline_result = {
            "exceptionId": "exc_001",
            "status": "IN_PROGRESS",
            "stages": {
                "intake": {"decision": "normalized"},
                "triage": {"decision": "classified"},
            },
            "evidence": ["Evidence 1", "Evidence 2"],
        }
        
        store.store_exception(exception, pipeline_result)
        
        # Make request
        response = client.get("/exceptions/TENANT_001/exc_001", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify canonical schema fields
        assert data["exceptionId"] == "exc_001"
        assert data["tenantId"] == "TENANT_001"
        assert data["sourceSystem"] == "ERP"
        assert data["exceptionType"] == "DataQualityFailure"
        assert data["severity"] == "HIGH"
        assert data["resolutionStatus"] == "IN_PROGRESS"
        assert data["rawPayload"] == {"error": "Invalid data format"}
        assert data["normalizedContext"] == {"field": "value"}
        assert data["detectedRules"] == ["rule1", "rule2"]
        assert data["suggestedActions"] == ["action1"]

    def test_get_exception_status_includes_audit_trail(self):
        """Test that response includes audit trail."""
        from datetime import datetime, timezone
        
        from src.models.exception_record import AuditEntry
        
        store = get_exception_store()
        
        # Create exception with audit trail
        exception = ExceptionRecord(
            exceptionId="exc_002",
            tenantId="TENANT_001",
            sourceSystem="ERP",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={},
            auditTrail=[
                AuditEntry(
                    action="Exception normalized",
                    timestamp=datetime.now(timezone.utc),
                    actor="IntakeAgent",
                ),
                AuditEntry(
                    action="Exception classified",
                    timestamp=datetime.now(timezone.utc),
                    actor="TriageAgent",
                ),
            ],
        )
        
        pipeline_result = {
            "exceptionId": "exc_002",
            "status": "OPEN",
            "stages": {},
            "evidence": [],
        }
        
        store.store_exception(exception, pipeline_result)
        
        # Make request
        response = client.get("/exceptions/TENANT_001/exc_002", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify audit trail is included
        assert "auditTrail" in data
        assert len(data["auditTrail"]) == 2
        assert data["auditTrail"][0]["action"] == "Exception normalized"
        assert data["auditTrail"][0]["actor"] == "IntakeAgent"
        assert data["auditTrail"][1]["action"] == "Exception classified"
        assert data["auditTrail"][1]["actor"] == "TriageAgent"

    def test_get_exception_status_includes_pipeline_result(self):
        """Test that response includes pipeline result."""
        store = get_exception_store()
        
        exception = ExceptionRecord(
            exceptionId="exc_003",
            tenantId="TENANT_001",
            sourceSystem="ERP",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={},
        )
        
        pipeline_result = {
            "exceptionId": "exc_003",
            "status": "RESOLVED",
            "stages": {
                "intake": {"decision": "normalized", "confidence": 0.95},
                "triage": {"decision": "classified", "confidence": 0.90},
                "policy": {"decision": "actionable", "confidence": 0.85},
                "resolution": {"decision": "resolved", "confidence": 0.80},
            },
            "evidence": ["Evidence 1", "Evidence 2", "Evidence 3"],
        }
        
        store.store_exception(exception, pipeline_result)
        
        # Make request
        response = client.get("/exceptions/TENANT_001/exc_003", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify pipeline result is included
        assert "pipelineResult" in data
        assert data["pipelineResult"]["status"] == "RESOLVED"
        assert "stages" in data["pipelineResult"]
        assert "evidence" in data["pipelineResult"]
        assert len(data["pipelineResult"]["evidence"]) == 3

    def test_get_exception_status_includes_resolution_status(self):
        """Test that response includes current resolution status."""
        store = get_exception_store()
        
        exception = ExceptionRecord(
            exceptionId="exc_004",
            tenantId="TENANT_001",
            sourceSystem="ERP",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={},
            resolutionStatus=ResolutionStatus.RESOLVED,
        )
        
        pipeline_result = {
            "exceptionId": "exc_004",
            "status": "RESOLVED",
            "stages": {},
            "evidence": [],
        }
        
        store.store_exception(exception, pipeline_result)
        
        # Make request
        response = client.get("/exceptions/TENANT_001/exc_004", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify resolution status
        assert data["resolutionStatus"] == "RESOLVED"


class TestStatusAPINotFound:
    """Tests for 404 error handling."""

    def test_get_exception_status_404_missing_exception(self):
        """Test that 404 is returned for missing exception."""
        response = client.get("/exceptions/TENANT_001/nonexistent_exc", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "nonexistent_exc" in data["detail"]
        assert "TENANT_001" in data["detail"]

    def test_get_exception_status_404_missing_tenant(self):
        """Test that 404 is returned for missing tenant."""
        # Register API key for NONEXISTENT_TENANT to avoid 403
        from src.api.auth import get_api_key_auth
        auth = get_api_key_auth()
        auth.register_api_key("test_key_nonexistent", "NONEXISTENT_TENANT")
        
        response = client.get("/exceptions/NONEXISTENT_TENANT/exc_001", headers={"X-API-KEY": "test_key_nonexistent"})
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestStatusAPITenantIsolation:
    """Tests for tenant isolation in status API."""

    def test_tenant_isolation_cannot_read_other_tenant_exception(self):
        """Test that tenant A cannot read tenant B's exception."""
        store = get_exception_store()
        
        # Store exception for tenant A
        exception_a = ExceptionRecord(
            exceptionId="exc_tenant_a",
            tenantId="TENANT_A",
            sourceSystem="ERP",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"data": "tenant_a"},
        )
        
        pipeline_result = {
            "exceptionId": "exc_tenant_a",
            "status": "OPEN",
            "stages": {},
            "evidence": [],
        }
        
        store.store_exception(exception_a, pipeline_result)
        
        # Try to retrieve as tenant B (should return 404)
        response = client.get("/exceptions/TENANT_B/exc_tenant_a", headers={"X-API-KEY": TENANT_B_API_KEY})
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_tenant_isolation_same_exception_id_different_tenants(self):
        """Test that same exception ID can exist for different tenants."""
        store = get_exception_store()
        
        # Store exception for tenant A
        exception_a = ExceptionRecord(
            exceptionId="exc_shared_id",
            tenantId="TENANT_A",
            sourceSystem="ERP",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"data": "tenant_a"},
        )
        
        # Store exception for tenant B with same ID
        exception_b = ExceptionRecord(
            exceptionId="exc_shared_id",
            tenantId="TENANT_B",
            sourceSystem="ERP",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"data": "tenant_b"},
        )
        
        pipeline_result_a = {
            "exceptionId": "exc_shared_id",
            "status": "OPEN",
            "stages": {},
            "evidence": [],
        }
        
        pipeline_result_b = {
            "exceptionId": "exc_shared_id",
            "status": "OPEN",
            "stages": {},
            "evidence": [],
        }
        
        store.store_exception(exception_a, pipeline_result_a)
        store.store_exception(exception_b, pipeline_result_b)
        
        # Retrieve tenant A's exception
        response_a = client.get("/exceptions/TENANT_A/exc_shared_id", headers={"X-API-KEY": TENANT_A_API_KEY})
        assert response_a.status_code == 200
        data_a = response_a.json()
        assert data_a["tenantId"] == "TENANT_A"
        assert data_a["rawPayload"] == {"data": "tenant_a"}
        
        # Retrieve tenant B's exception
        response_b = client.get("/exceptions/TENANT_B/exc_shared_id", headers={"X-API-KEY": TENANT_B_API_KEY})
        assert response_b.status_code == 200
        data_b = response_b.json()
        assert data_b["tenantId"] == "TENANT_B"
        assert data_b["rawPayload"] == {"data": "tenant_b"}


class TestStatusAPIResponseStructure:
    """Tests for response structure and format."""

    def test_response_structure_matches_canonical_schema(self):
        """Test that response structure matches canonical exception schema."""
        store = get_exception_store()
        
        exception = ExceptionRecord(
            exceptionId="exc_005",
            tenantId="TENANT_001",
            sourceSystem="ERP",
            exceptionType="DataQualityFailure",
            severity=Severity.HIGH,
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"error": "Invalid data"},
            normalizedContext={"field": "value"},
            detectedRules=["rule1"],
            suggestedActions=["action1"],
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        pipeline_result = {
            "exceptionId": "exc_005",
            "status": "OPEN",
            "stages": {},
            "evidence": [],
        }
        
        store.store_exception(exception, pipeline_result)
        
        response = client.get("/exceptions/TENANT_001/exc_005", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all canonical schema fields are present
        required_fields = [
            "exceptionId",
            "tenantId",
            "sourceSystem",
            "timestamp",
            "rawPayload",
            "normalizedContext",
            "detectedRules",
            "suggestedActions",
            "resolutionStatus",
            "auditTrail",
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify optional fields
        assert "exceptionType" in data
        assert "severity" in data
        
        # Verify pipeline result is included
        assert "pipelineResult" in data

    def test_response_includes_pipeline_errors_if_present(self):
        """Test that pipeline errors are included in response if present."""
        store = get_exception_store()
        
        exception = ExceptionRecord(
            exceptionId="exc_006",
            tenantId="TENANT_001",
            sourceSystem="ERP",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={},
        )
        
        pipeline_result = {
            "exceptionId": "exc_006",
            "status": "ESCALATED",
            "stages": {
                "intake": {"error": "IntakeAgent failed"},
            },
            "evidence": [],
            "errors": ["IntakeAgent failed: Connection timeout"],
        }
        
        store.store_exception(exception, pipeline_result)
        
        response = client.get("/exceptions/TENANT_001/exc_006", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify errors are included
        assert "pipelineResult" in data
        assert "errors" in data["pipelineResult"]
        assert len(data["pipelineResult"]["errors"]) == 1
        assert "Connection timeout" in data["pipelineResult"]["errors"][0]


class TestStatusAPIIntegration:
    """Integration tests for status API."""

    @pytest.mark.asyncio
    async def test_status_api_after_pipeline_run(self):
        """Test that status API works after pipeline run."""
        from src.domainpack.loader import load_domain_pack
        from src.orchestrator.runner import run_pipeline
        from src.tenantpack.loader import load_tenant_policy
        
        # Load packs
        domain_pack = load_domain_pack("domainpacks/finance.sample.json")
        tenant_policy = load_tenant_policy("tenantpacks/tenant_finance.sample.json")
        
        # Run pipeline
        exceptions = [
            {
                "tenantId": "TENANT_FINANCE_001",
                "sourceSystem": "TradingSystem",
                "exceptionType": "POSITION_BREAK",
                "rawPayload": {"accountId": "ACC-123"},
            }
        ]
        
        result = await run_pipeline(
            domain_pack=domain_pack,
            tenant_policy=tenant_policy,
            exceptions_batch=exceptions,
        )
        
        # Get exception ID from result
        assert len(result["results"]) > 0
        exception_id = result["results"][0].get("exceptionId")
        assert exception_id is not None
        
        # Register API key for TENANT_FINANCE_001
        from src.api.auth import get_api_key_auth
        auth = get_api_key_auth()
        finance_api_key = "test_api_key_tenant_finance_001"
        auth.register_api_key(finance_api_key, "TENANT_FINANCE_001")
        
        # Retrieve via status API
        response = client.get(f"/exceptions/TENANT_FINANCE_001/{exception_id}", headers={"X-API-KEY": finance_api_key})
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify exception data
        assert data["exceptionId"] == exception_id
        assert data["tenantId"] == "TENANT_FINANCE_001"
        assert "pipelineResult" in data
        assert "stages" in data["pipelineResult"]

