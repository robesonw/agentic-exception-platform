# Critical Issues Analysis - Colon Prefix & Severity Override

## Image Evidence Summary

From the exceptions dashboard, I can see:

### Issue 1: Colon Prefix Inconsistency
- **Some exceptions**: `: fin_settlement_fail` (with colon, lowercase 'f')
- **Other exceptions**: `FIN_SETTLEMENT_FAIL` (no colon, uppercase)
- **Impact**: Inconsistent exception type formatting breaks matching and lookup

### Issue 2: Severity Override Inconsistency  
- **Most FIN_SETTLEMENT_FAIL exceptions**: `HIGH` severity (yellow tag)
- **One FIN_SETTLEMENT_FAIL exception**: `LOW` severity (blue tag) ✅
- **Impact**: Severity override works SOMETIMES but not consistently

### Key Observation
**One exception DOES have LOW severity!** This proves:
- ✅ Tenant policy CAN load
- ✅ Severity override logic IS working
- ❌ But policy loading is INCONSISTENT

This suggests a **timing/race condition** or **database state issue**.

## Root Causes

### Root Cause 1: Colon Prefix Normalization
- Normalization code exists in 3 places but isn't always executing
- Catalog cache may have stale values
- Exception creation happens via two paths (direct DB + Kafka), causing race conditions

### Root Cause 2: Tenant Policy Loading
- ActiveConfigLoader uses instance-level caching
- Each worker creates new ActiveConfigLoader instance per event
- If tenant policy pack is not ACTIVE in database, load fails
- Cache doesn't remember "not found" state, so retries may succeed/fail randomly

## Fixes Required

### Fix 1: Ensure Tenant Policy Pack is ACTIVE
**Action Required**: Verify tenant policy pack status in database
1. Go to http://localhost:3000/admin/packs
2. Check tenant policy pack for ACME_CAPITAL
3. Verify status is ACTIVE (not DRAFT or DEPRECATED)
4. If not active, activate it

### Fix 2: Colon Prefix Normalization
**Status**: Code fixes applied but need service restart
- ✅ Normalization in `_weighted_choice` 
- ✅ Normalization in scenario engine
- ✅ Normalization in intake agent
- ✅ Cache clearing on init

**Action Required**: Restart services to apply fixes

### Fix 3: Improve Tenant Policy Loading Reliability
**Potential Issue**: ActiveConfigLoader may need better error handling or cache invalidation

## Next Steps

1. **VERIFY tenant policy pack is ACTIVE** (most critical!)
2. **RESTART all services** to apply normalization fixes
3. **GENERATE new exceptions** and verify both issues are fixed
4. **MONITOR logs** to see if tenant policy loads consistently

## Expected Results After Fixes

- ✅ All exception types: `FIN_SETTLEMENT_FAIL` (no colon, uppercase)
- ✅ All FIN_SETTLEMENT_FAIL exceptions: `LOW` severity (from tenant policy override)
- ✅ Consistent behavior across all exceptions

