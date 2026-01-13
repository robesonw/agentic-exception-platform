# Playbook UI Fix - Implementation Complete

## Problem Fixed

The Recommended Playbook panel was showing "No playbook available" even though playbooks were matched because `current_playbook_id` was not being set in the database.

## Root Cause

`PolicyWorker` was setting `playbook_id` to exception type strings (e.g., `"FIN_SETTLEMENT_FAIL"`), but the database field `current_playbook_id` requires an integer ID. The conversion logic failed, leaving the field as `None`.

## Solution Implemented

Updated `PolicyWorker._update_exception_policy()` method to:

1. **Detect string playbook IDs**: Check if `playbook_id` is a string (exception type) rather than numeric
2. **Look up database ID**: Use `PlaybookRepository.get_candidate_playbooks()` to find the actual playbook database record by exception type
3. **Use integer ID**: Set `current_playbook_id` to the integer `playbook_id` from the database record
4. **Fallback handling**: If lookup fails, log warning but continue (graceful degradation)

## Code Changes

**File**: `src/workers/policy_worker.py`

**Method**: `_update_exception_policy()`

**Changes**:
- Added logic to detect when `playbook_id` is a string (exception type)
- Added database lookup using `PlaybookRepository.get_candidate_playbooks()` with `exception_type` filter
- Extract integer `playbook_id` from the database record
- Use integer ID when setting `current_playbook_id` field

## Expected Behavior After Fix

1. ✅ Playbook matched by exception type
2. ✅ Database lookup finds playbook record
3. ✅ `current_playbook_id` is set to integer ID
4. ✅ API endpoint `/exceptions/{tenant_id}/{exception_id}/playbook` returns playbook data
5. ✅ UI shows playbook with steps
6. ✅ "Mark Complete" buttons appear for steps

## Testing

To verify the fix works:

1. **Restart the policy worker** (to pick up code changes)
2. **Generate a new exception** with a matched playbook
3. **Check database**: Verify `current_playbook_id` is set (not NULL)
4. **Check API**: `GET /exceptions/{tenant_id}/{exception_id}/playbook` should return playbook data
5. **Check UI**: Recommended Playbook panel should show playbook with steps
6. **Check buttons**: "Mark Complete" buttons should appear for pending steps

## Notes

- The fix uses `get_candidate_playbooks()` which filters by exception type stored in the `conditions` JSONB column
- If multiple playbooks match, uses the first one (ordered by priority/created_at desc)
- If no playbook is found in database, logs warning but continues (allows graceful degradation)
- Works for both string exception types and numeric playbook IDs (backward compatible)

## Related Files

- `src/workers/policy_worker.py` - Fixed method
- `src/infrastructure/repositories/playbook_repository.py` - Used for database lookup
- `src/api/routes/exceptions.py` - API endpoint that reads `current_playbook_id`
- `ui/src/components/exceptions/RecommendedPlaybookPanel.tsx` - UI component that displays playbook

