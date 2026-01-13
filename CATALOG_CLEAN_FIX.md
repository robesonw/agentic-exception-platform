# Catalog File Clean Fix - Final Fix for Colon Prefix Issue

## Issue
Exception types were STILL showing colon prefixes (`:fin_settlement_fail`, `:fin_failed_allocation`) even after normalization code was added.

## Root Cause
The `demo/demoCatalog.json` file **STILL contained colon-prefixed values** in the `exception_types` weights section. Even though normalization code existed to strip colons, the source data itself had colons.

## Fix Applied
**File**: `demo/demoCatalog.json`

**Change**: Cleaned all exception type values in the catalog file by:
1. Finding all scenarios with `weights.exception_types`
2. Stripping leading colons from all `value` fields
3. Saving the cleaned catalog file

**Python script used**:
```python
import json
f = open('demo/demoCatalog.json', 'r', encoding='utf-8')
data = json.load(f)
f.close()

scenarios = data.get('scenarios', [])
cleaned = 0
for s in scenarios:
    weights = s.get('weights', {})
    exc_types = weights.get('exception_types', [])
    for et in exc_types:
        v = et.get('value', '')
        if v.startswith(':'):
            et['value'] = v.lstrip(':').strip()
            cleaned += 1

f = open('demo/demoCatalog.json', 'w', encoding='utf-8')
json.dump(data, f, indent=2)
f.close()
```

## Triple Protection Layer
Now colon prefixes are prevented at THREE levels:
1. **Source Data** (Catalog File): Cleaned - no colons in source data ✅
2. **_weighted_choice Method**: Normalizes when selecting from catalog ✅
3. **Intake Agent**: Final defensive normalization ✅

## Services Restarted
- Backend restarted to pick up cleaned catalog file

## Testing
Generate 2 new exceptions and verify:
- ✅ Only 2 exceptions created (duplication fix working)
- ✅ No colon prefixes (FIN_SETTLEMENT_FAIL, not :fin_settlement_fail)
- ✅ LOW severity (if tenant policy is active)

## Status
✅ **FIXED** - Catalog file cleaned, backend restarted

