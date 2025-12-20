# Phase 12 Setup Guide

This guide helps you set up and test Phase 12 onboarding features.

## Issue: 500 Error on /admin/packs

If you're getting a 500 error on `http://localhost:3000/admin/packs`, it's likely because:

1. **Database tables don't exist** (most common)
2. **Database connection issue**
3. **Authentication issue**

## Step 1: Check Database Connection

Make sure your database is running and `DATABASE_URL` is set correctly:

```bash
# Check DATABASE_URL environment variable
echo $DATABASE_URL  # Linux/Mac
# or
echo %DATABASE_URL%  # Windows CMD
# or in PowerShell
$env:DATABASE_URL
```

The URL should look like:
```
postgresql+asyncpg://postgres:password@localhost:5432/dbname
```

## Step 2: Run Migrations

The Phase 12 tables need to be created. Run:

```bash
# Activate virtual environment first
.venv\Scripts\activate  # Windows
# or
source .venv/bin/activate  # Linux/Mac

# Run migrations
alembic upgrade head
```

Or use the helper script:
```bash
python scripts/run_migrations.py
```

This will create:
- `domain_packs` table
- `tenant_packs` table  
- `tenant_active_config` table
- Add `created_by` column to `tenant` table

## Step 3: Verify Tables Exist

Run the test script to check:

```bash
python scripts/test_phase12_endpoints.py
```

You should see:
```
domain_packs: OK
tenant_packs: OK
tenant_active_config: OK
```

## Step 4: Test the Endpoint

Once migrations are run, test the endpoint:

```bash
# Using curl
curl -X GET "http://localhost:8000/admin/packs/domain" \
  -H "X-API-KEY: your_api_key"

# Or visit in browser (with API key in header)
http://localhost:3000/admin/packs
```

## Step 5: Common Issues

### Issue: "password authentication failed"

**Solution**: Check your `DATABASE_URL` has the correct password.

### Issue: "relation does not exist" or "table does not exist"

**Solution**: Run migrations: `alembic upgrade head`

### Issue: "401 Unauthorized" or "403 Forbidden"

**Solution**: Make sure you have a valid API key and admin role.

### Issue: "503 Service Unavailable" with message about tables

**Solution**: The endpoint detected missing tables. Run migrations.

## Verification

After running migrations, you should be able to:

1. Visit `http://localhost:3000/admin/packs` without 500 errors
2. See empty lists (if no packs imported yet)
3. Import domain and tenant packs
4. Activate pack configurations

## Next Steps

1. **Create a tenant**: Visit `/admin/tenants` and create a tenant
2. **Import domain pack**: Go to `/admin/packs`, Domain Packs tab, click "Import Pack"
3. **Import tenant pack**: Go to Tenant Packs tab, click "Import Pack"
4. **Activate packs**: View pack details and click "Activate Version"

## Troubleshooting

If you still get errors after running migrations:

1. **Check server logs** for detailed error messages
2. **Verify database connection**: `python scripts/test_phase12_endpoints.py`
3. **Check API key**: Make sure you're authenticated with admin role
4. **Check browser console**: Look for network errors in DevTools

## Reference

- Migration file: `alembic/versions/013_add_onboarding_tables.py`
- API routes: `src/api/routes/onboarding.py`
- UI page: `ui/src/routes/admin/PacksPage.tsx`

