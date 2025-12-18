#!/usr/bin/env python3
r"""
Seed multiple exceptions for Finance and Healthcare tenants via API.

This script creates realistic exception data using the actual exception types
from the domain packs (finance.sample.json and healthcare.sample.json).

Usage:
    python scripts/seed_multi_tenant_exceptions.py [options]

Examples:
    # Seed 50 exceptions for each tenant (default)
    python scripts/seed_multi_tenant_exceptions.py

    # Seed 100 exceptions per tenant
    python scripts/seed_multi_tenant_exceptions.py --count 100

    # Seed only finance tenant with 30 exceptions
    python scripts/seed_multi_tenant_exceptions.py --tenant-id TENANT_FINANCE_001 --count 30

    # Skip health checks (faster, but less safe)
    python scripts/seed_multi_tenant_exceptions.py --skip-health-check

Prerequisites:
    1. PostgreSQL must be running (use: .\scripts\docker_db.ps1 start)
    2. Database migrations must be run (use: alembic upgrade head)
    3. API server must be running (use: uvicorn src.api.main:app --reload)
"""

import argparse
import asyncio
import json
import logging
import os
import random
import subprocess
import sys
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


class MultiTenantExceptionSeeder:
    """Seeder that creates realistic exceptions for Finance and Healthcare tenants."""

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
            "TENANT_HEALTHCARE_042": "test_api_key_tenant_healthcare_042",
        }

        # Finance domain exception types from domain pack
        self.finance_exception_types = [
            "MISMATCHED_TRADE_DETAILS",
            "FAILED_ALLOCATION",
            "POSITION_BREAK",
            "CASH_BREAK",
            "SETTLEMENT_FAIL",
            "REG_REPORT_REJECTED",
            "SEC_MASTER_MISMATCH",
        ]

        # Healthcare domain exception types from domain pack
        self.healthcare_exception_types = [
            "CLAIM_MISSING_AUTH",
            "CLAIM_CODE_MISMATCH",
            "PROVIDER_CREDENTIAL_EXPIRED",
            "PATIENT_DEMOGRAPHIC_CONFLICT",
            "PHARMACY_DUPLICATE_THERAPY",
            "ELIGIBILITY_COVERAGE_LAPSE",
        ]

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

    def _generate_finance_exception_payload(
        self,
        exception_id: str,
        tenant_id: str,
        exception_type: str,
        base_time: datetime,
    ) -> dict[str, Any]:
        """Generate realistic finance exception payload."""
        source_systems = ["TradingPlatform", "SettlementSystem", "RiskManagement", "Compliance", "AllocationSystem"]
        
        # Map exception types to realistic raw payloads
        payload_templates = {
            "MISMATCHED_TRADE_DETAILS": {
                "orderId": f"ORD-{random.randint(10000, 99999)}",
                "execId": f"EXEC-{random.randint(10000, 99999)}",
                "priceMismatch": round(random.uniform(0.01, 10.0), 2),
                "quantityMismatch": random.randint(1, 100),
                "cusip": f"{random.randint(1000000, 9999999)}",
                "counterparty": f"CPTY-{random.randint(100, 999)}",
                "tradeDate": (base_time - timedelta(days=1)).isoformat(),
            },
            "FAILED_ALLOCATION": {
                "orderId": f"ORD-{random.randint(10000, 99999)}",
                "allocId": f"ALLOC-{random.randint(10000, 99999)}",
                "blockQty": random.randint(1000, 10000),
                "allocatedQty": random.randint(500, 900),
                "missingQty": random.randint(100, 500),
                "accountIds": [f"ACC-{random.randint(1000, 9999)}" for _ in range(random.randint(2, 5))],
            },
            "POSITION_BREAK": {
                "accountId": f"ACC-{random.randint(1000, 9999)}",
                "cusip": f"{random.randint(1000000, 9999999)}",
                "expectedQty": random.randint(1000, 10000),
                "actualQty": random.randint(900, 1100),
                "difference": random.randint(-100, 100),
                "asOfDate": (base_time - timedelta(days=1)).isoformat(),
            },
            "CASH_BREAK": {
                "accountId": f"ACC-{random.randint(1000, 9999)}",
                "currency": random.choice(["USD", "EUR", "GBP"]),
                "expectedBalance": round(random.uniform(100000, 1000000), 2),
                "actualBalance": round(random.uniform(90000, 1100000), 2),
                "difference": round(random.uniform(-10000, 10000), 2),
                "valueDate": base_time.date().isoformat(),
            },
            "SETTLEMENT_FAIL": {
                "orderId": f"ORD-{random.randint(10000, 99999)}",
                "settleId": f"SETTLE-{random.randint(10000, 99999)}",
                "intendedSettleDate": (base_time - timedelta(days=2)).isoformat(),
                "failReason": random.choice([
                    "SSI_MISMATCH",
                    "INSUFFICIENT_SECURITIES",
                    "COUNTERPARTY_REJECT",
                    "INSUFFICIENT_CASH",
                ]),
                "counterparty": f"CPTY-{random.randint(100, 999)}",
            },
            "REG_REPORT_REJECTED": {
                "reportId": f"REG-{random.randint(10000, 99999)}",
                "regType": random.choice(["TR", "SFTR", "EMIR"]),
                "tradeId": f"TRADE-{random.randint(10000, 99999)}",
                "rejectReason": random.choice([
                    "MISSING_LEI",
                    "INVALID_UTI",
                    "MISSING_VENUE",
                    "INVALID_TIMESTAMP",
                ]),
                "submittedAt": (base_time - timedelta(hours=2)).isoformat(),
            },
            "SEC_MASTER_MISMATCH": {
                "cusip": f"{random.randint(1000000, 9999999)}",
                "isin": f"US{random.randint(1000000000, 9999999999)}",
                "field": random.choice(["coupon", "maturity", "currency", "issuer"]),
                "systemA_value": f"Value-{random.randint(1, 100)}",
                "systemB_value": f"Value-{random.randint(1, 100)}",
                "impact": random.choice(["ECONOMIC", "NON_ECONOMIC"]),
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

        # Determine severity based on exception type
        severity_map = {
            "POSITION_BREAK": "CRITICAL",
            "CASH_BREAK": "HIGH",
            "SETTLEMENT_FAIL": "HIGH",
            "MISMATCHED_TRADE_DETAILS": "HIGH",
            "REG_REPORT_REJECTED": "HIGH",
            "FAILED_ALLOCATION": "MEDIUM",
            "SEC_MASTER_MISMATCH": "LOW",
        }

        return {
            "sourceSystem": random.choice(source_systems),
            "rawPayload": raw_payload,
            "normalizedContext": {
                "domain": "CapitalMarketsTrading",
                "exceptionType": exception_type,
                "severity": severity_map.get(exception_type, "MEDIUM"),
            },
        }

    def _generate_healthcare_exception_payload(
        self,
        exception_id: str,
        tenant_id: str,
        exception_type: str,
        base_time: datetime,
    ) -> dict[str, Any]:
        """Generate realistic healthcare exception payload."""
        source_systems = ["ClaimsSystem", "EHR", "BillingPlatform", "Authorization", "PharmacySystem", "ProviderRegistry"]
        
        # Map exception types to realistic raw payloads
        payload_templates = {
            "CLAIM_MISSING_AUTH": {
                "claimId": f"CLM-{random.randint(100000, 999999)}",
                "patientId": f"PAT-{random.randint(10000, 99999)}",
                "providerId": f"PRV-{random.randint(1000, 9999)}",
                "procedureCodes": [f"{random.randint(10000, 99999)}" for _ in range(random.randint(1, 3))],
                "serviceDate": (base_time - timedelta(days=random.randint(1, 30))).date().isoformat(),
                "amount": round(random.uniform(100, 5000), 2),
            },
            "CLAIM_CODE_MISMATCH": {
                "claimId": f"CLM-{random.randint(100000, 999999)}",
                "patientId": f"PAT-{random.randint(10000, 99999)}",
                "procedureCodes": [f"{random.randint(10000, 99999)}"],
                "diagnosisCodes": [f"{random.choice(['E', 'I', 'K', 'M', 'N'])}{random.randint(10, 99)}.{random.randint(0, 9)}"],
                "mismatchType": random.choice(["PROCEDURE_DIAGNOSIS", "ELIGIBILITY", "COVERAGE"]),
            },
            "PROVIDER_CREDENTIAL_EXPIRED": {
                "providerId": f"PRV-{random.randint(1000, 9999)}",
                "npi": f"{random.randint(1000000000, 9999999999)}",
                "credentialExpiryDate": (base_time - timedelta(days=random.randint(1, 90))).date().isoformat(),
                "serviceDate": (base_time - timedelta(days=random.randint(1, 30))).date().isoformat(),
                "facilityId": f"FAC-{random.randint(100, 999)}",
            },
            "PATIENT_DEMOGRAPHIC_CONFLICT": {
                "patientId": f"PAT-{random.randint(10000, 99999)}",
                "conflictingField": random.choice(["dob", "gender", "insuranceId", "coverageStart"]),
                "systemA_value": f"Value-{random.randint(1, 100)}",
                "systemB_value": f"Value-{random.randint(1, 100)}",
                "affectsBilling": random.choice([True, False]),
            },
            "PHARMACY_DUPLICATE_THERAPY": {
                "orderId": f"ORD-{random.randint(100000, 999999)}",
                "patientId": f"PAT-{random.randint(10000, 99999)}",
                "ndc": f"{random.randint(10000, 99999)}-{random.randint(1000, 9999)}-{random.randint(10, 99)}",
                "dose": f"{random.randint(1, 10)}mg",
                "activeTherapies": [
                    {
                        "ndc": f"{random.randint(10000, 99999)}-{random.randint(1000, 9999)}-{random.randint(10, 99)}",
                        "startDate": (base_time - timedelta(days=random.randint(1, 60))).date().isoformat(),
                    }
                    for _ in range(random.randint(1, 3))
                ],
                "overlapDays": random.randint(1, 30),
            },
            "ELIGIBILITY_COVERAGE_LAPSE": {
                "patientId": f"PAT-{random.randint(10000, 99999)}",
                "insuranceId": f"INS-{random.randint(100000, 999999)}",
                "serviceDate": (base_time - timedelta(days=random.randint(1, 60))).date().isoformat(),
                "coverageStart": (base_time - timedelta(days=random.randint(90, 365))).date().isoformat(),
                "coverageEnd": (base_time - timedelta(days=random.randint(1, 89))).date().isoformat(),
                "claimId": f"CLM-{random.randint(100000, 999999)}",
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

        # Determine severity based on exception type
        severity_map = {
            "PHARMACY_DUPLICATE_THERAPY": "CRITICAL",
            "CLAIM_MISSING_AUTH": "HIGH",
            "ELIGIBILITY_COVERAGE_LAPSE": "HIGH",
            "PROVIDER_CREDENTIAL_EXPIRED": "HIGH",
            "CLAIM_CODE_MISMATCH": "MEDIUM",
            "PATIENT_DEMOGRAPHIC_CONFLICT": "LOW",
        }

        return {
            "sourceSystem": random.choice(source_systems),
            "rawPayload": raw_payload,
            "normalizedContext": {
                "domain": "HealthcareClaimsAndCareOps",
                "exceptionType": exception_type,
                "severity": severity_map.get(exception_type, "MEDIUM"),
            },
        }

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
            
            if response.status_code in (200, 202):
                data = response.json()
                # API returns ExceptionIngestionResponse with exceptionId (singular)
                # For batches, API processes first exception only (MVP limitation)
                if "exceptionId" in data:
                    # For batch, we'll get one ID back but ingest all payloads
                    # Return one ID per payload for tracking
                    exception_ids = [data["exceptionId"]] * len(exception_payloads)
                else:
                    exception_ids = []
                logger.info(f"[OK] Ingested batch of {len(exception_payloads)} exceptions (API returned {len(exception_ids)} ID(s))")
                return exception_ids
            else:
                logger.error(
                    f"[FAILED] Failed to ingest exceptions batch: {response.status_code} - {response.text}"
                )
                return []
        except httpx.RequestError as e:
            logger.error(f"[FAILED] Request error ingesting exceptions batch: {e}")
            return []

    async def ensure_tenant_exists(self, tenant_id: str) -> bool:
        """Ensure tenant exists in database, create if missing via SQL."""
        import subprocess
        
        try:
            # Check if tenant exists via SQL (using docker-compose defaults)
            # docker-compose.yml uses: POSTGRES_USER=sentinai, POSTGRES_DB=sentinai
            db_user = "sentinai"
            db_name = "sentinai"
            
            check_cmd = [
                "docker", "exec", "-i", "sentinai-postgres",
                "psql", "-U", db_user, "-d", db_name, "-tAc",
                f"SELECT COUNT(*) FROM tenant WHERE tenant_id = '{tenant_id}';"
            ]
            result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0 and result.stdout.strip() == "1":
                logger.debug(f"Tenant {tenant_id} already exists")
                return True
            
            # Create tenant via SQL
            domain_name = "CapitalMarketsTrading" if "FINANCE" in tenant_id else "HealthcareClaimsAndCareOps"
            tenant_name = tenant_id.replace("_", " ").title()
            
            create_cmd = [
                "docker", "exec", "-i", "sentinai-postgres",
                "psql", "-U", db_user, "-d", db_name, "-c",
                f"INSERT INTO tenant (tenant_id, name, status) VALUES ('{tenant_id}', '{tenant_name}', 'active') ON CONFLICT (tenant_id) DO NOTHING;"
            ]
            result = subprocess.run(create_cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                logger.info(f"Created tenant {tenant_id}")
                return True
            else:
                logger.warning(f"Failed to create tenant via SQL: {result.stderr}")
                return False
        except Exception as e:
            logger.warning(f"Failed to ensure tenant exists: {e}")
            return False
    
    async def seed_finance_tenant(
        self,
        tenant_id: str = "TENANT_FINANCE_001",
        count: int = 50,
    ) -> list[str]:
        """Seed data for finance tenant with realistic exception types."""
        logger.info(f"\n{'='*70}")
        logger.info(f"Seeding Finance Tenant: {tenant_id}")
        logger.info(f"{'='*70}")
        logger.info(f"Target count: {count} exceptions")
        
        # Ensure tenant exists
        await self.ensure_tenant_exists(tenant_id)
        
        exceptions = []
        base_time = datetime.now(timezone.utc)
        
        for i in range(count):
            exception_id = f"FIN-{uuid4().hex[:8].upper()}-{i+1:04d}"
            exception_type = random.choice(self.finance_exception_types)
            exception_time = base_time - timedelta(hours=random.randint(0, 168))  # Random time in last week
            
            payload = self._generate_finance_exception_payload(
                exception_id=exception_id,
                tenant_id=tenant_id,
                exception_type=exception_type,
                base_time=exception_time,
            )
            exceptions.append(payload)
        
        # Ingest individually (API processes one at a time even in batch mode)
        # Add small delay to avoid rate limiting
        all_exception_ids = []
        for i, exception_payload in enumerate(exceptions):
            # Small delay to avoid rate limiting (except for first request)
            if i > 0:
                await asyncio.sleep(0.15)  # 150ms delay between requests
            try:
                response = await self.client.post(
                    f"{self.api_url}/exceptions/{tenant_id}",
                    json={"exception": exception_payload},
                    headers=self._get_headers(tenant_id),
                )
                if response.status_code in (200, 202):
                    data = response.json()
                    if "exceptionId" in data:
                        all_exception_ids.append(data["exceptionId"])
                        if (i + 1) % 10 == 0:
                            logger.info(f"[PROGRESS] Ingested {i + 1}/{len(exceptions)} exceptions...")
                    else:
                        logger.warning(f"[WARNING] No exceptionId in response for exception {i+1}: {data}")
                else:
                    # Try to extract detailed error message
                    error_detail = response.text
                    try:
                        error_json = response.json()
                        # Try multiple possible fields for error details
                        error_detail = (
                            error_json.get("detail") or 
                            error_json.get("message") or 
                            error_json.get("error") or 
                            str(error_json)
                        )
                    except Exception as parse_error:
                        # If JSON parsing fails, use the raw text
                        error_detail = response.text[:500]  # Limit length
                    
                    logger.error(f"[FAILED] Failed to ingest exception {i+1}: {response.status_code}")
                    logger.error(f"  Error detail: {error_detail}")
                    
                    # Provide helpful hints based on error type
                    if response.status_code == 500:
                        error_lower = error_detail.lower()
                        if any(keyword in error_lower for keyword in ["kafka", "broker", "connection refused", "failed to publish"]):
                            logger.error("  [HINT] Kafka may not be running. Start Kafka with: docker-compose up -d kafka")
                        else:
                            logger.error("  [HINT] Check API server logs for detailed error information")
                            logger.error("  [HINT] Common causes: Kafka not running, database connection issues, or event publisher errors")
                    elif response.status_code == 401:
                        logger.error(f"  [HINT] API key may be invalid. Check that API server has been restarted after adding new API keys.")
                    elif response.status_code == 403:
                        logger.error(f"  [HINT] Tenant ID mismatch. Ensure API key matches the tenant ID in the URL.")
            except Exception as e:
                logger.error(f"[FAILED] Error ingesting exception {i+1}: {e}")
            
            # Small delay between requests to avoid overwhelming the API
            if i < len(exceptions) - 1:
                await asyncio.sleep(0.1)
        
        logger.info(f"[SUCCESS] Seeded {len(all_exception_ids)} exceptions for {tenant_id}")
        return all_exception_ids

    async def seed_healthcare_tenant(
        self,
        tenant_id: str = "TENANT_HEALTHCARE_042",
        count: int = 50,
    ) -> list[str]:
        """Seed data for healthcare tenant with realistic exception types."""
        logger.info(f"\n{'='*70}")
        logger.info(f"Seeding Healthcare Tenant: {tenant_id}")
        logger.info(f"{'='*70}")
        logger.info(f"Target count: {count} exceptions")
        
        # Ensure tenant exists
        await self.ensure_tenant_exists(tenant_id)
        
        exceptions = []
        base_time = datetime.now(timezone.utc)
        
        for i in range(count):
            exception_id = f"HC-{uuid4().hex[:8].upper()}-{i+1:04d}"
            exception_type = random.choice(self.healthcare_exception_types)
            exception_time = base_time - timedelta(hours=random.randint(0, 168))  # Random time in last week
            
            payload = self._generate_healthcare_exception_payload(
                exception_id=exception_id,
                tenant_id=tenant_id,
                exception_type=exception_type,
                base_time=exception_time,
            )
            exceptions.append(payload)
        
        # Ingest individually (API processes one at a time even in batch mode)
        all_exception_ids = []
        for i, exception_payload in enumerate(exceptions):
            try:
                response = await self.client.post(
                    f"{self.api_url}/exceptions/{tenant_id}",
                    json={"exception": exception_payload},
                    headers=self._get_headers(tenant_id),
                )
                if response.status_code in (200, 202):
                    data = response.json()
                    if "exceptionId" in data:
                        all_exception_ids.append(data["exceptionId"])
                        if (i + 1) % 10 == 0:
                            logger.info(f"[PROGRESS] Ingested {i + 1}/{len(exceptions)} exceptions...")
                    else:
                        logger.warning(f"[WARNING] No exceptionId in response for exception {i+1}: {data}")
                else:
                    # Try to extract detailed error message
                    error_detail = response.text
                    try:
                        error_json = response.json()
                        # Try multiple possible fields for error details
                        error_detail = (
                            error_json.get("detail") or 
                            error_json.get("message") or 
                            error_json.get("error") or 
                            str(error_json)
                        )
                    except Exception as parse_error:
                        # If JSON parsing fails, use the raw text
                        error_detail = response.text[:500]  # Limit length
                    
                    logger.error(f"[FAILED] Failed to ingest exception {i+1}: {response.status_code}")
                    logger.error(f"  Error detail: {error_detail}")
                    
                    # Provide helpful hints based on error type
                    if response.status_code == 500:
                        error_lower = error_detail.lower()
                        if any(keyword in error_lower for keyword in ["kafka", "broker", "connection refused", "failed to publish"]):
                            logger.error("  [HINT] Kafka may not be running. Start Kafka with: docker-compose up -d kafka")
                        else:
                            logger.error("  [HINT] Check API server logs for detailed error information")
                            logger.error("  [HINT] Common causes: Kafka not running, database connection issues, or event publisher errors")
                    elif response.status_code == 401:
                        logger.error(f"  [HINT] API key may be invalid. Check that API server has been restarted after adding new API keys.")
                    elif response.status_code == 403:
                        logger.error(f"  [HINT] Tenant ID mismatch. Ensure API key matches the tenant ID in the URL.")
            except Exception as e:
                logger.error(f"[FAILED] Error ingesting exception {i+1}: {e}")
            
            # Small delay between requests to avoid overwhelming the API
            if i < len(exceptions) - 1:
                await asyncio.sleep(0.1)
        
        logger.info(f"[SUCCESS] Seeded {len(all_exception_ids)} exceptions for {tenant_id}")
        return all_exception_ids


async def main():
    """Main seeding function."""
    parser = argparse.ArgumentParser(
        description="Seed multiple exceptions for Finance and Healthcare tenants",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API server URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--tenant-id",
        choices=["TENANT_FINANCE_001", "TENANT_HEALTHCARE_042", "all"],
        default="all",
        help="Specific tenant ID to seed or 'all' for both (default: all)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of exceptions to create per tenant (default: 50)",
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
    print("Multi-Tenant Exception Seeding")
    print("=" * 70)
    print(f"\nAPI URL: {args.api_url}")
    print(f"Tenant(s): {args.tenant_id}")
    print(f"Exceptions per tenant: {args.count}")
    if args.api_key:
        print(f"API Key: {args.api_key[:10]}..." if len(args.api_key) > 10 else f"API Key: {args.api_key}")
    print()
    
    async with MultiTenantExceptionSeeder(api_url=args.api_url, api_key=args.api_key) as seeder:
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
        
        if args.tenant_id == "TENANT_FINANCE_001":
            exception_ids = await seeder.seed_finance_tenant(
                tenant_id="TENANT_FINANCE_001",
                count=args.count,
            )
            all_exception_ids.extend(exception_ids)
        elif args.tenant_id == "TENANT_HEALTHCARE_042":
            exception_ids = await seeder.seed_healthcare_tenant(
                tenant_id="TENANT_HEALTHCARE_042",
                count=args.count,
            )
            all_exception_ids.extend(exception_ids)
        else:  # "all"
            finance_ids = await seeder.seed_finance_tenant(
                tenant_id="TENANT_FINANCE_001",
                count=args.count,
            )
            all_exception_ids.extend(finance_ids)
            
            healthcare_ids = await seeder.seed_healthcare_tenant(
                tenant_id="TENANT_HEALTHCARE_042",
                count=args.count,
            )
            all_exception_ids.extend(healthcare_ids)
        
        # Summary
        print("\n" + "=" * 70)
        print("Seeding Summary")
        print("=" * 70)
        print(f"Total exceptions ingested: {len(all_exception_ids)}")
        print(f"Successful: {len([x for x in all_exception_ids if x])}")
        print()
        print("Next steps:")
        print("1. Verify data in database:")
        print("   docker exec -it sentinai-postgres psql -U postgres -d sentinai -c \"SELECT tenant_id, COUNT(*) FROM exception GROUP BY tenant_id;\"")
        print("2. View data in UI:")
        print("   - Start UI: cd ui && npm run dev")
        print("   - Navigate to http://localhost:5173")
        print("   - Login with tenant: TENANT_FINANCE_001 or TENANT_HEALTHCARE_042")
        print("=" * 70)
        
        return 0 if all_exception_ids else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

