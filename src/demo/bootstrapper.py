"""
Demo Bootstrapper Service - Idempotent demo data setup.

Handles creation of demo tenants, packs, playbooks, tools, and exceptions
with idempotent operations and full audit support.
"""

import logging
import os
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.demo.catalog_loader import DemoCatalogLoader, CatalogLoadError
from src.demo.catalog_types import (
    DemoCatalog,
    DemoPlaybookDefinition,
    DemoScenario,
    DemoTenant,
    DemoToolDefinition,
    ExecutionMode,
    Industry,
    SimulationProfile,
)
from src.infrastructure.db.models import (
    DemoRunMode,
    ExceptionSeverity,
    ExceptionStatus,
    SimulateProfile,
    TenantStatus,
    ToolExecutionMode,
)
from src.infrastructure.repositories.onboarding_domain_pack_repository import DomainPackRepository
from src.infrastructure.repositories.platform_settings_repository import PlatformSettingsRepository
from src.infrastructure.repositories.playbook_repository import PlaybookRepository
from src.infrastructure.repositories.playbook_step_repository import PlaybookStepRepository
from src.infrastructure.repositories.tenant_policy_pack_repository import TenantPolicyPackRepository
from src.infrastructure.repositories.tenant_repository import TenantRepository
from src.infrastructure.repositories.onboarding_tenant_pack_repository import TenantPackRepository
from src.infrastructure.repositories.tool_definition_repository import ToolDefinitionRepository
from src.infrastructure.repositories.tool_enablement_repository import ToolEnablementRepository
from src.repository.dto import (
    ExceptionCreateDTO,
    ExceptionEventCreateDTO,
    ExceptionFilter,
    PlaybookCreateDTO,
    PlaybookStepCreateDTO,
    ToolDefinitionCreateDTO,
)
from src.repository.exceptions_repository import ExceptionRepository
from src.repository.exception_events_repository import ExceptionEventRepository

logger = logging.getLogger(__name__)


# Default demo settings keys
DEMO_SETTINGS_DEFAULTS = {
    "demo.enabled": (False, "boolean", "Enable demo mode"),
    "demo.catalog.path": ("./demo/demoCatalog.json", "string", "Path to demo catalog file"),
    "demo.catalog.version": (None, "string", "Current catalog version"),
    "demo.bootstrap.onStart": (True, "boolean", "Bootstrap demo data on startup"),
    "demo.scenarios.enabled": (True, "boolean", "Enable scenario generation"),
    "demo.scenarios.mode": ("continuous", "string", "Default scenario mode"),
    "demo.scenarios.active": ([], "json", "Active scenario IDs"),
    "demo.scenarios.tenants": ([], "json", "Target tenant keys (empty=all)"),
    "demo.scenarios.frequencySeconds": (120, "number", "Generation frequency"),
    "demo.scenarios.durationSeconds": (120, "number", "Scheduled run duration"),
    "demo.scenarios.burstCount": (25, "number", "Burst mode count"),
    "demo.scenarios.intensityMultiplier": (1.0, "number", "Intensity multiplier"),
    "demo.scenarios.lastRunAt": (None, "timestamp", "Last scenario run timestamp"),
    "demo.bootstrap.lastAt": (None, "timestamp", "Last bootstrap timestamp"),
}


