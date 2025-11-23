"""
Canonical exception schema models.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Exception severity levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ResolutionStatus(str, Enum):
    """Exception resolution status."""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class AuditEntry(BaseModel):
    """Single audit trail entry."""

    action: str
    timestamp: datetime
    actor: str


class Exception(BaseModel):
    """
    Canonical exception schema.
    Matches specification from docs/03-data-models-apis.md
    """

    exception_id: str = Field(..., alias="exceptionId")
    tenant_id: str = Field(..., alias="tenantId")
    source_system: str = Field(..., alias="sourceSystem")
    exception_type: Optional[str] = Field(None, alias="exceptionType")
    severity: Optional[Severity] = None
    timestamp: datetime
    raw_payload: Dict[str, Any] = Field(..., alias="rawPayload")
    normalized_context: Dict[str, Any] = Field(default_factory=dict, alias="normalizedContext")
    detected_rules: List[str] = Field(default_factory=list, alias="detectedRules")
    suggested_actions: List[str] = Field(default_factory=list, alias="suggestedActions")
    resolution_status: ResolutionStatus = Field(
        default=ResolutionStatus.OPEN, alias="resolutionStatus"
    )
    audit_trail: List[AuditEntry] = Field(default_factory=list, alias="auditTrail")

    class Config:
        populate_by_name = True

