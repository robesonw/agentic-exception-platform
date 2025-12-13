# Phase 7 – Actions & Playbooks MVP  
SentinAI – Multi-Tenant, Domain-Abstracted Exception Platform  
(Playbook Engine, Recommended Actions, Human-in-the-Loop Execution)

---

## 1. Purpose

Phase 7 introduces the **Actions & Playbooks MVP**.

Goal:  
For any exception, SentinAI should be able to:

1. **Recommend a playbook** (sequence of steps) based on:
   - Tenant
   - Domain
   - Exception type & severity
   - SLA status
   - Policy Pack & Domain Pack rules

2. **Execute or guide execution of steps**, with:
   - Clear, deterministic behavior (no surprise side-effects)
   - Read-only vs action-producing steps
   - Human-in-the-loop approvals for risky actions

3. **Expose playbook state in the UI**:
   - “Recommended Playbook” panel on Exception Detail
   - Step status: pending / running / completed / blocked
   - Who/what completed each step (agent vs human)

This is about **operationalizing** the intelligence we’ve built: turning LLM insight + policy into **repeatable workflows**.

---

## 2. Scope (MVP vs Non-Goals)

### In Scope (Phase 7)

- A **Playbook Engine** that:
  - Matches exceptions to appropriate playbooks.
  - Produces a clear recommended sequence of steps.
  - Tracks current step and execution state per exception.

- A **configuration-driven** playbook model:
  - Playbooks defined in DB/JSON via `playbook` and `playbook_step` tables.
  - Conditions driven by Domain Packs + Tenant Policy Packs (no hard-coded domain logic).

- **Basic step types**, including:
  - `notify` (e.g. send alert to queue, user, or system – stubbed or simple implementation)
  - `assign_owner` (assign to user/queue)
  - `set_status` (update exception status)
  - `add_comment` (append a note/event)
  - `call_tool` (invoke an allow-listed ToolDefinition – initially stub or log-only)

- Exception-level playbook state:
  - `current_playbook_id` & `current_step` fields on `exception` table (already defined in Phase 6).
  - Event log entries for each step execution.

- Minimal **UI integration**:
  - Exception Detail’s “Recommended Playbook” panel uses real backend data.
  - Ability for a user to:
    - See the recommended playbook and steps.
    - Advance steps manually (“Mark step as completed”).
    - Trigger certain actions if safe (e.g. notify only).

### Out of Scope (Phase 7)

- Full no-code workflow builder UI (drag-and-drop nodes) – we already have a mock; real builder can come later.
- Complex branching logic & loops (we will support simple conditions and linear flows for MVP).
- Deep integrations with external tools (ServiceNow/Jira/Slack/etc.) – we will stub or simulate tool execution, and log what would happen.
- Asynchronous distributed playbook executors – that’s more Phase 9.

---

## 3. Core Concepts

### 3.1 Playbook

A **Playbook** is a tenant-scoped, versioned template that defines:

- Metadata:
  - `playbook_id`
  - `tenant_id`
  - `name`
  - `version`
  - `conditions` (JSON)
  - `created_at`

- Conditions specify **when a playbook applies**, such as:
  - `domain`: Finance, Healthcare, Trading, Claims…
  - `exception_type`: “Trade Settlement Failure”, “Duplicate Claim”, etc.
  - `severity`: “critical”, “high”, etc.
  - `sla_window`: e.g. `{"minutes_remaining_lt": 60}`
  - `policy_tags`: tags from Tenant Policy Pack (e.g. `["margin_call", "reg_report"]`)

Examples (conceptual):

