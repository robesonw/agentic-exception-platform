"""
Explanation Analytics (P3-31).

Provides analytics on explanation quality, correlation with outcomes, and MTTR.
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from src.observability.metrics import MetricsCollector, get_metrics_collector
from src.orchestrator.store import ExceptionStore, get_exception_store

logger = logging.getLogger(__name__)


class ExplanationAnalytics:
    """
    Analytics service for explanations.
    
    Provides insights on:
    - Average quality scores
    - Correlation with resolution success/failure
    - Correlation with MTTR
    """

    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
        exception_store: Optional[ExceptionStore] = None,
        audit_dir: str = "./runtime/audit",
    ):
        """
        Initialize explanation analytics.
        
        Args:
            metrics_collector: Optional MetricsCollector instance
            exception_store: Optional ExceptionStore instance
            audit_dir: Directory containing audit logs
        """
        self.metrics_collector = metrics_collector or get_metrics_collector()
        self.exception_store = exception_store or get_exception_store()
        self.audit_dir = Path(audit_dir)

    def get_explanation_analytics(
        self,
        tenant_id: str,
        domain: Optional[str] = None,
        window_hours: int = 24,
    ) -> dict[str, Any]:
        """
        Get explanation analytics for a tenant and optional domain.
        
        Aggregates:
        - Average quality score
        - Correlation with resolution success/failure
        - Correlation with MTTR
        
        Args:
            tenant_id: Tenant identifier
            domain: Optional domain filter
            window_hours: Time window in hours (default: 24)
            
        Returns:
            Dictionary with analytics data
        """
        # Get metrics for tenant
        tenant_metrics = self.metrics_collector.get_or_create_metrics(tenant_id)
        
        # Calculate average quality score
        avg_quality = 0.0
        if tenant_metrics and tenant_metrics.explanation_quality_scores:
            avg_quality = sum(tenant_metrics.explanation_quality_scores) / len(
                tenant_metrics.explanation_quality_scores
            )
        
        # Calculate average latency
        avg_latency_ms = 0.0
        if tenant_metrics and tenant_metrics.explanation_latency_samples:
            avg_latency_ms = sum(tenant_metrics.explanation_latency_samples) / len(
                tenant_metrics.explanation_latency_samples
            )
        
        # Get total explanations generated
        total_explanations = 0
        if tenant_metrics:
            total_explanations = tenant_metrics.explanations_generated_total
        
        # Calculate explanations per exception
        explanations_per_exception = {}
        if tenant_metrics:
            explanations_per_exception = tenant_metrics.explanations_per_exception.copy()
        
        # Get correlation with resolution success
        # For MVP, we'll use a simple heuristic based on exception status
        correlation_with_success = self._calculate_success_correlation(
            tenant_id, domain, window_hours
        )
        
        # Get correlation with MTTR
        correlation_with_mttr = self._calculate_mttr_correlation(
            tenant_id, domain, window_hours
        )
        
        return {
            "tenant_id": tenant_id,
            "domain": domain,
            "window_hours": window_hours,
            "total_explanations": total_explanations,
            "average_quality_score": avg_quality,
            "average_latency_ms": avg_latency_ms,
            "explanations_per_exception": explanations_per_exception,
            "correlation_with_success": correlation_with_success,
            "correlation_with_mttr": correlation_with_mttr,
            "quality_score_distribution": self._get_quality_distribution(tenant_metrics),
            "latency_distribution": self._get_latency_distribution(tenant_metrics),
        }

    def _calculate_success_correlation(
        self, tenant_id: str, domain: Optional[str], window_hours: int
    ) -> dict[str, Any]:
        """
        Calculate correlation between explanation quality and resolution success.
        
        For MVP, uses simple heuristic based on exception status.
        """
        # Get exceptions for tenant
        all_exceptions = self.exception_store.get_tenant_exceptions(tenant_id)
        
        # Filter by domain if specified
        if domain:
            all_exceptions = [
                (exc, result)
                for exc, result in all_exceptions
                if exc.normalized_context.get("domain") == domain
            ]
        
        # Filter by time window
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        recent_exceptions = [
            (exc, result)
            for exc, result in all_exceptions
            if exc.timestamp >= cutoff_time
        ]
        
        # Simple correlation: exceptions with explanations vs without
        # In production, would analyze quality scores vs resolution status
        with_explanations = 0
        successful_with_explanations = 0
        without_explanations = 0
        successful_without_explanations = 0
        
        tenant_metrics = self.metrics_collector.get_or_create_metrics(tenant_id)
        exception_ids_with_explanations = set()
        if tenant_metrics:
            exception_ids_with_explanations = set(tenant_metrics.explanations_per_exception.keys())
        
        for exception, result in recent_exceptions:
            has_explanation = exception.exception_id in exception_ids_with_explanations
            is_successful = (
                exception.resolution_status.value == "RESOLVED"
                if exception.resolution_status
                else False
            )
            
            if has_explanation:
                with_explanations += 1
                if is_successful:
                    successful_with_explanations += 1
            else:
                without_explanations += 1
                if is_successful:
                    successful_without_explanations += 1
        
        # Calculate success rates
        success_rate_with = (
            successful_with_explanations / with_explanations
            if with_explanations > 0
            else 0.0
        )
        success_rate_without = (
            successful_without_explanations / without_explanations
            if without_explanations > 0
            else 0.0
        )
        
        return {
            "with_explanations": {
                "total": with_explanations,
                "successful": successful_with_explanations,
                "success_rate": success_rate_with,
            },
            "without_explanations": {
                "total": without_explanations,
                "successful": successful_without_explanations,
                "success_rate": success_rate_without,
            },
            "correlation": success_rate_with - success_rate_without,
        }

    def _calculate_mttr_correlation(
        self, tenant_id: str, domain: Optional[str], window_hours: int
    ) -> dict[str, Any]:
        """
        Calculate correlation between explanation quality and MTTR.
        
        For MVP, uses simple heuristic.
        """
        tenant_metrics = self.metrics_collector.get_or_create_metrics(tenant_id)
        
        if not tenant_metrics:
            return {"mttr_seconds": 0.0, "correlation": 0.0}
        
        # Get MTTR from metrics
        mttr_seconds = tenant_metrics.get_mttr_seconds()
        
        # Simple correlation: average quality vs MTTR
        # Higher quality should correlate with lower MTTR
        avg_quality = 0.0
        if tenant_metrics.explanation_quality_scores:
            avg_quality = sum(tenant_metrics.explanation_quality_scores) / len(
                tenant_metrics.explanation_quality_scores
            )
        
        # For MVP, use inverse correlation (higher quality = lower MTTR)
        # In production, would use statistical correlation
        correlation = -avg_quality * 0.1  # Simple heuristic
        
        return {
            "mttr_seconds": mttr_seconds,
            "average_quality": avg_quality,
            "correlation": correlation,
        }

    def _get_quality_distribution(
        self, tenant_metrics: Optional[Any]
    ) -> dict[str, int]:
        """Get quality score distribution."""
        if not tenant_metrics or not tenant_metrics.explanation_quality_scores:
            return {"0.0-0.5": 0, "0.5-0.7": 0, "0.7-0.9": 0, "0.9-1.0": 0}
        
        distribution = {"0.0-0.5": 0, "0.5-0.7": 0, "0.7-0.9": 0, "0.9-1.0": 0}
        
        for score in tenant_metrics.explanation_quality_scores:
            if score < 0.5:
                distribution["0.0-0.5"] += 1
            elif score < 0.7:
                distribution["0.5-0.7"] += 1
            elif score < 0.9:
                distribution["0.7-0.9"] += 1
            else:
                distribution["0.9-1.0"] += 1
        
        return distribution

    def _get_latency_distribution(
        self, tenant_metrics: Optional[Any]
    ) -> dict[str, Any]:
        """Get latency distribution."""
        if not tenant_metrics or not tenant_metrics.explanation_latency_samples:
            return {
                "min_ms": 0.0,
                "max_ms": 0.0,
                "avg_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
            }
        
        samples = tenant_metrics.explanation_latency_samples
        sorted_samples = sorted(samples)
        
        return {
            "min_ms": min(samples),
            "max_ms": max(samples),
            "avg_ms": sum(samples) / len(samples),
            "p50_ms": sorted_samples[len(sorted_samples) // 2] if sorted_samples else 0.0,
            "p95_ms": sorted_samples[int(len(sorted_samples) * 0.95)] if sorted_samples else 0.0,
            "p99_ms": sorted_samples[int(len(sorted_samples) * 0.99)] if sorted_samples else 0.0,
        }


# Global analytics instance
_explanation_analytics: Optional[ExplanationAnalytics] = None


def get_explanation_analytics() -> ExplanationAnalytics:
    """
    Get global explanation analytics instance.
    
    Returns:
        ExplanationAnalytics instance
    """
    global _explanation_analytics
    if _explanation_analytics is None:
        _explanation_analytics = ExplanationAnalytics()
    return _explanation_analytics

