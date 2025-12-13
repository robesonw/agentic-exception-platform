# Phase 7 Actions & Playbooks MVP - GitHub Issues Checklist

## Component: Playbook Matching Service

### Issue P7-1: Implement Playbook Matching Service
**Labels:** `component:playbook`, `phase:7`, `priority:high`
**Description:**
- Implement Playbook Matching Service that selects appropriate playbook for exceptions
- Load candidate playbooks for tenant from database
- Evaluate playbook conditions against exception attributes:
  - Domain match
  - Exception type match
  - Severity match
  - SLA window conditions
  - Policy tags from Tenant Policy Pack
- Rank playbooks by priority (if specified in conditions)
- Return selected playbook with reasoning summary
- Support idempotent matching (re-running should not duplicate events)
- Reference: docs/phase7-playbooks-mvp.md Section 3.3 (Playbook Selection), Section 5.1

**Dependencies:** P6-13 (Playbook Repository)

**Acceptance Criteria:**
- [ ] Playbook Matching Service implemented
- [ ] Candidate playbooks loaded from database
- [ ] Condition evaluation functional (domain, exception_type, severity, SLA, policy_tags)
- [ ] Playbook ranking by priority functional
- [ ] Reasoning summary generated for logging/Co-Pilot
- [ ] Idempotent matching verified
- [ ] Unit tests for matching logic
- [ ] Integration tests with database

---

### Issue P7-2: Implement Playbook Condition Evaluation Engine
**Labels:** `component:playbook`, `phase:7`, `priority:high`
**Description:**
- Implement condition evaluation engine for playbook matching
- Support condition types:
  - `domain`: exact match
  - `exception_type`: exact or pattern match
  - `severity_in`: array of allowed severities
  - `sla_minutes_remaining_lt`: SLA window comparison
  - `policy_tags`: array of required policy tags
- Support priority-based tie-breaking
- Handle overlapping playbooks (multiple matches)
- Reference: docs/phase7-playbooks-mvp.md Section 3.1 (Playbook - Conditions)

**Dependencies:** P7-1

**Acceptance Criteria:**
- [ ] Condition evaluation engine implemented
- [ ] All condition types supported
- [ ] Priority-based tie-breaking functional
- [ ] Overlapping playbook handling implemented
- [ ] Unit tests for condition evaluation
- [ ] Edge cases tested (no matches, multiple matches)

---

## Component: Playbook Execution Service

### Issue P7-3: Implement Playbook Execution Service - Core Framework
**Labels:** `component:playbook`, `phase:7`, `priority:high`
**Description:**
- Implement Playbook Execution Service for step execution
- Support methods:
  - `start_playbook_for_exception(tenant_id, exception_id, playbook_id, actor)`
  - `complete_step(tenant_id, exception_id, playbook_id, step_order, actor, notes)`
  - `skip_step(tenant_id, exception_id, playbook_id, step_order, actor, notes)` (optional)
- Validate step is next expected step before execution
- Load PlaybookStep from database
- Track execution state via exception fields (current_playbook_id, current_step)
- Emit events for playbook lifecycle (PlaybookStarted, PlaybookStepCompleted, PlaybookCompleted)
- Reference: docs/phase7-playbooks-mvp.md Section 4 (Execution Model), Section 5.2

**Dependencies:** P6-13, P6-14 (Playbook Repositories), P6-8 (Event Repository)

**Acceptance Criteria:**
- [ ] Playbook Execution Service implemented
- [ ] `start_playbook_for_exception()` functional
- [ ] `complete_step()` functional
- [ ] `skip_step()` functional (if implemented)
- [ ] Step validation (next expected step) implemented
- [ ] Execution state tracked in exception fields
- [ ] Events emitted for playbook lifecycle
- [ ] Unit tests for execution service
- [ ] Integration tests with database

---

