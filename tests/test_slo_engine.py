"""
Tests for SLO Engine (P3-25).

Tests SLO status computation, tenant-specific configs, and dimension evaluation.
"""

import pytest

from src.observability.metrics import MetricsCollector, TenantMetrics, ToolMetrics
from src.observability.slo_config import SLOConfig, SLOConfigLoader
from src.observability.slo_engine import SLOEngine, SLOStatus


class TestSLOConfig:
    """Tests for SLOConfig."""

    def test_slo_config_defaults(self):
        """Test SLO config with defaults."""
        config = SLOConfig(tenant_id="tenant_001")
        
        assert config.tenant_id == "tenant_001"
        assert config.domain is None
        assert config.target_latency_ms == 1000.0
        assert config.target_error_rate == 0.01
        assert config.target_mttr_minutes == 30.0
        assert config.target_auto_resolution_rate == 0.80
        assert config.target_throughput is None
        assert config.window_minutes == 60

    def test_slo_config_custom(self):
        """Test SLO config with custom values."""
        config = SLOConfig(
            tenant_id="tenant_001",
            domain="TestDomain",
            target_latency_ms=500.0,
            target_error_rate=0.005,
            target_mttr_minutes=15.0,
            target_auto_resolution_rate=0.90,
            target_throughput=10.0,
            window_minutes=30,
        )
        
        assert config.target_latency_ms == 500.0
        assert config.target_error_rate == 0.005
        assert config.target_mttr_minutes == 15.0
        assert config.target_auto_resolution_rate == 0.90
        assert config.target_throughput == 10.0
        assert config.window_minutes == 30

    def test_slo_config_to_dict(self):
        """Test SLO config to dictionary conversion."""
        config = SLOConfig(tenant_id="tenant_001", domain="TestDomain")
        data = config.to_dict()
        
        assert data["tenant_id"] == "tenant_001"
        assert data["domain"] == "TestDomain"
        assert "target_latency_ms" in data

    def test_slo_config_from_dict(self):
        """Test SLO config from dictionary."""
        data = {
            "tenant_id": "tenant_001",
            "domain": "TestDomain",
            "target_latency_ms": 500.0,
            "target_error_rate": 0.005,
        }
        
        config = SLOConfig.from_dict(data)
        
        assert config.tenant_id == "tenant_001"
        assert config.domain == "TestDomain"
        assert config.target_latency_ms == 500.0
        assert config.target_error_rate == 0.005
        # Should use defaults for missing fields
        assert config.target_mttr_minutes == 30.0


class TestSLOConfigLoader:
    """Tests for SLOConfigLoader."""

    def test_load_defaults_when_file_missing(self, tmp_path):
        """Test that defaults are used when config file is missing."""
        loader = SLOConfigLoader(config_dir=str(tmp_path))
        
        config = loader.load_config("tenant_001", "TestDomain")
        
        assert config.tenant_id == "tenant_001"
        assert config.domain == "TestDomain"
        assert config.target_latency_ms == 1000.0  # Default

    def test_load_from_yaml_file(self, tmp_path):
        """Test loading config from YAML file."""
        import yaml
        
        config_dir = tmp_path / "slo"
        config_dir.mkdir()
        
        config_file = config_dir / "tenant_001_TestDomain.yaml"
        config_data = {
            "target_latency_ms": 500.0,
            "target_error_rate": 0.005,
            "target_mttr_minutes": 15.0,
            "target_auto_resolution_rate": 0.90,
        }
        
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)
        
        loader = SLOConfigLoader(config_dir=str(config_dir))
        config = loader.load_config("tenant_001", "TestDomain")
        
        assert config.target_latency_ms == 500.0
        assert config.target_error_rate == 0.005
        assert config.target_mttr_minutes == 15.0
        assert config.target_auto_resolution_rate == 0.90

    def test_config_caching(self, tmp_path):
        """Test that configs are cached."""
        loader = SLOConfigLoader(config_dir=str(tmp_path))
        
        config1 = loader.load_config("tenant_001", "TestDomain")
        config2 = loader.load_config("tenant_001", "TestDomain")
        
        # Should return same instance (cached)
        assert config1 is config2


