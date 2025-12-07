"""
Verify and fix data storage for UI.

This script checks if exceptions are stored correctly and re-runs the seed if needed.
"""

import json
import logging
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests module not found. Install it with: pip install requests")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"


def check_backend():
    """Check if backend is running."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        response.raise_for_status()
        logger.info("✓ Backend server is running")
        return True
    except requests.exceptions.RequestException:
        logger.error("✗ Backend server is not running")
        logger.error("Please start the backend server first:")
        logger.error("  python -m uvicorn src.api.main:app --reload")
        return False


def check_exceptions(tenant_id: str, api_key: str):
    """Check if exceptions exist for a tenant."""
    try:
        response = requests.get(
            f"{BASE_URL}/ui/exceptions",
            params={"tenant_id": tenant_id, "page": 1, "page_size": 5},
            headers={"X-API-KEY": api_key},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        count = data.get("total", 0)
        logger.info(f"✓ Found {count} exceptions for tenant {tenant_id}")
        return count > 0
    except requests.exceptions.RequestException as e:
        logger.error(f"✗ Error checking exceptions: {e}")
        return False


def create_single_exception(tenant_id: str, api_key: str, domain_pack_path: str, tenant_policy_path: str):
    """Create a single exception via API."""
    logger.info(f"Creating exception for tenant {tenant_id}...")
    
    # Create a simple exception
    exception = {
        "sourceSystem": "TradingPlatform",
        "rawPayload": {
            "exceptionId": f"EXC_{tenant_id}_TEST",
            "timestamp": "2024-01-15T10:00:00Z",
            "type": "TradeSettlementFailure",
            "amount": 1000.0,
            "accountId": "ACC_001",
            "description": "Test exception for UI",
        },
    }
    
    request_payload = {
        "domainPackPath": str(Path(domain_pack_path).absolute()),
        "tenantPolicyPath": str(Path(tenant_policy_path).absolute()),
        "exceptions": [exception],
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/run",
            json=request_payload,
            headers={
                "X-API-KEY": api_key,
                "Content-Type": "application/json",
            },
            timeout=300,
        )
        response.raise_for_status()
        result = response.json()
        logger.info(f"✓ Created exception: {result.get('runId')}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"✗ Error creating exception: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response: {e.response.text}")
        return False


def main():
    """Main verification and fix function."""
    logger.info("=" * 60)
    logger.info("Verifying UI Data")
    logger.info("=" * 60)
    
    # Check backend
    if not check_backend():
        return
    
    # Test tenant configuration
    tenant_id = "TENANT_FINANCE_001"
    api_key = "test_api_key_tenant_finance"
    domain_pack = "domainpacks/finance.sample.json"
    tenant_policy = "tenantpacks/tenant_finance.sample.json"
    
    # Check if exceptions exist
    has_exceptions = check_exceptions(tenant_id, api_key)
    
    if not has_exceptions:
        logger.info("\nNo exceptions found. Creating test exception...")
        if create_single_exception(tenant_id, api_key, domain_pack, tenant_policy):
            # Wait a moment for processing
            time.sleep(2)
            # Check again
            check_exceptions(tenant_id, api_key)
    
    logger.info("\n" + "=" * 60)
    logger.info("Verification Complete")
    logger.info("=" * 60)
    logger.info("\nTo view data in UI:")
    logger.info("1. Make sure UI dev server is running: cd ui && npm run dev")
    logger.info("2. Navigate to: http://localhost:5173/login")
    logger.info(f"3. Login with:")
    logger.info(f"   - API Key: {api_key}")
    logger.info(f"   - Tenant: {tenant_id}")
    logger.info(f"   - Domain: CapitalMarketsTrading")
    logger.info("4. Navigate to /exceptions to view the data")


if __name__ == "__main__":
    main()

