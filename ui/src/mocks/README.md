# Mock Data for Playbooks UI

This directory contains example data for the Playbooks admin UI at `/admin/playbooks`.

## Example Data File

- `playbooks.example.json` - Contains 8 example playbooks from different domains (Finance and Healthcare)

## Data Structure

The example data matches the format expected by the UI's `Playbook` interface:

```typescript
{
  id: string                    // Format: tenant_id:domain:exception_type
  name: string                  // Human-readable playbook name
  version: string               // Version number (e.g., "1.0.0")
  tenantId: string              // Tenant identifier
  domain: string                // Domain name (e.g., "CapitalMarketsTrading")
  exceptionType: string         // Exception type this playbook handles
  matchRules: object            // Rules for matching exceptions to this playbook
  steps: Array<object>          // Array of playbook steps
  referencedTools: string[]     // List of tool names referenced in steps
  isActive: boolean             // Whether the playbook is currently active
  createdAt: string             // ISO 8601 timestamp
}
```

## Using the Example Data

### Option 1: Use the Mock Helper (Recommended for Development)

A helper utility is provided to easily enable mock data:

1. In `ui/src/api/admin.ts`, modify the `listPlaybooks` function:

```typescript
import { getMockPlaybooks, shouldUseMockData } from '../mocks/playbooksMock'

export async function listPlaybooks(params: ListPlaybooksParams = {}): Promise<{ items: Playbook[]; total: number }> {
  // Use mock data in development if enabled
  if (shouldUseMockData()) {
    return getMockPlaybooks(params)
  }
  
  // Original API call...
  const response = await httpClient.get<{
    items: any[]
    total: number
  }>('/admin/config/playbooks', {
    // ... rest of the code
  });
}
```

2. Similarly, update `getPlaybook`:

```typescript
import { getMockPlaybook, shouldUseMockData } from '../mocks/playbooksMock'

export async function getPlaybook(id: string): Promise<Playbook> {
  if (shouldUseMockData()) {
    const mock = getMockPlaybook(id)
    if (!mock) {
      throw new Error(`Playbook ${id} not found`)
    }
    return mock
  }
  
  // Original API call...
}
```

3. To enable mock data, set in your `.env` file:
```
VITE_USE_MOCK_DATA=true
```

Or it will automatically use mocks in development mode.

### Option 2: Backend API Mocking

If you're using a tool like MSW (Mock Service Worker), you can create a mock handler:

```typescript
// ui/src/mocks/handlers.ts
import { rest } from 'msw';
import playbooksData from './playbooks.example.json';

export const handlers = [
  rest.get('/api/admin/config/playbooks', (req, res, ctx) => {
    return res(ctx.json(playbooksData));
  }),
];
```

### Option 3: Seed Database (Production-like)

If you want to seed the actual database with this data, you'll need to:

1. Create a script that reads this JSON file
2. Transform the data to match your backend's expected format
3. Use your backend's API or database seeding scripts to insert the data

## Example Playbooks Included

### Finance Domain (CapitalMarketsTrading)
1. **Mismatched Trade Details Resolution** - Handles trade execution mismatches
2. **Failed Allocation Recovery** - Recovers from allocation failures
3. **Position Break Reconciliation** - Resolves position discrepancies
4. **Settlement Failure Recovery** - Handles settlement failures
5. **Cash Break Reconciliation** - Resolves cash ledger breaks (inactive)
6. **Regulatory Report Rejection Handling** - Handles rejected regulatory reports

### Healthcare Domain (HealthcareClaimsAndCareOps)
1. **Claim Missing Authorization Resolution** - Attaches missing authorizations to claims
2. **Provider Credential Remediation** - Updates expired provider credentials

## Notes

- All timestamps are in ISO 8601 format
- Tool references in `referencedTools` should match tools defined in your domain packs
- The `matchRules` object defines conditions for when this playbook should be applied
- Steps can reference previous step results using `${step_N.result.field}` syntax
- Exception context fields can be referenced using `${exception.normalizedContext.field}` syntax

