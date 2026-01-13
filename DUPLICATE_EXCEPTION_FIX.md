# Duplicate Exception Creation Fix

## Issue
User requested 2 exceptions but got 4 exceptions generated. All had wrong severity (HIGH instead of LOW) and some had colon prefixes.

## Root Cause
The `_create_exception_from_scenario` method was creating exceptions **twice**:
1. **Direct DB creation** (line 565-577): Created exception directly in database using `upsert_exception`
2. **Kafka event** (line 522-540): Published `ExceptionIngested` event to Kafka, which intake worker processes

This caused:
- **Duplication**: Each exception created twice → 2 requested = 4 in database
- **Inconsistent normalization**: Direct DB creation bypassed intake worker normalization
- **Race conditions**: Two code paths could create exceptions with different data

## Fix Applied
**File**: `src/demo/scenario_engine.py`

**Changes**:
1. **Removed direct DB creation** (lines 560-577)
   - Removed `exception_repo.upsert_exception()` call
   - Removed `event_repo.append_event()` call for "ExceptionCreated" event
   - Added comment explaining why we rely only on Kafka

2. **Updated return type** (line 442)
   - Changed `_create_exception_from_scenario` return type from `Optional[Exception]` to `None`
   - Updated caller to always count as generated (no need to check return value)

3. **Updated caller logic** (line 430-437)
   - Removed check for `if exc:` since method no longer returns exception
   - Always count as generated if no exception raised

## Benefits
✅ **No duplication**: Exceptions created once (via intake worker)
✅ **Consistent normalization**: All exceptions go through intake worker normalization
✅ **Proper pipeline processing**: All exceptions go through full pipeline (intake → triage → policy)
✅ **Cleaner code**: Single source of truth for exception creation

## Testing
1. Verify tenant policy pack for ACME_CAPITAL is ACTIVE (http://localhost:3000/admin/packs)
2. Generate 2 exceptions from demo page
3. Verify:
   - Only 2 exceptions created (not 4)
   - No colon prefixes (FIN_SETTLEMENT_FAIL, not : fin_settlement_fail)
   - LOW severity for FIN_SETTLEMENT_FAIL (if tenant policy is active)

## Status
✅ Code fix applied
✅ Services restarted
⚠️ User needs to verify tenant policy is ACTIVE for severity overrides to work

