"""
Demo Catalog Types - Pydantic models for demo catalog structure.

Defines all type definitions for the demo system including tenants,
scenarios, playbook bindings, and tool configurations.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Industry(str, Enum):
    """Supported industry types for demo tenants."""
    
    FINANCE = "finance"
    INSURANCE = "insurance"
    HEALTHCARE = "healthcare"
    RETAIL = "retail"
    SAAS_OPS = "saas_ops"


class DemoScenarioMode(str, Enum):
    """Demo scenario execution mode."""
    
    BURST = "burst"
    SCHEDULED = "scheduled"
    CONTINUOUS = "continuous"


class SimulationProfile(str, Enum):
    """Tool simulation profile."""
    
    SUCCESS = "success"
    FAIL = "fail"
    DELAYED = "delayed"
    FLAKY = "flaky"


class ExecutionMode(str, Enum):
    """Tool execution mode."""
    
    SIMULATE = "simulate"
    HTTP = "http"
    WEBHOOK = "webhook"
    QUEUE = "queue"


# =============================================================================
# Demo Tenant Models
# =============================================================================


class SeedPlan(BaseModel):
    """Seed plan for demo tenant exceptions."""
    
    min_exceptions: int = Field(default=10, ge=1, description="Minimum exceptions to seed")
    max_exceptions: int = Field(default=50, ge=1, description="Maximum exceptions to seed")
    lookback_days: int = Field(default=7, ge=1, description="Days to spread exceptions across")


class DomainPackRef(BaseModel):
    """Reference to a domain pack."""
    
    pack_key: str = Field(..., description="Domain pack key/name")
    version: str = Field(default="latest", description="Pack version")


class DemoTenant(BaseModel):
    """Demo tenant configuration."""
    
    tenant_key: str = Field(..., description="Unique tenant identifier (e.g., ACME_CAPITAL)")
    display_name: str = Field(..., description="Human-readable tenant name")
    industry: Industry = Field(..., description="Industry classification")
    tags: list[str] = Field(default_factory=lambda: ["demo"], description="Tenant tags")
    domain_pack_refs: list[DomainPackRef] = Field(default_factory=list, description="Domain pack references")
    seed_plan: SeedPlan = Field(default_factory=SeedPlan, description="Exception seeding plan")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


# =============================================================================
# Entity Template Models (for generating correlated data)
# =============================================================================


class EntityTemplate(BaseModel):
    """Template for generating correlated entity data."""
    
    entity_type: str = Field(..., description="Type of entity (e.g., trade, claim, patient)")
    prefix: str = Field(..., description="ID prefix (e.g., TRD, CLM, PAT)")
    fields: dict[str, Any] = Field(default_factory=dict, description="Field generation rules")
    correlations: list[str] = Field(default_factory=list, description="Related entity types")


class FinanceEntityTemplates(BaseModel):
    """Finance-specific entity templates."""
    
    trade_id_prefix: str = Field(default="TRD", description="Trade ID prefix")
    order_id_prefix: str = Field(default="ORD", description="Order ID prefix")
    allocation_id_prefix: str = Field(default="ALLOC", description="Allocation ID prefix")
    settlement_id_prefix: str = Field(default="SETL", description="Settlement ID prefix")
    account_id_prefix: str = Field(default="ACCT", description="Account ID prefix")
    
    booking_systems: list[str] = Field(
        default_factory=lambda: ["Murex", "Calypso", "Broadridge", "InternalTMS"],
        description="Available booking systems"
    )
    custodians: list[str] = Field(
        default_factory=lambda: ["BNY Mellon", "State Street", "Northern Trust", "JP Morgan"],
        description="Available custodians"
    )
    counterparties: list[str] = Field(
        default_factory=lambda: ["Goldman Sachs", "Morgan Stanley", "Citadel", "Blackrock", "Vanguard"],
        description="Available counterparties"
    )
    securities: list[dict[str, str]] = Field(
        default_factory=lambda: [
            {"cusip": "037833100", "ticker": "AAPL", "name": "Apple Inc"},
            {"cusip": "594918104", "ticker": "MSFT", "name": "Microsoft Corp"},
            {"cusip": "88160R101", "ticker": "TSLA", "name": "Tesla Inc"},
            {"cusip": "912828ZT7", "ticker": "UST10Y", "name": "US Treasury 10Y"},
            {"cusip": "78462F103", "ticker": "SPY", "name": "SPDR S&P 500"},
        ],
        description="Sample securities"
    )


class HealthcareEntityTemplates(BaseModel):
    """Healthcare-specific entity templates."""
    
    patient_id_prefix: str = Field(default="PAT", description="Patient ID prefix")
    encounter_id_prefix: str = Field(default="ENC", description="Encounter ID prefix")
    claim_id_prefix: str = Field(default="CLM", description="Claim ID prefix")
    auth_id_prefix: str = Field(default="AUTH", description="Authorization ID prefix")
    provider_id_prefix: str = Field(default="PRV", description="Provider ID prefix")
    
    facilities: list[str] = Field(
        default_factory=lambda: ["Main Hospital", "Urgent Care Center", "Specialty Clinic", "Imaging Center"],
        description="Available facilities"
    )
    payers: list[str] = Field(
        default_factory=lambda: ["Blue Cross", "Aetna", "UnitedHealth", "Cigna", "Medicare"],
        description="Available payers"
    )


class InsuranceEntityTemplates(BaseModel):
    """Insurance-specific entity templates."""
    
    claim_id_prefix: str = Field(default="INS-CLM", description="Claim ID prefix")
    policy_id_prefix: str = Field(default="POL", description="Policy ID prefix")
    premium_id_prefix: str = Field(default="PREM", description="Premium ID prefix")
    member_id_prefix: str = Field(default="MBR", description="Member ID prefix")
    
    coverage_types: list[str] = Field(
        default_factory=lambda: ["Auto", "Home", "Life", "Health", "Commercial"],
        description="Coverage types"
    )


class RetailEntityTemplates(BaseModel):
    """Retail-specific entity templates."""
    
    order_id_prefix: str = Field(default="RET-ORD", description="Order ID prefix")
    payment_id_prefix: str = Field(default="PAY", description="Payment ID prefix")
    shipment_id_prefix: str = Field(default="SHIP", description="Shipment ID prefix")
    refund_id_prefix: str = Field(default="REF", description="Refund ID prefix")
    customer_id_prefix: str = Field(default="CUST", description="Customer ID prefix")
    
    channels: list[str] = Field(
        default_factory=lambda: ["Web", "Mobile", "Store", "Marketplace"],
        description="Sales channels"
    )


class SaaSEntityTemplates(BaseModel):
    """SaaS/Ops-specific entity templates."""
    
    incident_id_prefix: str = Field(default="INC", description="Incident ID prefix")
    alert_id_prefix: str = Field(default="ALT", description="Alert ID prefix")
    cluster_id_prefix: str = Field(default="CLU", description="Cluster ID prefix")
    deployment_id_prefix: str = Field(default="DEP", description="Deployment ID prefix")
    
    services: list[str] = Field(
        default_factory=lambda: ["api-gateway", "auth-service", "payment-service", "user-service", "notification-service"],
        description="Service names"
    )
    regions: list[str] = Field(
        default_factory=lambda: ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
        description="Deployment regions"
    )


# =============================================================================
# Tool Simulation Models
# =============================================================================


class LatencyRange(BaseModel):
    """Latency range for simulation."""
    
    min: int = Field(default=100, ge=0, description="Minimum latency in milliseconds")
    max: int = Field(default=500, ge=0, description="Maximum latency in milliseconds")


class ToolSimulationConfig(BaseModel):
    """Tool simulation configuration."""
    
    profile: SimulationProfile = Field(default=SimulationProfile.SUCCESS, description="Simulation profile")
    latency: LatencyRange = Field(default_factory=LatencyRange, description="Latency range")
    result_template: dict[str, Any] = Field(default_factory=dict, description="Response template")
    failure_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Failure rate for flaky profile")


class DemoToolDefinition(BaseModel):
    """Demo tool definition with simulation support."""
    
    tool_key: str = Field(..., description="Unique tool identifier")
    name: str = Field(..., description="Tool display name")
    description: str = Field(default="", description="Tool description")
    execution_mode: ExecutionMode = Field(default=ExecutionMode.SIMULATE, description="Execution mode")
    simulation: ToolSimulationConfig = Field(default_factory=ToolSimulationConfig, description="Simulation config")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="Input JSON schema")
    output_schema: dict[str, Any] = Field(default_factory=dict, description="Output JSON schema")


# =============================================================================
# Playbook Models
# =============================================================================


class PlaybookStepDefinition(BaseModel):
    """Playbook step definition."""
    
    step_order: int = Field(..., ge=1, description="Step execution order")
    name: str = Field(..., description="Step name")
    action_type: str = Field(..., description="Action type (call_tool, notify, escalate, etc.)")
    tool_key: Optional[str] = Field(default=None, description="Tool to invoke if action_type=call_tool")
    params: dict[str, Any] = Field(default_factory=dict, description="Step parameters")
    on_success: Optional[str] = Field(default=None, description="Next step on success")
    on_failure: Optional[str] = Field(default=None, description="Next step on failure")


class DemoPlaybookDefinition(BaseModel):
    """Demo playbook definition."""
    
    playbook_key: str = Field(..., description="Unique playbook identifier")
    name: str = Field(..., description="Playbook display name")
    description: str = Field(default="", description="Playbook description")
    industry: Industry = Field(..., description="Target industry")
    exception_types: list[str] = Field(..., description="Exception types this playbook handles")
    severity_levels: list[str] = Field(default_factory=lambda: ["low", "medium", "high", "critical"])
    steps: list[PlaybookStepDefinition] = Field(..., description="Playbook steps")
    tools_required: list[str] = Field(default_factory=list, description="Tool keys required by this playbook")


# =============================================================================
# Scenario Models
# =============================================================================


class WeightedChoice(BaseModel):
    """Weighted choice for random selection."""
    
    value: str = Field(..., description="Choice value")
    weight: float = Field(default=1.0, ge=0.0, description="Selection weight")


class ScenarioWeights(BaseModel):
    """Weights for exception generation in a scenario."""
    
    exception_types: list[WeightedChoice] = Field(..., description="Exception type weights")
    sources: list[WeightedChoice] = Field(default_factory=list, description="Source system weights")
    severities: list[WeightedChoice] = Field(
        default_factory=lambda: [
            WeightedChoice(value="low", weight=0.3),
            WeightedChoice(value="medium", weight=0.4),
            WeightedChoice(value="high", weight=0.2),
            WeightedChoice(value="critical", weight=0.1),
        ]
    )
    statuses: list[WeightedChoice] = Field(
        default_factory=lambda: [
            WeightedChoice(value="open", weight=0.4),
            WeightedChoice(value="analyzing", weight=0.3),
            WeightedChoice(value="resolved", weight=0.2),
            WeightedChoice(value="escalated", weight=0.1),
        ]
    )


class PlaybookBinding(BaseModel):
    """Binding between exception type and playbook."""
    
    exception_type: str = Field(..., description="Exception type pattern")
    playbook_key: str = Field(..., description="Playbook to use")


class ToolBinding(BaseModel):
    """Binding between playbook and tools."""
    
    playbook_key: str = Field(..., description="Playbook key")
    tool_keys: list[str] = Field(..., description="Tool keys used by playbook")


class TimelineEvent(BaseModel):
    """Timeline event template."""
    
    event_type: str = Field(..., description="Event type")
    actor_type: str = Field(default="agent", description="Actor type (agent, user, system)")
    actor_id: Optional[str] = Field(default=None, description="Specific actor ID")
    delay_seconds_min: int = Field(default=0, ge=0, description="Minimum delay after previous event")
    delay_seconds_max: int = Field(default=60, ge=0, description="Maximum delay after previous event")
    payload_template: dict[str, Any] = Field(default_factory=dict, description="Event payload template")


class DemoScenario(BaseModel):
    """Demo scenario configuration."""
    
    scenario_id: str = Field(..., description="Unique scenario identifier")
    name: str = Field(..., description="Scenario display name")
    description: str = Field(default="", description="Scenario description")
    industry: Industry = Field(..., description="Target industry")
    weights: ScenarioWeights = Field(..., description="Generation weights")
    entity_templates: dict[str, Any] = Field(default_factory=dict, description="Entity generation templates")
    playbook_bindings: list[PlaybookBinding] = Field(default_factory=list, description="Playbook bindings")
    tool_bindings: list[ToolBinding] = Field(default_factory=list, description="Tool bindings")
    timeline_template: list[TimelineEvent] = Field(default_factory=list, description="Timeline event template")
    tags: list[str] = Field(default_factory=list, description="Scenario tags")


# =============================================================================
# Domain Pack Models (simplified for demo)
# =============================================================================


class DemoDomainPack(BaseModel):
    """Simplified domain pack for demo catalog."""
    
    domain_name: str = Field(..., description="Domain name")
    version: str = Field(default="1.0.0", description="Pack version")
    industry: Industry = Field(..., description="Industry classification")
    exception_types: list[str] = Field(..., description="Supported exception types")
    tools: list[DemoToolDefinition] = Field(default_factory=list, description="Domain tools")
    playbooks: list[DemoPlaybookDefinition] = Field(default_factory=list, description="Domain playbooks")


# =============================================================================
# Main Catalog Model
# =============================================================================


class DemoCatalog(BaseModel):
    """Complete demo catalog structure."""
    
    version: str = Field(..., description="Catalog version")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
    
    demo_tenants: list[DemoTenant] = Field(..., description="Demo tenant configurations")
    domain_packs: list[DemoDomainPack] = Field(default_factory=list, description="Domain pack library")
    scenarios: list[DemoScenario] = Field(..., description="Demo scenarios")
    
    # Finance-specific templates
    finance_templates: Optional[FinanceEntityTemplates] = Field(
        default_factory=FinanceEntityTemplates,
        description="Finance entity templates"
    )
    
    # Healthcare-specific templates
    healthcare_templates: Optional[HealthcareEntityTemplates] = Field(
        default_factory=HealthcareEntityTemplates,
        description="Healthcare entity templates"
    )
    
    # Insurance-specific templates
    insurance_templates: Optional[InsuranceEntityTemplates] = Field(
        default_factory=InsuranceEntityTemplates,
        description="Insurance entity templates"
    )
    
    # Retail-specific templates
    retail_templates: Optional[RetailEntityTemplates] = Field(
        default_factory=RetailEntityTemplates,
        description="Retail entity templates"
    )
    
    # SaaS/Ops-specific templates
    saas_templates: Optional[SaaSEntityTemplates] = Field(
        default_factory=SaaSEntityTemplates,
        description="SaaS/Ops entity templates"
    )


# =============================================================================
# Demo Settings Models
# =============================================================================


class DemoSettings(BaseModel):
    """Demo system settings (stored in platform_settings)."""
    
    enabled: bool = Field(default=False, description="Demo mode enabled")
    catalog_path: str = Field(default="./demo/demoCatalog.json", description="Catalog file path")
    catalog_version: Optional[str] = Field(default=None, description="Current catalog version")
    bootstrap_on_start: bool = Field(default=True, description="Bootstrap demo data on startup")
    
    scenarios_enabled: bool = Field(default=True, description="Scenario generation enabled")
    scenarios_mode: DemoScenarioMode = Field(default=DemoScenarioMode.CONTINUOUS, description="Default scenario mode")
    scenarios_active: list[str] = Field(default_factory=list, description="Active scenario IDs")
    scenarios_tenants: list[str] = Field(default_factory=list, description="Target tenant keys (empty=all)")
    
    frequency_seconds: int = Field(default=120, ge=1, description="Generation frequency")
    duration_seconds: int = Field(default=120, ge=1, description="Scheduled run duration")
    burst_count: int = Field(default=25, ge=1, description="Burst mode exception count")
    intensity_multiplier: float = Field(default=1.0, ge=0.1, le=10.0, description="Intensity multiplier")
    
    last_run_at: Optional[datetime] = Field(default=None, description="Last scenario run timestamp")
    bootstrap_last_at: Optional[datetime] = Field(default=None, description="Last bootstrap timestamp")


class DemoRunState(BaseModel):
    """Demo run state for API responses."""
    
    run_id: str = Field(..., description="Run identifier")
    status: str = Field(..., description="Run status")
    mode: DemoScenarioMode = Field(..., description="Run mode")
    scenario_ids: list[str] = Field(default_factory=list)
    tenant_keys: list[str] = Field(default_factory=list)
    frequency_seconds: Optional[int] = None
    duration_seconds: Optional[int] = None
    burst_count: Optional[int] = None
    started_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    generated_count: int = 0
    last_tick_at: Optional[datetime] = None
    error: Optional[str] = None


class DemoStatus(BaseModel):
    """Demo system status for API responses."""
    
    enabled: bool = Field(..., description="Demo mode enabled")
    bootstrap_complete: bool = Field(default=False, description="Bootstrap has been run")
    bootstrap_last_at: Optional[datetime] = Field(default=None)
    
    tenant_count: int = Field(default=0, description="Number of demo tenants")
    exception_count: int = Field(default=0, description="Number of demo exceptions")
    playbook_count: int = Field(default=0, description="Number of demo playbooks")
    tool_count: int = Field(default=0, description="Number of demo tools")
    
    scenarios_available: list[str] = Field(default_factory=list, description="Available scenario IDs")
    scenarios_active: list[str] = Field(default_factory=list, description="Currently active scenarios")
    
    active_run: Optional[DemoRunState] = Field(default=None, description="Currently active run")