class TestSLOEngine:
    """Tests for SLOEngine."""

    def test_compute_slo_status_all_passed(self):
        """Test SLO status computation when all dimensions pass."""
        # Create metrics with good values
        metrics_collector = MetricsCollector()
        metrics = metrics_collector.get_or_create_metrics("tenant_001")
        
        # Set up good metrics
        metrics.exception_count = 100
        metrics.auto_resolution_count = 85  # 85% auto-resolution (above 80% target)
        
        # Add tool metrics with low latency
        tool_metrics = metrics.get_or_create_tool_metrics("test_tool")
        tool_metrics.invocation_count = 100
        tool_metrics.success_count = 100
        tool_metrics.failure_count = 0
        tool_metrics.latency_samples = [0.1, 0.2, 0.3, 0.4, 0.5] * 20  # All < 1s
        
        # Add resolution timestamps (low MTTR)
        from datetime import datetime, timedelta, timezone
        
        now = datetime.now(timezone.utc)
        metrics.resolution_timestamps = [
            now - timedelta(minutes=10),
            now - timedelta(minutes=5),
            now,
        ]
        
        engine = SLOEngine(metrics_collector=metrics_collector)
        status = engine.compute_slo_status("tenant_001")
        
        assert status.overall_passed is True
        assert status.latency_status.passed is True
        assert status.error_rate_status.passed is True
        assert status.auto_resolution_rate_status.passed is True

    def test_compute_slo_status_latency_failed(self):
        """Test SLO status when latency fails."""
        metrics_collector = MetricsCollector()
        metrics = metrics_collector.get_or_create_metrics("tenant_001")
        
        # Set up metrics with high latency
        tool_metrics = metrics.get_or_create_tool_metrics("test_tool")
        tool_metrics.invocation_count = 100
        tool_metrics.success_count = 100
        tool_metrics.latency_samples = [2.0, 2.5, 3.0] * 33  # High latency (> 1s target)
        
        engine = SLOEngine(metrics_collector=metrics_collector)
        status = engine.compute_slo_status("tenant_001")
        
        assert status.latency_status.passed is False
        assert status.overall_passed is False

    def test_compute_slo_status_error_rate_failed(self):
        """Test SLO status when error rate fails."""
        metrics_collector = MetricsCollector()
        metrics = metrics_collector.get_or_create_metrics("tenant_001")
        
        # Set up metrics with high error rate
        tool_metrics = metrics.get_or_create_tool_metrics("test_tool")
        tool_metrics.invocation_count = 100
        tool_metrics.success_count = 90
        tool_metrics.failure_count = 10  # 10% error rate (> 1% target)
        
        engine = SLOEngine(metrics_collector=metrics_collector)
        status = engine.compute_slo_status("tenant_001")
        
        assert status.error_rate_status.passed is False
        assert status.overall_passed is False

    def test_compute_slo_status_auto_resolution_failed(self):
        """Test SLO status when auto-resolution rate fails."""
        metrics_collector = MetricsCollector()
        metrics = metrics_collector.get_or_create_metrics("tenant_001")
        
        # Set up metrics with low auto-resolution
        metrics.exception_count = 100
        metrics.auto_resolution_count = 50  # 50% auto-resolution (< 80% target)
        
        engine = SLOEngine(metrics_collector=metrics_collector)
        status = engine.compute_slo_status("tenant_001")
        
        assert status.auto_resolution_rate_status.passed is False
        assert status.overall_passed is False

    def test_compute_slo_status_with_domain(self):
        """Test SLO status computation with domain."""
        metrics_collector = MetricsCollector()
        metrics = metrics_collector.get_or_create_metrics("tenant_001")
        
        metrics.exception_count = 100
        metrics.auto_resolution_count = 85
        
        engine = SLOEngine(metrics_collector=metrics_collector)
        status = engine.compute_slo_status("tenant_001", domain="TestDomain")
        
        assert status.domain == "TestDomain"
        assert status.tenant_id == "tenant_001"

    def test_compute_p95_latency(self):
        """Test p95 latency computation."""
        metrics_collector = MetricsCollector()
        metrics = metrics_collector.get_or_create_metrics("tenant_001")
        
        # Add latency samples
        tool_metrics = metrics.get_or_create_tool_metrics("test_tool")
        tool_metrics.latency_samples = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        
        engine = SLOEngine(metrics_collector=metrics_collector)
        p95_ms = engine._compute_p95_latency_ms(metrics)
        
        # p95 should be around 0.95 seconds = 950ms
        assert p95_ms > 0
        assert p95_ms == pytest.approx(950.0, abs=50.0)

    def test_compute_error_rate(self):
        """Test error rate computation."""
        metrics_collector = MetricsCollector()
        metrics = metrics_collector.get_or_create_metrics("tenant_001")
        
        # Add tool metrics with failures
        tool_metrics = metrics.get_or_create_tool_metrics("test_tool")
        tool_metrics.invocation_count = 100
        tool_metrics.failure_count = 5  # 5% error rate
        
        engine = SLOEngine(metrics_collector=metrics_collector)
        error_rate = engine._compute_error_rate(metrics)
        
        assert error_rate == 0.05

    def test_compute_throughput(self):
        """Test throughput computation."""
        metrics_collector = MetricsCollector()
        metrics = metrics_collector.get_or_create_metrics("tenant_001")
        
        metrics.exception_count = 3600  # 3600 exceptions
        
        engine = SLOEngine(metrics_collector=metrics_collector)
        throughput = engine._compute_throughput(metrics, window_minutes=60)
        
        # 3600 exceptions in 60 minutes = 1 exception per second
        assert throughput == pytest.approx(1.0, abs=0.1)


class TestSLOStatus:
    """Tests for SLOStatus dataclass."""

    def test_slo_status_to_dict(self):
        """Test SLO status to dictionary conversion."""
        from src.observability.slo_engine import SLODimensionStatus
        
        latency_status = SLODimensionStatus(
            dimension_name="latency",
            current_value=500.0,
            target_value=1000.0,
            passed=True,
            margin=500.0,
        )
        
        error_rate_status = SLODimensionStatus(
            dimension_name="error_rate",
            current_value=0.005,
            target_value=0.01,
            passed=True,
            margin=0.005,
        )
        
        mttr_status = SLODimensionStatus(
            dimension_name="mttr",
            current_value=20.0,
            target_value=30.0,
            passed=True,
            margin=10.0,
        )
        
        auto_resolution_status = SLODimensionStatus(
            dimension_name="auto_resolution_rate",
            current_value=0.85,
            target_value=0.80,
            passed=True,
            margin=0.05,
        )
        
        from datetime import datetime, timezone
        
        status = SLOStatus(
            tenant_id="tenant_001",
            domain="TestDomain",
            timestamp=datetime.now(timezone.utc),
            overall_passed=True,
            latency_status=latency_status,
            error_rate_status=error_rate_status,
            mttr_status=mttr_status,
            auto_resolution_rate_status=auto_resolution_status,
        )
        
        data = status.to_dict()
        
        assert data["tenant_id"] == "tenant_001"
        assert data["domain"] == "TestDomain"
        assert data["overall_passed"] is True
        assert "latency_status" in data
        assert "error_rate_status" in data

