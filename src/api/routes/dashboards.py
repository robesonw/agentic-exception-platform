"""
Advanced Dashboard API endpoints.

Phase 2: Dashboard APIs for rich visualizations and analytics.
Provides summary, exceptions, playbooks, and tools dashboards.

Matches specification from phase2-mvp-issues.md Issue 41.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Path as PathParam, Query

from src.models.exception_record import ResolutionStatus
from src.observability.metrics import MetricsCollector
from src.orchestrator.store import get_exception_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboards", tags=["dashboards"])

# Global instances (would be injected via dependency in production)
_metrics_collector: MetricsCollector | None = None
_exception_store = None


def set_metrics_collector(collector: MetricsCollector) -> None:
    """Set the metrics collector (for dependency injection)."""
    global _metrics_collector
    _metrics_collector = collector


def get_metrics_collector() -> MetricsCollector:
    """Get the metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def get_exception_store_instance():
    """Get the exception store instance."""
    return get_exception_store()


@router.get("/{tenant_id}/summary")
async def get_summary_dashboard(
    tenant_id: str = PathParam(..., description="Tenant identifier"),
) -> dict[str, Any]:
    """
    Get summary dashboard data for a tenant.
    
    Provides high-level overview metrics including:
    - Overall exception processing statistics
    - Resolution rates and MTTR
    - Approval queue status
    - Top exception types
    - Confidence distribution summary
    
    Args:
        tenant_id: Tenant identifier
        
    Returns:
        Dictionary with summary dashboard data
    """
    logger.info(f"Retrieving summary dashboard for tenant {tenant_id}")
    
    try:
        metrics_collector = get_metrics_collector()
        exception_store = get_exception_store_instance()
        
        # Get metrics
        metrics = metrics_collector.get_metrics(tenant_id)
        
        # Get recent exceptions for additional context
        exceptions = exception_store.get_tenant_exceptions(tenant_id)
        
        # Calculate status breakdown
        status_breakdown = {
            "RESOLVED": 0,
            "ESCALATED": 0,
            "IN_PROGRESS": 0,
            "OPEN": 0,
            "PENDING_APPROVAL": 0,
        }
        
        for exception, pipeline_result in exceptions:
            status = exception.resolution_status.value
            if status in status_breakdown:
                status_breakdown[status] += 1
        
        # Get top exception types by recurrence
        exception_type_recurrence = metrics.get("exceptionTypeRecurrence", {})
        top_exception_types = sorted(
            exception_type_recurrence.items(),
            key=lambda x: x[1].get("occurrenceCount", 0),
            reverse=True,
        )[:5]  # Top 5
        
        top_exception_types_dict = {
            exception_type: {
                "occurrenceCount": data.get("occurrenceCount", 0),
                "uniqueCount": data.get("uniqueCount", 0),
                "recurrenceRate": data.get("recurrenceRate", 0.0),
            }
            for exception_type, data in top_exception_types
        }
        
        # Get confidence distribution summary
        confidence_dist = metrics.get("confidenceDistribution", {})
        
        return {
            "tenantId": tenant_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overview": {
                "totalExceptions": metrics.get("exceptionCount", 0),
                "autoResolutionRate": metrics.get("autoResolutionRate", 0.0),
                "mttrSeconds": metrics.get("mttrSeconds", 0.0),
                "statusBreakdown": status_breakdown,
            },
            "actionability": {
                "actionableApproved": metrics.get("actionableApprovedCount", 0),
                "actionableNonApproved": metrics.get("actionableNonApprovedCount", 0),
                "nonActionable": metrics.get("nonActionableCount", 0),
                "escalated": metrics.get("escalatedCount", 0),
            },
            "approvalQueue": metrics.get("approvalQueueMetrics", {}),
            "topExceptionTypes": top_exception_types_dict,
            "confidenceSummary": {
                "avgConfidence": confidence_dist.get("avgConfidence", 0.0),
                "medianConfidence": confidence_dist.get("medianConfidence", 0.0),
                "sampleCount": confidence_dist.get("sampleCount", 0),
                "distribution": confidence_dist.get("countByRange", {}),
            },
        }
    except Exception as e:
        logger.error(f"Failed to retrieve summary dashboard for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve summary dashboard: {str(e)}"
        )


