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
                
                # Get events from event_log table (EventStore) using TraceService
                from src.infrastructure.repositories.event_store_repository import EventStoreRepository
                from src.services.trace_service import TraceService
                
                event_store_repo = EventStoreRepository(session)
                trace_service = TraceService(event_store_repo)
                
                # Get all events for this exception (trace)
                trace_result = await trace_service.get_trace_for_exception(
                    exception_id=exception_id,
                    tenant_id=tenant_id,
                    page=1,
                    page_size=1000,  # Get all events for pipeline result
                )
                
                # Build pipeline result from events
                pipeline_result = {
                    "status": "COMPLETED" if resolution_status == ResolutionStatus.RESOLVED else "IN_PROGRESS",
                    "stages": {},
                    "evidence": [],
                }
                
                agent_decisions = {}
                for event_log in trace_result.items:
                    # Handle JSONB payload
                    payload = getattr(event_log, 'payload', None)
                    if payload is None:
                        payload = {}
                    elif not isinstance(payload, dict):
                        try:
                            import json
                            if isinstance(payload, str):
                                payload = json.loads(payload)
                            else:
                                payload = {}
                        except (json.JSONDecodeError, TypeError, ValueError):
                            payload = {}
                    
                    # Extract agent decisions from Completed events
                    if event_log.event_type.endswith("Completed"):
                        stage_name = event_log.event_type.replace("Completed", "").lower()
                        pipeline_result["stages"][stage_name] = {
                            "status": "completed",
                            "timestamp": event_log.timestamp.isoformat() if event_log.timestamp else None,
                        }
                        agent_decisions[stage_name] = payload
                
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
            
            async with get_db_session_context() as session:
                repo = ExceptionRepository(session)
                db_exception = await repo.get_exception(tenant_id, exception_id)
                
                if db_exception is None:
                    return None
                
                # Get events from event_log table (EventStore) using TraceService
                from src.infrastructure.repositories.event_store_repository import EventStoreRepository
                from src.services.trace_service import TraceService
                
                event_store_repo = EventStoreRepository(session)
                trace_service = TraceService(event_store_repo)
                
                # Get all events for this exception (trace)
                trace_result = await trace_service.get_trace_for_exception(
                    exception_id=exception_id,
                    tenant_id=tenant_id,
                    page=1,
                    page_size=1000,  # Get all events for evidence extraction
                )
                
                logger.info(
                    f"Retrieved {trace_result.total} events for evidence extraction "
                    f"(exception_id={exception_id}, tenant_id={tenant_id}, items={len(trace_result.items)})"
                )
                
                # Build evidence from events
                evidence = {
                    "rag_results": [],
                    "tool_outputs": [],
                    "agent_evidence": [],
                }
                
                if trace_result.total == 0 or len(trace_result.items) == 0:
                    logger.warning(f"No events found for exception {exception_id} in EventStore")
                    return evidence
                
                for event_log in trace_result.items:
                    logger.debug(
                        f"Processing event {event_log.event_type} for evidence extraction "
                        f"(event_id={event_log.event_id})"
                    )
                    # Handle JSONB payload - SQLAlchemy should return dict directly for JSONB
                    payload = getattr(event_log, 'payload', None)
                    if payload is None:
                        logger.debug(f"Event {event_log.event_id} has no payload")
                        continue
                    if not isinstance(payload, dict):
                        # Try to parse if it's a string
                        try:
                            import json
                            if isinstance(payload, str):
                                payload = json.loads(payload)
                            else:
                                logger.warning(f"Event {event_log.event_id} has non-dict payload: {type(payload)}")
                                continue
                        except (json.JSONDecodeError, TypeError, ValueError) as e:
                            logger.warning(f"Failed to parse payload for event {event_log.event_id}: {e}")
                            continue
                    
                    # Extract agent evidence from events
                    # TriageCompleted, PolicyEvaluationCompleted, etc. have evidence directly in payload
                    if "evidence" in payload:
                        evidence_list = payload["evidence"]
                        if isinstance(evidence_list, list) and evidence_list:
                            evidence["agent_evidence"].append({
                                "stage": event_log.event_type,
                                "evidence": evidence_list,
                            })
                            logger.debug(f"Added evidence from {event_log.event_type}: {len(evidence_list)} items")
                        elif evidence_list:  # Single item, not a list
                            evidence["agent_evidence"].append({
                                "stage": event_log.event_type,
                                "evidence": [evidence_list],
                            })
                            logger.debug(f"Added evidence from {event_log.event_type}: 1 item")
                    
                    # Also check for triage_result.evidence structure (nested)
                    if "triage_result" in payload and isinstance(payload["triage_result"], dict):
                        triage_result = payload["triage_result"]
                        if "evidence" in triage_result:
                            evidence_list = triage_result["evidence"] if isinstance(triage_result["evidence"], list) else [triage_result["evidence"]]
                            if evidence_list:  # Only add if not empty
                                evidence["agent_evidence"].append({
                                    "stage": "TriageCompleted",
                                    "evidence": evidence_list,
                                })
                    
                    # Also check for decision.evidence structure (nested)
                    if "decision" in payload:
                        if isinstance(payload["decision"], dict) and "evidence" in payload["decision"]:
                            decision = payload["decision"]
                            evidence_list = decision["evidence"] if isinstance(decision["evidence"], list) else [decision["evidence"]]
                            if evidence_list:  # Only add if not empty
                                evidence["agent_evidence"].append({
                                    "stage": event_log.event_type,
                                    "evidence": evidence_list,
                                })
                    
                    # Extract tool outputs
                    if "tool_output" in payload or "tool_result" in payload:
                        tool_output = payload.get("tool_output") or payload.get("tool_result")
                        if tool_output:  # Only add if not empty
                            evidence["tool_outputs"].append(tool_output)
                    
                    # Extract RAG results
                    if "rag_results" in payload or "similar_exceptions" in payload:
                        rag_results = payload.get("rag_results") or payload.get("similar_exceptions")
                        if isinstance(rag_results, list) and rag_results:
                            evidence["rag_results"].extend(rag_results)
                
                return evidence
        except Exception as e:
            logger.error(f"Error reading evidence from EventStore: {e}", exc_info=True)
            # Return empty evidence instead of falling back to in-memory store
            return {
                "rag_results": [],
                "tool_outputs": [],
                "agent_evidence": [],
            }
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
        # Phase 9: Read from PostgreSQL event_log table (EventStore) using TraceService
        try:
            from src.infrastructure.db.session import get_db_session_context
            from src.infrastructure.repositories.event_store_repository import EventStoreRepository
            from src.services.trace_service import TraceService
            
            async with get_db_session_context() as session:
                event_store_repo = EventStoreRepository(session)
                trace_service = TraceService(event_store_repo)
                
                # Get all events for this exception (trace)
                trace_result = await trace_service.get_trace_for_exception(
                    exception_id=exception_id,
                    tenant_id=tenant_id,
                    page=1,
                    page_size=1000,  # Get all events for audit trail
                )
                
                # Convert events to audit event format
                audit_events = []
                for event_log in trace_result.items:
                    # Extract actor info from metadata if available
                    metadata = event_log.event_metadata if isinstance(event_log.event_metadata, dict) else {}
                    actor_type = metadata.get("actor_type", "system")
                    actor_id = metadata.get("actor_id", "system")
                    
                    audit_events.append({
                        "timestamp": event_log.timestamp.isoformat() if event_log.timestamp else None,
                        "tenant_id": event_log.tenant_id,
                        "exception_id": event_log.exception_id,
                        "event_type": event_log.event_type,
                        "actor_type": actor_type,
                        "actor_id": actor_id,
                        "data": {
                            "event_type": event_log.event_type,
                            "payload": event_log.payload if isinstance(event_log.payload, dict) else {},
                            "metadata": metadata,
                        },
                    })
                
                # Sort by timestamp (oldest first)
                audit_events.sort(key=lambda x: x.get("timestamp", ""))
                
                return audit_events
        except Exception as e:
            logger.error(f"Error reading audit from EventStore: {e}", exc_info=True)
            # Return empty audit instead of falling back to JSONL files
            return []
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
    
    async def get_exception_workflow_graph(
        self, tenant_id: str, exception_id: str
    ) -> Optional[dict[str, Any]]:
        """
        Get workflow graph data for an exception.
        
        Constructs workflow nodes and edges from pipeline events and playbook execution state.
        Fetches playbook definition from:
        1. Database playbook table (via exception.current_playbook_id)
        2. Event payload (PlaybookMatched event)
        3. Domain/tenant pack definitions (fallback)
        
        Derives step statuses from PlaybookStepCompleted events.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            
        Returns:
            Dictionary with workflow graph data, or None if not found
        """
        try:
            from src.infrastructure.db.session import get_db_session_context
            from src.repository.exceptions_repository import ExceptionRepository
            from src.infrastructure.repositories.event_store_repository import EventStoreRepository
            from src.services.trace_service import TraceService
            from sqlalchemy.orm import selectinload
            from sqlalchemy import select
            from src.infrastructure.db.models import Playbook, PlaybookStep
            
            async with get_db_session_context() as session:
                # First check if exception exists
                repo = ExceptionRepository(session)
                db_exception = await repo.get_exception(tenant_id, exception_id)
                
                if db_exception is None:
                    return None
                
                # Get all events for this exception
                event_store_repo = EventStoreRepository(session)
                trace_service = TraceService(event_store_repo)
                
                trace_result = await trace_service.get_trace_for_exception(
                    exception_id=exception_id,
                    tenant_id=tenant_id,
                    page=1,
                    page_size=1000,  # Get all events for workflow construction
                )
                
                # Define standard pipeline stages workflow
                stages = [
                    {"id": "stage:intake", "label": "Intake", "type": "agent", "kind": "stage"},
                    {"id": "stage:triage", "label": "Triage", "type": "agent", "kind": "stage"},
                    {"id": "stage:policy", "label": "Policy Check", "type": "agent", "kind": "stage"},
                    {"id": "stage:playbook", "label": "Playbook", "type": "agent", "kind": "stage"},
                    {"id": "stage:tool", "label": "Tool Execution", "type": "system", "kind": "stage"},
                    {"id": "stage:feedback", "label": "Feedback", "type": "agent", "kind": "stage"},
                ]
                
                # Build nodes with status from events
                nodes = []
                stage_status = {}
                current_stage = None
                
                # Collect PlaybookStepCompleted events for step status derivation
                step_completed_events = []
                
                # Process events to determine stage statuses
                for event_log in trace_result.items:
                    event_type = event_log.event_type
                    timestamp = event_log.timestamp
                    event_data = event_log.payload if isinstance(event_log.payload, dict) else {}
                    
                    # Map event types to stages
                    if event_type == "ExceptionNormalized":
                        stage_status["stage:intake"] = {
                            "status": "completed",
                            "completed_at": timestamp,
                            "meta": {"event_type": event_type, "actor": "IntakeAgent"}
                        }
                    elif event_type == "TriageCompleted":
                        stage_status["stage:triage"] = {
                            "status": "completed",
                            "completed_at": timestamp,
                            "meta": {"event_type": event_type, "actor": "TriageAgent", "data": event_data}
                        }
                    elif event_type == "PolicyEvaluationCompleted":
                        stage_status["stage:policy"] = {
                            "status": "completed",
                            "completed_at": timestamp,
                            "meta": {"event_type": event_type, "actor": "PolicyAgent", "data": event_data}
                        }
                    elif event_type == "PlaybookMatched":
                        stage_status["stage:playbook"] = {
                            "status": "in-progress",
                            "started_at": timestamp,
                            "meta": {"event_type": event_type, "actor": "PlaybookAgent", "data": event_data}
                        }
                    elif event_type == "PlaybookStepCompleted":
                        # Collect step completion events for later processing
                        step_completed_events.append({
                            "timestamp": timestamp,
                            "data": event_data
                        })
                        # Update playbook stage status
                        stage_status["stage:playbook"] = {
                            "status": "completed",
                            "completed_at": timestamp,
                            "meta": {"event_type": event_type, "actor": "PlaybookAgent", "data": event_data}
                        }
                    elif event_type == "ToolExecutionRequested":
                        stage_status["stage:tool"] = {
                            "status": "in-progress",
                            "started_at": timestamp,
                            "meta": {"event_type": event_type, "actor": "ToolWorker", "data": event_data}
                        }
                    elif event_type == "ToolExecutionCompleted":
                        stage_status["stage:tool"] = {
                            "status": "completed",
                            "completed_at": timestamp,
                            "meta": {"event_type": event_type, "actor": "ToolWorker", "data": event_data}
                        }
                    elif event_type == "FeedbackCaptured":
                        stage_status["stage:feedback"] = {
                            "status": "completed",
                            "completed_at": timestamp,
                            "meta": {"event_type": event_type, "actor": "FeedbackAgent", "data": event_data}
                        }
                
                # Build nodes based on stages and their status
                for stage in stages:
                    stage_id = stage["id"]
                    status_info = stage_status.get(stage_id, {})
                    
                    # Determine status - default to pending for stages that haven't been processed
                    status = status_info.get("status", "pending")
                    
                    # Set current stage to first in-progress or first pending stage
                    if current_stage is None and status in ["in-progress", "pending"]:
                        current_stage = stage_id.replace("stage:", "")
                    
                    node = {
                        "id": stage_id,
                        "type": stage["type"],
                        "kind": stage["kind"],
                        "label": stage["label"],
                        "status": status,
                        "started_at": status_info.get("started_at"),
                        "completed_at": status_info.get("completed_at"),
                        "meta": status_info.get("meta", {}),
                    }
                    nodes.append(node)
                
                # Try to extract playbook information from multiple sources
                playbook_id = None
                playbook_name = None
                playbook_steps = []
                playbook_nodes = []
                playbook_edges = []
                
                # Source 1: Check if exception has current_playbook_id (DB reference)
                if hasattr(db_exception, 'current_playbook_id') and db_exception.current_playbook_id:
                    try:
                        # Query the playbook with its steps
                        stmt = (
                            select(Playbook)
                            .options(selectinload(Playbook.steps))
                            .where(
                                Playbook.playbook_id == db_exception.current_playbook_id,
                                Playbook.tenant_id == tenant_id
                            )
                        )
                        result = await session.execute(stmt)
                        db_playbook = result.scalar_one_or_none()
                        
                        if db_playbook:
                            playbook_id = db_playbook.playbook_id
                            playbook_name = db_playbook.name
                            # Convert DB steps to list format
                            playbook_steps = [
                                {
                                    "name": step.name,
                                    "action_type": step.action_type,
                                    "step_order": step.step_order,
                                    "params": step.params or {},
                                    "step_id": step.step_id
                                }
                                for step in sorted(db_playbook.steps, key=lambda s: s.step_order)
                            ]
                            logger.debug(
                                f"Loaded playbook from DB: id={playbook_id}, name={playbook_name}, "
                                f"steps={len(playbook_steps)}"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to load playbook from DB: {e}")
                
                # Source 2: If no DB playbook, look in PlaybookMatched event payload
                if not playbook_steps:
                    for event_log in trace_result.items:
                        if event_log.event_type == "PlaybookMatched" and event_log.payload:
                            try:
                                event_data = event_log.payload if isinstance(event_log.payload, dict) else json.loads(event_log.payload)
                                if isinstance(event_data, dict):
                                    # Check different possible payload structures
                                    playbook_info = event_data.get("playbook") or event_data.get("output", {}).get("playbook")
                                    playbook_id = playbook_id or event_data.get("playbook_id") or event_data.get("output", {}).get("playbook_id")
                                    
                                    if isinstance(playbook_info, dict):
                                        playbook_steps = playbook_info.get("steps", [])
                                        playbook_id = playbook_id or playbook_info.get("playbook_id")
                                        playbook_name = playbook_info.get("name", playbook_info.get("playbook_name"))
                                        logger.debug(
                                            f"Loaded playbook from event: id={playbook_id}, name={playbook_name}, "
                                            f"steps={len(playbook_steps) if playbook_steps else 0}"
                                        )
                                        break
                            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                                logger.warning(f"Failed to parse PlaybookMatched payload: {e}")
                
                # Source 3: If still no playbook, try domain/tenant pack (future enhancement)
                # This would require the domain pack registry lookup
                # For now, we rely on DB and event sources
                
                # Build step completion status map
                completed_steps = {}  # step_order/index -> completion info
                for evt in step_completed_events:
                    evt_data = evt.get("data", {})
                    # Try to extract step identifier from event
                    step_order = evt_data.get("step_order") or evt_data.get("step_index") or evt_data.get("step")
                    step_name = evt_data.get("step_name") or evt_data.get("name")
                    
                    if step_order is not None:
                        completed_steps[step_order] = {
                            "status": "completed",
                            "completed_at": evt.get("timestamp"),
                            "result": evt_data.get("result") or evt_data.get("output"),
                        }
                    elif step_name:
                        # Match by name if order not available
                        completed_steps[step_name] = {
                            "status": "completed",
                            "completed_at": evt.get("timestamp"),
                            "result": evt_data.get("result") or evt_data.get("output"),
                        }
                
                # Add playbook steps as nodes if they exist
                if playbook_steps and isinstance(playbook_steps, list):
                    current_exception_step = getattr(db_exception, 'current_step', None)
                    
                    for i, step in enumerate(playbook_steps):
                        step_order = i + 1
                        step_id = f"playbook:step:{step_order}"
                        
                        # Get step label
                        if isinstance(step, dict):
                            step_label = step.get("name", step.get("text", f"Step {step_order}"))
                            step_action = step.get("action_type", step.get("action", ""))
                        else:
                            step_label = str(step)
                            step_action = ""
                        
                        # Determine step status from completed events
                        step_status = "pending"
                        step_started_at = None
                        step_completed_at = None
                        step_result = None
                        
                        # Check by order first, then by name
                        completion_info = completed_steps.get(step_order) or completed_steps.get(step_label)
                        
                        if completion_info:
                            step_status = completion_info.get("status", "completed")
                            step_completed_at = completion_info.get("completed_at")
                            step_result = completion_info.get("result")
                        elif current_exception_step is not None:
                            # Derive status from exception.current_step
                            if step_order < current_exception_step:
                                step_status = "completed"
                            elif step_order == current_exception_step:
                                step_status = "in-progress"
                            # else remains "pending"
                        
                        step_meta = {
                            "step_index": step_order,
                            "step_data": step,
                            "action_type": step_action,
                        }
                        if step_result:
                            step_meta["result"] = step_result
                        
                        playbook_node = {
                            "id": step_id,
                            "type": "playbook",
                            "kind": "step", 
                            "label": step_label,
                            "status": step_status,
                            "started_at": step_started_at,
                            "completed_at": step_completed_at,
                            "meta": step_meta,
                        }
                        playbook_nodes.append(playbook_node)
                        
                        # Add edge from previous step or from playbook stage
                        if i == 0:
                            # Connect first step to playbook stage
                            playbook_edges.append({
                                "id": f"stage:playbook-to-{step_id}",
                                "source": "stage:playbook", 
                                "target": step_id,
                                "label": None
                            })
                        else:
                            # Connect to previous step
                            prev_step_id = f"playbook:step:{i}"
                            playbook_edges.append({
                                "id": f"{prev_step_id}-to-{step_id}",
                                "source": prev_step_id,
                                "target": step_id,
                                "label": None
                            })
                
                # Combine stage nodes and playbook step nodes
                all_nodes = nodes + playbook_nodes
                
                # Build edges - linear pipeline flow between stages
                edges = []
                for i in range(len(stages) - 1):
                    edge = {
                        "id": f"{stages[i]['id']}-to-{stages[i+1]['id']}",
                        "source": stages[i]["id"],
                        "target": stages[i+1]["id"],
                        "label": None
                    }
                    edges.append(edge)
                
                # Add playbook edges
                edges.extend(playbook_edges)
                
                # If we have playbook steps, connect last step to tool stage
                if playbook_nodes:
                    last_step = playbook_nodes[-1]
                    edges.append({
                        "id": f"{last_step['id']}-to-stage:tool",
                        "source": last_step["id"],
                        "target": "stage:tool",
                        "label": None
                    })
                    
                    # Remove the direct edge from playbook to tool stage
                    edges = [e for e in edges if not (e["source"] == "stage:playbook" and e["target"] == "stage:tool")]
                
                return {
                    "nodes": all_nodes,
                    "edges": edges,
                    "current_stage": current_stage,
                    "playbook_id": playbook_id,
                    "playbook_name": playbook_name,
                    "playbook_steps": playbook_steps,
                    "exception_current_step": getattr(db_exception, 'current_step', None),
                }
                
        except Exception as e:
            logger.error(f"Error building workflow graph for exception {exception_id}: {e}", exc_info=True)
            return None


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

