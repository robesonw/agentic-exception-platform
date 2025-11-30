"""
Tests for Explanation Integration with Audit and Metrics (P3-31).

Tests audit logging, metrics tracking, quality scoring, and analytics.
"""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path

from src.audit.logger import AuditLogger
from src.explainability.quality import generate_explanation_hash, score_explanation
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.observability.metrics import MetricsCollector
from src.orchestrator.store import ExceptionStore
from src.services.explanation_analytics import ExplanationAnalytics, get_explanation_analytics
from src.services.explanation_service import ExplanationFormat, ExplanationService


@pytest.fixture
def sample_exception():
    """Create a sample exception record."""
    return ExceptionRecord(
        exception_id="exc_001",
        tenant_id="tenant_001",
        exception_type="DataQualityFailure",
        severity=Severity.HIGH,
        resolution_status=ResolutionStatus.RESOLVED,
        source_system="test_system",
        timestamp=datetime.now(timezone.utc),
        raw_payload={"error": "test error"},
        normalized_context={"domain": "TestDomain"},
    )


@pytest.fixture
def sample_pipeline_result():
    """Create a sample pipeline result."""
    return {
        "stages": {
            "intake": {
                "decision": "Normalized exception",
                "confidence": 1.0,
            },
            "triage": {
                "decision": "Classified as DataQualityFailure",
                "confidence": 0.85,
            },
        },
        "context": {},
    }


@pytest.fixture
def audit_logger(tmp_path):
    """Create audit logger for testing."""
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir(parents=True)
    return AuditLogger(run_id="test_run", tenant_id="tenant_001")


@pytest.fixture
def metrics_collector():
    """Create metrics collector for testing."""
    return MetricsCollector()


@pytest.fixture
def exception_store(sample_exception, sample_pipeline_result):
    """Create exception store with sample data."""
    store = ExceptionStore()
    store.store_exception(sample_exception, sample_pipeline_result)
    return store


class TestExplanationQuality:
    """Tests for explanation quality scoring."""

    def test_score_text_explanation_good(self):
        """Test scoring a good text explanation."""
        explanation = """
        Exception exc_001 was classified as DataQualityFailure based on:
        - RAG similarity score of 0.92 with similar historical cases
        - Policy rule match: invalid_format
        - Tool execution result: validation failed
        
        The decision was made because the exception matches known patterns
        and the severity was determined to be HIGH based on the impact analysis.
        """
        
        score = score_explanation(explanation)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be a good score

    def test_score_text_explanation_poor(self):
        """Test scoring a poor text explanation."""
        explanation = "I don't know. Unable to determine."
        
        score = score_explanation(explanation)
        
        assert 0.0 <= score <= 1.0
        assert score < 0.5  # Should be a poor score

    def test_score_json_explanation(self):
        """Test scoring a JSON explanation."""
        explanation = {
            "timeline": {
                "events": [
                    {"agent_name": "TriageAgent", "summary": "Classified"},
                    {"agent_name": "PolicyAgent", "summary": "Allowed"},
                ]
            },
            "evidence_items": [
                {"type": "rag", "description": "Similar case"},
                {"type": "tool", "description": "Tool result"},
            ],
            "agent_decisions": {
                "triage": {"decision": "Classified"},
                "policy": {"decision": "Allowed"},
            },
        }
        
        score = score_explanation(explanation)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be a good score

    def test_generate_explanation_hash(self):
        """Test generating explanation hash."""
        explanation = {"test": "data"}
        
        hash1 = generate_explanation_hash(explanation)
        hash2 = generate_explanation_hash(explanation)
        
        assert hash1 == hash2  # Same explanation should produce same hash
        assert len(hash1) == 64  # SHA256 hex string length


