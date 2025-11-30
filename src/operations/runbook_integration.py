"""
Runbook Integration Hooks (P3-27).

Connects runbooks to:
- Violation incidents (from P3-22)
- SLO/SLA violations (P3-25)
- Major errors from observability subsystem
"""

import logging
from typing import Any, Optional

from src.operations.runbooks import (
    Runbook,
    RunbookExecutor,
    RunbookStatus,
    get_runbook_executor,
    get_runbook_suggester,
    suggest_runbooks_for_incident,
)

logger = logging.getLogger(__name__)


def trigger_runbooks_for_violation_incident(
    incident: Any,
    auto_execute: bool = False,
    tenant_id: Optional[str] = None,
) -> list[Runbook]:
    """
    Trigger runbook suggestions for a violation incident.
    
    Args:
        incident: Incident object from IncidentManager
        auto_execute: If True, automatically start execution of first suggested runbook
        tenant_id: Optional tenant identifier
        
    Returns:
        List of suggested runbooks
    """
    suggester = get_runbook_suggester()
    
    # Extract incident attributes for matching
    incident_dict = {}
    if hasattr(incident, "violation_type"):
        incident_dict["violation_type"] = incident.violation_type
    if hasattr(incident, "tenant_id"):
        tenant_id = tenant_id or incident.tenant_id
    
    # Suggest runbooks
    suggested = suggester.suggest_runbooks_for_incident(
        incident,
        severity="HIGH",  # Violations are typically high severity
        tenant_id=tenant_id,
    )
    
    if suggested:
        logger.info(
            f"Suggested {len(suggested)} runbook(s) for violation incident "
            f"{getattr(incident, 'id', 'unknown')}"
        )
        
        # Auto-execute first runbook if requested
        if auto_execute and suggested:
            executor = get_runbook_executor()
            execution = executor.start_execution(
                runbook=suggested[0],
                incident_id=getattr(incident, "id", "unknown"),
                tenant_id=tenant_id,
            )
            logger.info(f"Auto-started runbook execution {execution.id}")
    
    return suggested


def trigger_runbooks_for_slo_violation(
    slo_status: Any,
    auto_execute: bool = False,
    tenant_id: Optional[str] = None,
) -> list[Runbook]:
    """
    Trigger runbook suggestions for an SLO violation.
    
    Args:
        slo_status: SLOStatus object from SLO monitoring
        auto_execute: If True, automatically start execution of first suggested runbook
        tenant_id: Optional tenant identifier
        
    Returns:
        List of suggested runbooks
    """
    suggester = get_runbook_suggester()
    
    # Extract SLO violation details
    component = "slo"
    severity = "HIGH"  # SLO violations are typically high severity
    
    # Build incident-like object for matching
    incident_data = {
        "violation_type": "slo_violation",
        "component": component,
        "severity": severity,
        "tags": ["slo", "performance", "monitoring"],
    }
    
    # Add failed dimension info
    failed_dimensions = []
    if hasattr(slo_status, "latency_status") and not slo_status.latency_status.passed:
        failed_dimensions.append("latency")
    if hasattr(slo_status, "error_rate_status") and not slo_status.error_rate_status.passed:
        failed_dimensions.append("error_rate")
    if hasattr(slo_status, "mttr_status") and not slo_status.mttr_status.passed:
        failed_dimensions.append("mttr")
    
    if failed_dimensions:
        incident_data["error_code"] = f"SLO_VIOLATION_{'_'.join(failed_dimensions).upper()}"
    
    # Suggest runbooks
    suggested = suggester.suggest_runbooks_for_incident(
        incident_data,
        component=component,
        severity=severity,
        error_code=incident_data.get("error_code"),
        tags=incident_data.get("tags", []),
    )
    
    if suggested:
        logger.info(
            f"Suggested {len(suggested)} runbook(s) for SLO violation "
            f"(tenant={tenant_id or getattr(slo_status, 'tenant_id', 'unknown')})"
        )
        
        # Auto-execute first runbook if requested
        if auto_execute and suggested:
            executor = get_runbook_executor()
            # Create a synthetic incident ID for SLO violations
            incident_id = f"slo_violation_{getattr(slo_status, 'tenant_id', 'unknown')}_{slo_status.timestamp.isoformat()}"
            execution = executor.start_execution(
                runbook=suggested[0],
                incident_id=incident_id,
                tenant_id=tenant_id or getattr(slo_status, "tenant_id", None),
            )
            logger.info(f"Auto-started runbook execution {execution.id}")
    
    return suggested


def trigger_runbooks_for_observability_error(
    error_type: str,
    component: Optional[str] = None,
    error_code: Optional[str] = None,
    severity: str = "MEDIUM",
    tenant_id: Optional[str] = None,
    auto_execute: bool = False,
) -> list[Runbook]:
    """
    Trigger runbook suggestions for an observability error.
    
    Args:
        error_type: Type of error (e.g., "metrics_collection_failed", "log_aggregation_failed")
        component: Optional component name
        error_code: Optional error code
        severity: Error severity (default: MEDIUM)
        tenant_id: Optional tenant identifier
        auto_execute: If True, automatically start execution of first suggested runbook
        
    Returns:
        List of suggested runbooks
    """
    suggester = get_runbook_suggester()
    
    # Build incident-like object for matching
    incident_data = {
        "violation_type": "observability_error",
        "component": component or "observability",
        "severity": severity,
        "error_code": error_code,
        "tags": ["observability", "monitoring", error_type],
    }
    
    # Suggest runbooks
    suggested = suggester.suggest_runbooks_for_incident(
        incident_data,
        component=component,
        severity=severity,
        error_code=error_code,
        tags=incident_data.get("tags", []),
    )
    
    if suggested:
        logger.info(
            f"Suggested {len(suggested)} runbook(s) for observability error "
            f"{error_type} (component={component})"
        )
        
        # Auto-execute first runbook if requested
        if auto_execute and suggested:
            executor = get_runbook_executor()
            # Create a synthetic incident ID
            incident_id = f"obs_error_{error_type}_{component or 'unknown'}"
            execution = executor.start_execution(
                runbook=suggested[0],
                incident_id=incident_id,
                tenant_id=tenant_id,
            )
            logger.info(f"Auto-started runbook execution {execution.id}")
    
    return suggested

