"""
Seed script to generate example data for UI testing.

This script creates sample exceptions, guardrail recommendations, and ensures
config data is available for all UI features.

Usage:
    python scripts/seed_ui_data.py
"""

import asyncio
import json
import logging
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.domainpack.loader import load_domain_pack
from src.domainpack.storage import DomainPackStorage
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.orchestrator.runner import run_pipeline
from src.orchestrator.store import get_exception_store
from src.tenantpack.loader import load_tenant_policy, TenantPolicyRegistry
from src.learning.guardrail_recommender import GuardrailRecommender

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sample_exceptions(tenant_id: str, domain: str, count: int = 20) -> list[dict]:
    """Create sample exception payloads."""
    exceptions = []
    base_time = datetime.now(timezone.utc)
    
    # Different exception types based on domain
    if domain == "CapitalMarketsTrading":
        exception_types = [
            "TradeSettlementFailure",
            "PriceDiscrepancy",
            "RegulatoryViolation",
            "MarginCallException",
            "OrderExecutionError",
        ]
        source_systems = ["TradingPlatform", "SettlementSystem", "RiskManagement", "Compliance"]
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    elif domain == "HealthcareClaimsAndCareOps":
        exception_types = [
            "ClaimRejection",
            "PriorAuthRequired",
            "DuplicateClaim",
            "CoverageException",
            "BillingError",
        ]
        source_systems = ["ClaimsSystem", "EHR", "BillingPlatform", "Authorization"]
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    else:
        exception_types = ["GenericException", "ProcessingError", "ValidationFailure"]
        source_systems = ["SystemA", "SystemB", "SystemC"]
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    
    statuses = ["OPEN", "IN_PROGRESS", "RESOLVED", "ESCALATED"]
    
    for i in range(count):
        exception_type = exception_types[i % len(exception_types)]
        source_system = source_systems[i % len(source_systems)]
        severity = severities[i % len(severities)]
        status = statuses[i % len(statuses)]
        
        # Create timestamp with some variation
        timestamp = base_time - timedelta(hours=i * 2, minutes=i * 15)
        
        exception = {
            "sourceSystem": source_system,
            "rawPayload": {
                "exceptionId": f"EXC_{tenant_id}_{i:04d}",
                "timestamp": timestamp.isoformat(),
                "type": exception_type,
                "severity": severity,
                "amount": 1000.0 + (i * 100),
                "accountId": f"ACC_{i:05d}",
                "description": f"Sample {exception_type} exception #{i+1}",
                "metadata": {
                    "source": "seed_script",
                    "batch": "ui_demo",
                    "index": i,
                },
            },
        }
        exceptions.append(exception)
    
    return exceptions


async def seed_exceptions(tenant_id: str, domain_pack_path: str, tenant_policy_path: str):
    """Seed exceptions for a tenant."""
    logger.info(f"Seeding exceptions for tenant {tenant_id}...")
    
    # Load domain pack and tenant policy
    domain_pack = load_domain_pack(domain_pack_path)
    tenant_policy = load_tenant_policy(tenant_policy_path)
    
    # Create sample exceptions
    exceptions = create_sample_exceptions(tenant_id, domain_pack.domain_name, count=20)
    
    # Run pipeline to process exceptions
    result = await run_pipeline(
        domain_pack=domain_pack,
        tenant_policy=tenant_policy,
        exceptions_batch=exceptions,
        enable_parallel=False,  # Sequential for easier debugging
    )
    
    logger.info(f"Created {len(result['results'])} exceptions for tenant {tenant_id}")
    return result


