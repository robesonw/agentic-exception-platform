"""
Comprehensive tests for Advanced Dashboard APIs.

Tests:
- GET /dashboards/{tenantId}/summary
- GET /dashboards/{tenantId}/exceptions
- GET /dashboards/{tenantId}/playbooks
- GET /dashboards/{tenantId}/tools
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import dashboards
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.observability.metrics import MetricsCollector
from src.orchestrator.store import ExceptionStore

DEFAULT_API_KEY = "test_api_key_tenant_001"


@pytest.fixture
def metrics_collector():
    """Metrics collector for testing."""
    return MetricsCollector()


@pytest.fixture
def exception_store():
    """Exception store for testing."""
    return ExceptionStore()


@pytest.fixture
def sample_exception():
    """Sample exception record for testing."""
    return ExceptionRecord(
        exceptionId="EX001",
        tenantId="TENANT_A",
        sourceSystem="ERP",
        exceptionType="SETTLEMENT_FAIL",
        severity=Severity.HIGH,
        timestamp=datetime.now(timezone.utc),
        rawPayload={"orderId": "ORD001", "error": "Settlement failed"},
        resolutionStatus=ResolutionStatus.RESOLVED,
    )


@pytest.fixture
def client(metrics_collector, exception_store, sample_exception):
    """Test client with mocked dependencies."""
    # Setup metrics
    metrics_collector.record_exception(
        tenant_id="TENANT_A",
        status="RESOLVED",
        exception_type="SETTLEMENT_FAIL",
        exception_id="EX001",
        confidence=0.8,
    )
    metrics_collector.record_playbook_execution(
        tenant_id="TENANT_A",
        playbook_id="PB01",
        success=True,
        execution_time_seconds=5.0,
    )
    metrics_collector.record_tool_invocation(
        tenant_id="TENANT_A",
        tool_name="retry_settlement",
        success=True,
        latency_seconds=0.5,
        retry_count=0,
    )
    
    # Setup exception store
    exception_store.store_exception(
        sample_exception,
        {"status": "RESOLVED", "stages": {}}
    )
    
    # Inject dependencies
    dashboards.set_metrics_collector(metrics_collector)
    
    yield TestClient(app)
    
    # Cleanup
    metrics_collector.clear_all_metrics()
    exception_store.clear_all()


@pytest.fixture
def setup_api_key():
    """Setup API key for testing."""
    from src.api.auth import get_api_key_auth
    auth = get_api_key_auth()
    yield auth


class TestSummaryDashboard:
    """Tests for Summary Dashboard endpoint."""

    def test_get_summary_dashboard_success(self, client, setup_api_key):
        """Test successful retrieval of summary dashboard."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/dashboards/{tenant_id}/summary",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["tenantId"] == tenant_id
        assert "timestamp" in data
        assert "overview" in data
        assert "actionability" in data
        assert "approvalQueue" in data
        assert "topExceptionTypes" in data
        assert "confidenceSummary" in data
        
        # Verify overview data
        overview = data["overview"]
        assert "totalExceptions" in overview
        assert "autoResolutionRate" in overview
        assert "statusBreakdown" in overview
        
        # Verify confidence summary
        conf_summary = data["confidenceSummary"]
        assert "avgConfidence" in conf_summary
        assert "distribution" in conf_summary

    def test_get_summary_dashboard_empty_tenant(self, client, setup_api_key):
        """Test summary dashboard for tenant with no data."""
        tenant_id = "EMPTY_TENANT"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/dashboards/{tenant_id}/summary",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["tenantId"] == tenant_id
        assert data["overview"]["totalExceptions"] == 0


