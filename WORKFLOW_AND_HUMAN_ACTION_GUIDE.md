# Exception Processing Workflow & Human Action Guide

## Current State Analysis

Based on your exception `EXC-FIN-20260111185730-9235` showing `PolicyEvaluationCompleted`, here's what happens next and how human intervention fits in.

---

## Complete Workflow After PolicyEvaluationCompleted

### 1. **PolicyEvaluationCompleted** ✅ (Your Current Stage)

**What Happened:**
- PolicyWorker evaluated the exception against tenant policy guardrails
- Playbook was matched and assigned to the exception
- Event `PolicyEvaluationCompleted` was published
- Event `PlaybookMatched` was published

**What's Next:**
```
PolicyEvaluationCompleted
    ↓
PlaybookMatched Event Published
    ↓
PlaybookWorker Consumes Event
    ↓
PlaybookWorker Emits StepExecutionRequested
    ↓
ToolWorker OR Manual Step Completion
    ↓
PlaybookStepCompleted Events
    ↓
PlaybookCompleted (when all steps done)
    ↓
FeedbackWorker Processes Completion
```

### 2. **PlaybookWorker** (Next Automatic Step)

**What It Does:**
- Consumes `PlaybookMatched` events
- Loads the assigned playbook from Domain Pack
- Determines the next step to execute (based on `exception.current_step`)
- Emits `StepExecutionRequested` event for that step

**Current Behavior:**
- Emits step execution requests sequentially (one step at a time)
- Updates `exception.current_step` as steps complete
- Does NOT automatically execute steps (by design for MVP)

### 3. **Step Execution** (Human or Automated)

**Two Paths:**

#### Path A: Automated Tool Execution (Future/Phase 8+)
- ToolWorker consumes `StepExecutionRequested` events
- Executes tools automatically (for low-risk actions)
- Emits `ToolExecutionCompleted` events
- Emits `PlaybookStepCompleted` events

#### Path B: Manual Step Completion (Current MVP Behavior)
- Steps are **NOT automatically executed** in MVP
- Human operators must complete steps via API/UI
- Steps show as "pending" until manually completed

---

## Human Action Mechanisms

### 1. **Human Approval Queue** (For High-Risk Actions)

**Purpose:**
- Blocks high-risk actions until human approval
- Enforces tenant policy rules (e.g., CRITICAL severity requires approval)

**How It Works:**

**Policy Evaluation:**
- PolicyAgent checks `humanApprovalRules` in Tenant Policy Pack
- Example rule: `{"severity": "CRITICAL", "requireApproval": true}`
- If approval required, ResolutionAgent submits to ApprovalQueue

**Approval Queue API:**
```
GET /ui/approvals/{tenant_id}              # List pending approvals
POST /api/approvals/{approval_id}/approve  # Approve action
POST /api/approvals/{approval_id}/reject   # Reject action
```

**Approval Workflow:**
```
PolicyAgent → Approval Required
    ↓
ResolutionAgent → Submit to ApprovalQueue
    ↓
Status: PENDING (visible in UI)
    ↓
Human Reviews in Approval Dashboard
    ↓
Human Approves/Rejects
    ↓
If Approved → Action Proceeds
If Rejected → Action Blocked, Exception Escalated
```

**Current State:**
- Approval queue infrastructure exists (`src/workflow/approval.py`)
- Approval UI API exists (`src/api/routes/approval_ui.py`)
- **BUT**: Not fully integrated with event-driven workflow yet
- Approval queue is more for blocking resolution plans, not individual playbook steps

### 2. **Manual Playbook Step Completion** (Current Primary Mechanism)

**Purpose:**
- Allows humans to manually complete playbook steps
- Required for MVP since steps are not auto-executed

**API Endpoint:**
```
POST /exceptions/{tenant_id}/{exception_id}/playbook/steps/{step_order}/complete
```

**Request Body:**
```json
{
  "actorType": "human",
  "actorId": "user_123",
  "notes": "Step completed successfully"
}
```

**What Happens:**
1. API validates request
2. Creates `PlaybookStepCompletionRequested` event
3. Publishes to Kafka
4. PlaybookExecutionService processes event
5. Executes step action (notify, assign_owner, call_tool, etc.)
6. Emits `PlaybookStepCompleted` event
7. Updates `exception.current_step`
8. If all steps done, emits `PlaybookCompleted` event

**UI Integration:**
- Exception Detail page shows playbook steps
- Steps show status: "pending", "completed", "skipped"
- UI should have "Complete Step" buttons for pending steps
- Endpoint: `GET /exceptions/{tenant_id}/{exception_id}/playbook` shows step status

### 3. **Playbook Step Actions** (What Gets Executed)

**Supported Actions:**
- `notify` - Send notification (email, Slack, etc.)
- `assign_owner` - Assign exception to user/queue
- `set_status` - Update exception status
- `add_comment` - Add comment to exception
- `call_tool` - Execute a registered tool (requires approval for high-risk tools)

