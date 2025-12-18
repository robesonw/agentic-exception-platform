#!/usr/bin/env python3
r"""
Seed exception data via async API (Phase 9).

This script seeds exception data using the new async API endpoints that return 202 Accepted.
It works with the event-driven infrastructure and can seed multiple tenants with configurable counts.

Usage:
    # Seed both tenants with default counts
    python scripts/seed_async_data.py
    
    # Seed specific tenant with custom count
    python scripts/seed_async_data.py --tenant TENANT_FINANCE_001 --count 50
    
    # Seed all tenants with custom counts
    python scripts/seed_async_data.py --all-tenants --finance-count 100 --healthcare-count 50
    
    # Wait for async processing to complete
    python scripts/seed_async_data.py --wait-for-processing

Prerequisites:
    1. All services must be running (use: .\scripts\start-all.ps1)
    2. Backend API must be accessible at http://localhost:8000
    3. Workers must be running to process events
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class AsyncDataSeeder:
    """Seeder that populates data via async API (202 Accepted)."""

    def __init__(self, api_url: str = "http://localhost:8000", api_key: str | None = None):
        """
        Initialize seeder.
        
        Args:
            api_url: Base URL of the API server
            api_key: API key for authentication (if None, will try to auto-detect based on tenant)
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=60.0)
        
        # Default API keys for common tenants
        self._default_api_keys = {
            "TENANT_FINANCE_001": "test_api_key_tenant_finance",
            "TENANT_HEALTHCARE_001": "test_api_key_tenant_healthcare",
            "TENANT_HEALTH_001": "test_api_key_tenant_healthcare",
        }

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()

    async def check_api_health(self) -> bool:
        """Check if API server is running."""
        try:
            response = await self.client.get(f"{self.api_url}/health")
            if response.status_code == 200:
                logger.info("✅ API server is running")
                return True
            else:
                logger.error(f"❌ API health check returned {response.status_code}")
                return False
        except httpx.RequestError as e:
            logger.error(f"❌ Cannot connect to API server at {self.api_url}: {e}")
            return False

    def _get_api_key_for_tenant(self, tenant_id: str) -> str | None:
        """Get API key for a tenant."""
        if self.api_key:
            return self.api_key
        return self._default_api_keys.get(tenant_id)

    def _get_headers(self, tenant_id: str) -> dict[str, str]:
        """Get HTTP headers for API requests."""
        headers = {"Content-Type": "application/json"}
        api_key = self._get_api_key_for_tenant(tenant_id)
        if api_key:
            headers["X-API-KEY"] = api_key
        return headers

    async def ingest_exception_async(
        self,
        tenant_id: str,
        exception_payload: dict[str, Any],
    ) -> str | None:
        """
        Ingest exception via async API (expects 202 Accepted).
        
        Args:
            tenant_id: Tenant identifier
            exception_payload: Exception payload dictionary
            
        Returns:
            Exception ID if successful, None otherwise
        """
        try:
            response = await self.client.post(
                f"{self.api_url}/exceptions/{tenant_id}",
                json={"exception": exception_payload},
                headers=self._get_headers(tenant_id),
            )
            
            # Phase 9: API now returns 202 Accepted
            if response.status_code == 202:
                data = response.json()
                exception_id = data.get("exceptionId")
                if exception_id:
                    logger.debug(f"✅ Accepted exception: {exception_id}")
                    return exception_id
                else:
                    logger.warning(f"⚠️  No exception ID returned in response: {data}")
                    return None
            else:
                logger.error(
                    f"❌ Failed to ingest exception: {response.status_code} - {response.text}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"❌ Request error ingesting exception: {e}")
            return None

    async def wait_for_exception_processing(
        self,
        tenant_id: str,
        exception_id: str,
        max_wait_seconds: int = 30,
    ) -> bool:
        """
        Wait for exception to be processed (appears in GET endpoint).
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            max_wait_seconds: Maximum time to wait
            
        Returns:
            True if exception was found, False otherwise
        """
        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            try:
                response = await self.client.get(
                    f"{self.api_url}/exceptions/{tenant_id}/{exception_id}",
                    headers=self._get_headers(tenant_id),
                )
                if response.status_code == 200:
                    logger.debug(f"✅ Exception {exception_id} processed and found")
                    return True
            except httpx.RequestError:
                pass
            
            await asyncio.sleep(1)
        
        logger.warning(f"⚠️  Exception {exception_id} not found after {max_wait_seconds}s")
        return False

    def create_finance_exception_payload(
        self,
        index: int,
        tenant_id: str = "TENANT_FINANCE_001",
    ) -> dict[str, Any]:
        """Create finance exception payload."""
        exception_types = [
            "TradeSettlementFailure",
            "PriceDiscrepancy",
            "RegulatoryViolation",
            "MarginCallException",
            "OrderExecutionError",
            "AllocationMismatch",
            "CounterpartyRiskExceeded",
            "ComplianceViolation",
        ]
        source_systems = [
            "TradingPlatform",
            "SettlementSystem",
            "RiskManagement",
            "Compliance",
            "ClearingHouse",
        ]
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        
        exception_type = exception_types[index % len(exception_types)]
        source_system = source_systems[index % len(source_systems)]
        severity = severities[index % len(severities)]
        
        base_time = datetime.now(timezone.utc) - timedelta(hours=index * 2)
        
        return {
            "sourceSystem": source_system,
            "rawPayload": {
                "exceptionId": f"FIN-{index+1:05d}",
                "tenantId": tenant_id,
                "timestamp": base_time.isoformat(),
                "type": exception_type,
                "severity": severity,
                "description": f"Sample {exception_type} exception #{index+1}",
                "amount": 1000.0 + (index * 100),
                "entity": f"CPTY-{index:05d}",
                "accountId": f"ACC-{index:05d}",
                "orderId": f"ORD-{index:05d}",
                "tradeDate": base_time.date().isoformat(),
                "domain": "CapitalMarketsTrading",
            },
            "normalizedContext": {
                "domain": "CapitalMarketsTrading",
                "amount": 1000.0 + (index * 100),
                "entity": f"CPTY-{index:05d}",
            },
        }

    def create_healthcare_exception_payload(
        self,
        index: int,
        tenant_id: str = "TENANT_HEALTHCARE_001",
    ) -> dict[str, Any]:
        """Create healthcare exception payload."""
        exception_types = [
            "ClaimRejection",
            "PriorAuthRequired",
            "DuplicateClaim",
            "CoverageException",
            "BillingError",
            "ProviderCredentialingIssue",
            "MedicationSafetyAlert",
            "PatientDataQualityIssue",
        ]
        source_systems = [
            "ClaimsSystem",
            "EHR",
            "BillingPlatform",
            "Authorization",
            "PharmacySystem",
        ]
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        
        exception_type = exception_types[index % len(exception_types)]
        source_system = source_systems[index % len(source_systems)]
        severity = severities[index % len(severities)]
        
        base_time = datetime.now(timezone.utc) - timedelta(hours=index * 3)
        
        return {
            "sourceSystem": source_system,
            "rawPayload": {
                "exceptionId": f"HC-{index+1:05d}",
                "tenantId": tenant_id,
                "timestamp": base_time.isoformat(),
                "type": exception_type,
                "severity": severity,
                "description": f"Sample {exception_type} exception #{index+1}",
                "amount": 500.0 + (index * 50),
                "entity": f"PATIENT-{index:05d}",
                "patientId": f"PAT-{index:05d}",
                "claimId": f"CLM-{index:05d}",
                "providerId": f"PRV-{index:05d}",
                "domain": "HealthcareClaimsAndCareOps",
            },
            "normalizedContext": {
                "domain": "HealthcareClaimsAndCareOps",
                "amount": 500.0 + (index * 50),
                "entity": f"PATIENT-{index:05d}",
            },
        }

    async def seed_finance_tenant(
        self,
        tenant_id: str = "TENANT_FINANCE_001",
        count: int = 50,
        wait_for_processing: bool = False,
    ) -> list[str]:
        """Seed data for finance tenant."""
        logger.info(f"\n{'='*70}")
        logger.info(f"Seeding Finance Tenant: {tenant_id}")
        logger.info(f"Count: {count} exceptions")
        logger.info(f"{'='*70}")
        
        exception_ids = []
        for i in range(count):
            payload = self.create_finance_exception_payload(i, tenant_id)
            exception_id = await self.ingest_exception_async(tenant_id, payload)
            
            if exception_id:
                exception_ids.append(exception_id)
                
                # Wait for processing if requested
                if wait_for_processing:
                    await self.wait_for_exception_processing(tenant_id, exception_id)
            
            # Small delay to avoid overwhelming the API
            if (i + 1) % 10 == 0:
                logger.info(f"  Progress: {i+1}/{count} exceptions ingested")
                await asyncio.sleep(0.5)
            else:
                await asyncio.sleep(0.1)
        
        logger.info(f"✅ Seeded {len(exception_ids)}/{count} exceptions for {tenant_id}")
        return exception_ids

    async def seed_healthcare_tenant(
        self,
        tenant_id: str = "TENANT_HEALTHCARE_001",
        count: int = 30,
        wait_for_processing: bool = False,
    ) -> list[str]:
        """Seed data for healthcare tenant."""
        logger.info(f"\n{'='*70}")
        logger.info(f"Seeding Healthcare Tenant: {tenant_id}")
        logger.info(f"Count: {count} exceptions")
        logger.info(f"{'='*70}")
        
        exception_ids = []
        for i in range(count):
            payload = self.create_healthcare_exception_payload(i, tenant_id)
            exception_id = await self.ingest_exception_async(tenant_id, payload)
            
            if exception_id:
                exception_ids.append(exception_id)
                
                # Wait for processing if requested
                if wait_for_processing:
                    await self.wait_for_exception_processing(tenant_id, exception_id)
            
            # Small delay to avoid overwhelming the API
            if (i + 1) % 10 == 0:
                logger.info(f"  Progress: {i+1}/{count} exceptions ingested")
                await asyncio.sleep(0.5)
            else:
                await asyncio.sleep(0.1)
        
        logger.info(f"✅ Seeded {len(exception_ids)}/{count} exceptions for {tenant_id}")
        return exception_ids

    async def verify_data(
        self,
        tenant_id: str,
        expected_min_count: int = 1,
    ) -> dict[str, Any]:
        """
        Verify data exists by querying API.
        
        Args:
            tenant_id: Tenant identifier
            expected_min_count: Minimum expected count
            
        Returns:
            Dictionary with verification results
        """
        try:
            # Query exceptions endpoint
            response = await self.client.get(
                f"{self.api_url}/exceptions/{tenant_id}",
                params={"page": 1, "page_size": 1},
                headers=self._get_headers(tenant_id),
            )
            
            if response.status_code == 200:
                data = response.json()
                total = data.get("total", 0)
                return {
                    "success": total >= expected_min_count,
                    "total": total,
                    "expected_min": expected_min_count,
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "total": 0,
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "total": 0,
            }


async def main():
    """Main seeding function."""
    parser = argparse.ArgumentParser(
        description="Seed exception data via async API (Phase 9)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Seed both tenants with default counts
  python scripts/seed_async_data.py
  
  # Seed specific tenant with custom count
  python scripts/seed_async_data.py --tenant TENANT_FINANCE_001 --count 100
  
  # Seed all tenants with custom counts
  python scripts/seed_async_data.py --all-tenants --finance-count 100 --healthcare-count 50
  
  # Wait for async processing to complete
  python scripts/seed_async_data.py --wait-for-processing
        """,
    )
    
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API server URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--tenant",
        choices=["TENANT_FINANCE_001", "TENANT_HEALTHCARE_001"],
        help="Specific tenant ID to seed",
    )
    parser.add_argument(
        "--all-tenants",
        action="store_true",
        help="Seed all tenants",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of exceptions to create (default: 50, used when seeding single tenant)",
    )
    parser.add_argument(
        "--finance-count",
        type=int,
        default=50,
        help="Number of exceptions for finance tenant (default: 50)",
    )
    parser.add_argument(
        "--healthcare-count",
        type=int,
        default=30,
        help="Number of exceptions for healthcare tenant (default: 30)",
    )
    parser.add_argument(
        "--wait-for-processing",
        action="store_true",
        help="Wait for async processing to complete (slower but ensures data is processed)",
    )
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip API health check",
    )
    parser.add_argument(
        "--api-key",
        help="API key for authentication (if not provided, will try to auto-detect)",
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.all_tenants and not args.tenant:
        parser.error("Either --tenant or --all-tenants must be specified")
    
    print("=" * 70)
    print("Async Exception Data Seeding (Phase 9)")
    print("=" * 70)
    print(f"\nAPI URL: {args.api_url}")
    if args.tenant:
        print(f"Tenant: {args.tenant}")
        print(f"Count: {args.count}")
    else:
        print(f"Finance Tenant: TENANT_FINANCE_001 ({args.finance_count} exceptions)")
        print(f"Healthcare Tenant: TENANT_HEALTHCARE_001 ({args.healthcare_count} exceptions)")
    if args.wait_for_processing:
        print("Mode: Wait for async processing (slower)")
    else:
        print("Mode: Fire and forget (faster)")
    print()
    
    async with AsyncDataSeeder(api_url=args.api_url, api_key=args.api_key) as seeder:
        # Health check
        if not args.skip_health_check:
            logger.info("Performing health check...")
            api_ok = await seeder.check_api_health()
            if not api_ok:
                logger.error(
                    "\n❌ API server is not running or not accessible.\n"
                    "Please start all services with:\n"
                    "  .\\scripts\\start-all.ps1"
                )
                return 1
        
        # Seed data
        all_exception_ids = []
        
        if args.tenant == "TENANT_FINANCE_001":
            exception_ids = await seeder.seed_finance_tenant(
                tenant_id=args.tenant,
                count=args.count,
                wait_for_processing=args.wait_for_processing,
            )
            all_exception_ids.extend(exception_ids)
            
            # Verify
            logger.info("\nVerifying data...")
            verification = await seeder.verify_data(args.tenant, expected_min_count=1)
            if verification["success"]:
                logger.info(f"✅ Verified: {verification['total']} exceptions found")
            else:
                logger.warning(f"⚠️  Verification: {verification.get('error', 'Unknown error')}")
        
        elif args.tenant == "TENANT_HEALTHCARE_001":
            exception_ids = await seeder.seed_healthcare_tenant(
                tenant_id=args.tenant,
                count=args.count,
                wait_for_processing=args.wait_for_processing,
            )
            all_exception_ids.extend(exception_ids)
            
            # Verify
            logger.info("\nVerifying data...")
            verification = await seeder.verify_data(args.tenant, expected_min_count=1)
            if verification["success"]:
                logger.info(f"✅ Verified: {verification['total']} exceptions found")
            else:
                logger.warning(f"⚠️  Verification: {verification.get('error', 'Unknown error')}")
        
        elif args.all_tenants:
            # Seed finance
            finance_ids = await seeder.seed_finance_tenant(
                tenant_id="TENANT_FINANCE_001",
                count=args.finance_count,
                wait_for_processing=args.wait_for_processing,
            )
            all_exception_ids.extend(finance_ids)
            
            # Seed healthcare
            healthcare_ids = await seeder.seed_healthcare_tenant(
                tenant_id="TENANT_HEALTHCARE_001",
                count=args.healthcare_count,
                wait_for_processing=args.wait_for_processing,
            )
            all_exception_ids.extend(healthcare_ids)
            
            # Verify both
            logger.info("\nVerifying data...")
            finance_verification = await seeder.verify_data("TENANT_FINANCE_001", expected_min_count=1)
            healthcare_verification = await seeder.verify_data("TENANT_HEALTHCARE_001", expected_min_count=1)
            
            if finance_verification["success"]:
                logger.info(f"✅ Finance: {finance_verification['total']} exceptions found")
            else:
                logger.warning(f"⚠️  Finance verification: {finance_verification.get('error', 'Unknown error')}")
            
            if healthcare_verification["success"]:
                logger.info(f"✅ Healthcare: {healthcare_verification['total']} exceptions found")
            else:
                logger.warning(f"⚠️  Healthcare verification: {healthcare_verification.get('error', 'Unknown error')}")
        
        # Summary
        print("\n" + "=" * 70)
        print("Seeding Summary")
        print("=" * 70)
        print(f"Total exceptions ingested: {len(all_exception_ids)}")
        print(f"Successful: {len([x for x in all_exception_ids if x])}")
        print(f"Failed: {len([x for x in all_exception_ids if not x])}")
        print()
        print("Next steps:")
        print("1. View data in UI:")
        print("   - Navigate to http://localhost:3000")
        print("   - Select tenant: TENANT_FINANCE_001 or TENANT_HEALTHCARE_001")
        print("2. Check API directly:")
        print("   - Finance: http://localhost:8000/exceptions/TENANT_FINANCE_001")
        print("   - Healthcare: http://localhost:8000/exceptions/TENANT_HEALTHCARE_001")
        print("3. View API docs:")
        print("   - http://localhost:8000/docs")
        print("=" * 70)
        
        return 0 if all_exception_ids else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