### Issue P7-4: Implement Playbook Step Action Executors
**Labels:** `component:playbook`, `phase:7`, `priority:high`
**Description:**
- Implement action executors for MVP step types:
  - `notify`: send alert/notification (stubbed or simple implementation)
  - `assign_owner`: assign exception to user/queue
  - `set_status`: update exception status (controlled transitions)
  - `add_comment`: append note/event to exception
  - `call_tool`: invoke allow-listed ToolDefinition (stub or log-only for MVP)
- Resolve template placeholders in step params using:
  - Exception attributes
  - Domain Pack fields
  - Tenant Policy Pack fields
- Support safe action execution (low-risk actions only)
- Log action execution results
- Reference: docs/phase7-playbooks-mvp.md Section 3.2 (PlaybookStep), Section 4.3 (Safe Action Types)

**Dependencies:** P7-3

**Acceptance Criteria:**
- [ ] Action executors implemented for all MVP step types
- [ ] Template placeholder resolution functional
- [ ] Safe action execution enforced
- [ ] Action execution results logged
- [ ] Unit tests for each action type
- [ ] Integration tests verify action execution

---

### Issue P7-5: Implement Human-in-the-Loop Approval Workflow
**Labels:** `component:playbook`, `phase:7`, `priority:medium`
**Description:**
- Implement human-in-the-loop approval workflow for high-risk actions
- Steps are not automatically executed for risky actions
- Engine computes recommended steps and exposes via UI
- Operator can manually complete steps via API
- System validates step is next expected step
- Append PlaybookStepCompleted event with actor_type (human/agent/system)
- Move current_step forward after completion
- Mark playbook complete when last step is completed
- Reference: docs/phase7-playbooks-mvp.md Section 4.2 (Human-in-the-loop Execution)

**Dependencies:** P7-3, P7-4

**Acceptance Criteria:**
- [ ] Human-in-the-loop workflow implemented
- [ ] Step validation before completion functional
- [ ] Actor type tracking (human/agent/system) functional
- [ ] Playbook completion detection functional
- [ ] Unit tests for approval workflow
- [ ] Integration tests verify human approval flow

---

## Component: Playbook Repository Enhancements

### Issue P7-6: Enhance Playbook Repository for Matching Queries
**Labels:** `component:repository`, `phase:7`, `priority:high`
**Description:**
- Enhance PlaybookRepository with query methods for matching:
  - `get_candidate_playbooks(tenant_id, domain, exception_type, severity, sla_minutes_remaining, policy_tags)`
  - `get_playbook_with_steps(playbook_id, tenant_id)` - retrieve playbook with ordered steps
- Support filtering by conditions (domain, exception_type, severity, etc.)
- Optimize queries for matching performance
- Reference: docs/phase7-playbooks-mvp.md Section 5.1 (Playbook Matching Service)

**Dependencies:** P6-13

**Acceptance Criteria:**
- [ ] Candidate playbook query methods implemented
- [ ] Playbook with steps retrieval functional
- [ ] Condition-based filtering supported
- [ ] Query performance optimized with indexes
- [ ] Unit tests for query methods
- [ ] Integration tests verify matching queries

---

### Issue P7-7: Enhance Playbook Step Repository for Execution
**Labels:** `component:repository`, `phase:7`, `priority:high`
**Description:**
- Enhance PlaybookStepRepository with execution support:
  - `get_step_by_order(playbook_id, step_order, tenant_id)` - retrieve specific step
  - `get_steps_ordered(playbook_id, tenant_id)` - retrieve all steps in order
- Support step ordering validation
- Ensure tenant isolation in all queries
- Reference: docs/phase7-playbooks-mvp.md Section 5.2 (Playbook Execution Service)

**Dependencies:** P6-14

**Acceptance Criteria:**
- [ ] Step retrieval by order implemented
- [ ] Ordered steps retrieval functional
- [ ] Step ordering validation functional
- [ ] Tenant isolation enforced
- [ ] Unit tests for step repository methods
- [ ] Integration tests verify step retrieval

---

## Component: Playbook APIs

