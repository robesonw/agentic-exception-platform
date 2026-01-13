# Severity Override Implementation

## Summary

Implemented tenant policy `customSeverityOverrides` feature in TriageAgent. The agent now checks tenant policy overrides after evaluating domain pack severity rules and applies them when a match is found.

## Changes Made

### 1. TriageAgent (`src/agents/triage.py`)

- **Added import**: `from src.models.tenant_policy import TenantPolicyPack`
- **Updated `__init__`**: Added optional `tenant_policy: Optional[TenantPolicyPack] = None` parameter
- **Updated `_evaluate_severity()` method**: 
  - Now checks `tenant_policy.custom_severity_overrides` after domain pack rules
  - Matches exception types (normalized to uppercase, no leading colons/spaces)
  - Applies override severity if match found
  - Logs when override is applied
  - Falls back to domain pack severity if no override matches

### 2. TriageWorker (`src/workers/triage_worker.py`)

- **Added import**: `from src.models.tenant_policy import TenantPolicyPack`
- **Updated `__init__`**: Added optional `tenant_policy: Optional[TenantPolicyPack] = None` parameter
- **Updated TriageAgent initialization**: Passes `tenant_policy` to TriageAgent

### 3. Worker Entry Point (`src/workers/__main__.py`)

- **Updated TriageWorker creation**: Passes `tenant_policy` stub (same pattern as PolicyWorker)

## How It Works

1. **Domain Pack Evaluation**: TriageAgent first evaluates domain pack severity rules to get base severity
2. **Override Check**: If `tenant_policy` is provided and has `custom_severity_overrides`, checks for matching exception type
3. **Exception Type Matching**: Normalizes both exception type and override type (uppercase, no leading colons/spaces) for comparison
4. **Override Application**: If match found, uses override severity instead of domain pack severity
5. **Logging**: Logs when override is applied for debugging

## Example

```python
# Domain Pack
severityRules: [
  { "condition": "exceptionType == 'FIN_SETTLEMENT_FAIL'", "severity": "HIGH" }
]

# Tenant Policy Pack
customSeverityOverrides: [
  { "exceptionType": "FIN_SETTLEMENT_FAIL", "severity": "LOW" }
]

# Result
# Domain pack says: HIGH
# Override says: LOW
# Final severity: LOW (from override)
```

## Important Note

**Current Limitation**: Workers are initialized with stub tenant policies. For this feature to work:

1. **For Testing/MVP**: Ensure the worker has the correct tenant policy loaded when it starts
2. **For Production**: Workers should load tenant policy per-event based on `tenant_id` from the event

The code implementation is correct and will apply overrides when the tenant policy is provided. The infrastructure concern is ensuring the correct tenant policy is available to the worker.

## Testing

To test the implementation:

1. Ensure tenant policy pack is imported and activated in the database
2. Restart the triage worker (or ensure it has the correct tenant policy)
3. Generate new exceptions with the override exception type
4. Check that severity is overridden (check logs for "Applied tenant policy severity override" message)
5. Verify exception severity in database/UI matches override, not domain pack

## Next Steps (Future Enhancement)

For proper multi-tenant support, consider:

1. Loading tenant policy per-event in `TriageWorker.process_event()`
2. Using a tenant policy repository/service to fetch active policy by tenant_id
3. Caching policies per-tenant to avoid repeated database queries
4. Handling policy versioning (use active version for tenant)

