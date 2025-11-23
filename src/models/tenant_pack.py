"""
Tenant Policy Pack schema models.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.models.domain_pack import Guardrails, Playbook, PlaybookStep


class SeverityOverride(BaseModel):
    """Custom severity override for exception type."""

    exception_type: str = Field(..., alias="exceptionType")
    severity: str

    class Config:
        populate_by_name = True


class HumanApprovalRule(BaseModel):
    """Human approval rule based on severity."""

    severity: str
    require_approval: bool = Field(..., alias="requireApproval")

    class Config:
        populate_by_name = True


class RetentionPolicies(BaseModel):
    """Data retention policies."""

    data_ttl: int = Field(..., alias="dataTTL")  # Time to live in days

    class Config:
        populate_by_name = True


class TenantPolicyPack(BaseModel):
    """
    Tenant Policy Pack schema.
    Matches specification from docs/03-data-models-apis.md
    """

    tenant_id: str = Field(..., alias="tenantId")
    domain_name: str = Field(..., alias="domainName")
    custom_severity_overrides: List[SeverityOverride] = Field(
        default_factory=list, alias="customSeverityOverrides"
    )
    custom_guardrails: Optional[Guardrails] = Field(None, alias="customGuardrails")
    approved_tools: List[str] = Field(default_factory=list, alias="approvedTools")
    human_approval_rules: List[HumanApprovalRule] = Field(
        default_factory=list, alias="humanApprovalRules"
    )
    retention_policies: Optional[RetentionPolicies] = Field(None, alias="retentionPolicies")
    custom_playbooks: List[Playbook] = Field(default_factory=list, alias="customPlaybooks")

    class Config:
        populate_by_name = True