```json
{
  "match": {
    "domain": "Finance",
    "exception_type": "Trade Settlement Failure",
    "severity_in": ["high", "critical"],
    "sla_minutes_remaining_lt": 60
  },
  "priority": 100
}
Playbooks can be overlapping; the engine will pick the best match based on priority.

3.2 PlaybookStep
Each PlaybookStep belongs to a Playbook and represents one action or check:

Key attributes:

step_id

playbook_id

step_order (1, 2, 3…)

name (short label)

action_type (enum)

params (JSON)

created_at

MVP action_type values:

notify

Params: channel, template_id, placeholders (entity, amount, etc.)

assign_owner

Params: queue or user_id

set_status

Params: status (e.g. escalated, resolved, pending_review)

add_comment

Params: text_template with placeholders

call_tool

Params: tool_id, payload_template

The engine resolves templates using:

Exception attributes

Domain Pack & Tenant Policy Pack fields

3.3 Playbook Selection
For a given exception (tenant_id, exception_id):

Look up:

Exception record

Tenant Policy Pack

Domain Pack

Compute candidate playbooks for tenant_id:

Evaluate conditions JSON for each.

Filter by domain, exception_type, severity, SLA window, policy tags, etc.

Rank and choose:

Highest priority (if included in conditions)

Or last-updated, or explicit tie-breaking rule.

Set on exception:

current_playbook_id = selected_playbook_id

current_step = 1 (if not already in progress)

The selection is triggered:

At exception creation (by IntakeAgent / orchestration).

When severity changes.

When SLA window changes (future improvement).

4. Execution Model (MVP)
4.1 Step State per Exception
We will not store per-step state in separate tables yet. For MVP:

exception.current_playbook_id

exception.current_step

The rest of the state is tracked via events in exception_event:

PlaybookStarted (event_type)

PlaybookStepCompleted

PlaybookStepSkipped

PlaybookCompleted

Each event’s payload includes:

playbook_id

step_id / step_order

action_type

actor_type (agent/human/system)

actor_id (user / agent name)

Optional notes / result

4.2 Human-in-the-loop Execution
For Phase 7 MVP:

Steps are not automatically executed for high-risk actions. Instead:

Engine computes the recommended steps.

UI shows them.

Operator clicks “Complete Step” (for things they actually did in external systems), or calls safe actions via API.

The system:

Validates the step is the next expected step.

Appends an event such as PlaybookStepCompleted.

Bumps current_step on the exception.

If the last step is completed → emits PlaybookCompleted and may set status = resolved (depending on params and policy).

4.3 Safe Action Types (MVP)
We limit executable actions to those that are low risk:

notify: internally logs or (optionally) sends a stubbed notification.

add_comment: appends notes to event log.

set_status: controlled transitions only (e.g. cannot jump directly from open to resolved without steps).

assign_owner: changes owner field within allowed constraints.

call_tool will, in MVP:

Either log “would call tool X with params Y”, or

Perform a simple, safe stub (e.g. call an internal dummy endpoint).

5. Backend Changes (Phase 7)
5.1 Playbook Matching Service
Implement a Playbook Matching Service that:

Takes (tenant_id, exception) as input.

Loads:

Candidate playbooks for the tenant.

Tenant policy pack / domain pack as needed.

Evaluates playbook conditions.

Returns:

Selected playbook (or None if no match).

Reasoning summary (for logging/Co-Pilot display).

This service is used by:

Agents: TriageAgent / PolicyAgent / ResolutionAgent.

Exception APIs when recalculating recommended playbook manually.

5.2 Playbook Execution Service
Implement a Playbook Execution Service that:

Given (tenant_id, exception_id, playbook_id, step_order) and actor:

Validates this step is the next expected step.

Loads PlaybookStep.

Executes the action (either real or stub):

For safe actions: update exception, append events.

For risky actions: require explicit human invocation; still append events.

Emits PlaybookStepCompleted event.

Moves current_step forward, or marks playbook complete.

Provides methods:

start_playbook_for_exception

complete_step

(Optional) skip_step (for MVP, we can treat “skip” as a controlled completion with a flag).

5.3 APIs
New/updated endpoints:

POST /api/exceptions/{exception_id}/playbook/recalculate

Re-run playbook matching and update current_playbook_id / current_step (idempotent).

Logs an event.

GET /api/exceptions/{exception_id}/playbook

Returns:

Selected playbook metadata

Steps

Current step

Event-derived status per step (completed/pending)

POST /api/exceptions/{exception_id}/playbook/steps/{step_order}/complete

Body includes actor_type, actor_id, optional notes.

Invokes Playbook Execution Service.

These endpoints must enforce tenant isolation and be safe by default.

6. UI Changes (Phase 7)
6.1 Exception Detail – Recommended Playbook Panel
The existing “Recommended Playbook” panel will be wired to the new backend:

Shows:

Playbook name and version.

Steps list with:

Name

Action type

Status (Pending, Completed, Skipped)

Visual highlight for current step.

Capabilities:

“Recalculate Playbook” button:

Calls /playbook/recalculate.

For each step:

“Mark Completed” button (for allowed action types).

Optionally “Skip” button (if spec allows).

Step completion:

Calls /playbook/steps/{step_order}/complete.

Updates state + timeline after success.

6.2 Audit & Timeline Integration
Playbook-related events appear in the Exception event timeline:

PlaybookStarted

PlaybookStepCompleted

PlaybookCompleted

UI will:

Add small badges or icons to differentiate playbook events from other events.

7. Agent Integration (MVP Level)
Agents will propose and log playbook info, not fully automate everything yet:

TriageAgent:

Suggests severity / type.

Can hint at which playbook to use (via the Matching Service).

PolicyAgent:

Confirms that the recommended playbook aligns with policy pack rules.

Logs PolicyEvaluated events.

ResolutionAgent:

Suggests high-level “next action”.

Aligns with the playbook’s next step.

FeedbackAgent:

Observes outcomes (completed steps, resolution time).

Feeds back into analytics, but learning loops are Phase 10.

In MVP, the source of truth for playbook state is:

DB fields (current_playbook_id, current_step)

Events in exception_event

Agents do not bypass human approvals for high-risk steps.

8. Non-Functional Requirements
All operations must be tenant-aware and enforce strict isolation.

Playbook matching and execution must be idempotent:

Re-running matching should not duplicate events or corrupt state.

Completing a step twice should either be blocked or be a no-op with safe logging.

All step executions must emit events to the append-only log.

LLM usage (if any) in recommending or summarizing playbooks must go through the existing LLM routing with guardrails.

9. Exit Criteria (Phase 7)
Backend

Playbook Matching Service implemented and tested.

Playbook Execution Service implemented with:

start_playbook_for_exception

complete_step

APIs:

/api/exceptions/{id}/playbook

/api/exceptions/{id}/playbook/recalculate

/api/exceptions/{id}/playbook/steps/{step_order}/complete

All operations use DB-backed Playbook and PlaybookStep repositories.

Events emitted for playbook lifecycle (Started, StepCompleted, Completed).

UI

Exception Detail panel shows real recommended playbook & steps.

Users can:

Recalculate playbook.

Complete steps for safe action types.

Timeline shows playbook-related events.

Tests

Unit tests for matching & execution services.

API tests for playbook endpoints.

UI tests (or at least integration tests) around the Exception Detail with playbook display.

Documentation

docs/phase7-playbooks-mvp.md describes:

Scope, models, APIs, and UI behavior.

Main README/docs index updated to mention Phase 7 status when implemented.

For detailed configuration guide, see: [`docs/playbooks-configuration.md`](./playbooks-configuration.md)

For API reference, see: [`docs/playbooks-api.md`](./playbooks-api.md)