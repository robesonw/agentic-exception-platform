"""
Audit logging system with JSONL file persistence.
Matches specification from docs/08-security-compliance.md and phase1-mvp-issues.md

Phase 3: Enhanced with partitioning hooks for multi-tenant scaling.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.infrastructure.partitioning import PartitioningHelper
from src.models.agent_contracts import AgentDecision
from src.models.exception_record import ExceptionRecord
from src.models.exception_record import ExceptionRecord


class AuditLoggerError(Exception):
    """Raised when audit logging operations fail."""

    pass


class AuditLogger:
    """
    Audit logger that writes all events to JSONL files.
    
    Every agent decision, tool call, and system action is logged
    with timestamps, run_id, and tenant_id for full traceability.
    """

    def __init__(self, run_id: str, tenant_id: Optional[str] = None):
        """
        Initialize the audit logger.
        
        Args:
            run_id: Unique identifier for this execution run
            tenant_id: Optional tenant identifier (can be set per event)
        """
        self.run_id = run_id
        self.default_tenant_id = tenant_id
        self._log_file: Optional[Path] = None
        self._file_handle = None
        self._ensure_audit_directory()

    def _ensure_audit_directory(self) -> None:
        """Ensure the audit directory exists."""
        audit_dir = Path("./runtime/audit")
        audit_dir.mkdir(parents=True, exist_ok=True)

    def _get_log_file(self, tenant_id: Optional[str] = None) -> Path:
        """
        Get the log file path for this run_id.
        
        Phase 3: Partitions by tenant_id for scaling.
        
        Args:
            tenant_id: Optional tenant ID for partitioning
        """
        if self._log_file is None:
            audit_dir = Path("./runtime/audit")
            # Phase 3: Partition by tenant_id if available
            if tenant_id:
                tenant_dir = audit_dir / tenant_id
                tenant_dir.mkdir(parents=True, exist_ok=True)
                self._log_file = tenant_dir / f"{self.run_id}.jsonl"
            else:
                self._log_file = audit_dir / f"{self.run_id}.jsonl"
        return self._log_file

    def _get_file_handle(self, tenant_id: Optional[str] = None):
        """
        Get or create the file handle for writing.
        
        Phase 3: Supports tenant-specific file handles for partitioning.
        
        Args:
            tenant_id: Optional tenant ID for partitioning
        """
        # For MVP, use single file handle. In production, could use per-tenant handles.
        # If tenant_id changes, we'd need to close and reopen, but for MVP we use single handle.
        if self._file_handle is None:
            log_file = self._get_log_file(tenant_id)
            self._file_handle = open(log_file, "a", encoding="utf-8")
        return self._file_handle

    def _serialize_for_json(self, obj: Any) -> Any:
        """
        Recursively serialize objects to JSON-serializable format.
        
        Handles:
        - datetime objects -> ISO format strings
        - ExceptionRecord objects -> dict with serialized fields
        - Other Pydantic models -> dict
        - Nested dicts and lists
        
        Args:
            obj: Object to serialize
            
        Returns:
            JSON-serializable representation
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, ExceptionRecord):
            # Convert ExceptionRecord to dict and serialize nested objects
            record_dict = obj.model_dump()
            return self._serialize_for_json(record_dict)
        elif hasattr(obj, "model_dump"):
            # Pydantic model
            return self._serialize_for_json(obj.model_dump())
        elif isinstance(obj, dict):
            return {k: self._serialize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._serialize_for_json(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            # Fallback: try to convert to string
            return str(obj)

    def _write_log_entry(self, event_type: str, data: dict[str, Any], tenant_id: Optional[str] = None) -> None:
        """
        Write a log entry to the JSONL file.
        
        Phase 3: Uses partitioning by tenant_id for scaling.
        
        Args:
            event_type: Type of event (agent_event, tool_call, decision)
            data: Event-specific data (must be JSON-serializable)
            tenant_id: Optional tenant ID (uses default if not provided)
        """
        effective_tenant_id = tenant_id or self.default_tenant_id
        
        # Phase 3: Extract partition key for indexing hints
        partition_key = None
        if effective_tenant_id:
            partition_key = PartitioningHelper.create_partition_key(effective_tenant_id)
        
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "tenant_id": effective_tenant_id,
            "event_type": event_type,
            "data": data,
        }
        
        # Phase 3: Add partition metadata for indexing
        if partition_key:
            log_entry["_partition"] = partition_key.to_dict()
            log_entry["_index_hint"] = PartitioningHelper.create_index_hint(
                tenant_created=True
            ).to_dict()
        
        # Remove None values
        log_entry = {k: v for k, v in log_entry.items() if v is not None}
        
        try:
            # Phase 3: Get file handle with tenant partitioning
            file_handle = self._get_file_handle(effective_tenant_id)
            json_line = json.dumps(log_entry, ensure_ascii=False, default=str)
            file_handle.write(json_line + "\n")
            file_handle.flush()  # Ensure immediate write
        except (IOError, OSError) as e:
            raise AuditLoggerError(f"Failed to write audit log entry: {e}") from e

    def log_agent_event(
        self,
        agent_name: str,
        input_data: dict[str, Any],
        output: AgentDecision,
        tenant_id: Optional[str] = None,
    ) -> None:
        """
        Log an agent event (input and output).
        
        Every agent MUST log both input and output for full traceability.
        
        Args:
            agent_name: Name of the agent (e.g., "IntakeAgent", "TriageAgent")
            input_data: Agent input data (exception, context, etc.)
            output: Agent decision output
            tenant_id: Optional tenant ID (uses default if not provided)
        """
        # Extract tenant_id from input if available
        if tenant_id is None and isinstance(input_data.get("exception"), ExceptionRecord):
            tenant_id = input_data["exception"].tenant_id
        
        # Serialize input_data to ensure all objects are JSON-serializable
        serialized_input = self._serialize_for_json(input_data)
        
        data = {
            "agent_name": agent_name,
            "input": serialized_input,
            "output": {
                "decision": output.decision,
                "confidence": output.confidence,
                "evidence": output.evidence,
                "next_step": output.next_step,
            },
        }
        
        self._write_log_entry("agent_event", data, tenant_id)

    def log_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> None:
        """
        Log a tool invocation.
        
        Every tool invocation must be logged for security and compliance.
        
        Args:
            tool_name: Name of the tool being invoked
            args: Tool arguments/parameters
            result: Tool execution result
            tenant_id: Optional tenant ID (uses default if not provided)
        """
        data = {
            "tool_name": tool_name,
            "args": args,
            "result": result,
        }
        
        self._write_log_entry("tool_call", data, tenant_id)

    def log_decision(
        self,
        stage: str,
        decision_json: dict[str, Any],
        tenant_id: Optional[str] = None,
        explanation_id: Optional[str] = None,
        explanation_quality_score: Optional[float] = None,
    ) -> None:
        """
        Log a decision at a specific stage.
        
        Phase 3: Enhanced with explanation tracking (P3-31).
        
        Args:
            stage: Stage name (e.g., "triage", "policy", "resolution")
            decision_json: Decision data as JSON-serializable dict
            tenant_id: Optional tenant ID (uses default if not provided)
            explanation_id: Optional explanation identifier (P3-31)
            explanation_quality_score: Optional explanation quality score (P3-31)
        """
        data = {
            "stage": stage,
            "decision": decision_json,
        }
        
        # Phase 3: Add explanation tracking fields (P3-31)
        if explanation_id:
            data["explanation_id"] = explanation_id
        if explanation_quality_score is not None:
            data["explanation_quality_score"] = explanation_quality_score
        
        self._write_log_entry("decision", data, tenant_id)

    def log_explanation_generated(
        self,
        exception_id: str,
        tenant_id: str,
        format: str,
        agent_names_involved: list[str],
        explanation_id: Optional[str] = None,
        explanation_quality_score: Optional[float] = None,
        latency_ms: Optional[float] = None,
    ) -> None:
        """
        Log explanation generation event.
        
        Phase 3: Tracks explanation generation for analytics (P3-31).
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            format: Explanation format (json, text, structured)
            agent_names_involved: List of agent names involved in the explanation
            explanation_id: Optional explanation identifier (hash)
            explanation_quality_score: Optional quality score
            latency_ms: Optional generation latency in milliseconds
        """
        data = {
            "exception_id": exception_id,
            "format": format,
            "agent_names_involved": agent_names_involved,
        }
        
        if explanation_id:
            data["explanation_id"] = explanation_id
        if explanation_quality_score is not None:
            data["explanation_quality_score"] = explanation_quality_score
        if latency_ms is not None:
            data["latency_ms"] = latency_ms
        
        metadata = {
            "exception_id": exception_id,
            "format": format,
            "agent_count": len(agent_names_involved),
        }
        data["metadata"] = metadata
        
        self._write_log_entry("EXPLANATION_GENERATED", data, tenant_id)

    def log_guardrail_recommendation_generated(
        self,
        tenant_id: str,
        domain: str,
        recommendation_id: str,
        guardrail_id: str,
        recommendation_data: dict[str, Any],
    ) -> None:
        """
        Log guardrail recommendation generation event.
        
        Phase 3: Tracks guardrail recommendation generation for analytics (P3-10).
        
        Args:
            tenant_id: Tenant identifier
            domain: Domain name identifier
            recommendation_id: Recommendation identifier
            guardrail_id: Guardrail identifier
            recommendation_data: Recommendation data dictionary
        """
        data = {
            "recommendation_id": recommendation_id,
            "guardrail_id": guardrail_id,
            "domain": domain,
            "recommendation": recommendation_data,
        }
        
        self._write_log_entry("GUARDRAIL_RECOMMENDATION_GENERATED", data, tenant_id)

    def log_guardrail_recommendation_reviewed(
        self,
        tenant_id: str,
        recommendation_id: str,
        guardrail_id: str,
        review_status: str,  # "accepted" or "rejected"
        reviewed_by: Optional[str] = None,
        review_notes: Optional[str] = None,
    ) -> None:
        """
        Log guardrail recommendation review event.
        
        Phase 3: Tracks guardrail recommendation acceptance/rejection (P3-10).
        
        Args:
            tenant_id: Tenant identifier
            recommendation_id: Recommendation identifier
            guardrail_id: Guardrail identifier
            review_status: Review status ("accepted" or "rejected")
            reviewed_by: Optional user who reviewed the recommendation
            review_notes: Optional review notes
        """
        event_type = (
            "GUARDRAIL_RECOMMENDATION_ACCEPTED"
            if review_status.lower() == "accepted"
            else "GUARDRAIL_RECOMMENDATION_REJECTED"
        )
        
        data = {
            "recommendation_id": recommendation_id,
            "guardrail_id": guardrail_id,
            "review_status": review_status,
        }
        
        if reviewed_by:
            data["reviewed_by"] = reviewed_by
        if review_notes:
            data["review_notes"] = review_notes
        
        self._write_log_entry(event_type, data, tenant_id)

    def flush(self) -> None:
        """
        Flush any buffered log entries to disk.
        
        Ensures all log entries are written before continuing.
        """
        if self._file_handle is not None:
            try:
                self._file_handle.flush()
            except (IOError, OSError) as e:
                raise AuditLoggerError(f"Failed to flush audit log: {e}") from e

    def close(self) -> None:
        """
        Close the log file handle.
        
        Should be called when done logging to ensure all data is written.
        """
        if self._file_handle is not None:
            try:
                self._file_handle.flush()
                self._file_handle.close()
                self._file_handle = None
            except (IOError, OSError) as e:
                raise AuditLoggerError(f"Failed to close audit log: {e}") from e

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures file is closed."""
        self.close()
