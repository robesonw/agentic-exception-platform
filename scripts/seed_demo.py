#!/usr/bin/env python3
"""
Demo Data Seed Script for SentinAI Exception Processing Platform.

Populates the database with comprehensive demo data for showcasing:
- 2 active domain packs (Finance, Healthcare)
- Tenant pack override for TENANT_FINANCE_001
- 20 exceptions across severities
- 5+ exceptions with recommended_playbook
- 3+ exceptions with executed playbook steps + audit/tool events

Usage:
    python scripts/seed_demo.py
    python scripts/seed_demo.py --reset
    python scripts/seed_demo.py --verify-only

Idempotent: Safe to run multiple times (uses upsert/skip-if-exists logic).

Reference: docs/06-mvp-plan.md, docs/demo-seeding.md
"""

import asyncio
import hashlib
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass

import argparse
from sqlalchemy import select, text, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

DEMO_CONFIG = {
    "tenants": {
        "TENANT_FINANCE_001": {
            "name": "Acme Capital Partners",
            "domain": "Finance",
        },
        "TENANT_HEALTH_001": {
            "name": "MedCare Health Systems",
            "domain": "Healthcare",
        },
    },
    "domain_packs": ["Finance", "Healthcare"],
    "exception_count": 20,
}

# Finance Exception Types with realistic descriptions
FINANCE_EXCEPTION_TYPES = [
    {
        "type": "SETTLEMENT_FAIL",
        "description": "Trade settlement failed due to counterparty issues",
        "source_systems": ["Murex", "Calypso", "Summit"],
        "severity_weight": "high",
    },
    {
        "type": "POSITION_BREAK",
        "description": "Position mismatch between front and back office",
        "source_systems": ["Murex", "SimCorp", "Bloomberg AIM"],
        "severity_weight": "critical",
    },
    {
        "type": "CASH_BREAK",
        "description": "Cash reconciliation discrepancy",
        "source_systems": ["TLM", "Intellimatch", "SmartStream"],
        "severity_weight": "high",
    },
    {
        "type": "FAILED_ALLOCATION",
        "description": "Block trade allocation failed",
        "source_systems": ["Bloomberg TOMS", "Eze OMS", "Charles River"],
        "severity_weight": "medium",
    },
    {
        "type": "REG_REPORT_REJECTED",
        "description": "Regulatory report rejected by authority",
        "source_systems": ["Cappitech", "IHS Markit", "Bloomberg RHUB"],
        "severity_weight": "high",
    },
]

# Healthcare Exception Types
HEALTHCARE_EXCEPTION_TYPES = [
    {
        "type": "CLAIM_DENIAL",
        "description": "Insurance claim denied - requires investigation",
        "source_systems": ["Epic", "Cerner", "ClaimsPro"],
        "severity_weight": "high",
    },
    {
        "type": "ELIGIBILITY_MISMATCH",
        "description": "Patient eligibility verification failed",
        "source_systems": ["Availity", "Change Healthcare", "Trizetto"],
        "severity_weight": "medium",
    },
    {
        "type": "CODING_ERROR",
        "description": "Incorrect procedure or diagnosis coding",
        "source_systems": ["3M Encoder", "Optum CAC", "Epic HIM"],
        "severity_weight": "medium",
    },
    {
        "type": "AUTH_EXPIRY",
        "description": "Prior authorization expired before service",
        "source_systems": ["Surescripts", "CoverMyMeds", "Epic"],
        "severity_weight": "critical",
    },
    {
        "type": "COORDINATION_FAILURE",
        "description": "COB coordination failure between payers",
        "source_systems": ["BCBS", "UHC Portal", "Aetna Connect"],
        "severity_weight": "low",
    },
]

# Finance Playbooks
FINANCE_PLAYBOOKS = [
    {
        "name": "SettlementFailureResolution",
        "description": "Automated resolution workflow for failed settlements",
        "conditions": {"exception_type": "SETTLEMENT_FAIL", "severity": ["high", "critical"]},
        "steps": [
            {"name": "Fetch Settlement Details", "action_type": "call_tool", "params": {"tool_name": "getSettlement"}},
            {"name": "Verify Counterparty SSI", "action_type": "call_tool", "params": {"tool_name": "verifySSI"}},
            {"name": "Initiate Settlement Retry", "action_type": "call_tool", "params": {"tool_name": "triggerSettlementRetry"}},
            {"name": "Notify Operations", "action_type": "notify", "params": {"channel": "email", "template": "settlement_fail_ops"}},
        ],
    },
    {
        "name": "PositionBreakInvestigation",
        "description": "Investigation workflow for position discrepancies",
        "conditions": {"exception_type": "POSITION_BREAK", "severity": ["critical"]},
        "steps": [
            {"name": "Fetch Position Snapshot", "action_type": "call_tool", "params": {"tool_name": "getPositions"}},
            {"name": "Compare Trade History", "action_type": "call_tool", "params": {"tool_name": "getExecutions"}},
            {"name": "Calculate Variance", "action_type": "call_tool", "params": {"tool_name": "recalculatePosition"}},
            {"name": "Escalate to Risk", "action_type": "escalate", "params": {"team": "risk_management"}},
        ],
    },
    {
        "name": "CashBreakReconciliation",
        "description": "Cash break resolution and reconciliation",
        "conditions": {"exception_type": "CASH_BREAK", "severity": ["high", "medium"]},
        "steps": [
            {"name": "Fetch Cash Movements", "action_type": "call_tool", "params": {"tool_name": "getCashMovements"}},
            {"name": "Identify Break Source", "action_type": "analyze", "params": {"model": "cash_break_classifier"}},
            {"name": "Apply Correction", "action_type": "call_tool", "params": {"tool_name": "postCashAdjustment"}},
        ],
    },
    {
        "name": "RegulatoryReportRepair",
        "description": "Fix and resubmit rejected regulatory reports",
        "conditions": {"exception_type": "REG_REPORT_REJECTED"},
        "steps": [
            {"name": "Fetch Report Details", "action_type": "call_tool", "params": {"tool_name": "getRegReport"}},
            {"name": "Identify Rejection Reason", "action_type": "analyze", "params": {"model": "reg_rejection_classifier"}},
            {"name": "Regenerate Report", "action_type": "call_tool", "params": {"tool_name": "regenerateRegReport"}},
            {"name": "Resubmit to Authority", "action_type": "call_tool", "params": {"tool_name": "submitRegReport"}},
        ],
    },
]

