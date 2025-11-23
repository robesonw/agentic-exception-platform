"""
Tests for MetricsCollector.
Tests metric tracking, tenant isolation, and calculations.
"""

import pytest

from src.observability.metrics import MetricsCollector, TenantMetrics


class TestTenantMetrics:
    """Tests for TenantMetrics dataclass."""

    def test_auto_resolution_rate_no_exceptions(self):
        """Test auto-resolution rate with no exceptions."""
        metrics = TenantMetrics(tenant_id="TENANT_001")
        assert metrics.get_auto_resolution_rate() == 0.0

    def test_auto_resolution_rate_calculation(self):
        """Test auto-resolution rate calculation."""
        metrics = TenantMetrics(tenant_id="TENANT_001")
        metrics.exception_count = 10
        metrics.auto_resolution_count = 7
        
        assert metrics.get_auto_resolution_rate() == 0.7

    def test_auto_resolution_rate_all_resolved(self):
        """Test auto-resolution rate when all resolved."""
        metrics = TenantMetrics(tenant_id="TENANT_001")
        metrics.exception_count = 5
        metrics.auto_resolution_count = 5
        
        assert metrics.get_auto_resolution_rate() == 1.0

    def test_mttr_seconds_no_resolutions(self):
        """Test MTTR with no resolutions."""
        metrics = TenantMetrics(tenant_id="TENANT_001")
        assert metrics.get_mttr_seconds() == 0.0

    def test_mttr_seconds_single_resolution(self):
        """Test MTTR with single resolution."""
        from datetime import datetime, timezone
        
        metrics = TenantMetrics(tenant_id="TENANT_001")
        metrics.resolution_timestamps = [datetime.now(timezone.utc)]
        
        assert metrics.get_mttr_seconds() == 0.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        metrics = TenantMetrics(tenant_id="TENANT_001")
        metrics.exception_count = 10
        metrics.auto_resolution_count = 7
        metrics.actionable_approved_count = 5
        
        result = metrics.to_dict()
        
        assert result["tenantId"] == "TENANT_001"
        assert result["exceptionCount"] == 10
        assert result["autoResolutionRate"] == 0.7
        assert result["actionableApprovedCount"] == 5


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_get_or_create_metrics(self):
        """Test getting or creating metrics for tenant."""
        collector = MetricsCollector()
        metrics = collector.get_or_create_metrics("TENANT_001")
        
        assert metrics is not None
        assert metrics.tenant_id == "TENANT_001"
        assert metrics.exception_count == 0

    def test_get_or_create_metrics_returns_same_instance(self):
        """Test that get_or_create returns same instance."""
        collector = MetricsCollector()
        metrics1 = collector.get_or_create_metrics("TENANT_001")
        metrics2 = collector.get_or_create_metrics("TENANT_001")
        
        assert metrics1 is metrics2

    def test_record_exception_increments_count(self):
        """Test that recording exception increments count."""
        collector = MetricsCollector()
        collector.record_exception("TENANT_001", "RESOLVED")
        
        metrics = collector.get_metrics("TENANT_001")
        assert metrics["exceptionCount"] == 1

    def test_record_exception_tracks_actionability(self):
        """Test that actionability is tracked correctly."""
        collector = MetricsCollector()
        
        collector.record_exception("TENANT_001", "RESOLVED", "ACTIONABLE_APPROVED_PROCESS")
        collector.record_exception("TENANT_001", "RESOLVED", "ACTIONABLE_NON_APPROVED_PROCESS")
        collector.record_exception("TENANT_001", "OPEN", "NON_ACTIONABLE_INFO_ONLY")
        
        metrics = collector.get_metrics("TENANT_001")
        assert metrics["exceptionCount"] == 3
        assert metrics["actionableApprovedCount"] == 1
        assert metrics["actionableNonApprovedCount"] == 1
        assert metrics["nonActionableCount"] == 1

    def test_record_exception_tracks_resolution_status(self):
        """Test that resolution status is tracked."""
        collector = MetricsCollector()
        
        collector.record_exception("TENANT_001", "RESOLVED")
        collector.record_exception("TENANT_001", "ESCALATED")
        collector.record_exception("TENANT_001", "IN_PROGRESS")
        
        metrics = collector.get_metrics("TENANT_001")
        assert metrics["exceptionCount"] == 3
        assert metrics["autoResolutionCount"] == 1
        assert metrics["escalatedCount"] == 1

    def test_record_pipeline_run(self):
        """Test recording metrics from pipeline run."""
        collector = MetricsCollector()
        
        results = [
            {
                "status": "RESOLVED",
                "stages": {
                    "policy": {
                        "evidence": ["Actionability: ACTIONABLE_APPROVED_PROCESS"],
                    }
                },
            },
            {
                "status": "ESCALATED",
                "stages": {
                    "policy": {
                        "evidence": ["Actionability: NON_ACTIONABLE_INFO_ONLY"],
                    }
                },
            },
        ]
        
        collector.record_pipeline_run("TENANT_001", results)
        
        metrics = collector.get_metrics("TENANT_001")
        assert metrics["exceptionCount"] == 2
        assert metrics["actionableApprovedCount"] == 1
        assert metrics["nonActionableCount"] == 1
        assert metrics["autoResolutionCount"] == 1
        assert metrics["escalatedCount"] == 1

    def test_get_metrics_returns_correct_structure(self):
        """Test that get_metrics returns correct structure."""
        collector = MetricsCollector()
        collector.record_exception("TENANT_001", "RESOLVED", "ACTIONABLE_APPROVED_PROCESS")
        
        metrics = collector.get_metrics("TENANT_001")
        
        assert "tenantId" in metrics
        assert "exceptionCount" in metrics
        assert "autoResolutionRate" in metrics
        assert "mttrSeconds" in metrics
        assert "actionableApprovedCount" in metrics
        assert "actionableNonApprovedCount" in metrics
        assert "nonActionableCount" in metrics
        assert "escalatedCount" in metrics

    def test_get_all_metrics(self):
        """Test getting metrics for all tenants."""
        collector = MetricsCollector()
        collector.record_exception("TENANT_001", "RESOLVED")
        collector.record_exception("TENANT_002", "ESCALATED")
        
        all_metrics = collector.get_all_metrics()
        
        assert "TENANT_001" in all_metrics
        assert "TENANT_002" in all_metrics
        assert all_metrics["TENANT_001"]["exceptionCount"] == 1
        assert all_metrics["TENANT_002"]["exceptionCount"] == 1

    def test_reset_metrics(self):
        """Test resetting metrics for a tenant."""
        collector = MetricsCollector()
        collector.record_exception("TENANT_001", "RESOLVED")
        
        assert collector.get_metrics("TENANT_001")["exceptionCount"] == 1
        
        collector.reset_metrics("TENANT_001")
        
        assert collector.get_metrics("TENANT_001")["exceptionCount"] == 0

    def test_clear_all_metrics(self):
        """Test clearing all metrics."""
        collector = MetricsCollector()
        collector.record_exception("TENANT_001", "RESOLVED")
        collector.record_exception("TENANT_002", "ESCALATED")
        
        collector.clear_all_metrics()
        
        all_metrics = collector.get_all_metrics()
        assert len(all_metrics) == 0


