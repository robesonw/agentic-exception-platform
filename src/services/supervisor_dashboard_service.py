"""
Supervisor Dashboard Service for Phase 3.

Aggregates data from multiple sources to provide supervisor overview:
- Exception counts by severity and status
- Escalations
- Pending approvals
- Policy violations
- Optimization suggestions

Matches specification from phase3-mvp-issues.md P3-15.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.models.exception_record import ResolutionStatus, Severity
from src.optimization.engine import OptimizationEngine
from src.orchestrator.store import get_exception_store

logger = logging.getLogger(__name__)


class SupervisorDashboardService:
    """
    Service for aggregating supervisor dashboard data.
    
    Phase 3 MVP: Simple aggregation from existing stores.
    No heavy analytics store required yet.
    """

    def __init__(
        self,
        exception_store=None,
        optimization_engine: Optional[OptimizationEngine] = None,
    ):
        """
        Initialize supervisor dashboard service.
        
        Args:
            exception_store: Exception store instance (default: get from singleton)
            optimization_engine: Optional optimization engine for suggestions
        """
        self.exception_store = exception_store or get_exception_store()
        self.optimization_engine = optimization_engine

    def get_overview(
        self,
        tenant_id: str,
        domain: Optional[str] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Get supervisor overview dashboard data.
        
        Args:
            tenant_id: Tenant identifier
            domain: Optional domain filter
            from_ts: Optional start timestamp
            to_ts: Optional end timestamp
            
        Returns:
            Dictionary with:
            {
                "counts": {
                    "by_severity": {severity: count},
                    "by_status": {status: count},
                },
                "escalations_count": int,
                "pending_approvals_count": int,
                "top_policy_violations": list[dict],
                "optimization_suggestions_summary": dict,
            }
        """
        # Get all exceptions for tenant
        tenant_exceptions = self.exception_store.get_tenant_exceptions(tenant_id)
        
        # Filter by domain if provided
        if domain:
            tenant_exceptions = [
                (exc, result)
                for exc, result in tenant_exceptions
                if exc.normalized_context and exc.normalized_context.get("domain") == domain
            ]
        
        # Filter by timestamp if provided
        if from_ts or to_ts:
            filtered = []
            for exc, result in tenant_exceptions:
                exc_ts = exc.timestamp
                if from_ts and exc_ts < from_ts:
                    continue
                if to_ts and exc_ts > to_ts:
                    continue
                filtered.append((exc, result))
            tenant_exceptions = filtered
        
        # Aggregate counts by severity
        counts_by_severity: dict[str, int] = {
            "LOW": 0,
            "MEDIUM": 0,
            "HIGH": 0,
            "CRITICAL": 0,
        }
        
        # Aggregate counts by status
        counts_by_status: dict[str, int] = {
            "OPEN": 0,
            "IN_PROGRESS": 0,
            "RESOLVED": 0,
            "ESCALATED": 0,
            "PENDING_APPROVAL": 0,
        }
        
        escalations_count = 0
        pending_approvals_count = 0
        
        for exception, _ in tenant_exceptions:
            # Count by severity
            if exception.severity:
                severity_str = exception.severity.value if hasattr(exception.severity, "value") else str(exception.severity)
                counts_by_severity[severity_str] = counts_by_severity.get(severity_str, 0) + 1
            
            # Count by status
            status_str = exception.resolution_status.value if hasattr(exception.resolution_status, "value") else str(exception.resolution_status)
            counts_by_status[status_str] = counts_by_status.get(status_str, 0) + 1
            
            # Count escalations
            if exception.resolution_status == ResolutionStatus.ESCALATED:
                escalations_count += 1
            
            # Count pending approvals
            if exception.resolution_status == ResolutionStatus.PENDING_APPROVAL:
                pending_approvals_count += 1
        
        # Get top policy violations from audit logs
        top_policy_violations = self._get_top_policy_violations(tenant_id, domain, limit=10)
        
        # Get optimization suggestions summary
        optimization_summary = self._get_optimization_suggestions_summary(tenant_id, domain)
        
        return {
            "counts": {
                "by_severity": counts_by_severity,
                "by_status": counts_by_status,
            },
            "escalations_count": escalations_count,
            "pending_approvals_count": pending_approvals_count,
            "top_policy_violations": top_policy_violations,
            "optimization_suggestions_summary": optimization_summary,
        }

    def get_escalations(
        self,
        tenant_id: str,
        domain: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get list of escalated exceptions with key metadata.
        
        Args:
            tenant_id: Tenant identifier
            domain: Optional domain filter
            limit: Maximum number of escalations to return
            
        Returns:
            List of escalation dictionaries with:
            {
                "exception_id": str,
                "tenant_id": str,
                "domain": str,
                "exception_type": str,
                "severity": str,
                "timestamp": str,
                "escalation_reason": str,
            }
        """
        tenant_exceptions = self.exception_store.get_tenant_exceptions(tenant_id)
        
        escalations = []
        for exception, pipeline_result in tenant_exceptions:
            # Filter by domain if provided
            if domain:
                exc_domain = exception.normalized_context.get("domain") if exception.normalized_context else None
                if exc_domain != domain:
                    continue
            
            # Only include escalated exceptions
            if exception.resolution_status != ResolutionStatus.ESCALATED:
                continue
            
            # Extract escalation reason from pipeline result or evidence
            escalation_reason = "Unknown"
            if pipeline_result:
                stages = pipeline_result.get("stages", {})
                # Check supervisor or policy stages for escalation reason
                if "supervisor" in stages:
                    supervisor_decision = stages["supervisor"]
                    if isinstance(supervisor_decision, dict):
                        escalation_reason = supervisor_decision.get("escalation_reason", "Unknown")
                elif "policy" in stages:
                    policy_decision = stages["policy"]
                    if isinstance(policy_decision, dict):
                        escalation_reason = policy_decision.get("decision", "Policy violation")
            
            escalations.append({
                "exception_id": exception.exception_id,
                "tenant_id": exception.tenant_id,
                "domain": exception.normalized_context.get("domain") if exception.normalized_context else None,
                "exception_type": exception.exception_type,
                "severity": exception.severity.value if exception.severity else None,
                "timestamp": exception.timestamp.isoformat() if exception.timestamp else None,
                "escalation_reason": escalation_reason,
            })
        
        # Sort by timestamp (most recent first)
        escalations.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Limit results
        return escalations[:limit]

    def get_policy_violations(
        self,
        tenant_id: str,
        domain: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get recent policy violation events.
        
        Args:
            tenant_id: Tenant identifier
            domain: Optional domain filter
            limit: Maximum number of violations to return
            
        Returns:
            List of policy violation dictionaries with:
            {
                "exception_id": str,
                "tenant_id": str,
                "domain": str,
                "timestamp": str,
                "violation_type": str,
                "violated_rule": str,
                "decision": str,
            }
        """
        # Read from audit logs to find policy violations
        violations = []
        
        # Use instance audit_dir if set, otherwise default
        audit_dir = getattr(self, "audit_dir", None) or Path("./runtime/audit")
        if not audit_dir.exists():
            return violations
        
        # Scan all audit log files
        for audit_file in audit_dir.glob("*.jsonl"):
            try:
                with open(audit_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            entry = json.loads(line)
                            
                            # Filter by tenant
                            if entry.get("tenant_id") != tenant_id:
                                continue
                            
                            # Filter by domain if provided
                            if domain:
                                entry_domain = entry.get("domain")
                                if entry_domain != domain:
                                    continue
                            
                            # Look for policy agent decisions with BLOCK or REQUIRE_APPROVAL
                            # Check event_type and agent name
                            event_type = entry.get("event_type", "")
                            data = entry.get("data", {})
                            if isinstance(data, dict):
                                agent_name = data.get("agent_name", "")
                                decision_data = data.get("output", {})
                            else:
                                agent_name = ""
                                decision_data = {}
                            
                            if event_type == "agent_event" and agent_name == "PolicyAgent":
                                # Extract decision from output
                                if isinstance(decision_data, dict):
                                    decision = decision_data.get("decision", "")
                                else:
                                    decision = str(decision_data)
                                
                                if decision in ["BLOCK", "REQUIRE_APPROVAL"]:
                                    # Extract violation details
                                    violated_rules = []
                                    if isinstance(decision_data, dict):
                                        evidence = decision_data.get("evidence", [])
                                        for ev in evidence:
                                            if isinstance(ev, str) and "violated" in ev.lower():
                                                violated_rules.append(ev)
                                    
                                    # Extract exception_id from data if available
                                    exception_id = "unknown"
                                    if isinstance(data, dict):
                                        input_data = data.get("input", {})
                                        if isinstance(input_data, dict):
                                            exception = input_data.get("exception", {})
                                            if isinstance(exception, dict):
                                                exception_id = exception.get("exception_id", "unknown")
                                    
                                    violations.append({
                                        "exception_id": exception_id,
                                        "tenant_id": entry.get("tenant_id", tenant_id),
                                        "domain": domain,  # Use provided domain filter
                                        "timestamp": entry.get("timestamp", datetime.now(timezone.utc).isoformat()),
                                        "violation_type": decision,
                                        "violated_rule": violated_rules[0] if violated_rules else "Unknown rule",
                                        "decision": decision,
                                    })
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                logger.warning(f"Failed to read audit file {audit_file}: {e}")
                continue
        
        # Sort by timestamp (most recent first)
        violations.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Limit results
        return violations[:limit]

    def _get_top_policy_violations(
        self,
        tenant_id: str,
        domain: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get top policy violations (simplified version of get_policy_violations).
        
        Args:
            tenant_id: Tenant identifier
            domain: Optional domain filter
            limit: Maximum number of violations to return
            
        Returns:
            List of top policy violations
        """
        return self.get_policy_violations(tenant_id, domain, limit=limit)

    def _get_optimization_suggestions_summary(
        self,
        tenant_id: str,
        domain: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Get summary of optimization suggestions.
        
        Args:
            tenant_id: Tenant identifier
            domain: Optional domain filter
            
        Returns:
            Dictionary with:
            {
                "total_suggestions": int,
                "by_category": {category: count},
                "high_priority_count": int,
            }
        """
        if not self.optimization_engine:
            return {
                "total_suggestions": 0,
                "by_category": {},
                "high_priority_count": 0,
            }
        
        try:
            # Get recommendations from optimization engine
            recommendations = self.optimization_engine.generate_recommendations(tenant_id, domain or "default")
            
            # Aggregate by category
            by_category: dict[str, int] = {}
            high_priority_count = 0
            
            for rec in recommendations:
                # Handle both dict and OptimizationRecommendation objects
                if isinstance(rec, dict):
                    category = rec.get("category", "unknown")
                    confidence = rec.get("confidence", 0.0)
                    impact = rec.get("impact_estimate", "")
                else:
                    category = rec.category
                    confidence = rec.confidence
                    impact = rec.impact_estimate
                
                by_category[category] = by_category.get(category, 0) + 1
                
                # Count high priority (high confidence or high impact)
                if confidence > 0.7 or "high" in str(impact).lower():
                    high_priority_count += 1
            
            return {
                "total_suggestions": len(recommendations),
                "by_category": by_category,
                "high_priority_count": high_priority_count,
            }
        except Exception as e:
            logger.warning(f"Failed to get optimization suggestions: {e}")
            return {
                "total_suggestions": 0,
                "by_category": {},
                "high_priority_count": 0,
            }


# Singleton instance
_supervisor_dashboard_service: Optional[SupervisorDashboardService] = None


def get_supervisor_dashboard_service() -> SupervisorDashboardService:
    """
    Get the global supervisor dashboard service instance.
    
    Returns:
        SupervisorDashboardService instance
    """
    global _supervisor_dashboard_service
    if _supervisor_dashboard_service is None:
        _supervisor_dashboard_service = SupervisorDashboardService()
    return _supervisor_dashboard_service

