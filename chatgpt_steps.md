started with below while pointing to 06-doc:
Read docs/06-mvp-plan.md and create a Phase 1 MVP task checklist as GitHub issues, grouped by component
=> that created the .gitbuh - issues


👉 Run Cursor Prompt #1 — Create Project Skeleton
Then:
👉 Prompt #2 — Canonical Models
👉 Prompt #3 — Domain Pack Loader
👉 Prompt #4 — TenantPolicy Loader
👉 Prompt #5 — Tool Registry



Cursor Prompt #1 — Create Python Project Skeleton

We are starting Phase 1 MVP implementation in Python.

Follow the architecture rules and constraints in:
- docs/master_project_instruction_full.md
- docs/01-architecture.md
- docs/06-mvp-plan.md

Use FastAPI + pydantic v2.

Create the full project skeleton with these folders:
- src/api
- src/models
- src/domainpack
- src/tenantpack
- src/tools
- src/agents
- src/orchestrator
- src/audit
- tests

Add:
- requirements.txt
- pyproject.toml
- README.md (with run instructions)

Do NOT add any domain-specific logic.
Only structural scaffolding.

This implements Phase 1: foundational scaffolding,
corresponding broadly to Issues #3, #5, #6, #11 (structural prep),
but do NOT implement business logic yet.


❗ Why this step first?

Because:

Models depend on nothing

Packs depend on models

Tools depend on packs

Agents depend on tools + packs

Orchestrator depends on agents

This is the correct architectural dependency tree.




NEXT STEP (Step 2):
Implement Canonical Schemas (Models)

Use this prompt next:

Cursor Prompt #2 — Implement Canonical Schemas

Implement canonical schemas per:
- docs/03-data-models-apis.md
- docs/master_project_instruction_full.md

Create in src/models:
- exception_record.py (ExceptionRecord)
- domain_pack.py (DomainPack)
- tenant_policy.py (TenantPolicyPack)
- agent_contracts.py (AgentMessage, AgentDecision)

Use pydantic v2.
Ensure strict validation, type safety, and
.data / .model_validate_json helpers.

Add unit tests in tests/test_models.py.

This maps to issues:
- Issue 3 (canonical schema normalization foundation)
- Issue 6 (agent contracts foundation)
- Issue 5 indirectly (orchestrator needs these)




NEXT STEP (Step 3):
Implement Domain Pack Loader
Cursor Prompt #3 — Domain Pack Loader

Implement DomainPack loader and validator.

Spec references:
- docs/05-domain-pack-schema.md
- docs/master_project_instruction_full.md

Create src/domainpack/loader.py with:
- load_domain_pack(path: str) -> DomainPack
- validate_domain_pack(pack: DomainPack)
- DomainPackRegistry (in-memory registry by domainName/version)

Validation rules:
- exceptionTypes must exist
- playbooks must reference valid exceptionTypes
- tools in playbooks must exist in domainPack.tools

Add tests in tests/test_domainpack_loader.py
using:
- domainpacks/finance.sample.json
- domainpacks/healthcare.sample.json

Corresponds to Phase 1 Issues:
- Issue 3 (normalization base)
- Issue 7 (intake agent needs domain pack)
- Issue 8 (triage agent uses classification)




NEXT STEP (Step 4):
Tenant Policy Pack Loader

Use this prompt:

Cursor Prompt #4 — Tenant Policy Loader

Implement TenantPolicyPack loader and validator.

Spec references:
- docs/03-data-models-apis.md
- docs/master_project_instruction_full.md

Create src/tenantpack/loader.py:
- load_tenant_policy(path: str) -> TenantPolicyPack
- validate_tenant_policy(policy, domainPack)
- TenantPolicyRegistry

Validation:
- approvedBusinessProcesses must match domain pack playbook IDs
- toolsAllowList must match domain pack tools
- guardrailOverrides must align with domain guardrails

Add tests in tests/test_tenantpack_loader.py

Maps to issues:
- Issue 9 (policy agent needs these)
- Issue 11 (tool registry relies on policy allowlists)





NEXT STEP (Step 5):
Implement Tool Registry
Cursor Prompt #5 — Tool Registry