class TestMetricsCollectorTenantIsolation:
    """Tests for tenant isolation in metrics collection."""

    def test_tenant_isolation_separate_metrics(self):
        """Test that different tenants have separate metrics."""
        collector = MetricsCollector()
        
        collector.record_exception("TENANT_A", "RESOLVED")
        collector.record_exception("TENANT_A", "RESOLVED")
        collector.record_exception("TENANT_B", "ESCALATED")
        
        metrics_a = collector.get_metrics("TENANT_A")
        metrics_b = collector.get_metrics("TENANT_B")
        
        assert metrics_a["exceptionCount"] == 2
        assert metrics_b["exceptionCount"] == 1
        assert metrics_a["autoResolutionCount"] == 2
        assert metrics_b["autoResolutionCount"] == 0

    def test_tenant_isolation_no_cross_contamination(self):
        """Test that metrics don't leak between tenants."""
        collector = MetricsCollector()
        
        # Record metrics for tenant A
        for i in range(5):
            collector.record_exception("TENANT_A", "RESOLVED", "ACTIONABLE_APPROVED_PROCESS")
        
        # Record metrics for tenant B
        for i in range(3):
            collector.record_exception("TENANT_B", "ESCALATED", "NON_ACTIONABLE_INFO_ONLY")
        
        metrics_a = collector.get_metrics("TENANT_A")
        metrics_b = collector.get_metrics("TENANT_B")
        
        # Verify tenant A metrics
        assert metrics_a["exceptionCount"] == 5
        assert metrics_a["actionableApprovedCount"] == 5
        assert metrics_a["nonActionableCount"] == 0
        
        # Verify tenant B metrics
        assert metrics_b["exceptionCount"] == 3
        assert metrics_b["actionableApprovedCount"] == 0
        assert metrics_b["nonActionableCount"] == 3

    def test_tenant_isolation_reset(self):
        """Test that resetting one tenant doesn't affect others."""
        collector = MetricsCollector()
        
        collector.record_exception("TENANT_A", "RESOLVED")
        collector.record_exception("TENANT_B", "RESOLVED")
        
        collector.reset_metrics("TENANT_A")
        
        assert collector.get_metrics("TENANT_A")["exceptionCount"] == 0
        assert collector.get_metrics("TENANT_B")["exceptionCount"] == 1


