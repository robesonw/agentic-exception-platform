# End-to-End Architecture Document

## High-Level Architecture
The Domain-Abstracted Agentic AI Platform is designed as a modular, scalable, and secure system for handling enterprise exception processing across multiple tenants and domains. At its core, the platform employs a multi-agent orchestration model that processes exceptions through a pipeline of specialized agents: IntakeAgent, TriageAgent, PolicyAgent, ResolutionAgent, and FeedbackAgent, with an optional SupervisorAgent for oversight. The architecture ensures domain abstraction by loading configurations dynamically from Domain Packs and Tenant Policy Packs, allowing plug-and-play adaptability without code changes.

Key principles:
- **Domain Abstraction**: No hardcoding of domain-specific logic; all ontology, rules, playbooks, and tools are loaded from configurable packs.
- **Multi-Tenancy**: Strict isolation of data, memory, tools, and configurations per tenant to ensure compliance and security.
- **Agentic Orchestration**: Agents communicate via standardized contracts, with decisions audited and explainable.
- **Safety-First**: Guardrails, allow-lists, and human-in-loop mechanisms prevent unauthorized actions.
- **Observability**: Integrated logging, metrics, and dashboards for real-time monitoring.

The system supports batch and streaming ingestion, resolution via registered tools, and continuous learning from feedback.

## Component Diagrams (Text-Based)
### Overall System Diagram

[External Sources: Logs, DBs, APIs, Queues, Files] --> [Gateway / Tenant Router]
--> [Exception Ingestion Service] --> [Agent Orchestrator]
Agent Orchestrator orchestrates:

IntakeAgent
TriageAgent --> PolicyAgent --> ResolutionAgent --> FeedbackAgent
(Optional: SupervisorAgent oversees all)
Supporting Layers:
Skill/Tool Registry (per-tenant)
Memory Layer (per-tenant RAG index)
LLM Routing Layer (Phase 5: domain/tenant-aware provider selection)
Playbook Matching Service (Phase 7: condition-based playbook selection)
Playbook Execution Service (Phase 7: step-by-step execution)
Audit & Observability System
Admin UI / API
Output: Resolved Exceptions, Dashboards, Audit Trails, Playbook Execution Events


### Agent Orchestration Workflow Diagram

Exception --> IntakeAgent (Normalize)
--> TriageAgent (Classify, Score, Diagnose, Suggest Playbook [Phase 7])
--> PolicyAgent (Enforce Rules, Approve Actions, Assign Playbook [Phase 7])
--> ResolutionAgent (Align Plan with Playbook Steps [Phase 7])
--> FeedbackAgent (Capture Outcomes, Compute Playbook Metrics [Phase 7], Update Memory)
Loop: If escalation needed --> Human Approval or SupervisorAgent

### Playbook Flow Diagram (Phase 7)

```
Playbook Matching Flow:
  Exception → TriageAgent
    → PlaybookMatchingService.match_playbook()
      → Evaluate conditions (domain, type, severity, SLA, tags)
      → Rank by priority
      → Return best match
    → Store suggested_playbook_id in context

Playbook Assignment Flow:
  Exception + Suggested Playbook → PolicyAgent
    → Validate against approved playbooks
    → If approved:
        → Set exception.current_playbook_id
        → Set exception.current_step = 1
        → Emit PlaybookAssigned event

Playbook Execution Flow:
  Exception with Assigned Playbook → ResolutionAgent
    → Load playbook and steps
    → Align resolution plan with steps
    → Prepare action plan (does not execute in MVP)
  
  Manual Step Completion (via API):
    → PlaybookExecutionService.complete_step()
      → Execute step action (notify, assign_owner, etc.)
      → Resolve placeholders
      → Emit PlaybookStepCompleted event
      → Update exception.current_step
      → If all steps done: Emit PlaybookCompleted event

Playbook Metrics Flow:
  Exception Resolved → FeedbackAgent
    → Compute playbook metrics:
        - total_steps
        - completed_steps
        - duration
        - last_actor
    → Emit FeedbackCaptured event with metrics
```


## Deployment Modes
- **Central SaaS**: Hosted in a cloud environment (e.g., AWS, Azure) with multi-tenant isolation via namespaces, VPCs, or containers. All tenants share infrastructure but with logical separation. Suitable for enterprises managing many clients remotely.
- **Edge Runner (On-Prem)**: Deployed directly in the client's environment using containerized setups (e.g., Docker/Kubernetes). Each tenant runs an isolated instance, syncing configurations from a central repo. Ideal for regulated industries requiring data sovereignty.
- **Hybrid**: Combines SaaS for orchestration and on-prem for sensitive data processing. Exceptions are routed to edge nodes for resolution, with aggregated metrics sent to central observability. Supports federation for cross-tenant insights without data leakage.

## Multi-Tenant Isolation Model
- **Data Isolation**: Separate databases or schemas per tenant (e.g., PostgreSQL with row-level security). Exceptions and memory stores are partitioned by tenantId.
- **Configuration Isolation**: Domain Packs and Tenant Policy Packs are loaded into tenant-specific caches.
- **Tool Isolation**: Tools are registered per tenant with allow-lists; execution sandboxes prevent cross-tenant access.
- **Memory Isolation**: Per-tenant RAG indexes (e.g., using VectorDB like Pinecone) ensure no knowledge leakage.
- **Access Controls**: RBAC enforced via JWT or API keys, with tenant-scoped sessions.

