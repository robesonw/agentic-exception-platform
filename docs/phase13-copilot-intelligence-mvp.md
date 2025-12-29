Phase 13 — Copilot Intelligence MVP (Enterprise-Grade)

1. Purpose

Upgrade the SentinAI Copilot from basic summaries to an enterprise “read-mostly” operational assistant that:

answers with evidence (RAG)

produces actionable playbook guidance

respects tenant isolation

supports approval workflow for any optional actions

supports multi-domain packs (finance/healthcare/etc.)

2. Scope

In scope

RAG indexing pipeline (policies, playbooks, SOP docs, past resolved exceptions)

Copilot query router (intent detection: summary, explain, find similar, recommend playbook, draft response)

Evidence-first responses (citations to internal docs/exceptions)

“Explainability panel” in UI (why classification, why playbook, retrieved sources)

Conversation memory per session (scoped to tenant + user)

Safety constraints for actions (“read-only by default”)

Out of scope

full autonomous remediation without approval

marketplace knowledge packs

advanced fine-tuning

3. Key User Journeys

Summarize today’s exceptions

grouped by severity/domain/type

highlights SLA breaches and rising clusters

Explain why this exception was classified this way

show top features/rules + model confidence

show evidence retrieved (policy doc snippets, similar cases)

Find similar exceptions

returns top N similar with outcomes

recommended next steps/playbook based on similarity

Recommend playbook

selects best match from active playbooks

explains match logic

provides step-by-step operator guide

Draft operator response

produces email/chat template with placeholders

strictly read-only (no sending)

4. Architecture
   4.1 Retrieval Sources (“Knowledge Collections”)

PolicyDocs (SOPs, policy packs, playbook docs)

ResolvedExceptions (final state, resolution notes)

AuditEvents (why changes happened)

ToolRegistry (capabilities, not secrets)

4.2 Indexing

Background jobs:

index policy docs on import/activation

index resolved exceptions daily/hourly

index playbook metadata on activation

Storage:

vector DB (start simple: Postgres pgvector or SQLite FAISS for dev)

metadata tables keyed by tenant/domain/version

4.3 Copilot Request Flow

UI → /copilot/chat

intent detection

retrieval plan

fetch evidence

prompt assembly with citations

LLM response

structured response output

5. Backend APIs (MVP)

POST /copilot/chat

POST /copilot/sessions (create)

GET /copilot/sessions/{id}

POST /copilot/index/rebuild (admin only)

GET /copilot/evidence/{request_id} (debug/admin)

GET /copilot/similar/{exception_id}

6. Response Contract (structured)

Copilot must return structured sections:

{
"answer": "...",
"bullets": ["..."],
"citations": [
{ "source_type": "policy_doc", "source_id": "SOP-FIN-001", "title": "...", "snippet": "...", "url": null },
{ "source_type": "exception", "source_id": "EX-2024-1120", "title": "Resolved case", "snippet": "...", "url": "/exceptions/EX-2024-1120" }
],
"recommended_playbook": {
"playbook_id": "PB-FIN-001",
"confidence": 0.92,
"steps": [{ "step": 1, "text": "..." }]
},
"safety": {
"mode": "READ_ONLY",
"actions_allowed": []
}
}

7. UI Enhancements

Copilot chat supports:

citations panel (expandable)

“Show similar cases”

“Apply playbook guidance” (read-only checklist)

“Copy operator response”

Exception Detail page:

“Ask Copilot about this exception” shortcut

evidence + reasoning tab

Section 7A — Playbook Workflow Viewer (Read-Only, MVP)

Objective:
Provide a visual, explainable representation of playbooks and their execution state to operators, supervisors, and Copilot—without introducing editable workflows yet.

7A.1 Purpose

The Playbook Workflow Viewer allows users to:

visually understand how an exception will be resolved

see which step is current, completed, failed, or skipped

understand why a playbook was recommended

correlate agent actions and human approvals to workflow steps

This significantly improves:

explainability

trust in automation