# Healthcare Playbooks
HEALTHCARE_PLAYBOOKS = [
    {
        "name": "ClaimDenialAppeal",
        "description": "Automated claim denial appeal workflow",
        "conditions": {"exception_type": "CLAIM_DENIAL", "severity": ["high", "critical"]},
        "steps": [
            {"name": "Fetch Claim Details", "action_type": "call_tool", "params": {"tool_name": "getClaimDetails"}},
            {"name": "Analyze Denial Reason", "action_type": "analyze", "params": {"model": "denial_reason_classifier"}},
            {"name": "Generate Appeal Letter", "action_type": "call_tool", "params": {"tool_name": "generateAppealLetter"}},
            {"name": "Submit Appeal", "action_type": "call_tool", "params": {"tool_name": "submitAppeal"}},
        ],
    },
    {
        "name": "EligibilityVerification",
        "description": "Re-verify patient eligibility workflow",
        "conditions": {"exception_type": "ELIGIBILITY_MISMATCH"},
        "steps": [
            {"name": "Fetch Patient Info", "action_type": "call_tool", "params": {"tool_name": "getPatientInfo"}},
            {"name": "Re-verify Eligibility", "action_type": "call_tool", "params": {"tool_name": "checkEligibility"}},
            {"name": "Update Records", "action_type": "call_tool", "params": {"tool_name": "updateEligibilityRecord"}},
        ],
    },
]

# Finance Tools
FINANCE_TOOLS = [
    {"name": "getSettlement", "type": "http", "description": "Fetch settlement details by ID"},
    {"name": "verifySSI", "type": "http", "description": "Verify Standard Settlement Instructions"},
    {"name": "triggerSettlementRetry", "type": "http", "description": "Trigger settlement retry workflow"},
    {"name": "getPositions", "type": "http", "description": "Fetch position snapshot"},
    {"name": "getExecutions", "type": "http", "description": "Fetch trade executions"},
    {"name": "recalculatePosition", "type": "http", "description": "Recalculate position from trades"},
    {"name": "getCashMovements", "type": "http", "description": "Fetch cash movement records"},
    {"name": "postCashAdjustment", "type": "http", "description": "Post cash adjustment entry"},
    {"name": "getRegReport", "type": "http", "description": "Fetch regulatory report details"},
    {"name": "regenerateRegReport", "type": "http", "description": "Regenerate regulatory report"},
    {"name": "submitRegReport", "type": "http", "description": "Submit report to regulatory authority"},
]

# Healthcare Tools
HEALTHCARE_TOOLS = [
    {"name": "getClaimDetails", "type": "http", "description": "Fetch claim details by ID"},
    {"name": "generateAppealLetter", "type": "http", "description": "Generate appeal letter from template"},
    {"name": "submitAppeal", "type": "http", "description": "Submit appeal to payer"},
    {"name": "getPatientInfo", "type": "http", "description": "Fetch patient demographic info"},
    {"name": "checkEligibility", "type": "http", "description": "Check real-time eligibility"},
    {"name": "updateEligibilityRecord", "type": "http", "description": "Update eligibility record"},
]


# =============================================================================
# Database Connection
# =============================================================================

async def get_db_session():
    """Create database session."""
    import os
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://sentinai:sentinai@localhost:5432/sentinai"
    )
    
    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session(), engine


def compute_checksum(content: dict) -> str:
    """Compute SHA256 checksum for pack content."""
    content_str = json.dumps(content, sort_keys=True)
    return hashlib.sha256(content_str.encode()).hexdigest()[:16]


# =============================================================================
# Seeding Functions
# =============================================================================

