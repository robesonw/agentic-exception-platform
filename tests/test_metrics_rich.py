"""
Comprehensive tests for Rich Metrics Collection.

Tests Phase 2 enhancements:
- Per-playbook success rates
- Per-tool latency, retry counts, failure rates
- Approval queue aging
- Recurrence stats by exceptionType
- Confidence distribution
- Metrics persistence
"""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.observability.metrics import (
    ApprovalQueueMetrics,
    ConfidenceDistribution,
    ExceptionTypeRecurrence,
    MetricsCollector,
    PlaybookMetrics,
    TenantMetrics,
    ToolMetrics,
)


class TestPlaybookMetrics:
    """Tests for PlaybookMetrics."""

    def test_playbook_metrics_success_rate(self):
        """Test playbook success rate calculation."""
        metrics = PlaybookMetrics(playbook_id="PB01")
        
        # No executions
        assert metrics.get_success_rate() == 0.0
        
        # Add executions
        metrics.execution_count = 10
        metrics.success_count = 7
        metrics.failure_count = 3
        
        assert metrics.get_success_rate() == 0.7
        assert metrics.execution_count == 10

    def test_playbook_metrics_avg_execution_time(self):
        """Test playbook average execution time calculation."""
        metrics = PlaybookMetrics(playbook_id="PB01")
        
        # No executions
        assert metrics.get_avg_execution_time() == 0.0
        
        # Add executions
        metrics.execution_count = 5
        metrics.total_execution_time_seconds = 25.0
        
        assert metrics.get_avg_execution_time() == 5.0


class TestToolMetrics:
    """Tests for ToolMetrics."""

    def test_tool_metrics_success_rate(self):
        """Test tool success rate calculation."""
        metrics = ToolMetrics(tool_name="retry_settlement")
        
        # No invocations
        assert metrics.get_success_rate() == 0.0
        assert metrics.get_failure_rate() == 0.0
        
        # Add invocations
        metrics.invocation_count = 20
        metrics.success_count = 18
        metrics.failure_count = 2
        
        assert metrics.get_success_rate() == 0.9
        assert metrics.get_failure_rate() == 0.1

    def test_tool_metrics_latency_percentiles(self):
        """Test tool latency percentile calculations."""
        metrics = ToolMetrics(tool_name="get_order")
        
        # No samples
        assert metrics.get_p50_latency() == 0.0
        assert metrics.get_p95_latency() == 0.0
        assert metrics.get_p99_latency() == 0.0
        
        # Add samples
        metrics.latency_samples = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        metrics.invocation_count = 10
        metrics.total_latency_seconds = sum(metrics.latency_samples)
        
        assert metrics.get_avg_latency() == 0.55
        # For 10 samples, median (p50) is average of 5th and 6th elements
        # Sorted: [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        # Index 5 (6th element) = 0.6
        assert metrics.get_p50_latency() == 0.6
        assert metrics.get_p95_latency() == 1.0  # 95th percentile (index 9)
        assert metrics.get_p99_latency() == 1.0  # 99th percentile (index 9)

    def test_tool_metrics_avg_retries(self):
        """Test tool average retry calculation."""
        metrics = ToolMetrics(tool_name="retry_settlement")
        
        # No invocations
        assert metrics.get_avg_retries() == 0.0
        
        # Add invocations with retries
        metrics.invocation_count = 10
        metrics.total_retry_count = 15
        
        assert metrics.get_avg_retries() == 1.5


class TestApprovalQueueMetrics:
    """Tests for ApprovalQueueMetrics."""

    def test_approval_queue_avg_age(self):
        """Test approval queue average age calculation."""
        metrics = ApprovalQueueMetrics()
        
        # No pending
        assert metrics.get_avg_pending_age() == 0.0
        
        # Add pending ages
        metrics.pending_count = 3
        metrics.total_pending_age_seconds = 300.0  # 5 minutes total
        
        assert metrics.get_avg_pending_age() == 100.0  # 100 seconds average


class TestExceptionTypeRecurrence:
    """Tests for ExceptionTypeRecurrence."""

    def test_exception_type_recurrence(self):
        """Test exception type recurrence tracking."""
        recurrence = ExceptionTypeRecurrence(exception_type="SETTLEMENT_FAIL")
        
        # No occurrences
        assert recurrence.get_unique_count() == 0
        assert recurrence.get_recurrence_rate() == 0.0
        
        # Add occurrences
        recurrence.occurrence_count = 10
        recurrence.unique_exception_ids = {"EX001", "EX002", "EX003"}
        
        assert recurrence.get_unique_count() == 3
        assert recurrence.get_recurrence_rate() == pytest.approx(10.0 / 3.0, rel=1e-6)


