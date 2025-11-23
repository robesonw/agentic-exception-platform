"""
Tenant Policy Pack schema models with strict Pydantic v2 validation.
Matches specification from docs/03-data-models-apis.md
"""

from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from src.models.domain_pack import Guardrails, Playbook


class SeverityOverride(BaseModel):
    """Custom severity override for exception type."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    exception_type: str = Field(..., alias="exceptionType", min_length=1, description="Exception type to override")
    severity: str = Field(..., min_length=1, description="Override severity level")


class HumanApprovalRule(BaseModel):
    """Human approval rule based on severity."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    severity: str = Field(..., min_length=1, description="Severity level")
    require_approval: bool = Field(..., alias="requireApproval", description="Whether approval is required")


class RetentionPolicies(BaseModel):
    """Data retention policies."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    data_ttl: int = Field(..., alias="dataTTL", gt=0, description="Time to live in days")


class TenantPolicyPack(BaseModel):
    """
    Tenant Policy Pack schema with strict validation.
    
    Matches specification from docs/03-data-models-apis.md and
    docs/master_project_instruction_full.md Section 5.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    tenant_id: str = Field(..., alias="tenantId", min_length=1, description="Tenant identifier")
    domain_name: str = Field(
        ..., alias="domainName", min_length=1, description="Domain name (references Domain Pack)"
    )
    custom_severity_overrides: list[SeverityOverride] = Field(
        default_factory=list,
        alias="customSeverityOverrides",
        description="Custom severity overrides per exception type",
    )
    custom_guardrails: Guardrails | None = Field(
        None, alias="customGuardrails", description="Custom guardrails (overrides Domain Pack)"
    )
    approved_tools: list[str] = Field(
        default_factory=list, alias="approvedTools", description="List of approved tool names"
    )
    human_approval_rules: list[HumanApprovalRule] = Field(
        default_factory=list,
        alias="humanApprovalRules",
        description="Human approval rules per severity",
    )
    retention_policies: RetentionPolicies | None = Field(
        None, alias="retentionPolicies", description="Data retention policies"
    )
    custom_playbooks: list[Playbook] = Field(
        default_factory=list, alias="customPlaybooks", description="Custom playbooks (overrides Domain Pack)"
    )

    @classmethod
    def model_validate_json(cls, json_data: str | bytes, *, strict: bool | None = None) -> "TenantPolicyPack":
        """
        Validate and create TenantPolicyPack from JSON string.
        
        Args:
            json_data: JSON string or bytes
            strict: Enable strict mode validation
            
        Returns:
            Validated TenantPolicyPack instance
        """
        return super().model_validate_json(json_data, strict=strict)

    def model_dump_json(self, *, exclude_none: bool = False, **kwargs) -> str:
        """
        Serialize TenantPolicyPack to JSON string.
        
        Args:
            exclude_none: Exclude None values from output
            **kwargs: Additional serialization options
            
        Returns:
            JSON string representation
        """
        return super().model_dump_json(exclude_none=exclude_none, **kwargs)

