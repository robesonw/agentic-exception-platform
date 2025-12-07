"""
Incident workflow for policy and tool violations.

Phase 3 MVP: Basic incident tracking and resolution.
Full integration with ITSM systems can be added in later phases.

Matches specification from phase3-mvp-issues.md P3-22.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


class IncidentStatus(str, Enum):
    """Incident status values."""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Incident(BaseModel):
    """Incident record for violations."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique incident identifier")
    tenant_id: str = Field(..., alias="tenantId", min_length=1, description="Tenant identifier")
    violation_id: str = Field(..., alias="violationId", min_length=1, description="Violation identifier")
    violation_type: str = Field(..., alias="violationType", description="Type of violation (policy/tool)")
    status: IncidentStatus = Field(default=IncidentStatus.OPEN, description="Incident status")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), alias="createdAt", description="Incident creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), alias="updatedAt", description="Last update timestamp"
    )
    resolved_at: Optional[datetime] = Field(None, alias="resolvedAt", description="Resolution timestamp")
    resolution_summary: Optional[str] = Field(None, alias="resolutionSummary", description="Resolution summary")
    assigned_to: Optional[str] = Field(None, alias="assignedTo", description="Assigned person/team")


class IncidentManager:
    """
    Manages incident lifecycle for violations.
    
    Phase 3 MVP: Simple file-based storage.
    Future: Integration with ITSM systems (ServiceNow, Jira, etc.)
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        """
        Initialize incident manager.
        
        Args:
            storage_dir: Directory for storing incident records (default: ./runtime/incidents)
        """
        self.storage_dir = storage_dir or Path("./runtime/incidents")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def open_incident(
        self,
        tenant_id: str,
        violation_id: str,
        violation_type: str,
    ) -> str:
        """
        Open a new incident for a violation.
        
        Args:
            tenant_id: Tenant identifier
            violation_id: Violation identifier
            violation_type: Type of violation ("policy" or "tool")
            
        Returns:
            Incident ID
        """
        incident = Incident(
            tenant_id=tenant_id,
            violation_id=violation_id,
            violation_type=violation_type,
            status=IncidentStatus.OPEN,
        )
        
        # Persist incident
        self._persist_incident(incident)
        
        logger.info(
            f"Opened incident {incident.id} for violation {violation_id} "
            f"(tenant={tenant_id}, type={violation_type})"
        )
        
        # Phase 3: Trigger runbook suggestions for violation incidents (P3-27)
        try:
            from src.operations.runbook_integration import trigger_runbooks_for_violation_incident
            
            suggested_runbooks = trigger_runbooks_for_violation_incident(
                incident=incident,
                auto_execute=False,  # Don't auto-execute, just suggest
                tenant_id=tenant_id,
            )
            if suggested_runbooks:
                logger.info(
                    f"Suggested {len(suggested_runbooks)} runbook(s) for incident {incident.id}"
                )
        except Exception as e:
            logger.warning(f"Failed to trigger runbook suggestions for incident: {e}")
        
        return incident.id

    def close_incident(
        self,
        incident_id: str,
        resolution_summary: str,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """
        Close an incident with a resolution summary.
        
        Args:
            incident_id: Incident identifier
            resolution_summary: Human-readable resolution summary
            tenant_id: Optional tenant identifier for lookup
            
        Returns:
            True if incident was found and closed, False otherwise
        """
        # Load incident
        incident = self._load_incident(incident_id, tenant_id)
        if not incident:
            logger.warning(f"Incident {incident_id} not found")
            return False
        
        # Update incident
        incident.status = IncidentStatus.CLOSED
        incident.resolved_at = datetime.now(timezone.utc)
        incident.updated_at = datetime.now(timezone.utc)
        incident.resolution_summary = resolution_summary
        
        # Persist updated incident
        self._persist_incident(incident)
        
        logger.info(f"Closed incident {incident_id} with resolution: {resolution_summary}")
        
        return True

    def get_incident(self, incident_id: str, tenant_id: Optional[str] = None) -> Optional[Incident]:
        """
        Get an incident by ID.
        
        Args:
            incident_id: Incident identifier
            tenant_id: Optional tenant identifier for lookup
            
        Returns:
            Incident if found, None otherwise
        """
        return self._load_incident(incident_id, tenant_id)

    def _persist_incident(self, incident: Incident) -> None:
        """Persist incident to storage."""
        incident_file = self.storage_dir / f"{incident.tenant_id}_incidents.jsonl"
        with open(incident_file, "a", encoding="utf-8") as f:
            incident_dict = incident.model_dump(by_alias=True, mode="json")
            f.write(json.dumps(incident_dict) + "\n")

    def _load_incident(self, incident_id: str, tenant_id: Optional[str] = None) -> Optional[Incident]:
        """Load incident from storage."""
        # If tenant_id is provided, only search that tenant's file
        if tenant_id:
            incident_file = self.storage_dir / f"{tenant_id}_incidents.jsonl"
            if incident_file.exists():
                with open(incident_file, "r", encoding="utf-8") as f:
                    for line in f:
                        data = json.loads(line)
                        if data.get("id") == incident_id:
                            return Incident.model_validate(data)
            return None
        
        # Otherwise, search all tenant files
        for incident_file in self.storage_dir.glob("*_incidents.jsonl"):
            try:
                with open(incident_file, "r", encoding="utf-8") as f:
                    for line in f:
                        data = json.loads(line)
                        if data.get("id") == incident_id:
                            return Incident.model_validate(data)
            except Exception as e:
                logger.warning(f"Error reading incident file {incident_file}: {e}")
        
        return None


# Global incident manager instance
# In production, this would be injected via dependency injection
_incident_manager: Optional[IncidentManager] = None


def get_incident_manager() -> IncidentManager:
    """
    Get the global incident manager instance.
    
    Returns:
        IncidentManager instance
    """
    global _incident_manager
    if _incident_manager is None:
        _incident_manager = IncidentManager()
    return _incident_manager

