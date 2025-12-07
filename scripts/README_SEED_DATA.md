# UI Data Seeding Guide

This guide explains how to seed example data for testing the UI.

## Quick Start

1. **Start the backend server:**
   ```bash
   python -m uvicorn src.api.main:app --reload
   ```

2. **Run the seed script:**
   ```bash
   python scripts/seed_ui_data_simple.py
   ```
   
   Or use the convenience wrapper:
   ```bash
   python scripts/reseed_data.py
   ```
   
   **Note:** If the backend was restarted, you'll need to re-run the seed script as the exception store is in-memory and data is lost on restart.

3. **Start the UI dev server:**
   ```bash
   cd ui
   npm run dev
   ```

4. **Access the UI:**
   - Navigate to http://localhost:5173/login
   - Select tenant: `TENANT_FINANCE_001`
   - Select API key: `test_api_key_tenant_finance`
   - Select domain: `CapitalMarketsTrading` (or `TestDomain`)
   - Click "Continue"

## What Gets Seeded

The seed script creates:

1. **Config Files:**
   - Domain packs copied to `runtime/domainpacks/`
   - Tenant policy packs copied to `runtime/tenantpacks/`
   - These appear in the Config Browser (`/config`)

2. **Exceptions:**
   - 20 sample exceptions per tenant
   - Processed through the full pipeline (Intake → Triage → Policy → Resolution → Feedback)
   - Available in the Exceptions List (`/exceptions`)
   - Full detail available in Exception Detail pages (`/exceptions/:id`)

3. **Guardrail Recommendations:**
   - 5 sample recommendations per tenant/domain
   - Saved to `runtime/learning/{tenant_id}_{domain}_recommendations.jsonl`
   - Available in the Recommendations tab (`/config` → Recommendations tab)

## Available Test Tenants

Based on the sample tenant policy files:

| Tenant ID | Domain | API Key | Notes |
|-----------|--------|---------|-------|
| `TENANT_FINANCE_001` | `CapitalMarketsTrading` | `test_api_key_tenant_finance` | Finance domain with trading exceptions |
| `TENANT_HEALTHCARE_042` | `HealthcareClaimsAndCareOps` | (use matching API key) | Healthcare domain (may have validation issues) |

## Troubleshooting

### Backend Not Running
If you see "Backend server is not running", make sure the backend is started:
```bash
python -m uvicorn src.api.main:app --reload
```

### Tenant ID Mismatch
If you see "Tenant ID mismatch" errors, ensure:
- The API key matches the tenant ID
- The tenant policy file has the correct `tenantId` field
- You're using the correct API key in the seed script

### Healthcare Domain Pack Validation Errors
The healthcare domain pack may have schema validation issues. For now, focus on the finance domain pack which works correctly.

### No Exceptions Showing
- **Important:** If the backend was restarted, the in-memory exception store is cleared. Re-run the seed script:
  ```bash
  python scripts/seed_ui_data_simple.py
  ```
- Check that the backend server is running
- Verify exceptions were created (check backend logs)
- Ensure you're using the correct tenant ID and API key in the UI
- Check browser console for API errors
- Verify data exists via API:
  ```bash
  python -c "import requests; r = requests.get('http://localhost:8000/ui/exceptions?tenant_id=TENANT_FINANCE_001&page=1&page_size=10', headers={'X-API-KEY': 'test_api_key_tenant_finance'}); print('Total:', r.json().get('total', 0))"
  ```

## Manual Data Creation

If the seed script doesn't work, you can manually create exceptions via the API:

```bash
curl -X POST "http://localhost:8000/run" \
  -H "X-API-KEY: test_api_key_tenant_finance" \
  -H "Content-Type: application/json" \
  -d '{
    "domainPackPath": "domainpacks/finance.sample.json",
    "tenantPolicyPath": "tenantpacks/tenant_finance.sample.json",
    "exceptions": [
      {
        "sourceSystem": "TradingPlatform",
        "rawPayload": {
          "exceptionId": "EXC_001",
          "timestamp": "2024-01-15T10:00:00Z",
          "type": "TradeSettlementFailure",
          "amount": 1000.0,
          "description": "Sample exception"
        }
      }
    ]
  }'
```

## Viewing Seeded Data

After seeding, you can view:

1. **Exceptions List:** `/exceptions`
   - Filter by severity, status, date range
   - Click any exception ID to view details

2. **Exception Detail:** `/exceptions/:id`
   - Summary card with key information
   - Timeline tab: Agent decisions and pipeline stages
   - Evidence tab: RAG results, tool outputs, agent evidence
   - Explanation tab: Natural language explanations
   - Audit tab: Complete audit trail

3. **Supervisor Dashboard:** `/supervisor`
   - Overview KPIs
   - Escalations tab
   - Policy Violations tab

4. **Config Browser:** `/config`
   - Domain Packs tab
   - Tenant Policy Packs tab
   - Playbooks tab
   - Recommendations tab (guardrail recommendations)

5. **Config Detail:** `/config/:type/:id`
   - View full configuration JSON
   - Compare versions (if multiple versions exist)

## Next Steps

- Explore different exception types and severities
- Test filtering and pagination
- Try the simulation feature (Re-run button on exception detail page)
- Review guardrail recommendations
- Browse configuration files

