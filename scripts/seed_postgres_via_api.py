#!/usr/bin/env python3
r"""
Seed PostgreSQL database via API calls.

This script seeds the database by calling the API endpoints, ensuring data
appears in both PostgreSQL and the UI.

Usage:
    python scripts/seed_postgres_via_api.py [--api-url http://localhost:8000] [--tenant-id TENANT_001] [--api-key KEY]

Prerequisites:
    1. PostgreSQL must be running (use: .\scripts\docker_db.ps1 start)
    2. Database migrations must be run (use: alembic upgrade head)
    3. API server must be running (use: uvicorn src.api.main:app --reload)
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class DatabaseSeeder:
    """Seeder that populates PostgreSQL via API calls."""

    def __init__(self, api_url: str = "http://localhost:8000", api_key: str | None = None):
        """
        Initialize seeder.
        
        Args:
            api_url: Base URL of the API server
            api_key: API key for authentication (if None, will try to auto-detect based on tenant)
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Default API keys for common tenants
        self._default_api_keys = {
            "TENANT_FINANCE_001": "test_api_key_tenant_finance",
            "TENANT_HEALTHCARE_001": "test_api_key_tenant_healthcare",
            "TENANT_001": "test_api_key_tenant_001",
            "TENANT_002": "test_api_key_tenant_002",
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
                logger.info("[OK] API server is running")
                return True
            else:
                logger.error(f"[FAILED] API health check returned {response.status_code}")
                return False
        except httpx.RequestError as e:
            logger.error(f"[FAILED] Cannot connect to API server at {self.api_url}: {e}")
            return False

    async def check_db_health(self) -> bool:
        """Check if database is accessible via API."""
        try:
            response = await self.client.get(f"{self.api_url}/health/db")
            if response.status_code == 200:
                logger.info("[OK] Database is accessible via API")
                return True
            else:
                logger.warning(f"[WARNING] Database health check returned {response.status_code}")
                return False
        except httpx.RequestError as e:
            logger.warning(f"[WARNING] Cannot check database health: {e}")
            return False

    def create_exception_payload(
        self,
        exception_id: str,
        tenant_id: str,
        exception_type: str,
        severity: str,
        source_system: str,
        domain: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Create exception payload for API.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            exception_type: Exception type
            severity: Severity level (LOW, MEDIUM, HIGH, CRITICAL)
            source_system: Source system name
            domain: Domain name (e.g., Finance, Healthcare)
            **kwargs: Additional fields (amount, entity, description, etc.)
            
        Returns:
            Exception payload dictionary
        """
        base_time = datetime.now(timezone.utc) - timedelta(hours=kwargs.get("hours_ago", 0))
        
        # Build normalized context with domain
        normalized_context = kwargs.get("normalized_context", {})
        if domain:
            normalized_context["domain"] = domain
        
        payload = {
            "sourceSystem": source_system,
            "rawPayload": {
                "exceptionId": exception_id,
                "tenantId": tenant_id,
                "timestamp": base_time.isoformat(),
                "type": exception_type,
                "severity": severity,
                "description": kwargs.get("description", f"Sample {exception_type} exception"),
                "domain": domain,  # Add domain to raw payload
                **kwargs.get("metadata", {}),
            },
            # Add normalized context with domain
            "normalizedContext": normalized_context,
        }
        
        # Add optional fields
        if "amount" in kwargs:
            payload["rawPayload"]["amount"] = kwargs["amount"]
            if "normalizedContext" not in payload:
                payload["normalizedContext"] = {}
            payload["normalizedContext"]["amount"] = kwargs["amount"]
        if "entity" in kwargs:
            payload["rawPayload"]["entity"] = kwargs["entity"]
            if "normalizedContext" not in payload:
                payload["normalizedContext"] = {}
            payload["normalizedContext"]["entity"] = kwargs["entity"]
        if "accountId" in kwargs:
            payload["rawPayload"]["accountId"] = kwargs["accountId"]
        
        return payload

    def _get_api_key_for_tenant(self, tenant_id: str) -> str | None:
        """
        Get API key for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            API key if available, None otherwise
        """
        if self.api_key:
            return self.api_key
        return self._default_api_keys.get(tenant_id)

    def _get_headers(self, tenant_id: str) -> dict[str, str]:
        """
        Get HTTP headers for API requests.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary of HTTP headers
        """
        headers = {"Content-Type": "application/json"}
        api_key = self._get_api_key_for_tenant(tenant_id)
        if api_key:
            headers["X-API-KEY"] = api_key
        return headers

    async def ingest_exception(
        self,
        tenant_id: str,
        exception_payload: dict[str, Any],
    ) -> str | None:
        """
        Ingest exception via API.
        
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
            
            if response.status_code == 200:
                data = response.json()
                exception_ids = data.get("exceptionIds", [])
                if exception_ids:
                    logger.info(f"[OK] Ingested exception: {exception_ids[0]}")
                    return exception_ids[0]
                else:
                    logger.warning(f"[WARNING] No exception ID returned for {exception_payload.get('rawPayload', {}).get('exceptionId')}")
                    return None
            else:
                logger.error(
                    f"[FAILED] Failed to ingest exception: {response.status_code} - {response.text}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"[FAILED] Request error ingesting exception: {e}")
            return None

    async def ingest_exceptions_batch(
        self,
        tenant_id: str,
        exception_payloads: list[dict[str, Any]],
    ) -> list[str]:
        """
        Ingest multiple exceptions via API batch endpoint.
        
        Args:
            tenant_id: Tenant identifier
            exception_payloads: List of exception payload dictionaries
            
        Returns:
            List of exception IDs that were successfully ingested
        """
        try:
            response = await self.client.post(
                f"{self.api_url}/exceptions/{tenant_id}",
                json={"exceptions": exception_payloads},
                headers=self._get_headers(tenant_id),
            )
            
            if response.status_code == 200:
                data = response.json()
                exception_ids = data.get("exceptionIds", [])
                logger.info(f"[OK] Ingested {len(exception_ids)} exceptions in batch")
                return exception_ids
            else:
                logger.error(
                    f"[FAILED] Failed to ingest exceptions batch: {response.status_code} - {response.text}"
                )
                return []
        except httpx.RequestError as e:
            logger.error(f"[FAILED] Request error ingesting exceptions batch: {e}")
            return []

    async def seed_finance_tenant(self, tenant_id: str = "TENANT_FINANCE_001", count: int = 20):
        """Seed data for finance tenant."""
        logger.info(f"\n{'='*70}")
        logger.info(f"Seeding Finance Tenant: {tenant_id}")
        logger.info(f"{'='*70}")
        
        exception_types = [
            "TradeSettlementFailure",
            "PriceDiscrepancy",
            "RegulatoryViolation",
            "MarginCallException",
            "OrderExecutionError",
        ]
        source_systems = ["TradingPlatform", "SettlementSystem", "RiskManagement", "Compliance"]
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        domain = "Finance"
        
        exceptions = []
        for i in range(count):
            exception_id = f"FIN-{i+1:04d}"
            exception_type = exception_types[i % len(exception_types)]
            source_system = source_systems[i % len(source_systems)]
            severity = severities[i % len(severities)]
            
            payload = self.create_exception_payload(
                exception_id=exception_id,
                tenant_id=tenant_id,
                exception_type=exception_type,
                severity=severity,
                source_system=source_system,
                domain=domain,
                amount=1000.0 + (i * 100),
                entity=f"CPTY-{i:05d}",
                accountId=f"ACC-{i:05d}",
                description=f"Sample {exception_type} exception #{i+1}",
                hours_ago=i * 2,
                normalized_context={"domain": domain},
                metadata={
                    "source": "seed_script",
                    "batch": "finance_demo",
                    "index": i,
                },
            )
            exceptions.append(payload)
        
        # Ingest in batches of 5
        batch_size = 5
        all_exception_ids = []
        for i in range(0, len(exceptions), batch_size):
            batch = exceptions[i : i + batch_size]
            exception_ids = await self.ingest_exceptions_batch(tenant_id, batch)
            all_exception_ids.extend(exception_ids)
            await asyncio.sleep(0.5)  # Small delay between batches
        
        logger.info(f"[SUCCESS] Seeded {len(all_exception_ids)} exceptions for {tenant_id}")
        return all_exception_ids

    async def seed_healthcare_tenant(self, tenant_id: str = "TENANT_HEALTHCARE_001", count: int = 15):
        """Seed data for healthcare tenant."""
        logger.info(f"\n{'='*70}")
        logger.info(f"Seeding Healthcare Tenant: {tenant_id}")
        logger.info(f"{'='*70}")
        
        exception_types = [
            "ClaimRejection",
            "PriorAuthRequired",
            "DuplicateClaim",
            "CoverageException",
            "BillingError",
        ]
        source_systems = ["ClaimsSystem", "EHR", "BillingPlatform", "Authorization"]
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        domain = "Healthcare"
        
        exceptions = []
        for i in range(count):
            exception_id = f"HC-{i+1:04d}"
            exception_type = exception_types[i % len(exception_types)]
            source_system = source_systems[i % len(source_systems)]
            severity = severities[i % len(severities)]
            
            payload = self.create_exception_payload(
                exception_id=exception_id,
                tenant_id=tenant_id,
                exception_type=exception_type,
                severity=severity,
                source_system=source_system,
                domain=domain,
                amount=500.0 + (i * 50),
                entity=f"PATIENT-{i:05d}",
                description=f"Sample {exception_type} exception #{i+1}",
                hours_ago=i * 3,
                normalized_context={"domain": domain},
                metadata={
                    "source": "seed_script",
                    "batch": "healthcare_demo",
                    "index": i,
                },
            )
            exceptions.append(payload)
        
        # Ingest in batches
        batch_size = 5
        all_exception_ids = []
        for i in range(0, len(exceptions), batch_size):
            batch = exceptions[i : i + batch_size]
            exception_ids = await self.ingest_exceptions_batch(tenant_id, batch)
            all_exception_ids.extend(exception_ids)
            await asyncio.sleep(0.5)
        
        logger.info(f"[SUCCESS] Seeded {len(all_exception_ids)} exceptions for {tenant_id}")
        return all_exception_ids

    async def seed_custom_tenant(
        self,
        tenant_id: str,
        count: int = 10,
        domain: str = "Generic",
    ):
        """Seed data for a custom tenant."""
        logger.info(f"\n{'='*70}")
        logger.info(f"Seeding Custom Tenant: {tenant_id} (Domain: {domain})")
        logger.info(f"{'='*70}")
        
        exception_types = ["GenericException", "ProcessingError", "ValidationFailure"]
        source_systems = ["SystemA", "SystemB", "SystemC"]
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        
        # Auto-detect domain from tenant_id if not provided
        if domain == "Generic":
            if "FINANCE" in tenant_id.upper():
                domain = "Finance"
            elif "HEALTHCARE" in tenant_id.upper() or "HEALTH" in tenant_id.upper():
                domain = "Healthcare"
        
        exceptions = []
        for i in range(count):
            exception_id = f"EXC-{i+1:04d}"
            exception_type = exception_types[i % len(exception_types)]
            source_system = source_systems[i % len(source_systems)]
            severity = severities[i % len(severities)]
            
            payload = self.create_exception_payload(
                exception_id=exception_id,
                tenant_id=tenant_id,
                exception_type=exception_type,
                severity=severity,
                source_system=source_system,
                domain=domain,
                description=f"Sample {exception_type} exception #{i+1}",
                hours_ago=i * 4,
                normalized_context={"domain": domain},
                metadata={
                    "source": "seed_script",
                    "batch": "custom_demo",
                    "index": i,
                    "domain": domain,
                },
            )
            exceptions.append(payload)
        
        # Ingest in batches
        batch_size = 5
        all_exception_ids = []
        for i in range(0, len(exceptions), batch_size):
            batch = exceptions[i : i + batch_size]
            exception_ids = await self.ingest_exceptions_batch(tenant_id, batch)
            all_exception_ids.extend(exception_ids)
            await asyncio.sleep(0.5)
        
        logger.info(f"[SUCCESS] Seeded {len(all_exception_ids)} exceptions for {tenant_id}")
        return all_exception_ids

    async def verify_data_in_db(self, tenant_id: str) -> dict[str, int]:
        """
        Verify data exists in database by querying API.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with counts of exceptions and events
        """
        try:
            # Try to get exceptions (if API endpoint exists)
            # For now, just return placeholder
            return {
                "exceptions": 0,
                "events": 0,
            }
        except Exception as e:
            logger.warning(f"Could not verify data in database: {e}")
            return {"exceptions": 0, "events": 0}


async def main():
    """Main seeding function."""
    parser = argparse.ArgumentParser(description="Seed PostgreSQL database via API calls")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API server URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--tenant-id",
        help="Specific tenant ID to seed (if not provided, seeds all default tenants)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=20,
        help="Number of exceptions to create per tenant (default: 20)",
    )
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip API and database health checks",
    )
    parser.add_argument(
        "--api-key",
        help="API key for authentication (if not provided, will try to auto-detect based on tenant)",
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("PostgreSQL Database Seeding via API")
    print("=" * 70)
    print(f"\nAPI URL: {args.api_url}")
    print(f"Exceptions per tenant: {args.count}")
    if args.api_key:
        print(f"API Key: {args.api_key[:10]}..." if len(args.api_key) > 10 else f"API Key: {args.api_key}")
    print()
    
    async with DatabaseSeeder(api_url=args.api_url, api_key=args.api_key) as seeder:
        # Health checks
        if not args.skip_health_check:
            logger.info("Performing health checks...")
            api_ok = await seeder.check_api_health()
            if not api_ok:
                logger.error(
                    "\n[FAILED] API server is not running or not accessible.\n"
                    "Please start the API server with:\n"
                    "  uvicorn src.api.main:app --reload"
                )
                return 1
            
            db_ok = await seeder.check_db_health()
            if not db_ok:
                logger.warning(
                    "\n[WARNING] Database health check failed.\n"
                    "Make sure PostgreSQL is running and migrations are applied:\n"
                    "  .\\scripts\\docker_db.ps1 start\n"
                    "  alembic upgrade head"
                )
        
        # Seed data
        all_exception_ids = []
        
        if args.tenant_id:
            # Seed specific tenant
            logger.info(f"Seeding tenant: {args.tenant_id}")
            # Check if API key is available
            api_key = seeder._get_api_key_for_tenant(args.tenant_id)
            if not api_key:
                logger.warning(
                    f"[WARNING] No API key found for tenant {args.tenant_id}. "
                    f"Please provide one with --api-key or ensure tenant has a default API key."
                )
            exception_ids = await seeder.seed_custom_tenant(
                tenant_id=args.tenant_id,
                count=args.count,
            )
            all_exception_ids.extend(exception_ids)
        else:
            # Seed default tenants
            finance_ids = await seeder.seed_finance_tenant(
                tenant_id="TENANT_FINANCE_001",
                count=args.count,
            )
            all_exception_ids.extend(finance_ids)
            
            healthcare_ids = await seeder.seed_healthcare_tenant(
                tenant_id="TENANT_HEALTHCARE_001",
                count=args.count // 2,
            )
            all_exception_ids.extend(healthcare_ids)
        
        # Summary
        print("\n" + "=" * 70)
        print("Seeding Summary")
        print("=" * 70)
        print(f"Total exceptions ingested: {len(all_exception_ids)}")
        print(f"Successful: {len([x for x in all_exception_ids if x])}")
        print(f"Failed: {len([x for x in all_exception_ids if not x])}")
        print()
        print("Next steps:")
        print("1. Verify data in database:")
        print("   docker exec -it sentinai-postgres psql -U postgres -d sentinai -c \"SELECT COUNT(*) FROM exception;\"")
        print("2. View data in UI:")
        print("   - Start UI: cd ui && npm run dev")
        print("   - Navigate to http://localhost:5173")
        print("   - Login with tenant: TENANT_FINANCE_001")
        print("=" * 70)
        
        return 0 if all_exception_ids else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

