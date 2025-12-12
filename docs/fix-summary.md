# Fix Summary: PostgreSQL Persistence and Enum Handling

## Issues Fixed

### 1. API Not Persisting to PostgreSQL
- **Problem**: API ingestion endpoint was normalizing exceptions but not saving them to PostgreSQL
- **Solution**: Added PostgreSQL persistence code to `src/api/routes/exceptions.py` that:
  - Auto-creates tenants if they don't exist
  - Maps ExceptionRecord to database Exception model
  - Uses idempotent `upsert_exception` operation
  - Logs events to `exception_event` table

### 2. Enum Value Mismatch
- **Problem**: Database stores lowercase enum values (e.g., "high"), but SQLAlchemy was trying to match against enum names (e.g., "HIGH")
- **Solution**: Added `values_callable=lambda x: [e.value for e in x]` to all Enum column definitions in `src/infrastructure/db/models.py`
  - This tells SQLAlchemy to use the enum's `.value` attribute instead of the enum name
  - Fixed for: `TenantStatus`, `ExceptionSeverity`, `ExceptionStatus`, `ActorType`

### 3. Domain Not Included in Payloads
- **Problem**: Seeding script wasn't including domain in exception payloads
- **Solution**: Updated `scripts/seed_postgres_via_api.py` to:
  - Accept `domain` parameter in `create_exception_payload`
  - Add domain to both `rawPayload` and `normalizedContext`
  - Auto-detect domain from tenant_id

### 4. API Key Authentication
- **Problem**: Seeding script was getting 401 Unauthorized errors
- **Solution**: Added automatic API key detection and `X-API-KEY` header

## Next Steps

1. **Restart API Server** (CRITICAL):
   ```powershell
   # Stop current server (Ctrl+C), then:
   $env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai"
   uvicorn src.api.main:app --reload
   ```

2. **Verify Database Connection**:
   ```powershell
   python scripts/diagnose_api_db_connection.py
   ```

3. **Seed Data**:
   ```powershell
   python scripts/seed_postgres_via_api.py --tenant-id TENANT_FINANCE_001 --count 50
   ```

4. **Verify Data in Database**:
   ```powershell
   docker exec sentinai-postgres psql -U postgres -d sentinai -c "SELECT COUNT(*) FROM exception;"
   docker exec sentinai-postgres psql -U postgres -d sentinai -c "SELECT exception_id, tenant_id, domain, severity, status FROM exception LIMIT 10;"
   ```

## Important Notes

- The API server **MUST** have `DATABASE_URL` set in its environment
- The API server **MUST** be restarted after code changes
- Enum values are now correctly mapped between Python and PostgreSQL
- All persistence operations are idempotent (safe to retry)

