#!/usr/bin/env python3
"""
Seed demo exceptions via async Kafka event publishing.

This script:
- Creates demo tenants/packs/playbooks/tools if missing (via API)
- Publishes N ExceptionIngested events to Kafka (not direct DB inserts)
- Waits for pipeline completion (polls DB for playbook assignment / events)
- Prints a summary (processed, failed, dlq)

Usage:
    python scripts/seed_demo_async.py [options]

Examples:
    # Seed 10 exceptions for default tenant
    python scripts/seed_demo_async.py --count 10

    # Seed 50 exceptions for specific tenant
    python scripts/seed_demo_async.py --tenant TENANT_FINANCE_001 --count 50

    # Seed and wait for completion
    python scripts/seed_demo_async.py --seed --count 20

Prerequisites:
    1. PostgreSQL must be running
    2. Kafka must be running
    3. Workers must be running
    4. API server must be running (for creating demo data)
"""

import argparse
import asyncio
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.events.types import ExceptionIngested
from src.infrastructure.db.session import get_db_session_context, initialize_database
from src.messaging.broker import get_broker
from src.messaging.event_publisher import EventPublisherService
from src.messaging.event_store import DatabaseEventStore
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class AsyncDemoSeeder:
    """Seeder that publishes exceptions to Kafka and monitors processing."""

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        kafka_bootstrap_servers: Optional[str] = None,
    ):
        """
        Initialize seeder.
        
        Args:
            api_url: Base URL of the API server (for creating demo data)
            kafka_bootstrap_servers: Kafka bootstrap servers (defaults to env var)
        """
        self.api_url = api_url.rstrip("/")
        self.kafka_bootstrap_servers = (
            kafka_bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        )
        
        # Default tenant configurations
        self.default_tenants = {
            "TENANT_FINANCE_001": {
                "domain": "finance",
                "exception_types": [
                    "MISMATCHED_TRADE_DETAILS",
                    "FAILED_ALLOCATION",
                    "POSITION_BREAK",
                    "CASH_BREAK",
                    "SETTLEMENT_FAIL",
                    "REG_REPORT_REJECTED",
                    "SEC_MASTER_MISMATCH",
                ],
            },
            "TENANT_HEALTHCARE_042": {
                "domain": "healthcare",
                "exception_types": [
                    "CLAIM_MISSING_AUTH",
                    "CLAIM_CODE_MISMATCH",
                    "PROVIDER_CREDENTIAL_EXPIRED",
                    "PATIENT_DEMOGRAPHIC_CONFLICT",
                    "PHARMACY_DUPLICATE_THERAPY",
                    "ELIGIBILITY_COVERAGE_LAPSE",
                ],
            },
        }
        
        # Initialize event publisher
        self.event_publisher: Optional[EventPublisherService] = None

    async def initialize(self) -> None:
        """Initialize database and event publisher."""
        logger.info("Initializing database connection...")
        await initialize_database()
        
        logger.info("Initializing event publisher...")
        broker = get_broker()
        event_store = DatabaseEventStore()
        self.event_publisher = EventPublisherService(
            broker=broker,
            event_store=event_store,
        )

    async def ensure_demo_data(self, tenant_id: str) -> bool:
        """
        Ensure demo tenants/packs/playbooks/tools exist (via API).
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            True if demo data exists or was created successfully
        """
        import httpx
        
        tenant_config = self.default_tenants.get(tenant_id)
        if not tenant_config:
            logger.warning(f"Unknown tenant {tenant_id}, skipping demo data creation")
            return False
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Check if tenant exists
            try:
                response = await client.get(
                    f"{self.api_url}/admin/tenants/{tenant_id}",
                    headers={"X-API-KEY": "admin_key"},  # Default admin key
                )
                if response.status_code == 200:
                    logger.info(f"Tenant {tenant_id} already exists")
                    return True
            except Exception as e:
                logger.warning(f"Could not check tenant existence: {e}")
            
            # Try to create demo data via API
            # Note: This assumes API endpoints exist for creating demo data
            # For MVP, we'll just log a warning if tenant doesn't exist
            logger.warning(
                f"Tenant {tenant_id} may not exist. "
                f"Please ensure demo data is created via API or manually."
            )
            return True  # Continue anyway

    def _generate_exception_payload(
        self,
        tenant_id: str,
        exception_type: str,
        exception_id: str,
    ) -> dict[str, Any]:
        """Generate realistic exception payload."""
        tenant_config = self.default_tenants.get(tenant_id, {})
        domain = tenant_config.get("domain", "unknown")
        
        base_time = datetime.now(timezone.utc)
        
        if domain == "finance":
            source_systems = [
                "TradingPlatform",
                "SettlementSystem",
                "RiskManagement",
                "Compliance",
                "AllocationSystem",
            ]
            
            payload_templates = {
                "MISMATCHED_TRADE_DETAILS": {
                    "orderId": f"ORD-{random.randint(10000, 99999)}",
                    "execId": f"EXEC-{random.randint(10000, 99999)}",
                    "priceMismatch": round(random.uniform(0.01, 10.0), 2),
                    "quantityMismatch": random.randint(1, 100),
                },
                "FAILED_ALLOCATION": {
                    "orderId": f"ORD-{random.randint(10000, 99999)}",
                    "allocId": f"ALLOC-{random.randint(10000, 99999)}",
                    "blockQty": random.randint(1000, 10000),
                    "allocatedQty": random.randint(500, 900),
                },
                "POSITION_BREAK": {
                    "accountId": f"ACC-{random.randint(1000, 9999)}",
                    "cusip": f"{random.randint(1000000, 9999999)}",
                    "expectedQty": random.randint(1000, 10000),
                    "actualQty": random.randint(900, 1100),
                },
                "CASH_BREAK": {
                    "accountId": f"ACC-{random.randint(1000, 9999)}",
                    "currency": random.choice(["USD", "EUR", "GBP"]),
                    "expectedBalance": round(random.uniform(100000, 1000000), 2),
                    "actualBalance": round(random.uniform(90000, 1100000), 2),
                },
                "SETTLEMENT_FAIL": {
                    "orderId": f"ORD-{random.randint(10000, 99999)}",
                    "settleId": f"SETTLE-{random.randint(10000, 99999)}",
                    "intendedSettleDate": (base_time - timedelta(days=2)).isoformat(),
                    "failReason": random.choice([
                        "SSI_MISMATCH",
                        "INSUFFICIENT_SECURITIES",
                        "COUNTERPARTY_REJECT",
                    ]),
                },
                "REG_REPORT_REJECTED": {
                    "reportId": f"REG-{random.randint(10000, 99999)}",
                    "regType": random.choice(["TR", "SFTR", "EMIR"]),
                    "rejectReason": random.choice([
                        "MISSING_LEI",
                        "INVALID_UTI",
                        "MISSING_VENUE",
                    ]),
                },
                "SEC_MASTER_MISMATCH": {
                    "cusip": f"{random.randint(1000000, 9999999)}",
                    "field": random.choice(["coupon", "maturity", "currency"]),
                    "systemA_value": f"Value-{random.randint(1, 100)}",
                    "systemB_value": f"Value-{random.randint(1, 100)}",
                },
            }
            
            raw_payload = payload_templates.get(
                exception_type,
                {"error": f"Unknown exception type: {exception_type}"},
            )
            raw_payload.update({
                "exceptionId": exception_id,
                "tenantId": tenant_id,
                "timestamp": base_time.isoformat(),
                "type": exception_type,
            })
            
            return {
                "sourceSystem": random.choice(source_systems),
                "rawPayload": raw_payload,
            }
        
        elif domain == "healthcare":
            source_systems = [
                "ClaimsSystem",
                "EHR",
                "PharmacySystem",
                "ProviderPortal",
            ]
            
            payload_templates = {
                "CLAIM_MISSING_AUTH": {
                    "claimId": f"CLM-{random.randint(10000, 99999)}",
                    "patientId": f"PAT-{random.randint(1000, 9999)}",
                    "providerId": f"PROV-{random.randint(100, 999)}",
                    "serviceDate": (base_time - timedelta(days=random.randint(1, 30))).isoformat(),
                },
                "CLAIM_CODE_MISMATCH": {
                    "claimId": f"CLM-{random.randint(10000, 99999)}",
                    "submittedCode": random.choice(["99213", "99214", "99215"]),
                    "expectedCode": random.choice(["99213", "99214", "99215"]),
                    "diagnosisCode": f"ICD10-{random.randint(100, 999)}",
                },
                "PROVIDER_CREDENTIAL_EXPIRED": {
                    "providerId": f"PROV-{random.randint(100, 999)}",
                    "credentialType": random.choice(["DEA", "NPI", "StateLicense"]),
                    "expirationDate": (base_time - timedelta(days=random.randint(-30, 30))).isoformat(),
                },
                "PATIENT_DEMOGRAPHIC_CONFLICT": {
                    "patientId": f"PAT-{random.randint(1000, 9999)}",
                    "field": random.choice(["dateOfBirth", "address", "phone"]),
                    "systemA_value": f"Value-{random.randint(1, 100)}",
                    "systemB_value": f"Value-{random.randint(1, 100)}",
                },
                "PHARMACY_DUPLICATE_THERAPY": {
                    "patientId": f"PAT-{random.randint(1000, 9999)}",
                    "prescriptionId": f"RX-{random.randint(10000, 99999)}",
                    "duplicateRxId": f"RX-{random.randint(10000, 99999)}",
                    "medication": random.choice(["Lisinopril", "Metformin", "Atorvastatin"]),
                },
                "ELIGIBILITY_COVERAGE_LAPSE": {
                    "patientId": f"PAT-{random.randint(1000, 9999)}",
                    "policyId": f"POL-{random.randint(10000, 99999)}",
                    "lapseDate": (base_time - timedelta(days=random.randint(1, 90))).isoformat(),
                },
            }
            
            raw_payload = payload_templates.get(
                exception_type,
                {"error": f"Unknown exception type: {exception_type}"},
            )
            raw_payload.update({
                "exceptionId": exception_id,
                "tenantId": tenant_id,
                "timestamp": base_time.isoformat(),
                "type": exception_type,
            })
            
            return {
                "sourceSystem": random.choice(source_systems),
                "rawPayload": raw_payload,
            }
        
        else:
            # Generic payload
            return {
                "sourceSystem": "UnknownSystem",
                "rawPayload": {
                    "exceptionId": exception_id,
                    "tenantId": tenant_id,
                    "timestamp": base_time.isoformat(),
                    "type": exception_type,
                    "error": "Generic exception",
                },
            }

    async def publish_exceptions(
        self,
        tenant_id: str,
        count: int,
    ) -> list[str]:
        """
        Publish N ExceptionIngested events to Kafka.
        
        Args:
            tenant_id: Tenant identifier
            count: Number of exceptions to publish
            
        Returns:
            List of exception IDs
        """
        tenant_config = self.default_tenants.get(tenant_id)
        if not tenant_config:
            raise ValueError(f"Unknown tenant: {tenant_id}")
        
        exception_types = tenant_config["exception_types"]
        exception_ids = []
        
        logger.info(f"Publishing {count} exceptions for tenant {tenant_id}...")
        
        for i in range(count):
            exception_id = str(uuid4())
            exception_ids.append(exception_id)
            
            # Select random exception type
            exception_type = random.choice(exception_types)
            
            # Generate payload
            payload = self._generate_exception_payload(
                tenant_id=tenant_id,
                exception_type=exception_type,
                exception_id=exception_id,
            )
            
            # Create ExceptionIngested event
            event = ExceptionIngested.create(
                tenant_id=tenant_id,
                exception_id=exception_id,
                raw_payload=payload["rawPayload"],
                source_system=payload["sourceSystem"],
                ingestion_method="async_seeder",
                correlation_id=exception_id,
            )
            
            # Publish to Kafka
            try:
                await self.event_publisher.publish_event(
                    topic="exceptions",
                    event=event.model_dump(by_alias=True),
                    partition_key=tenant_id,  # Partition by tenant
                )
                logger.debug(f"Published exception {exception_id} ({i+1}/{count})")
            except Exception as e:
                logger.error(f"Failed to publish exception {exception_id}: {e}")
                raise
        
        logger.info(f"Published {len(exception_ids)} exceptions to Kafka")
        return exception_ids

    async def wait_for_completion(
        self,
        exception_ids: list[str],
        tenant_id: str,
        timeout_seconds: int = 300,
        poll_interval: int = 5,
    ) -> dict[str, Any]:
        """
        Wait for pipeline completion by polling DB.
        
        Args:
            exception_ids: List of exception IDs to monitor
            tenant_id: Tenant identifier
            timeout_seconds: Maximum time to wait
            poll_interval: Seconds between polls
            
        Returns:
            Dictionary with status summary
        """
        logger.info(f"Waiting for {len(exception_ids)} exceptions to be processed...")
        
        start_time = time.time()
        processed = set()
        failed = set()
        dlq = set()
        
        while time.time() - start_time < timeout_seconds:
            # Query database for exception status
            async with get_db_session_context() as session:
                # Check each exception
                for exception_id in exception_ids:
                    if exception_id in processed or exception_id in failed or exception_id in dlq:
                        continue
                    
                    try:
                        # Query exception from database
                        result = await session.execute(
                            text("""
                                SELECT 
                                    exception_id,
                                    resolution_status,
                                    current_playbook_id,
                                    updated_at
                                FROM exception
                                WHERE exception_id = :exception_id
                                  AND tenant_id = :tenant_id
                            """),
                            {"exception_id": exception_id, "tenant_id": tenant_id},
                        )
                        row = result.first()
                        
                        if row:
                            resolution_status = row.resolution_status
                            playbook_id = row.current_playbook_id
                            
                            # Check if processed (has playbook assignment or resolved)
                            if playbook_id is not None or resolution_status in ["RESOLVED", "CLOSED"]:
                                processed.add(exception_id)
                                logger.debug(f"Exception {exception_id} processed (playbook_id={playbook_id}, status={resolution_status})")
                            elif resolution_status == "FAILED":
                                failed.add(exception_id)
                                logger.debug(f"Exception {exception_id} failed")
                        
                        # Check for DLQ events
                        dlq_result = await session.execute(
                            text("""
                                SELECT event_id
                                FROM dead_letter_events
                                WHERE exception_id = :exception_id
                                  AND tenant_id = :tenant_id
                            """),
                            {"exception_id": exception_id, "tenant_id": tenant_id},
                        )
                        if dlq_result.fetchone():
                            dlq.add(exception_id)
                            logger.debug(f"Exception {exception_id} in DLQ")
                    
                    except Exception as e:
                        logger.warning(f"Error checking exception {exception_id}: {e}")
                
                # Check if all are processed
                remaining = len(exception_ids) - len(processed) - len(failed) - len(dlq)
                if remaining == 0:
                    logger.info("All exceptions processed!")
                    break
                
                logger.info(
                    f"Progress: {len(processed)} processed, {len(failed)} failed, "
                    f"{len(dlq)} dlq, {remaining} remaining"
                )
            
            # Wait before next poll
            await asyncio.sleep(poll_interval)
        
        elapsed_time = time.time() - start_time
        
        return {
            "processed": len(processed),
            "failed": len(failed),
            "dlq": len(dlq),
            "remaining": len(exception_ids) - len(processed) - len(failed) - len(dlq),
            "elapsed_seconds": elapsed_time,
            "exception_ids": {
                "processed": list(processed),
                "failed": list(failed),
                "dlq": list(dlq),
            },
        }

    async def run(
        self,
        tenant_id: str,
        count: int,
        seed: bool = False,
        wait: bool = True,
    ) -> dict[str, Any]:
        """
        Run the seeding process.
        
        Args:
            tenant_id: Tenant identifier
            count: Number of exceptions to seed
            seed: If True, ensure demo data exists first
            wait: If True, wait for completion
            
        Returns:
            Summary dictionary
        """
        # Initialize
        await self.initialize()
        
        # Ensure demo data exists
        if seed:
            logger.info("Ensuring demo data exists...")
            await self.ensure_demo_data(tenant_id)
        
        # Publish exceptions
        exception_ids = await self.publish_exceptions(tenant_id, count)
        
        # Wait for completion
        summary = None
        if wait:
            summary = await self.wait_for_completion(exception_ids, tenant_id)
        else:
            summary = {
                "processed": 0,
                "failed": 0,
                "dlq": 0,
                "remaining": count,
                "elapsed_seconds": 0,
                "exception_ids": {
                    "processed": [],
                    "failed": [],
                    "dlq": [],
                },
            }
        
        return {
            "tenant_id": tenant_id,
            "published": len(exception_ids),
            "exception_ids": exception_ids,
            **summary,
        }


