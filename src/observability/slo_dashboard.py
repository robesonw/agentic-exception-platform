"""
SLO Dashboard Support (P3-25).

Helper functions for exposing SLO status summaries for supervisor dashboard.
"""

from typing import Optional

from src.observability.slo_engine import SLOEngine, SLOStatus, get_slo_engine


def get_slo_summary(
    tenant_id: str, domain: Optional[str] = None
) -> dict[str, any]:
    """
    Get SLO summary for supervisor dashboard.
    
    Args:
        tenant_id: Tenant identifier
        domain: Optional domain name
        
    Returns:
        Dictionary with SLO summary suitable for dashboard display
    """
    slo_engine = get_slo_engine()
    status = slo_engine.compute_slo_status(tenant_id, domain)
    
    # Build summary
    summary = {
        "tenant_id": status.tenant_id,
        "domain": status.domain,
        "overall_passed": status.overall_passed,
        "timestamp": status.timestamp.isoformat(),
        "dimensions": {
            "latency": {
                "current": status.latency_status.current_value,
                "target": status.latency_status.target_value,
                "passed": status.latency_status.passed,
                "unit": "ms",
            },
            "error_rate": {
                "current": status.error_rate_status.current_value,
                "target": status.error_rate_status.target_value,
                "passed": status.error_rate_status.passed,
                "unit": "percentage",
            },
            "mttr": {
                "current": status.mttr_status.current_value,
                "target": status.mttr_status.target_value,
                "passed": status.mttr_status.passed,
                "unit": "minutes",
            },
            "auto_resolution_rate": {
                "current": status.auto_resolution_rate_status.current_value,
                "target": status.auto_resolution_rate_status.target_value,
                "passed": status.auto_resolution_rate_status.passed,
                "unit": "percentage",
            },
        },
    }
    
    if status.throughput_status:
        summary["dimensions"]["throughput"] = {
            "current": status.throughput_status.current_value,
            "target": status.throughput_status.target_value,
            "passed": status.throughput_status.passed,
            "unit": "exceptions_per_second",
        }
    
    return summary


def get_slo_summaries_for_tenants(
    tenant_ids: list[str], domain: Optional[str] = None
) -> dict[str, dict[str, any]]:
    """
    Get SLO summaries for multiple tenants.
    
    Args:
        tenant_ids: List of tenant identifiers
        domain: Optional domain filter
        
    Returns:
        Dictionary mapping tenant_id to SLO summary
    """
    summaries = {}
    
    for tenant_id in tenant_ids:
        try:
            summaries[tenant_id] = get_slo_summary(tenant_id, domain)
        except Exception as e:
            # Log error but continue with other tenants
            import logging
            
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get SLO summary for tenant {tenant_id}: {e}")
            summaries[tenant_id] = {
                "tenant_id": tenant_id,
                "domain": domain,
                "error": str(e),
            }
    
    return summaries

