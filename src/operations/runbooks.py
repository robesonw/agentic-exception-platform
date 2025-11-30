"""
Operational Runbooks and Incident Playbooks (P3-27).

Provides structured runbooks for common error conditions and platform incidents.
Integrates with observability and notification systems.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


class RunbookStatus(str, Enum):
    """Runbook execution status."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class RunbookStep:
    """A single step in a runbook."""

    step_number: int
    title: str
    description: str
    action: str  # e.g., "check_logs", "restart_service", "escalate"
    expected_outcome: Optional[str] = None
    timeout_seconds: Optional[int] = None
    requires_approval: bool = False


class Runbook(BaseModel):
    """
    Runbook definition for operational procedures.
    
    Loaded from YAML configuration files.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    id: str = Field(..., description="Unique runbook identifier")
    name: str = Field(..., min_length=1, description="Runbook name")
    description: str = Field(..., description="Runbook description")
    triggers: list[str] = Field(
        default_factory=list, description="Trigger conditions (tags, error codes, etc.)"
    )
    steps: list[dict[str, Any]] = Field(
        default_factory=list, description="List of runbook steps"
    )
    severity: str = Field(
        default="MEDIUM", description="Severity level (LOW, MEDIUM, HIGH, CRITICAL)"
    )
    owner: Optional[str] = Field(None, description="Runbook owner/team")
    tags: list[str] = Field(
        default_factory=list, description="Tags for categorization and matching"
    )
    component: Optional[str] = Field(
        None, description="Component/system this runbook applies to"
    )
    error_codes: list[str] = Field(
        default_factory=list, description="Error codes that trigger this runbook"
    )

    def get_steps(self) -> list[RunbookStep]:
        """
        Convert step dictionaries to RunbookStep objects.
        
        Returns:
            List of RunbookStep objects
        """
        steps = []
        for idx, step_dict in enumerate(self.steps, start=1):
            step = RunbookStep(
                step_number=idx,
                title=step_dict.get("title", f"Step {idx}"),
                description=step_dict.get("description", ""),
                action=step_dict.get("action", ""),
                expected_outcome=step_dict.get("expected_outcome"),
                timeout_seconds=step_dict.get("timeout_seconds"),
                requires_approval=step_dict.get("requires_approval", False),
            )
            steps.append(step)
        return steps


class RunbookExecution(BaseModel):
    """
    Execution record for a runbook.
    
    Tracks the execution of a runbook for a specific incident.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique execution identifier"
    )
    runbook_id: str = Field(..., alias="runbookId", description="Runbook identifier")
    incident_id: str = Field(..., alias="incidentId", description="Incident identifier")
    start_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        alias="startTime",
        description="Execution start timestamp",
    )
    end_time: Optional[datetime] = Field(
        None, alias="endTime", description="Execution end timestamp"
    )
    status: RunbookStatus = Field(
        default=RunbookStatus.PENDING, description="Execution status"
    )
    notes: Optional[str] = Field(None, description="Execution notes")
    executed_by: Optional[str] = Field(
        None, alias="executedBy", description="Person/team who executed the runbook"
    )
    tenant_id: Optional[str] = Field(
        None, alias="tenantId", description="Tenant identifier"
    )


class RunbookLoader:
    """
    Loads runbook definitions from YAML files.
    
    Looks for runbooks in: ./config/runbooks/*.yaml
    """

    def __init__(self, config_dir: str = "config/runbooks"):
        """
        Initialize runbook loader.
        
        Args:
            config_dir: Directory containing runbook YAML files
        """
        self.config_dir = Path(config_dir)
        self._runbooks: dict[str, Runbook] = {}
        self._load_runbooks()

    def _load_runbooks(self) -> None:
        """Load all runbooks from YAML files."""
        if not self.config_dir.exists():
            logger.warning(f"Runbook config directory not found: {self.config_dir}")
            return

        for yaml_file in self.config_dir.glob("*.yaml"):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                
                if not data:
                    logger.warning(f"Empty runbook file: {yaml_file}")
                    continue
                
                # Handle single runbook or list of runbooks
                runbooks_data = data if isinstance(data, list) else [data]
                
                for runbook_data in runbooks_data:
                    try:
                        runbook = Runbook.model_validate(runbook_data)
                        self._runbooks[runbook.id] = runbook
                        logger.info(f"Loaded runbook: {runbook.id} - {runbook.name}")
                    except Exception as e:
                        logger.error(
                            f"Failed to load runbook from {yaml_file}: {e}",
                            exc_info=True,
                        )
            except Exception as e:
                logger.error(f"Failed to read runbook file {yaml_file}: {e}", exc_info=True)

    def get_runbook(self, runbook_id: str) -> Optional[Runbook]:
        """
        Get a runbook by ID.
        
        Args:
            runbook_id: Runbook identifier
            
        Returns:
            Runbook if found, None otherwise
        """
        return self._runbooks.get(runbook_id)

    def list_runbooks(self) -> list[Runbook]:
        """
        List all loaded runbooks.
        
        Returns:
            List of all runbooks
        """
        return list(self._runbooks.values())

    def reload(self) -> None:
        """Reload runbooks from files."""
        self._runbooks.clear()
        self._load_runbooks()