class TestAuditIntegration:
    """Tests for audit integration."""

    def test_log_explanation_generated(self, audit_logger, tmp_path):
        """Test logging explanation generation."""
        audit_logger.log_explanation_generated(
            exception_id="exc_001",
            tenant_id="tenant_001",
            format="json",
            agent_names_involved=["TriageAgent", "PolicyAgent"],
            explanation_id="hash_123",
            explanation_quality_score=0.85,
            latency_ms=150.0,
        )
        
        # Verify audit log was written
        audit_file = tmp_path / "audit" / "tenant_001" / "test_run.jsonl"
        assert audit_file.exists()
        
        # Read and verify entry
        with open(audit_file, "r", encoding="utf-8") as f:
            line = f.readline()
            entry = json.loads(line)
            
            assert entry["event_type"] == "EXPLANATION_GENERATED"
            assert entry["data"]["exception_id"] == "exc_001"
            assert entry["data"]["format"] == "json"
            assert entry["data"]["explanation_id"] == "hash_123"
            assert entry["data"]["explanation_quality_score"] == 0.85
            assert entry["data"]["latency_ms"] == 150.0

    def test_log_decision_with_explanation(self, audit_logger, tmp_path):
        """Test logging decision with explanation fields."""
        audit_logger.log_decision(
            stage="triage",
            decision_json={"decision": "Classified"},
            tenant_id="tenant_001",
            explanation_id="hash_123",
            explanation_quality_score=0.85,
        )
        
        # Verify audit log was written
        audit_file = tmp_path / "audit" / "tenant_001" / "test_run.jsonl"
        assert audit_file.exists()
        
        # Read and verify entry
        with open(audit_file, "r", encoding="utf-8") as f:
            line = f.readline()
            entry = json.loads(line)
            
            assert entry["event_type"] == "decision"
            assert entry["data"]["explanation_id"] == "hash_123"
            assert entry["data"]["explanation_quality_score"] == 0.85


class TestMetricsIntegration:
    """Tests for metrics integration."""

    def test_record_explanation_generated(self, metrics_collector):
        """Test recording explanation metrics."""
        metrics_collector.record_explanation_generated(
            tenant_id="tenant_001",
            exception_id="exc_001",
            latency_ms=150.0,
            quality_score=0.85,
        )
        
        # Verify metrics were recorded
        tenant_metrics = metrics_collector.get_tenant_metrics("tenant_001")
        
        assert tenant_metrics.explanations_generated_total == 1
        assert tenant_metrics.explanations_per_exception["exc_001"] == 1
        assert len(tenant_metrics.explanation_latency_samples) == 1
        assert tenant_metrics.explanation_latency_samples[0] == 150.0
        assert len(tenant_metrics.explanation_quality_scores) == 1
        assert tenant_metrics.explanation_quality_scores[0] == 0.85

    def test_record_multiple_explanations(self, metrics_collector):
        """Test recording multiple explanations."""
        metrics_collector.record_explanation_generated(
            tenant_id="tenant_001",
            exception_id="exc_001",
            latency_ms=150.0,
            quality_score=0.85,
        )
        
        metrics_collector.record_explanation_generated(
            tenant_id="tenant_001",
            exception_id="exc_001",
            latency_ms=200.0,
            quality_score=0.90,
        )
        
        metrics_collector.record_explanation_generated(
            tenant_id="tenant_001",
            exception_id="exc_002",
            latency_ms=100.0,
            quality_score=0.80,
        )
        
        # Verify metrics
        tenant_metrics = metrics_collector.get_tenant_metrics("tenant_001")
        
        assert tenant_metrics.explanations_generated_total == 3
        assert tenant_metrics.explanations_per_exception["exc_001"] == 2
        assert tenant_metrics.explanations_per_exception["exc_002"] == 1
        assert len(tenant_metrics.explanation_latency_samples) == 3
        assert len(tenant_metrics.explanation_quality_scores) == 3