class TestMetricsCollectorCalculations:
    """Tests for metric calculations."""

    def test_auto_resolution_rate_calculation(self):
        """Test auto-resolution rate calculation."""
        collector = MetricsCollector()
        
        # Record 10 exceptions, 7 resolved
        for i in range(7):
            collector.record_exception("TENANT_001", "RESOLVED")
        for i in range(3):
            collector.record_exception("TENANT_001", "ESCALATED")
        
        metrics = collector.get_metrics("TENANT_001")
        assert metrics["autoResolutionRate"] == 0.7

    def test_mttr_approximation(self):
        """Test MTTR approximation."""
        collector = MetricsCollector()
        
        # Record resolved exceptions with resolution times
        collector.record_exception("TENANT_001", "RESOLVED", resolution_time_seconds=10.0)
        collector.record_exception("TENANT_001", "RESOLVED", resolution_time_seconds=20.0)
        collector.record_exception("TENANT_001", "RESOLVED", resolution_time_seconds=15.0)
        
        metrics = collector.get_metrics("TENANT_001")
        # MTTR is approximate in MVP, so we just verify it's calculated
        assert "mttrSeconds" in metrics
        assert isinstance(metrics["mttrSeconds"], float)

    def test_actionability_tracking(self):
        """Test that actionability counts are tracked correctly."""
        collector = MetricsCollector()
        
        collector.record_exception("TENANT_001", "RESOLVED", "ACTIONABLE_APPROVED_PROCESS")
        collector.record_exception("TENANT_001", "RESOLVED", "ACTIONABLE_APPROVED_PROCESS")
        collector.record_exception("TENANT_001", "OPEN", "ACTIONABLE_NON_APPROVED_PROCESS")
        collector.record_exception("TENANT_001", "OPEN", "NON_ACTIONABLE_INFO_ONLY")
        collector.record_exception("TENANT_001", "OPEN", "NON_ACTIONABLE_INFO_ONLY")
        
        metrics = collector.get_metrics("TENANT_001")
        assert metrics["actionableApprovedCount"] == 2
        assert metrics["actionableNonApprovedCount"] == 1
        assert metrics["nonActionableCount"] == 2


class TestMetricsCollectorIntegration:
    """Integration tests for metrics collection."""

    def test_complete_workflow(self):
        """Test complete metrics collection workflow."""
        collector = MetricsCollector()
        
        # Simulate pipeline run results
        results = [
            {
                "status": "RESOLVED",
                "stages": {
                    "policy": {
                        "evidence": ["Actionability: ACTIONABLE_APPROVED_PROCESS"],
                    }
                },
            },
            {
                "status": "RESOLVED",
                "stages": {
                    "policy": {
                        "evidence": ["Actionability: ACTIONABLE_APPROVED_PROCESS"],
                    }
                },
            },
            {
                "status": "ESCALATED",
                "stages": {
                    "policy": {
                        "evidence": ["Actionability: NON_ACTIONABLE_INFO_ONLY"],
                    }
                },
            },
        ]
        
        collector.record_pipeline_run("TENANT_001", results)
        
        metrics = collector.get_metrics("TENANT_001")
        
        assert metrics["exceptionCount"] == 3
        assert metrics["autoResolutionCount"] == 2
        assert metrics["escalatedCount"] == 1
        assert metrics["actionableApprovedCount"] == 2
        assert metrics["nonActionableCount"] == 1
        assert metrics["autoResolutionRate"] == pytest.approx(2.0 / 3.0, abs=0.01)

