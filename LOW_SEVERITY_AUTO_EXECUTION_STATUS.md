# LOW Severity Auto-Execution Status

## Current State

**LOW severity exceptions are correctly assigned LOW severity** (verified with exception `aecceb8f-a7ea-4111-9c8d-98cc87c89e97`).

However, **auto-execution for LOW severity exceptions is NOT yet implemented**.

## Workflow Guide Reference

From `WORKFLOW_AND_HUMAN_ACTION_GUIDE.md` line 270-271:

```
- High-risk exceptions → Approval Queue → Manual Step Completion
- Low-risk exceptions → Direct to Manual Step Completion (or auto-execute in future)
```

The phrase **"(or auto-execute in future)"** indicates this is a planned feature, not currently implemented.

## Current Behavior

**ALL exceptions (including LOW severity) currently require manual step completion:**

1. PlaybookWorker emits `StepExecutionRequested` events
2. Steps wait for manual completion via:
   - UI: "Mark Completed" button in RecommendedPlaybookPanel
   - API: `POST /exceptions/{id}/playbook/steps/{step_order}/complete`
3. No automatic step execution based on severity

## What's Working

✅ **Severity Override**: LOW severity is correctly applied via tenant policy overrides  
✅ **Manual Step Completion**: Works via UI and API  
✅ **Playbook Matching**: Playbooks are matched and assigned correctly  
✅ **Pipeline Flow**: Intake → Triage → Policy → Playbook Matched → Steps Pending

## What's Not Implemented

❌ **Auto-Execution for LOW Severity**: No logic to automatically complete steps for LOW severity exceptions  
❌ **Severity-Based Execution Policy**: No code that checks severity to decide auto-execute vs manual

## Implementation Requirements (Future)

To implement auto-execution for LOW severity exceptions, you would need:

1. **Policy Decision**: PolicyAgent or PlaybookWorker needs to determine if steps should auto-execute based on:
   - Exception severity (LOW = auto-execute)
   - Tenant policy `humanApprovalRules` (check `requireApproval: false` for LOW)
   - Guardrails configuration

2. **Auto-Execution Logic**: ToolWorker or a new AutoExecutionWorker would:
   - Receive `StepExecutionRequested` events
   - Check if auto-execution is allowed (severity-based)
   - Automatically execute tool calls for the step
   - Emit `StepExecutionCompleted` events
   - Trigger next step automatically

3. **Configuration**: Tenant policy `humanApprovalRules` should support:
   ```json
   {
     "severity": "LOW",
     "requireApproval": false,  // Allow auto-execution
     "autoExecute": true  // NEW: Enable auto-execution
   }
   ```

## Recommendation

For now:
- ✅ Severity override is working correctly
- ✅ Manual step completion is the expected workflow
- ⏳ Auto-execution is a future enhancement

To proceed with manual completion:
1. Navigate to exception detail page
2. Find "Recommended Playbook" panel
3. Click "Mark Completed" for each step
4. Steps will complete sequentially

## Next Steps

If you want auto-execution implemented:
1. Create a feature request/issue
2. Define acceptance criteria (which severities? which steps?)
3. Implement auto-execution logic in ToolWorker or new worker
4. Add configuration to tenant policy packs
5. Update workflow guide to remove "(or auto-execute in future)"