### Issue P7-8: Implement Playbook Recalculation API Endpoint
**Labels:** `component:api`, `phase:7`, `priority:high`
**Description:**
- Implement `POST /api/exceptions/{exception_id}/playbook/recalculate` endpoint
- Re-run playbook matching for exception
- Update `current_playbook_id` and `current_step` on exception
- Log event for recalculation
- Ensure idempotent operation (re-running should not duplicate events)
- Enforce tenant isolation
- Reference: docs/phase7-playbooks-mvp.md Section 5.3 (APIs)

**Dependencies:** P7-1, P6-6 (Exception Repository)

**Acceptance Criteria:**
- [ ] Recalculation endpoint implemented
- [ ] Playbook matching re-executed
- [ ] Exception fields updated correctly
- [ ] Event logged for recalculation
- [ ] Idempotent operation verified
- [ ] Tenant isolation enforced
- [ ] API tests for recalculation endpoint
- [ ] Integration tests verify recalculation

---

### Issue P7-9: Implement Playbook Status API Endpoint
**Labels:** `component:api`, `phase:7`, `priority:high`
**Description:**
- Implement `GET /api/exceptions/{exception_id}/playbook` endpoint
- Return playbook metadata:
  - Selected playbook (name, version, conditions)
  - Steps list with status (pending/completed/skipped)
  - Current step indicator
  - Event-derived status per step
- Derive step status from exception_event log
- Enforce tenant isolation
- Reference: docs/phase7-playbooks-mvp.md Section 5.3 (APIs)

**Dependencies:** P6-13, P6-14, P6-8 (Event Repository)

**Acceptance Criteria:**
- [ ] Playbook status endpoint implemented
- [ ] Playbook metadata returned correctly
- [ ] Steps list with status returned
- [ ] Current step indicator functional
- [ ] Event-derived status calculation functional
- [ ] Tenant isolation enforced
- [ ] API tests for playbook status endpoint
- [ ] Integration tests verify status retrieval

---

### Issue P7-10: Implement Playbook Step Completion API Endpoint
**Labels:** `component:api`, `phase:7`, `priority:high`
**Description:**
- Implement `POST /api/exceptions/{exception_id}/playbook/steps/{step_order}/complete` endpoint
- Accept request body with:
  - `actor_type` (human/agent/system)
  - `actor_id` (user ID or agent name)
  - `notes` (optional)
- Invoke Playbook Execution Service to complete step
- Validate step is next expected step
- Execute action (if safe)
- Emit PlaybookStepCompleted event
- Update exception state (current_step)
- Return updated playbook status
- Enforce tenant isolation
- Reference: docs/phase7-playbooks-mvp.md Section 5.3 (APIs)

**Dependencies:** P7-3, P7-4

**Acceptance Criteria:**
- [ ] Step completion endpoint implemented
- [ ] Request body validation functional
- [ ] Step validation (next expected) functional
- [ ] Action execution triggered
- [ ] Event emitted correctly
- [ ] Exception state updated
- [ ] Tenant isolation enforced
- [ ] API tests for step completion endpoint
- [ ] Integration tests verify step completion

---

## Component: Agent Integration

### Issue P7-11: Integrate Playbook Matching into TriageAgent
**Labels:** `component:agent`, `phase:7`, `priority:medium`
**Description:**
- Integrate Playbook Matching Service into TriageAgent
- After triage completion, suggest playbook via Matching Service
- Log playbook suggestion in agent decision
- Do not automatically assign playbook (PolicyAgent will confirm)
- Reference: docs/phase7-playbooks-mvp.md Section 7 (Agent Integration - MVP Level)

**Dependencies:** P7-1

**Acceptance Criteria:**
- [ ] TriageAgent integrated with Playbook Matching Service
- [ ] Playbook suggestion logged in agent decision
- [ ] No automatic playbook assignment
- [ ] Existing TriageAgent tests updated and passing
- [ ] Integration tests verify playbook suggestion

---

