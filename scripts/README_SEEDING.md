# Exception Data Seeding Guide

This guide explains how to seed exception data for testing and demonstration purposes.

## Overview

The `seed_multi_tenant_exceptions.py` script creates realistic exception data for Finance and Healthcare tenants using the actual exception types defined in the domain packs.

## Prerequisites

1. **PostgreSQL Database**: Must be running
   ```powershell
   .\scripts\docker_db.ps1 start
   ```

2. **Database Migrations**: Must be applied
   ```bash
   alembic upgrade head
   ```

3. **API Server**: Must be running
   ```bash
   uvicorn src.api.main:app --reload
   ```

4. **Python Virtual Environment**: Must be activated
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

## Usage

### Basic Usage

Seed 50 exceptions for both Finance and Healthcare tenants (default):
```bash
python scripts/seed_multi_tenant_exceptions.py
```

### Seed Specific Tenant

Seed only Finance tenant:
```bash
python scripts/seed_multi_tenant_exceptions.py --tenant-id TENANT_FINANCE_001 --count 50
```

Seed only Healthcare tenant:
```bash
python scripts/seed_multi_tenant_exceptions.py --tenant-id TENANT_HEALTHCARE_042 --count 50
```

### Custom Count

Seed 100 exceptions per tenant:
```bash
python scripts/seed_multi_tenant_exceptions.py --count 100
```

### Skip Health Checks (Faster)

If you're confident services are running:
```bash
python scripts/seed_multi_tenant_exceptions.py --skip-health-check
```

### Custom API URL

If API is running on a different port:
```bash
python scripts/seed_multi_tenant_exceptions.py --api-url http://localhost:8080
```

## Exception Types Generated

### Finance Domain (TENANT_FINANCE_001)

The script generates exceptions using these types from `domainpacks/finance.sample.json`:

- **MISMATCHED_TRADE_DETAILS**: Execution details don't match original trade order
- **FAILED_ALLOCATION**: Allocations for block trades failed or partially processed
- **POSITION_BREAK**: Position quantity doesn't reconcile with trades + settlements (CRITICAL)
- **CASH_BREAK**: Cash ledger doesn't match expected clearing amounts (HIGH)
- **SETTLEMENT_FAIL**: Trade failed to settle by intended settle date (HIGH)
- **REG_REPORT_REJECTED**: Regulatory report rejected due to missing/invalid fields (HIGH)
- **SEC_MASTER_MISMATCH**: Security master identifiers inconsistent across systems (LOW)

### Healthcare Domain (TENANT_HEALTHCARE_042)

The script generates exceptions using these types from `domainpacks/healthcare.sample.json`:

- **CLAIM_MISSING_AUTH**: Claim submitted without required prior authorization (HIGH)
- **CLAIM_CODE_MISMATCH**: Procedure code inconsistent with diagnosis or eligibility (MEDIUM)
- **PROVIDER_CREDENTIAL_EXPIRED**: Provider credential/NPI status expired at service time (HIGH)
- **PATIENT_DEMOGRAPHIC_CONFLICT**: Patient demographics conflict across systems (LOW)
- **PHARMACY_DUPLICATE_THERAPY**: Medication order duplicates active therapy (CRITICAL)
- **ELIGIBILITY_COVERAGE_LAPSE**: Coverage inactive or lapsed on service date (HIGH)

## Generated Data Structure

Each exception includes:

- **Unique Exception ID**: Format `FIN-{UUID}-{sequence}` or `HC-{UUID}-{sequence}`
- **Realistic Payloads**: Domain-specific fields matching the exception type
- **Random Timestamps**: Exceptions distributed over the last week
- **Appropriate Severities**: Based on exception type and domain pack rules
- **Source Systems**: Randomly selected from domain-appropriate systems
- **Entity References**: Order IDs, Patient IDs, Account IDs, etc.

## Verification

After seeding, verify data in the database:

```sql
-- Count exceptions per tenant
SELECT tenant_id, COUNT(*) as exception_count 
FROM exception 
GROUP BY tenant_id;

-- View recent exceptions
SELECT exception_id, tenant_id, exception_type, severity, created_at
FROM exception
ORDER BY created_at DESC
LIMIT 20;
```

Or via Docker:
```bash
docker exec -it sentinai-postgres psql -U postgres -d sentinai -c "SELECT tenant_id, COUNT(*) FROM exception GROUP BY tenant_id;"
```

## View in UI

1. Start the UI:
   ```bash
   cd ui
   npm run dev
   ```

2. Navigate to: http://localhost:5173

3. Login with:
   - Tenant: `TENANT_FINANCE_001` or `TENANT_HEALTHCARE_042`
   - Use the appropriate API key if authentication is enabled

## Troubleshooting

### API Server Not Running
```
[FAILED] Cannot connect to API server at http://localhost:8000
```
**Solution**: Start the API server with `uvicorn src.api.main:app --reload`

### Database Connection Failed
```
[WARNING] Database health check failed
```
**Solution**: 
1. Ensure PostgreSQL is running: `.\scripts\docker_db.ps1 start`
2. Run migrations: `alembic upgrade head`

### Authentication Errors
```
[FAILED] Failed to ingest exception: 401 - Unauthorized
```
**Solution**: Provide API key with `--api-key` parameter or ensure default API keys are configured in the script.

### Slow Performance
For large counts (100+), the script ingests exceptions individually with a 0.1s delay between requests. This ensures reliability but may take time.

## Script Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--api-url` | API server URL | `http://localhost:8000` |
| `--tenant-id` | Tenant to seed (`TENANT_FINANCE_001`, `TENANT_HEALTHCARE_042`, or `all`) | `all` |
| `--count` | Number of exceptions per tenant | `50` |
| `--skip-health-check` | Skip API and database health checks | `False` |
| `--api-key` | API key for authentication | Auto-detect from tenant |

## Notes

- Exceptions are generated with realistic, domain-appropriate data structures
- Timestamps are distributed randomly over the last week
- Each exception type includes relevant entity references (order IDs, patient IDs, etc.)
- Severities are automatically assigned based on domain pack rules
- The script provides progress updates every 10 exceptions