Implement a typed Tool Registry with allow-list enforcement.

Spec refs:
- docs/master_project_instruction_full.md
- docs/02-modules-components.md

Create:
src/tools/registry.py with:
- ToolDefinition class
- ToolRegistry register/get/list/validate
- AllowListEnforcer(policyPack) to prevent forbidden tool access

Add tests in tests/test_tool_registry.py.

Maps to Phase 1 issues:
- Issue 11 (tool registry CRUD)
- Issue 12 (invocation interface preparation)
- Required for ResolutionAgent (Issue 10)




After Step 5…

You will have:

✔ Schemas
✔ Domain + tenant packs load/validate
✔ Tool registry
✔ Project structure
✔ Tests

Now you can safely move to:

Agents → Orchestrator → Ingestion → API → RAG → Metrics

in that order.






Next 5 Cursor Prompts (Prompts 6–10)

⭐ Prompt 6 — Implement Audit Logging System

Maps to issues:

Audit & Observability System (Issue group: 3 issues)

Tool call auditing (Issue 11 from Tool Registry tasks)

Paste this into Cursor:

Implement the Audit Logging system.

Spec references:
- docs/master_project_instruction_full.md (audit requirements)
- docs/08-security-compliance.md
- phase1-mvp-issues.md (Audit & Observability issues)

Create `src/audit/logger.py` with:

Classes & Functions:
- AuditLogger(run_id: str)
  - log_agent_event(agent_name, input, output)
  - log_tool_call(tool_name, args, result)
  - log_decision(stage, decision_json)
  - flush()

Storage:
- Write each event as a JSON line into:
  ./runtime/audit/{run_id}.jsonl

Rules:
- Every agent MUST log input and output
- Every tool invocation must be logged
- Logs must contain timestamps, run_id, tenant_id

Add tests:
- tests/test_audit_logger.py
- Validate file created, JSON lines valid, logs contain required fields

Acceptance Criteria:
- Satisfies Audit issues in phase1-mvp-issues.md
- Matches audit behavior in master_project_instruction_full.md



⭐ Prompt 7 — Implement IntakeAgent (MVP version)

Maps to issues:

IntakeAgent (1 issue)

Exception Ingestion Service (corresponding issues)

Paste this into Cursor:

Implement IntakeAgent (MVP version).

Spec references:
- docs/04-agent-templates.md (IntakeAgent template)
- docs/master_project_instruction_full.md
- phase1-mvp-issues.md (IntakeAgent + Exception Ingestion issues)

Location:
  src/agents/intake.py

Responsibilities:
- Normalize raw exception into ExceptionRecord model
- Validate domainPack.exceptionTypes contains the given exceptionType
- Assign initial metadata: timestamp, tenantId, pipelineId
- Produce structured AgentDecision containing:
  - normalized exception
  - validation results
  - next stage = "triage"

Constraints:
- No domain-specific logic
- All behavior must be based on canonical ExceptionRecord schema
- Log via AuditLogger

Add tests:
- tests/test_intake.py
- Use sample finance + healthcare exceptions


⭐ Prompt 8 — Implement TriageAgent

Maps to issues:

TriageAgent issue

Classification issues

Severity rules

Paste this into Cursor:

Implement TriageAgent.

Spec references:
- docs/04-agent-templates.md (TriageAgent)
- docs/05-domain-pack-schema.md (exceptionTypes, severityRules)
- docs/master_project_instruction_full.md
- phase1-mvp-issues.md (TriageAgent issue)

Location:
  src/agents/triage.py

Responsibilities:
- Read normalized ExceptionRecord
- Classify exceptionType → severity using domainPack.severityRules
- Select severity = highest matching rule OR defaultSeverity
- Produce AgentDecision with:
  classification
  severity
  next stage = "policy"

Rules:
- No domain-specific heuristics
- Use ONLY what domain pack provides
- Log triage decision with AuditLogger

Add tests:
  tests/test_triage.py
  - Finance sample (e.g., POSITION_BREAK -> CRITICAL)
  - Healthcare sample (e.g., PHARMACY_DUPLICATE_THERAPY -> CRITICAL)