### Issue P7-12: Integrate Playbook Matching into PolicyAgent
**Labels:** `component:agent`, `phase:7`, `priority:high`
**Description:**
- Integrate Playbook Matching Service into PolicyAgent
- After policy evaluation, confirm recommended playbook aligns with policy pack rules
- Assign playbook to exception (set current_playbook_id, current_step = 1)
- Log PolicyEvaluated event with playbook assignment
- Ensure playbook selection respects tenant guardrails
- Reference: docs/phase7-playbooks-mvp.md Section 7 (Agent Integration - MVP Level)

**Dependencies:** P7-1, P6-18 (PolicyAgent with Repositories)

**Acceptance Criteria:**
- [ ] PolicyAgent integrated with Playbook Matching Service
- [ ] Playbook confirmation against policy pack functional
- [ ] Playbook assignment to exception functional
- [ ] PolicyEvaluated event includes playbook info
- [ ] Tenant guardrails respected
- [ ] Existing PolicyAgent tests updated and passing
- [ ] Integration tests verify playbook assignment

---

### Issue P7-13: Integrate Playbook Execution into ResolutionAgent
**Labels:** `component:agent`, `phase:7`, `priority:medium`
**Description:**
- Integrate Playbook Execution Service into ResolutionAgent
- ResolutionAgent suggests high-level "next action" aligned with playbook's next step
- Do not automatically execute steps (human-in-the-loop for MVP)
- Log ResolutionSuggested event with playbook step reference
- Reference: docs/phase7-playbooks-mvp.md Section 7 (Agent Integration - MVP Level)

**Dependencies:** P7-3, P6-19 (ResolutionAgent with Repositories)

**Acceptance Criteria:**
- [ ] ResolutionAgent integrated with Playbook Execution Service
- [ ] Next action suggestion aligned with playbook step
- [ ] No automatic step execution
- [ ] ResolutionSuggested event includes playbook step reference
- [ ] Existing ResolutionAgent tests updated and passing
- [ ] Integration tests verify playbook alignment

---

### Issue P7-14: Integrate Playbook Analytics into FeedbackAgent
**Labels:** `component:agent`, `phase:7`, `priority:low`
**Description:**
- Integrate playbook analytics into FeedbackAgent
- Observe playbook execution outcomes (completed steps, resolution time)
- Feed back into analytics (learning loops are Phase 10)
- Log FeedbackCaptured event with playbook metrics
- Reference: docs/phase7-playbooks-mvp.md Section 7 (Agent Integration - MVP Level)

**Dependencies:** P7-3, P6-20 (FeedbackAgent with Repositories)

**Acceptance Criteria:**
- [ ] FeedbackAgent observes playbook execution outcomes
- [ ] Playbook metrics captured in feedback
- [ ] FeedbackCaptured event includes playbook metrics
- [ ] Existing FeedbackAgent tests updated and passing
- [ ] Integration tests verify playbook analytics

---

## Component: UI Integration

### Issue P7-15: Implement Recommended Playbook Panel in Exception Detail
**Labels:** `component:ui`, `phase:7`, `priority:high`
**Description:**
- Implement "Recommended Playbook" panel in Exception Detail view
- Display playbook metadata:
  - Playbook name and version
  - Steps list with:
    - Step name
    - Action type
    - Status (Pending, Completed, Skipped)
  - Visual highlight for current step
- Fetch data from `/api/exceptions/{id}/playbook` endpoint
- Ensure tenant context is passed to API
- Reference: docs/phase7-playbooks-mvp.md Section 6.1 (Exception Detail - Recommended Playbook Panel)

**Dependencies:** P7-9

**Acceptance Criteria:**
- [ ] Recommended Playbook panel implemented
- [ ] Playbook metadata displayed correctly
- [ ] Steps list with status displayed
- [ ] Current step highlighted visually
- [ ] Data fetched from backend API
- [ ] Tenant context passed correctly
- [ ] UI tests for playbook panel
- [ ] Integration tests verify panel display

---