def seed_guardrail_recommendations(tenant_id: str, domain: str):
    """Seed guardrail recommendations."""
    logger.info(f"Seeding guardrail recommendations for tenant {tenant_id}, domain {domain}...")
    
    recommender = GuardrailRecommender()
    
    # Create sample recommendations
    recommendations = []
    for i in range(5):
        recommendation = {
            "guardrailId": f"guardrail_{i+1}",
            "tenantId": tenant_id,
            "currentConfig": {
                "allowLists": ["tool1", "tool2"],
                "blockLists": [],
                "humanApprovalThreshold": 0.8,
            },
            "proposedChange": {
                "allowLists": ["tool1", "tool2", "tool3"],
                "blockLists": [],
                "humanApprovalThreshold": 0.75,
            },
            "reason": f"High false positive rate detected. Recommendation #{i+1} suggests lowering threshold to reduce false positives.",
            "impactAnalysis": {
                "expectedFalsePositiveReduction": 0.15,
                "riskLevel": "LOW",
                "affectedExceptions": 10 + i,
            },
            "reviewRequired": True,
            "createdAt": (datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
            "confidence": 0.7 + (i * 0.05),
            "metadata": {
                "source": "seed_script",
                "sample": True,
            },
        }
        recommendations.append(recommendation)
    
    # Save recommendations to file (GuardrailRecommender expects JSONL format)
    learning_dir = Path("runtime/learning")
    learning_dir.mkdir(parents=True, exist_ok=True)
    
    recommendations_file = learning_dir / f"{tenant_id}_{domain}_recommendations.jsonl"
    with open(recommendations_file, "w", encoding="utf-8") as f:
        for rec in recommendations:
            f.write(json.dumps(rec) + "\n")
    
    logger.info(f"Created {len(recommendations)} guardrail recommendations in {recommendations_file}")
    return recommendations


def copy_config_files():
    """Copy sample config files to runtime directories for config browser."""
    logger.info("Copying config files to runtime directories...")
    
    # Copy domain packs
    domain_pack_storage = DomainPackStorage()
    runtime_domainpacks = Path("runtime/domainpacks")
    runtime_domainpacks.mkdir(parents=True, exist_ok=True)
    
    # Copy finance domain pack
    finance_domain_pack = load_domain_pack("domainpacks/finance.sample.json")
    tenant_id = "tenant_001"
    tenant_dir = runtime_domainpacks / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    
    finance_pack_file = tenant_dir / f"{finance_domain_pack.domain_name}.json"
    shutil.copy("domainpacks/finance.sample.json", finance_pack_file)
    logger.info(f"Copied finance domain pack to {finance_pack_file}")
    
    # Copy healthcare domain pack
    healthcare_domain_pack = load_domain_pack("domainpacks/healthcare.sample.json")
    healthcare_pack_file = tenant_dir / f"{healthcare_domain_pack.domain_name}.json"
    shutil.copy("domainpacks/healthcare.sample.json", healthcare_pack_file)
    logger.info(f"Copied healthcare domain pack to {healthcare_pack_file}")
    
    # Copy tenant policies
    runtime_tenantpacks = Path("runtime/tenantpacks")
    runtime_tenantpacks.mkdir(parents=True, exist_ok=True)
    
    # Copy finance tenant policy
    finance_tenant_policy = load_tenant_policy("tenantpacks/tenant_finance.sample.json")
    finance_policy_file = runtime_tenantpacks / f"{finance_tenant_policy.tenant_id}.json"
    shutil.copy("tenantpacks/tenant_finance.sample.json", finance_policy_file)
    logger.info(f"Copied finance tenant policy to {finance_policy_file}")
    
    # Copy healthcare tenant policy
    healthcare_tenant_policy = load_tenant_policy("tenantpacks/tenant_healthcare.sample.json")
    healthcare_policy_file = runtime_tenantpacks / f"{healthcare_tenant_policy.tenant_id}.json"
    shutil.copy("tenantpacks/tenant_healthcare.sample.json", healthcare_policy_file)
    logger.info(f"Copied healthcare tenant policy to {healthcare_policy_file}")


async def main():
    """Main seed function."""
    logger.info("Starting UI data seeding...")
    
    # Copy config files first
    copy_config_files()
    
    # Seed data for multiple tenants
    tenants = [
        {
            "tenant_id": "tenant_001",
            "domain_pack": "domainpacks/finance.sample.json",
            "tenant_policy": "tenantpacks/tenant_finance.sample.json",
            "domain": "CapitalMarketsTrading",
        },
        {
            "tenant_id": "TENANT_001",
            "domain_pack": "domainpacks/finance.sample.json",
            "tenant_policy": "tenantpacks/tenant_finance.sample.json",
            "domain": "CapitalMarketsTrading",
        },
        {
            "tenant_id": "TENANT_002",
            "domain_pack": "domainpacks/healthcare.sample.json",
            "tenant_policy": "tenantpacks/tenant_healthcare.sample.json",
            "domain": "HealthcareClaimsAndCareOps",
        },
        {
            "tenant_id": "TENANT_FINANCE_001",
            "domain_pack": "domainpacks/finance.sample.json",
            "tenant_policy": "tenantpacks/tenant_finance.sample.json",
            "domain": "CapitalMarketsTrading",
        },
    ]
    
    # Seed exceptions for each tenant
    for tenant_config in tenants:
        try:
            await seed_exceptions(
                tenant_id=tenant_config["tenant_id"],
                domain_pack_path=tenant_config["domain_pack"],
                tenant_policy_path=tenant_config["tenant_policy"],
            )
            
            # Seed guardrail recommendations
            seed_guardrail_recommendations(
                tenant_id=tenant_config["tenant_id"],
                domain=tenant_config["domain"],
            )
        except Exception as e:
            logger.error(f"Error seeding data for tenant {tenant_config['tenant_id']}: {e}", exc_info=True)
    
    logger.info("UI data seeding completed!")
    logger.info("\nNext steps:")
    logger.info("1. Start the backend server: python -m uvicorn src.api.main:app --reload")
    logger.info("2. Start the UI dev server: cd ui && npm run dev")
    logger.info("3. Navigate to http://localhost:5173/login")
    logger.info("4. Select a tenant and API key to view the seeded data")


if __name__ == "__main__":
    asyncio.run(main())