⭐ Prompt 9 — Implement PolicyAgent

Maps to issues:

PolicyAgent issue

Guardrail enforcement

Allowed playbooks

CRITICAL no-auto-action rules

Paste into Cursor:

Implement PolicyAgent.

Spec references:
- docs/04-agent-templates.md (PolicyAgent)
- docs/03-data-models-apis.md (policy & guardrails)
- docs/master_project_instruction_full.md
- phase1-mvp-issues.md (PolicyAgent issue)

Location:
  src/agents/policy.py

Responsibilities:
- Apply tenant policies and guardrails:
  * approvedBusinessProcesses
  * severityOverrides
  * noAutoActionIfSeverityIn
  * requireHumanApprovalFor
  * maxAutoRetries
  * escalateIfConfidenceBelow

- Decide:
  * Is this exception actionable?
  * Is the playbook allowed?
  * Is human approval required?

Output:
- AgentDecision with:
  - actionability classification:
      ACTIONABLE_APPROVED_PROCESS
      ACTIONABLE_NON_APPROVED_PROCESS
      NON_ACTIONABLE_INFO_ONLY
  - selectedPlaybookId if allowed
  - flags: humanApprovalRequired
  - next stage = "resolution"

Rules:
- Never approve a playbook not in tenant.approvedBusinessProcesses
- Never auto-execute CRITICAL unless tenant overrides

Add tests:
  tests/test_policy.py



⭐ Prompt 10 — Implement ResolutionAgent (MVP)

Maps to issues:

ResolutionAgent issue

Playbook execution path

Tool allow-list enforcement

Paste this into Cursor:

Implement ResolutionAgent (MVP version).

Spec references:
- docs/04-agent-templates.md (ResolutionAgent)
- docs/05-domain-pack-schema.md (playbooks)
- docs/master_project_instruction_full.md
- phase1-mvp-issues.md (ResolutionAgent + tool invocation issues)

Location:
  src/agents/resolution.py

Responsibilities:
- If PolicyAgent marked actionable + approved:
    * Load the selected playbook
    * Resolve each step into a structured action plan
    * DO NOT execute tools yet in MVP
    * Validate each referenced tool exists in domainPack.tools
    * Validate tool is allow-listed for this tenant

- If non-approved but actionable:
    * Generate a suggestedDraftPlaybook structure

- Output AgentDecision with:
    - resolvedPlan (list of structured actions)
    - suggestedDraftPlaybook (if applicable)
    - next stage = "feedback"

Rules:
- No tool execution, only planning
- Full validation of references
- Log decisions with AuditLogger

Add tests:
  tests/test_resolution.py


🎯 What You’ll Have After These 5 Prompts

After Prompt 6–10, your MVP will have:

✔ A working audit system
✔ Intake → Triage → Policy → Resolution agents
✔ Cross-domain domain pack support
✔ Tool registry + allow-list integration
✔ Full validation logic
✔ Logging + structured agent decisions
✔ All agent-level unit tests


You’ve already done:

1–5 (scaffold, models, pack loaders, tool registry)

6–10 (audit + Intake/Triage/Policy/Resolution agents)

So next we finish the pipeline + thin APIs + MVP memory/obs..





Cursor Prompt 11 — Implement FeedbackAgent (MVP placeholder)

Maps to issues:

FeedbackAgent isn’t explicitly listed as its own issue, but it’s required by Issue 5 Orchestrator pipeline and master spec.

Paste into Cursor:

Implement FeedbackAgent (MVP placeholder).

Spec references:
- docs/04-agent-templates.md (FeedbackAgent)
- docs/master_project_instruction_full.md
- phase1-mvp-issues.md (Orchestrator requires Feedback stage)

Location:
  src/agents/feedback.py

Responsibilities:
- Accept ResolutionAgent output
- Append outcome placeholder fields:
    * resolutionStatus
    * feedbackCapturedAt
    * learningArtifacts (empty list for MVP)
- Produce AgentDecision with:
    - decision = "FEEDBACK_CAPTURED"
    - confidence = 1.0
    - evidence includes final resolution summary
    - nextStep = "complete"
- Log input/output via AuditLogger