### Issue P7-16: Implement Playbook Recalculation Button
**Labels:** `component:ui`, `phase:7`, `priority:medium`
**Description:**
- Implement "Recalculate Playbook" button in Recommended Playbook panel
- Call `POST /api/exceptions/{id}/playbook/recalculate` endpoint
- Show loading state during recalculation
- Refresh playbook display after successful recalculation
- Handle errors gracefully
- Reference: docs/phase7-playbooks-mvp.md Section 6.1

**Dependencies:** P7-8, P7-15

**Acceptance Criteria:**
- [ ] Recalculate button implemented
- [ ] API call functional
- [ ] Loading state displayed
- [ ] Playbook display refreshed after recalculation
- [ ] Error handling implemented
- [ ] UI tests for recalculation button
- [ ] Integration tests verify recalculation flow

---

### Issue P7-17: Implement Step Completion Actions in UI
**Labels:** `component:ui`, `phase:7`, `priority:high`
**Description:**
- Implement step completion actions in Recommended Playbook panel
- For each step, show:
  - "Mark Completed" button (for allowed action types)
  - Optionally "Skip" button (if spec allows)
- On step completion:
  - Call `POST /api/exceptions/{id}/playbook/steps/{step_order}/complete`
  - Show loading state
  - Refresh playbook display after success
  - Update timeline after success
- Handle errors gracefully
- Reference: docs/phase7-playbooks-mvp.md Section 6.1

**Dependencies:** P7-10, P7-15

**Acceptance Criteria:**
- [ ] Step completion buttons implemented
- [ ] API call functional
- [ ] Loading state displayed
- [ ] Playbook display refreshed after completion
- [ ] Timeline updated after completion
- [ ] Error handling implemented
- [ ] UI tests for step completion
- [ ] Integration tests verify step completion flow

---

### Issue P7-18: Integrate Playbook Events into Event Timeline
**Labels:** `component:ui`, `phase:7`, `priority:medium`
**Description:**
- Integrate playbook-related events into Exception event timeline
- Display playbook events:
  - PlaybookStarted
  - PlaybookStepCompleted
  - PlaybookCompleted
- Add visual badges/icons to differentiate playbook events from other events
- Show event details (playbook_id, step_id, actor_type, actor_id, notes)
- Reference: docs/phase7-playbooks-mvp.md Section 6.2 (Audit & Timeline Integration)

**Dependencies:** P6-27 (Event Timeline UI), P6-8 (Event Repository)

**Acceptance Criteria:**
- [ ] Playbook events displayed in timeline
- [ ] Visual differentiation for playbook events
- [ ] Event details displayed correctly
- [ ] Timeline updated after playbook actions
- [ ] UI tests for playbook events in timeline
- [ ] Integration tests verify event display

---

## Component: Testing

### Issue P7-19: Implement Unit Tests for Playbook Matching Service
**Labels:** `component:testing`, `phase:7`, `priority:high`
**Description:**
- Write comprehensive unit tests for Playbook Matching Service
- Test condition evaluation:
  - Domain matching
  - Exception type matching
  - Severity matching
  - SLA window conditions
  - Policy tag matching
- Test playbook ranking and selection
- Test idempotent matching
- Test edge cases (no matches, multiple matches)
- Reference: docs/phase7-playbooks-mvp.md Section 9 (Exit Criteria - Tests)

**Dependencies:** P7-1, P7-2

**Acceptance Criteria:**
- [ ] Unit tests for matching service implemented
- [ ] All condition types tested
- [ ] Playbook ranking tested
- [ ] Idempotent matching tested
- [ ] Edge cases tested
- [ ] Test coverage >80% for matching service
- [ ] All tests passing

---

### Issue P7-20: Implement Unit Tests for Playbook Execution Service
**Labels:** `component:testing`, `phase:7`, `priority:high`
**Description:**
- Write comprehensive unit tests for Playbook Execution Service
- Test step execution:
  - Step validation (next expected step)
  - Action execution for each action type
  - Template placeholder resolution
  - Event emission
  - State updates
- Test playbook lifecycle:
  - Playbook start
  - Step completion
  - Playbook completion