class TestExplanationServiceIntegration:
    """Tests for explanation service with audit and metrics."""

    def test_get_explanation_records_metrics(
        self, exception_store, metrics_collector, audit_logger
    ):
        """Test that getting explanation records metrics."""
        service = ExplanationService(
            exception_store=exception_store,
            audit_logger=audit_logger,
            metrics_collector=metrics_collector,
        )
        
        explanation = service.get_explanation(
            "exc_001", "tenant_001", ExplanationFormat.JSON
        )
        
        # Verify metrics were recorded
        tenant_metrics = metrics_collector.get_tenant_metrics("tenant_001")
        assert tenant_metrics.explanations_generated_total == 1
        assert len(tenant_metrics.explanation_latency_samples) == 1
        assert len(tenant_metrics.explanation_quality_scores) == 1

    def test_get_explanation_logs_audit(
        self, exception_store, audit_logger, tmp_path
    ):
        """Test that getting explanation logs audit entry."""
        service = ExplanationService(
            exception_store=exception_store,
            audit_logger=audit_logger,
        )
        
        explanation = service.get_explanation(
            "exc_001", "tenant_001", ExplanationFormat.JSON
        )
        
        # Verify audit log was written
        audit_file = tmp_path / "audit" / "tenant_001" / "test_run.jsonl"
        assert audit_file.exists()
        
        # Read and verify entry
        with open(audit_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # Find EXPLANATION_GENERATED entry
            explanation_entries = [
                json.loads(line)
                for line in lines
                if json.loads(line).get("event_type") == "EXPLANATION_GENERATED"
            ]
            
            assert len(explanation_entries) == 1
            entry = explanation_entries[0]
            assert entry["data"]["exception_id"] == "exc_001"
            assert "explanation_quality_score" in entry["data"]
            assert "latency_ms" in entry["data"]


class TestExplanationAnalytics:
    """Tests for explanation analytics."""

    def test_get_explanation_analytics(
        self, exception_store, metrics_collector, sample_exception
    ):
        """Test getting explanation analytics."""
        # Record some metrics
        metrics_collector.record_explanation_generated(
            tenant_id="tenant_001",
            exception_id="exc_001",
            latency_ms=150.0,
            quality_score=0.85,
        )
        
        metrics_collector.record_explanation_generated(
            tenant_id="tenant_001",
            exception_id="exc_002",
            latency_ms=200.0,
            quality_score=0.90,
        )
        
        # Get analytics
        analytics = ExplanationAnalytics(
            metrics_collector=metrics_collector,
            exception_store=exception_store,
        )
        
        result = analytics.get_explanation_analytics("tenant_001")
        
        assert result["tenant_id"] == "tenant_001"
        assert result["total_explanations"] == 2
        assert result["average_quality_score"] > 0.0
        assert result["average_latency_ms"] > 0.0
        assert "correlation_with_success" in result
        assert "correlation_with_mttr" in result

    def test_quality_distribution(self, metrics_collector):
        """Test quality score distribution."""
        # Record various quality scores
        for score in [0.3, 0.6, 0.8, 0.95, 0.4, 0.7, 0.9]:
            metrics_collector.record_explanation_generated(
                tenant_id="tenant_001",
                exception_id=f"exc_{score}",
                latency_ms=100.0,
                quality_score=score,
            )
        
        analytics = ExplanationAnalytics(metrics_collector=metrics_collector)
        result = analytics.get_explanation_analytics("tenant_001")
        
        distribution = result["quality_score_distribution"]
        assert distribution["0.0-0.5"] > 0
        assert distribution["0.5-0.7"] > 0
        assert distribution["0.7-0.9"] > 0
        assert distribution["0.9-1.0"] > 0

    def test_latency_distribution(self, metrics_collector):
        """Test latency distribution."""
        # Record various latencies
        latencies = [50.0, 100.0, 150.0, 200.0, 250.0]
        for latency in latencies:
            metrics_collector.record_explanation_generated(
                tenant_id="tenant_001",
                exception_id=f"exc_{latency}",
                latency_ms=latency,
                quality_score=0.85,
            )
        
        analytics = ExplanationAnalytics(metrics_collector=metrics_collector)
        result = analytics.get_explanation_analytics("tenant_001")
        
        latency_dist = result["latency_distribution"]
        assert latency_dist["min_ms"] == 50.0
        assert latency_dist["max_ms"] == 250.0
        assert latency_dist["avg_ms"] > 0.0
        assert latency_dist["p50_ms"] > 0.0
        assert latency_dist["p95_ms"] > 0.0