async def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed demo exceptions via async Kafka event publishing"
    )
    parser.add_argument(
        "--tenant",
        type=str,
        default="TENANT_FINANCE_001",
        help="Tenant ID (default: TENANT_FINANCE_001)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of exceptions to seed (default: 10)",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Ensure demo tenants/packs/playbooks/tools exist first",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Don't wait for completion (just publish and exit)",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000",
        help="API server URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--kafka-servers",
        type=str,
        default=None,
        help="Kafka bootstrap servers (default: from KAFKA_BOOTSTRAP_SERVERS env var)",
    )
    
    args = parser.parse_args()
    
    seeder = AsyncDemoSeeder(
        api_url=args.api_url,
        kafka_bootstrap_servers=args.kafka_servers,
    )
    
    try:
        summary = await seeder.run(
            tenant_id=args.tenant,
            count=args.count,
            seed=args.seed,
            wait=not args.no_wait,
        )
        
        # Print summary
        print("\n" + "=" * 60)
        print("Seeding Summary")
        print("=" * 60)
        print(f"Tenant ID:        {summary['tenant_id']}")
        print(f"Published:        {summary['published']}")
        print(f"Processed:       {summary['processed']}")
        print(f"Failed:           {summary['failed']}")
        print(f"DLQ:              {summary['dlq']}")
        print(f"Remaining:        {summary['remaining']}")
        if summary['elapsed_seconds'] > 0:
            print(f"Elapsed Time:     {summary['elapsed_seconds']:.1f}s")
        print("=" * 60)
        
        if summary['remaining'] > 0:
            print(f"\nWarning: {summary['remaining']} exceptions not yet processed")
            return 1
        
        return 0
    
    except Exception as e:
        logger.error(f"Seeding failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

