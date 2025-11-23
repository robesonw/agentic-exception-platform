"""
Metrics collector for tracking exception processing metrics per tenant.
Matches specification from docs/master_project_instruction_full.md
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TenantMetrics:
    """Metrics for a single tenant."""

    tenant_id: str
    exception_count: int = 0
    auto_resolution_count: int = 0
    actionable_approved_count: int = 0
    actionable_non_approved_count: int = 0
    non_actionable_count: int = 0
    escalated_count: int = 0
    total_resolution_time_seconds: float = 0.0
    resolution_timestamps: list[datetime] = field(default_factory=list)

    def get_auto_resolution_rate(self) -> float:
        """
        Calculate auto-resolution rate.
        
        Returns:
            Auto-resolution rate as float between 0.0 and 1.0
        """
        if self.exception_count == 0:
            return 0.0
        return self.auto_resolution_count / self.exception_count

    def get_mttr_seconds(self) -> float:
        """
        Calculate Mean Time To Resolution (MTTR) in seconds.
        
        For MVP, this is approximate based on resolution timestamps.
        
        Returns:
            MTTR in seconds, or 0.0 if no resolutions
        """
        if not self.resolution_timestamps:
            return 0.0
        
        # For MVP, calculate average time between exception creation and resolution
        # In production, this would track actual resolution times
        if len(self.resolution_timestamps) < 2:
            return 0.0
        
        # Calculate average time between timestamps
        total_time = 0.0
        for i in range(1, len(self.resolution_timestamps)):
            time_diff = (
                self.resolution_timestamps[i] - self.resolution_timestamps[i - 1]
            ).total_seconds()
            total_time += time_diff
        
        return total_time / (len(self.resolution_timestamps) - 1) if len(self.resolution_timestamps) > 1 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """
        Convert metrics to dictionary for API response.
        
        Returns:
            Dictionary with all metrics
        """
        return {
            "tenantId": self.tenant_id,
            "exceptionCount": self.exception_count,
            "autoResolutionRate": self.get_auto_resolution_rate(),
            "mttrSeconds": self.get_mttr_seconds(),
            "actionableApprovedCount": self.actionable_approved_count,
            "actionableNonApprovedCount": self.actionable_non_approved_count,
            "nonActionableCount": self.non_actionable_count,
            "escalatedCount": self.escalated_count,
            "autoResolutionCount": self.auto_resolution_count,  # Include raw count for reference
        }


class MetricsCollector:
    """
    Metrics collector with per-tenant isolation.
    
    Tracks exception processing metrics per tenant:
    - exceptionCount
    - autoResolutionRate
    - mttrSeconds (MVP approximate)
    - actionableApprovedCount
    - actionableNonApprovedCount
    - nonActionableCount
    """

    def __init__(self):
        """Initialize metrics collector."""
        self._metrics: dict[str, TenantMetrics] = {}

    def get_or_create_metrics(self, tenant_id: str) -> TenantMetrics:
        """
        Get or create metrics for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            TenantMetrics instance
        """
        if tenant_id not in self._metrics:
            self._metrics[tenant_id] = TenantMetrics(tenant_id=tenant_id)
            logger.info(f"Created metrics tracking for tenant {tenant_id}")
        
        return self._metrics[tenant_id]

    def record_exception(
        self,
        tenant_id: str,
        status: str,
        actionability: str | None = None,
        resolution_time_seconds: float = 0.0,
    ) -> None:
        """
        Record an exception processing result.
        
        Args:
            tenant_id: Tenant identifier
            status: Final status (RESOLVED, ESCALATED, IN_PROGRESS, OPEN)
            actionability: Actionability classification (if available)
            resolution_time_seconds: Time taken to resolve (for MVP, approximate)
        """
        metrics = self.get_or_create_metrics(tenant_id)
        metrics.exception_count += 1
        
        # Track actionability
        if actionability == "ACTIONABLE_APPROVED_PROCESS":
            metrics.actionable_approved_count += 1
        elif actionability == "ACTIONABLE_NON_APPROVED_PROCESS":
            metrics.actionable_non_approved_count += 1
        elif actionability == "NON_ACTIONABLE_INFO_ONLY":
            metrics.non_actionable_count += 1
        
        # Track resolution status
        if status == "RESOLVED":
            metrics.auto_resolution_count += 1
            if resolution_time_seconds > 0:
                metrics.total_resolution_time_seconds += resolution_time_seconds
                metrics.resolution_timestamps.append(datetime.now(timezone.utc))
        elif status == "ESCALATED":
            metrics.escalated_count += 1
        
        logger.debug(
            f"Recorded exception for tenant {tenant_id}: status={status}, "
            f"actionability={actionability}"
        )

    def record_pipeline_run(
        self, tenant_id: str, results: list[dict[str, Any]]
    ) -> None:
        """
        Record metrics from a pipeline run.
        
        Args:
            tenant_id: Tenant identifier
            results: List of exception processing results from pipeline
        """
        for result in results:
            status = result.get("status", "UNKNOWN")
            actionability = None
            
            # Extract actionability from stages if available
            stages = result.get("stages", {})
            if "policy" in stages and isinstance(stages["policy"], dict):
                policy_evidence = stages["policy"].get("evidence", [])
                for evidence in policy_evidence:
                    if "Actionability:" in evidence:
                        actionability = evidence.split("Actionability:")[1].strip()
                        break
            
            # Calculate approximate resolution time (for MVP)
            # In production, this would track actual timestamps
            resolution_time_seconds = 0.0
            if status == "RESOLVED":
                # Approximate: assume 1 second per stage completed
                completed_stages = sum(
                    1 for stage in stages.values() if isinstance(stage, dict) and "error" not in stage
                )
                resolution_time_seconds = completed_stages * 1.0
            
            self.record_exception(tenant_id, status, actionability, resolution_time_seconds)

    def get_metrics(self, tenant_id: str) -> dict[str, Any]:
        """
        Get metrics for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with all metrics for the tenant
        """
        metrics = self.get_or_create_metrics(tenant_id)
        return metrics.to_dict()

    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """
        Get metrics for all tenants.
        
        Returns:
            Dictionary mapping tenant_id to metrics
        """
        return {tenant_id: metrics.to_dict() for tenant_id, metrics in self._metrics.items()}

    def reset_metrics(self, tenant_id: str) -> None:
        """
        Reset metrics for a tenant.
        
        Args:
            tenant_id: Tenant identifier
        """
        if tenant_id in self._metrics:
            self._metrics[tenant_id] = TenantMetrics(tenant_id=tenant_id)
            logger.info(f"Reset metrics for tenant {tenant_id}")

    def clear_all_metrics(self) -> None:
        """Clear all metrics for all tenants."""
        self._metrics.clear()
        logger.info("Cleared all metrics")

