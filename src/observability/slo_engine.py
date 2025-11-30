"""
SLO/SLA Engine (P3-25).

Computes SLO status from metrics and compares against targets.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.observability.metrics import MetricsCollector, get_metrics_collector
from src.observability.slo_config import SLOConfig, load_slo_config

logger = logging.getLogger(__name__)


@dataclass
class SLODimensionStatus:
    """Status for a single SLO dimension."""

    dimension_name: str
    current_value: float
    target_value: float
    passed: bool
    margin: float  # Difference between current and target (positive = passed, negative = failed)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "dimension_name": self.dimension_name,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "passed": self.passed,
            "margin": self.margin,
        }


@dataclass
class SLOStatus:
    """
    Overall SLO status for a tenant and domain.
    
    Includes status for each dimension and overall pass/fail.
    """

    tenant_id: str
    domain: Optional[str]
    timestamp: datetime
    overall_passed: bool
    latency_status: SLODimensionStatus
    error_rate_status: SLODimensionStatus
    mttr_status: SLODimensionStatus
    auto_resolution_rate_status: SLODimensionStatus
    throughput_status: Optional[SLODimensionStatus] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {
            "tenant_id": self.tenant_id,
            "domain": self.domain,
            "timestamp": self.timestamp.isoformat(),
            "overall_passed": self.overall_passed,
            "latency_status": self.latency_status.to_dict(),
            "error_rate_status": self.error_rate_status.to_dict(),
            "mttr_status": self.mttr_status.to_dict(),
            "auto_resolution_rate_status": self.auto_resolution_rate_status.to_dict(),
        }
        if self.throughput_status:
            result["throughput_status"] = self.throughput_status.to_dict()
        return result


class SLOEngine:
    """
    Engine for computing SLO status from metrics.
    
    Aggregates metrics from MetricsCollector and compares against SLOConfig targets.
    """

    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize SLO engine.
        
        Args:
            metrics_collector: Optional MetricsCollector instance
        """
        self.metrics_collector = metrics_collector or get_metrics_collector()

    def compute_slo_status(
        self,
        tenant_id: str,
        domain: Optional[str] = None,
        window_minutes: Optional[int] = None,
    ) -> SLOStatus:
        """
        Compute SLO status for tenant and domain.
        
        Args:
            tenant_id: Tenant identifier
            domain: Optional domain name
            window_minutes: Optional time window override (uses config default if not provided)
            
        Returns:
            SLOStatus instance
        """
        # Load SLO config
        config = load_slo_config(tenant_id, domain)
        
        # Use config window or override
        window = window_minutes or config.window_minutes
        
        # Get metrics
        metrics = self.metrics_collector.get_or_create_metrics(tenant_id)
        
        # Compute latency (p95 from tool metrics)
        p95_latency_ms = self._compute_p95_latency_ms(metrics)
        latency_status = SLODimensionStatus(
            dimension_name="latency",
            current_value=p95_latency_ms,
            target_value=config.target_latency_ms,
            passed=p95_latency_ms <= config.target_latency_ms,
            margin=config.target_latency_ms - p95_latency_ms,
        )
        
        # Compute error rate
        error_rate = self._compute_error_rate(metrics)
        error_rate_status = SLODimensionStatus(
            dimension_name="error_rate",
            current_value=error_rate,
            target_value=config.target_error_rate,
            passed=error_rate <= config.target_error_rate,
            margin=config.target_error_rate - error_rate,
        )
        
        # Compute MTTR (convert seconds to minutes)
        mttr_seconds = metrics.get_mttr_seconds()
        mttr_minutes = mttr_seconds / 60.0 if mttr_seconds > 0 else 0.0
        mttr_status = SLODimensionStatus(
            dimension_name="mttr",
            current_value=mttr_minutes,
            target_value=config.target_mttr_minutes,
            passed=mttr_minutes <= config.target_mttr_minutes if mttr_minutes > 0 else True,
            margin=config.target_mttr_minutes - mttr_minutes if mttr_minutes > 0 else config.target_mttr_minutes,
        )
        
        # Compute auto-resolution rate
        auto_resolution_rate = metrics.get_auto_resolution_rate()
        auto_resolution_rate_status = SLODimensionStatus(
            dimension_name="auto_resolution_rate",
            current_value=auto_resolution_rate,
            target_value=config.target_auto_resolution_rate,
            passed=auto_resolution_rate >= config.target_auto_resolution_rate,
            margin=auto_resolution_rate - config.target_auto_resolution_rate,
        )
        
        # Compute throughput (if configured)
        throughput_status = None
        if config.target_throughput is not None:
            throughput = self._compute_throughput(metrics, window)
            throughput_status = SLODimensionStatus(
                dimension_name="throughput",
                current_value=throughput,
                target_value=config.target_throughput,
                passed=throughput >= config.target_throughput,
                margin=throughput - config.target_throughput,
            )
        
        # Overall status: all dimensions must pass
        overall_passed = (
            latency_status.passed
            and error_rate_status.passed
            and mttr_status.passed
            and auto_resolution_rate_status.passed
            and (throughput_status is None or throughput_status.passed)
        )
        
        return SLOStatus(
            tenant_id=tenant_id,
            domain=domain,
            timestamp=datetime.now(timezone.utc),
            overall_passed=overall_passed,
            latency_status=latency_status,
            error_rate_status=error_rate_status,
            mttr_status=mttr_status,
            auto_resolution_rate_status=auto_resolution_rate_status,
            throughput_status=throughput_status,
        )

    def _compute_p95_latency_ms(self, metrics) -> float:
        """
        Compute p95 latency in milliseconds from tool metrics.
        
        Args:
            metrics: TenantMetrics instance
            
        Returns:
            p95 latency in milliseconds
        """
        all_latencies: list[float] = []
        
        for tool_metrics in metrics.tool_metrics.values():
            all_latencies.extend(tool_metrics.latency_samples)
        
        if not all_latencies:
            return 0.0
        
        # Calculate p95
        sorted_latencies = sorted(all_latencies)
        index = int(len(sorted_latencies) * 0.95)
        p95_seconds = sorted_latencies[min(index, len(sorted_latencies) - 1)]
        
        # Convert to milliseconds
        return p95_seconds * 1000.0

    def _compute_error_rate(self, metrics) -> float:
        """
        Compute error rate from tool metrics.
        
        Args:
            metrics: TenantMetrics instance
            
        Returns:
            Error rate as float between 0.0 and 1.0
        """
        total_invocations = 0
        total_failures = 0
        
        for tool_metrics in metrics.tool_metrics.values():
            total_invocations += tool_metrics.invocation_count
            total_failures += tool_metrics.failure_count
        
        if total_invocations == 0:
            return 0.0
        
        return total_failures / total_invocations

    def _compute_throughput(self, metrics, window_minutes: int) -> float:
        """
        Compute throughput (exceptions per second).
        
        Args:
            metrics: TenantMetrics instance
            window_minutes: Time window in minutes
            
        Returns:
            Throughput as exceptions per second
        """
        if metrics.exception_count == 0:
            return 0.0
        
        window_seconds = window_minutes * 60.0
        return metrics.exception_count / window_seconds if window_seconds > 0 else 0.0


# Global engine instance
_slo_engine: Optional[SLOEngine] = None


def get_slo_engine() -> SLOEngine:
    """
    Get global SLO engine instance.
    
    Returns:
        SLOEngine instance
    """
    global _slo_engine
    if _slo_engine is None:
        _slo_engine = SLOEngine()
    return _slo_engine