async def seed_tenants(session: AsyncSession) -> dict[str, bool]:
    """Seed demo tenants. Returns dict of tenant_id -> created status."""
    from src.infrastructure.db.models import Tenant, TenantStatus
    
    logger.info("Seeding tenants...")
    results = {}
    
    for tenant_id, config in DEMO_CONFIG["tenants"].items():
        # Check if exists
        result = await session.execute(
            select(Tenant).where(Tenant.tenant_id == tenant_id)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.info(f"  ✓ Tenant {tenant_id} already exists")
            results[tenant_id] = False
        else:
            tenant = Tenant(
                tenant_id=tenant_id,
                name=config["name"],
                status=TenantStatus.ACTIVE,
                created_by="seed_demo",
            )
            session.add(tenant)
            logger.info(f"  + Created tenant: {tenant_id}")
            results[tenant_id] = True
    
    await session.commit()
    return results


async def seed_domain_packs(session: AsyncSession) -> dict[str, int]:
    """Seed domain packs. Returns dict of domain -> pack_id."""
    from src.infrastructure.db.models import DomainPack, PackStatus
    
    logger.info("Seeding domain packs...")
    results = {}
    
    domain_content = {
        "Finance": {
            "domainName": "Finance",
            "description": "Capital Markets Trading Exception Management",
            "exceptionTypes": {et["type"]: {"description": et["description"]} for et in FINANCE_EXCEPTION_TYPES},
            "severityRules": [
                {"condition": "exceptionType == 'POSITION_BREAK'", "severity": "CRITICAL"},
                {"condition": "exceptionType == 'SETTLEMENT_FAIL'", "severity": "HIGH"},
                {"condition": "exceptionType == 'CASH_BREAK'", "severity": "HIGH"},
            ],
            "playbooks": [pb["name"] for pb in FINANCE_PLAYBOOKS],
            "tools": [t["name"] for t in FINANCE_TOOLS],
        },
        "Healthcare": {
            "domainName": "Healthcare",
            "description": "Healthcare Claims and Care Operations",
            "exceptionTypes": {et["type"]: {"description": et["description"]} for et in HEALTHCARE_EXCEPTION_TYPES},
            "severityRules": [
                {"condition": "exceptionType == 'AUTH_EXPIRY'", "severity": "CRITICAL"},
                {"condition": "exceptionType == 'CLAIM_DENIAL'", "severity": "HIGH"},
            ],
            "playbooks": [pb["name"] for pb in HEALTHCARE_PLAYBOOKS],
            "tools": [t["name"] for t in HEALTHCARE_TOOLS],
        },
    }
    
    for domain in DEMO_CONFIG["domain_packs"]:
        content = domain_content.get(domain, {"domainName": domain})
        checksum = compute_checksum(content)
        version = "v1.0"
        
        # Check if exists
        result = await session.execute(
            select(DomainPack).where(
                DomainPack.domain == domain,
                DomainPack.version == version
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.info(f"  ✓ Domain pack {domain} v1.0 already exists (id={existing.id})")
            results[domain] = existing.id
        else:
            pack = DomainPack(
                domain=domain,
                version=version,
                content_json=content,
                checksum=checksum,
                status=PackStatus.ACTIVE,
                created_by="seed_demo",
            )
            session.add(pack)
            await session.flush()
            logger.info(f"  + Created domain pack: {domain} v1.0 (id={pack.id})")
            results[domain] = pack.id
    
    await session.commit()
    return results


async def seed_tenant_packs(session: AsyncSession) -> dict[str, int]:
    """Seed tenant packs with overrides. Returns dict of tenant_id -> pack_id."""
    from src.infrastructure.db.models import TenantPack, PackStatus
    
    logger.info("Seeding tenant packs...")
    results = {}
    
    tenant_content = {
        "TENANT_FINANCE_001": {
            "tenantId": "TENANT_FINANCE_001",
            "domainName": "Finance",
            "description": "Custom overrides for Acme Capital Partners",
            "customSeverityOverrides": [
                {"exceptionType": "REG_REPORT_REJECTED", "severity": "CRITICAL"},  # Override: elevated
            ],
            "humanApprovalRules": [
                {"severity": "CRITICAL", "requireApproval": True},
                {"severity": "HIGH", "requireApproval": False},
            ],
            "approvedTools": [t["name"] for t in FINANCE_TOOLS],
            "customPlaybooks": [],
        },
        "TENANT_HEALTH_001": {
            "tenantId": "TENANT_HEALTH_001",
            "domainName": "Healthcare",
            "description": "Custom overrides for MedCare Health Systems",
            "customSeverityOverrides": [],
            "humanApprovalRules": [
                {"severity": "CRITICAL", "requireApproval": True},
                {"severity": "HIGH", "requireApproval": True},  # Healthcare requires more approvals
            ],
            "approvedTools": [t["name"] for t in HEALTHCARE_TOOLS],
            "customPlaybooks": [],
        },
    }
    
    for tenant_id, content in tenant_content.items():
        checksum = compute_checksum(content)
        version = "v1.0"
        
        # Check if exists
        result = await session.execute(
            select(TenantPack).where(
                TenantPack.tenant_id == tenant_id,
                TenantPack.version == version
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.info(f"  ✓ Tenant pack {tenant_id} v1.0 already exists (id={existing.id})")
            results[tenant_id] = existing.id
        else:
            pack = TenantPack(
                tenant_id=tenant_id,
                version=version,
                content_json=content,
                checksum=checksum,
                status=PackStatus.ACTIVE,
                created_by="seed_demo",
            )
            session.add(pack)
            await session.flush()
            logger.info(f"  + Created tenant pack: {tenant_id} v1.0 (id={pack.id})")
            results[tenant_id] = pack.id
    
    await session.commit()
    return results


async def seed_playbooks(session: AsyncSession) -> dict[str, dict[str, int]]:
    """Seed playbooks for each tenant. Returns nested dict of tenant_id -> playbook_name -> playbook_id."""
    from src.infrastructure.db.models import Playbook, PlaybookStep
    
    logger.info("Seeding playbooks...")
    results = {}
    
    tenant_playbooks = {
        "TENANT_FINANCE_001": FINANCE_PLAYBOOKS,
        "TENANT_HEALTH_001": HEALTHCARE_PLAYBOOKS,
    }
    
    for tenant_id, playbooks in tenant_playbooks.items():
        results[tenant_id] = {}
        
        for pb_config in playbooks:
            # Check if exists (use .first() in case of duplicates)
            result = await session.execute(
                select(Playbook).where(
                    Playbook.tenant_id == tenant_id,
                    Playbook.name == pb_config["name"]
                ).limit(1)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                logger.info(f"  ✓ Playbook {pb_config['name']} exists for {tenant_id}")
                results[tenant_id][pb_config["name"]] = existing.playbook_id
            else:
                playbook = Playbook(
                    tenant_id=tenant_id,
                    name=pb_config["name"],
                    version=1,
                    conditions=pb_config["conditions"],
                )
                session.add(playbook)
                await session.flush()
                
                # Add steps
                for idx, step_config in enumerate(pb_config["steps"], 1):
                    step = PlaybookStep(
                        playbook_id=playbook.playbook_id,
                        step_order=idx,
                        name=step_config["name"],
                        action_type=step_config["action_type"],
                        params=step_config["params"],
                    )
                    session.add(step)
                
                logger.info(f"  + Created playbook: {pb_config['name']} with {len(pb_config['steps'])} steps")
                results[tenant_id][pb_config["name"]] = playbook.playbook_id
    
    await session.commit()
    return results


async def seed_tools(session: AsyncSession) -> dict[str, dict[str, int]]:
    """Seed tools for each tenant. Returns nested dict of tenant_id -> tool_name -> tool_id."""
    from src.infrastructure.db.models import ToolDefinition
    
    logger.info("Seeding tools...")
    results = {}
    
    tenant_tools = {
        "TENANT_FINANCE_001": FINANCE_TOOLS,
        "TENANT_HEALTH_001": HEALTHCARE_TOOLS,
    }
    
    for tenant_id, tools in tenant_tools.items():
        results[tenant_id] = {}
        
        for tool_config in tools:
            # Check if exists (use limit(1) in case of duplicates)
            result = await session.execute(
                select(ToolDefinition).where(
                    ToolDefinition.tenant_id == tenant_id,
                    ToolDefinition.name == tool_config["name"]
                ).limit(1)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                logger.info(f"  ✓ Tool {tool_config['name']} exists for {tenant_id}")
                results[tenant_id][tool_config["name"]] = existing.tool_id
            else:
                tool = ToolDefinition(
                    tenant_id=tenant_id,
                    name=tool_config["name"],
                    type=tool_config["type"],
                    config={
                        "description": tool_config["description"],
                        "endpoint": f"https://api.demo.com/{tool_config['name']}",
                        "method": "POST",
                        "auth": {"type": "api_key"},
                    },
                )
                session.add(tool)
                await session.flush()
                logger.info(f"  + Created tool: {tool_config['name']} for {tenant_id}")
                results[tenant_id][tool_config["name"]] = tool.tool_id
    
    await session.commit()
    return results


async def seed_exceptions(
    session: AsyncSession,
    playbook_ids: dict[str, dict[str, int]],
    tool_ids: dict[str, dict[str, int]],
) -> list[dict]:
    """Seed exceptions with varying states. Returns list of created exception info."""
    from src.infrastructure.db.models import (
        Exception as ExceptionModel,
        ExceptionEvent,
        ExceptionSeverity,
        ExceptionStatus,
        ActorType,
        ToolExecution,
        ToolExecutionStatus,
        GovernanceAuditEvent,
    )
    
    logger.info("Seeding exceptions...")
    results = []
    
    # Define exception scenarios
    scenarios = [
        # Finance exceptions - 12 total
        # 5 with recommended playbook, 3 with executed steps
        {"tenant": "TENANT_FINANCE_001", "type": "SETTLEMENT_FAIL", "severity": "high", "status": "open", "playbook": None, "executed_steps": 0},
        {"tenant": "TENANT_FINANCE_001", "type": "SETTLEMENT_FAIL", "severity": "high", "status": "analyzing", "playbook": "SettlementFailureResolution", "executed_steps": 2},
        {"tenant": "TENANT_FINANCE_001", "type": "SETTLEMENT_FAIL", "severity": "critical", "status": "resolved", "playbook": "SettlementFailureResolution", "executed_steps": 4},
        {"tenant": "TENANT_FINANCE_001", "type": "POSITION_BREAK", "severity": "critical", "status": "escalated", "playbook": "PositionBreakInvestigation", "executed_steps": 3},
        {"tenant": "TENANT_FINANCE_001", "type": "POSITION_BREAK", "severity": "critical", "status": "analyzing", "playbook": "PositionBreakInvestigation", "executed_steps": 1},
        {"tenant": "TENANT_FINANCE_001", "type": "CASH_BREAK", "severity": "high", "status": "open", "playbook": None, "executed_steps": 0},
        {"tenant": "TENANT_FINANCE_001", "type": "CASH_BREAK", "severity": "medium", "status": "resolved", "playbook": "CashBreakReconciliation", "executed_steps": 3},
        {"tenant": "TENANT_FINANCE_001", "type": "FAILED_ALLOCATION", "severity": "medium", "status": "open", "playbook": None, "executed_steps": 0},
        {"tenant": "TENANT_FINANCE_001", "type": "REG_REPORT_REJECTED", "severity": "high", "status": "analyzing", "playbook": "RegulatoryReportRepair", "executed_steps": 2},
        {"tenant": "TENANT_FINANCE_001", "type": "REG_REPORT_REJECTED", "severity": "high", "status": "open", "playbook": None, "executed_steps": 0},
        {"tenant": "TENANT_FINANCE_001", "type": "SETTLEMENT_FAIL", "severity": "medium", "status": "resolved", "playbook": None, "executed_steps": 0},
        {"tenant": "TENANT_FINANCE_001", "type": "POSITION_BREAK", "severity": "high", "status": "open", "playbook": None, "executed_steps": 0},
        
        # Healthcare exceptions - 8 total
        {"tenant": "TENANT_HEALTH_001", "type": "CLAIM_DENIAL", "severity": "high", "status": "open", "playbook": None, "executed_steps": 0},
        {"tenant": "TENANT_HEALTH_001", "type": "CLAIM_DENIAL", "severity": "critical", "status": "analyzing", "playbook": "ClaimDenialAppeal", "executed_steps": 2},
        {"tenant": "TENANT_HEALTH_001", "type": "CLAIM_DENIAL", "severity": "high", "status": "resolved", "playbook": "ClaimDenialAppeal", "executed_steps": 4},
        {"tenant": "TENANT_HEALTH_001", "type": "ELIGIBILITY_MISMATCH", "severity": "medium", "status": "open", "playbook": None, "executed_steps": 0},
        {"tenant": "TENANT_HEALTH_001", "type": "ELIGIBILITY_MISMATCH", "severity": "medium", "status": "analyzing", "playbook": "EligibilityVerification", "executed_steps": 1},
        {"tenant": "TENANT_HEALTH_001", "type": "CODING_ERROR", "severity": "medium", "status": "open", "playbook": None, "executed_steps": 0},
        {"tenant": "TENANT_HEALTH_001", "type": "AUTH_EXPIRY", "severity": "critical", "status": "escalated", "playbook": None, "executed_steps": 0},
        {"tenant": "TENANT_HEALTH_001", "type": "COORDINATION_FAILURE", "severity": "low", "status": "resolved", "playbook": None, "executed_steps": 0},
    ]
    
    severity_map = {
        "low": ExceptionSeverity.LOW,
        "medium": ExceptionSeverity.MEDIUM,
        "high": ExceptionSeverity.HIGH,
        "critical": ExceptionSeverity.CRITICAL,
    }
    
    status_map = {
        "open": ExceptionStatus.OPEN,
        "analyzing": ExceptionStatus.ANALYZING,
        "resolved": ExceptionStatus.RESOLVED,
        "escalated": ExceptionStatus.ESCALATED,
    }
    
    source_systems_by_type = {
        **{et["type"]: et["source_systems"] for et in FINANCE_EXCEPTION_TYPES},
        **{et["type"]: et["source_systems"] for et in HEALTHCARE_EXCEPTION_TYPES},
    }
    
    domain_by_tenant = {
        "TENANT_FINANCE_001": "Finance",
        "TENANT_HEALTH_001": "Healthcare",
    }
    
    # Counters for exception IDs
    exc_counters = {"TENANT_FINANCE_001": 1, "TENANT_HEALTH_001": 1}
    
    for scenario in scenarios:
        tenant_id = scenario["tenant"]
        domain = domain_by_tenant[tenant_id]
        exc_type = scenario["type"]
        
        # Generate unique exception ID
        exc_id = f"EX-DEMO-{tenant_id[-3:]}-{exc_counters[tenant_id]:04d}"
        exc_counters[tenant_id] += 1
        
        # Check if exception already exists
        result = await session.execute(
            select(ExceptionModel).where(ExceptionModel.exception_id == exc_id)
        )
        if result.scalar_one_or_none():
            logger.info(f"  ✓ Exception {exc_id} already exists")
            continue
        
        # Select source system
        source_systems = source_systems_by_type.get(exc_type, ["SystemX"])
        source_system = source_systems[exc_counters[tenant_id] % len(source_systems)]
        
        # Calculate timestamps
        base_time = datetime.now(timezone.utc) - timedelta(hours=exc_counters[tenant_id] * 6)
        sla_hours = {"critical": 4, "high": 8, "medium": 24, "low": 72}
        sla_deadline = base_time + timedelta(hours=sla_hours.get(scenario["severity"], 24))
        
        # Get playbook ID if assigned
        playbook_id = None
        current_step = None
        if scenario["playbook"] and scenario["playbook"] in playbook_ids.get(tenant_id, {}):
            playbook_id = playbook_ids[tenant_id][scenario["playbook"]]
            current_step = scenario["executed_steps"] if scenario["executed_steps"] > 0 else 1
        
        # Create exception
        exception = ExceptionModel(
            exception_id=exc_id,
            tenant_id=tenant_id,
            domain=domain,
            type=exc_type,
            severity=severity_map[scenario["severity"]],
            status=status_map[scenario["status"]],
            source_system=source_system,
            entity=f"ENTITY-{exc_counters[tenant_id]:05d}",
            amount=round(10000 + (exc_counters[tenant_id] * 5000), 2) if domain == "Finance" else None,
            sla_deadline=sla_deadline,
            owner="ops_agent" if scenario["status"] != "open" else None,
            current_playbook_id=playbook_id,
            current_step=current_step,
        )
        session.add(exception)
        await session.flush()
        
        logger.info(f"  + Created exception: {exc_id} ({exc_type}, {scenario['severity']}, {scenario['status']})")
        
        # Create exception events for timeline
        event_time = base_time
        
        # ExceptionIngested event
        event = ExceptionEvent(
            exception_id=exc_id,
            tenant_id=tenant_id,
            event_type="ExceptionIngested",
            actor_type=ActorType.SYSTEM,
            actor_id="intake_worker",
            payload={
                "source": source_system,
                "exception_type": exc_type,
                "raw_data": {"demo": True},
            },
        )
        session.add(event)
        event_time += timedelta(minutes=1)
        
        # TriageCompleted event
        if scenario["status"] != "open":
            event = ExceptionEvent(
                exception_id=exc_id,
                tenant_id=tenant_id,
                event_type="TriageCompleted",
                actor_type=ActorType.AGENT,
                actor_id="triage_agent",
                payload={
                    "assigned_severity": scenario["severity"],
                    "recommended_playbook": scenario["playbook"],
                    "confidence": 0.92,
                },
            )
            session.add(event)
            event_time += timedelta(minutes=5)
        
        # PlaybookStarted and step events
        if scenario["playbook"] and scenario["executed_steps"] > 0:
            # PlaybookStarted
            event = ExceptionEvent(
                exception_id=exc_id,
                tenant_id=tenant_id,
                event_type="PlaybookStarted",
                actor_type=ActorType.AGENT,
                actor_id="playbook_agent",
                payload={
                    "playbook_name": scenario["playbook"],
                    "playbook_id": playbook_id,
                },
            )
            session.add(event)
            event_time += timedelta(minutes=2)
            
            # Step completion events with tool executions
            for step_num in range(1, scenario["executed_steps"] + 1):
                # PlaybookStepCompleted
                event = ExceptionEvent(
                    exception_id=exc_id,
                    tenant_id=tenant_id,
                    event_type="PlaybookStepCompleted",
                    actor_type=ActorType.AGENT,
                    actor_id="playbook_agent",
                    payload={
                        "step_number": step_num,
                        "step_name": f"Step {step_num}",
                        "result": "success",
                    },
                )
                session.add(event)
                
                # Create tool execution for first 2 steps
                if step_num <= 2:
                    # Find a tool for this tenant
                    tool_name = list(tool_ids.get(tenant_id, {}).keys())[0] if tool_ids.get(tenant_id) else None
                    if tool_name:
                        tool_id = tool_ids[tenant_id][tool_name]
                        
                        # ToolExecution record
                        tool_exec = ToolExecution(
                            tenant_id=tenant_id,
                            tool_id=tool_id,
                            exception_id=exc_id,
                            status=ToolExecutionStatus.SUCCEEDED,
                            requested_by_actor_type=ActorType.AGENT,
                            requested_by_actor_id="playbook_agent",
                            input_payload={"exception_id": exc_id, "step": step_num},
                            output_payload={"status": "success", "data": {"demo": True}},
                        )
                        session.add(tool_exec)
                        
                        # ToolExecutionCompleted event
                        event = ExceptionEvent(
                            exception_id=exc_id,
                            tenant_id=tenant_id,
                            event_type="ToolExecutionCompleted",
                            actor_type=ActorType.AGENT,
                            actor_id="tool_agent",
                            payload={
                                "tool_name": tool_name,
                                "tool_id": tool_id,
                                "result": "success",
                            },
                        )
                        session.add(event)
                
                event_time += timedelta(minutes=3)
        
        # Governance audit event for playbook assignment
        if scenario["playbook"]:
            audit_event = GovernanceAuditEvent(
                event_type="PLAYBOOK_RECOMMENDED",
                actor_id="triage_agent",
                actor_role="agent",
                tenant_id=tenant_id,
                domain=domain,
                entity_type="playbook",
                entity_id=str(playbook_id) if playbook_id else "unknown",
                action="link",
                after_json={
                    "exception_id": exc_id,
                    "playbook_name": scenario["playbook"],
                    "confidence": 0.92,
                },
            )
            session.add(audit_event)
        
        results.append({
            "exception_id": exc_id,
            "tenant_id": tenant_id,
            "type": exc_type,
            "severity": scenario["severity"],
            "status": scenario["status"],
            "playbook": scenario["playbook"],
            "executed_steps": scenario["executed_steps"],
        })
    
    await session.commit()
    return results


async def run_copilot_indexing(session: AsyncSession):
    """Index the seeded data for Copilot RAG."""
    logger.info("Indexing data for Copilot RAG...")
    
    try:
        from src.services.copilot.embedding_service import EmbeddingService
        from src.infrastructure.repositories.copilot_document_repository import (
            CopilotDocumentRepository,
            DocumentChunk,
        )
        from src.infrastructure.db.models import (
            Exception as ExceptionModel,
            Playbook,
            PlaybookStep,
            ToolDefinition,
        )
        
        embedding_service = EmbeddingService()
        doc_repo = CopilotDocumentRepository(session)
        
        indexed_count = 0
        
        for tenant_id in DEMO_CONFIG["tenants"].keys():
            # Index exceptions
            result = await session.execute(
                select(ExceptionModel).where(ExceptionModel.tenant_id == tenant_id)
            )
            exceptions = result.scalars().all()
            
            for exc in exceptions:
                content = f"Exception {exc.exception_id}: {exc.type} ({exc.severity.value if exc.severity else 'unknown'} severity, {exc.status.value if exc.status else 'unknown'} status) from {exc.source_system}"
                embedding_result = await embedding_service.generate_embedding(content)
                
                chunk = DocumentChunk(
                    source_type="resolved_exception",
                    source_id=str(exc.exception_id),
                    chunk_id=f"exc-{exc.exception_id}-0",
                    chunk_index=0,
                    content=content,
                    embedding=embedding_result.embedding,
                    embedding_model=embedding_result.model,
                    embedding_dimension=embedding_result.dimension,
                    domain=exc.domain,
                    version="1",
                    metadata={"exception_id": str(exc.exception_id), "type": exc.type},
                )
                await doc_repo.upsert_chunks_batch(tenant_id, [chunk])
                indexed_count += 1
            
            # Index playbooks
            result = await session.execute(
                select(Playbook).where(Playbook.tenant_id == tenant_id)
            )
            playbooks = result.scalars().all()
            
            for pb in playbooks:
                # Get steps
                steps_result = await session.execute(
                    select(PlaybookStep).where(PlaybookStep.playbook_id == pb.playbook_id)
                )
                steps = steps_result.scalars().all()
                step_names = [s.name for s in steps]
                
                content = f"Playbook: {pb.name}. Steps: {', '.join(step_names)}. Conditions: {json.dumps(pb.conditions)}"
                embedding_result = await embedding_service.generate_embedding(content)
                
                chunk = DocumentChunk(
                    source_type="playbook",
                    source_id=str(pb.playbook_id),
                    chunk_id=f"pb-{pb.playbook_id}-0",
                    chunk_index=0,
                    content=content,
                    embedding=embedding_result.embedding,
                    embedding_model=embedding_result.model,
                    embedding_dimension=embedding_result.dimension,
                    domain=DEMO_CONFIG["tenants"][tenant_id]["domain"],
                    version=str(pb.version),
                    metadata={"playbook_name": pb.name, "step_count": len(steps)},
                )
                await doc_repo.upsert_chunks_batch(tenant_id, [chunk])
                indexed_count += 1
        
        await session.commit()
        logger.info(f"  ✓ Indexed {indexed_count} documents for Copilot")
        return indexed_count
        
    except Exception as e:
        logger.warning(f"  ⚠ Copilot indexing skipped: {e}")
        return 0


async def reset_demo_data(session: AsyncSession):
    """Reset all demo data (for --reset flag)."""
    logger.info("Resetting demo data...")
    
    from src.infrastructure.db.models import (
        GovernanceAuditEvent,
        ToolExecution,
        ExceptionEvent,
        CopilotDocument,
    )
    
    for tenant_id in DEMO_CONFIG["tenants"].keys():
        # Delete in correct order for FK constraints
        tables_to_clear = [
            ("governance_audit_event", "tenant_id"),
            ("tool_execution", "tenant_id"),
            ("exception_event", "tenant_id"),
            ("exception", "tenant_id"),
            ("copilot_documents", "tenant_id"),
            ("playbook_step", None),  # via playbook_id
            ("playbook", "tenant_id"),
            ("tool_definition", "tenant_id"),
            ("tenant_packs", "tenant_id"),
        ]
        
        for table, tenant_col in tables_to_clear:
            try:
                if tenant_col:
                    await session.execute(
                        text(f"DELETE FROM {table} WHERE {tenant_col} = :tenant_id"),
                        {"tenant_id": tenant_id}
                    )
                elif table == "playbook_step":
                    await session.execute(
                        text("""
                            DELETE FROM playbook_step 
                            WHERE playbook_id IN (
                                SELECT playbook_id FROM playbook WHERE tenant_id = :tenant_id
                            )
                        """),
                        {"tenant_id": tenant_id}
                    )
            except Exception as e:
                logger.debug(f"  Note: {table} clear skipped ({e})")
        
        logger.info(f"  ✓ Cleared data for tenant: {tenant_id}")
    
    # Clear domain packs
    for domain in DEMO_CONFIG["domain_packs"]:
        try:
            await session.execute(
                text("DELETE FROM domain_packs WHERE domain = :domain"),
                {"domain": domain}
            )
        except Exception:
            pass
    
    await session.commit()
    logger.info("Reset complete.")


def print_verification_summary(exceptions: list[dict]):
    """Print verification URLs and demo click path."""
    
    print("\n" + "=" * 70)
    print("[SUCCESS] DEMO DATA SEEDED SUCCESSFULLY")
    print("=" * 70)
    
    print("\n[URLS] VERIFICATION URLs:")
    print("-" * 40)
    print("  UI:           http://localhost:3000")
    print("  API Docs:     http://localhost:8000/docs")
    print("  Exceptions:   http://localhost:3000/exceptions")
    print("  Admin Packs:  http://localhost:3000/admin/packs")
    print("  Playbooks:    http://localhost:3000/admin/playbooks")
    print("  Workflow:     http://localhost:3000/workflow")
    print("  Copilot:      http://localhost:3000/copilot")
    
    print("\n[DEMO] DEMO CLICK PATH:")
    print("-" * 40)
    print("  1. Open http://localhost:3000")
    print("  2. Select 'TENANT_FINANCE_001' from tenant dropdown")
    print("  3. Click 'Exceptions' -> See finance exceptions")
    print("  4. Filter by 'Critical' severity -> See POSITION_BREAK exceptions")
    print("  5. Click on EX-DEMO-* -> View exception timeline")
    print("  6. See 'Workflow' tab -> View playbook execution steps")
    print("  7. Navigate to 'Admin > Packs' -> See Finance domain pack")
    print("  8. Navigate to 'Admin > Playbooks' -> See SettlementFailureResolution")
    print("  9. Switch tenant to 'TENANT_HEALTH_001' -> See healthcare exceptions")
    print(" 10. Open Copilot -> Ask 'What playbooks handle settlement failures?'")
    
    if exceptions:
        print("\n[DATA] DATA SUMMARY (newly created):")
        print("-" * 40)
        
        # Count by tenant
        by_tenant = {}
        for exc in exceptions:
            tid = exc["tenant_id"]
            if tid not in by_tenant:
                by_tenant[tid] = {"total": 0, "with_playbook": 0, "with_executed_steps": 0}
            by_tenant[tid]["total"] += 1
            if exc["playbook"]:
                by_tenant[tid]["with_playbook"] += 1
            if exc["executed_steps"] > 0:
                by_tenant[tid]["with_executed_steps"] += 1
        
        for tenant_id, counts in by_tenant.items():
            print(f"\n  {tenant_id}:")
            print(f"    Total exceptions:          {counts['total']}")
            print(f"    With recommended playbook: {counts['with_playbook']}")
            print(f"    With executed steps:       {counts['with_executed_steps']}")
    else:
        print("\n[DATA] DATA SUMMARY:")
        print("-" * 40)
        print("  All demo data already exists (idempotent run)")
    
    print("\n" + "=" * 70)
    print("[OK] Ready for demo!")
    print("=" * 70 + "\n")


async def verify_data(session: AsyncSession) -> dict:
    """Verify seeded data exists and return counts."""
    from src.infrastructure.db.models import (
        Tenant,
        DomainPack,
        TenantPack,
        Playbook,
        ToolDefinition,
        Exception as ExceptionModel,
        ExceptionEvent,
        ToolExecution,
        GovernanceAuditEvent,
    )
    
    counts = {}
    
    for model, name in [
        (Tenant, "tenants"),
        (DomainPack, "domain_packs"),
        (TenantPack, "tenant_packs"),
        (Playbook, "playbooks"),
        (ToolDefinition, "tools"),
        (ExceptionModel, "exceptions"),
        (ExceptionEvent, "exception_events"),
        (ToolExecution, "tool_executions"),
        (GovernanceAuditEvent, "audit_events"),
    ]:
        result = await session.execute(select(model))
        counts[name] = len(result.scalars().all())
    
    return counts


# =============================================================================
# Main Entry Point
# =============================================================================

async def main(reset: bool = False, verify_only: bool = False):
    """Main seeding function."""
    session, engine = await get_db_session()
    
    try:
        if verify_only:
            counts = await verify_data(session)
            print("\n[DATA] Current Data Counts:")
            for name, count in counts.items():
                print(f"  {name}: {count}")
            return
        
        if reset:
            await reset_demo_data(session)
        
        # Seed in order
        await seed_tenants(session)
        await seed_domain_packs(session)
        await seed_tenant_packs(session)
        playbook_ids = await seed_playbooks(session)
        tool_ids = await seed_tools(session)
        exceptions = await seed_exceptions(session, playbook_ids, tool_ids)
        await run_copilot_indexing(session)
        
        # Print verification summary
        print_verification_summary(exceptions)
        
    except Exception as e:
        logger.error(f"Seeding failed: {e}", exc_info=True)
        await session.rollback()
        raise
    finally:
        await session.close()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed demo data for SentinAI platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/seed_demo.py              # Seed demo data (idempotent)
  python scripts/seed_demo.py --reset      # Reset and reseed all demo data
  python scripts/seed_demo.py --verify-only # Just verify existing data counts
        """,
    )
    
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset all demo data before seeding",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing data, don't seed",
    )
    
    args = parser.parse_args()
    
    asyncio.run(main(reset=args.reset, verify_only=args.verify_only))
