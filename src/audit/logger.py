"""
Audit logging system with JSONL file persistence.
Matches specification from docs/08-security-compliance.md and phase1-mvp-issues.md
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.models.agent_contracts import AgentDecision
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

    def _get_log_file(self) -> Path:
        """Get the log file path for this run_id."""
        if self._log_file is None:
            audit_dir = Path("./runtime/audit")
            self._log_file = audit_dir / f"{self.run_id}.jsonl"
        return self._log_file

    def _get_file_handle(self):
        """Get or create the file handle for writing."""
        if self._file_handle is None:
            log_file = self._get_log_file()
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
        
        Args:
            event_type: Type of event (agent_event, tool_call, decision)
            data: Event-specific data (must be JSON-serializable)
            tenant_id: Optional tenant ID (uses default if not provided)
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "tenant_id": tenant_id or self.default_tenant_id,
            "event_type": event_type,
            "data": data,
        }
        
        # Remove None values
        log_entry = {k: v for k, v in log_entry.items() if v is not None}
        
        try:
            file_handle = self._get_file_handle()
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
    ) -> None:
        """
        Log a decision at a specific stage.
        
        Args:
            stage: Stage name (e.g., "triage", "policy", "resolution")
            decision_json: Decision data as JSON-serializable dict
            tenant_id: Optional tenant ID (uses default if not provided)
        """
        data = {
            "stage": stage,
            "decision": decision_json,
        }
        
        self._write_log_entry("decision", data, tenant_id)

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
