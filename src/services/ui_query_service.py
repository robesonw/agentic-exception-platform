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

    async def search_exceptions(
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
        
        Phase 6: Now reads from PostgreSQL instead of in-memory store.
        
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
        # Phase 6: Read from PostgreSQL
        try:
            from src.infrastructure.db.session import get_db_session_context
            from src.repository.exceptions_repository import ExceptionRepository
            from src.repository.dto import ExceptionFilter
            from src.infrastructure.db.models import ExceptionStatus, ExceptionSeverity
            
            async with get_db_session_context() as session:
                repo = ExceptionRepository(session)
                
                # Build filter
                filters = ExceptionFilter()
                if domain:
                    filters.domain = domain
                if status:
                    # Map ResolutionStatus to ExceptionStatus
                    status_map = {
                        ResolutionStatus.OPEN: ExceptionStatus.OPEN,
                        ResolutionStatus.IN_PROGRESS: ExceptionStatus.ANALYZING,
                        ResolutionStatus.RESOLVED: ExceptionStatus.RESOLVED,
                        ResolutionStatus.ESCALATED: ExceptionStatus.ESCALATED,
                    }
                    filters.status = status_map.get(status)
                if severity:
                    # Map Severity to ExceptionSeverity
                    severity_map = {
                        Severity.LOW: ExceptionSeverity.LOW,
                        Severity.MEDIUM: ExceptionSeverity.MEDIUM,
                        Severity.HIGH: ExceptionSeverity.HIGH,
                        Severity.CRITICAL: ExceptionSeverity.CRITICAL,
                    }
                    filters.severity = severity_map.get(severity)
                if from_ts:
                    filters.created_from = from_ts
                if to_ts:
                    filters.created_to = to_ts
                
                # List exceptions from PostgreSQL
                result = await repo.list_exceptions(
                    tenant_id=tenant_id,
                    filters=filters,
                    page=page,
                    page_size=page_size,
                )
                
                # Convert database exceptions to ExceptionRecord format
                items = []
                for db_exc in result.items:
                    # Map to ExceptionRecord (similar to ui_status.py)
                    severity_map = {
                        "low": Severity.LOW,
                        "medium": Severity.MEDIUM,
                        "high": Severity.HIGH,
                        "critical": Severity.CRITICAL,
                    }
                    severity_enum = severity_map.get(
                        db_exc.severity.value if hasattr(db_exc.severity, 'value') else str(db_exc.severity).lower(),
                        Severity.MEDIUM
                    )
                    
                    status_map = {
                        "open": ResolutionStatus.OPEN,
                        "analyzing": ResolutionStatus.IN_PROGRESS,
                        "resolved": ResolutionStatus.RESOLVED,
                        "escalated": ResolutionStatus.ESCALATED,
                    }
                    resolution_status = status_map.get(
                        db_exc.status.value if hasattr(db_exc.status, 'value') else str(db_exc.status).lower(),
                        ResolutionStatus.OPEN
                    )
                    
                    # Build normalized context
                    normalized_context = {"domain": db_exc.domain}
                    if db_exc.entity:
                        normalized_context["entity"] = db_exc.entity
                    
                    # Create ExceptionRecord
                    exception = ExceptionRecord(
                        exception_id=db_exc.exception_id,
                        tenant_id=db_exc.tenant_id,
                        source_system=db_exc.source_system,
                        exception_type=db_exc.type,
                        severity=severity_enum,
                        timestamp=db_exc.created_at or datetime.now(timezone.utc),
                        raw_payload={},
                        normalized_context=normalized_context,
                        resolution_status=resolution_status,
                    )
                    
                    # Apply text search filter if provided
                    if search:
                        search_lower = search.lower()
                        matches = (
                            search_lower in (exception.exception_type or "").lower()
                            or search_lower in (exception.source_system or "").lower()
                        )
                        if not matches:
                            continue
                    
                    # Create minimal pipeline result
                    pipeline_result = {
                        "status": "COMPLETED" if resolution_status == ResolutionStatus.RESOLVED else "IN_PROGRESS",
                        "stages": {},
                    }
                    
                    items.append({
                        "exception": exception.model_dump(),
                        "pipeline_result": pipeline_result,
                    })
                
                # Recalculate total if search filter was applied
                if search:
                    total = len(items)
                    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
                else:
                    total = result.total
                    total_pages = result.total_pages
                
                return {
                    "items": items,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                }
        except Exception as e:
            logger.warning(f"Error reading from PostgreSQL, falling back to in-memory store: {e}")
            # Fallback to in-memory store
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

    async def get_exception_detail(
        self, tenant_id: str, exception_id: str
    ) -> Optional[dict[str, Any]]:
        """
        Get full exception detail with agent decisions.
        
        Phase 6: Now reads from PostgreSQL instead of in-memory store.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            
        Returns:
            Dictionary with exception record and agent decisions, or None if not found
        """
        # Phase 6: Read from PostgreSQL
        try:
            from src.infrastructure.db.session import get_db_session_context
            from src.repository.exceptions_repository import ExceptionRepository
            from src.repository.exception_events_repository import ExceptionEventRepository
            from src.models.exception_record import Severity, ResolutionStatus
            
            async with get_db_session_context() as session:
                repo = ExceptionRepository(session)
                db_exception = await repo.get_exception(tenant_id, exception_id)
                
                if db_exception is None:
                    return None
                
                # Map to ExceptionRecord (same as in exceptions.py)
                severity_map = {
                    "low": Severity.LOW,
                    "medium": Severity.MEDIUM,
                    "high": Severity.HIGH,
                    "critical": Severity.CRITICAL,
                }
                severity_enum = severity_map.get(
                    db_exception.severity.value if hasattr(db_exception.severity, 'value') else str(db_exception.severity).lower(),
                    Severity.MEDIUM
                )
                
                status_map = {
                    "open": ResolutionStatus.OPEN,
                    "analyzing": ResolutionStatus.IN_PROGRESS,
                    "resolved": ResolutionStatus.RESOLVED,
                    "escalated": ResolutionStatus.ESCALATED,
                }
                resolution_status = status_map.get(
                    db_exception.status.value if hasattr(db_exception.status, 'value') else str(db_exception.status).lower(),
                    ResolutionStatus.OPEN
                )
                
                normalized_context = {"domain": db_exception.domain}
                if db_exception.entity:
                    normalized_context["entity"] = db_exception.entity
                
                exception = ExceptionRecord(
                    exception_id=db_exception.exception_id,
                    tenant_id=db_exception.tenant_id,
                    source_system=db_exception.source_system,
                    exception_type=db_exception.type,
                    severity=severity_enum,
                    timestamp=db_exception.created_at or datetime.now(timezone.utc),
                    raw_payload={},
                    normalized_context=normalized_context,
                    resolution_status=resolution_status,
                )
                
                # Get events for pipeline result
                event_repo = ExceptionEventRepository(session)
                events = await event_repo.get_events_for_exception(tenant_id, exception_id)
                
                # Build pipeline result from events
                pipeline_result = {
                    "status": "COMPLETED" if resolution_status == ResolutionStatus.RESOLVED else "IN_PROGRESS",
                    "stages": {},
                    "evidence": [],
                }
                
                agent_decisions = {}
                for event in events:
                    if event.event_type.endswith("Completed"):
                        stage_name = event.event_type.replace("Completed", "").lower()
                        pipeline_result["stages"][stage_name] = {
                            "status": "completed",
                            "timestamp": event.created_at.isoformat(),
                        }
                        agent_decisions[stage_name] = event.payload
                
                return {
                    "exception": exception.model_dump(),
                    "agent_decisions": agent_decisions,
                    "pipeline_result": pipeline_result,
                }
        except Exception as e:
            logger.warning(f"Error reading from PostgreSQL, falling back to in-memory store: {e}")
            # Fallback to in-memory store
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

    async def get_exception_evidence(
        self, tenant_id: str, exception_id: str
    ) -> Optional[dict[str, Any]]:
        """
        Get evidence chains for an exception (RAG results, tool outputs).
        
        Phase 6: Now reads from PostgreSQL instead of in-memory store.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            
        Returns:
            Dictionary with evidence chains, or None if not found
        """
        # Phase 6: Read from PostgreSQL
        try:
            from src.infrastructure.db.session import get_db_session_context
            from src.repository.exceptions_repository import ExceptionRepository
            from src.repository.exception_events_repository import ExceptionEventRepository
            
            async with get_db_session_context() as session:
                repo = ExceptionRepository(session)
                db_exception = await repo.get_exception(tenant_id, exception_id)
                
                if db_exception is None:
                    return None
                
                # Get events for evidence
                event_repo = ExceptionEventRepository(session)
                events = await event_repo.get_events_for_exception(tenant_id, exception_id)
                
                # Build evidence from events
                evidence = {
                    "rag_results": [],
                    "tool_outputs": [],
                    "agent_evidence": [],
                }
                
                for event in events:
                    payload = event.payload if isinstance(event.payload, dict) else {}
                    
                    # Extract agent evidence from events
                    if "evidence" in payload:
                        evidence["agent_evidence"].append({
                            "stage": event.event_type,
                            "evidence": payload["evidence"],
                        })
                    
                    # Extract tool outputs
                    if "tool_output" in payload or "tool_result" in payload:
                        tool_output = payload.get("tool_output") or payload.get("tool_result")
                        evidence["tool_outputs"].append(tool_output)
                    
                    # Extract RAG results
                    if "rag_results" in payload or "similar_exceptions" in payload:
                        rag_results = payload.get("rag_results") or payload.get("similar_exceptions")
                        if isinstance(rag_results, list):
                            evidence["rag_results"].extend(rag_results)
                
                return evidence
        except Exception as e:
            logger.warning(f"Error reading from PostgreSQL, falling back to in-memory store: {e}")
            # Fallback to in-memory store
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

    async def get_exception_audit(
        self, tenant_id: str, exception_id: str
    ) -> list[dict[str, Any]]:
        """
        Get audit events related to an exception.
        
        Phase 6: Now reads from PostgreSQL exception_event table instead of JSONL files.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            
        Returns:
            List of audit event dictionaries
        """
        # Phase 6: Read from PostgreSQL exception_event table
        try:
            from src.infrastructure.db.session import get_db_session_context
            from src.repository.exception_events_repository import ExceptionEventRepository
            
            async with get_db_session_context() as session:
                event_repo = ExceptionEventRepository(session)
                events = await event_repo.get_events_for_exception(tenant_id, exception_id)
                
                # Convert events to audit event format
                audit_events = []
                for event in events:
                    actor_type = event.actor_type.value if hasattr(event.actor_type, 'value') else str(event.actor_type)
                    audit_events.append({
                        "timestamp": event.created_at.isoformat() if event.created_at else None,
                        "tenant_id": event.tenant_id,
                        "exception_id": event.exception_id,
                        "event_type": event.event_type,
                        "actor_type": actor_type,
                        "actor_id": event.actor_id,
                        "data": {
                            "event_type": event.event_type,
                            "payload": event.payload,
                        },
                    })
                
                # Sort by timestamp (oldest first)
                audit_events.sort(key=lambda x: x.get("timestamp", ""))
                
                return audit_events
        except Exception as e:
            logger.warning(f"Error reading from PostgreSQL, falling back to JSONL files: {e}")
            # Fallback to JSONL files
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