Constraints:
- No learning automation in Phase 1
- Must remain domain-agnostic

Add tests:
  tests/test_feedback_agent.py
  - Use a mocked ResolutionAgent output to verify schema correctness and audit logging.


Cursor Prompt 12 — Implement Orchestrator Pipeline Runner

Maps to issues:

Issue 5: Agent Orchestrator with Pipeline Coordination (high)

Issue 6: Agent Communication Contracts (medium)

Paste into Cursor:


Implement the Orchestrator pipeline runner.

Spec references:
- docs/01-architecture.md (pipeline flow)
- docs/02-modules-components.md
- docs/master_project_instruction_full.md
- phase1-mvp-issues.md (Issues 5 and 6)

Location:
  src/orchestrator/runner.py

Responsibilities:
- run_pipeline(domain_pack, tenant_policy, exceptions_batch) -> dict
- Execute agents in strict order per exception:
    IntakeAgent -> TriageAgent -> PolicyAgent -> ResolutionAgent -> FeedbackAgent
- Maintain per-exception context object:
    * normalized exception
    * classification + severity
    * policy decision
    * resolution plan
    * feedback outcome
    * evidence list
- On any agent failure:
    * capture error in evidence
    * mark resolutionStatus = ESCALATED
- Write audit entries for each stage

Output:
- Return final JSON output matching master spec schema:
  { tenantId, runId, results:[...] }

Add tests:
- tests/test_orchestrator_runner.py
- Integration-style test that loads:
    domainpacks/finance.sample.json
    tenantpacks/tenant_finance.sample.json
  and processes 2-3 sample exceptions end-to-end.



Cursor Prompt 13 — Implement Exception Ingestion + Run API

Maps to issues:

Issue 3: Exception Ingestion Service normalization (high)

Issue 4: REST ingestion endpoint POST /exceptions/{tenantId} (high)

Also supports your MVP “/run” orchestration surface.

Paste into Cursor:

Implement Exception Ingestion API + Run endpoint.

Spec references:
- docs/03-data-models-apis.md
- docs/master_project_instruction_full.md
- phase1-mvp-issues.md (Issues 3 and 4)

Location:
  src/api/app.py (FastAPI app)
  src/api/exceptions.py (router)
  src/api/run.py (router)

Endpoints:
1) POST /exceptions/{tenantId}
   - Accept raw exception payload (list or single)
   - Normalize via IntakeAgent into ExceptionRecord
   - Return exceptionId(s)

2) POST /run
   Body:
     {
       "domainPackPath": "...",
       "tenantPolicyPath": "...",
       "exceptions": [ ...raw exceptions... ]
     }
   - Load packs via loaders
   - Call run_pipeline(...)
   - Return pipeline output JSON

Constraints:
- No auth in MVP (gateway issues deferred)
- Validate request bodies with pydantic models
- Log ingestion events

Add tests:
- tests/test_api_exceptions.py
- tests/test_api_run.py
  using FastAPI TestClient.


Cursor Prompt 14 — Implement Per-Tenant RAG Memory (MVP Stub)

Maps to issues:

Issue 13: Per-Tenant RAG index setup (high)

Issue 14: RAG query interface (medium)

Paste into Cursor:


Implement MVP Memory/RAG layer with per-tenant isolation.

Spec references:
- docs/master_project_instruction_full.md (memory layer rules)
- docs/02-modules-components.md
- phase1-mvp-issues.md (Issues 13 and 14)

If src/memory/ does not exist, create it.

Location:
  src/memory/index.py
  src/memory/rag.py

Responsibilities:
- MemoryIndexRegistry:
    * get_or_create_index(tenant_id)
    * add_exception(tenant_id, exception_record, resolution_summary)
    * search_similar(tenant_id, exception_record, k=5)

Implementation:
- MVP can use in-memory list + cosine similarity stub OR FAISS if available.
- Provide an EmbeddingProvider interface with a dummy embedding implementation for Phase 1.

Integration:
- TriageAgent should call search_similar(...) if available, but handle empty index gracefully.

Add tests:
- tests/test_memory_rag.py
  - verify tenant isolation (tenantA results never include tenantB data)
  - verify search returns ranked items.


