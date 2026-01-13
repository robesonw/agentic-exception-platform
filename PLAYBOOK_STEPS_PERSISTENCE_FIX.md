# Playbook Steps Persistence Fix

## Problem

Playbooks were being created when domain packs were imported, but playbook **steps were not being persisted** to the database. This caused:

- ✅ Playbook records existed in database
- ✅ Playbooks could be matched and assigned to exceptions
- ❌ Steps list was empty (`steps=[]`)
- ❌ UI showed "No steps available"
- ❌ "Mark Complete" buttons didn't appear

## Root Cause

The `_extract_and_persist_playbooks()` function in `src/api/routes/admin_domainpacks.py` only created playbook records, but did not iterate through and persist the playbook steps.

## Solution

Updated `_extract_and_persist_playbooks()` to:

1. **Create playbook** (as before)
2. **Iterate through playbook.steps** from the domain pack
3. **Create PlaybookStepCreateDTO** for each step
4. **Persist steps** using `PlaybookStepRepository.create_playbook_step()`

## Code Changes

**File**: `src/api/routes/admin_domainpacks.py`

**Method**: `_extract_and_persist_playbooks()`

**Changes**:
- Added import for `PlaybookStepRepository` and `PlaybookStepCreateDTO`
- After creating playbook, iterate through `playbook.steps`
- Extract step fields (name, action, action_type, parameters)
- Create `PlaybookStepCreateDTO` for each step
- Call `step_repo.create_playbook_step()` to persist step
- Added error handling to continue with other steps if one fails

**Note**: `create_playbook_step()` automatically assigns `step_order` (next available order number), so we don't need to specify it manually.

## Expected Behavior After Fix

1. ✅ Domain pack imported
2. ✅ Playbook created with steps persisted
3. ✅ API endpoint `/exceptions/{tenant_id}/{exception_id}/playbook` returns steps
4. ✅ UI shows playbook with steps list
5. ✅ "Mark Complete" buttons appear for pending steps

## Testing

To verify the fix works:

1. **Re-import domain pack** (or wait for next import)
2. **Check database**: Verify `playbook_step` table has entries for playbooks
3. **Generate new exception**: Create exception with matched playbook
4. **Check API**: `GET /exceptions/{tenant_id}/{exception_id}/playbook` should return steps
5. **Check UI**: Recommended Playbook panel should show steps with "Mark Complete" buttons

## Important Note

**Existing playbooks won't have steps** - they were created before this fix. You need to:

1. Re-import the domain pack (this will create new playbook versions with steps)
2. Or manually add steps to existing playbooks via API/database

## Related Files

- `src/api/routes/admin_domainpacks.py` - Fixed function
- `src/infrastructure/repositories/playbook_step_repository.py` - Used for step persistence
- `src/api/routes/exceptions.py` - API endpoint that reads steps
- `ui/src/components/exceptions/RecommendedPlaybookPanel.tsx` - UI component that displays steps

