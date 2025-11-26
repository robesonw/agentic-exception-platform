"""
Canonical exception record schema with strict Pydantic v2 validation.
Matches specification from docs/03-data-models-apis.md
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


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
    PENDING_APPROVAL = "PENDING_APPROVAL"  # Phase 2: Waiting for human approval


class AuditEntry(BaseModel):
    """Single audit trail entry."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    action: str = Field(..., min_length=1, description="Description of the action performed")
    timestamp: datetime = Field(..., description="ISO datetime when action occurred")
    actor: str = Field(..., min_length=1, description="Agent or system component performing action")


class ExceptionRecord(BaseModel):
    """
    Canonical exception record schema.
    
    Matches specification from docs/03-data-models-apis.md and
    docs/master_project_instruction_full.md.
    
    This is the core data structure for all exception processing.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "exceptionId": "exc_001",
                "tenantId": "tenant_001",
                "sourceSystem": "ERP",
                "exceptionType": "DataQualityFailure",
                "severity": "HIGH",
                "timestamp": "2024-01-15T10:30:00Z",
                "rawPayload": {"error": "Invalid data format"},
                "normalizedContext": {},
                "detectedRules": [],
                "suggestedActions": [],
                "resolutionStatus": "OPEN",
                "auditTrail": [],
            }
        },
    )

    exception_id: str = Field(..., alias="exceptionId", min_length=1, description="Unique exception identifier")
    tenant_id: str = Field(..., alias="tenantId", min_length=1, description="Tenant identifier")
    source_system: str = Field(..., alias="sourceSystem", min_length=1, description="Source system name (e.g., 'ERP')")
    exception_type: str | None = Field(
        None, alias="exceptionType", description="Exception type from Domain Pack taxonomy"
    )
    severity: Severity | None = Field(None, description="Exception severity level")
    timestamp: datetime = Field(..., description="ISO datetime when exception occurred")
    raw_payload: dict[str, Any] = Field(..., alias="rawPayload", description="Arbitrary source data")
    normalized_context: dict[str, Any] = Field(
        default_factory=dict,
        alias="normalizedContext",
        description="Key-value pairs from normalization",
    )
    detected_rules: list[str] = Field(
        default_factory=list, alias="detectedRules", description="Array of violated rules"
    )
    suggested_actions: list[str] = Field(
        default_factory=list, alias="suggestedActions", description="Array of potential resolutions"
    )
    resolution_status: ResolutionStatus = Field(
        default=ResolutionStatus.OPEN,
        alias="resolutionStatus",
        description="Current resolution status",
    )
    audit_trail: list[AuditEntry] = Field(
        default_factory=list, alias="auditTrail", description="Array of audit entries"
    )

    @classmethod
    def model_validate_json(cls, json_data: str | bytes, *, strict: bool | None = None) -> "ExceptionRecord":
        """
        Validate and create ExceptionRecord from JSON string.
        
        Args:
            json_data: JSON string or bytes
            strict: Enable strict mode validation
            
        Returns:
            Validated ExceptionRecord instance
        """
        return super().model_validate_json(json_data, strict=strict)

    def model_dump_json(self, *, exclude_none: bool = False, by_alias: bool = True, **kwargs) -> str:
        """
        Serialize ExceptionRecord to JSON string.
        
        Args:
            exclude_none: Exclude None values from output
            by_alias: Use field aliases (camelCase) instead of field names (snake_case)
            **kwargs: Additional serialization options
            
        Returns:
            JSON string representation
        """
        return super().model_dump_json(exclude_none=exclude_none, by_alias=by_alias, **kwargs)

