"""
UI Query Service for Operator UI Backend APIs.

Provides helper functions for querying exceptions, evidence, and audit history.
Reuses existing persistence from exception store, audit trail, and RAG memory.

Matches specification from phase3-mvp-issues.md P3-12.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.orchestrator.store import ExceptionStore, get_exception_store

logger = logging.getLogger(__name__)


class UIQueryServiceError(Exception):
    """Raised when UI query operations fail."""

    pass


class UIQueryService:
    """
    Service for querying exceptions, evidence, and audit history for operator UI.
    
    Responsibilities:
    - Search and filter exceptions
    - Retrieve exception details with agent decisions
    - Retrieve evidence chains (RAG results, tool outputs)
    - Retrieve audit events for exceptions
    """

    def __init__(self, exception_store: Optional[ExceptionStore] = None):
        """
        Initialize UI Query Service.
        
        Args:
            exception_store: Optional ExceptionStore instance (defaults to global singleton)
        """
        self.exception_store = exception_store or get_exception_store()
        self.audit_dir = Path("./runtime/audit")

    def search_exceptions(
        self,
        tenant_id: str,
        domain: Optional[str] = None,
        status: Optional[ResolutionStatus] = None,
        severity: Optional[Severity] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """
        Search and filter exceptions with pagination.
        
        Args:
            tenant_id: Tenant identifier
            domain: Optional domain filter
            status: Optional resolution status filter
            severity: Optional severity filter
            from_ts: Optional start timestamp filter
            to_ts: Optional end timestamp filter
            search: Optional text search query
            page: Page number (1-indexed)
            page_size: Number of results per page
            
        Returns:
            Dictionary with:
            {
                "items": list[dict],  # Exception records with pipeline results
                "total": int,  # Total count matching filters
                "page": int,  # Current page
                "page_size": int,  # Page size
                "total_pages": int,  # Total pages
            }
        """
        # Get all exceptions for tenant
        all_exceptions = self.exception_store.get_tenant_exceptions(tenant_id)
        
        # Apply filters
        filtered = []
        for exception, pipeline_result in all_exceptions:
            # Domain filter (domain may be in normalized_context or not present)
            if domain:
                # Check normalized_context for domain, or skip filter if not available
                exception_domain = exception.normalized_context.get("domain") if hasattr(exception, "normalized_context") else None
                if exception_domain and exception_domain != domain:
                    continue
                # If domain filter is specified but exception has no domain, skip it
                # (This allows domain filtering to work when domain is present)
                if exception_domain is None:
                    continue
            
            # Status filter
            if status and exception.resolution_status != status:
                continue
            
            # Severity filter
            if severity and exception.severity != severity:
                continue
            
            # Timestamp filters
            if from_ts and exception.timestamp < from_ts:
                continue
            if to_ts and exception.timestamp > to_ts:
                continue
            
            # Text search (simple substring match in exception_type, source_system, raw_payload)
            if search:
                search_lower = search.lower()
                matches = (
                    search_lower in (exception.exception_type or "").lower()
                    or search_lower in (exception.source_system or "").lower()
                    or search_lower in str(exception.raw_payload).lower()
                )
                if not matches:
                    continue
            
            filtered.append((exception, pipeline_result))
        
        # Sort by timestamp (newest first)
        filtered.sort(key=lambda x: x[0].timestamp, reverse=True)
        
        # Pagination
        total = len(filtered)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated = filtered[start_idx:end_idx]
        
        # Serialize results
        items = []
        for exception, pipeline_result in paginated:
            item = {
                "exception": exception.model_dump(),
                "pipeline_result": pipeline_result,
            }
            items.append(item)
        
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def get_exception_detail(
        self, tenant_id: str, exception_id: str
    ) -> Optional[dict[str, Any]]:
        """
        Get full exception detail with agent decisions.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            
        Returns:
            Dictionary with exception record and agent decisions, or None if not found
        """
        result = self.exception_store.get_exception(tenant_id, exception_id)
        if not result:
            return None
        
        exception, pipeline_result = result
        
        # Extract agent decisions from pipeline result
        agent_decisions = {}
        if "stages" in pipeline_result:
            stages = pipeline_result["stages"]
            for stage_name, decision in stages.items():
                if hasattr(decision, "model_dump"):
                    agent_decisions[stage_name] = decision.model_dump()
                elif isinstance(decision, dict):
                    agent_decisions[stage_name] = decision
                else:
                    agent_decisions[stage_name] = str(decision)
        
        return {
            "exception": exception.model_dump(),
            "agent_decisions": agent_decisions,
            "pipeline_result": pipeline_result,
        }

    def get_exception_evidence(
        self, tenant_id: str, exception_id: str
    ) -> Optional[dict[str, Any]]:
        """
        Get evidence chains for an exception (RAG results, tool outputs).
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            
        Returns:
            Dictionary with evidence chains, or None if not found
        """
        result = self.exception_store.get_exception(tenant_id, exception_id)
        if not result:
            return None
        
        exception, pipeline_result = result
        
        # Extract evidence from pipeline result and agent decisions
        evidence = {
            "rag_results": [],
            "tool_outputs": [],
            "agent_evidence": [],
        }
        
        # Extract RAG results from agent decisions
        if "stages" in pipeline_result:
            stages = pipeline_result["stages"]
            for stage_name, decision in stages.items():
                if hasattr(decision, "evidence"):
                    evidence["agent_evidence"].append({
                        "stage": stage_name,
                        "evidence": decision.evidence,
                    })
                elif isinstance(decision, dict) and "evidence" in decision:
                    evidence["agent_evidence"].append({
                        "stage": stage_name,
                        "evidence": decision["evidence"],
                    })
        
        # Extract tool outputs from pipeline result
        if "tool_outputs" in pipeline_result:
            evidence["tool_outputs"] = pipeline_result["tool_outputs"]
        
        # Extract RAG results from pipeline result
        if "rag_results" in pipeline_result:
            evidence["rag_results"] = pipeline_result["rag_results"]
        
        return evidence

    def get_exception_audit(
        self, tenant_id: str, exception_id: str
    ) -> list[dict[str, Any]]:
        """
        Get audit events related to an exception.
        
        Reads from audit JSONL files and filters by exception_id.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            
        Returns:
            List of audit event dictionaries
        """
        audit_events = []
        
        # Scan all audit log files
        if not self.audit_dir.exists():
            return audit_events
        
        for audit_file in self.audit_dir.glob("*.jsonl"):
            try:
                with open(audit_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        
                        try:
                            event = json.loads(line)
                            
                            # Filter by tenant_id and exception_id
                            if event.get("tenant_id") != tenant_id:
                                continue
                            
                            # Check if event is related to this exception
                            data = event.get("data", {})
                            is_related = False
                            
                            # Check in input data
                            if isinstance(data.get("input"), dict):
                                input_data = data["input"]
                                if isinstance(input_data.get("exception"), dict):
                                    exc_dict = input_data["exception"]
                                    if exc_dict.get("exception_id") == exception_id:
                                        is_related = True
                                elif hasattr(input_data.get("exception"), "exception_id"):
                                    if input_data["exception"].exception_id == exception_id:
                                        is_related = True
                            
                            # Check in output data
                            if isinstance(data.get("output"), dict):
                                output_data = data["output"]
                                if "exception_id" in str(output_data):
                                    is_related = True
                            
                            # Check in tool call data
                            if "tool_name" in data and "exception_id" in str(data):
                                is_related = True
                            
                            if is_related:
                                audit_events.append(event)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse audit log line in {audit_file}")
                            continue
            except Exception as e:
                logger.warning(f"Failed to read audit file {audit_file}: {e}")
                continue
        
        # Sort by timestamp (oldest first)
        audit_events.sort(key=lambda x: x.get("timestamp", ""))
        
        return audit_events


# Global singleton instance
_ui_query_service: Optional[UIQueryService] = None


def get_ui_query_service() -> UIQueryService:
    """
    Get the global UI query service instance.
    
    Returns:
        UIQueryService instance
    """
    global _ui_query_service
    if _ui_query_service is None:
        _ui_query_service = UIQueryService()
    return _ui_query_service

