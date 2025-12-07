"""
Simple seed script to generate example data for UI testing using API calls.

This script uses HTTP requests to seed data, avoiding import dependencies.

Usage:
    python scripts/seed_ui_data_simple.py
    
Prerequisites:
    - Backend server must be running on http://localhost:8000
    - Install requests: pip install requests
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests module not found. Install it with: pip install requests")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"


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
    elif domain == "HealthcareClaimsAndCareOps":
        exception_types = [
            "ClaimRejection",
            "PriorAuthRequired",
            "DuplicateClaim",
            "CoverageException",
            "BillingError",
        ]
        source_systems = ["ClaimsSystem", "EHR", "BillingPlatform", "Authorization"]
    else:
        exception_types = ["GenericException", "ProcessingError", "ValidationFailure"]
        source_systems = ["SystemA", "SystemB", "SystemC"]
    
    for i in range(count):
        exception_type = exception_types[i % len(exception_types)]
        source_system = source_systems[i % len(source_systems)]
        
        # Create timestamp with some variation
        timestamp = base_time - timedelta(hours=i * 2, minutes=i * 15)
        
        exception = {
            "sourceSystem": source_system,
            "rawPayload": {
                "exceptionId": f"EXC_{tenant_id}_{i:04d}",
                "timestamp": timestamp.isoformat(),
                "type": exception_type,
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


def seed_exceptions_via_api(tenant_id: str, domain_pack_path: str, tenant_policy_path: str, api_key: str = "test-api-key-123"):
    """Seed exceptions via API."""
    logger.info(f"Seeding exceptions for tenant {tenant_id} via API...")
    
    # Read domain pack and tenant policy files
    domain_pack_path_obj = Path(domain_pack_path)
    tenant_policy_path_obj = Path(tenant_policy_path)
    
    if not domain_pack_path_obj.exists():
        logger.error(f"Domain pack not found: {domain_pack_path}")
        return
    
    if not tenant_policy_path_obj.exists():
        logger.error(f"Tenant policy not found: {tenant_policy_path}")
        return
    
    with open(domain_pack_path_obj, "r", encoding="utf-8") as f:
        domain_pack_data = json.load(f)
    
    with open(tenant_policy_path_obj, "r", encoding="utf-8") as f:
        tenant_policy_data = json.load(f)
    
    # Create sample exceptions
    domain_name = domain_pack_data.get("domainName", "UnknownDomain")
    exceptions = create_sample_exceptions(tenant_id, domain_name, count=20)
    
    # Prepare request payload
    request_payload = {
        "domainPackPath": str(domain_pack_path_obj.absolute()),
        "tenantPolicyPath": str(tenant_policy_path_obj.absolute()),
        "exceptions": exceptions,
    }
    
    # Call API
    try:
        response = requests.post(
            f"{BASE_URL}/run",
            json=request_payload,
            headers={
                "X-API-KEY": api_key,
                "Content-Type": "application/json",
            },
            timeout=300,  # 5 minutes timeout
        )
        response.raise_for_status()
        result = response.json()
        logger.info(f"Created {len(result.get('results', []))} exceptions for tenant {tenant_id}")
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"Error seeding exceptions via API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response: {e.response.text}")
        return None


def seed_guardrail_recommendations(tenant_id: str, domain: str):
    """Seed guardrail recommendations by creating JSONL file."""
    logger.info(f"Seeding guardrail recommendations for tenant {tenant_id}, domain {domain}...")
    
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
    runtime_domainpacks = Path("runtime/domainpacks")
    runtime_domainpacks.mkdir(parents=True, exist_ok=True)
    
    # Copy finance domain pack
    tenant_id = "tenant_001"
    tenant_dir = runtime_domainpacks / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    
    finance_pack_file = tenant_dir / "CapitalMarketsTrading.json"
    if Path("domainpacks/finance.sample.json").exists():
        import shutil
        shutil.copy("domainpacks/finance.sample.json", finance_pack_file)
        logger.info(f"Copied finance domain pack to {finance_pack_file}")
    
    # Copy healthcare domain pack
    healthcare_pack_file = tenant_dir / "HealthcareClaimsAndCareOps.json"
    if Path("domainpacks/healthcare.sample.json").exists():
        import shutil
        shutil.copy("domainpacks/healthcare.sample.json", healthcare_pack_file)
        logger.info(f"Copied healthcare domain pack to {healthcare_pack_file}")
    
    # Copy tenant policies
    runtime_tenantpacks = Path("runtime/tenantpacks")
    runtime_tenantpacks.mkdir(parents=True, exist_ok=True)
    
    # Copy finance tenant policy
    if Path("tenantpacks/tenant_finance.sample.json").exists():
        import shutil
        with open("tenantpacks/tenant_finance.sample.json", "r", encoding="utf-8") as f:
            finance_policy_data = json.load(f)
        finance_tenant_id = finance_policy_data.get("tenantId", "tenant_finance")
        finance_policy_file = runtime_tenantpacks / f"{finance_tenant_id}.json"
        shutil.copy("tenantpacks/tenant_finance.sample.json", finance_policy_file)
        logger.info(f"Copied finance tenant policy to {finance_policy_file}")
    
    # Copy healthcare tenant policy
    if Path("tenantpacks/tenant_healthcare.sample.json").exists():
        import shutil
        with open("tenantpacks/tenant_healthcare.sample.json", "r", encoding="utf-8") as f:
            healthcare_policy_data = json.load(f)
        healthcare_tenant_id = healthcare_policy_data.get("tenantId", "tenant_healthcare")
        healthcare_policy_file = runtime_tenantpacks / f"{healthcare_tenant_id}.json"
        shutil.copy("tenantpacks/tenant_healthcare.sample.json", healthcare_policy_file)
        logger.info(f"Copied healthcare tenant policy to {healthcare_policy_file}")


def main():
    """Main seed function."""
    logger.info("Starting UI data seeding (simple API-based version)...")
    logger.info(f"Using backend URL: {BASE_URL}")
    
    # Check if backend is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        response.raise_for_status()
        logger.info("Backend server is running")
    except requests.exceptions.RequestException:
        logger.error(f"Backend server is not running at {BASE_URL}")
        logger.error("Please start the backend server first:")
        logger.error("  python -m uvicorn src.api.main:app --reload")
        return
    
    # Copy config files first
    copy_config_files()
    
    # Seed data for multiple tenants
    # Note: Use tenant IDs that match the tenant policy files
    tenants = [
        {
            "tenant_id": "TENANT_FINANCE_001",  # Matches tenant_finance.sample.json
            "domain_pack": "domainpacks/finance.sample.json",
            "tenant_policy": "tenantpacks/tenant_finance.sample.json",
            "domain": "CapitalMarketsTrading",
            "api_key": "test_api_key_tenant_finance",  # Use matching API key
        },
    ]
    
    # Seed exceptions for each tenant
    for tenant_config in tenants:
        try:
            seed_exceptions_via_api(
                tenant_id=tenant_config["tenant_id"],
                domain_pack_path=tenant_config["domain_pack"],
                tenant_policy_path=tenant_config["tenant_policy"],
                api_key=tenant_config.get("api_key", "test-api-key-123"),
            )
            
            # Seed guardrail recommendations
            seed_guardrail_recommendations(
                tenant_id=tenant_config["tenant_id"],
                domain=tenant_config["domain"],
            )
            
            # Small delay between tenants
            time.sleep(2)
        except Exception as e:
            logger.error(f"Error seeding data for tenant {tenant_config['tenant_id']}: {e}", exc_info=True)
    
    logger.info("\n" + "="*60)
    logger.info("UI data seeding completed!")
    logger.info("="*60)
    logger.info("\nNext steps:")
    logger.info("1. Backend server should already be running")
    logger.info("2. Start the UI dev server: cd ui && npm run dev")
    logger.info("3. Navigate to http://localhost:5173/login")
    logger.info("4. Select a tenant and API key to view the seeded data")
    logger.info("\nAvailable test tenants:")
    for tenant_config in tenants:
        logger.info(f"  - {tenant_config['tenant_id']} ({tenant_config['domain']})")


if __name__ == "__main__":
    main()