- Test human-in-the-loop workflow
- Reference: docs/phase7-playbooks-mvp.md Section 9 (Exit Criteria - Tests)

**Dependencies:** P7-3, P7-4, P7-5

**Acceptance Criteria:**
- [ ] Unit tests for execution service implemented
- [ ] Step execution tested
- [ ] Action types tested
- [ ] Playbook lifecycle tested
- [ ] Human-in-the-loop workflow tested
- [ ] Test coverage >80% for execution service
- [ ] All tests passing

---

### Issue P7-21: Implement API Tests for Playbook Endpoints
**Labels:** `component:testing`, `phase:7`, `priority:high`
**Description:**
- Write integration tests for playbook API endpoints:
  - `POST /api/exceptions/{id}/playbook/recalculate`
  - `GET /api/exceptions/{id}/playbook`
  - `POST /api/exceptions/{id}/playbook/steps/{step_order}/complete`
- Test tenant isolation in API responses
- Test error handling (invalid step order, missing playbook, etc.)
- Test idempotent operations
- Reference: docs/phase7-playbooks-mvp.md Section 9 (Exit Criteria - Tests)

**Dependencies:** P7-8, P7-9, P7-10

**Acceptance Criteria:**
- [ ] API tests for all playbook endpoints implemented
- [ ] Tenant isolation verified in API tests
- [ ] Error handling tested
- [ ] Idempotent operations tested
- [ ] All API tests passing
- [ ] Integration tests with database

---

### Issue P7-22: Implement UI Tests for Playbook Features
**Labels:** `component:testing`, `phase:7`, `priority:medium`
**Description:**
- Write UI tests (or integration tests) for playbook features:
  - Recommended Playbook panel display
  - Playbook recalculation flow
  - Step completion flow
  - Playbook events in timeline
- Test user interactions and state updates
- Test error states and loading states
- Reference: docs/phase7-playbooks-mvp.md Section 9 (Exit Criteria - Tests)

**Dependencies:** P7-15, P7-16, P7-17, P7-18

**Acceptance Criteria:**
- [ ] UI tests for playbook features implemented
- [ ] User interactions tested
- [ ] State updates verified
- [ ] Error and loading states tested
- [ ] All UI tests passing
- [ ] Integration tests verify end-to-end flow

---

### Issue P7-23: Implement End-to-End Playbook Flow Test
**Labels:** `component:testing`, `phase:7`, `priority:high`
**Description:**
- Write end-to-end test for complete playbook flow:
  1. Create exception
  2. TriageAgent suggests playbook
  3. PolicyAgent assigns playbook
  4. Playbook displayed in UI
  5. User completes steps via UI
  6. Playbook completion verified
  7. Events logged correctly
- Verify playbook state throughout lifecycle
- Verify event timeline completeness
- Reference: docs/phase7-playbooks-mvp.md Section 9 (Exit Criteria - Tests)

**Dependencies:** P7-11, P7-12, P7-15, P7-17

**Acceptance Criteria:**
- [ ] End-to-end playbook flow test implemented
- [ ] Complete lifecycle tested
- [ ] Playbook state verified at each stage
- [ ] Event timeline completeness verified
- [ ] Test passes consistently
- [ ] Test documented

---

## Component: Documentation

### Issue P7-24: Create Playbook Configuration Documentation
**Labels:** `component:documentation`, `phase:7`, `priority:high`
**Description:**
- Create documentation for playbook configuration:
  - Playbook schema and structure
  - Condition syntax and examples
  - Step types and action parameters
  - Template placeholder syntax
  - Playbook versioning
- Include examples for different domains
- Document playbook creation and management
- Reference: docs/phase7-playbooks-mvp.md Section 3 (Core Concepts)

**Dependencies:** P7-1, P7-2, P7-4

**Acceptance Criteria:**
- [ ] Playbook configuration documentation created
- [ ] Schema and structure documented
- [ ] Condition syntax documented with examples
- [ ] Step types and parameters documented
- [ ] Template placeholder syntax documented
- [ ] Examples for different domains included
- [ ] Playbook management documented

