"""
Metrics API endpoints.
Exposes exception processing metrics per tenant.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path

from src.observability.metrics import MetricsCollector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])

# Global metrics collector instance
# In production, this would be injected via dependency injection
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """
    Get the global metrics collector instance.
    
    Returns:
        MetricsCollector instance
    """
    return _metrics_collector


@router.get("/{tenant_id}")
async def get_tenant_metrics(tenant_id: str = Path(..., description="Tenant identifier")) -> dict[str, Any]:
    """
    Get metrics for a specific tenant.
    
    Returns:
        Dictionary with metrics:
        {
            "tenantId": str,
            "exceptionCount": int,
            "autoResolutionRate": float,
            "mttrSeconds": float,
            "actionableApprovedCount": int,
            "actionableNonApprovedCount": int,
            "nonActionableCount": int,
            "escalatedCount": int
        }
    """
    logger.info(f"Retrieving metrics for tenant {tenant_id}")
    
    try:
        metrics = get_metrics_collector().get_metrics(tenant_id)
        return metrics
    except Exception as e:
        logger.error(f"Failed to retrieve metrics for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")


@router.get("")
async def get_all_metrics() -> dict[str, dict[str, Any]]:
    """
    Get metrics for all tenants.
    
    Returns:
        Dictionary mapping tenant_id to metrics
    """
    logger.info("Retrieving metrics for all tenants")
    
    try:
        all_metrics = get_metrics_collector().get_all_metrics()
        return all_metrics
    except Exception as e:
        logger.error(f"Failed to retrieve all metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")
