"""
Tests for Metrics API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes.metrics import get_metrics_collector

client = TestClient(app)

# Default API key for tests
DEFAULT_API_KEY = "test_api_key_tenant_001"


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset metrics before each test."""
    collector = get_metrics_collector()
    collector.clear_all_metrics()
    yield
    collector.clear_all_metrics()


class TestMetricsAPI:
    """Tests for GET /metrics/{tenantId} endpoint."""

    def test_get_tenant_metrics_empty(self):
        """Test getting metrics for tenant with no data."""
        response = client.get("/metrics/TENANT_001", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        assert data["tenantId"] == "TENANT_001"
        assert data["exceptionCount"] == 0
        assert data["autoResolutionRate"] == 0.0

    def test_get_tenant_metrics_with_data(self):
        """Test getting metrics for tenant with data."""
        collector = get_metrics_collector()
        collector.record_exception("TENANT_001", "RESOLVED", "ACTIONABLE_APPROVED_PROCESS")
        collector.record_exception("TENANT_001", "RESOLVED", "ACTIONABLE_APPROVED_PROCESS")
        
        response = client.get("/metrics/TENANT_001", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        assert data["exceptionCount"] == 2
        assert data["autoResolutionRate"] == 1.0
        assert data["actionableApprovedCount"] == 2

    def test_get_tenant_metrics_structure(self):
        """Test that response has correct structure."""
        collector = get_metrics_collector()
        collector.record_exception("TENANT_001", "RESOLVED")
        
        response = client.get("/metrics/TENANT_001", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        
        assert "tenantId" in data
        assert "exceptionCount" in data
        assert "autoResolutionRate" in data
        assert "mttrSeconds" in data
        assert "actionableApprovedCount" in data
        assert "actionableNonApprovedCount" in data
        assert "nonActionableCount" in data
        assert "escalatedCount" in data

    def test_get_all_metrics(self):
        """Test getting metrics for all tenants."""
        collector = get_metrics_collector()
        collector.record_exception("TENANT_001", "RESOLVED")
        collector.record_exception("TENANT_002", "ESCALATED")
        
        response = client.get("/metrics", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        
        assert "TENANT_001" in data
        assert "TENANT_002" in data
        assert data["TENANT_001"]["exceptionCount"] == 1
        assert data["TENANT_002"]["exceptionCount"] == 1

    def test_get_all_metrics_empty(self):
        """Test getting all metrics when no data exists."""
        response = client.get("/metrics", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) == 0


class TestMetricsAPICalculations:
    """Tests for metric calculations in API responses."""

    def test_auto_resolution_rate_in_response(self):
        """Test that auto-resolution rate is calculated correctly."""
        collector = get_metrics_collector()
        
        # Record 10 exceptions, 7 resolved
        for i in range(7):
            collector.record_exception("TENANT_001", "RESOLVED")
        for i in range(3):
            collector.record_exception("TENANT_001", "ESCALATED")
        
        response = client.get("/metrics/TENANT_001", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        assert data["autoResolutionRate"] == pytest.approx(0.7, abs=0.01)

    def test_actionability_counts_in_response(self):
        """Test that actionability counts are in response."""
        collector = get_metrics_collector()
        
        collector.record_exception("TENANT_001", "RESOLVED", "ACTIONABLE_APPROVED_PROCESS")
        collector.record_exception("TENANT_001", "OPEN", "ACTIONABLE_NON_APPROVED_PROCESS")
        collector.record_exception("TENANT_001", "OPEN", "NON_ACTIONABLE_INFO_ONLY")
        
        response = client.get("/metrics/TENANT_001", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        assert data["actionableApprovedCount"] == 1
        assert data["actionableNonApprovedCount"] == 1
        assert data["nonActionableCount"] == 1


class TestMetricsAPITenantIsolation:
    """Tests for tenant isolation in metrics API."""

    def test_tenant_isolation_separate_metrics(self):
        """Test that different tenants have separate metrics."""
        collector = get_metrics_collector()
        
        collector.record_exception("TENANT_A", "RESOLVED")
        collector.record_exception("TENANT_A", "RESOLVED")
        collector.record_exception("TENANT_B", "ESCALATED")
        
        response_a = client.get("/metrics/TENANT_A", headers={"X-API-KEY": DEFAULT_API_KEY})
        response_b = client.get("/metrics/TENANT_B", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response_a.status_code == 200
        assert response_b.status_code == 200
        
        data_a = response_a.json()
        data_b = response_b.json()
        
        assert data_a["exceptionCount"] == 2
        assert data_b["exceptionCount"] == 1
        assert data_a["autoResolutionCount"] == 2
        assert data_b["autoResolutionCount"] == 0

    def test_tenant_isolation_no_cross_contamination(self):
        """Test that metrics don't leak between tenants."""
        collector = get_metrics_collector()
        
        # Record metrics for tenant A
        for i in range(5):
            collector.record_exception("TENANT_A", "RESOLVED", "ACTIONABLE_APPROVED_PROCESS")
        
        # Record metrics for tenant B
        for i in range(3):
            collector.record_exception("TENANT_B", "ESCALATED", "NON_ACTIONABLE_INFO_ONLY")
        
        response_a = client.get("/metrics/TENANT_A", headers={"X-API-KEY": DEFAULT_API_KEY})
        response_b = client.get("/metrics/TENANT_B", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        data_a = response_a.json()
        data_b = response_b.json()
        
        # Verify tenant A metrics
        assert data_a["exceptionCount"] == 5
        assert data_a["actionableApprovedCount"] == 5
        assert data_a["nonActionableCount"] == 0
        
        # Verify tenant B metrics
        assert data_b["exceptionCount"] == 3
        assert data_b["actionableApprovedCount"] == 0
        assert data_b["nonActionableCount"] == 3


class TestMetricsAPIIntegration:
    """Integration tests for metrics API."""

    @pytest.mark.asyncio
    async def test_metrics_updated_after_pipeline_run(self):
        """Test that metrics are updated after pipeline run."""
        from src.domainpack.loader import load_domain_pack
        from src.tenantpack.loader import load_tenant_policy
        from src.orchestrator.runner import run_pipeline
        from src.observability.metrics import MetricsCollector
        
        # Load packs
        domain_pack = load_domain_pack("domainpacks/finance.sample.json")
        tenant_policy = load_tenant_policy("tenantpacks/tenant_finance.sample.json")
        
        # Create metrics collector
        metrics_collector = MetricsCollector()
        
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
            metrics_collector=metrics_collector,
        )
        
        # Check metrics via API
        # Note: We need to set the global collector for the API to see it
        from src.api.routes.metrics import _metrics_collector
        _metrics_collector._metrics = metrics_collector._metrics
        
        response = client.get("/metrics/TENANT_FINANCE_001", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        assert data["exceptionCount"] >= 1

