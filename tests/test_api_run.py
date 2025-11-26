"""
Tests for Pipeline Run API endpoints.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.auth import Role, get_api_key_auth
from src.api.main import app

client = TestClient(app)

# Default API key for tests
DEFAULT_API_KEY = "test_api_key_tenant_001"
FINANCE_API_KEY = "test_api_key_tenant_finance_001"


@pytest.fixture
def sample_domain_pack_path():
    """Path to sample domain pack."""
    return "domainpacks/finance.sample.json"


@pytest.fixture
def sample_tenant_policy_path():
    """Path to sample tenant policy."""
    return "tenantpacks/tenant_finance.sample.json"


@pytest.fixture(autouse=True)
def setup_api_keys():
    """Set up API keys for tests."""
    from src.api.middleware import get_rate_limiter
    auth = get_api_key_auth()
    auth.register_api_key(FINANCE_API_KEY, "TENANT_FINANCE_001", Role.ADMIN)
    auth.register_api_key(DEFAULT_API_KEY, "TENANT_001", Role.ADMIN)
    limiter = get_rate_limiter()
    yield
    # Reset rate limiter after each test
    limiter._request_timestamps.clear()
    # Cleanup handled by auth fixture in other test files


@pytest.fixture
def sample_exceptions():
    """Sample exceptions for testing."""
    return [
        {
            "tenantId": "TENANT_FINANCE_001",
            "sourceSystem": "TradingSystem",
            "exceptionType": "POSITION_BREAK",
            "rawPayload": {
                "accountId": "ACC-123",
                "cusip": "CUSIP-456",
                "expectedPosition": 1000,
                "actualPosition": 950,
            },
        }
    ]


class TestRunPipelineAPI:
    """Tests for POST /run endpoint."""

    def test_execute_pipeline_success(
        self, sample_domain_pack_path, sample_tenant_policy_path, sample_exceptions
    ):
        """Test successful pipeline execution."""
        # Verify files exist
        assert Path(sample_domain_pack_path).exists()
        assert Path(sample_tenant_policy_path).exists()
        
        response = client.post(
            "/run",
            headers={"X-API-KEY": FINANCE_API_KEY},
            json={
                "domainPackPath": sample_domain_pack_path,
                "tenantPolicyPath": sample_tenant_policy_path,
                "exceptions": sample_exceptions,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "tenantId" in data
        assert "runId" in data
        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) == 1

    def test_execute_pipeline_missing_domain_pack(self, sample_tenant_policy_path, sample_exceptions):
        """Test that missing domain pack file returns 400."""
        response = client.post(
            "/run",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "domainPackPath": "nonexistent/pack.json",
                "tenantPolicyPath": sample_tenant_policy_path,
                "exceptions": sample_exceptions,
            },
        )
        
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    def test_execute_pipeline_missing_tenant_policy(self, sample_domain_pack_path, sample_exceptions):
        """Test that missing tenant policy file returns 400."""
        response = client.post(
            "/run",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "domainPackPath": sample_domain_pack_path,
                "tenantPolicyPath": "nonexistent/policy.json",
                "exceptions": sample_exceptions,
            },
        )
        
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    def test_execute_pipeline_empty_exceptions(self, sample_domain_pack_path, sample_tenant_policy_path):
        """Test that empty exceptions list returns 400."""
        response = client.post(
            "/run",
            headers={"X-API-KEY": FINANCE_API_KEY},
            json={
                "domainPackPath": sample_domain_pack_path,
                "tenantPolicyPath": sample_tenant_policy_path,
                "exceptions": [],
            },
        )
        
        assert response.status_code == 400
        assert "No exceptions" in response.json()["detail"]

    def test_execute_pipeline_multiple_exceptions(
        self, sample_domain_pack_path, sample_tenant_policy_path
    ):
        """Test pipeline execution with multiple exceptions."""
        exceptions = [
            {
                "tenantId": "TENANT_FINANCE_001",
                "sourceSystem": "TradingSystem",
                "exceptionType": "POSITION_BREAK",
                "rawPayload": {"accountId": "ACC-123"},
            },
            {
                "tenantId": "TENANT_FINANCE_001",
                "sourceSystem": "SettlementSystem",
                "exceptionType": "SETTLEMENT_FAIL",
                "rawPayload": {"orderId": "ORD-789"},
            },
        ]
        
        response = client.post(
            "/run",
            headers={"X-API-KEY": FINANCE_API_KEY},
            json={
                "domainPackPath": sample_domain_pack_path,
                "tenantPolicyPath": sample_tenant_policy_path,
                "exceptions": exceptions,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2


class TestRunPipelineAPIResponseFormat:
    """Tests for response format correctness."""

    def test_response_contains_required_fields(
        self, sample_domain_pack_path, sample_tenant_policy_path, sample_exceptions
    ):
        """Test that response contains all required fields."""
        response = client.post(
            "/run",
            headers={"X-API-KEY": FINANCE_API_KEY},
            json={
                "domainPackPath": sample_domain_pack_path,
                "tenantPolicyPath": sample_tenant_policy_path,
                "exceptions": sample_exceptions,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "tenantId" in data
        assert "runId" in data
        assert "results" in data
        assert isinstance(data["tenantId"], str)
        assert isinstance(data["runId"], str)
        assert isinstance(data["results"], list)

    def test_response_results_structure(
        self, sample_domain_pack_path, sample_tenant_policy_path, sample_exceptions
    ):
        """Test that results have correct structure."""
        response = client.post(
            "/run",
            headers={"X-API-KEY": FINANCE_API_KEY},
            json={
                "domainPackPath": sample_domain_pack_path,
                "tenantPolicyPath": sample_tenant_policy_path,
                "exceptions": sample_exceptions,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        result = data["results"][0]
        
        assert "exceptionId" in result
        assert "status" in result
        assert "stages" in result
        assert "evidence" in result
        assert "exception" in result
        
        # Verify stages structure
        stages = result["stages"]
        assert "intake" in stages
        assert "triage" in stages
        assert "policy" in stages
        assert "resolution" in stages
        assert "feedback" in stages


class TestRunPipelineAPIErrorHandling:
    """Tests for error handling in pipeline execution."""

    def test_invalid_domain_pack_json(self, sample_tenant_policy_path, sample_exceptions, tmp_path):
        """Test that invalid domain pack JSON returns 400."""
        invalid_pack = tmp_path / "invalid_pack.json"
        invalid_pack.write_text("{ invalid json }")
        
        response = client.post(
            "/run",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "domainPackPath": str(invalid_pack),
                "tenantPolicyPath": sample_tenant_policy_path,
                "exceptions": sample_exceptions,
            },
        )
        
        assert response.status_code in [400, 500]
        assert "validation" in response.json()["detail"].lower() or "json" in response.json()["detail"].lower()

    def test_invalid_tenant_policy_json(self, sample_domain_pack_path, sample_exceptions, tmp_path):
        """Test that invalid tenant policy JSON returns 400."""
        invalid_policy = tmp_path / "invalid_policy.json"
        invalid_policy.write_text("{ invalid json }")
        
        response = client.post(
            "/run",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "domainPackPath": sample_domain_pack_path,
                "tenantPolicyPath": str(invalid_policy),
                "exceptions": sample_exceptions,
            },
        )
        
        assert response.status_code in [400, 500]
        assert "validation" in response.json()["detail"].lower() or "json" in response.json()["detail"].lower()

    def test_missing_request_fields(self):
        """Test that missing required fields return 422."""
        response = client.post(
            "/run",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "domainPackPath": "path/to/pack.json",
                # Missing tenantPolicyPath and exceptions
            },
        )
        
        assert response.status_code == 422  # Validation error


class TestRunPipelineAPIIntegration:
    """Integration tests for pipeline execution."""

    def test_end_to_end_pipeline_execution(
        self, sample_domain_pack_path, sample_tenant_policy_path
    ):
        """Test complete end-to-end pipeline execution."""
        exceptions = [
            {
                "tenantId": "TENANT_FINANCE_001",
                "sourceSystem": "TradingSystem",
                "exceptionType": "POSITION_BREAK",
                "rawPayload": {
                    "accountId": "ACC-123",
                    "cusip": "CUSIP-456",
                    "expectedPosition": 1000,
                    "actualPosition": 950,
                },
            }
        ]
        
        response = client.post(
            "/run",
            headers={"X-API-KEY": FINANCE_API_KEY},
            json={
                "domainPackPath": sample_domain_pack_path,
                "tenantPolicyPath": sample_tenant_policy_path,
                "exceptions": exceptions,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify tenant ID matches
        assert data["tenantId"] == "TENANT_FINANCE_001"
        
        # Verify run ID is generated
        assert data["runId"] is not None
        assert len(data["runId"]) > 0
        
        # Verify exception was processed
        result = data["results"][0]
        assert result["exceptionId"] is not None
        assert result["status"] in ["OPEN", "IN_PROGRESS", "ESCALATED", "RESOLVED"]
        
        # Verify all stages executed
        assert "intake" in result["stages"]
        assert "triage" in result["stages"]
        assert "policy" in result["stages"]
        assert "resolution" in result["stages"]
        assert "feedback" in result["stages"]
        
        # Verify exception data
        exception_data = result["exception"]
        assert exception_data["exceptionType"] == "POSITION_BREAK"
        assert exception_data["severity"] == "CRITICAL"