class RunbookSuggester:
    """
    Suggests runbooks for incidents based on matching criteria.
    
    Matches on tags, severity, component, error codes, and triggers.
    """

    def __init__(self, runbook_loader: Optional[RunbookLoader] = None):
        """
        Initialize runbook suggester.
        
        Args:
            runbook_loader: Optional RunbookLoader instance
        """
        self.runbook_loader = runbook_loader or RunbookLoader()

    def suggest_runbooks_for_incident(
        self, incident: Any, **kwargs: Any
    ) -> list[Runbook]:
        """
        Suggest runbooks for an incident.
        
        Args:
            incident: Incident object (from IncidentManager) or dict with incident data
            **kwargs: Additional context (component, error_code, severity, etc.)
            
        Returns:
            List of suggested runbooks, sorted by relevance
        """
        # Extract incident attributes
        if isinstance(incident, dict):
            incident_type = incident.get("violation_type") or incident.get("violationType")
            severity = kwargs.get("severity") or incident.get("severity", "MEDIUM")
            component = kwargs.get("component") or incident.get("component")
            error_code = kwargs.get("error_code") or incident.get("error_code")
            tags = kwargs.get("tags") or incident.get("tags", [])
        else:
            # Assume it's an Incident object
            incident_type = getattr(incident, "violation_type", None)
            severity = kwargs.get("severity", "MEDIUM")
            component = kwargs.get("component")
            error_code = kwargs.get("error_code")
            tags = kwargs.get("tags", [])

        # Build matching criteria
        matching_runbooks: list[tuple[Runbook, int]] = []

        for runbook in self.runbook_loader.list_runbooks():
            score = 0

            # Match on severity
            if runbook.severity.upper() == severity.upper():
                score += 10

            # Match on component
            if component and runbook.component:
                if component.lower() == runbook.component.lower():
                    score += 20

            # Match on error codes
            if error_code and runbook.error_codes:
                if error_code in runbook.error_codes:
                    score += 30

            # Match on tags
            if tags and runbook.tags:
                common_tags = set(tags) & set(runbook.tags)
                score += len(common_tags) * 5

            # Match on triggers
            if runbook.triggers:
                # Check if any trigger matches incident type or other attributes
                for trigger in runbook.triggers:
                    trigger_lower = trigger.lower()
                    if incident_type and incident_type.lower() in trigger_lower:
                        score += 15
                    if error_code and error_code.lower() in trigger_lower:
                        score += 15

            # Only include runbooks with positive score
            if score > 0:
                matching_runbooks.append((runbook, score))

        # Sort by score (descending) and return runbooks
        matching_runbooks.sort(key=lambda x: x[1], reverse=True)
        return [runbook for runbook, _ in matching_runbooks]