## Agent Orchestration Workflow
1. **Intake**: Route exception to tenant-specific pipeline; normalize to canonical schema.
2. **Triage**: Classify and prioritize based on Domain Pack taxonomy and severity rules. **Phase 7**: Suggests playbooks via Playbook Matching Service.
3. **Policy Check**: Evaluate against Tenant Policy Pack guardrails; gate high-severity actions. **Phase 7**: Approves and assigns playbooks to exceptions.
4. **Resolution**: Select and execute approved playbooks/tools; audit all steps. **Phase 7**: Aligns resolution plan with assigned playbook steps.
5. **Feedback**: Log outcomes; update RAG and playbooks if patterns detected. **Phase 7**: Computes playbook execution metrics (steps completed, duration, success rate).
6. **Escalation/Loop**: If confidence low or policy blocks, escalate to human or SupervisorAgent.

This workflow is event-driven, using message queues (e.g., Kafka) for asynchronous processing.

### Data Flow References

For detailed data flow diagrams and component interactions, see:
- [`docs/Arch-Diagram.md`](./Arch-Diagram.md) - System component diagram with playbook services
- [`docs/phase7-playbooks-mvp.md`](./phase7-playbooks-mvp.md) - Detailed playbook implementation and flows
- [`docs/playbooks-api.md`](./playbooks-api.md) - API endpoints and request/response flows

## Playbook Matching & Execution Flow (Phase 7)

### Playbook Matching Service

The **Playbook Matching Service** evaluates playbook conditions against exception attributes to select the most appropriate playbook for an exception.

**Matching Process:**
1. Load candidate playbooks for the tenant from the database
2. Extract exception attributes (domain, exception_type, severity, SLA deadline, policy_tags)
3. Evaluate playbook conditions (domain match, exception_type match, severity_in, sla_minutes_remaining_lt, policy_tags)
4. Rank matching playbooks by priority (higher priority = better match)
5. Select best matching playbook (highest priority, newest if priority equal)

**Agent Integration Points:**
- **TriageAgent**: Calls matching service to suggest playbooks during classification. Result stored in context as `suggested_playbook_id` and `playbook_reasoning`.
- **PolicyAgent**: Receives playbook suggestion from TriageAgent context, validates against approved playbooks, and assigns approved playbook to exception (`exception.current_playbook_id`, `exception.current_step = 1`).
- **API Endpoint**: `POST /exceptions/{tenant_id}/{exception_id}/playbook/recalculate` allows manual recalculation and assignment update.

### Playbook Execution Service

The **Playbook Execution Service** manages step-by-step execution of playbook steps, with support for human-in-the-loop completion.

**Execution Process:**
1. Load playbook and ordered steps from database
2. Validate step exists and is valid for completion
3. Execute step action (if applicable): `notify`, `assign_owner`, `set_status`, `add_comment`, `call_tool`
4. Resolve placeholders in step parameters using exception context
5. Emit `PlaybookStepCompleted` event
6. Update `exception.current_step` to next step
7. If all steps completed, emit `PlaybookCompleted` event

**Agent Integration Points:**
- **ResolutionAgent**: Reads assigned playbook from exception, aligns resolution plan with playbook steps, and prepares action plan. Does not execute steps in MVP (execution is manual via API).
- **FeedbackAgent**: After exception resolution, computes playbook metrics (total_steps, completed_steps, duration, last_actor) and includes in `FeedbackCaptured` event payload.
- **API Endpoint**: `POST /exceptions/{tenant_id}/{exception_id}/playbook/steps/{step_order}/complete` allows manual step completion with actor tracking.

### Playbook Status Derivation

Playbook step status is derived from exception events, not stored directly in the database:

**Status Logic:**
- **"completed"**: Step has `PlaybookStepCompleted` event, OR `PlaybookCompleted` event exists (all steps completed), OR step order < `current_step`
- **"pending"**: Step has no completion events and is at or after `current_step`
- **"skipped"**: Reserved for future use (not implemented in MVP)

**API Endpoint**: `GET /exceptions/{tenant_id}/{exception_id}/playbook` queries events and derives status dynamically.

### Data Flow: Playbook Lifecycle

```
Exception Created
  ↓
TriageAgent (suggests playbook via matching service)
  ↓
PolicyAgent (approves & assigns playbook to exception)
  ↓
PlaybookAssigned event emitted
  ↓
ResolutionAgent (aligns plan with playbook steps)
  ↓
[Manual Step Completion via API]
  ↓
PlaybookStepCompleted event emitted
  ↓
exception.current_step updated
  ↓
[Repeat for each step]
  ↓
All steps completed → PlaybookCompleted event emitted
  ↓
FeedbackAgent (computes metrics)
  ↓
FeedbackCaptured event with playbook metrics
```

### Agent-Playbook Interaction Summary

| Agent | Phase | Interaction | Outcome |
|-------|-------|-------------|---------|
| **TriageAgent** | 7 | Calls `PlaybookMatchingService.match_playbook()` | Suggests playbook, stores `suggested_playbook_id` in context |
| **PolicyAgent** | 7 | Validates suggestion, assigns approved playbook | Sets `exception.current_playbook_id` and `exception.current_step = 1`, emits `PlaybookAssigned` event |
| **ResolutionAgent** | 7 | Reads assigned playbook, aligns resolution plan | Creates resolution plan matching playbook steps (does not execute) |
| **FeedbackAgent** | 7 | Computes playbook execution metrics | Emits `FeedbackCaptured` event with metrics (steps, duration, success) |

### Playbook Events

The following events are emitted during playbook lifecycle:
- `PlaybookAssigned`: When PolicyAgent assigns playbook (or API recalculation changes assignment)
- `PlaybookRecalculated`: When API endpoint recalculates and updates assignment
- `PlaybookStarted`: When first step begins execution (future use)
- `PlaybookStepCompleted`: When a step is completed (via API or execution service)
- `PlaybookCompleted`: When all steps in a playbook are completed
- `FeedbackCaptured`: Includes playbook metrics when exception is resolved