class TestExceptionsDashboard:
    """Tests for Exceptions Dashboard endpoint."""

    def test_get_exceptions_dashboard_success(self, client, setup_api_key):
        """Test successful retrieval of exceptions dashboard."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/dashboards/{tenant_id}/exceptions",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["tenantId"] == tenant_id
        assert "timestamp" in data
        assert "totalExceptions" in data
        assert "exceptions" in data
        assert "exceptionTypeBreakdown" in data
        assert "statusDistribution" in data
        
        # Verify exception list
        assert isinstance(data["exceptions"], list)
        if len(data["exceptions"]) > 0:
            exception = data["exceptions"][0]
            assert "exceptionId" in exception
            assert "exceptionType" in exception
            assert "status" in exception

    def test_get_exceptions_dashboard_with_status_filter(self, client, setup_api_key):
        """Test exceptions dashboard with status filter."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/dashboards/{tenant_id}/exceptions",
            params={"status": "RESOLVED"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned exceptions should have RESOLVED status
        for exception in data["exceptions"]:
            assert exception["status"] == "RESOLVED"

    def test_get_exceptions_dashboard_with_limit(self, client, setup_api_key):
        """Test exceptions dashboard with limit parameter."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/dashboards/{tenant_id}/exceptions",
            params={"limit": 10},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["exceptions"]) <= 10

    def test_get_exceptions_dashboard_empty_tenant(self, client, setup_api_key):
        """Test exceptions dashboard for tenant with no exceptions."""
        tenant_id = "EMPTY_TENANT"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/dashboards/{tenant_id}/exceptions",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["tenantId"] == tenant_id
        assert data["totalExceptions"] == 0
        assert len(data["exceptions"]) == 0


class TestPlaybooksDashboard:
    """Tests for Playbooks Dashboard endpoint."""

    def test_get_playbooks_dashboard_success(self, client, setup_api_key):
        """Test successful retrieval of playbooks dashboard."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/dashboards/{tenant_id}/playbooks",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["tenantId"] == tenant_id
        assert "timestamp" in data
        assert "summary" in data
        assert "playbooks" in data
        assert "topPerformers" in data
        
        # Verify summary
        summary = data["summary"]
        assert "totalPlaybooks" in summary
        assert "totalExecutions" in summary
        assert "overallSuccessRate" in summary
        
        # Verify playbooks list
        assert isinstance(data["playbooks"], list)
        if len(data["playbooks"]) > 0:
            playbook = data["playbooks"][0]
            assert "playbookId" in playbook
            assert "executionCount" in playbook
            assert "successRate" in playbook

    def test_get_playbooks_dashboard_empty_tenant(self, client, setup_api_key):
        """Test playbooks dashboard for tenant with no playbook metrics."""
        tenant_id = "EMPTY_TENANT"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/dashboards/{tenant_id}/playbooks",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["tenantId"] == tenant_id
        assert data["summary"]["totalPlaybooks"] == 0
        assert len(data["playbooks"]) == 0


class TestToolsDashboard:
    """Tests for Tools Dashboard endpoint."""

    def test_get_tools_dashboard_success(self, client, setup_api_key):
        """Test successful retrieval of tools dashboard."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/dashboards/{tenant_id}/tools",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["tenantId"] == tenant_id
        assert "timestamp" in data
        assert "summary" in data
        assert "tools" in data
        assert "topUsed" in data
        assert "mostReliable" in data
        assert "highestLatency" in data
        
        # Verify summary
        summary = data["summary"]
        assert "totalTools" in summary
        assert "totalInvocations" in summary
        assert "overallSuccessRate" in summary
        
        # Verify tools list
        assert isinstance(data["tools"], list)
        if len(data["tools"]) > 0:
            tool = data["tools"][0]
            assert "toolName" in tool
            assert "invocationCount" in tool
            assert "successRate" in tool
            assert "avgLatencySeconds" in tool

    def test_get_tools_dashboard_empty_tenant(self, client, setup_api_key):
        """Test tools dashboard for tenant with no tool metrics."""
        tenant_id = "EMPTY_TENANT"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/dashboards/{tenant_id}/tools",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["tenantId"] == tenant_id
        assert data["summary"]["totalTools"] == 0
        assert len(data["tools"]) == 0

