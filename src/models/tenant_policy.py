"""
Tenant Policy Pack schema models with strict Pydantic v2 validation.
Matches specification from docs/03-data-models-apis.md
"""

from typing import Any, Optional

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


class ToolOverride(BaseModel):
    """Tool property override from Tenant Policy Pack."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    tool_name: str = Field(..., alias="toolName", min_length=1, description="Tool name to override")
    timeout_seconds: Optional[float] = Field(
        None, alias="timeoutSeconds", ge=0.0, description="Override timeout in seconds"
    )
    max_retries: Optional[int] = Field(
        None, alias="maxRetries", ge=0, description="Override maximum retries"
    )


class RetentionPolicies(BaseModel):
    """Data retention policies."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    data_ttl: int = Field(..., alias="dataTTL", gt=0, description="Time to live in days")


class EmbeddingConfig(BaseModel):
    """Embedding provider configuration for tenant."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    provider: str = Field(
        ..., min_length=1, description="Embedding provider name (e.g., 'openai', 'huggingface')"
    )
    model: str = Field(
        ..., min_length=1, description="Model name (e.g., 'text-embedding-ada-002', 'sentence-transformers/all-MiniLM-L6-v2')"
    )
    api_key: Optional[str] = Field(
        None, alias="apiKey", description="API key for provider (if required)"
    )
    dimension: Optional[int] = Field(
        None, ge=1, description="Embedding dimension override (if applicable)"
    )


class NotificationPolicies(BaseModel):
    """Notification policies for tenant."""

    model_config = ConfigDict(
        extra="allow",  # Allow extra fields for flexible webhook configuration
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    channels: list[str] = Field(
        default_factory=list,
        description="List of notification channels (e.g., 'email', 'teamsWebhook', 'slackWebhook')",
    )
    recipients_by_group: dict[str, list[str]] = Field(
        default_factory=dict,
        alias="recipientsByGroup",
        description="Map of group names to recipient email addresses",
    )
    webhook_urls: dict[str, str] = Field(
        default_factory=dict,
        alias="webhookUrls",
        description="Map of channel names to webhook URLs",
    )
    smtp_config: Optional[dict[str, Any]] = Field(
        None,
        alias="smtpConfig",
        description="SMTP configuration (host, port, user, password, useTls)",
    )


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
    tool_overrides: list[ToolOverride] = Field(
        default_factory=list,
        alias="toolOverrides",
        description="Tool property overrides (timeouts, retries)",
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
    embedding_config: Optional[EmbeddingConfig] = Field(
        None, alias="embeddingConfig", description="Custom embedding provider configuration per tenant"
    )
    notification_policies: Optional[NotificationPolicies] = Field(
        None, alias="notificationPolicies", description="Notification policies for alerts and updates"
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