class TestConfidenceDistribution:
    """Tests for ConfidenceDistribution."""

    def test_confidence_distribution(self):
        """Test confidence distribution tracking."""
        dist = ConfidenceDistribution()
        
        # No samples
        assert dist.get_avg_confidence() == 0.0
        assert dist.get_median_confidence() == 0.0
        
        # Add samples
        dist.add_sample(0.5)
        dist.add_sample(0.7)
        dist.add_sample(0.9)
        
        assert dist.get_avg_confidence() == pytest.approx(0.7, rel=1e-6)
        assert dist.get_median_confidence() == 0.7
        # 0.5 goes to "0.5-0.7", 0.7 goes to "0.7-0.9", 0.9 goes to "0.9-1.0"
        assert dist.count_by_range["0.5-0.7"] == 1  # 0.5
        assert dist.count_by_range["0.7-0.9"] == 1  # 0.7
        assert dist.count_by_range["0.9-1.0"] == 1  # 0.9


class TestTenantMetrics:
    """Tests for TenantMetrics."""

    def test_tenant_metrics_playbook_tracking(self):
        """Test playbook metrics tracking."""
        metrics = TenantMetrics(tenant_id="TENANT_A")
        
        # Get or create playbook metrics
        pb_metrics = metrics.get_or_create_playbook_metrics("PB01")
        assert pb_metrics.playbook_id == "PB01"
        
        # Same instance returned
        pb_metrics2 = metrics.get_or_create_playbook_metrics("PB01")
        assert pb_metrics is pb_metrics2

    def test_tenant_metrics_tool_tracking(self):
        """Test tool metrics tracking."""
        metrics = TenantMetrics(tenant_id="TENANT_A")
        
        # Get or create tool metrics
        tool_metrics = metrics.get_or_create_tool_metrics("retry_settlement")
        assert tool_metrics.tool_name == "retry_settlement"
        
        # Same instance returned
        tool_metrics2 = metrics.get_or_create_tool_metrics("retry_settlement")
        assert tool_metrics is tool_metrics2

    def test_tenant_metrics_exception_type_recurrence(self):
        """Test exception type recurrence tracking."""
        metrics = TenantMetrics(tenant_id="TENANT_A")
        
        # Get or create recurrence
        recurrence = metrics.get_or_create_exception_type_recurrence("SETTLEMENT_FAIL")
        assert recurrence.exception_type == "SETTLEMENT_FAIL"
        
        # Same instance returned
        recurrence2 = metrics.get_or_create_exception_type_recurrence("SETTLEMENT_FAIL")
        assert recurrence is recurrence2


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    @pytest.fixture
    def temp_storage_dir(self):
        """Temporary storage directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def collector(self, temp_storage_dir):
        """Metrics collector for testing."""
        return MetricsCollector(storage_root=temp_storage_dir)

    def test_record_playbook_execution(self, collector):
        """Test recording playbook execution."""
        tenant_id = "TENANT_A"
        playbook_id = "PB01"
        
        # Record successful execution
        collector.record_playbook_execution(
            tenant_id=tenant_id,
            playbook_id=playbook_id,
            success=True,
            execution_time_seconds=5.0,
        )
        
        metrics = collector.get_or_create_metrics(tenant_id)
        pb_metrics = metrics.playbook_metrics[playbook_id]
        
        assert pb_metrics.execution_count == 1
        assert pb_metrics.success_count == 1
        assert pb_metrics.failure_count == 0
        assert pb_metrics.total_execution_time_seconds == 5.0
        assert pb_metrics.get_success_rate() == 1.0
        
        # Record failed execution
        collector.record_playbook_execution(
            tenant_id=tenant_id,
            playbook_id=playbook_id,
            success=False,
            execution_time_seconds=2.0,
        )
        
        assert pb_metrics.execution_count == 2
        assert pb_metrics.success_count == 1
        assert pb_metrics.failure_count == 1
        assert pb_metrics.get_success_rate() == 0.5

    def test_record_tool_invocation(self, collector):
        """Test recording tool invocation."""
        tenant_id = "TENANT_A"
        tool_name = "retry_settlement"
        
        # Record successful invocation
        collector.record_tool_invocation(
            tenant_id=tenant_id,
            tool_name=tool_name,
            success=True,
            latency_seconds=0.5,
            retry_count=0,
        )
        
        metrics = collector.get_or_create_metrics(tenant_id)
        tool_metrics = metrics.tool_metrics[tool_name]
        
        assert tool_metrics.invocation_count == 1
        assert tool_metrics.success_count == 1
        assert tool_metrics.failure_count == 0
        assert tool_metrics.total_retry_count == 0
        assert tool_metrics.total_latency_seconds == 0.5
        assert len(tool_metrics.latency_samples) == 1
        assert tool_metrics.get_success_rate() == 1.0
        
        # Record failed invocation with retries
        collector.record_tool_invocation(
            tenant_id=tenant_id,
            tool_name=tool_name,
            success=False,
            latency_seconds=1.0,
            retry_count=3,
        )
        
        assert tool_metrics.invocation_count == 2
        assert tool_metrics.success_count == 1
        assert tool_metrics.failure_count == 1
        assert tool_metrics.total_retry_count == 3
        assert tool_metrics.get_avg_retries() == 1.5
        assert tool_metrics.get_failure_rate() == 0.5

    def test_update_approval_queue_metrics(self, collector):
        """Test updating approval queue metrics."""
        tenant_id = "TENANT_A"
        
        # Create pending approvals
        now = datetime.now(timezone.utc)
        pending_approvals = [
            {"submitted_at": (now - timedelta(minutes=30)).isoformat()},
            {"submitted_at": (now - timedelta(minutes=60)).isoformat()},
            {"submitted_at": (now - timedelta(minutes=90)).isoformat()},
        ]
        
        collector.update_approval_queue_metrics(
            tenant_id=tenant_id,
            pending_approvals=pending_approvals,
            approval_count=5,
            rejection_count=2,
            timeout_count=1,
        )
        
        metrics = collector.get_or_create_metrics(tenant_id)
        queue_metrics = metrics.approval_queue_metrics
        
        assert queue_metrics.pending_count == 3
        assert queue_metrics.approval_count == 5
        assert queue_metrics.rejection_count == 2
        assert queue_metrics.timeout_count == 1
        assert queue_metrics.oldest_pending_age_seconds > 0
        assert queue_metrics.get_avg_pending_age() > 0

    def test_record_exception_with_recurrence(self, collector):
        """Test recording exception with recurrence tracking."""
        tenant_id = "TENANT_A"
        exception_type = "SETTLEMENT_FAIL"
        exception_id = "EX001"
        
        # Record first occurrence
        collector.record_exception(
            tenant_id=tenant_id,
            status="RESOLVED",
            exception_type=exception_type,
            exception_id=exception_id,
            confidence=0.8,
        )
        
        metrics = collector.get_or_create_metrics(tenant_id)
        recurrence = metrics.exception_type_recurrence[exception_type]
        
        assert recurrence.occurrence_count == 1
        assert recurrence.get_unique_count() == 1
        assert recurrence.first_seen is not None
        assert recurrence.last_seen is not None
        
        # Record same exception again (recurrence)
        collector.record_exception(
            tenant_id=tenant_id,
            status="RESOLVED",
            exception_type=exception_type,
            exception_id=exception_id,
            confidence=0.9,
        )
        
        assert recurrence.occurrence_count == 2
        assert recurrence.get_unique_count() == 1  # Same exception ID
        assert recurrence.get_recurrence_rate() == 2.0

    def test_record_exception_with_confidence(self, collector):
        """Test recording exception with confidence distribution."""
        tenant_id = "TENANT_A"
        
        # Record exceptions with different confidence scores
        collector.record_exception(
            tenant_id=tenant_id,
            status="RESOLVED",
            confidence=0.5,
        )
        collector.record_exception(
            tenant_id=tenant_id,
            status="RESOLVED",
            confidence=0.7,
        )
        collector.record_exception(
            tenant_id=tenant_id,
            status="RESOLVED",
            confidence=0.9,
        )
        
        metrics = collector.get_or_create_metrics(tenant_id)
        conf_dist = metrics.confidence_distribution
        
        assert len(conf_dist.samples) == 3
        assert conf_dist.get_avg_confidence() == pytest.approx(0.7, rel=1e-6)
        # 0.5 goes to "0.5-0.7", 0.7 goes to "0.7-0.9", 0.9 goes to "0.9-1.0"
        assert conf_dist.count_by_range["0.5-0.7"] == 1  # 0.5
        assert conf_dist.count_by_range["0.7-0.9"] == 1  # 0.7
        assert conf_dist.count_by_range["0.9-1.0"] == 1  # 0.9

    def test_persist_and_load_metrics(self, collector, temp_storage_dir):
        """Test metrics persistence and loading."""
        tenant_id = "TENANT_A"
        
        # Record some metrics
        collector.record_playbook_execution(
            tenant_id=tenant_id,
            playbook_id="PB01",
            success=True,
            execution_time_seconds=5.0,
        )
        collector.record_tool_invocation(
            tenant_id=tenant_id,
            tool_name="retry_settlement",
            success=True,
            latency_seconds=0.5,
            retry_count=0,
        )
        collector.record_exception(
            tenant_id=tenant_id,
            status="RESOLVED",
            exception_type="SETTLEMENT_FAIL",
            exception_id="EX001",
            confidence=0.8,
        )
        
        # Persist metrics
        collector.persist_metrics(tenant_id)
        
        # Verify file exists
        metrics_file = Path(temp_storage_dir) / f"{tenant_id}.json"
        assert metrics_file.exists()
        
        # Load metrics
        collector2 = MetricsCollector(storage_root=temp_storage_dir)
        loaded = collector2.load_metrics(tenant_id)
        assert loaded is True
        
        # Verify metrics were loaded
        metrics = collector2.get_metrics(tenant_id)
        assert metrics["playbookMetrics"]["PB01"]["executionCount"] == 1
        assert metrics["toolMetrics"]["retry_settlement"]["invocationCount"] == 1
        assert metrics["exceptionTypeRecurrence"]["SETTLEMENT_FAIL"]["occurrenceCount"] == 1

    def test_persist_all_metrics(self, collector, temp_storage_dir):
        """Test persisting all metrics."""
        # Record metrics for multiple tenants
        collector.record_exception(tenant_id="TENANT_A", status="RESOLVED")
        collector.record_exception(tenant_id="TENANT_B", status="RESOLVED")
        
        # Persist all
        collector.persist_all_metrics()
        
        # Verify files exist
        assert (Path(temp_storage_dir) / "TENANT_A.json").exists()
        assert (Path(temp_storage_dir) / "TENANT_B.json").exists()

    def test_get_metrics_includes_rich_metrics(self, collector):
        """Test that get_metrics includes all rich metrics."""
        tenant_id = "TENANT_A"
        
        # Record various metrics
        collector.record_playbook_execution(
            tenant_id=tenant_id,
            playbook_id="PB01",
            success=True,
            execution_time_seconds=5.0,
        )
        collector.record_tool_invocation(
            tenant_id=tenant_id,
            tool_name="retry_settlement",
            success=True,
            latency_seconds=0.5,
            retry_count=0,
        )
        collector.update_approval_queue_metrics(
            tenant_id=tenant_id,
            pending_approvals=[{"submitted_at": datetime.now(timezone.utc).isoformat()}],
        )
        collector.record_exception(
            tenant_id=tenant_id,
            status="RESOLVED",
            exception_type="SETTLEMENT_FAIL",
            exception_id="EX001",
            confidence=0.8,
        )
        
        # Get metrics
        metrics = collector.get_metrics(tenant_id)
        
        # Verify all rich metrics are present
        assert "playbookMetrics" in metrics
        assert "PB01" in metrics["playbookMetrics"]
        assert "toolMetrics" in metrics
        assert "retry_settlement" in metrics["toolMetrics"]
        assert "approvalQueueMetrics" in metrics
        assert "exceptionTypeRecurrence" in metrics
        assert "SETTLEMENT_FAIL" in metrics["exceptionTypeRecurrence"]
        assert "confidenceDistribution" in metrics

    def test_record_pipeline_run_with_rich_metrics(self, collector):
        """Test recording pipeline run with rich metrics extraction."""
        tenant_id = "TENANT_A"
        
        results = [
            {
                "status": "RESOLVED",
                "stages": {
                    "policy": {
                        "evidence": ["Actionability: ACTIONABLE_APPROVED_PROCESS"],
                        "confidence": 0.85,
                    },
                    "triage": {"confidence": 0.9},
                },
                "exception": {
                    "exception_type": "SETTLEMENT_FAIL",
                    "exception_id": "EX001",
                },
            },
            {
                "status": "ESCALATED",
                "stages": {
                    "policy": {
                        "evidence": ["Actionability: NON_ACTIONABLE_INFO_ONLY"],
                        "confidence": 0.6,
                    },
                },
                "exception": {
                    "exception_type": "SETTLEMENT_FAIL",
                    "exception_id": "EX002",
                },
            },
        ]
        
        collector.record_pipeline_run(tenant_id=tenant_id, results=results)
        
        metrics = collector.get_metrics(tenant_id)
        
        # Verify exception tracking
        assert metrics["exceptionCount"] == 2
        assert metrics["actionableApprovedCount"] == 1
        assert metrics["nonActionableCount"] == 1
        assert metrics["escalatedCount"] == 1
        
        # Verify recurrence tracking
        assert "SETTLEMENT_FAIL" in metrics["exceptionTypeRecurrence"]
        recurrence = metrics["exceptionTypeRecurrence"]["SETTLEMENT_FAIL"]
        assert recurrence["occurrenceCount"] == 2
        assert recurrence["uniqueCount"] == 2
        
        # Verify confidence distribution
        conf_dist = metrics["confidenceDistribution"]
        assert conf_dist["sampleCount"] == 2  # Two confidence samples

