# Playbook UI "No Playbook Available" Bug

## Problem

The Recommended Playbook panel shows "No playbook available" even though:
- Pipeline Status shows "Playbook Matched" ✅
- Audit trail shows `PlaybookMatched` event was emitted ✅
- Playbook was matched and event was published ✅

But the UI shows "No playbook available" because the exception's `current_playbook_id` field is `None` in the database.

## Root Cause

In `src/workers/policy_worker.py`, when a playbook is matched:

1. **Playbook ID is set to exception type string**: 
   - Line 291: `playbook_id = playbook_exc_type` (e.g., `"FIN_SETTLEMENT_FAIL"`)
   - This is a STRING, not a database integer ID

2. **Conversion to integer fails**:
   - Line 465: `playbook_id_int = int(playbook_id) if playbook_id.isdigit() else None`
   - Since `"FIN_SETTLEMENT_FAIL"` is not numeric, `playbook_id.isdigit()` returns `False`
   - Result: `playbook_id_int = None`

3. **current_playbook_id is not set**:
   - Line 466: `update_fields["current_playbook_id"] = playbook_id_int` (which is `None`)
   - The exception's `current_playbook_id` field remains `None`

4. **API endpoint returns empty response**:
   - `GET /exceptions/{tenant_id}/{exception_id}/playbook` checks `if db_exception.current_playbook_id is None`
   - Returns empty response with `playbookId: None, playbookName: None, steps: []`

5. **UI shows "No playbook available"**:
   - `RecommendedPlaybookPanel` checks `if (!data || !data.playbookId || !data.playbookName)`
   - Shows "No playbook available"

## Code References

**PolicyWorker** (`src/workers/policy_worker.py`):
- Line 291: Sets `playbook_id = playbook_exc_type` (string)
- Line 465-466: Tries to convert to integer, fails, sets to `None`
- Line 323-331: Emits `PlaybookMatched` event (but database field not set)

**API Endpoint** (`src/api/routes/exceptions.py`):
- Line 1588: `if db_exception.current_playbook_id is None: return empty response`
- Line 1601: `playbook = await playbook_repo.get_playbook(db_exception.current_playbook_id, tenant_id)`
- Requires integer `current_playbook_id` to load playbook from database

**UI Component** (`ui/src/components/exceptions/RecommendedPlaybookPanel.tsx`):
- Line 131: `if (!data || !data.playbookId || !data.playbookName)` → Shows "No playbook available"

## Solution

The `PolicyWorker` needs to:

1. **Look up the actual playbook database ID** from the playbooks table based on exception type
2. **Use the database integer ID** when setting `current_playbook_id`
3. **Or** use a different mechanism that doesn't require integer IDs (but this would require schema changes)

### Option 1: Look up playbook ID from database (Recommended)

When matching a playbook by exception type, query the `playbooks` table to get the actual integer `playbook_id`:

```python
# After matching playbook by exception type
if playbook_id and isinstance(playbook_id, str):
    # Look up actual playbook ID from database
    async with get_db_session_context() as session:
        playbook_repo = PlaybookRepository(session)
        # Query playbooks by exception_type or name
        playbooks = await playbook_repo.list_playbooks(tenant_id)
        for pb in playbooks:
            if pb.exception_type == playbook_id or pb.name == playbook_id:
                playbook_id = pb.playbook_id  # Use integer ID
                break
```

### Option 2: Store playbook reference differently

Allow `current_playbook_id` to store string identifiers, but this requires schema changes.

## Impact

- **Users cannot complete playbook steps** because the UI doesn't show the playbook
- **Manual step completion is blocked** even though playbook was matched
- **Workflow is broken** for all exceptions with matched playbooks

## Workaround

Until this is fixed, users cannot complete steps via the UI. The playbook matching works, but the database field is not set, so the UI cannot display it.

## Next Steps

1. Update `PolicyWorker._update_exception_policy()` to look up actual playbook ID from database
2. Ensure playbooks are stored in database with integer IDs when domain packs are imported
3. Use integer playbook IDs when setting `current_playbook_id`
4. Test that UI shows playbook after fix
5. Verify "Mark Complete" buttons appear for steps

