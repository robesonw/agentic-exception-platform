# Demo Verification Guide

This document provides a quick verification checklist for the demo environment.

## Prerequisites

1. **Database**: PostgreSQL running with migrations applied
2. **Backend**: FastAPI server running on `http://localhost:8000`
3. **UI**: React dev server running on `http://localhost:5173` (or configured port)
4. **Demo Data**: 1000+ exceptions seeded across tenants

## Quick Verification

### 1. Data Verification

Run the verification script:
```bash
python scripts/verify_demo_data.py
```

Expected output:
- Tenants: 6+
- Exceptions: 1000+
- Events: 6000+
- Playbooks: 12
- Tools: 16

### 2. Backend Health

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"healthy"}`

### 3. API Endpoints

#### Test with Finance Tenant:
```bash
curl -H "X-API-KEY: test_api_key_tenant_finance" \
     -H "X-Tenant-Id: TENANT_FINANCE_001" \
     http://localhost:8000/ui/status/TENANT_FINANCE_001?limit=10
```

#### Test with Healthcare Tenant:
```bash
curl -H "X-API-KEY: test_api_key_tenant_health" \
     -H "X-Tenant-Id: TENANT_HEALTH_001" \
     http://localhost:8000/ui/status/TENANT_HEALTH_001?limit=10
```

### 4. UI Access

Open browser to:
- `http://localhost:5173` (or configured Vite port)

## Demo Features to Show

### 1. Exceptions List
- Navigate to Exceptions page
- Should show 500+ exceptions for Finance tenant
- Filter by severity, status, date range
- Pagination working

### 2. Exception Detail
- Click any exception
- View:
  - Basic info (ID, severity, status, SLA)
  - Timeline (full event history)
  - Playbook status (if assigned)
  - Evidence/Explanation tabs

### 3. Playbooks
- View playbook list
- See playbook steps and conditions
- Check playbook execution status on exceptions

### 4. Tools
- Navigate to Tools page
- See global and tenant-scoped tools
- View tool definitions and schemas
- Check tool enablement status

### 5. Timeline View
- Open exception detail
- Navigate to Timeline tab
- See full event history:
  - ExceptionIngested
  - TriageCompleted
  - PolicyEvaluated
  - PlaybookStarted
  - PlaybookStepCompleted
  - ToolExecutionRequested/Completed
  - ResolutionSuggested
  - PlaybookCompleted
  - FeedbackCaptured

## API Keys for Demo

- **Finance Tenant**: `test_api_key_tenant_finance` → `TENANT_FINANCE_001`
- **Healthcare Tenant**: `test_api_key_tenant_health` → `TENANT_HEALTH_001`

## Troubleshooting

### Backend not starting
- Check database connection: `DATABASE_URL` in `.env`
- Run migrations: `alembic upgrade head`
- Check logs for errors

### No exceptions showing
- Verify data was seeded: `python scripts/verify_demo_data.py`
- Check API key matches tenant ID
- Verify database has data: `python scripts/check_tenants.py`

### UI not connecting
- Check `VITE_API_BASE_URL` in `ui/.env`
- Verify backend is running
- Check browser console for CORS errors

## Demo Script

1. **Start Services**:
   ```bash
   # Terminal 1: Backend
   uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
   
   # Terminal 2: UI
   cd ui && npm run dev
   ```

2. **Verify Data**:
   ```bash
   python scripts/verify_demo_data.py
   ```

3. **Open UI**: Navigate to `http://localhost:5173`

4. **Demo Flow**:
   - Show exceptions list (500+ items)
   - Open exception detail
   - Show timeline with full event history
   - Show playbook execution
   - Show tools page
   - Switch tenants to show multi-tenant isolation