---

### Issue P7-25: Create Playbook API Documentation
**Labels:** `component:documentation`, `phase:7`, `priority:medium`
**Description:**
- Create API documentation for playbook endpoints:
  - `POST /api/exceptions/{id}/playbook/recalculate`
  - `GET /api/exceptions/{id}/playbook`
  - `POST /api/exceptions/{id}/playbook/steps/{step_order}/complete`
- Document request/response schemas
- Document error responses
- Include usage examples
- Reference: docs/phase7-playbooks-mvp.md Section 5.3 (APIs)

**Dependencies:** P7-8, P7-9, P7-10

**Acceptance Criteria:**
- [ ] Playbook API documentation created
- [ ] Request/response schemas documented
- [ ] Error responses documented
- [ ] Usage examples included
- [ ] API documentation integrated into main docs

---

### Issue P7-26: Update Architecture Documentation for Playbooks
**Labels:** `component:documentation`, `phase:7`, `priority:medium`
**Description:**
- Update main architecture documentation to reflect playbook engine
- Document playbook matching flow
- Document playbook execution flow
- Update data flow diagrams to include playbooks
- Document agent integration with playbooks
- Reference: docs/phase7-playbooks-mvp.md Section 5 (Backend Changes), Section 7 (Agent Integration)

**Dependencies:** P7-1, P7-3, P7-11, P7-12

**Acceptance Criteria:**
- [ ] Architecture documentation updated
- [ ] Playbook matching flow documented
- [ ] Playbook execution flow documented
- [ ] Data flow diagrams updated
- [ ] Agent integration documented
- [ ] Phase 7 status mentioned in main README

---

## Summary

**Total Issues:** 26
**High Priority:** 16
**Medium Priority:** 7
**Low Priority:** 3

**Components Covered:**
- Playbook Matching Service (2 issues)
- Playbook Execution Service (3 issues)
- Playbook Repository Enhancements (2 issues)
- Playbook APIs (3 issues)
- Agent Integration (4 issues)
- UI Integration (4 issues)
- Testing (5 issues)
- Documentation (3 issues)

**Phase 7 Actions & Playbooks MVP Milestones (from docs/phase7-playbooks-mvp.md):**
- Playbook Engine (matching exceptions to playbooks)
- Configuration-driven playbook model (DB/JSON, no hard-coded domain logic)
- Basic step types (notify, assign_owner, set_status, add_comment, call_tool)
- Exception-level playbook state (current_playbook_id, current_step)
- Human-in-the-loop execution (safe actions only)
- UI integration (Recommended Playbook panel, step completion)

**Key Phase 7 Playbooks Focus Areas:**
1. **Playbook Matching**: Configuration-driven matching based on tenant, domain, exception type, severity, SLA, policy tags
2. **Playbook Execution**: Step-by-step execution with human-in-the-loop approvals for risky actions
3. **Playbook State**: Exception-level state tracking (current_playbook_id, current_step) with event log
4. **Action Executors**: Safe action execution for MVP step types (notify, assign_owner, set_status, add_comment, call_tool)
5. **API Integration**: Playbook recalculation, status retrieval, and step completion endpoints
6. **Agent Integration**: Agents suggest and align with playbooks, but do not bypass human approvals
7. **UI Integration**: Recommended Playbook panel with step display, recalculation, and completion actions
8. **Testing**: Comprehensive tests for matching, execution, APIs, UI, and end-to-end flow
9. **Documentation**: Playbook configuration, API, and architecture documentation

**Spec References:**
- docs/phase7-playbooks-mvp.md - Phase 7 Actions & Playbooks MVP specification
- docs/01-architecture.md - Overall architecture document
- docs/03-data-models-apis.md - Backend API schemas and data models
- docs/06-mvp-plan.md - MVP milestones and implementation order
- docs/phase6-persistence-mvp.md - Phase 6 Persistence & State MVP (prerequisite)

