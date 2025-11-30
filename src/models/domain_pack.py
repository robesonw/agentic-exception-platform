"""
Domain Pack schema models with strict Pydantic v2 validation.
Matches specification from docs/03-data-models-apis.md
"""

from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict


class EntityDefinition(BaseModel):
    """Entity definition within Domain Pack."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    attributes: dict[str, Any] = Field(default_factory=dict, description="Entity attributes")
    relations: list[str] = Field(default_factory=list, description="Entity relations")


class ExceptionTypeDefinition(BaseModel):
    """Exception type definition."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    name: Optional[str] = Field(None, min_length=1, description="Exception type name (optional, may be keyed in parent structure)")
    description: str = Field(..., min_length=1, description="Exception type description")
    detection_rules: list[str] = Field(
        default_factory=list, alias="detectionRules", description="Rules for detecting this exception type"
    )
    severity_rules: list["SeverityRule"] = Field(
        default_factory=list, alias="severityRules", description="Severity mapping rules for this exception type"
    )


class SeverityRule(BaseModel):
    """Severity mapping rule."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    condition: str = Field(..., min_length=1, description="Condition expression")
    severity: str = Field(..., min_length=1, description="Severity level (LOW|MEDIUM|HIGH|CRITICAL)")


class ToolDefinition(BaseModel):
    """Tool definition within Domain Pack."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    description: str = Field(..., min_length=1, description="Tool description")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")
    endpoint: str = Field(..., min_length=1, description="Tool endpoint URL")
    version: str = Field(default="1.0.0", description="Tool version for compatibility checks")
    timeout_seconds: Optional[float] = Field(
        default=None, alias="timeoutSeconds", ge=0.0, description="Request timeout in seconds"
    )
    max_retries: int = Field(
        default=3, alias="maxRetries", ge=0, description="Maximum number of retry attempts"
    )


class PlaybookStep(BaseModel):
    """Single step in a playbook."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    step_id: Optional[str] = Field(None, alias="stepId", description="Optional step identifier")
    action: str = Field(..., min_length=1, description="Action to perform")
    parameters: dict[str, Any] | None = Field(None, description="Action parameters")
    description: Optional[str] = Field(None, description="Optional step description")


class Playbook(BaseModel):
    """Playbook definition."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    exception_type: str = Field(..., alias="exceptionType", min_length=1, description="Exception type this playbook handles")
    steps: list[PlaybookStep] = Field(default_factory=list, description="Sequence of playbook steps")


class Guardrails(BaseModel):
    """Guardrails configuration."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    allow_lists: list[str] = Field(
        default_factory=list, alias="allowLists", description="List of allowed items"
    )
    block_lists: list[str] = Field(
        default_factory=list, alias="blockLists", description="List of blocked items"
    )
    human_approval_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        alias="humanApprovalThreshold",
        description="Confidence threshold requiring human approval",
    )


class TestCase(BaseModel):
    """Test case for Domain Pack validation."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    input: dict[str, Any] = Field(..., description="Test input data")
    expected_output: dict[str, Any] = Field(..., alias="expectedOutput", description="Expected test output")


class DomainPack(BaseModel):
    """
    Domain Pack schema with strict validation.
    
    Matches specification from docs/03-data-models-apis.md and
    docs/master_project_instruction_full.md Section 5.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    domain_name: str = Field(..., alias="domainName", min_length=1, description="Domain name identifier")
    entities: dict[str, EntityDefinition] = Field(
        default_factory=dict, description="Entity definitions keyed by entity name"
    )
    exception_types: dict[str, ExceptionTypeDefinition] = Field(
        default_factory=dict, alias="exceptionTypes", description="Exception type definitions"
    )
    severity_rules: list[SeverityRule] = Field(
        default_factory=list, alias="severityRules", description="Severity mapping rules"
    )
    tools: dict[str, ToolDefinition] = Field(
        default_factory=dict, description="Tool definitions keyed by tool name"
    )
    playbooks: list[Playbook] = Field(default_factory=list, description="Resolution playbooks")
    guardrails: Guardrails = Field(default_factory=Guardrails, description="Guardrails configuration")
    test_suites: list[TestCase] = Field(
        default_factory=list, alias="testSuites", description="Test cases for validation"
    )

    @classmethod
    def model_validate_json(cls, json_data: str | bytes, *, strict: bool | None = None) -> "DomainPack":
        """
        Validate and create DomainPack from JSON string.
        
        Args:
            json_data: JSON string or bytes
            strict: Enable strict mode validation
            
        Returns:
            Validated DomainPack instance
        """
        return super().model_validate_json(json_data, strict=strict)

    def model_dump_json(self, *, exclude_none: bool = False, **kwargs) -> str:
        """
        Serialize DomainPack to JSON string.
        
        Args:
            exclude_none: Exclude None values from output
            **kwargs: Additional serialization options
            
        Returns:
            JSON string representation
        """
        return super().model_dump_json(exclude_none=exclude_none, **kwargs)