class RunbookExecutor:
    """
    Executes and tracks runbook executions.
    
    Manages the lifecycle of runbook executions and persists execution records.
    """

    def __init__(self, storage_dir: str = "./runtime/runbooks"):
        """
        Initialize runbook executor.
        
        Args:
            storage_dir: Directory for storing execution records
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.executions_file = self.storage_dir / "executions.jsonl"

    def start_execution(
        self,
        runbook: Runbook,
        incident_id: str,
        tenant_id: Optional[str] = None,
        executed_by: Optional[str] = None,
    ) -> RunbookExecution:
        """
        Start a runbook execution.
        
        Args:
            runbook: Runbook to execute
            incident_id: Incident identifier
            tenant_id: Optional tenant identifier
            executed_by: Optional person/team executing the runbook
            
        Returns:
            RunbookExecution instance
        """
        execution = RunbookExecution(
            runbook_id=runbook.id,
            incident_id=incident_id,
            status=RunbookStatus.IN_PROGRESS,
            tenant_id=tenant_id,
            executed_by=executed_by,
        )

        # Persist execution
        self._persist_execution(execution)

        logger.info(
            f"Started runbook execution {execution.id} for runbook {runbook.id} "
            f"and incident {incident_id}"
        )

        return execution

    def complete_execution(
        self,
        execution_id: str,
        status: RunbookStatus,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Complete a runbook execution.
        
        Args:
            execution_id: Execution identifier
            status: Final status (COMPLETED, FAILED, or CANCELLED)
            notes: Optional execution notes
            
        Returns:
            True if execution was found and updated, False otherwise
        """
        execution = self._load_execution(execution_id)
        if not execution:
            logger.warning(f"Runbook execution {execution_id} not found")
            return False

        # Update execution
        execution.status = status
        execution.end_time = datetime.now(timezone.utc)
        execution.notes = notes

        # Persist updated execution
        self._persist_execution(execution)

        logger.info(
            f"Completed runbook execution {execution_id} with status {status.value}"
        )

        return True

    def get_execution(self, execution_id: str) -> Optional[RunbookExecution]:
        """
        Get a runbook execution by ID.
        
        Args:
            execution_id: Execution identifier
            
        Returns:
            RunbookExecution if found, None otherwise
        """
        return self._load_execution(execution_id)

    def get_executions_for_incident(
        self, incident_id: str
    ) -> list[RunbookExecution]:
        """
        Get all executions for an incident.
        
        Args:
            incident_id: Incident identifier
            
        Returns:
            List of RunbookExecution instances
        """
        executions = []
        if not self.executions_file.exists():
            return executions

        try:
            with open(self.executions_file, "r", encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line)
                    if data.get("incidentId") == incident_id:
                        execution = RunbookExecution.model_validate(data)
                        executions.append(execution)
        except Exception as e:
            logger.error(f"Failed to load executions: {e}", exc_info=True)

        return executions

    def _persist_execution(self, execution: RunbookExecution) -> None:
        """Persist execution to storage."""
        try:
            with open(self.executions_file, "a", encoding="utf-8") as f:
                execution_dict = execution.model_dump(by_alias=True, mode="json")
                f.write(json.dumps(execution_dict, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to persist execution: {e}", exc_info=True)

    def _load_execution(self, execution_id: str) -> Optional[RunbookExecution]:
        """Load execution from storage."""
        if not self.executions_file.exists():
            return None

        try:
            with open(self.executions_file, "r", encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line)
                    if data.get("id") == execution_id:
                        return RunbookExecution.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to load execution: {e}", exc_info=True)

        return None


# Global instances
_runbook_loader: Optional[RunbookLoader] = None
_runbook_suggester: Optional[RunbookSuggester] = None
_runbook_executor: Optional[RunbookExecutor] = None


def get_runbook_loader() -> RunbookLoader:
    """Get global runbook loader instance."""
    global _runbook_loader
    if _runbook_loader is None:
        _runbook_loader = RunbookLoader()
    return _runbook_loader


def get_runbook_suggester() -> RunbookSuggester:
    """Get global runbook suggester instance."""
    global _runbook_suggester
    if _runbook_suggester is None:
        _runbook_suggester = RunbookSuggester()
    return _runbook_suggester


def get_runbook_executor() -> RunbookExecutor:
    """Get global runbook executor instance."""
    global _runbook_executor
    if _runbook_executor is None:
        _runbook_executor = RunbookExecutor()
    return _runbook_executor


def suggest_runbooks_for_incident(incident: Any, **kwargs: Any) -> list[Runbook]:
    """
    Suggest runbooks for an incident.
    
    Convenience function for integration.
    
    Args:
        incident: Incident object or dict
        **kwargs: Additional context
        
    Returns:
        List of suggested runbooks
    """
    suggester = get_runbook_suggester()
    return suggester.suggest_runbooks_for_incident(incident, **kwargs)

