# PostgreSQL API Integration Fix

## Issue
The API ingestion endpoint was normalizing exceptions but not persisting them to PostgreSQL. Data was only stored in the in-memory store.

## Solution
Updated `src/api/routes/exceptions.py` to:
1. Persist normalized exceptions to PostgreSQL using `ExceptionRepository`
2. Log events to `ExceptionEventRepository`
3. Auto-create tenants if they don't exist
4. Use idempotent upsert operations

## Changes Made

### 1. Added PostgreSQL Persistence to Ingestion Endpoint
- After normalizing exceptions via IntakeAgent, the code now:
  - Creates/verifies tenant exists in database
  - Maps ExceptionRecord to database Exception model
  - Saves to PostgreSQL using `upsert_exception` (idempotent)
  - Logs creation event to `exception_event` table

### 2. Added Domain to Seeding Script
- Updated `scripts/seed_postgres_via_api.py` to:
  - Include `domain` parameter in `create_exception_payload`
  - Add domain to both `rawPayload` and `normalizedContext`
  - Auto-detect domain from tenant_id (Finance/Healthcare)
  - Pass domain explicitly for all tenant seeding methods

## Testing

After restarting the API server, run:

```powershell
python scripts/seed_postgres_via_api.py --tenant-id TENANT_FINANCE_001 --count 50
```

Then verify data in database:

```powershell
docker exec sentinai-postgres psql -U postgres -d sentinai -c "SELECT COUNT(*) FROM exception;"
docker exec sentinai-postgres psql -U postgres -d sentinai -c "SELECT exception_id, tenant_id, domain, severity, status FROM exception LIMIT 10;"
docker exec sentinai-postgres psql -U postgres -d sentinai -c "SELECT COUNT(*) FROM exception_event;"
```

## Important Notes

1. **API Server Must Be Restarted**: The changes require restarting the API server to take effect
2. **Database Connection**: Ensure `DATABASE_URL` is set in the API server environment
3. **Tenant Creation**: Tenants are auto-created if they don't exist
4. **Idempotency**: Uses `upsert_exception` so re-running the seed script won't create duplicates

## Troubleshooting

If data still doesn't appear:

1. Check API server logs for database errors
2. Verify DATABASE_URL is set: `echo $env:DATABASE_URL`
3. Check database connection: `python scripts/check_db_connection.py`
4. Verify migrations: `alembic current`