**Tool Execution:**
- Tools are registered in Domain Pack
- Tenant Policy Pack defines `approvedTools` allow-list
- High-risk tools require approval (even if step is manually completed)
- Tool execution emits `ToolExecutionRequested` → `ToolExecutionCompleted` events

---

## Current Application State

### ✅ What's Working

1. **Event-Driven Pipeline:**
   - Intake → Triage → Policy → Playbook Matching ✅
   - Events stored in `event_log` table
   - Workers process events asynchronously

2. **Playbook Matching:**
   - PolicyWorker matches playbooks based on exception type/severity
   - Playbooks assigned to exceptions
   - Playbook metadata stored in exception record

3. **Event Storage & Querying:**
   - Events stored in database
   - API endpoints for querying event timelines
   - UI can display audit trail

4. **Infrastructure:**
   - Approval queue system exists
   - Playbook execution service exists
   - Manual step completion API exists

### ⚠️ What's Partially Implemented

1. **Playbook Step Execution:**
   - PlaybookWorker emits `StepExecutionRequested` events
   - **BUT**: Steps are NOT automatically executed (by design for MVP)
   - Manual completion required via API

2. **Tool Execution:**
   - Tool execution infrastructure exists
   - **BUT**: Not fully integrated with playbook step execution
   - ToolWorker exists but may not be consuming all step execution requests

3. **Human Approval Integration:**
   - Approval queue exists
   - **BUT**: Not fully integrated with event-driven workflow
   - Approval is more for blocking resolution plans, not playbook steps

4. **UI Integration:**
   - Exception detail page shows playbook status
   - **BUT**: Manual step completion UI may not be fully implemented
   - Approval dashboard may not be fully integrated

---

## Recommended Next Steps for Your Exception

### For Exception `EXC-FIN-20260111185730-9235`:

**Current Status:**
- ✅ PolicyEvaluationCompleted
- ✅ PlaybookMatched
- ⏳ Waiting for PlaybookWorker to process (if not already done)
- ⏳ Steps pending manual completion

**To Complete the Exception:**

1. **Check if PlaybookWorker has processed:**
   - Look for `StepExecutionRequested` events in the audit trail
   - Check if `exception.current_step` is set

2. **If steps are pending:**
   - View playbook steps: `GET /exceptions/{tenant_id}/{exception_id}/playbook`
   - Complete steps manually: `POST /exceptions/{tenant_id}/{exception_id}/playbook/steps/{step_order}/complete`
   - Or use the UI if step completion buttons are available

3. **For human approval (if required):**
   - Check approval queue: `GET /ui/approvals/{tenant_id}`
   - Approve/reject as needed
   - Approval will unblock playbook execution

---

## Architecture Notes

### Why Steps Are Not Auto-Executed (MVP Design)

**Safety First:**
- Prevents unauthorized actions
- Ensures human oversight for all actions
- Allows review before execution

**Future Enhancement (Phase 8+):**
- Low-risk steps can auto-execute
- High-risk steps require approval
- Hybrid: Auto-execute with human approval for exceptions

### Human-in-the-Loop Design

**Two Levels:**

1. **Approval Queue** (High-Level):
   - Blocks entire resolution plans
   - Applied at PolicyAgent stage
   - For exceptions requiring human review before any action

2. **Manual Step Completion** (Step-Level):
   - Humans complete individual playbook steps
   - Applied at PlaybookWorker/ToolWorker stage
   - For step-by-step human oversight

**Combined:**
- High-risk exceptions → Approval Queue → Manual Step Completion
- Low-risk exceptions → Direct to Manual Step Completion (or auto-execute in future)

---

## Summary

**Your Exception's Journey:**
1. ✅ Intake → Normalized
2. ✅ Triage → Classified
3. ✅ Policy → Evaluated, Playbook Matched
4. ⏳ Playbook → Steps Pending (awaiting manual completion)
5. ⏳ Steps → Need Human Completion
6. ⏳ Completion → Feedback & Metrics

**Human Action Required:**
- **Manual Step Completion** is the primary mechanism in MVP
- Use API endpoint: `POST /exceptions/{tenant_id}/{exception_id}/playbook/steps/{step_order}/complete`
- **UI IS AVAILABLE**: The `RecommendedPlaybookPanel` component in the Exception Detail page has "Mark Completed" buttons
- Approval queue exists but is more for high-level plan blocking

**How to Complete Steps in UI:**
1. Navigate to Exception Detail page: `http://localhost:3000/exceptions/{exception_id}`
2. Find the "Recommended Playbook" panel (typically on the right side or in a tab)
3. Look for playbook steps list
4. Find the current step (marked with ▶ or highlighted)
5. Click "Mark Completed" button for that step
6. Step will be completed and `PlaybookStepCompleted` event will be emitted
7. Next step becomes available for completion
8. Repeat until all steps are completed

**Next Steps:**
1. ✅ Check exception detail page UI for playbook steps
2. ✅ Click "Mark Completed" for pending steps
3. ✅ Monitor completion via audit trail events
4. ✅ All steps completed → `PlaybookCompleted` event → FeedbackWorker processes

