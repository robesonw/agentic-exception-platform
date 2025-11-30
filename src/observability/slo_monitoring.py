"""
SLO Monitoring and Alerting (P3-25).

Periodic SLO checks and alerting for SLO violations.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.notify.service import NotificationService, get_notification_service
from src.observability.slo_engine import SLOEngine, SLOStatus, get_slo_engine

logger = logging.getLogger(__name__)


class SLOMonitor:
    """
    Monitor for SLO status across all tenants.
    
    Periodically checks SLOs and generates alerts for violations.
    """

    def __init__(
        self,
        slo_engine: Optional[SLOEngine] = None,
        notification_service: Optional[NotificationService] = None,
        storage_dir: str = "./runtime/slo",
    ):
        """
        Initialize SLO monitor.
        
        Args:
            slo_engine: Optional SLOEngine instance
            notification_service: Optional NotificationService instance
            storage_dir: Directory for storing SLO status logs
        """
        self.slo_engine = slo_engine or get_slo_engine()
        self.notification_service = notification_service or get_notification_service()
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def run_slo_check_all_tenants(
        self, tenant_ids: Optional[list[str]] = None, domain: Optional[str] = None
    ) -> list[SLOStatus]:
        """
        Run SLO check for all tenants (or specified tenants).
        
        Args:
            tenant_ids: Optional list of tenant IDs to check. If None, checks all known tenants.
            domain: Optional domain filter
            
        Returns:
            List of SLOStatus instances
        """
        from src.observability.metrics import get_metrics_collector
        
        metrics_collector = get_metrics_collector()
        
        # Get tenant IDs to check
        if tenant_ids is None:
            # Get all tenants from metrics collector
            tenant_ids = list(metrics_collector._metrics.keys())
        
        if not tenant_ids:
            logger.warning("No tenants found for SLO check")
            return []
        
        logger.info(f"Running SLO check for {len(tenant_ids)} tenant(s)")
        
        results: list[SLOStatus] = []
        
        for tenant_id in tenant_ids:
            try:
                status = self.slo_engine.compute_slo_status(tenant_id, domain)
                results.append(status)
                
                # Log status
                self._log_slo_status(status)
                
                # Generate alerts for failures
                if not status.overall_passed:
                    self._generate_alert(status)
                    
                    # Phase 3: Trigger runbook suggestions for SLO violations (P3-27)
                    try:
                        from src.operations.runbook_integration import trigger_runbooks_for_slo_violation
                        
                        suggested_runbooks = trigger_runbooks_for_slo_violation(
                            slo_status=status,
                            auto_execute=False,  # Don't auto-execute, just suggest
                            tenant_id=status.tenant_id,
                        )
                        if suggested_runbooks:
                            logger.info(
                                f"Suggested {len(suggested_runbooks)} runbook(s) for SLO violation "
                                f"(tenant={status.tenant_id})"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to trigger runbook suggestions for SLO violation: {e}")
                    
            except Exception as e:
                logger.error(
                    f"Failed to compute SLO status for tenant {tenant_id}: {e}",
                    exc_info=True,
                )
        
        return results

    def _log_slo_status(self, status: SLOStatus) -> None:
        """
        Log SLO status to JSONL file.
        
        Args:
            status: SLOStatus instance
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_file = self.storage_dir / f"{timestamp}_slo_status.jsonl"
        
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(status.to_dict(), default=str) + "\n")
            logger.debug(f"Logged SLO status to {log_file}")
        except Exception as e:
            logger.error(f"Failed to log SLO status: {e}", exc_info=True)

    def _generate_alert(self, status: SLOStatus) -> None:
        """
        Generate alert for SLO violation.
        
        Args:
            status: SLOStatus instance with overall_passed=False
        """
        # Build failure details
        failed_dimensions = []
        
        if not status.latency_status.passed:
            failed_dimensions.append(
                f"Latency: {status.latency_status.current_value:.2f}ms "
                f"(target: {status.latency_status.target_value:.2f}ms)"
            )
        
        if not status.error_rate_status.passed:
            failed_dimensions.append(
                f"Error Rate: {status.error_rate_status.current_value:.2%} "
                f"(target: {status.error_rate_status.target_value:.2%})"
            )
        
        if not status.mttr_status.passed:
            failed_dimensions.append(
                f"MTTR: {status.mttr_status.current_value:.2f}min "
                f"(target: {status.mttr_status.target_value:.2f}min)"
            )
        
        if not status.auto_resolution_rate_status.passed:
            failed_dimensions.append(
                f"Auto-Resolution Rate: {status.auto_resolution_rate_status.current_value:.2%} "
                f"(target: {status.auto_resolution_rate_status.target_value:.2%})"
            )
        
        if status.throughput_status and not status.throughput_status.passed:
            failed_dimensions.append(
                f"Throughput: {status.throughput_status.current_value:.2f}/s "
                f"(target: {status.throughput_status.target_value:.2f}/s)"
            )
        
        subject = f"[SLO Violation] Tenant {status.tenant_id}"
        if status.domain:
            subject += f" - Domain {status.domain}"
        
        message = (
            f"SLO violation detected for tenant {status.tenant_id}.\n\n"
            f"Failed dimensions:\n"
            + "\n".join(f"  - {dim}" for dim in failed_dimensions)
            + f"\n\nTimestamp: {status.timestamp.isoformat()}"
        )
        
        try:
            self.notification_service.send_notification(
                tenant_id=status.tenant_id,
                group="SLOOps",  # SLO operations group
                subject=subject,
                message=message,
                payload_link=f"/ui/slo/{status.tenant_id}/{status.domain or 'all'}",
            )
            logger.warning(
                f"Generated SLO violation alert for tenant {status.tenant_id}, "
                f"domain {status.domain}"
            )
        except Exception as e:
            logger.error(f"Failed to send SLO violation alert: {e}", exc_info=True)


# Global monitor instance
_slo_monitor: Optional[SLOMonitor] = None


def get_slo_monitor() -> SLOMonitor:
    """
    Get global SLO monitor instance.
    
    Returns:
        SLOMonitor instance
    """
    global _slo_monitor
    if _slo_monitor is None:
        _slo_monitor = SLOMonitor()
    return _slo_monitor


def run_slo_check_all_tenants(
    tenant_ids: Optional[list[str]] = None, domain: Optional[str] = None
) -> list[SLOStatus]:
    """
    Run SLO check for all tenants.
    
    Convenience function for periodic jobs.
    
    Args:
        tenant_ids: Optional list of tenant IDs to check
        domain: Optional domain filter
        
    Returns:
        List of SLOStatus instances
    """
    monitor = get_slo_monitor()
    return monitor.run_slo_check_all_tenants(tenant_ids, domain)