Cursor Prompt 15 — Implement Basic Observability + Metrics Endpoint

Maps to issues:

Issue 16: Structured logs + metrics (medium)

Issue 19: Metrics API endpoint GET /metrics/{tenantId} (medium)
(Issue 17 dashboard is low priority, skip for now unless you want it.)

Paste into Cursor:


Implement basic observability (structured logs + metrics) and expose metrics API.

Spec refs:
- docs/master_project_instruction_full.md (success metrics)
- docs/07-test-plan.md (observability validation)
- phase1-mvp-issues.md (Issue 16 and Issue 19)

Location:
  src/observability/metrics.py   (create folder if missing)
  src/api/metrics.py            (FastAPI router)

Metrics to track per tenant:
- exceptionCount
- autoResolutionRate
- mttrSeconds (MVP approximate)
- actionableApprovedCount
- actionableNonApprovedCount
- nonActionableCount

Requirements:
- MetricsCollector class updated by Orchestrator after each run
- Tenant-scoped isolation
- Expose GET /metrics/{tenantId} returning JSON metrics

Add tests:
- tests/test_metrics_collector.py
- tests/test_api_metrics.py


After Prompts 11–15 you’ll have:

✅ Full agent chain (incl. Feedback)
✅ Orchestrator running end-to-end
✅ /exceptions ingestion + /run pipeline API
✅ Per-tenant memory/RAG stub
✅ Metrics collection + /metrics endpoint
✅ Integration tests





Absolutely — here are Prompts 16–20, copy-paste ready, using your Option-A filenames and mapped to the remaining Phase-1 issues in your checklist.

They align to the open/high-value items left in phase1-mvp-issues.md:

Issue 18 Status API 

phase1-mvp-issues

Issue 12 Tool Invocation Interface 

phase1-mvp-issues

Issues 1 & 2 Tenant Router + Auth 

phase1-mvp-issues

Issue 20 End-to-End Pipeline Test 

phase1-mvp-issues

Issue 21 Unit Tests + Coverage 

phase1-mvp-issues

(We’re intentionally skipping the low-priority dashboard for now — Issue 17. 

phase1-mvp-issues

)


Cursor Prompt 16 — Implement Status API Endpoint (GET /exceptions/{tenantId}/{exceptionId})

Maps to: Issue 18 

phase1-mvp-issues

Paste into Cursor:

Implement Status API endpoint.

Spec refs:
- docs/03-data-models-apis.md
- docs/master_project_instruction_full.md
- phase1-mvp-issues.md Issue 18 (Status API)

Location:
  src/api/status.py (new FastAPI router)
  src/api/app.py (include router)

Endpoint:
  GET /exceptions/{tenantId}/{exceptionId}

Behavior:
- Retrieve the latest ExceptionRecord + pipeline result for that tenant/exceptionId.
- Include current resolutionStatus and the audit trail in response.
- If not found, return 404 with structured error.

Storage for MVP:
- Use an in-memory ExceptionStore updated by Orchestrator after /run.
- Add ExceptionStore in src/orchestrator/store.py or src/models/store.py.

Tests:
- tests/test_api_status.py using FastAPI TestClient.
- Verify:
   * successful fetch returns canonical exception schema + audit trail
   * tenant isolation (cannot read another tenant’s exception)
   * 404 for missing id

Acceptance criteria must match Issue 18.



Cursor Prompt 17 — Implement Tool Invocation Interface (stubbed HTTP)

Maps to: Issue 12 

phase1-mvp-issues

Paste into Cursor:


Implement Tool Invocation Interface (MVP stub).

Spec refs:
- docs/master_project_instruction_full.md (tool safety)
- docs/02-modules-components.md
- phase1-mvp-issues.md Issue 12

Location:
  src/tools/invoker.py (new)
  src/tools/registry.py (wire in)

Responsibilities:
- ToolInvoker class that can invoke allow-listed tools.
- MVP supports HTTP tools only (no gRPC yet):
    invoke(tool_name: str, args: dict, tenant_policy, domain_pack) -> dict