demo clarity for enterprise buyers

7A.2 Scope (MVP)

Included

Read-only workflow diagram rendering

Step status overlay (runtime execution)

Integration with Exception Detail and Copilot

Excluded (Future Phase)

Drag/drop editing

Creating or modifying playbooks via UI

Conditional logic editing

7A.3 Data Source & Model
Source of Truth

Playbook definitions from Domain Pack / Tenant Pack

Execution events from runtime pipeline (ResolutionAgent / FeedbackAgent)

Canonical Playbook Graph Model

Backend or shared library maps playbook JSON → graph:

{
"playbook_id": "PB-FIN-001",
"name": "Handle Settlement Failure",
"nodes": [
{
"id": "step-1",
"type": "agent",
"label": "Classify Failure",
"agent": "TriageAgent"
},
{
"id": "step-2",
"type": "decision",
"label": "Severity > HIGH?"
},
{
"id": "step-3",
"type": "human",
"label": "Supervisor Approval"
},
{
"id": "step-4",
"type": "system",
"label": "Trigger Settlement Correction"
}
],
"edges": [
{ "from": "step-1", "to": "step-2" },
{ "from": "step-2", "to": "step-3", "condition": "true" },
{ "from": "step-2", "to": "step-4", "condition": "false" }
]
}

7A.4 Execution Overlay Model

At runtime, workflow steps are decorated with execution metadata:

{
"step_id": "step-3",
"status": "PENDING | IN_PROGRESS | COMPLETED | FAILED | SKIPPED",
"started_at": "...",
"completed_at": "...",
"actor": "AI_AGENT | HUMAN | SYSTEM",
"notes": "Awaiting supervisor approval"
}

7A.5 Backend APIs (Optional, Lightweight)

If needed for UI decoupling:

GET /playbooks/{playbook_id}/graph
GET /exceptions/{exception_id}/playbook-execution

Note: These APIs may simply adapt existing pack + execution data—no new persistence required.

7A.6 UI Implementation
Technology

React Flow (preferred) or equivalent graph library

Placement

Exception Detail Page

New tab: “Workflow”

Shows:

playbook diagram

current step highlighted

step-by-step execution state

Copilot Integration

Copilot responses may include:

“View workflow” action

“Highlight current step” shortcut

“Explain why this step is next”

7A.7 Visual Conventions
Step Type Icon Color
Agent 🤖 Blue
Human 👤 Purple
Decision 🔀 Orange
System ⚙️ Gray
Status Indicator
Pending Hollow circle
In Progress Pulsing
Completed Green check
Failed Red cross
Skipped Dashed
7A.8 Copilot Enhancements (Tie-In)

Copilot can now answer:

“Show me the workflow for this exception”

“Which step is blocking resolution?”

“Why is human approval required here?”

“What happens if this step fails?”

Copilot responses must:

reference workflow step IDs

cite playbook definition + execution state

remain read-only

7A.9 Security & Governance

Workflow viewer is read-only

Visible to:

operators (execution view)

supervisors (full context)

admins (definition + history)

All workflow state transitions are auditable (Phase 12/10)

7A.10 Acceptance Criteria

Phase 13 workflow viewer is complete when:

A playbook renders as a graph

Execution status overlays update live or on refresh

Copilot can reference workflow steps

No playbook editing is possible via UI

Viewer works for both Finance and Healthcare packs

8. RBAC & Safety

Copilot always tenant-scoped

Read-only by default

Any “action suggestion” must go through:

config governance approval OR

explicit operator confirmation workflow

9. Testing

Unit tests:

intent router

retrieval filtering by tenant/domain

response schema validation

Integration tests:

index build → query returns citations

Security tests:

ensure no cross-tenant retrieval

10. Acceptance Criteria

Phase 13 is complete when:

Copilot answers include citations from stored knowledge

Similar cases query works and is tenant-scoped

Copilot recommends playbooks with explainability

UI shows citations & evidence cleanly

All responses follow structured schema

Indexing runs and can rebuild from Admin
