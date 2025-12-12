# Verification Steps: PostgreSQL Persistence

## ✅ Current Status

The diagnostic script confirms:
- ✅ Database connection is working
- ✅ Direct persistence is working (created test tenant, exception, and event)
- ✅ Database contains: 1 exception, 2 events, 3 tenants

## Next Steps to Verify Full Integration

### 1. Ensure API Server Has DATABASE_URL Set

The API server **must** have `DATABASE_URL` in its environment:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai"
```

### 2. Restart API Server

```powershell
# Stop current server (Ctrl+C), then:
uvicorn src.api.main:app --reload
```

### 3. Verify API Server Can Connect to Database

```powershell
# Check health endpoint
curl http://localhost:8000/health/db
# Should return: {"status":"healthy","database":"connected"}
```

### 4. Seed Data via API

```powershell
python scripts/seed_postgres_via_api.py --tenant-id TENANT_FINANCE_001 --count 50
```

### 5. Verify Data in Database

```powershell
# Count exceptions
docker exec sentinai-postgres psql -U postgres -d sentinai -c "SELECT COUNT(*) FROM exception;"

# View sample exceptions
docker exec sentinai-postgres psql -U postgres -d sentinai -c "SELECT exception_id, tenant_id, domain, severity, status FROM exception LIMIT 10;"

# Count events
docker exec sentinai-postgres psql -U postgres -d sentinai -c "SELECT COUNT(*) FROM exception_event;"
```

### 6. Check API Server Logs

Look for:
- `"Saved/upserted exception ... to PostgreSQL"` - indicates successful persistence
- `"Logged event for exception ..."` - indicates successful event logging
- Any database errors (should be logged with full traceback)

## Troubleshooting

### If data still doesn't appear:

1. **Check API server logs** for database errors
2. **Verify DATABASE_URL** is set in API server environment:
   ```powershell
   # In the API server terminal, check:
   echo $env:DATABASE_URL
   ```
3. **Test database connection** from API server context:
   ```powershell
   python scripts/diagnose_api_db_connection.py
   ```
4. **Check if API server was restarted** after code changes
5. **Verify PostgreSQL is running**:
   ```powershell
   .\scripts\docker_db.ps1 status
   ```

## Expected Results

After seeding 50 exceptions:
- `exception` table should have ~50 rows (plus any test data)
- `exception_event` table should have ~50 rows (one event per exception)
- `tenant` table should have at least 1 row (TENANT_FINANCE_001)

All exceptions should have:
- `domain` = "Finance" (or "Generic" if auto-detection didn't work)
- Valid `severity` values: low, medium, high, critical
- Valid `status` values: open, analyzing, resolved, escalated