class DemoBootstrapperService:
    """
    Idempotent demo data bootstrapper.
    
    Ensures demo tenants, packs, playbooks, tools, and exceptions exist
    without duplicating data.
    """
    
    # Required demo tenants
    REQUIRED_TENANTS = [
        DemoTenant(
            tenant_key="ACME_CAPITAL",
            display_name="Acme Capital Management",
            industry=Industry.FINANCE,
            tags=["demo", "finance"],
        ),
        DemoTenant(
            tenant_key="SHIELDSURE_INSURANCE",
            display_name="ShieldSure Insurance Co",
            industry=Industry.INSURANCE,
            tags=["demo", "insurance"],
        ),
        DemoTenant(
            tenant_key="CAREBRIDGE_HEALTH",
            display_name="CareBridge Health Systems",
            industry=Industry.HEALTHCARE,
            tags=["demo", "healthcare"],
        ),
        DemoTenant(
            tenant_key="GLOBALRETAIL_LTD",
            display_name="GlobalRetail Ltd",
            industry=Industry.RETAIL,
            tags=["demo", "retail"],
        ),
        DemoTenant(
            tenant_key="CLOUDOPS_PRO",
            display_name="CloudOps Pro Services",
            industry=Industry.SAAS_OPS,
            tags=["demo", "saas_ops"],
        ),
    ]
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
        # Initialize repositories
        self.settings_repo = PlatformSettingsRepository(session)
        self.tenant_repo = TenantRepository(session)
        self.domain_pack_repo = DomainPackRepository(session)
        self.tenant_policy_repo = TenantPolicyPackRepository(session)
        self.playbook_repo = PlaybookRepository(session)
        self.playbook_step_repo = PlaybookStepRepository(session)
        self.tool_def_repo = ToolDefinitionRepository(session)
        self.tool_enablement_repo = ToolEnablementRepository(session)
        self.exception_repo = ExceptionRepository(session)
        self.event_repo = ExceptionEventRepository(session)
        self.tenant_pack_repo = TenantPackRepository(session)
        
        self._catalog: Optional[DemoCatalog] = None
    
    async def bootstrap(self, force: bool = False) -> dict[str, Any]:
        """
        Run full demo bootstrap.
        
        Args:
            force: Force bootstrap even if already done.
            
        Returns:
            Bootstrap result summary.
        """
        result = {
            "success": True,
            "tenants_created": 0,
            "tenants_existing": 0,
            "domain_packs_created": 0,
            "tenant_packs_created": 0,
            "playbooks_created": 0,
            "tools_created": 0,
            "exceptions_created": 0,
            "errors": [],
        }
        
        try:
            # Check if demo mode is enabled
            enabled = await self.settings_repo.get_value("demo.enabled", False)
            if not enabled and not force:
                logger.info("Demo mode is disabled, skipping bootstrap")
                result["success"] = True
                result["message"] = "Demo mode disabled"
                return result
            
            # Ensure default settings exist
            await self._ensure_default_settings()
            
            # Load catalog
            try:
                catalog_path = await self.settings_repo.get_value(
                    "demo.catalog.path",
                    "./demo/demoCatalog.json"
                )
                self._catalog = DemoCatalogLoader.load(catalog_path)
            except CatalogLoadError as e:
                logger.warning(f"Could not load demo catalog: {e}. Using built-in defaults.")
                self._catalog = None
            
            # Create demo tenants
            tenants_result = await self._ensure_demo_tenants()
            result["tenants_created"] = tenants_result["created"]
            result["tenants_existing"] = tenants_result["existing"]
            
            # Create domain packs for each industry
            packs_result = await self._ensure_domain_packs()
            result["domain_packs_created"] = packs_result["created"]
            
            # Create tenant packs for each demo tenant
            for tenant in self.REQUIRED_TENANTS:
                tenant_pack_count = await self._ensure_tenant_pack(tenant)
                result["tenant_packs_created"] += tenant_pack_count
            
            # Create playbooks for each tenant
            for tenant in self.REQUIRED_TENANTS:
                playbook_count = await self._ensure_tenant_playbooks(tenant)
                result["playbooks_created"] += playbook_count
            
            # Create tools for each tenant
            for tenant in self.REQUIRED_TENANTS:
                tool_count = await self._ensure_tenant_tools(tenant)
                result["tools_created"] += tool_count
            
            # Seed exceptions for each tenant
            for tenant in self.REQUIRED_TENANTS:
                exc_count = await self._seed_tenant_exceptions(tenant)
                result["exceptions_created"] += exc_count
            
            # Update bootstrap timestamp
            await self.settings_repo.set(
                "demo.bootstrap.lastAt",
                datetime.now(timezone.utc),
                value_type="timestamp",
                updated_by="demo_bootstrapper",
            )
            
            await self.session.commit()
            
            logger.info(
                f"Demo bootstrap complete: "
                f"{result['tenants_created']} tenants created, "
                f"{result['playbooks_created']} playbooks, "
                f"{result['tools_created']} tools, "
                f"{result['exceptions_created']} exceptions"
            )
            
        except Exception as e:
            logger.error(f"Demo bootstrap failed: {e}", exc_info=True)
            result["success"] = False
            result["errors"].append(str(e))
            await self.session.rollback()
        
        return result
    
    async def _ensure_default_settings(self) -> None:
        """Ensure default demo settings exist from env vars."""
        env_defaults = {
            "demo.enabled": (
                os.getenv("DEMO_MODE_DEFAULT", "false").lower() == "true",
                "boolean",
                "Enable demo mode",
            ),
            "demo.catalog.path": (
                os.getenv("DEMO_CATALOG_PATH", "./demo/demoCatalog.json"),
                "string",
                "Path to demo catalog file",
            ),
            "demo.bootstrap.onStart": (
                os.getenv("DEMO_BOOTSTRAP_ON_START", "true").lower() == "true",
                "boolean",
                "Bootstrap demo data on startup",
            ),
            "demo.scenarios.enabled": (
                os.getenv("DEMO_SCENARIOS_DEFAULT", "true").lower() == "true",
                "boolean",
                "Enable scenario generation",
            ),
            "demo.scenarios.mode": (
                os.getenv("DEMO_SCENARIO_MODE_DEFAULT", "continuous"),
                "string",
                "Default scenario mode",
            ),
            "demo.scenarios.frequencySeconds": (
                int(os.getenv("DEMO_SCENARIO_FREQUENCY_SECONDS", "120")),
                "number",
                "Generation frequency in seconds",
            ),
            "demo.scenarios.durationSeconds": (
                int(os.getenv("DEMO_SCENARIO_DURATION_SECONDS", "120")),
                "number",
                "Scheduled run duration in seconds",
            ),
            "demo.scenarios.burstCount": (
                int(os.getenv("DEMO_SCENARIO_BURST_COUNT", "25")),
                "number",
                "Burst mode exception count",
            ),
        }
        
        await self.settings_repo.ensure_defaults(env_defaults, updated_by="env_bootstrap")
    
    async def _ensure_demo_tenants(self) -> dict[str, int]:
        """Ensure all required demo tenants exist."""
        result = {"created": 0, "existing": 0}
        
        # Combine required tenants with catalog tenants
        tenants_to_create = list(self.REQUIRED_TENANTS)
        
        if self._catalog:
            for cat_tenant in self._catalog.demo_tenants:
                if not any(t.tenant_key == cat_tenant.tenant_key for t in tenants_to_create):
                    tenants_to_create.append(cat_tenant)
        
        for tenant in tenants_to_create:
            existing = await self.tenant_repo.get_tenant(tenant.tenant_key)
            
            if existing:
                result["existing"] += 1
                # Update tags and industry if needed
                if existing.tags != tenant.tags or existing.industry != tenant.industry.value:
                    from src.infrastructure.db.models import Tenant as TenantModel
                    existing.tags = tenant.tags
                    existing.industry = tenant.industry.value
                    await self.session.flush()
            else:
                from src.infrastructure.db.models import Tenant as TenantModel
                new_tenant = TenantModel(
                    tenant_id=tenant.tenant_key,
                    name=tenant.display_name,
                    status=TenantStatus.ACTIVE,
                    tags=tenant.tags,
                    industry=tenant.industry.value,
                    metadata=tenant.metadata or {},
                )
                self.session.add(new_tenant)
                result["created"] += 1
                logger.info(f"Created demo tenant: {tenant.tenant_key}")
        
        await self.session.flush()
        return result
    
    async def _ensure_domain_packs(self) -> dict[str, int]:
        """Ensure domain packs exist for each industry."""
        from src.infrastructure.db.models import PackStatus
        
        result = {"created": 0}
        
        industry_domain_map = {
            Industry.FINANCE: "CapitalMarketsTrading",
            Industry.HEALTHCARE: "HealthcareClaimsAndCareOps",
            Industry.INSURANCE: "InsuranceClaimsProcessing",
            Industry.RETAIL: "RetailOperations",
            Industry.SAAS_OPS: "SaaSOperations",
        }
        
        for industry, domain in industry_domain_map.items():
            existing = await self.domain_pack_repo.get_latest_version(domain)
            
            if not existing:
                # Create minimal domain pack
                pack_json = self._create_minimal_domain_pack(domain, industry)
                domain_pack = await self.domain_pack_repo.create_domain_pack(
                    domain=domain,
                    version="1.0",
                    content_json=pack_json,
                    created_by="demo_bootstrap",
                )
                # Activate the domain pack immediately
                await self.domain_pack_repo.update_pack_status(
                    pack_id=domain_pack.id,
                    status=PackStatus.ACTIVE,
                )
                result["created"] += 1
                logger.info(f"Created and activated domain pack: {domain}")
        
        return result
    
    def _create_minimal_domain_pack(self, domain: str, industry: Industry) -> dict[str, Any]:
        """Create a minimal domain pack for an industry."""
        exception_types = self._get_exception_types_for_industry(industry)
        
        return {
            "domainName": domain,
            "version": "1.0.0",
            "entities": {},
            "exceptionTypes": {et: {"name": et, "description": f"{et} exception"} for et in exception_types},
            "severityRules": [],
            "tools": {},
            "playbooks": [],
            "guardrails": {
                "allowLists": {"tools": [], "actions": []},
                "blockLists": {"tools": [], "actions": []},
            },
        }
    
    def _get_exception_types_for_industry(self, industry: Industry) -> list[str]:
        """Get exception types for an industry."""
        types_map = {
            Industry.FINANCE: [
                "FIN_SETTLEMENT_FAIL",
                "FIN_FAILED_ALLOCATION",
                "FIN_POSITION_BREAK",
                "FIN_NOSTRO_MISMATCH",
                "FIN_REG_REPORT_REJECTED",
                "FIN_TRADE_VALIDATION_ERROR",
                "FIN_CASH_MOVEMENT_ERROR",
            ],
            Industry.HEALTHCARE: [
                "HLTH_CLAIM_MISSING_AUTH",
                "HLTH_CLAIM_CODE_MISMATCH",
                "HLTH_PROVIDER_CREDENTIAL_EXPIRED",
                "HLTH_PATIENT_DEMOGRAPHIC_CONFLICT",
                "HLTH_PHARMACY_DUPLICATE_THERAPY",
                "HLTH_ELIGIBILITY_COVERAGE_LAPSE",
            ],
            Industry.INSURANCE: [
                "INS_CLAIM_VALIDATION_ERROR",
                "INS_POLICY_COVERAGE_MISMATCH",
                "INS_PREMIUM_CALCULATION_ERROR",
                "INS_FRAUD_DETECTION_ALERT",
                "INS_DOCUMENT_MISSING",
            ],
            Industry.RETAIL: [
                "RET_ORDER_FULFILLMENT_ERROR",
                "RET_PAYMENT_PROCESSING_FAIL",
                "RET_INVENTORY_MISMATCH",
                "RET_SHIPMENT_DELIVERY_FAIL",
                "RET_REFUND_PROCESSING_ERROR",
            ],
            Industry.SAAS_OPS: [
                "OPS_SERVICE_DEGRADATION",
                "OPS_DEPLOYMENT_FAILURE",
                "OPS_SECURITY_ALERT",
                "OPS_RESOURCE_EXHAUSTION",
                "OPS_DATA_SYNC_ERROR",
            ],
        }
        return types_map.get(industry, [])
    
    async def _ensure_tenant_pack(self, tenant: DemoTenant) -> int:
        """Ensure tenant pack exists for a demo tenant."""
        # Check if tenant pack already exists
        existing = await self.tenant_pack_repo.get_latest_version(tenant.tenant_key)
        
        if existing:
            logger.debug(f"Tenant pack already exists for {tenant.tenant_key}")
            return 0
        
        # Create tenant pack for this tenant
        industry_domain_map = {
            Industry.FINANCE: "CapitalMarketsTrading",
            Industry.HEALTHCARE: "HealthcareClaimsAndCareOps",
            Industry.INSURANCE: "InsuranceClaimsProcessing",
            Industry.RETAIL: "RetailOperations",
            Industry.SAAS_OPS: "SaaSOperations",
        }
        
        domain = industry_domain_map.get(tenant.industry, "General")
        exception_types = self._get_exception_types_for_industry(tenant.industry)
        
        # Create tenant pack content
        pack_content = {
            "tenantId": tenant.tenant_key,
            "domainName": domain,
            "customSeverityOverrides": [
                {"exceptionType": exception_types[0], "severity": "HIGH"} if exception_types else {}
            ],
            "customGuardrails": {
                "allowLists": [],
                "blockLists": [],
                "humanApprovalThreshold": 0.75,
            },
            "approvedTools": self._get_approved_tools_for_industry(tenant.industry),
            "humanApprovalRules": [
                {"severity": "CRITICAL", "requireApproval": True},
                {"severity": "HIGH", "requireApproval": False},
                {"severity": "MEDIUM", "requireApproval": False},
                {"severity": "LOW", "requireApproval": False},
            ],
            "retentionPolicies": {
                "dataTTL": 90,
            },
            "customPlaybooks": [],
        }
        
        await self.tenant_pack_repo.create_tenant_pack(
            tenant_id=tenant.tenant_key,
            version="v1.0",
            content_json=pack_content,
            created_by="demo_bootstrapper",
        )
        
        logger.info(f"Created tenant pack for {tenant.tenant_key}")
        return 1
    
    def _get_approved_tools_for_industry(self, industry: Industry) -> list[str]:
        """Get approved tool names for an industry's tenant pack."""
        tools_map = {
            Industry.FINANCE: [
                "getOrder", "getExecutions", "getAllocations", "getPositions",
                "getCashMovements", "getSettlement", "repairAllocation",
                "triggerSettlementRetry", "recalculatePosition", "regenerateRegReport",
                "openCase", "assignCase", "escalateCase",
            ],
            Industry.HEALTHCARE: [
                "getClaimDetails", "getPatientInfo", "getAuthorizationStatus",
                "getCoverageDetails", "getClinicalNotes", "resubmitClaim",
                "requestAuth", "updatePatientInfo", "openCase", "escalateCase",
            ],
            Industry.INSURANCE: [
                "getClaimDetails", "getPolicyInfo", "getCoverageDetails",
                "getFraudScore", "getClaimHistory", "reprocessClaim",
                "requestDocuments", "escalateClaim", "openCase", "assignCase",
            ],
            Industry.RETAIL: [
                "getOrderDetails", "getInventoryStatus", "getShipmentInfo",
                "getPaymentStatus", "getRefundHistory", "reprocessOrder",
                "updateInventory", "retryPayment", "openCase", "escalateCase",
            ],
            Industry.SAAS_OPS: [
                "getServiceStatus", "getResourceMetrics", "getDeploymentLogs",
                "getAlertHistory", "getIncidentDetails", "restartService",
                "scaleResources", "rollbackDeployment", "openCase", "escalateCase",
            ],
        }
        return tools_map.get(industry, [])
    
    async def _ensure_tenant_playbooks(self, tenant: DemoTenant) -> int:
        """Ensure playbooks exist for a tenant."""
        created = 0
        
        playbooks = self._get_playbooks_for_industry(tenant.industry)
        
        for playbook_def in playbooks:
            # Check if playbook exists
            existing = await self.playbook_repo.get_playbook_by_name(
                tenant.tenant_key,
                playbook_def.name,
            )
            
            if not existing:
                conditions = {
                    "match": {
                        "exception_types": playbook_def.exception_types,
                        "severity_in": playbook_def.severity_levels,
                    },
                    "priority": 10,
                }
                
                playbook = await self.playbook_repo.create_playbook(
                    tenant_id=tenant.tenant_key,
                    playbook_data=PlaybookCreateDTO(
                        name=playbook_def.name,
                        version=1,
                        conditions=conditions,
                    ),
                )
                
                # Create steps
                for step_def in playbook_def.steps:
                    await self.playbook_step_repo.create_step(
                        playbook_id=playbook.playbook_id,
                        step_data=PlaybookStepCreateDTO(
                            name=step_def.name,
                            action_type=step_def.action_type,
                            params={
                                "tool_key": step_def.tool_key,
                                **step_def.params,
                            },
                        ),
                        tenant_id=tenant.tenant_key,
                    )
                
                created += 1
                logger.debug(f"Created playbook: {playbook_def.name} for {tenant.tenant_key}")
        
        return created
    
    def _get_playbooks_for_industry(self, industry: Industry) -> list[DemoPlaybookDefinition]:
        """
        Get production-quality playbook definitions for an industry.
        
        These playbooks represent realistic exception resolution workflows
        that would be used in enterprise environments.
        """
        from src.demo.catalog_types import PlaybookStepDefinition
        
        if industry == Industry.FINANCE:
            return [
                # Playbook 1: Trade Settlement Failure Resolution
                DemoPlaybookDefinition(
                    playbook_key="PB_TRADE_SETTLEMENT_RESOLUTION",
                    name="Trade Settlement Failure Resolution",
                    description="End-to-end resolution workflow for failed trade settlements, covering validation, counterparty checks, and automated repair",
                    industry=Industry.FINANCE,
                    exception_types=["FIN_SETTLEMENT_FAIL"],
                    steps=[
                        PlaybookStepDefinition(
                            step_order=1, 
                            name="Retrieve Trade Details", 
                            action_type="call_tool", 
                            tool_key="GetTradeDetails",
                            params={"include": ["booking", "allocations", "settlement_instructions"]},
                        ),
                        PlaybookStepDefinition(
                            step_order=2, 
                            name="Validate Settlement Instructions", 
                            action_type="call_tool", 
                            tool_key="ValidateSettlementInstructions",
                            params={"check_ssi": True, "verify_counterparty": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=3, 
                            name="Check Counterparty Affirmation Status", 
                            action_type="call_tool", 
                            tool_key="CheckAffirmationStatus",
                            params={"include_history": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=4, 
                            name="Verify Settlement Date Calendar", 
                            action_type="call_tool", 
                            tool_key="CheckSettlementCalendar",
                            params={"calendars": ["TARGET2", "FEDWIRE", "NYSE"]},
                        ),
                        PlaybookStepDefinition(
                            step_order=5, 
                            name="Apply Settlement Correction", 
                            action_type="call_tool", 
                            tool_key="ApplySettlementCorrection",
                            params={"auto_approve": False, "require_4eye": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=6, 
                            name="Resubmit to Settlement System", 
                            action_type="call_tool", 
                            tool_key="ResubmitSettlement",
                            params={"priority": "HIGH", "notify_ops": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=7, 
                            name="Notify Operations Team", 
                            action_type="notify", 
                            params={"channel": "operations", "template": "settlement_resolved"},
                        ),
                    ],
                    tools_required=["GetTradeDetails", "ValidateSettlementInstructions", "CheckAffirmationStatus", "CheckSettlementCalendar", "ApplySettlementCorrection", "ResubmitSettlement"],
                ),
                # Playbook 2: Position Break Investigation
                DemoPlaybookDefinition(
                    playbook_key="PB_POSITION_BREAK_INVESTIGATION",
                    name="Position Break Investigation & Reconciliation",
                    description="Systematic investigation of position discrepancies between internal books and custodian records",
                    industry=Industry.FINANCE,
                    exception_types=["FIN_POSITION_BREAK"],
                    steps=[
                        PlaybookStepDefinition(
                            step_order=1, 
                            name="Extract Internal Position", 
                            action_type="call_tool", 
                            tool_key="GetInternalPosition",
                            params={"as_of": "T-1", "include_pending": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=2, 
                            name="Fetch Custodian Statement", 
                            action_type="call_tool", 
                            tool_key="GetCustodianPosition",
                            params={"source": "SWIFT_MT535", "include_corporate_actions": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=3, 
                            name="Calculate Position Delta", 
                            action_type="call_tool", 
                            tool_key="CalculatePositionDelta",
                            params={"tolerance_pct": 0.01},
                        ),
                        PlaybookStepDefinition(
                            step_order=4, 
                            name="Identify Root Cause", 
                            action_type="call_tool", 
                            tool_key="AnalyzeBreakCause",
                            params={"check_unsettled": True, "check_ca_pending": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=5, 
                            name="Create Reconciliation Adjustment", 
                            action_type="call_tool", 
                            tool_key="CreateReconciliationEntry",
                            params={"require_approval": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=6, 
                            name="Escalate if Unresolved", 
                            action_type="escalate", 
                            params={"team": "middle_office", "severity": "HIGH"},
                        ),
                    ],
                    tools_required=["GetInternalPosition", "GetCustodianPosition", "CalculatePositionDelta", "AnalyzeBreakCause", "CreateReconciliationEntry"],
                ),
                # Playbook 3: Failed Allocation Resolution
                DemoPlaybookDefinition(
                    playbook_key="PB_ALLOCATION_FAILURE_RESOLUTION",
                    name="Trade Allocation Failure Resolution",
                    description="Resolve failed block trade allocations to underlying accounts",
                    industry=Industry.FINANCE,
                    exception_types=["FIN_FAILED_ALLOCATION"],
                    steps=[
                        PlaybookStepDefinition(
                            step_order=1, 
                            name="Get Block Trade Details", 
                            action_type="call_tool", 
                            tool_key="GetBlockTrade",
                            params={"include_allocations": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=2, 
                            name="Validate Account Eligibility", 
                            action_type="call_tool", 
                            tool_key="ValidateAccountEligibility",
                            params={"check_restrictions": True, "check_capacity": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=3, 
                            name="Verify Pro-Rata Calculation", 
                            action_type="call_tool", 
                            tool_key="VerifyAllocationCalc",
                            params={"method": "pro_rata"},
                        ),
                        PlaybookStepDefinition(
                            step_order=4, 
                            name="Correct Allocation Split", 
                            action_type="call_tool", 
                            tool_key="CorrectAllocation",
                            params={"maintain_fairness": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=5, 
                            name="Reprocess Allocations", 
                            action_type="call_tool", 
                            tool_key="ReprocessAllocations",
                            params={"validate_after": True},
                        ),
                    ],
                    tools_required=["GetBlockTrade", "ValidateAccountEligibility", "VerifyAllocationCalc", "CorrectAllocation", "ReprocessAllocations"],
                ),
                # Playbook 4: Regulatory Report Rejection
                DemoPlaybookDefinition(
                    playbook_key="PB_REG_REPORT_REJECTION_FIX",
                    name="Regulatory Report Rejection Resolution",
                    description="Investigate and fix rejected regulatory reports (MiFID II, EMIR, Dodd-Frank)",
                    industry=Industry.FINANCE,
                    exception_types=["FIN_REG_REPORT_REJECTED"],
                    steps=[
                        PlaybookStepDefinition(
                            step_order=1, 
                            name="Parse Rejection Details", 
                            action_type="call_tool", 
                            tool_key="ParseRegReportRejection",
                            params={"include_validation_errors": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=2, 
                            name="Fetch Original Report Data", 
                            action_type="call_tool", 
                            tool_key="GetRegReportData",
                            params={"include_source_trades": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=3, 
                            name="Validate Against Schema", 
                            action_type="call_tool", 
                            tool_key="ValidateReportSchema",
                            params={"schema_version": "latest"},
                        ),
                        PlaybookStepDefinition(
                            step_order=4, 
                            name="Apply Data Corrections", 
                            action_type="call_tool", 
                            tool_key="ApplyReportCorrections",
                            params={"audit_trail": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=5, 
                            name="Resubmit to Regulator", 
                            action_type="call_tool", 
                            tool_key="ResubmitRegReport",
                            params={"include_correction_reason": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=6, 
                            name="Log Compliance Audit Record", 
                            action_type="notify", 
                            params={"channel": "compliance_audit", "template": "reg_report_corrected"},
                        ),
                    ],
                    tools_required=["ParseRegReportRejection", "GetRegReportData", "ValidateReportSchema", "ApplyReportCorrections", "ResubmitRegReport"],
                ),
            ]
        elif industry == Industry.HEALTHCARE:
            return [
                # Playbook 1: Missing Prior Authorization
                DemoPlaybookDefinition(
                    playbook_key="PB_MISSING_PRIOR_AUTH",
                    name="Missing Prior Authorization Resolution",
                    description="Locate and attach missing prior authorization for claim processing",
                    industry=Industry.HEALTHCARE,
                    exception_types=["HLTH_CLAIM_MISSING_AUTH"],
                    steps=[
                        PlaybookStepDefinition(
                            step_order=1, 
                            name="Get Claim Details", 
                            action_type="call_tool", 
                            tool_key="GetClaimDetails",
                            params={"include_procedure_codes": True, "include_diagnosis": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=2, 
                            name="Search Authorization Database", 
                            action_type="call_tool", 
                            tool_key="SearchPriorAuth",
                            params={"search_window_days": 90, "include_expired": False},
                        ),
                        PlaybookStepDefinition(
                            step_order=3, 
                            name="Verify Authorization Match", 
                            action_type="call_tool", 
                            tool_key="VerifyAuthMatch",
                            params={"check_procedure_codes": True, "check_provider": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=4, 
                            name="Link Authorization to Claim", 
                            action_type="call_tool", 
                            tool_key="LinkAuthToClaim",
                            params={"update_claim_status": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=5, 
                            name="Resubmit Claim for Adjudication", 
                            action_type="call_tool", 
                            tool_key="ResubmitClaim",
                            params={"priority": "STANDARD"},
                        ),
                    ],
                    tools_required=["GetClaimDetails", "SearchPriorAuth", "VerifyAuthMatch", "LinkAuthToClaim", "ResubmitClaim"],
                ),
                # Playbook 2: Procedure Code Mismatch
                DemoPlaybookDefinition(
                    playbook_key="PB_PROCEDURE_CODE_MISMATCH",
                    name="Procedure Code Mismatch Resolution",
                    description="Investigate and resolve procedure code discrepancies",
                    industry=Industry.HEALTHCARE,
                    exception_types=["HLTH_CLAIM_CODE_MISMATCH"],
                    steps=[
                        PlaybookStepDefinition(
                            step_order=1, 
                            name="Retrieve Claim & Medical Record", 
                            action_type="call_tool", 
                            tool_key="GetClaimWithMedicalRecord",
                            params={"include_clinical_notes": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=2, 
                            name="Validate CPT/ICD Codes", 
                            action_type="call_tool", 
                            tool_key="ValidateProcedureCodes",
                            params={"check_bundling": True, "check_medical_necessity": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=3, 
                            name="Check Payer Code Requirements", 
                            action_type="call_tool", 
                            tool_key="GetPayerCodeRequirements",
                            params={"payer_specific_rules": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=4, 
                            name="Apply Code Correction", 
                            action_type="call_tool", 
                            tool_key="ApplyCodeCorrection",
                            params={"require_coder_review": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=5, 
                            name="Reprocess Claim", 
                            action_type="call_tool", 
                            tool_key="ResubmitClaim",
                            params={"flag_for_audit": True},
                        ),
                    ],
                    tools_required=["GetClaimWithMedicalRecord", "ValidateProcedureCodes", "GetPayerCodeRequirements", "ApplyCodeCorrection", "ResubmitClaim"],
                ),
                # Playbook 3: Provider Credential Expiration
                DemoPlaybookDefinition(
                    playbook_key="PB_PROVIDER_CREDENTIAL_EXPIRED",
                    name="Provider Credential Expiration Handler",
                    description="Handle claims with expired provider credentials",
                    industry=Industry.HEALTHCARE,
                    exception_types=["HLTH_PROVIDER_CREDENTIAL_EXPIRED"],
                    steps=[
                        PlaybookStepDefinition(
                            step_order=1, 
                            name="Get Provider Details", 
                            action_type="call_tool", 
                            tool_key="GetProviderDetails",
                            params={"include_credentials": True, "include_network_status": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=2, 
                            name="Check Credential Registry", 
                            action_type="call_tool", 
                            tool_key="CheckCredentialRegistry",
                            params={"source": "NPPES", "include_state_license": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=3, 
                            name="Request Credential Update", 
                            action_type="call_tool", 
                            tool_key="RequestCredentialUpdate",
                            params={"send_provider_notification": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=4, 
                            name="Hold Claim Pending Verification", 
                            action_type="call_tool", 
                            tool_key="HoldClaimPending",
                            params={"reason": "CREDENTIAL_VERIFICATION", "hold_days": 30},
                        ),
                        PlaybookStepDefinition(
                            step_order=5, 
                            name="Notify Provider Relations", 
                            action_type="notify", 
                            params={"channel": "provider_relations", "template": "credential_expired"},
                        ),
                    ],
                    tools_required=["GetProviderDetails", "CheckCredentialRegistry", "RequestCredentialUpdate", "HoldClaimPending"],
                ),
            ]
        elif industry == Industry.INSURANCE:
            return [
                # Playbook 1: Claim Validation Error
                DemoPlaybookDefinition(
                    playbook_key="PB_CLAIM_VALIDATION_ERROR",
                    name="Claim Validation Error Resolution",
                    description="Resolve validation errors on insurance claim submissions",
                    industry=Industry.INSURANCE,
                    exception_types=["INS_CLAIM_VALIDATION_ERROR"],
                    steps=[
                        PlaybookStepDefinition(
                            step_order=1, 
                            name="Retrieve Claim & Policy", 
                            action_type="call_tool", 
                            tool_key="GetClaimAndPolicy",
                            params={"include_coverage_details": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=2, 
                            name="Identify Validation Failures", 
                            action_type="call_tool", 
                            tool_key="GetValidationErrors",
                            params={"include_field_level": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=3, 
                            name="Cross-Reference with Policy Terms", 
                            action_type="call_tool", 
                            tool_key="CheckPolicyTerms",
                            params={"check_exclusions": True, "check_limits": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=4, 
                            name="Apply Data Corrections", 
                            action_type="call_tool", 
                            tool_key="ApplyClaimCorrections",
                            params={"log_changes": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=5, 
                            name="Revalidate Claim", 
                            action_type="call_tool", 
                            tool_key="RevalidateClaim",
                            params={"full_validation": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=6, 
                            name="Route to Adjudicator", 
                            action_type="call_tool", 
                            tool_key="RouteToAdjudicator",
                            params={"queue": "STANDARD"},
                        ),
                    ],
                    tools_required=["GetClaimAndPolicy", "GetValidationErrors", "CheckPolicyTerms", "ApplyClaimCorrections", "RevalidateClaim", "RouteToAdjudicator"],
                ),
                # Playbook 2: Fraud Detection Alert
                DemoPlaybookDefinition(
                    playbook_key="PB_FRAUD_ALERT_INVESTIGATION",
                    name="Fraud Alert Investigation",
                    description="Investigate and triage fraud detection alerts on claims",
                    industry=Industry.INSURANCE,
                    exception_types=["INS_FRAUD_DETECTION_ALERT"],
                    steps=[
                        PlaybookStepDefinition(
                            step_order=1, 
                            name="Get Fraud Alert Details", 
                            action_type="call_tool", 
                            tool_key="GetFraudAlertDetails",
                            params={"include_risk_indicators": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=2, 
                            name="Fetch Claimant History", 
                            action_type="call_tool", 
                            tool_key="GetClaimantHistory",
                            params={"lookback_years": 5, "include_related_parties": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=3, 
                            name="Run Enhanced Verification", 
                            action_type="call_tool", 
                            tool_key="RunEnhancedVerification",
                            params={"check_external_databases": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=4, 
                            name="Calculate Risk Score", 
                            action_type="call_tool", 
                            tool_key="CalculateFraudRiskScore",
                            params={"model": "v2_ensemble"},
                        ),
                        PlaybookStepDefinition(
                            step_order=5, 
                            name="Route Based on Risk", 
                            action_type="call_tool", 
                            tool_key="RouteByRiskLevel",
                            params={"high_risk_queue": "SIU", "low_risk_action": "PROCESS"},
                        ),
                    ],
                    tools_required=["GetFraudAlertDetails", "GetClaimantHistory", "RunEnhancedVerification", "CalculateFraudRiskScore", "RouteByRiskLevel"],
                ),
                # Playbook 3: Policy Coverage Mismatch
                DemoPlaybookDefinition(
                    playbook_key="PB_COVERAGE_MISMATCH",
                    name="Policy Coverage Mismatch Resolution",
                    description="Resolve discrepancies between claimed and actual coverage",
                    industry=Industry.INSURANCE,
                    exception_types=["INS_POLICY_COVERAGE_MISMATCH"],
                    steps=[
                        PlaybookStepDefinition(
                            step_order=1, 
                            name="Get Policy Coverage Details", 
                            action_type="call_tool", 
                            tool_key="GetPolicyCoverage",
                            params={"as_of_loss_date": True, "include_endorsements": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=2, 
                            name="Compare Claim to Coverage", 
                            action_type="call_tool", 
                            tool_key="CompareClaimToCoverage",
                            params={"check_sublimits": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=3, 
                            name="Check Policy Amendments", 
                            action_type="call_tool", 
                            tool_key="GetPolicyAmendments",
                            params={"effective_date_check": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=4, 
                            name="Adjust Claim or Deny", 
                            action_type="call_tool", 
                            tool_key="AdjustClaimCoverage",
                            params={"generate_explanation": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=5, 
                            name="Send Coverage Decision Letter", 
                            action_type="notify", 
                            params={"channel": "claimant_correspondence", "template": "coverage_decision"},
                        ),
                    ],
                    tools_required=["GetPolicyCoverage", "CompareClaimToCoverage", "GetPolicyAmendments", "AdjustClaimCoverage"],
                ),
            ]
        elif industry == Industry.RETAIL:
            return [
                # Playbook 1: Order Fulfillment Error
                DemoPlaybookDefinition(
                    playbook_key="PB_ORDER_FULFILLMENT_ERROR",
                    name="Order Fulfillment Error Resolution",
                    description="Resolve errors preventing order fulfillment",
                    industry=Industry.RETAIL,
                    exception_types=["RET_ORDER_FULFILLMENT_ERROR"],
                    steps=[
                        PlaybookStepDefinition(
                            step_order=1, 
                            name="Get Order Details", 
                            action_type="call_tool", 
                            tool_key="GetOrderDetails",
                            params={"include_items": True, "include_shipping": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=2, 
                            name="Check Inventory Availability", 
                            action_type="call_tool", 
                            tool_key="CheckInventoryAvailability",
                            params={"check_all_warehouses": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=3, 
                            name="Identify Fulfillment Blockers", 
                            action_type="call_tool", 
                            tool_key="IdentifyFulfillmentBlockers",
                            params={"check_address": True, "check_payment": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=4, 
                            name="Apply Resolution Action", 
                            action_type="call_tool", 
                            tool_key="ApplyFulfillmentFix",
                            params={"auto_substitute": False},
                        ),
                        PlaybookStepDefinition(
                            step_order=5, 
                            name="Requeue for Fulfillment", 
                            action_type="call_tool", 
                            tool_key="RequeueOrder",
                            params={"expedite": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=6, 
                            name="Notify Customer if Delayed", 
                            action_type="notify", 
                            params={"channel": "customer_service", "template": "order_delay"},
                        ),
                    ],
                    tools_required=["GetOrderDetails", "CheckInventoryAvailability", "IdentifyFulfillmentBlockers", "ApplyFulfillmentFix", "RequeueOrder"],
                ),
                # Playbook 2: Payment Processing Failure
                DemoPlaybookDefinition(
                    playbook_key="PB_PAYMENT_FAILURE",
                    name="Payment Processing Failure Resolution",
                    description="Handle failed payment transactions",
                    industry=Industry.RETAIL,
                    exception_types=["RET_PAYMENT_PROCESSING_FAIL"],
                    steps=[
                        PlaybookStepDefinition(
                            step_order=1, 
                            name="Get Payment Transaction Details", 
                            action_type="call_tool", 
                            tool_key="GetPaymentDetails",
                            params={"include_gateway_response": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=2, 
                            name="Analyze Failure Reason", 
                            action_type="call_tool", 
                            tool_key="AnalyzePaymentFailure",
                            params={"check_fraud_flags": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=3, 
                            name="Attempt Alternative Payment Method", 
                            action_type="call_tool", 
                            tool_key="TryAlternativePayment",
                            params={"fallback_methods": ["backup_card", "paypal"]},
                        ),
                        PlaybookStepDefinition(
                            step_order=4, 
                            name="Request Customer Action", 
                            action_type="call_tool", 
                            tool_key="SendPaymentUpdateRequest",
                            params={"template": "payment_failed"},
                        ),
                        PlaybookStepDefinition(
                            step_order=5, 
                            name="Hold Order Pending Payment", 
                            action_type="call_tool", 
                            tool_key="HoldOrderPendingPayment",
                            params={"hold_hours": 48},
                        ),
                    ],
                    tools_required=["GetPaymentDetails", "AnalyzePaymentFailure", "TryAlternativePayment", "SendPaymentUpdateRequest", "HoldOrderPendingPayment"],
                ),
            ]
        elif industry == Industry.SAAS_OPS:
            return [
                # Playbook 1: Service Degradation
                DemoPlaybookDefinition(
                    playbook_key="PB_SERVICE_DEGRADATION",
                    name="Service Degradation Response",
                    description="Automated response to service performance degradation",
                    industry=Industry.SAAS_OPS,
                    exception_types=["OPS_SERVICE_DEGRADATION"],
                    steps=[
                        PlaybookStepDefinition(
                            step_order=1, 
                            name="Get Service Health Metrics", 
                            action_type="call_tool", 
                            tool_key="GetServiceMetrics",
                            params={"metrics": ["latency_p99", "error_rate", "throughput"]},
                        ),
                        PlaybookStepDefinition(
                            step_order=2, 
                            name="Identify Affected Components", 
                            action_type="call_tool", 
                            tool_key="IdentifyAffectedComponents",
                            params={"include_dependencies": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=3, 
                            name="Check Recent Deployments", 
                            action_type="call_tool", 
                            tool_key="CheckRecentDeployments",
                            params={"lookback_hours": 24},
                        ),
                        PlaybookStepDefinition(
                            step_order=4, 
                            name="Scale Up Resources", 
                            action_type="call_tool", 
                            tool_key="ScaleServiceResources",
                            params={"scale_factor": 1.5, "max_instances": 10},
                        ),
                        PlaybookStepDefinition(
                            step_order=5, 
                            name="Update Status Page", 
                            action_type="call_tool", 
                            tool_key="UpdateStatusPage",
                            params={"status": "DEGRADED", "auto_resolve": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=6, 
                            name="Alert On-Call Engineer", 
                            action_type="notify", 
                            params={"channel": "pagerduty", "severity": "P2"},
                        ),
                    ],
                    tools_required=["GetServiceMetrics", "IdentifyAffectedComponents", "CheckRecentDeployments", "ScaleServiceResources", "UpdateStatusPage"],
                ),
                # Playbook 2: Deployment Failure
                DemoPlaybookDefinition(
                    playbook_key="PB_DEPLOYMENT_FAILURE",
                    name="Deployment Failure Rollback",
                    description="Handle failed deployments with automatic rollback",
                    industry=Industry.SAAS_OPS,
                    exception_types=["OPS_DEPLOYMENT_FAILURE"],
                    steps=[
                        PlaybookStepDefinition(
                            step_order=1, 
                            name="Get Deployment Details", 
                            action_type="call_tool", 
                            tool_key="GetDeploymentDetails",
                            params={"include_logs": True, "include_health_checks": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=2, 
                            name="Analyze Failure Cause", 
                            action_type="call_tool", 
                            tool_key="AnalyzeDeploymentFailure",
                            params={"check_config_drift": True},
                        ),
                        PlaybookStepDefinition(
                            step_order=3, 
                            name="Initiate Rollback", 
                            action_type="call_tool", 
                            tool_key="InitiateRollback",
                            params={"target_version": "previous_stable"},
                        ),
                        PlaybookStepDefinition(
                            step_order=4, 
                            name="Verify Rollback Health", 
                            action_type="call_tool", 
                            tool_key="VerifyServiceHealth",
                            params={"wait_seconds": 60, "health_threshold": 0.99},
                        ),
                        PlaybookStepDefinition(
                            step_order=5, 
                            name="Create Incident Ticket", 
                            action_type="call_tool", 
                            tool_key="CreateIncidentTicket",
                            params={"severity": "HIGH", "assign_to": "platform_team"},
                        ),
                        PlaybookStepDefinition(
                            step_order=6, 
                            name="Notify Engineering", 
                            action_type="notify", 
                            params={"channel": "engineering", "template": "deployment_rollback"},
                        ),
                    ],
                    tools_required=["GetDeploymentDetails", "AnalyzeDeploymentFailure", "InitiateRollback", "VerifyServiceHealth", "CreateIncidentTicket"],
                ),
            ]
        
        return []
    
    async def _ensure_tenant_tools(self, tenant: DemoTenant) -> int:
        """Ensure tools exist for a tenant."""
        created = 0
        
        tools = self._get_tools_for_industry(tenant.industry)
        
        for tool_def in tools:
            # Check if tool exists
            existing = await self.tool_def_repo.get_tool_by_name(
                tenant.tenant_key,
                tool_def.tool_key,
            )
            
            if not existing:
                # Map execution mode
                exec_mode = (
                    ToolExecutionMode.SIMULATE
                    if tool_def.execution_mode == ExecutionMode.SIMULATE
                    else ToolExecutionMode.HTTP
                )
                
                # Map simulation profile
                sim_profile = None
                if tool_def.simulation:
                    profile_map = {
                        SimulationProfile.SUCCESS: SimulateProfile.SUCCESS,
                        SimulationProfile.FAIL: SimulateProfile.FAIL,
                        SimulationProfile.DELAYED: SimulateProfile.DELAYED,
                        SimulationProfile.FLAKY: SimulateProfile.FLAKY,
                    }
                    sim_profile = profile_map.get(tool_def.simulation.profile)
                
                tool = await self.tool_def_repo.create_tool_with_simulation(
                    tenant_id=tenant.tenant_key,
                    tool_data=ToolDefinitionCreateDTO(
                        name=tool_def.tool_key,
                        type="http",
                        config={
                            "endpoint": f"/api/tools/{tool_def.tool_key}",
                            "method": "POST",
                            "description": tool_def.description,
                        },
                    ),
                    execution_mode=exec_mode,
                    simulate_profile=sim_profile,
                    simulate_latency_ms=(
                        {"min": tool_def.simulation.latency.min, "max": tool_def.simulation.latency.max}
                        if tool_def.simulation
                        else None
                    ),
                    simulate_result_template=(
                        tool_def.simulation.result_template
                        if tool_def.simulation
                        else None
                    ),
                )
                
                # Enable tool for tenant
                await self.tool_enablement_repo.set_enablement(
                    tenant.tenant_key,
                    tool.tool_id,
                    enabled=True,
                )
                
                created += 1
                logger.debug(f"Created tool: {tool_def.tool_key} for {tenant.tenant_key}")
        
        return created
    
    def _get_tools_for_industry(self, industry: Industry) -> list[DemoToolDefinition]:
        """
        Get tool definitions for an industry that align with playbook steps.
        
        These tools simulate the actual integrations that would exist in a
        production enterprise environment.
        """
        from src.demo.catalog_types import LatencyRange, ToolSimulationConfig
        
        if industry == Industry.FINANCE:
            return [
                # Settlement Resolution Tools
                DemoToolDefinition(
                    tool_key="GetTradeDetails",
                    name="Get Trade Details",
                    description="Retrieve comprehensive trade details including booking, allocations, and settlement instructions from the OMS",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=600),
                        result_template={
                            "trade_id": "TRD-{{random}}",
                            "status": "PENDING_SETTLEMENT",
                            "trade_date": "2026-01-01",
                            "settlement_date": "2026-01-03",
                            "counterparty": "Goldman Sachs",
                            "security": "AAPL US Equity",
                            "quantity": 10000,
                            "price": 185.50,
                            "settlement_amount": 1855000.00,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="ValidateSettlementInstructions",
                    name="Validate Settlement Instructions",
                    description="Verify SSI (Standard Settlement Instructions) and counterparty details",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=300, max=800),
                        result_template={
                            "valid": True,
                            "ssi_matched": True,
                            "counterparty_verified": True,
                            "bic_code": "GLOSGB2L",
                            "account_validated": True,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="CheckAffirmationStatus",
                    name="Check Affirmation Status",
                    description="Query counterparty affirmation status in the affirmation platform",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=400, max=1200),
                        result_template={
                            "affirmation_status": "AFFIRMED",
                            "affirmed_at": "2026-01-02T14:30:00Z",
                            "affirmed_by": "GS_OPS",
                            "matching_reference": "MTH-{{random}}",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="CheckSettlementCalendar",
                    name="Check Settlement Calendar",
                    description="Verify settlement date against market calendars (TARGET2, FEDWIRE, etc.)",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=100, max=300),
                        result_template={
                            "is_business_day": True,
                            "calendars_checked": ["TARGET2", "FEDWIRE", "NYSE"],
                            "next_settlement_date": "2026-01-03",
                            "holidays_in_range": [],
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="ApplySettlementCorrection",
                    name="Apply Settlement Correction",
                    description="Apply corrective actions to resolve settlement issues",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=500, max=1500),
                        result_template={
                            "correction_applied": True,
                            "correction_type": "SSI_UPDATE",
                            "new_settlement_date": "2026-01-03",
                            "requires_approval": False,
                            "audit_id": "AUD-{{random}}",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="ResubmitSettlement",
                    name="Resubmit Settlement",
                    description="Resubmit settlement instruction to depository/custodian",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=300, max=800),
                        result_template={
                            "resubmitted": True,
                            "settlement_ref": "STL-{{random}}",
                            "status": "SUBMITTED",
                            "expected_settlement": "2026-01-03T16:00:00Z",
                        },
                    ),
                ),
                # Position Break Tools
                DemoToolDefinition(
                    tool_key="GetInternalPosition",
                    name="Get Internal Position",
                    description="Extract position from internal books and records",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=300, max=1000),
                        result_template={
                            "security": "AAPL US Equity",
                            "position_qty": 150000,
                            "market_value": 27825000.00,
                            "as_of_date": "2026-01-01",
                            "pending_settlements": 2,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="GetCustodianPosition",
                    name="Get Custodian Position",
                    description="Fetch position from custodian statement (MT535/MT536)",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=500, max=2000),
                        result_template={
                            "custodian": "State Street",
                            "security": "AAPL US Equity",
                            "position_qty": 149000,
                            "market_value": 27639500.00,
                            "statement_date": "2026-01-01",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="CalculatePositionDelta",
                    name="Calculate Position Delta",
                    description="Compute difference between internal and custodian positions",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=100, max=300),
                        result_template={
                            "quantity_delta": 1000,
                            "value_delta": 185500.00,
                            "delta_pct": 0.67,
                            "within_tolerance": False,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="AnalyzeBreakCause",
                    name="Analyze Break Cause",
                    description="Identify root cause of position discrepancy",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=400, max=1200),
                        result_template={
                            "likely_cause": "UNSETTLED_TRADE",
                            "confidence": 0.92,
                            "related_trades": ["TRD-2026-001234"],
                            "recommendation": "Wait for settlement T+2",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="CreateReconciliationEntry",
                    name="Create Reconciliation Entry",
                    description="Create reconciliation adjustment entry",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=500),
                        result_template={
                            "entry_id": "REC-{{random}}",
                            "status": "PENDING_APPROVAL",
                            "adjustment_qty": 1000,
                            "created_by": "SYSTEM",
                        },
                    ),
                ),
                # Allocation Tools
                DemoToolDefinition(
                    tool_key="GetBlockTrade",
                    name="Get Block Trade",
                    description="Retrieve block trade and its allocations",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=600),
                        result_template={
                            "block_id": "BLK-{{random}}",
                            "total_quantity": 50000,
                            "num_allocations": 5,
                            "allocation_status": "PARTIAL",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="ValidateAccountEligibility",
                    name="Validate Account Eligibility",
                    description="Check if accounts are eligible for allocation",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=300, max=800),
                        result_template={
                            "all_eligible": True,
                            "accounts_checked": 5,
                            "restrictions_found": 0,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="VerifyAllocationCalc",
                    name="Verify Allocation Calculation",
                    description="Verify pro-rata or other allocation methodology",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=100, max=400),
                        result_template={
                            "calculation_valid": True,
                            "method": "PRO_RATA",
                            "total_allocated": 50000,
                            "rounding_diff": 0,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="CorrectAllocation",
                    name="Correct Allocation",
                    description="Apply corrections to allocation splits",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=400, max=1000),
                        result_template={
                            "corrected": True,
                            "allocations_updated": 2,
                            "audit_trail_id": "ALT-{{random}}",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="ReprocessAllocations",
                    name="Reprocess Allocations",
                    description="Reprocess allocation splits for a block trade",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=500, max=1500),
                        result_template={
                            "status": "COMPLETED",
                            "allocations_created": 5,
                            "total_allocated": 50000,
                        },
                    ),
                ),
                # Regulatory Reporting Tools
                DemoToolDefinition(
                    tool_key="ParseRegReportRejection",
                    name="Parse Regulatory Report Rejection",
                    description="Parse and extract validation errors from regulatory rejection",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=100, max=400),
                        result_template={
                            "rejection_code": "FIELD_VALIDATION_ERROR",
                            "failed_fields": ["LEI", "ExecutionVenue"],
                            "regulator": "ESMA",
                            "report_type": "MIFID_II",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="GetRegReportData",
                    name="Get Regulatory Report Data",
                    description="Fetch the original report data and source trades",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=600),
                        result_template={
                            "report_id": "REP-{{random}}",
                            "num_trades": 15,
                            "submission_date": "2026-01-01",
                            "report_status": "REJECTED",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="ValidateReportSchema",
                    name="Validate Report Schema",
                    description="Validate report against regulatory schema",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=300, max=800),
                        result_template={
                            "schema_valid": True,
                            "schema_version": "2.1.0",
                            "validation_errors": [],
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="ApplyReportCorrections",
                    name="Apply Report Corrections",
                    description="Apply data corrections to regulatory report",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=400, max=1200),
                        result_template={
                            "corrections_applied": 2,
                            "fields_corrected": ["LEI", "ExecutionVenue"],
                            "audit_id": "COR-{{random}}",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="ResubmitRegReport",
                    name="Resubmit Regulatory Report",
                    description="Resubmit corrected report to regulatory authority",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=500, max=2000),
                        result_template={
                            "submitted": True,
                            "submission_ref": "SUB-{{random}}",
                            "expected_response_hours": 24,
                        },
                    ),
                ),
            ]
        elif industry == Industry.HEALTHCARE:
            return [
                # Prior Authorization Tools
                DemoToolDefinition(
                    tool_key="GetClaimDetails",
                    name="Get Claim Details",
                    description="Retrieve comprehensive claim information including procedure and diagnosis codes",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=500),
                        result_template={
                            "claim_id": "CLM-{{random}}",
                            "patient_id": "PAT-{{random}}",
                            "procedure_codes": ["99213", "87430"],
                            "diagnosis_codes": ["J06.9", "Z01.89"],
                            "total_charges": 450.00,
                            "status": "PENDING_AUTH",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="SearchPriorAuth",
                    name="Search Prior Authorization",
                    description="Search for existing prior authorization in the system",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=400, max=1000),
                        result_template={
                            "authorizations_found": 1,
                            "auth_id": "AUTH-{{random}}",
                            "auth_status": "APPROVED",
                            "valid_from": "2025-12-01",
                            "valid_to": "2026-03-01",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="VerifyAuthMatch",
                    name="Verify Authorization Match",
                    description="Verify authorization matches claim procedures and provider",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=600),
                        result_template={
                            "match_verified": True,
                            "procedure_match": True,
                            "provider_match": True,
                            "date_valid": True,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="LinkAuthToClaim",
                    name="Link Authorization to Claim",
                    description="Associate authorization with the claim record",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=150, max=400),
                        result_template={
                            "linked": True,
                            "claim_id": "CLM-{{random}}",
                            "auth_id": "AUTH-{{random}}",
                            "link_timestamp": "2026-01-01T10:30:00Z",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="ResubmitClaim",
                    name="Resubmit Claim",
                    description="Resubmit claim for adjudication after corrections",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=300, max=800),
                        result_template={
                            "resubmitted": True,
                            "new_claim_status": "PENDING_ADJUDICATION",
                            "queue_position": 47,
                            "estimated_processing_hours": 4,
                        },
                    ),
                ),
                # Procedure Code Tools
                DemoToolDefinition(
                    tool_key="GetClaimWithMedicalRecord",
                    name="Get Claim with Medical Record",
                    description="Retrieve claim along with associated clinical documentation",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=400, max=1200),
                        result_template={
                            "claim_id": "CLM-{{random}}",
                            "clinical_notes_attached": True,
                            "documentation_complete": True,
                            "chart_review_status": "PENDING",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="ValidateProcedureCodes",
                    name="Validate Procedure Codes",
                    description="Validate CPT/ICD codes for bundling and medical necessity",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=300, max=900),
                        result_template={
                            "codes_valid": True,
                            "bundling_issues": [],
                            "medical_necessity_met": True,
                            "suggested_modifiers": [],
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="GetPayerCodeRequirements",
                    name="Get Payer Code Requirements",
                    description="Fetch payer-specific coding requirements and rules",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=600),
                        result_template={
                            "payer": "Aetna",
                            "special_requirements": ["modifier_25_required"],
                            "coding_guidelines_version": "2026-Q1",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="ApplyCodeCorrection",
                    name="Apply Code Correction",
                    description="Apply coding corrections based on review",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=250, max=700),
                        result_template={
                            "corrections_applied": True,
                            "codes_updated": ["99213-25"],
                            "requires_coder_review": False,
                            "correction_reason": "Added modifier for separate E/M service",
                        },
                    ),
                ),
                # Provider Credential Tools
                DemoToolDefinition(
                    tool_key="GetProviderDetails",
                    name="Get Provider Details",
                    description="Retrieve provider information and credentials",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=500),
                        result_template={
                            "npi": "1234567890",
                            "provider_name": "Dr. Jane Smith",
                            "specialty": "Internal Medicine",
                            "network_status": "IN_NETWORK",
                            "credentials": ["MD", "FACP"],
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="CheckCredentialRegistry",
                    name="Check Credential Registry",
                    description="Verify credentials against NPPES and state licensing boards",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=500, max=1500),
                        result_template={
                            "nppes_verified": True,
                            "state_license_valid": True,
                            "license_expiry": "2027-06-30",
                            "no_sanctions": True,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="RequestCredentialUpdate",
                    name="Request Credential Update",
                    description="Request provider to update expired credentials",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=100, max=300),
                        result_template={
                            "request_sent": True,
                            "notification_type": "EMAIL",
                            "request_id": "CRED-{{random}}",
                            "response_due_date": "2026-01-15",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="HoldClaimPending",
                    name="Hold Claim Pending Verification",
                    description="Place claim on hold pending credential or other verification",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=100, max=300),
                        result_template={
                            "claim_held": True,
                            "hold_reason": "CREDENTIAL_VERIFICATION",
                            "hold_expiry": "2026-02-01",
                            "escalation_date": "2026-01-20",
                        },
                    ),
                ),
            ]
        elif industry == Industry.INSURANCE:
            return [
                # Claim Validation Tools
                DemoToolDefinition(
                    tool_key="GetClaimAndPolicy",
                    name="Get Claim and Policy",
                    description="Retrieve claim details along with associated policy information",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=300, max=800),
                        result_template={
                            "claim_id": "CLM-{{random}}",
                            "policy_number": "POL-{{random}}",
                            "loss_date": "2025-12-28",
                            "claim_type": "AUTO_COLLISION",
                            "policy_status": "ACTIVE",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="GetValidationErrors",
                    name="Get Validation Errors",
                    description="Retrieve detailed validation errors for a claim",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=150, max=400),
                        result_template={
                            "errors": [{"field": "loss_location", "message": "Missing required field"}],
                            "warnings": [],
                            "total_errors": 1,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="CheckPolicyTerms",
                    name="Check Policy Terms",
                    description="Verify claim against policy terms, exclusions, and limits",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=300, max=900),
                        result_template={
                            "coverage_applicable": True,
                            "exclusions_checked": True,
                            "within_limits": True,
                            "deductible": 500.00,
                            "coverage_limit": 100000.00,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="ApplyClaimCorrections",
                    name="Apply Claim Corrections",
                    description="Apply data corrections to claim record",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=600),
                        result_template={
                            "corrections_applied": True,
                            "fields_updated": ["loss_location"],
                            "audit_id": "COR-{{random}}",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="RevalidateClaim",
                    name="Revalidate Claim",
                    description="Run full validation on corrected claim",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=300, max=800),
                        result_template={
                            "validation_passed": True,
                            "errors": [],
                            "warnings": [],
                            "ready_for_adjudication": True,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="RouteToAdjudicator",
                    name="Route to Adjudicator",
                    description="Route validated claim to adjudication queue",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=100, max=300),
                        result_template={
                            "routed": True,
                            "queue": "AUTO_CLAIMS",
                            "priority": "STANDARD",
                            "estimated_completion_hours": 24,
                        },
                    ),
                ),
                # Fraud Detection Tools
                DemoToolDefinition(
                    tool_key="GetFraudAlertDetails",
                    name="Get Fraud Alert Details",
                    description="Retrieve details of fraud detection alert",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=500),
                        result_template={
                            "alert_id": "FRD-{{random}}",
                            "risk_indicators": ["MULTIPLE_CLAIMS_SHORT_PERIOD", "HIGH_VALUE"],
                            "model_score": 0.78,
                            "triggered_rules": ["R-101", "R-205"],
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="GetClaimantHistory",
                    name="Get Claimant History",
                    description="Fetch historical claims and related party information",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=400, max=1200),
                        result_template={
                            "total_claims_5yr": 3,
                            "total_paid_5yr": 12500.00,
                            "related_parties_flagged": 0,
                            "previous_investigations": 0,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="RunEnhancedVerification",
                    name="Run Enhanced Verification",
                    description="Run additional verification against external databases",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=600, max=2000),
                        result_template={
                            "verification_complete": True,
                            "identity_verified": True,
                            "address_verified": True,
                            "external_flags": [],
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="CalculateFraudRiskScore",
                    name="Calculate Fraud Risk Score",
                    description="Calculate comprehensive fraud risk score",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=300, max=800),
                        result_template={
                            "final_score": 0.35,
                            "risk_level": "LOW",
                            "model_version": "v2.3",
                            "confidence": 0.92,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="RouteByRiskLevel",
                    name="Route by Risk Level",
                    description="Route claim based on fraud risk assessment",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=100, max=300),
                        result_template={
                            "routed_to": "STANDARD_PROCESSING",
                            "siu_referral": False,
                            "additional_review_required": False,
                        },
                    ),
                ),
                # Coverage Mismatch Tools
                DemoToolDefinition(
                    tool_key="GetPolicyCoverage",
                    name="Get Policy Coverage",
                    description="Retrieve detailed coverage information as of loss date",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=250, max=700),
                        result_template={
                            "coverages": [
                                {"type": "COLLISION", "limit": 50000, "deductible": 500},
                                {"type": "COMPREHENSIVE", "limit": 50000, "deductible": 250},
                            ],
                            "policy_effective": "2025-06-01",
                            "policy_expiry": "2026-06-01",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="CompareClaimToCoverage",
                    name="Compare Claim to Coverage",
                    description="Compare claimed losses to available coverage",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=600),
                        result_template={
                            "coverage_applicable": True,
                            "coverage_gap": False,
                            "claim_amount": 15000.00,
                            "covered_amount": 14500.00,
                            "deductible_applied": 500.00,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="GetPolicyAmendments",
                    name="Get Policy Amendments",
                    description="Fetch any policy amendments or endorsements",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=500),
                        result_template={
                            "amendments": [],
                            "endorsements": ["RENTAL_CAR_COVERAGE"],
                            "effective_dates_verified": True,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="AdjustClaimCoverage",
                    name="Adjust Claim Coverage",
                    description="Adjust claim based on coverage verification",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=300, max=800),
                        result_template={
                            "adjustment_applied": True,
                            "original_claim": 15000.00,
                            "adjusted_claim": 14500.00,
                            "adjustment_reason": "Deductible applied",
                            "explanation_generated": True,
                        },
                    ),
                ),
            ]
        elif industry == Industry.RETAIL:
            return [
                # Order Fulfillment Tools
                DemoToolDefinition(
                    tool_key="GetOrderDetails",
                    name="Get Order Details",
                    description="Retrieve complete order information including items and shipping",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=150, max=400),
                        result_template={
                            "order_id": "ORD-{{random}}",
                            "customer_id": "CUST-{{random}}",
                            "items": [{"sku": "SKU-001", "qty": 2, "price": 49.99}],
                            "total": 99.98,
                            "status": "PENDING_FULFILLMENT",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="CheckInventoryAvailability",
                    name="Check Inventory Availability",
                    description="Check stock availability across all warehouses",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=600),
                        result_template={
                            "all_available": True,
                            "warehouse_allocation": [{"warehouse": "WH-EAST", "sku": "SKU-001", "qty": 2}],
                            "backorder_items": [],
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="IdentifyFulfillmentBlockers",
                    name="Identify Fulfillment Blockers",
                    description="Identify what is preventing order fulfillment",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=500),
                        result_template={
                            "blockers": ["ADDRESS_VALIDATION_FAILED"],
                            "blocker_details": {"field": "zip_code", "message": "Invalid ZIP code format"},
                            "resolvable": True,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="ApplyFulfillmentFix",
                    name="Apply Fulfillment Fix",
                    description="Apply resolution to fulfillment blocker",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=600),
                        result_template={
                            "fix_applied": True,
                            "action_taken": "ADDRESS_CORRECTED",
                            "validated": True,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="RequeueOrder",
                    name="Requeue Order",
                    description="Requeue order for fulfillment processing",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=100, max=300),
                        result_template={
                            "requeued": True,
                            "new_status": "READY_FOR_PICK",
                            "estimated_ship_date": "2026-01-02",
                            "expedited": True,
                        },
                    ),
                ),
                # Payment Processing Tools
                DemoToolDefinition(
                    tool_key="GetPaymentDetails",
                    name="Get Payment Details",
                    description="Retrieve payment transaction details including gateway response",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=150, max=400),
                        result_template={
                            "transaction_id": "TXN-{{random}}",
                            "amount": 99.98,
                            "status": "DECLINED",
                            "gateway_response": "INSUFFICIENT_FUNDS",
                            "card_last_four": "4242",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="AnalyzePaymentFailure",
                    name="Analyze Payment Failure",
                    description="Analyze reason for payment failure",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=500),
                        result_template={
                            "failure_type": "SOFT_DECLINE",
                            "retryable": True,
                            "fraud_flags": [],
                            "recommendation": "RETRY_WITH_SAME_CARD",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="TryAlternativePayment",
                    name="Try Alternative Payment",
                    description="Attempt payment with alternative method on file",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=400, max=1200),
                        result_template={
                            "alternative_found": True,
                            "method_tried": "BACKUP_CARD",
                            "result": "APPROVED",
                            "new_transaction_id": "TXN-{{random}}",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="SendPaymentUpdateRequest",
                    name="Send Payment Update Request",
                    description="Request customer to update payment information",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=100, max=300),
                        result_template={
                            "notification_sent": True,
                            "channel": "EMAIL",
                            "expiry_hours": 48,
                            "update_link_generated": True,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="HoldOrderPendingPayment",
                    name="Hold Order Pending Payment",
                    description="Place order on hold awaiting payment resolution",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=100, max=250),
                        result_template={
                            "order_held": True,
                            "hold_reason": "PAYMENT_PENDING",
                            "auto_cancel_hours": 48,
                            "inventory_reserved": True,
                        },
                    ),
                ),
            ]
        elif industry == Industry.SAAS_OPS:
            return [
                # Service Degradation Tools
                DemoToolDefinition(
                    tool_key="GetServiceMetrics",
                    name="Get Service Metrics",
                    description="Retrieve real-time service health metrics",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=100, max=300),
                        result_template={
                            "service": "api-gateway",
                            "latency_p99_ms": 850,
                            "error_rate_pct": 2.5,
                            "throughput_rps": 1500,
                            "status": "DEGRADED",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="IdentifyAffectedComponents",
                    name="Identify Affected Components",
                    description="Map impact to dependent services and components",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=600),
                        result_template={
                            "affected_services": ["user-service", "order-service"],
                            "affected_customers_estimate": 1500,
                            "dependency_chain": ["api-gateway", "auth-service", "database"],
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="CheckRecentDeployments",
                    name="Check Recent Deployments",
                    description="Check for recent deployments that may have caused issues",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=150, max=400),
                        result_template={
                            "recent_deployments": [
                                {"service": "api-gateway", "version": "v2.3.1", "deployed_at": "2026-01-01T08:00:00Z"}
                            ],
                            "correlation_score": 0.85,
                            "rollback_available": True,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="ScaleServiceResources",
                    name="Scale Service Resources",
                    description="Horizontally scale service to handle increased load",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=500, max=1500),
                        result_template={
                            "scaled": True,
                            "previous_replicas": 3,
                            "new_replicas": 5,
                            "scale_time_seconds": 45,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="UpdateStatusPage",
                    name="Update Status Page",
                    description="Update public status page with incident information",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=100, max=300),
                        result_template={
                            "status_updated": True,
                            "incident_id": "INC-{{random}}",
                            "public_status": "DEGRADED_PERFORMANCE",
                            "estimated_resolution": "2026-01-01T12:00:00Z",
                        },
                    ),
                ),
                # Deployment Failure Tools
                DemoToolDefinition(
                    tool_key="GetDeploymentDetails",
                    name="Get Deployment Details",
                    description="Retrieve deployment information including logs and health checks",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=200, max=600),
                        result_template={
                            "deployment_id": "DEP-{{random}}",
                            "service": "payment-service",
                            "version": "v3.1.0",
                            "status": "FAILED",
                            "failure_reason": "HEALTH_CHECK_FAILED",
                            "logs_available": True,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="AnalyzeDeploymentFailure",
                    name="Analyze Deployment Failure",
                    description="Analyze root cause of deployment failure",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=300, max=900),
                        result_template={
                            "root_cause": "DATABASE_MIGRATION_FAILED",
                            "error_message": "Column 'user_preferences' already exists",
                            "config_drift_detected": False,
                            "recommendation": "ROLLBACK_AND_FIX_MIGRATION",
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="InitiateRollback",
                    name="Initiate Rollback",
                    description="Initiate rollback to previous stable version",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=500, max=2000),
                        result_template={
                            "rollback_initiated": True,
                            "target_version": "v3.0.5",
                            "rollback_id": "RB-{{random}}",
                            "estimated_completion_seconds": 120,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="VerifyServiceHealth",
                    name="Verify Service Health",
                    description="Verify service health after rollback or remediation",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=300, max=800),
                        result_template={
                            "health_check_passed": True,
                            "all_endpoints_healthy": True,
                            "latency_normal": True,
                            "error_rate_normal": True,
                        },
                    ),
                ),
                DemoToolDefinition(
                    tool_key="CreateIncidentTicket",
                    name="Create Incident Ticket",
                    description="Create incident ticket for tracking and postmortem",
                    execution_mode=ExecutionMode.SIMULATE,
                    simulation=ToolSimulationConfig(
                        profile=SimulationProfile.SUCCESS,
                        latency=LatencyRange(min=150, max=400),
                        result_template={
                            "ticket_id": "INC-{{random}}",
                            "severity": "P2",
                            "assigned_team": "platform-engineering",
                            "postmortem_scheduled": True,
                        },
                    ),
                ),
            ]
        
        return []
    
    async def _seed_tenant_exceptions(self, tenant: DemoTenant) -> int:
        """
        Seed realistic exceptions for a tenant that match available playbooks.
        
        Creates exceptions with proper context that demonstrates the value
        of automated exception resolution.
        """
        # Check current exception count
        result = await self.exception_repo.list_exceptions(
            tenant_id=tenant.tenant_key,
            filters=ExceptionFilter(),  # Empty filter to get all
            page=1,
            page_size=1,
        )
        
        min_exceptions = tenant.seed_plan.min_exceptions if hasattr(tenant, 'seed_plan') else 10
        
        if result.total >= min_exceptions:
            return 0
        
        # Generate exceptions to reach minimum
        count_to_create = min_exceptions - result.total
        created = 0
        
        # Get realistic exception scenarios for this industry
        scenarios = self._get_exception_scenarios_for_industry(tenant.industry)
        
        for i in range(count_to_create):
            # Pick a scenario
            scenario = random.choice(scenarios)
            
            # Generate created_at within lookback period
            lookback_days = tenant.seed_plan.lookback_days if hasattr(tenant, 'seed_plan') else 7
            created_at = datetime.now(timezone.utc) - timedelta(
                days=random.randint(0, lookback_days),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )
            
            exc_id = f"EXC-{tenant.industry.value[:3].upper()}-{datetime.now().strftime('%Y%m%d')}-{i:05d}"
            
            # Generate realistic entity and amount for the scenario
            entity, amount = self._generate_scenario_entity_amount(tenant.industry, scenario)
            
            await self.exception_repo.create_exception(
                tenant_id=tenant.tenant_key,
                data=ExceptionCreateDTO(
                    exception_id=exc_id,
                    tenant_id=tenant.tenant_key,
                    domain=self._industry_to_domain(tenant.industry),
                    type=scenario["type"],
                    severity=scenario["severity"],
                    source_system=scenario["source"],
                    entity=entity,
                    amount=Decimal(str(round(amount, 2))),
                    metadata=scenario.get("metadata", {}),
                    created_at=created_at,
                )
            )
            created += 1
        
        logger.debug(f"Seeded {created} exceptions for {tenant.tenant_key}")
        return created
    
    def _get_exception_scenarios_for_industry(self, industry: Industry) -> list[dict]:
        """
        Get realistic exception scenarios for an industry.
        
        Each scenario includes the exception type, severity, source system,
        and relevant metadata that matches what a real system would produce.
        """
        if industry == Industry.FINANCE:
            return [
                # Settlement Failures
                {
                    "type": "FIN_SETTLEMENT_FAIL",
                    "severity": ExceptionSeverity.HIGH,
                    "source": "DTCC",
                    "metadata": {
                        "failure_reason": "UNMATCHED_INSTRUCTION",
                        "counterparty": "Goldman Sachs",
                        "settlement_method": "DVP",
                        "market": "US_EQUITY",
                    },
                },
                {
                    "type": "FIN_SETTLEMENT_FAIL",
                    "severity": ExceptionSeverity.CRITICAL,
                    "source": "Euroclear",
                    "metadata": {
                        "failure_reason": "INSUFFICIENT_SECURITIES",
                        "counterparty": "Morgan Stanley",
                        "settlement_method": "FOP",
                        "market": "EU_FIXED_INCOME",
                    },
                },
                {
                    "type": "FIN_SETTLEMENT_FAIL",
                    "severity": ExceptionSeverity.MEDIUM,
                    "source": "SWIFT",
                    "metadata": {
                        "failure_reason": "SSI_MISMATCH",
                        "counterparty": "JP Morgan",
                        "message_type": "MT548",
                        "nack_reason_code": "AC04",
                    },
                },
                # Position Breaks
                {
                    "type": "FIN_POSITION_BREAK",
                    "severity": ExceptionSeverity.HIGH,
                    "source": "State Street",
                    "metadata": {
                        "internal_qty": 150000,
                        "custodian_qty": 149000,
                        "variance": 1000,
                        "security": "AAPL US Equity",
                    },
                },
                {
                    "type": "FIN_POSITION_BREAK",
                    "severity": ExceptionSeverity.CRITICAL,
                    "source": "BNY Mellon",
                    "metadata": {
                        "internal_qty": 500000,
                        "custodian_qty": 485000,
                        "variance": 15000,
                        "security": "US Treasury 10Y",
                    },
                },
                # Allocation Failures
                {
                    "type": "FIN_FAILED_ALLOCATION",
                    "severity": ExceptionSeverity.MEDIUM,
                    "source": "Charles River",
                    "metadata": {
                        "block_id": "BLK-2026-001234",
                        "failure_reason": "ACCOUNT_RESTRICTION",
                        "accounts_affected": 2,
                    },
                },
                {
                    "type": "FIN_FAILED_ALLOCATION",
                    "severity": ExceptionSeverity.HIGH,
                    "source": "Bloomberg AIM",
                    "metadata": {
                        "block_id": "BLK-2026-005678",
                        "failure_reason": "ROUNDING_ERROR",
                        "total_quantity": 50000,
                        "allocated_quantity": 49997,
                    },
                },
                # Regulatory Report Rejections
                {
                    "type": "FIN_REG_REPORT_REJECTED",
                    "severity": ExceptionSeverity.HIGH,
                    "source": "ESMA",
                    "metadata": {
                        "report_type": "MIFID_II",
                        "rejection_code": "REJ-003",
                        "failed_fields": ["LEI", "ExecutionVenue"],
                    },
                },
                {
                    "type": "FIN_REG_REPORT_REJECTED",
                    "severity": ExceptionSeverity.CRITICAL,
                    "source": "SEC",
                    "metadata": {
                        "report_type": "CAT",
                        "rejection_code": "VAL-ERR-102",
                        "deadline": "T+1",
                    },
                },
            ]
        elif industry == Industry.HEALTHCARE:
            return [
                # Prior Authorization Issues
                {
                    "type": "HLTH_CLAIM_MISSING_AUTH",
                    "severity": ExceptionSeverity.HIGH,
                    "source": "ClaimsPortal",
                    "metadata": {
                        "procedure_code": "27447",
                        "procedure_desc": "Total Knee Replacement",
                        "payer": "UnitedHealthcare",
                        "requires_auth": True,
                    },
                },
                {
                    "type": "HLTH_CLAIM_MISSING_AUTH",
                    "severity": ExceptionSeverity.MEDIUM,
                    "source": "EHRSystem",
                    "metadata": {
                        "procedure_code": "43239",
                        "procedure_desc": "Upper GI Endoscopy",
                        "payer": "Aetna",
                        "auth_search_attempted": True,
                    },
                },
                # Code Mismatch Issues
                {
                    "type": "HLTH_CLAIM_CODE_MISMATCH",
                    "severity": ExceptionSeverity.MEDIUM,
                    "source": "BillingSystem",
                    "metadata": {
                        "claim_cpt": "99214",
                        "documented_cpt": "99213",
                        "reason": "Documentation does not support level 4 visit",
                    },
                },
                {
                    "type": "HLTH_CLAIM_CODE_MISMATCH",
                    "severity": ExceptionSeverity.HIGH,
                    "source": "CodeReviewSystem",
                    "metadata": {
                        "bundling_issue": True,
                        "codes": ["99213", "87430"],
                        "rule": "Global surgery period violation",
                    },
                },
                # Provider Credential Issues
                {
                    "type": "HLTH_PROVIDER_CREDENTIAL_EXPIRED",
                    "severity": ExceptionSeverity.HIGH,
                    "source": "CredentialingSystem",
                    "metadata": {
                        "provider_npi": "1234567890",
                        "expired_credential": "State License",
                        "expiry_date": "2025-12-31",
                    },
                },
                {
                    "type": "HLTH_PROVIDER_CREDENTIAL_EXPIRED",
                    "severity": ExceptionSeverity.CRITICAL,
                    "source": "PayerNetwork",
                    "metadata": {
                        "provider_npi": "9876543210",
                        "issue": "Network participation terminated",
                        "effective_date": "2025-11-01",
                    },
                },
            ]
        elif industry == Industry.INSURANCE:
            return [
                # Claim Validation Errors
                {
                    "type": "INS_CLAIM_VALIDATION_ERROR",
                    "severity": ExceptionSeverity.MEDIUM,
                    "source": "ClaimsPortal",
                    "metadata": {
                        "validation_errors": ["Missing loss location", "Invalid date format"],
                        "claim_type": "AUTO_COLLISION",
                        "error_count": 2,
                    },
                },
                {
                    "type": "INS_CLAIM_VALIDATION_ERROR",
                    "severity": ExceptionSeverity.HIGH,
                    "source": "PolicyAdmin",
                    "metadata": {
                        "validation_errors": ["Policy not active on loss date"],
                        "claim_type": "PROPERTY_DAMAGE",
                        "loss_date": "2025-12-15",
                        "policy_expiry": "2025-12-01",
                    },
                },
                # Fraud Detection Alerts
                {
                    "type": "INS_FRAUD_DETECTION_ALERT",
                    "severity": ExceptionSeverity.HIGH,
                    "source": "FraudModel_v2",
                    "metadata": {
                        "risk_score": 0.78,
                        "indicators": ["MULTIPLE_CLAIMS_SHORT_PERIOD", "HIGH_VALUE"],
                        "triggered_rules": ["R-101", "R-205"],
                    },
                },
                {
                    "type": "INS_FRAUD_DETECTION_ALERT",
                    "severity": ExceptionSeverity.CRITICAL,
                    "source": "SIU_Referral",
                    "metadata": {
                        "risk_score": 0.92,
                        "indicators": ["STAGED_ACCIDENT_PATTERN", "RELATED_PARTY_NETWORK"],
                        "siu_case_opened": True,
                    },
                },
                # Coverage Mismatch Issues
                {
                    "type": "INS_POLICY_COVERAGE_MISMATCH",
                    "severity": ExceptionSeverity.MEDIUM,
                    "source": "AdjudicationEngine",
                    "metadata": {
                        "claimed_coverage": "RENTAL_CAR",
                        "policy_coverage": "NO_RENTAL",
                        "claim_amount": 1200.00,
                    },
                },
                {
                    "type": "INS_POLICY_COVERAGE_MISMATCH",
                    "severity": ExceptionSeverity.HIGH,
                    "source": "PolicyAdmin",
                    "metadata": {
                        "issue": "Deductible not met",
                        "claim_amount": 450.00,
                        "deductible": 500.00,
                    },
                },
            ]
        elif industry == Industry.RETAIL:
            return [
                # Order Fulfillment Errors
                {
                    "type": "RET_ORDER_FULFILLMENT_ERROR",
                    "severity": ExceptionSeverity.HIGH,
                    "source": "FulfillmentSystem",
                    "metadata": {
                        "blocker": "ADDRESS_VALIDATION_FAILED",
                        "error_detail": "Invalid ZIP code format",
                        "warehouse": "WH-EAST",
                    },
                },
                {
                    "type": "RET_ORDER_FULFILLMENT_ERROR",
                    "severity": ExceptionSeverity.MEDIUM,
                    "source": "InventorySystem",
                    "metadata": {
                        "blocker": "ITEM_OUT_OF_STOCK",
                        "sku": "SKU-12345",
                        "quantity_needed": 2,
                        "quantity_available": 0,
                    },
                },
                {
                    "type": "RET_ORDER_FULFILLMENT_ERROR",
                    "severity": ExceptionSeverity.CRITICAL,
                    "source": "eCommerce",
                    "metadata": {
                        "blocker": "FRAUD_CHECK_FAILED",
                        "order_value": 2500.00,
                        "customer_type": "NEW",
                    },
                },
                # Payment Processing Failures
                {
                    "type": "RET_PAYMENT_PROCESSING_FAIL",
                    "severity": ExceptionSeverity.HIGH,
                    "source": "PaymentGateway",
                    "metadata": {
                        "gateway_response": "INSUFFICIENT_FUNDS",
                        "card_last_four": "4242",
                        "amount": 299.99,
                        "retryable": True,
                    },
                },
                {
                    "type": "RET_PAYMENT_PROCESSING_FAIL",
                    "severity": ExceptionSeverity.CRITICAL,
                    "source": "PaymentGateway",
                    "metadata": {
                        "gateway_response": "SUSPECTED_FRAUD",
                        "card_last_four": "1234",
                        "amount": 1599.00,
                        "retryable": False,
                    },
                },
                {
                    "type": "RET_PAYMENT_PROCESSING_FAIL",
                    "severity": ExceptionSeverity.MEDIUM,
                    "source": "PaymentGateway",
                    "metadata": {
                        "gateway_response": "CARD_EXPIRED",
                        "card_last_four": "9876",
                        "amount": 89.99,
                        "backup_method_available": True,
                    },
                },
            ]
        elif industry == Industry.SAAS_OPS:
            return [
                # Service Degradation
                {
                    "type": "OPS_SERVICE_DEGRADATION",
                    "severity": ExceptionSeverity.CRITICAL,
                    "source": "Datadog",
                    "metadata": {
                        "service": "api-gateway",
                        "latency_p99_ms": 2500,
                        "error_rate_pct": 5.2,
                        "affected_customers": 1500,
                    },
                },
                {
                    "type": "OPS_SERVICE_DEGRADATION",
                    "severity": ExceptionSeverity.HIGH,
                    "source": "PagerDuty",
                    "metadata": {
                        "service": "database-primary",
                        "cpu_pct": 95,
                        "memory_pct": 88,
                        "alert_name": "High Resource Utilization",
                    },
                },
                # Deployment Failures
                {
                    "type": "OPS_DEPLOYMENT_FAILURE",
                    "severity": ExceptionSeverity.HIGH,
                    "source": "ArgoCD",
                    "metadata": {
                        "deployment_id": "DEP-2026-001234",
                        "service": "payment-service",
                        "version": "v3.1.0",
                        "failure_reason": "HEALTH_CHECK_FAILED",
                    },
                },
                {
                    "type": "OPS_DEPLOYMENT_FAILURE",
                    "severity": ExceptionSeverity.CRITICAL,
                    "source": "Kubernetes",
                    "metadata": {
                        "deployment_id": "DEP-2026-005678",
                        "service": "auth-service",
                        "version": "v2.8.0",
                        "failure_reason": "IMAGE_PULL_ERROR",
                        "pods_affected": 5,
                    },
                },
                # Security Alerts
                {
                    "type": "OPS_SECURITY_ALERT",
                    "severity": ExceptionSeverity.CRITICAL,
                    "source": "Snyk",
                    "metadata": {
                        "vulnerability": "CVE-2026-12345",
                        "severity": "CRITICAL",
                        "package": "lodash",
                        "affected_services": ["api-gateway", "user-service"],
                    },
                },
                {
                    "type": "OPS_SECURITY_ALERT",
                    "severity": ExceptionSeverity.HIGH,
                    "source": "CloudTrail",
                    "metadata": {
                        "alert_type": "UNAUTHORIZED_ACCESS_ATTEMPT",
                        "source_ip": "203.0.113.50",
                        "target_resource": "s3://production-data",
                        "attempts": 15,
                    },
                },
            ]
        
        return []
    
    def _generate_scenario_entity_amount(
        self, industry: Industry, scenario: dict
    ) -> tuple[str, float]:
        """Generate realistic entity ID and amount for a scenario."""
        exc_type = scenario["type"]
        
        if industry == Industry.FINANCE:
            if "SETTLEMENT" in exc_type:
                entity = f"TRD-{datetime.now().strftime('%Y')}-{random.randint(100000, 999999)}"
                amount = random.uniform(50000, 5000000)
            elif "POSITION" in exc_type:
                entity = f"POS-{random.choice(['AAPL', 'MSFT', 'GOOGL', 'AMZN'])}-{random.randint(1000, 9999)}"
                amount = random.uniform(100000, 10000000)
            elif "ALLOCATION" in exc_type:
                entity = f"BLK-{datetime.now().strftime('%Y')}-{random.randint(100000, 999999)}"
                amount = random.uniform(500000, 25000000)
            elif "REG_REPORT" in exc_type:
                entity = f"REP-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
                amount = random.uniform(10000, 500000)
            else:
                entity = f"TRD-{datetime.now().strftime('%Y')}-{random.randint(100000, 999999)}"
                amount = random.uniform(10000, 1000000)
                
        elif industry == Industry.HEALTHCARE:
            entity = f"CLM-{datetime.now().strftime('%Y')}-{random.randint(100000, 999999)}"
            if "CODE_MISMATCH" in exc_type:
                amount = random.uniform(100, 5000)
            elif "MISSING_AUTH" in exc_type:
                amount = random.uniform(5000, 150000)
            else:
                amount = random.uniform(500, 25000)
                
        elif industry == Industry.INSURANCE:
            entity = f"CLM-{datetime.now().strftime('%Y')}-{random.randint(100000, 999999)}"
            if "FRAUD" in exc_type:
                amount = random.uniform(10000, 500000)
            elif "COVERAGE_MISMATCH" in exc_type:
                amount = random.uniform(500, 25000)
            else:
                amount = random.uniform(1000, 100000)
                
        elif industry == Industry.RETAIL:
            entity = f"ORD-{datetime.now().strftime('%Y%m%d')}-{random.randint(10000, 99999)}"
            if "PAYMENT" in exc_type:
                amount = random.uniform(50, 3000)
            else:
                amount = random.uniform(25, 1500)
                
        elif industry == Industry.SAAS_OPS:
            if "DEPLOYMENT" in exc_type:
                entity = f"DEP-{datetime.now().strftime('%Y')}-{random.randint(100000, 999999)}"
            elif "SECURITY" in exc_type:
                entity = f"SEC-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
            else:
                entity = f"INC-{datetime.now().strftime('%Y')}-{random.randint(10000, 99999)}"
            # SaaS ops typically doesn't have monetary amounts, use impact score
            amount = random.uniform(0, 100)  # Impact score
        else:
            entity = f"ENT-{datetime.now().strftime('%Y')}-{random.randint(100000, 999999)}"
            amount = random.uniform(1000, 100000)
            
        return entity, amount

    def _industry_to_domain(self, industry: Industry) -> str:
        """Map industry to domain name."""
        domain_map = {
            Industry.FINANCE: "CapitalMarketsTrading",
            Industry.HEALTHCARE: "HealthcareClaimsAndCareOps",
            Industry.INSURANCE: "InsuranceClaimsProcessing",
            Industry.RETAIL: "RetailOperations",
            Industry.SAAS_OPS: "SaaSOperations",
        }
        return domain_map.get(industry, "Unknown")
