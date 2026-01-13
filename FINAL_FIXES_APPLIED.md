# Final Fixes Applied for Colon Prefix and Severity Issues

## Issues Reported
1. **Colon Prefix Inconsistency**: One exception has colon prefix (`: fin_settlement_fail`), one doesn't
2. **Severity Override Not Working**: Both exceptions show HIGH severity instead of LOW (from tenant policy)
3. **Extra Exception**: Asked for 1 exception, got 2

## Fixes Applied

### 1. Enhanced Catalog Cache Clearing
**File:** `src/demo/scenario_engine.py` (line 70-71)
**Fix:** Clear class-level catalog cache when creating DemoScenarioEngine instance
```python
# Always start with no catalog cache to ensure fresh load
self._catalog: Optional[DemoCatalog] = None
# Clear class-level cache to ensure fresh catalog
DemoCatalogLoader.clear_cache()
```

### 2. Triple Normalization Protection (Already Applied)
- **Source Level** (`_weighted_choice`): Strips colons when selecting from catalog
- **Scenario Engine Level**: Normalizes after selection
- **Intake Agent Level**: Final defensive normalization

### 3. Force Catalog Reload (Already Applied)
**File:** `src/demo/scenario_engine.py` (line 632-636)
**Fix:** Force reload catalog in `_get_catalog` method

## Remaining Issues to Investigate

### Issue 1: Severity Override Not Working
**Symptoms:** Exceptions show HIGH severity instead of LOW
**Root Cause:** Triage worker logs show "No tenant policy loaded for tenant ACME_CAPITAL"
**Action Required:** 
- Verify tenant policy pack is ACTIVE in database
- Check if tenant policy pack exists for ACME_CAPITAL
- Verify ActiveConfigLoader is loading the pack correctly

### Issue 2: Colon Prefix Still Appearing
**Symptoms:** One exception has colon prefix, one doesn't
**Possible Causes:**
1. Catalog cache still has old values (even after clear)
2. Exception created via different code path
3. Race condition between direct DB creation and Kafka event processing

### Issue 3: Two Exceptions Instead of One
**Possible Causes:**
1. Exception created twice (direct DB + via Kafka)
2. Burst count logic issue
3. Multiple tenants/scenarios being processed

## Verification Steps

1. **Check Tenant Policy Status:**
   ```powershell
   # Check if tenant policy is active
   curl -H "X-API-Key: demo_acme_capital" http://localhost:8000/admin/packs/tenant?tenant_id=ACME_CAPITAL
   ```

2. **Generate New Exception:**
   - Go to http://localhost:3000/admin/demo
   - Select "Settlement Failure Storm"
   - Burst count: 1
   - Generate

3. **Verify:**
   - Should see only 1 exception
   - Exception type: `FIN_SETTLEMENT_FAIL` (no colon)
   - Severity: `LOW` (from tenant policy override)

## Code Changes Status

✅ All normalization fixes applied
✅ Catalog cache clearing enhanced
✅ Force reload added

⚠️ **Tenant policy loading issue needs investigation** - logs show policy not being loaded

## Next Steps

1. Verify tenant policy pack is ACTIVE
2. If not active, activate it
3. Restart services
4. Generate new exception
5. Verify both issues are fixed