@router.get("/{tenant_id}/exceptions")
async def get_exceptions_dashboard(
    tenant_id: str = PathParam(..., description="Tenant identifier"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of exceptions to return"),
    status: str | None = Query(None, description="Filter by status (RESOLVED, ESCALATED, etc.)"),
    exception_type: str | None = Query(None, description="Filter by exception type"),
) -> dict[str, Any]:
    """
    Get exceptions dashboard data for a tenant.
    
    Provides detailed exception data including:
    - Recent exceptions with status
    - Exception type breakdown
    - Recurrence statistics
    - Status distribution
    
    Args:
        tenant_id: Tenant identifier
        limit: Maximum number of exceptions to return
        status: Optional status filter
        exception_type: Optional exception type filter
        
    Returns:
        Dictionary with exceptions dashboard data
    """
    logger.info(f"Retrieving exceptions dashboard for tenant {tenant_id}")
    
    try:
        metrics_collector = get_metrics_collector()
        exception_store = get_exception_store_instance()
        
        # Get metrics
        metrics = metrics_collector.get_metrics(tenant_id)
        
        # Get exceptions
        all_exceptions = exception_store.get_tenant_exceptions(tenant_id)
        
        # Apply filters
        filtered_exceptions = []
        for exception, pipeline_result in all_exceptions:
            if status and exception.resolution_status.value != status:
                continue
            if exception_type and exception.exception_type != exception_type:
                continue
            filtered_exceptions.append((exception, pipeline_result))
        
        # Sort by timestamp (most recent first)
        filtered_exceptions.sort(
            key=lambda x: x[0].timestamp if x[0].timestamp else datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        
        # Limit results
        limited_exceptions = filtered_exceptions[:limit]
        
        # Format exception data for dashboard
        exception_list = []
        for exception, pipeline_result in limited_exceptions:
            exception_list.append({
                "exceptionId": exception.exception_id,
                "exceptionType": exception.exception_type,
                "status": exception.resolution_status.value,
                "severity": exception.severity.value if exception.severity else None,
                "timestamp": exception.timestamp.isoformat() if exception.timestamp else None,
                "sourceSystem": exception.source_system,
            })
        
        # Get exception type breakdown
        exception_type_recurrence = metrics.get("exceptionTypeRecurrence", {})
        type_breakdown = {
            exc_type: {
                "count": data.get("occurrenceCount", 0),
                "uniqueCount": data.get("uniqueCount", 0),
                "recurrenceRate": data.get("recurrenceRate", 0.0),
                "firstSeen": data.get("firstSeen"),
                "lastSeen": data.get("lastSeen"),
            }
            for exc_type, data in exception_type_recurrence.items()
        }
        
        # Calculate status distribution
        status_distribution = {}
        for exception, _ in all_exceptions:
            status = exception.resolution_status.value
            status_distribution[status] = status_distribution.get(status, 0) + 1
        
        return {
            "tenantId": tenant_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "totalExceptions": len(all_exceptions),
            "filteredCount": len(filtered_exceptions),
            "exceptions": exception_list,
            "exceptionTypeBreakdown": type_breakdown,
            "statusDistribution": status_distribution,
        }
    except Exception as e:
        logger.error(f"Failed to retrieve exceptions dashboard for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve exceptions dashboard: {str(e)}"
        )


@router.get("/{tenant_id}/playbooks")
async def get_playbooks_dashboard(
    tenant_id: str = PathParam(..., description="Tenant identifier"),
) -> dict[str, Any]:
    """
    Get playbooks dashboard data for a tenant.
    
    Provides playbook effectiveness metrics including:
    - Per-playbook success rates
    - Execution counts and times
    - Top performing playbooks
    - Playbook performance trends
    
    Args:
        tenant_id: Tenant identifier
        
    Returns:
        Dictionary with playbooks dashboard data
    """
    logger.info(f"Retrieving playbooks dashboard for tenant {tenant_id}")
    
    try:
        metrics_collector = get_metrics_collector()
        
        # Get metrics
        metrics = metrics_collector.get_metrics(tenant_id)
        
        # Get playbook metrics
        playbook_metrics = metrics.get("playbookMetrics", {})
        
        # Calculate summary statistics
        total_executions = sum(
            pm.get("executionCount", 0) for pm in playbook_metrics.values()
        )
        total_successes = sum(
            pm.get("successCount", 0) for pm in playbook_metrics.values()
        )
        total_failures = sum(
            pm.get("failureCount", 0) for pm in playbook_metrics.values()
        )
        
        overall_success_rate = (
            total_successes / total_executions if total_executions > 0 else 0.0
        )
        
        # Sort playbooks by execution count (most used first)
        sorted_playbooks = sorted(
            playbook_metrics.items(),
            key=lambda x: x[1].get("executionCount", 0),
            reverse=True,
        )
        
        # Format playbook data
        playbook_list = []
        for playbook_id, pm_data in sorted_playbooks:
            playbook_list.append({
                "playbookId": playbook_id,
                "executionCount": pm_data.get("executionCount", 0),
                "successCount": pm_data.get("successCount", 0),
                "failureCount": pm_data.get("failureCount", 0),
                "successRate": pm_data.get("successRate", 0.0),
                "avgExecutionTimeSeconds": pm_data.get("avgExecutionTimeSeconds", 0.0),
            })
        
        # Top performing playbooks (by success rate, min 5 executions)
        top_performers = [
            {
                "playbookId": playbook_id,
                "successRate": pm_data.get("successRate", 0.0),
                "executionCount": pm_data.get("executionCount", 0),
            }
            for playbook_id, pm_data in playbook_metrics.items()
            if pm_data.get("executionCount", 0) >= 5
        ]
        top_performers.sort(key=lambda x: x["successRate"], reverse=True)
        top_performers = top_performers[:5]  # Top 5
        
        return {
            "tenantId": tenant_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "totalPlaybooks": len(playbook_metrics),
                "totalExecutions": total_executions,
                "totalSuccesses": total_successes,
                "totalFailures": total_failures,
                "overallSuccessRate": overall_success_rate,
            },
            "playbooks": playbook_list,
            "topPerformers": top_performers,
        }
    except Exception as e:
        logger.error(f"Failed to retrieve playbooks dashboard for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve playbooks dashboard: {str(e)}"
        )


@router.get("/{tenant_id}/tools")
async def get_tools_dashboard(
    tenant_id: str = PathParam(..., description="Tenant identifier"),
) -> dict[str, Any]:
    """
    Get tools dashboard data for a tenant.
    
    Provides tool performance metrics including:
    - Per-tool latency (avg, p50, p95, p99)
    - Success/failure rates
    - Retry statistics
    - Top used tools
    - Tool reliability metrics
    
    Args:
        tenant_id: Tenant identifier
        
    Returns:
        Dictionary with tools dashboard data
    """
    logger.info(f"Retrieving tools dashboard for tenant {tenant_id}")
    
    try:
        metrics_collector = get_metrics_collector()
        
        # Get metrics
        metrics = metrics_collector.get_metrics(tenant_id)
        
        # Get tool metrics
        tool_metrics = metrics.get("toolMetrics", {})
        
        # Calculate summary statistics
        total_invocations = sum(
            tm.get("invocationCount", 0) for tm in tool_metrics.values()
        )
        total_successes = sum(
            tm.get("successCount", 0) for tm in tool_metrics.values()
        )
        total_failures = sum(
            tm.get("failureCount", 0) for tm in tool_metrics.values()
        )
        total_retries = sum(
            int(tm.get("avgRetries", 0.0) * tm.get("invocationCount", 0))
            for tm in tool_metrics.values()
        )
        
        overall_success_rate = (
            total_successes / total_invocations if total_invocations > 0 else 0.0
        )
        overall_failure_rate = (
            total_failures / total_invocations if total_invocations > 0 else 0.0
        )
        
        # Sort tools by invocation count (most used first)
        sorted_tools = sorted(
            tool_metrics.items(),
            key=lambda x: x[1].get("invocationCount", 0),
            reverse=True,
        )
        
        # Format tool data
        tool_list = []
        for tool_name, tm_data in sorted_tools:
            tool_list.append({
                "toolName": tool_name,
                "invocationCount": tm_data.get("invocationCount", 0),
                "successCount": tm_data.get("successCount", 0),
                "failureCount": tm_data.get("failureCount", 0),
                "successRate": tm_data.get("successRate", 0.0),
                "failureRate": tm_data.get("failureRate", 0.0),
                "avgLatencySeconds": tm_data.get("avgLatencySeconds", 0.0),
                "avgRetries": tm_data.get("avgRetries", 0.0),
                "p50LatencySeconds": tm_data.get("p50LatencySeconds", 0.0),
                "p95LatencySeconds": tm_data.get("p95LatencySeconds", 0.0),
                "p99LatencySeconds": tm_data.get("p99LatencySeconds", 0.0),
            })
        
        # Top used tools
        top_used = [
            {
                "toolName": tool_name,
                "invocationCount": tm_data.get("invocationCount", 0),
                "successRate": tm_data.get("successRate", 0.0),
            }
            for tool_name, tm_data in sorted_tools[:10]  # Top 10
        ]
        
        # Most reliable tools (by success rate, min 10 invocations)
        reliable_tools = [
            {
                "toolName": tool_name,
                "successRate": tm_data.get("successRate", 0.0),
                "invocationCount": tm_data.get("invocationCount", 0),
                "avgLatencySeconds": tm_data.get("avgLatencySeconds", 0.0),
            }
            for tool_name, tm_data in tool_metrics.items()
            if tm_data.get("invocationCount", 0) >= 10
        ]
        reliable_tools.sort(key=lambda x: x["successRate"], reverse=True)
        reliable_tools = reliable_tools[:5]  # Top 5
        
        # Tools with highest latency
        high_latency_tools = [
            {
                "toolName": tool_name,
                "avgLatencySeconds": tm_data.get("avgLatencySeconds", 0.0),
                "p95LatencySeconds": tm_data.get("p95LatencySeconds", 0.0),
                "invocationCount": tm_data.get("invocationCount", 0),
            }
            for tool_name, tm_data in tool_metrics.items()
            if tm_data.get("invocationCount", 0) >= 5
        ]
        high_latency_tools.sort(key=lambda x: x["avgLatencySeconds"], reverse=True)
        high_latency_tools = high_latency_tools[:5]  # Top 5
        
        return {
            "tenantId": tenant_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "totalTools": len(tool_metrics),
                "totalInvocations": total_invocations,
                "totalSuccesses": total_successes,
                "totalFailures": total_failures,
                "totalRetries": total_retries,
                "overallSuccessRate": overall_success_rate,
                "overallFailureRate": overall_failure_rate,
            },
            "tools": tool_list,
            "topUsed": top_used,
            "mostReliable": reliable_tools,
            "highestLatency": high_latency_tools,
        }
    except Exception as e:
        logger.error(f"Failed to retrieve tools dashboard for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve tools dashboard: {str(e)}"
        )