Rules:
- Validate tool exists in DomainPack.tools
- Enforce tenant allow-list via AllowListEnforcer
- Perform HTTP call using requests or httpx
- Sandbox behavior for MVP:
    * allow "dry_run=True" to skip real call and return mock response
- Always audit log:
    * tool name
    * args
    * response / error

Integration:
- Update ResolutionAgent to optionally execute tools ONLY when:
    * policy approved
    * not CRITICAL
    * humanApprovalRequired == false
  Keep default = dry_run for MVP.

Tests:
- tests/test_tool_invoker.py
- Mock HTTP responses.
- Verify allow-list blocks forbidden tools.
- Verify audit logged.

Acceptance criteria must match Issue 12.


Cursor Prompt 18 — Implement Tenant Router + Authentication Middleware

Maps to: Issues 1 & 2 

phase1-mvp-issues

Paste into Cursor:

Implement Tenant Router + Authentication for FastAPI.

Spec refs:
- docs/master_project_instruction_full.md (tenant isolation + auth)
- docs/08-security-compliance.md
- phase1-mvp-issues.md Issues 1 and 2

Location:
  src/api/auth.py (new)
  src/api/middleware.py (new)
  src/api/app.py (wire middleware)

Requirements:
1) Authentication:
- Support API Key auth for MVP.
- Read header: "X-API-KEY"
- Map API keys to tenantId using a simple in-memory dict in auth.py.
- If missing/invalid -> 401.
- Securely log auth failures.

2) Tenant Router:
- Middleware extracts tenantId from auth context.
- Attach tenantId to request.state.tenant_id.
- Ensure /exceptions/{tenantId} and /run use request tenantId and reject mismatch.
- Add simple per-tenant rate limiting stub (counter per minute).

No JWT in MVP yet, but design should allow later extension.

Tests:
- tests/test_auth_and_router.py
- Verify:
   * API key yields correct tenantId
   * invalid key rejected
   * mismatch between path tenantId and auth tenantId -> 403
   * tenant isolation verified

Acceptance criteria must match Issues 1 & 2.




Cursor Prompt 19 — Implement End-to-End Pipeline Test Suite

Maps to: Issue 20 

phase1-mvp-issues

Paste into Cursor:

Implement Phase 1 End-to-End Pipeline tests.

Spec refs:
- docs/07-test-plan.md
- docs/master_project_instruction_full.md
- phase1-mvp-issues.md Issue 20

Location:
  tests/test_e2e_pipeline.py

Requirements:
- Load finance domain + tenant packs from:
    domainpacks/finance.sample.json
    tenantpacks/tenant_finance.sample.json
- Run full pipeline:
    Intake → Triage → Policy → Resolution → Feedback
- Use a small batch (3–5) of realistic finance exceptions.
- Assert:
    * pipeline completes
    * results JSON matches canonical schema
    * at least 80% of test exceptions classified as ACTIONABLE_APPROVED_PROCESS 
      (adjust fixture to satisfy rate)
    * audit trail has entries for every agent stage
    * no forbidden tools executed (dry_run)

Document test rationale in comments.

Acceptance criteria must match Issue 20.


Cursor Prompt 20 — Harden Unit Tests + Add Coverage Report

Maps to: Issue 21 

phase1-mvp-issues

Paste into Cursor:


Finalize Phase 1 testing & coverage.

Spec refs:
- docs/07-test-plan.md
- docs/master_project_instruction_full.md
- phase1-mvp-issues.md Issue 21

Tasks:
1) Review all Phase 1 modules and ensure unit tests exist:
   - models
   - domainpack loader
   - tenantpack loader
   - tool registry + invoker
   - audit logger
   - all agents
   - orchestrator
   - APIs (exceptions/run/status/metrics)
   - memory/RAG

2) Add missing unit tests to reach >80% coverage.

3) Add tenant isolation tests where missing.

4) Mock external dependencies consistently:
   - embedding provider
   - HTTP tools
   - LLM placeholders

5) Add coverage tooling:
   - update requirements.txt to include pytest-cov
   - add a Makefile or script in scripts/run_tests.sh:
       pytest --cov=src --cov-report=term-missing --cov-report=html

Tests:
- Ensure all tests pass in CI/local.

Acceptance criteria must match Issue 21.
