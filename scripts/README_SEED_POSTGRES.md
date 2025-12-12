# PostgreSQL Database Seeding via API

This script seeds the PostgreSQL database by calling the API endpoints, ensuring data appears in both the database and the UI.

## Prerequisites

1. **PostgreSQL must be running:**
   ```powershell
   .\scripts\docker_db.ps1 start
   ```

2. **Database migrations must be applied:**
   ```powershell
   alembic upgrade head
   ```

3. **API server must be running:**
   ```powershell
   uvicorn src.api.main:app --reload
   ```

## Usage

### Basic Usage (Seed Default Tenants)

```powershell
python scripts/seed_postgres_via_api.py
```

This will seed:
- `TENANT_FINANCE_001` with 20 finance exceptions
- `TENANT_HEALTHCARE_001` with 10 healthcare exceptions

### Custom Options

```powershell
# Seed specific tenant
python scripts/seed_postgres_via_api.py --tenant-id MY_TENANT --count 50

# Use different API URL
python scripts/seed_postgres_via_api.py --api-url http://localhost:8080

# Skip health checks
python scripts/seed_postgres_via_api.py --skip-health-check
```

## What Gets Created

The script creates sample exceptions via the API, which means:

1. **Data flows through the normal ingestion pipeline:**
   - IntakeAgent normalizes the exceptions
   - Data is stored in PostgreSQL
   - Events are logged to the exception_event table

2. **Data appears in both:**
   - **PostgreSQL database** (queryable via SQL)
   - **UI** (visible in the exceptions list)

## Verifying Data

### Check Database

```powershell
# Count exceptions
docker exec sentinai-postgres psql -U postgres -d sentinai -c "SELECT COUNT(*) FROM exception;"

# View exceptions for a tenant
docker exec sentinai-postgres psql -U postgres -d sentinai -c "SELECT exception_id, tenant_id, domain, severity, status FROM exception WHERE tenant_id = 'TENANT_FINANCE_001' LIMIT 10;"

# View events
docker exec sentinai-postgres psql -U postgres -d sentinai -c "SELECT COUNT(*) FROM exception_event;"
```

### Check UI

1. Start the UI dev server:
   ```powershell
   cd ui
   npm run dev
   ```

2. Navigate to http://localhost:5173

3. Login with:
   - Tenant: `TENANT_FINANCE_001`
   - API Key: `test_api_key_tenant_finance` (if using test auth)

4. Navigate to the Exceptions page - you should see the seeded exceptions

## Troubleshooting

### API Server Not Running

```
[FAILED] API server is not running or not accessible.
```

**Solution:** Start the API server:
```powershell
uvicorn src.api.main:app --reload
```

### Database Not Accessible

```
[WARNING] Database health check failed.
```

**Solution:** 
1. Ensure PostgreSQL is running: `.\scripts\docker_db.ps1 status`
2. Check migrations: `alembic current`
3. Apply migrations if needed: `alembic upgrade head`

### No Exceptions Created

If the script runs but no exceptions are created:

1. Check API logs for errors
2. Verify the ingestion endpoint is working:
   ```powershell
   curl -X POST http://localhost:8000/exceptions/TENANT_FINANCE_001 -H "Content-Type: application/json" -d '{"exception": {"sourceSystem": "Test", "rawPayload": {"exceptionId": "TEST-001", "type": "TestException", "severity": "LOW"}}}'
   ```

## Differences from Other Seed Scripts

- **`seed_ui_data.py`**: Uses in-memory store (Phase 1-2)
- **`seed_postgres_via_api.py`**: Uses PostgreSQL via API (Phase 6+)

The new script ensures data goes through the full ingestion pipeline and is stored in PostgreSQL, making it visible in both the database and UI.

