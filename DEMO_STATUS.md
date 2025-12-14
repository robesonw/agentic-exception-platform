# Demo Status & Setup Summary

## ✅ Completed

### 1. Database & Data
- **Database**: PostgreSQL connected and migrated
- **Demo Data**: Successfully seeded
  - 1056 exceptions (553 Finance + 500 Healthcare + 3 test)
  - 6783 events (full timelines)
  - 12 playbooks (6 per tenant)
  - 46 playbook steps
  - 16 tools (4 global + 6 per tenant)
  - Tool executions: 0 (need to verify if this is expected)

### 2. Backend API
- **Status**: Running on `http://localhost:8000`
- **Health Check**: ✅ Working (`/health` returns healthy)
- **Database Connection**: ⚠️ Health check shows disconnected, but data queries work
- **API Keys**: Configured
  - `test_api_key_tenant_finance` → `TENANT_FINANCE_001` (ADMIN)
  - `test_api_key_tenant_health` → `TENANT_HEALTH_001` (ADMIN)

### 3. UI
- **Status**: Started (check if running on `http://localhost:5173`)
- **Configuration**: `.env` file created with `VITE_API_BASE_URL=http://localhost:8000`

### 4. Files Created
- `.env` - Database configuration
- `ui/.env` - UI API configuration
- `scripts/verify_demo_data.py` - Data verification script
- `scripts/check_tenants.py` - Tenant verification script
- `scripts/verify_demo_endpoints.py` - Endpoint verification script
- `docs/demo-verification.md` - Verification guide

## ⚠️ Issues to Fix

### 1. UI Status Endpoint
- **Issue**: Returns 0 exceptions (falling back to in-memory store)
- **Location**: `src/api/routes/ui_status.py`
- **Cause**: Database query may be failing silently, catching exception and falling back
- **Fix Needed**: Debug the database query in `get_recent_exceptions` function

### 2. Exceptions List Endpoint
- **Issue**: Returns 500 Internal Server Error
- **Location**: `src/api/routes/exceptions.py` - `list_exceptions` function
- **Fix Needed**: Check error logs and fix the database query

### 3. Database Health Check
- **Issue**: Returns 503 (database disconnected)
- **Location**: `src/api/main.py` - `/health/db` endpoint
- **Note**: This may be a false negative - data queries work, so connection is likely fine

## 🎯 Demo Readiness

### Ready to Demo:
- ✅ Data is in database (verified)
- ✅ Backend server is running
- ✅ UI server started
- ✅ API keys configured
- ✅ All supporting data (playbooks, tools, events) created

### Needs Quick Fix:
- ⚠️ API endpoints need debugging (likely simple query issues)
- ⚠️ UI may not display data until endpoints are fixed

## 🚀 Quick Fix Steps

### Option 1: Debug Endpoints (Recommended)
1. Check backend logs for error details
2. Fix database queries in:
   - `src/api/routes/ui_status.py` - `get_recent_exceptions`
   - `src/api/routes/exceptions.py` - `list_exceptions`
3. Test endpoints again

### Option 2: Use Direct Database Queries
If endpoints can't be fixed quickly, you can:
1. Show data directly from database using verification scripts
2. Demonstrate the data structure and relationships
3. Show UI structure (even if data doesn't load)

## 📋 Demo Checklist

### Before Demo:
- [ ] Verify backend is running: `curl http://localhost:8000/health`
- [ ] Verify UI is running: Open `http://localhost:5173`
- [ ] Run data verification: `python scripts/verify_demo_data.py`
- [ ] Test at least one endpoint manually

### During Demo:
1. **Show Data Volume**
   - Run: `python scripts/verify_demo_data.py`
   - Show: 1000+ exceptions, 6000+ events

2. **Show Multi-Tenant Isolation**
   - Switch between Finance and Healthcare tenants
   - Show different data sets

3. **Show Exception Details**
   - Open exception detail page
   - Show timeline with full event history
   - Show playbook execution status

4. **Show Playbooks**
   - List playbooks
   - Show playbook steps and conditions
   - Show playbook execution on exceptions

5. **Show Tools**
   - List global and tenant-scoped tools
   - Show tool definitions and schemas
   - Show tool enablement

## 🔧 Troubleshooting

### Backend Not Starting
```bash
# Check database connection
python scripts/check_tenants.py

# Check .env file
cat .env

# Restart backend
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### UI Not Loading Data
1. Check browser console for errors
2. Verify `VITE_API_BASE_URL` in `ui/.env`
3. Test API endpoint directly with curl
4. Check CORS settings in backend

### No Data Showing
1. Verify data exists: `python scripts/verify_demo_data.py`
2. Check tenant IDs match API keys
3. Test database query directly

## 📊 Data Summary

```
Tenants: 6
  - TENANT_FINANCE_001: 553 exceptions
  - TENANT_HEALTH_001: 500 exceptions
  - Others: 3 exceptions

Total Exceptions: 1056
Total Events: 6783
Playbooks: 12 (6 per tenant)
Playbook Steps: 46
Tools: 16 (4 global + 12 tenant-scoped)
```

## 🎬 Demo Script

1. **Introduction**: "This is a multi-tenant exception processing platform..."
2. **Data Overview**: Show verification script output
3. **UI Navigation**: 
   - Exceptions list (if working)
   - Exception detail
   - Timeline view
   - Playbooks
   - Tools
4. **Multi-Tenant**: Switch tenants to show isolation
5. **Features**: Highlight key capabilities

## 📝 Notes

- All demo data is realistic and follows domain patterns
- Event timelines are complete and show full lifecycle
- Playbooks have diverse conditions and steps
- Tools include both global and tenant-scoped examples
- Data spans last 7 days with realistic timestamps

---

**Last Updated**: After seeding 1000 exceptions
**Status**: Data ready, endpoints need debugging
**Next Step**: Fix API endpoints or use alternative demo approach

