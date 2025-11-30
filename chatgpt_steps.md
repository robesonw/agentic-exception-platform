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





Recommended Cursor Prompt for Phase 2 Task Checklist

Paste this exact prompt into Cursor:

Read docs/06-mvp-plan.md and identify all requirements that belong to Phase 2 (beyond the Phase 1 MVP implementation that is already completed). 

Using the same formatting style as phase1-mvp-issues.md, generate a new file in the repo:

  .github/ISSUE_TEMPLATE/phase2-mvp-issues.md

This file must contain:
- A full Phase 2 task breakdown
- Grouped by functional areas
- Each with (#) identifiers like in Phase 1
- Clear acceptance criteria
- Direct references to the relevant sections in docs/06-mvp-plan.md
- DO NOT duplicate Phase 1 tasks
- DO NOT modify phase1-mvp-issues.md

Phase 2 should include:
- Advanced RAG (vector DB, embedding provider, semantic search)
- Tool execution engine (real execution, retries, error handling)
- Policy learning improvements
- Human-in-the-loop approval workflow
- Playbook generation/optimization via LLM
- Multi-agent orchestration
- Rich metrics + dashboards
- Notification service (email/Slack)
- Optional gateway/auth hardening
- Partial automation for resolution actions

Generate the file .github/ISSUE_TEMPLATE/phase2-mvp-issues.md with a complete and clean Phase 2 checklist.





Phase 2 — Next 10 Cursor Coding Prompts (21–30)


Prompt 21 — Upgrade Domain Pack Loader + Hot Reload (Phase 2)

Maps to: Issue 22 (high) 

phase2-mvp-issues

Paste into Cursor:

Phase 2 implementation: Upgrade Domain Pack Loader + Validator with hot reloading.

Spec refs:
- docs/05-domain-pack-schema.md
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 22

Tasks:
1) Enhance src/domainpack/loader.py to support BOTH JSON and YAML packs.
   - Add load_domain_pack(path) that infers parser by extension.
2) Add schema validation improvements:
   - validate ontology, entities, exception taxonomy, severity rules, tools, playbooks, guardrails.
3) Implement hot-reloading:
   - Watch domainpacks/ folder for changes (use watchdog).
   - On change, reload pack into registry with version bump.
4) Enforce tenant-scoped isolation:
   - DomainPackRegistry should store packs per tenant namespace.
   - No cross-tenant access to packs.

Tests:
- tests/test_domainpack_hot_reload.py
- Verify JSON + YAML load.
- Verify reload replaces pack.
- Verify tenant isolation.

Acceptance criteria must satisfy Issue 22.

⭐ Prompt 22 — Domain Pack Storage + Caching + Version Rollback

Maps to: Issue 23 (medium) 

phase2-mvp-issues

Paste into Cursor:

Phase 2 implementation: Domain Pack persistent storage + caching + versioning.

Spec refs:
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 23

Tasks:
1) Create src/domainpack/storage.py:
   - store_pack(tenant_id, pack)
   - get_pack(tenant_id, domain_name, version=None)
   - list_versions(tenant_id, domain_name)
   - rollback_version(tenant_id, domain_name, target_version)

2) MVP storage:
   - filesystem under ./runtime/domainpacks/{tenantId}/{domainName}/{version}.json

3) Add caching:
   - simple LRU cache per tenant for active packs.

4) Add usage tracking:
   - store last_used_timestamp and usage_count per pack.

Tests:
- tests/test_domainpack_storage.py
- Verify store/retrieve/version list/rollback.
- Verify cache hit behavior.
- Verify tenant segregation.

Acceptance criteria must satisfy Issue 23.

⭐ Prompt 23 — Extend Tool Registry for Domain Tools + Overrides

Maps to: Issue 24 (high) 

phase2-mvp-issues

Paste into Cursor:

Phase 2 implementation: Extend Tool Registry for Domain Tools.

Spec refs:
- docs/master_project_instruction_full.md
- docs/02-modules-components.md
- phase2-mvp-issues.md Issue 24

Tasks:
1) Update src/tools/registry.py:
   - Load tool definitions from DomainPack.tools on pack registration.
   - Namespace tools by tenant + domain:
       {tenantId}:{domainName}:{toolName}

2) Implement inheritance/override:
   - TenantPolicyPack.toolsAllowList may override tool properties (timeouts, retries).
   - Domain tool definitions remain canonical unless overridden.

3) Implement tool version compatibility checks:
   - Each tool definition may declare version.
   - Registry rejects incompatible versions for tenant.

Tests:
- tests/test_tool_registry_domain_tools.py
- Verify domain tools load into registry.
- Verify overrides applied.
- Verify namespacing + isolation.

Acceptance criteria must satisfy Issue 24.

⭐ Prompt 24 — Advanced Tool Execution Engine (Retries, Timeout, Circuit Breaker)

Maps to: Issue 25 (high) 

phase2-mvp-issues

Paste into Cursor:

Phase 2 implementation: Advanced Tool Execution Engine.

Spec refs:
- docs/master_project_instruction_full.md
- docs/08-security-compliance.md
- phase2-mvp-issues.md Issue 25

Tasks:
1) Create src/tools/execution_engine.py with ToolExecutionEngine:
   - execute(tool_name, args, tenant_policy, domain_pack, mode="sync"|"async")
   - retry with exponential backoff
   - timeout handling per tool definition
   - circuit breaker per tool (open/half-open/closed)
   - validate tool output schema when argsSchema/returns present

2) Support async execution:
   - use asyncio + httpx.

3) Update src/tools/invoker.py to delegate to ToolExecutionEngine.

4) Audit every attempt/outcome.

Tests:
- tests/test_tool_execution_engine.py
- Mock failures to verify retry/backoff.
- Mock timeout behavior.
- Verify circuit breaker trips after threshold.
- Verify async path.

Acceptance criteria must satisfy Issue 25.

⭐ Prompt 25 — Domain-Specific Playbook Management + Selection

Maps to: Issue 26 (high) 

phase2-mvp-issues

Paste into Cursor:

Phase 2 implementation: Domain-specific Playbook support.

Spec refs:
- docs/master_project_instruction_full.md
- docs/05-domain-pack-schema.md
- phase2-mvp-issues.md Issue 26

Tasks:
1) Create src/playbooks/manager.py:
   - load_playbooks(domain_pack)
   - select_playbook(exception_record, tenant_policy, domain_pack)
   - support inheritance/composition (simple merge rules MVP)
   - versioning hooks (read from domain pack versions)

2) Integrate with ResolutionAgent:
   - ResolutionAgent uses PlaybookManager for selection instead of manual lookup.

3) Enforce tenant isolation of playbooks.

Tests:
- tests/test_playbook_manager.py
- Verify selection by exceptionType.
- Verify only approved playbooks chosen.
- Verify tenant isolation.

Acceptance criteria must satisfy Issue 26.

⭐ Prompt 26 — Partial Automation of Resolution Actions

Maps to: Issue 36 (high) 

phase2-mvp-issues

Paste into Cursor:

Phase 2 implementation: Partial automation for resolution actions.

Spec refs:
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 36

Tasks:
1) Upgrade src/agents/resolution.py:
   - If PolicyAgent allows auto-action AND severity not CRITICAL:
       execute playbook steps using ToolExecutionEngine.
   - Respect confidence thresholds from tenant policy.
   - If any step fails:
       attempt rollback if rollback tool is defined OR escalate.

2) Add per-step execution status:
   - SUCCESS | FAILED | SKIPPED | NEEDS_APPROVAL

3) Always audit each executed step.

Tests:
- tests/test_resolution_partial_automation.py
- Mock tool execution success/failure.
- Verify rollback/escalation path.
- Verify CRITICAL never auto-executes.

Acceptance criteria must satisfy Issue 36.

⭐ Prompt 27 — Embedding Provider Integration (multi-provider + caching)

Maps to: Issue 29 (high) 

phase2-mvp-issues

Paste into Cursor:

Phase 2 implementation: Embedding Provider Integration.

Spec refs:
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 29

Tasks:
1) Create src/memory/embeddings.py:
   - EmbeddingProvider interface
   - OpenAIEmbeddingProvider (config driven)
   - HFEmbeddingProvider stub (optional)
   - EmbeddingCache (LRU + disk optional)

2) Tenant customization:
   - TenantPolicyPack may specify embedding provider/model.

3) Quality metrics:
   - log embedding latency, cache hit rate.

Tests:
- tests/test_embeddings.py
- Mock providers.
- Verify caching works.
- Verify tenant-specific provider config.

Acceptance criteria must satisfy Issue 29.

⭐ Prompt 28 — Vector DB Integration (Qdrant/Pinecone/Weaviate adapter)

Maps to: Issue 28 (high) 

phase2-mvp-issues

Paste into Cursor:

Phase 2 implementation: Production Vector DB integration.

Spec refs:
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 28

Tasks:
1) Create src/memory/vector_store.py:
   - VectorStore interface
   - QdrantVectorStore implementation (default)
   - connection pooling + retry
   - per-tenant namespace/collection

2) Migrate Phase 1 MemoryIndexRegistry:
   - replace in-memory storage with VectorStore.
   - keep a fallback mode for local tests.

3) Backup/recovery stubs:
   - export_collection(tenant_id)
   - restore_collection(tenant_id)

Tests:
- tests/test_vector_store_qdrant.py
- Use mocked Qdrant client.
- Verify per-tenant isolation & persistence calls.

Acceptance criteria must satisfy Issue 28.

⭐ Prompt 29 — Advanced Semantic Search (Hybrid + re-ranking)

Maps to: Issue 30 (medium) 

phase2-mvp-issues

Paste into Cursor:

Phase 2 implementation: Advanced Semantic Search (hybrid).

Spec refs:
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 30

Tasks:
1) Upgrade src/memory/rag.py:
   - hybrid_search(exception_record, k=5, filters=None)
      * vector search via VectorStore
      * keyword match against stored metadata
      * merge + rerank results

2) Add:
   - filtering by exceptionType, severity, domainName
   - relevance scores + explanation

3) Integrate into TriageAgent:
   - include top similar cases as evidence.

Tests:
- tests/test_semantic_search_hybrid.py
- Verify hybrid search merges correctly.
- Verify filters work.
- Verify explanations returned.

Acceptance criteria must satisfy Issue 30.

⭐ Prompt 30 — Human Approval Workflow + Approval Queue API

Maps to: Issue 31 (high) 

phase2-mvp-issues

Paste into Cursor:

Phase 2 implementation: Human-in-the-loop Approval Workflow.

Spec refs:
- docs/master_project_instruction_full.md
- docs/08-security-compliance.md
- phase2-mvp-issues.md Issue 31

Tasks:
1) Create src/workflow/approval.py:
   - ApprovalQueue (per tenant)
   - submit_for_approval(exceptionId, plan, evidence)
   - approve(approvalId, user, comments)
   - reject(approvalId, user, comments)
   - timeout + escalation
   - approval history persisted in ./runtime/approvals/{tenantId}.jsonl

2) Integrate into PolicyAgent & ResolutionAgent:
   - If humanApprovalRequired:
       ResolutionAgent submits plan to queue and halts execution.
   - Orchestrator marks status = PENDING_APPROVAL.

3) Add API:
   - POST /approvals/{tenantId}
   - GET /approvals/{tenantId}
   - POST /approvals/{tenantId}/{approvalId}/approve
   - POST /approvals/{tenantId}/{approvalId}/reject

Tests:
- tests/test_approval_workflow.py
- tests/test_api_approvals.py
- Verify queue behavior, timeout/escalation, audit trail.

Acceptance criteria must satisfy Issue 31.

What’s covered vs Phase-2 issues

These 10 prompts implement the core Phase-2 “engine upgrades”:

Domain pack hot reload + persistence (22–23)

Domain tools + advanced execution engine (24–25)

Playbook manager + partial automation (26, 36)

Embeddings + Vector DB + hybrid search (29, 28, 30)

Human approvals (31)

That’s the meat of Phase 2. Admin UI, dashboards, supervisor agent, policy learning, notifications, multi-domain testing come next once these are stable. 

phase2-mvp-issues





Phase 2 — Remaining Cursor Coding Prompts (31–46)
⭐ Prompt 31 — LLM-Based Playbook Generation + Optimization

Maps to: Issue 27

Paste into Cursor:

Phase 2: Implement LLM-Based Playbook Generation and Optimization.

Spec refs:
- docs/master_project_instruction_full.md
- docs/04-agent-templates.md
- phase2-mvp-issues.md Issue 27

Tasks:
1) Create src/llm/provider.py:
   - LLMProvider interface
   - GrokProvider/OpenAIProvider stubs (config-driven)
   - safe_generate(prompt, schema) enforcing JSON-only output

2) Create src/playbooks/generator.py:
   - generate_playbook(exception_record, evidence, domain_pack)
   - output must conform to DomainPack.playbooks schema
   - tag generated playbooks as approved=false

3) Integrate into ResolutionAgent:
   - If PolicyAgent classifies ACTIONABLE_NON_APPROVED_PROCESS:
        call PlaybookGenerator and attach suggestedDraftPlaybook.

4) Add playbook optimization:
   - optimize_playbook(playbook, past_outcomes) -> improved draft
   - use tenant memory / outcomes as evidence

Safety:
- enforce output JSON schema validation
- never auto-approve LLM-generated playbooks

Tests:
- tests/test_playbook_generator_llm.py
- mock LLMProvider to return valid/invalid JSON
- verify schema validation blocks invalid output

⭐ Prompt 32 — Advanced Multi-Agent Orchestration (parallel + supervisor hooks)

Maps to: Issue 33

Paste into Cursor:

Phase 2: Implement Advanced Multi-Agent Orchestration.

Spec refs:
- docs/01-architecture.md
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 33

Tasks:
1) Upgrade src/orchestrator/runner.py:
   - support parallel execution across exceptions using asyncio.gather
   - support timeouts per stage
   - persist per-exception state snapshots

2) Add orchestration hooks:
   - before_stage(agent_name, context)
   - after_stage(agent_name, decision)
   - on_failure(agent_name, error)

3) Allow branching:
   - if PolicyAgent returns PENDING_APPROVAL → stop pipeline for that exception
   - if non-actionable → skip ResolutionAgent and go to FeedbackAgent

4) Maintain deterministic order within each exception.

Tests:
- tests/test_orchestrator_parallel.py
- verify parallel batch execution produces same per-item decisions
- verify branching behavior

⭐ Prompt 33 — SupervisorAgent for Oversight

Maps to: Issue 34

Paste into Cursor:

Phase 2: Implement SupervisorAgent.

Spec refs:
- docs/04-agent-templates.md
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 34

Tasks:
1) Create src/agents/supervisor.py:
   - Runs after PolicyAgent and after ResolutionAgent
   - Reviews decisions for safety/consistency
   - Can override nextStep to "ESCALATE" if confidence too low / policy breach

2) Integrate into Orchestrator hooks:
   - call SupervisorAgent on checkpoints:
       * post-policy
       * post-resolution
   - SupervisorAgent output appended to evidence

Rules:
- never executes tools, only governs flow
- uses tenant guardrails + domain pack rules

Tests:
- tests/test_supervisor_agent.py
- verify overrides trigger escalation

⭐ Prompt 34 — Policy Learning + Improvement Loop

Maps to: Issue 35

Paste into Cursor:

Phase 2: Implement Policy Learning and Improvement.

Spec refs:
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 35

Tasks:
1) Create src/learning/policy_learning.py:
   - ingest_feedback(exceptionId, outcome, human_override)
   - detect recurring exceptions & success/failure patterns
   - suggest policy updates (not auto-applied)

2) Store learning artifacts per tenant:
   ./runtime/learning/{tenantId}.jsonl

3) Integrate with FeedbackAgent:
   - if human override exists, log it for learning
   - attach policySuggestions list in feedback output

Safety:
- suggestions only, never auto-edit tenant policies

Tests:
- tests/test_policy_learning.py

⭐ Prompt 35 — Approval UI Backend + Minimal Dashboard API

Maps to: Issue 32

Paste into Cursor:

Phase 2: Implement Approval UI backend + minimal dashboard API.

Spec refs:
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 32

Tasks:
1) Create src/api/approval_ui.py:
   - GET /ui/approvals/{tenantId}
     returns pending approvals with evidence + plan

2) Create src/api/ui_status.py:
   - GET /ui/exceptions/{tenantId}
     returns recent exceptions with statuses

3) Keep output UI-friendly but derived from canonical schemas.

Tests:
- tests/test_api_ui_approvals.py
- tests/test_api_ui_status.py

⭐ Prompt 36 — Admin API/UI: Domain Pack Management

Maps to: Issue 37

Paste into Cursor:

Phase 2: Implement Admin APIs for Domain Pack Management.

Spec refs:
- docs/03-data-models-apis.md
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 37

Tasks:
1) Create src/api/admin_domainpacks.py:
   - POST /admin/domainpacks/{tenantId}
      upload pack (JSON/YAML), validate, store, register
   - GET /admin/domainpacks/{tenantId}
      list domain packs + versions + usage stats
   - POST /admin/domainpacks/{tenantId}/rollback
      rollback active version

2) Wire into FastAPI app.

Tests:
- tests/test_api_admin_domainpacks.py

⭐ Prompt 37 — Admin API/UI: Tenant Policy Pack Management

Maps to: Issue 38

Paste into Cursor:

Phase 2: Implement Admin APIs for Tenant Policy Pack Management.

Spec refs:
- docs/03-data-models-apis.md
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 38

Tasks:
1) Create src/api/admin_tenantpolicies.py:
   - POST /admin/tenantpolicies/{tenantId}
     upload policy pack, validate against active domain pack
   - GET /admin/tenantpolicies/{tenantId}
     return active policy + history
   - POST /admin/tenantpolicies/{tenantId}/activate
     activate a version

Tests:
- tests/test_api_admin_tenantpolicies.py

⭐ Prompt 38 — Admin API/UI: Tool Management

Maps to: Issue 39

Paste into Cursor:

Phase 2: Implement Admin APIs for Tool Management.

Spec refs:
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 39

Tasks:
1) Create src/api/admin_tools.py:
   - POST /admin/tools/{tenantId}/{domainName}
     register/override tool definitions
   - GET /admin/tools/{tenantId}/{domainName}
     list tools + allowlist status
   - POST /admin/tools/{tenantId}/{domainName}/disable
     disable a tool

2) Integrate with ToolRegistry + AllowListEnforcer.

Tests:
- tests/test_api_admin_tools.py

⭐ Prompt 39 — Rich Metrics Collector (expanded)

Maps to: Issue 40

Paste into Cursor:

Phase 2: Implement Rich Metrics Collection.

Spec refs:
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 40

Tasks:
1) Upgrade src/observability/metrics.py:
   - per-playbook success rates
   - per-tool latency, retry counts, failure rates
   - approval queue aging
   - recurrence stats by exceptionType
   - confidence distribution

2) Persist metrics periodically:
   ./runtime/metrics/{tenantId}.json

Tests:
- tests/test_metrics_rich.py

⭐ Prompt 40 — Advanced Dashboards Backend APIs

Maps to: Issue 41

Paste into Cursor:

Phase 2: Implement Advanced Dashboard APIs (backend only).

Spec refs:
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 41

Tasks:
1) Create src/api/dashboards.py:
   - GET /dashboards/{tenantId}/summary
   - GET /dashboards/{tenantId}/exceptions
   - GET /dashboards/{tenantId}/playbooks
   - GET /dashboards/{tenantId}/tools

2) Outputs derived from RichMetricsCollector + ExceptionStore.

Tests:
- tests/test_api_dashboards.py

⭐ Prompt 41 — Notification Service (Email + Webhook)

Maps to: Issue 42

Paste into Cursor:

Phase 2: Implement Notification Service.

Spec refs:
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 42

Tasks:
1) Create src/notify/service.py:
   - NotificationService with channels:
       * email (SMTP config)
       * webhook (Teams/Slack)
   - send_notification(tenant_id, group, subject, message, payload_link)

2) Integrate into Orchestrator:
   - notify on escalation
   - notify on approval required
   - notify on auto-resolution complete

3) TenantPolicyPack.notificationPolicies drives routing.

Tests:
- tests/test_notification_service.py
- mock SMTP + webhook

⭐ Prompt 42 — Alert Rules + Escalation Automation

Maps to: Issue 43

Paste into Cursor:

Phase 2: Implement Alert Rules and Escalation.

Spec refs:
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 43

Tasks:
1) Create src/observability/alerts.py:
   - define alert rules per tenant:
       * high exception volume
       * repeated CRITICAL breaks
       * tool circuit breaker open
       * approval queue aging
   - evaluate_alerts(metrics, tenant_policy)

2) On trigger:
   - openCase/escalateCase via ToolExecutionEngine
   - send notification

Tests:
- tests/test_alert_rules.py

⭐ Prompt 43 — Gateway/Auth Hardening (Optional)

Maps to: Issue 44 (optional)

Paste into Cursor:

Phase 2 (Optional): Gateway/Auth hardening.

Spec refs:
- docs/08-security-compliance.md
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 44

Tasks:
1) Upgrade src/api/auth.py:
   - support JWT auth in addition to API key
   - tenantId from JWT claims
   - RBAC roles: viewer, operator, admin

2) Add rate limiting real implementation (slowapi or custom).

Tests:
- tests/test_auth_jwt.py

⭐ Prompt 44 — Multi-Domain Simulation + Load Testing Harness

Maps to: Issue 45

Paste into Cursor:

Phase 2: Implement Multi-Domain Simulation and Testing Harness.

Spec refs:
- docs/07-test-plan.md
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 45

Tasks:
1) Create src/simulation/runner.py:
   - load multiple domain packs
   - generate synthetic exception batches
   - run through orchestrator
   - collect performance metrics

2) Provide CLI:
   python -m src.simulation.runner --domains finance,healthcare --batch 1000

Tests:
- tests/test_simulation_runner.py (small batch)

⭐ Prompt 45 — Domain Pack Test Suite Execution Engine

Maps to: Issue 46

Paste into Cursor:

Phase 2: Implement Domain Pack Test Suite Execution.

Spec refs:
- docs/05-domain-pack-schema.md (testSuites)
- docs/master_project_instruction_full.md
- phase2-mvp-issues.md Issue 46

Tasks:
1) Create src/domainpack/test_runner.py:
   - run_test_suites(domain_pack, tenant_policy, orchestrator)
   - validate expectedPlaybookId for each case
   - output pass/fail report

2) Expose API:
   POST /admin/domainpacks/{tenantId}/{domainName}/run-tests

Tests:
- tests/test_domainpack_test_runner.py

⭐ Prompt 46 — Phase-2 Final Regression + Coverage Gate

Maps to: “final hardening” implied in Phase-2 issues

Paste into Cursor:

Phase 2: Final regression hardening.

Spec refs:
- docs/07-test-plan.md
- docs/master_project_instruction_full.md

Tasks:
1) Add missing unit/integration tests for Phase 2 modules:
   - playbook generator
   - execution engine
   - approvals
   - admin APIs
   - notifications
   - alerts
   - simulation + test runner

2) Ensure tenant isolation tests cover:
   - vector store collections
   - domain packs storage
   - approval queues
   - notifications routing

3) Upgrade scripts/run_tests.sh:
   pytest --cov=src --cov-report=term-missing --cov-report=html
   enforce >85% coverage

4) Run multi-domain simulation with small batch in CI.

Deliver:
- stable Phase 2 MVP
















-------overall so far : 

PHASE 2 — What You Achieved

Phase 1 gave you the basic skeleton of a multi-tenant agentic exception engine:

5 core agents

deterministic classification & decision flow

domain packs & tenant policies

tool registry

audit logging

ingestion + pipeline APIs

simple RAG memory

tests + observability

Phase 2 evolves the system into a true, scalable, intelligent, partially-autonomous agentic platform.

Below is the full story of what Phase 2 added.

🔥 1. Domain Pack Evolution & Governance

Phase 2 transforms Domain Packs from static configuration files into a dynamic, versioned, reloadable knowledge layer, similar to how modern enterprise systems treat domain ontologies.

You added:
✔ JSON + YAML domain packs
✔ Deep validation of domain taxonomy
✔ Hot reloading via file watchers
✔ Persistent storage & version control (rollback)
✔ Per-tenant isolation
✔ Domain tool definitions & overrides

Why this matters:
Now your system can support continuous domain changes (new exception types, new playbooks, new tools) without needing code changes.
This is a huge enterprise requirement.

🔥 2. Tool Execution Engine (Real Automation Infrastructure)

Phase 1 tool usage was “dry-run.”
Phase 2 introduces real execution with control-plane protections.

You added:
✔ Execution Engine

Sync + async

Retries + exponential backoff

Timeouts

Circuit breakers

Output schema validation

Tool namespacing by tenant + domain

✔ ToolInvoker now orchestrates real workflows
✔ Full auditing for every tool call

Why this matters:
Your platform can now actually perform actions, not just suggest them — still within a safe envelope.

🔥 3. Advanced Playbook Management

Phase 1: resolution was static, read-only.
Phase 2: playbooks become intelligent, evolvable, and multi-version.

You added:
✔ PlaybookManager

selection rules

inheritance

composition

versioning

✔ Integration with ResolutionAgent
✔ Partial automation of playbook steps
✔ Rollback logic
✔ Per-step execution states

Why this matters:
Playbooks are now treated as operational runbooks — not static text — enabling precise automation.

🔥 4. Embeddings + Vector Database + Hybrid Semantic Search

Phase 1 had a simple in-memory RAG.

Phase 2 adds the real AI-powered knowledge layer:

✔ Multi-provider Embedding Provider

(OpenAI, HF, etc.)

✔ Embedding caching
✔ Vector DB integration (Qdrant/Pinecone/Weaviate)
✔ Per-tenant vector namespaces
✔ Hybrid search:

semantic vector search

keyword search

confidence scoring

reranking

filtering by exceptionType/severity/domain

✔ TriageAgent enhanced with semantic evidence

Why this matters:
Your agentic decisions now leverage historical similarity — a core feature of real agentic systems.

🔥 5. Multi-Agent Orchestration

Phase 2 introduces more autonomy and intelligence across multiple agents.

✔ Parallel pipeline execution (async)
✔ Branching logic (approval, non-actionable, escalations)
✔ SupervisorAgent (checks & overrides)
✔ Orchestrator hooks before/after each agent
✔ Per-exception state snapshots

Why this matters:
Your system now behaves like a swarm of cooperating agents, not a linear pipeline.

🔥 6. Human Approval Workflow

This is enterprise-grade human-in-the-loop handling.

✔ ApprovalQueue per tenant
✔ Approval submission & history
✔ Timeout & escalation rules
✔ REST APIs for approving/rejecting
✔ SupervisorAgent + PolicyAgent integration

Why this matters:
Human governance is mandatory for compliance-heavy industries like finance & healthcare.

🔥 7. Policy Learning Engine

You added a feedback loop to continuously improve tenant policies.

✔ Learning artifacts recorded
✔ Pattern detection & analysis
✔ Suggestions for policy updates (not auto-applied)
✔ Integration with FeedbackAgent

Why this matters:
Your system now learns from operations and proposes optimizations.

This is the first step toward self-tuning agentic behavior.

🔥 8. Admin APIs (Domain, Tenant, Tools)

Phase 2 added full administrative control:

✔ Upload domain packs
✔ Upload tenant policy packs
✔ Activate versions
✔ List & audit versions
✔ Rollback
✔ Tool registration / override / disable
✔ Tenant isolation for all admin actions

Why this matters:
Your platform is now manageable by operators without code changes.

🔥 9. Expanded Observability + Notifications + Alerts

You enhanced observability far beyond Phase 1:

✔ Rich metrics:

playbook success

tool latency

retries & failures

recurrence patterns

approval queue aging

confidence distributions

✔ Dashboard APIs
✔ Notification service (email + webhooks)
✔ Alert rules system

(detect anomalies, open cases, escalate)

Why this matters:
Your system is now monitorable, proactive, and enterprise-ready.

🔥 10. Simulation & Test Suite Execution

You added tooling for domain testing & load simulation:

✔ Multi-domain simulation runner
✔ Synthetic exception generation
✔ Playbook test suite executor
✔ CI-level regression runner

Why this matters:
Allows you to validate domain packs & policies before going to production.

⭐ Summary of What Phase 2 Achieved
🎯 Major Achievements

The platform evolved from a deterministic rules engine → a semi-autonomous agentic AI system

Real automation capabilities (tool execution)

Domain & tenant governance elevated to enterprise-grade

RAG became real semantic search

Human approval workflows added

Observability & notifications added

Multi-agent orchestration upgraded

Policy learning introduced

🎯 Phase 2 transformed your system from a “smart orchestrator” → into a “true enterprise AI agent platform.”
🎯 Phase 3 will make it fully autonomous, LLM-driven, self-improving, and capable of end-to-end execution.
















phase 3:


Read the following project specs and existing MVP phases:

- docs/master_project_instruction_full.md
- docs/01-architecture.md ... docs/09-tenant-onboarding.md
- docs/06-mvp-plan.md
- .github/ISSUE_TEMPLATE/phase1-mvp-issues.md
- .github/ISSUE_TEMPLATE/phase2-mvp-issues.md

Your task:
Create a **Phase 3 MVP issues file** that extends Phase 1 + Phase 2, without duplicating them.

Create a new file:

  .github/ISSUE_TEMPLATE/phase3-mvp-issues.md

### Phase 3 – Overall Goals

Derive details from the documents, but Phase 3 should explicitly focus on:

1) **LLM-Enhanced Agent Reasoning**
   - LLM-augmented agents (Triage, Policy, Resolution, Supervisor) with explainable reasoning
   - Natural language explanation of decisions for operators
   - Safe, JSON-bounded outputs with schema validation
   - Fallback strategies if LLMs fail or time out

2) **Autonomous Optimization & Continuous Learning**
   - Stronger policy learning loop (suggested policy/playbook changes based on outcomes)
   - Automatic recommendation of:
     * new severity rules
     * new or updated playbooks
     * guardrail adjustments
   - Human-in-the-loop approval for any changes
   - Metrics-driven optimization (success rates, MTTR, false positives/negatives)

3) **Full UX & Workflow Layer**
   - Rich operator UI backend support (APIs) for:
     * browsing exceptions, decisions, evidence, and audit history
     * interacting with agents in natural language (“Why did you do this?”)
     * trigger re-runs or “what-if” simulations on selected exceptions
   - Supervisor dashboards (cross-tenant / cross-domain view, if allowed by design)
   - Configuration UX: viewing and diffing Domain Packs, Tenant Policies, Playbooks

4) **Streaming / Near-Real-Time Capabilities**
   - Optional streaming ingestion mode (e.g. Kafka, MQ stubs)
   - Incremental decision streaming (stage-by-stage updates)
   - Backpressure and rate control to protect downstream tools and vector DB

5) **Safety, Guardrails & Red-Teaming**
   - Expanded safety rules for LLM calls and tool usage
   - Red-team / test harness to validate LLM prompts and outputs
   - Scenarios to ensure no policy violation, no unauthorized tool usage
   - Synthetic adversarial test suites for high-risk domains (finance, healthcare)

6) **Multi-Domain & Multi-Tenant Scale Readiness**
   - Hardening for many domains & tenants
   - SLO/SLA metrics definitions (latency, throughput, error rates)
   - Tenancy-aware quotas and limits (LLM usage, vector DB usage, tool calls)
   - Operational runbooks (error handling, incident playbooks)

7) **Explainability & Traceability**
   - Human-readable decision timelines for each exception:
     * which agents ran
     * which evidence was used (from RAG, tools, policies)
     * why certain actions/playbooks were chosen or rejected
   - API endpoints to retrieve and present explanations
   - Tie into existing audit + metrics

### Structure of .github/ISSUE_TEMPLATE/phase3-mvp-issues.md

Follow the same style and structure used in `phase1-mvp-issues.md` and `phase2-mvp-issues.md`, including:

- Grouped epics/sections (e.g., "LLM-Enhanced Reasoning", "Autonomous Optimization", "UX & Workflow", etc.)
- Numbered issues: P3-1, P3-2, ... (or a similar consistent scheme)
- For each issue:
  - Title
  - Priority (high/medium/low)
  - Description
  - Dependencies (Phase 1/2 issues, if relevant)
  - Acceptance criteria
  - Relevant spec references (point back to existing docs where possible)

Important constraints:
- DO NOT duplicate Phase 1 or Phase 2 tasks.
- Assume Phase 1 and Phase 2 are fully implemented and stable.
- Focus Phase 3 on LLM integration, autonomy, UX, safety, and scale.
- Keep issues granular enough that each one can map to a set of concrete coding prompts later.

Deliverable:
- A complete, well-structured `.github/ISSUE_TEMPLATE/phase3-mvp-issues.md` that can be used directly as the Phase 3 implementation backlog.





Created the Phase 3 MVP issues file at .github/ISSUE_TEMPLATE/phase3-mvp-issues.md.
Summary
The file includes 31 issues organized into 7 component areas:
LLM-Enhanced Agent Reasoning (6 issues) — P3-1 through P3-6
LLM-augmented agents with explainable reasoning
Safe JSON-bounded outputs with schema validation
Fallback strategies and timeout handling
Autonomous Optimization & Continuous Learning (5 issues) — P3-7 through P3-11
Enhanced policy learning loop
Automatic recommendations for severity rules, playbooks, and guardrails
Metrics-driven optimization engine
Full UX & Workflow Layer (5 issues) — P3-12 through P3-16
Operator UI backend APIs
Natural language interaction APIs
Re-run and what-if simulation APIs
Supervisor dashboards and configuration UX
Streaming / Near-Real-Time Capabilities (3 issues) — P3-17 through P3-19
Kafka/MQ streaming ingestion
Incremental decision streaming
Backpressure and rate control
Safety, Guardrails & Red-Teaming (4 issues) — P3-20 through P3-23
Expanded safety rules
Red-team test harness
Policy violation detection
Adversarial test suites for high-risk domains
Multi-Domain & Multi-Tenant Scale Readiness (4 issues) — P3-24 through P3-27
Hardening for many domains/tenants
SLO/SLA metrics and monitoring
Tenancy-aware quotas and limits
Operational runbooks
Explainability & Traceability (4 issues) — P3-28 through P3-31
Human-readable decision timelines
Evidence tracking and attribution
Explanation API endpoints
Integration with audit and metrics
Each issue includes:
Title and labels
Priority (high/medium/low)
Description
Dependencies on Phase 1/2 issues
Acceptance criteria
References to relevant spec documents
The file follows the same structure as Phase 1 and Phase 2, avoids duplication, and focuses on Phase 3 goals. Ready to use as the Phase 3 implementation backlog.





Phase 3 – Prompts 1–10 (LLM Reasoning + Optimization)
⭐ Prompt P3-1 — Shared LLM Client + Agent Output Schemas (Foundation)

Covers part of: P3-5 (safe JSON-bounded LLM outputs) and sets the foundation for P3-1..4, P3-6.

Cursor prompt:

Phase 3: Implement shared LLMClient + agent output schemas foundation.

Spec refs:
- docs/master_project_instruction_full.md (LLM usage, agent outputs)
- docs/04-agent-templates.md
- docs/03-data-models-apis.md
- docs/phase3-mvp-issues.md (P3-5, P3-1..P3-4)

Tasks:
1) Create or extend src/llm/provider.py:
   - Define LLMClient interface with:
       * generate_json(self, prompt: str, schema_name: str, timeout_s: Optional[int]) -> dict
       * provider-agnostic config (provider, model, max_tokens, temperature, etc.)
   - Implement at least one concrete provider (e.g., OpenAI/Grok) using existing config conventions.
   - Ensure we always request JSON-only output and handle token/cost logging hooks.

2) Create src/llm/schemas.py:
   - Define JSON schemas (or Pydantic models) for agent LLM outputs:
       * TriageLLMOutput
       * PolicyLLMOutput
       * ResolutionLLMOutput
       * SupervisorLLMOutput
   - Each schema should include:
       * structured reasoning (e.g., reasoning_steps[], evidence_references[])
       * main decision payload (e.g., predicted_exception_type, predicted_severity, policy_decision, action_rationale, etc.)
       * confidence scores
       * natural_language_summary

3) Wire schemas into LLMClient:
   - LLMClient.generate_json() should accept schema_name and know which JSON schema to validate against later (but validation is a separate step).

4) Keep everything tenant-aware:
   - LLMClient must accept tenant_id for future per-tenant model/tuning (even if Phase 3 MVP simply logs it).

Tests:
- tests/test_llm_client.py
   * mock provider HTTP calls
   * ensure generate_json returns decoded dict and logs basic metadata
- tests/test_llm_schemas.py
   * basic instantiation/validation of each schema

⭐ Prompt P3-2 — JSON Schema Validation + Sanitization Layer (Core of P3-5)

Covers: P3-5 (safe JSON-bounded LLM outputs).

Phase 3: Implement strict JSON schema validation and sanitization for all LLM agent outputs.

Spec refs:
- docs/master_project_instruction_full.md Section 7 (Agent Response Format)
- docs/phase3-mvp-issues.md P3-5

Tasks:
1) Create src/llm/validation.py:
   - validate_llm_output(schema_name: str, raw_text: str) -> dict
     * tries to parse JSON
     * validates against the appropriate schema (from src/llm/schemas.py)
     * on failure, raises ValidationError with detailed info

   - sanitize_llm_output(schema_name: str, parsed: dict) -> dict
     * strips unknown fields
     * clamps numeric values to safe ranges where relevant
     * ensures required fields exist (or applies safe defaults)

2) Add fallback JSON parsing:
   - If raw_text is almost-JSON (extra text around JSON):
     * attempt to extract inner JSON block heuristically
     * re-validate

3) Integrate with LLMClient:
   - Add helper LLMClient.safe_generate(schema_name, prompt, timeout_s) that:
       * calls provider
       * runs validate_llm_output + sanitize_llm_output
       * returns cleaned dict or raises a well-typed error.

4) Logging & audit:
   - On validation failure, log event into audit/metrics with:
       * tenant_id, agent_name, schema_name, error_type.

Tests:
- tests/test_llm_validation.py
   * valid vs invalid JSON
   * extra fields stripped
   * malformed JSON recovered via fallback
   * validation errors raised correctly

⭐ Prompt P3-3 — LLM Fallbacks, Timeouts, Circuit Breaker (P3-6)

Covers: P3-6 (fallback strategies and graceful degradation).

Phase 3: Implement LLM fallback strategies, timeouts, and circuit breaker.

Spec refs:
- docs/master_project_instruction_full.md Section 8 (Safety, Compliance, Reliability)
- docs/phase3-mvp-issues.md P3-6

Tasks:
1) Create src/llm/fallbacks.py:
   - LLMFallbackPolicy:
       * timeout_s per agent
       * max_retries
       * backoff strategy
       * circuit breaker thresholds (failure count/time window)
   - implement call_with_fallback(agent_name, tenant_id, schema_name, prompt, rule_based_fn):
       * try LLMClient.safe_generate with timeout and retries
       * if persistent failure or circuit breaker open:
           - call rule_based_fn() (existing deterministic logic)
           - mark decision as LLM_FALLBACK in metadata

2) Circuit breaker:
   - Maintain in-memory per-agent/per-tenant breaker state (Phase 3 MVP).
   - Support: CLOSED → OPEN → HALF_OPEN transitions.

3) Agent integration point:
   - Expose helper function that agents can call:
       * llm_or_rules(agent_name, tenant_id, schema_name, prompt, rule_based_fn) -> dict

4) Logging:
   - All fallback events log:
       * reason: timeout / validation_error / circuit_open
       * which path used: LLM vs rule_based.

Tests:
- tests/test_llm_fallbacks.py
   * timeouts trigger fallback
   * repeated failures open circuit breaker
   * half-open probes work as expected
   * rule-based fallback used when breaker is open

⭐ Prompt P3-4 — LLM-Augmented TriageAgent (P3-1)

Covers: P3-1 (LLM-enhanced triage with explanations).

Phase 3: Enhance TriageAgent with LLM reasoning + explainability.

Spec refs:
- docs/master_project_instruction_full.md Section 3 (Triage Agent)
- docs/04-agent-templates.md
- docs/phase3-mvp-issues.md P3-1

Assume:
- Existing src/agents/triage_agent.py from Phase 1.
- RAG + vector search from Phase 2 already integrated.

Tasks:
1) Update src/agents/triage_agent.py:
   - Add a method build_triage_prompt(exception_record, rag_evidence, rules_evidence) -> str
   - Use llm_or_rules(...) from src/llm/fallbacks.py with schema_name="TriageLLMOutput".
   - Merge:
       * deterministic/rule-based classification
       * LLM suggestions
       * RAG evidence
     into a final decision:
       * exception_type
       * severity
       * confidence_score

2) Expose structured reasoning:
   - Persist LLM reasoning fields into triage output:
       * reasoning_steps[]
       * evidence_references[]
       * natural_language_summary
   - Ensure these are added to:
       * audit trail
       * evidence block used by downstream agents.

3) Rule-based fallback:
   - If LLM fails or circuit breaker open:
       * fall back to existing Phase 1 logic (no behavior regression).

Tests:
- tests/test_triage_agent_llm.py
   * mock LLMClient and RAG results
   * verify final triage outcome respects policy + LLM reasoning
   * verify fallback path works when LLM disabled
   * ensure reasoning is stored in audit/evidence fields

⭐ Prompt P3-5 — LLM-Augmented PolicyAgent (P3-2)
Phase 3: Enhance PolicyAgent with LLM rule explanation and policy reasoning.

Spec refs:
- docs/master_project_instruction_full.md Section 5 (Policy & Guardrails)
- docs/phase3-mvp-issues.md P3-2

Assume:
- Existing src/agents/policy_agent.py from Phase 1.
- Tenant policies & guardrails from Domain/Tenant Policy Packs (Phase 2).

Tasks:
1) Update src/agents/policy_agent.py:
   - Add build_policy_prompt(exception_record, triage_result, tenant_policy, domain_pack) -> str
   - Use llm_or_rules("PolicyAgent", tenant_id, "PolicyLLMOutput", prompt, rule_based_fn).
   - rule_based_fn should:
       * use existing deterministic guardrail logic as baseline.

2) LLM output handling:
   - Explain which guardrails triggered and why.
   - Provide:
       * applied_rules[]
       * violated_rules[]
       * decision: ALLOW / REQUIRE_APPROVAL / BLOCK
       * reasoning_steps[]
       * tenant_policy_explanation
       * human_readable_violation_report

3) Persist explanations:
   - Store policy reasoning in:
       * audit
       * evidence for SupervisorAgent + dashboards.

Tests:
- tests/test_policy_agent_llm.py
   * verify LLM reasoning augmenting rule decisions (not contradicting guardrails)
   * policy violation report generated
   * fallback path uses pure rules when LLM unavailable

⭐ Prompt P3-6 — LLM-Augmented ResolutionAgent (P3-3)
Phase 3: Enhance ResolutionAgent with LLM-based action explanation.

Spec refs:
- docs/master_project_instruction_full.md Section 4 (Resolution Agent)
- docs/phase3-mvp-issues.md P3-3

Assume:
- src/agents/resolution_agent.py exists with playbook execution (Phase 2).

Tasks:
1) Update src/agents/resolution_agent.py:
   - Add build_resolution_prompt(exception_record, triage_result, policy_decision, selected_playbook, evidence) -> str
   - Use llm_or_rules("ResolutionAgent", tenant_id, "ResolutionLLMOutput", prompt, rule_based_fn).

2) LLM output semantics:
   - Provide:
       * explanation why this playbook is appropriate
       * reasons for rejecting alternative playbooks
       * explanation of tool execution order & dependencies
       * natural_language_action_summary for operators.

3) Integration with partial automation:
   - Do NOT change which tools are executed (respect existing guardrails & playbooks).
   - LLM is advisory on explanation, not an authority for adding new tools here (new playbooks come from P3-9).

4) Persist reasoning:
   - Store resolution reasoning in:
       * audit trail
       * timeline/evidence.

Tests:
- tests/test_resolution_agent_llm.py
   * verify explanation fields populated
   * verify no tools are executed that are not in the approved playbook
   * fallback retains existing behavior when LLM fails

⭐ Prompt P3-7 — LLM-Augmented SupervisorAgent (P3-4)
Phase 3: Enhance SupervisorAgent with LLM oversight reasoning.

Spec refs:
- docs/04-agent-templates.md (SupervisorAgent)
- docs/phase3-mvp-issues.md P3-4

Assume:
- src/agents/supervisor_agent.py exists from Phase 2.

Tasks:
1) Update src/agents/supervisor_agent.py:
   - Add build_supervisor_prompt(context_snapshot) -> str
     * includes triage, policy, resolution decisions
     * includes key evidence and confidence scores
   - Use llm_or_rules("SupervisorAgent", tenant_id, "SupervisorLLMOutput", prompt, rule_based_fn).

2) Supervisor LLM responsibilities:
   - Check for:
       * inconsistencies between agents
       * high risk + low confidence combos
       * policy violation risks
   - Output:
       * oversight_decision: OK / ESCALATE / REQUIRE_APPROVAL
       * escalation_reason
       * anomaly_explanation
       * suggested_human_message

3) Integration:
   - Orchestrator uses SupervisorAgent output to:
       * override next step to ESCALATE or PENDING_APPROVAL when needed.

Tests:
- tests/test_supervisor_agent_llm.py
   * verify oversight decisions can trigger escalation
   * ensure LLM cannot “allow” flows that guardrails blocked
   * verify fallback uses basic heuristic logic when LLM unavailable

⭐ Prompt P3-8 — Enhanced Policy Learning Loop (P3-7)
Phase 3: Enhance Policy Learning Loop with outcome analysis and suggestions.

Spec refs:
- docs/master_project_instruction_full.md Section 6 (Learning/Feedback)
- docs/phase3-mvp-issues.md P3-7

Assume:
- src/learning/policy_learning.py exists from Phase 2.

Tasks:
1) Extend src/learning/policy_learning.py:
   - Track per-policy-rule outcomes:
       * success_count, failure_count
       * MTTR distributions
       * false_positive_count, false_negative_count (derived from overrides & post-fact corrections)

2) Suggest improvements:
   - implement suggest_policy_improvements(tenant_id) -> list[Suggestion]
       * Suggestion includes:
           - rule_id
           - detected_issue (too strict / too lenient / low effectiveness)
           - proposed_change (description only, not applied)
           - impact_estimate (based on metrics)

3) Feedback integration:
   - FeedbackAgent should call policy learning with final outcome:
       * whether resolution was considered successful
       * whether human overrides occurred.

4) Persist suggestions and surface them:
   - store suggestions into ./runtime/learning/{tenantId}_policy_suggestions.jsonl.

Tests:
- tests/test_policy_learning_enhanced.py
   * simulate rule outcomes
   * verify suggestions generated correctly
   * ensure no auto-policy change is applied

⭐ Prompt P3-9 — Automatic Severity Rule Recommendation (P3-8)
Phase 3: Implement automatic severity rule recommendation engine.

Spec refs:
- docs/03-data-models-apis.md (Severity rules in Domain Pack)
- docs/phase3-mvp-issues.md P3-8

Tasks:
1) Create src/learning/severity_recommender.py:
   - analyze_severity_patterns(tenant_id, domain_name) -> list[SeverityRuleSuggestion]
   - data sources:
       * historical exceptions
       * triage decisions
       * overrides where severity was changed by humans
   - identify patterns like:
       * specific attributes/fields that correlate with escalated cases
       * combinations that should be HIGH instead of MEDIUM, etc.

2) Suggest rules:
   - each SeverityRuleSuggestion includes:
       * candidate_rule (domain-pack-compatible structure)
       * confidence_score
       * example_exceptions (ids) that motivated the rule.

3) Integrate with Policy Learning:
   - policy_learning can call severity_recommender and aggregate into a combined suggestion report.

4) Persist + audit:
   - write suggestions to ./runtime/learning/{tenantId}_{domainName}_severity_suggestions.jsonl.

Tests:
- tests/test_severity_recommender.py
   * synthetic data where a clear pattern exists → verify rule suggestion points it out
   * ensure suggestions are non-destructive (no rules auto-applied)

⭐ Prompt P3-10 — Automatic Playbook Recommendation & Optimization (P3-9)
Phase 3: Implement automatic playbook recommendation and optimization engine.

Spec refs:
- docs/master_project_instruction_full.md Section 4 (Resolution Agent)
- docs/03-data-models-apis.md (Playbooks)
- docs/phase3-mvp-issues.md P3-9

Assume:
- PlaybookManager + LLM-based playbook generation exist from Phase 2.

Tasks:
1) Create src/learning/playbook_recommender.py:
   - analyze_resolutions(tenant_id, domain_name) -> list[PlaybookSuggestion]
   - use:
       * historical successful resolutions (high success, low MTTR)
       * patterns of repeated manual steps by operators
   - output suggestions:
       * candidate_playbook (playbook schema)
       * effectiveness_prediction (based on historical stats)
       * supporting_examples (exception ids).

2) Optimization:
   - optimize_existing_playbooks(tenant_id, domain_name):
       * detect underperforming playbooks (low success, long MTTR)
       * suggest modifications (e.g., remove redundant steps, adjust order)
       * call into existing LLM-based playbook generator where appropriate BUT never auto-activate.

3) Human-in-loop workflow:
   - design structures for:
       * mark_suggestion_reviewed(...)
       * mark_playbook_accepted/rejected(...)
   - persist suggestions and decisions into ./runtime/learning/{tenantId}_{domainName}_playbook_suggestions.jsonl.

Tests:
- tests/test_playbook_recommender.py
   * verify suggestions based on synthetic success metrics
   * verify optimization identifies poor playbooks and proposes changes


We already covered P3-1…P3-10; let’s continue with the next 10 prompts, mapped to the Phase 3 issues and in a dependency-friendly order.

Below are ready-to-paste Cursor prompts for:

P3-11 – Metrics-driven optimization engine

P3-12 – Operator UI backend APIs

P3-13 – Natural language interaction API

P3-14 – Re-run & what-if simulation API

P3-15 – Supervisor dashboard APIs

P3-16 – Config diff/view APIs

P3-17 – Streaming ingestion mode

P3-18 – Incremental decision streaming

P3-19 – Backpressure & rate control

P3-20 – Expanded safety rules

They assume your existing structure (FastAPI app, agents in src/agents/*.py, learning modules, etc.).

🔹 Prompt 11 — Metrics-Driven Optimization Engine (P3-11)
Phase 3: Implement metrics-driven optimization engine (P3-11).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-11 (Metrics-Driven Optimization Engine)
- docs/master_project_instruction_full.md Section 13 (Key Success Metrics)
- Phase 2: metrics + policy learning modules

Goals:
- Central engine that consumes metrics (success rates, MTTR, false pos/neg)
- Produces optimization recommendations across:
  * policies
  * severity rules
  * playbooks
  * guardrails

Tasks:
1) Create src/optimization/engine.py:
   - Define dataclasses / Pydantic models:
       * OptimizationSignal (source, metric_type, current_value, target_value, tenant_id, domain)
       * OptimizationRecommendation (id, tenant_id, domain, category: ["policy","severity","playbook","guardrail"], description, impact_estimate, confidence, related_entities)
   - Implement OptimizationEngine with methods:
       * collect_signals(tenant_id, domain) -> list[OptimizationSignal]
          - pulls from:
              · policy learning metrics
              · severity recommender metrics
              · playbook recommender metrics
              · guardrail recommender metrics
       * generate_recommendations(tenant_id, domain) -> list[OptimizationRecommendation]
          - calls into:
              · policy_learning.suggest_policy_improvements(...)
              · severity_recommender.analyze_severity_patterns(...)
              · playbook_recommender.analyze_resolutions(...)
              · guardrail_recommender.analyze_guardrail_outcomes(...)
          - normalizes all into OptimizationRecommendation objects

2) Storage:
   - Write recommendations to:
       ./runtime/optimization/{tenantId}_{domain}_recommendations.jsonl
   - Each line = JSON of OptimizationRecommendation with timestamp.

3) Integration:
   - Add a service entry point:
       src/services/optimization_service.py
       * run_periodic_optimization(tenant_id, domain) -> None
       * This will be used by ops/cron or admin API (Phase 3+).

4) Tests:
   - tests/test_optimization_engine.py:
       * use fake policy/severity/playbook/guardrail suggestors
       * verify combined recommendations are generated and written
       * ensure categories, impact, and confidence fields are set.

Keep implementation Phase-3-MVP simple: no A/B rollout yet, just analysis + recommendation objects.

🔹 Prompt 12 — Operator UI Backend APIs for Exception Browsing (P3-12)
Phase 3: Implement Operator UI backend APIs for exception browsing (P3-12).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-12 (Operator UI Backend APIs) 
- docs/03-data-models-apis.md (System-Level REST APIs)
- Phase 1: Status API + Audit Trail

Goals:
- REST APIs to power an operator UI:
  * browse exceptions, decisions, evidence, audit history
  * filter/search/paginate
  * access RAG evidence and agent reasoning
  * optional real-time updates via WebSocket/SSE

Tasks:
1) Create src/api/router_operator.py:
   - FastAPI APIRouter with prefix e.g. "/ui":
       * GET /ui/exceptions
           - query params: tenant_id, domain, status, severity, from_ts, to_ts, page, page_size, search
       * GET /ui/exceptions/{exception_id}
           - returns full ExceptionRecord plus agent decisions
       * GET /ui/exceptions/{exception_id}/evidence
           - returns evidence chains, RAG results, tool outputs
       * GET /ui/exceptions/{exception_id}/audit
           - returns audit events related to this exception

2) Data sources:
   - reuse existing persistence from:
       * exception store (Phase 2)
       * audit trail (Phase 1)
       * RAG memory references
   - add helper functions in src/services/ui_query_service.py:
       * search_exceptions(...)
       * get_exception_detail(exception_id)
       * get_exception_evidence(exception_id)
       * get_exception_audit(exception_id)

3) Real-time updates:
   - For now, implement SSE or basic WebSocket stub:
       * GET /ui/stream/exceptions (SSE)
           - placeholder returning heartbeat and dummy "update" events
           - actual incremental updates completed in P3-18

4) Wire router:
   - Include router_operator in main FastAPI app (e.g., src/server/app.py).

5) Tests:
   - tests/test_operator_apis.py:
       * test browsing with pagination and filters using in-memory or test DB
       * test detail/evidence/audit endpoints shape
       * test SSE/WebSocket endpoint at least returns valid handshake/stream.

🔹 Prompt 13 — Natural Language Interaction API (P3-13)
Phase 3: Implement natural language interaction API for agent queries (P3-13).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-13 (Natural Language Interaction API) :contentReference[oaicite:1]{index=1}
- docs/master_project_instruction_full.md Section 7 (Explainable decisions)
- LLM client + schemas from P3-1..P3-6

Goals:
- Operators can ask:
   * "Why did you block this?"
   * "What evidence did Triage use?"
   * "What alternative actions were possible?"
- Answers use existing explainability data + LLM summarization.

Tasks:
1) Create src/api/router_nlq.py:
   - POST /ui/nlq
       * body:
           - tenant_id
           - exception_id
           - question: str
       * response:
           - answer: str
           - answer_sources: list[evidence_ids]
           - agent_context_used: list[agent_names]

2) Implement NLQ service:
   - src/services/nlq_service.py with:
       * answer_question(tenant_id, exception_id, question) -> dict
   - Steps:
       1. Fetch exception, decisions, evidence, timelines from stores.
       2. Build compact "context bundle" (only relevant facts).
       3. Build LLM prompt:
           - include question
           - include structured context (agents, decisions, evidence)
           - instruct LLM to answer grounded in provided context only.
       4. Use LLMClient.safe_generate(schema_name="NLQAnswer" or simple text mode).
       5. Return answer + references (ids of evidence/decisions used).

3) Safety:
   - Ensure NLQ cannot see cross-tenant data.
   - Ensure question + context are logged/audited.

4) Tests:
   - tests/test_nlq_api.py:
       * mock LLM client
       * verify the API shapes and that context bundle is constructed
       * verify multi-question scenarios (short test).

🔹 Prompt 14 — Re-Run & What-If Simulation API (P3-14)
Phase 3: Implement re-run and what-if simulation API (P3-14).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-14 (Re-Run and What-If Simulation API) :contentReference[oaicite:2]{index=2}
- docs/master_project_instruction_full.md Section 4 (Core Capabilities)
- Orchestrator from Phase 1 + advanced orchestration from Phase 2

Goals:
- Allow operators to:
   * re-run an exception with minor parameter changes
   * run "what-if" scenarios (e.g. different severity or policy settings)
   * run in simulation mode (no persistent side effects)

Tasks:
1) Create src/api/router_simulation.py:
   - POST /ui/exceptions/{exception_id}/rerun
       * body: { tenant_id, overrides?: { severity?, policies?, playbook? }, simulation: bool }
   - GET /ui/simulations/{simulation_id}
       * returns simulation result, including decisions, evidence, comparison to original.

2) Orchestrator integration:
   - In src/orchestrator/engine.py (or equivalent):
       * add run_simulation(exception_record, overrides, tenant_id) -> SimulationResult
       * simulation should:
           - reuse same agent pipeline
           - respect guardrails
           - NOT persist changes to real exception state
           - tag audit events as "SIMULATION".

3) Comparison logic:
   - Implement helper in src/services/simulation_compare.py:
       * compare_runs(original_run, simulated_run) -> diff structure
           - highlight changed: severity, decisions, actions, approvals required.

4) Storage:
   - Save simulation results to:
       ./runtime/simulations/{tenantId}/{simulationId}.json

5) Tests:
   - tests/test_simulation_api.py
       * verify rerun and what-if APIs
       * verify simulation mode does not update main exception record
       * verify comparison output is generated.

🔹 Prompt 15 — Supervisor Dashboard Backend APIs (P3-15)
Phase 3: Implement Supervisor Dashboard backend APIs (P3-15).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-15 (Supervisor Dashboard Backend APIs)
- docs/master_project_instruction_full.md (Supervisor responsibilities, oversight, metrics)

Goals:
- Supervisor view over:
   * high-risk exceptions
   * escalations
   * policy violations
   * optimization suggestions

Tasks:
1) Create src/api/router_supervisor_dashboard.py:
   - GET /ui/supervisor/overview
       * query: tenant_id, domain, from_ts, to_ts
       * returns:
           - counts (by severity, status)
           - number of escalations, pending approvals
           - top policy violations
           - summary of optimization suggestions.
   - GET /ui/supervisor/escalations
       * returns list of escalated exceptions with key metadata.
   - GET /ui/supervisor/policy-violations
       * returns recent policy violation events.

2) Service layer:
   - src/services/supervisor_dashboard_service.py:
       * aggregate from:
           - audit logs
           - supervisor decisions
           - policy violation detector (later P3-22)
           - optimization engine suggestions.

3) Performance:
   - Do simple aggregation in MVP; no heavy analytics store required yet.

4) Tests:
   - tests/test_supervisor_dashboard_api.py
       * use synthetic stored events
       * verify API shapes and basic aggregation.

🔹 Prompt 16 — Config Viewing & Diff APIs (P3-16)
Phase 3: Implement configuration viewing and diffing APIs (P3-16).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-16 (Config Viewing & Diff APIs) :contentReference[oaicite:3]{index=3}
- docs/03-data-models-apis.md (Domain Pack Schema, Tenant Policy Pack Schema)
- Phase 2: Domain Pack loader + admin APIs

Goals:
- Backend APIs to:
   * view Domain Packs, Tenant Policy Packs, Playbooks
   * diff versions
   * view history and support rollback stubs

Tasks:
1) Create src/api/router_config_view.py:
   - GET /admin/config/domain-packs
       * query: tenant_id?, domain?
   - GET /admin/config/domain-packs/{id}
   - GET /admin/config/tenant-policies/{id}
   - GET /admin/config/playbooks/{id}
   - GET /admin/config/diff
       * query: type (domain_pack|tenant_policy|playbook), left_version, right_version

2) Implement service layer:
   - src/services/config_view_service.py:
       * list_configs(type, tenant_id, domain)
       * get_config_by_id(type, id)
       * diff_configs(type, left_version, right_version) -> structured diff
   - Use underlying storage where Domain Packs & Policies already live (Phase 2).

3) History & rollback stubs:
   - For MVP:
       * history endpoints show ordered versions with timestamps
       * rollback endpoint can be a stub that validates but does not apply in Phase 3.

4) Tests:
   - tests/test_config_view_apis.py
       * verify listing, detail, diff responses on synthetic configs.

🔹 Prompt 17 — Streaming Ingestion Mode (Kafka/MQ Stub) (P3-17)
Phase 3: Implement streaming ingestion mode (Kafka/MQ stub) (P3-17).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-17 (Streaming Ingestion Mode) :contentReference[oaicite:4]{index=4}
- docs/master_project_instruction_full.md Section 2 (Exception Intake & Normalization - streaming + batch)
- Phase 1: Exception ingestion service + REST endpoint

Goals:
- Add optional streaming ingestion:
   * Kafka or MQ stub abstraction
   * both batch (existing REST) and streaming supported

Tasks:
1) Create src/ingestion/streaming.py:
   - Define interface:
       * class StreamingIngestionBackend(Protocol):
           - start()
           - stop()
       * KafkaIngestionBackend(StreamingIngestionBackend) (stub implementation using aiokafka or placeholder interface).
   - Define message schema for exception messages (consistent with ExceptionRecord input).

2) Abstraction:
   - Implement StreamingIngestionService:
       * __init__(backend: StreamingIngestionBackend, normalizer)
       * on message:
           - normalize to ExceptionRecord
           - pass into orchestrator / queue.

3) Configuration:
   - Add config entries:
       * streaming.enabled
       * streaming.backend = "kafka" | "stub"
       * streaming.kafka.bootstrap_servers, topic, group_id etc.
   - Provide default stub backend that just reads from an in-memory queue for tests.

4) Tests:
   - tests/test_streaming_ingestion.py
       * use stub backend that pushes messages into service
       * verify messages end up in orchestrator or processing queue.

🔹 Prompt 18 — Incremental Decision Streaming (Stage-by-Stage Updates) (P3-18)
Phase 3: Implement incremental decision streaming (stage-by-stage updates) (P3-18).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-18 (Incremental Decision Streaming) 
- docs/master_project_instruction_full.md Section 4 (Agent Orchestration Workflow)
- Phase 1: Orchestrator core
- Phase 3: operator UI APIs (P3-12)

Goals:
- Send live updates as each stage completes:
   * Intake → Triage → Policy → Resolution → Feedback
- Expose via WebSocket/SSE for operator UI.

Tasks:
1) Orchestrator events:
   - In src/orchestrator/engine.py:
       * define EventBus or callback mechanism (simple MVP):
           - on_stage_completed(event: StageCompletedEvent)
       * StageCompletedEvent includes:
           - exception_id, stage_name, timestamp, decision_summary

2) Streaming transport:
   - Implement src/streaming/decision_stream.py:
       * subscribe to orchestrator events
       * push updates into:
           - in-memory pub/sub registry keyed by tenant_id, exception_id.

3) API integration:
   - Enhance /ui/stream/exceptions endpoint (from P3-12) to:
       * allow subscription per exception_id
       * use Server-Sent Events or WebSocket to stream StageCompletedEvent as JSON.

4) Tests:
   - tests/test_incremental_streaming.py
       * simulate orchestrator running through all stages
       * verify events are emitted in correct order
       * verify SSE/WebSocket test client receives events.

🔹 Prompt 19 — Backpressure & Rate Control for Streaming (P3-19)
Phase 3: Implement backpressure and rate control for streaming (P3-19).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-19 (Backpressure and Rate Control) :contentReference[oaicite:6]{index=6}
- docs/master_project_instruction_full.md Section 8 (Safety, Compliance, and Reliability)
- Phase 3: streaming ingestion (P3-17) and incremental streaming (P3-18)
- Phase 2: advanced vector DB integration

Goals:
- Protect:
   * vector DB
   * tool execution engine
   * orchestrator
- from overload via backpressure, rate limiting, and adaptive control.

Tasks:
1) Queue + metrics:
   - Add queue depth tracking to StreamingIngestionService and orchestrator work queue:
       * current_depth, max_depth thresholds.
   - Expose metrics (e.g., via existing metrics subsystem).

2) Backpressure policy:
   - Create src/streaming/backpressure.py:
       * BackpressurePolicy with:
           - max_queue_depth
           - max_in_flight_exceptions
           - rate_limit_per_tenant
       * controller that:
           - when thresholds exceeded:
               · slows down or pauses consuming from Kafka/MQ
               · emits events/alerts
               · optionally drops low-priority messages in MVP (configurable).

3) Integration:
   - In streaming backend(s), periodically consult BackpressurePolicy before polling/committing messages.
   - For vector DB or tools:
       * optional check to delay new operations when system under stress.

4) Tests:
   - tests/test_backpressure.py:
       * simulate high message rates
       * verify streaming slows or pauses
       * verify events/metrics updated when thresholds crossed.

🔹 Prompt 20 — Expanded Safety Rules for LLM Calls & Tool Usage (P3-20)
Phase 3: Implement expanded safety rules for LLM calls and tool usage (P3-20).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-20 (Expanded Safety Rules for LLM Calls and Tool Usage) 
- docs/08-security-compliance.md (Security & Compliance Checklist)
- Phase 1: Tool Registry + Invocation
- Phase 3: P3-5 (safe JSON-bounded outputs)

Goals:
- Central safety rules around:
   * LLM usage (rate, tokens, cost)
   * tool usage (execution time, resources, retries)
   * per-tenant overrides

Tasks:
1) Create src/safety/rules.py:
   - SafetyRuleConfig:
       * llm:
           - max_tokens_per_call
           - max_calls_per_minute
           - max_cost_per_hour (approx)
       * tools:
           - max_exec_time_ms
           - max_retries
           - disallowed_tools
       * tenant_overrides: dict[tenant_id, SafetyRuleConfig]

   - SafetyEnforcer:
       * check_llm_call(tenant_id, tokens, estimated_cost) -> None or raises SafetyViolation
       * check_tool_call(tenant_id, tool_name, estimated_time_ms) -> None or raises SafetyViolation
       * record_usage(...) for metrics & enforcement.

2) Integrate with LLMClient:
   - Before making calls, consult SafetyEnforcer.check_llm_call.
   - On completion, record_usage.

3) Integrate with ExecutionEngine:
   - Before invoking a tool, call SafetyEnforcer.check_tool_call.
   - On completion, record usage and flag long-running executions.

4) Config:
   - Add safety configuration section to existing config files:
       * global defaults
       * per-tenant overrides.

5) Tests:
   - tests/test_safety_rules.py:
       * verify rules block calls when limits exceeded
       * verify tenant-specific overrides work
       * ensure safety violations are logged/audited.


If you want, next step I can generate the remaining Phase 3 prompts for:

Red-team harness (P3-21), policy violation detection (P3-22)

Quotas & SLO/SLA (P3-23–P3-26)

Runbooks, decision timelines, evidence tracking, explanation APIs (P3-27–P3-31).







Love it, let’s finish Phase 3 properly 💪

Below are Phase 3 code prompts for P3-21 → P3-31 in a Cursor-friendly format, continuing the same style as before. Each is self-contained so you can paste them one by one.

🔹 Prompt 21 — Red-Team Test Harness for LLM Prompts & Outputs (P3-21)
Phase 3: Implement Red-Team Test Harness for LLM prompts and outputs (P3-21).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-21 (Red-Team Test Harness for LLM Prompts and Outputs)
- docs/08-security-compliance.md (Security & Compliance Checklist)

Goals:
- Create a red-team harness that can:
  * run adversarial tests against LLM prompts and outputs
  * simulate prompt injection / jailbreaking attempts
  * validate outputs against safety rules and schemas
  * produce reports and plug into CI

Tasks:
1) Create src/redteam/harness.py:
   - Define data models:
       * RedTeamScenario(id, name, description, agent_name, schema_name, prompt_template, attack_type, expected_outcome)
       * RedTeamResult(scenario_id, passed, violations, raw_output, parsed_output, metadata)
   - Implement RedTeamHarness with:
       * run_scenario(scenario: RedTeamScenario) -> RedTeamResult
          - builds adversarial prompt from template + attack pattern
          - calls LLMClient.safe_generate(schema_name=...)
          - uses validation + safety modules to detect violations
       * run_suite(scenarios: list[RedTeamScenario]) -> list[RedTeamResult]

2) Scenario library:
   - Add src/redteam/scenarios.py with predefined scenarios:
       * injection into system prompt
       * instruction to ignore safety rules
       * attempts to bypass allow-lists
       * attempts to generate unstructured, non-JSON output
   - Focus on triage, policy, resolution, supervisor agents first.

3) Reporting:
   - Implement src/redteam/reporting.py:
       * generate_report(results: list[RedTeamResult]) -> dict
       * write JSON/Markdown reports under:
           ./runtime/redteam/{timestamp}_report.json
           ./runtime/redteam/{timestamp}_report.md

4) CI entrypoint:
   - Add a CLI/pytest-style entry:
       * scripts/run_redteam.py
       * can be called from CI to run default scenario suite and fail build on critical violations.

5) Tests:
   - tests/test_redteam_harness.py:
       * mock LLM client to produce both safe and unsafe outputs
       * verify detection of:
           - schema violations
           - safety rule violations
           - obvious prompt injection patterns

🔹 Prompt 22 — Policy Violation & Unauthorized Tool Usage Detection (P3-22)
Phase 3: Implement policy violation and unauthorized tool usage detection (P3-22).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-22 (Policy Violation and Unauthorized Tool Usage Detection)
- docs/master_project_instruction_full.md Section 8 (Safety, Compliance, and Reliability)

Goals:
- Detect when:
  * decisions violate tenant/domain policies
  * tools are used outside allow-lists or misconfigured
- Provide real-time alerts + automatic blocking of unsafe actions.

Tasks:
1) Create src/safety/violation_detector.py:
   - Data models:
       * PolicyViolation(id, tenant_id, exception_id, agent_name, rule_id, description, severity, timestamp)
       * ToolViolation(id, tenant_id, exception_id, tool_name, description, severity, timestamp)
   - Implement ViolationDetector with:
       * check_policy_decision(tenant_id, exception_record, triage_result, policy_decision, tenant_policy) -> list[PolicyViolation]
       * check_tool_call(tenant_id, exception_id, tool_def, tool_call_request) -> Optional[ToolViolation]
       * record_violation(violation) -> None

2) Integration:
   - In PolicyAgent (src/agents/policy.py):
       * after final decision, call check_policy_decision(...)
       * if severe violation detected -> mark decision as BLOCK and notify.
   - In ExecutionEngine (before actual tool invocation):
       * call check_tool_call(...)
       * if violation returned -> block call and raise SafetyViolation.

3) Monitoring & alerting:
   - Integrate with observability:
       * emit metrics per violation type (policy/tool, severity)
       * send alerts via existing notification service (Phase 2).
   - Store violations under:
       ./runtime/violations/{tenantId}_violations.jsonl

4) Incident workflow stub:
   - Add src/safety/incidents.py:
       * open_incident(violation) -> incident_id
       * close_incident(incident_id, resolution_summary)
     (Phase 3 MVP: just log and persist; full integration with ITSM can be later.)

5) Tests:
   - tests/test_violation_detector.py:
       * simulate decisions that contradict policies
       * simulate tool invocations not on allow-list
       * verify violations emitted, logged, and block behavior executed.

🔹 Prompt 23 — Synthetic Adversarial Test Suites for High-Risk Domains (P3-23)
Phase 3: Implement synthetic adversarial test suites for high-risk domains (P3-23).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-23 (Synthetic Adversarial Test Suites for High-Risk Domains)
- docs/08-security-compliance.md (Regulatory Alignment - FINRA/HIPAA)

Goals:
- Build domain-specific adversarial suites for:
   * finance (FINRA-style constraints)
   * healthcare (HIPAA-style constraints)
- Plug into red-team harness for automated runs.

Tasks:
1) Create src/redteam/adversarial_suites.py:
   - Define:
       * build_finance_adversarial_suite() -> list[RedTeamScenario]
       * build_healthcare_adversarial_suite() -> list[RedTeamScenario]
   - Scenarios should:
       * craft malicious or edge-case exceptions (e.g., sensitive data, suspicious patterns)
       * attempt to steer agents to violate policies or regulatory constraints.
   - Tag scenarios with metadata:
       * domain = "finance" | "healthcare"
       * regulation = "FINRA" | "HIPAA"

2) Synthetic data generation:
   - Under src/redteam/data_generators.py:
       * generate_finance_exception_edge_cases()
       * generate_healthcare_exception_edge_cases()
   - Use Domain Packs for those domains where possible so exceptions are structurally valid.

3) Execution integration:
   - Update scripts/run_redteam.py:
       * add flags: --domain finance|healthcare|all
       * run appropriate adversarial suite(s) and produce domain-specific report sections.

4) Reporting:
   - Extend redteam/reporting.py to:
       * include per-domain section with:
           - scenarios run
           - pass/fail counts
           - regulatory-related violations.

5) Tests:
   - tests/test_adversarial_suites.py:
       * ensure suites are built with expected number of scenarios
       * ensure generated exceptions conform to the Domain Pack schema
       * use stubbed harness to verify suite invocation.

🔹 Prompt 24 — Infrastructure Hardening for Many Domains & Tenants (P3-24)
Phase 3: Implement infrastructure hardening for many domains & tenants (P3-24).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-24 (Hardening for Many Domains & Tenants)
- docs/01-architecture.md (Multi-Tenant Isolation Model)

Goals:
- Support:
   * many domains per tenant
   * many tenants on shared infra
- Through:
   * resource pooling/isolation
   * domain pack caching and lazy loading
   * DB partitioning/indexing hooks.

Tasks:
1) Domain pack caching:
   - In src/domain/packs.py (or equivalent):
       * implement DomainPackCache:
           - get_pack(tenant_id, domain_name, version=None)
               · use in-memory LRU cache
               · load lazily from storage when missing
           - invalidate(tenant_id, domain_name, version)
       * ensure thread-safety.

2) Tenant-specific resource pools:
   - In src/infrastructure/resources.py:
       * define TenantResourcePool:
           - db_connections
           - vector_db_clients
           - tool_client_limiter
       * implement simple registry:
           - get_pool(tenant_id) -> TenantResourcePool
       * use pooling for:
           - DB access (where applicable)
           - vector store adapters
           - tool HTTP clients.

3) DB partitioning / indexing:
   - In persistence layer (e.g., src/storage/exception_store.py, audit_store, metrics_store):
       * add partitioning key = tenant_id (and optionally domain).
       * ensure compound indexes on:
           - tenant_id, domain, created_at
           - tenant_id, status, severity.

4) Perf hooks:
   - Add a small script:
       * scripts/run_multitenant_smoke.py
       * spins up synthetic tenants/domains, sends traffic, and logs latency + resource usage (MVP).

5) Tests:
   - tests/test_domain_pack_cache.py
   - tests/test_tenant_resource_pool.py
       * verify caching, invalidation, and tenant isolation
       * verify no cross-tenant sharing of caches that should be isolated.

🔹 Prompt 25 — SLO/SLA Metrics Definitions & Monitoring (P3-25)
Phase 3: Implement SLO/SLA metrics definitions and monitoring (P3-25).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-25 (SLO/SLA Metrics Definitions and Monitoring)
- docs/master_project_instruction_full.md Section 13 (Key Success Metrics)
- Phase 2: metrics collection + dashboards

Goals:
- Define and track SLO/SLA per tenant:
   * latency, throughput, error rates
   * auto-resolution rate, MTTR
- Provide monitoring, alerts, and reporting.

Tasks:
1) SLO config:
   - Create src/observability/slo_config.py:
       * SLOConfig(tenant_id, domain, target_latency_ms, target_error_rate, target_mttr_minutes, target_auto_resolution_rate, etc.)
       * load from config file:
           ./config/slo/{tenantId}_{domain}.yaml (if present) with sensible defaults otherwise.

2) Metrics computation:
   - In src/observability/slo_engine.py:
       * compute_slo_status(tenant_id, domain, window) -> SLOStatus
         - aggregates metrics from existing metrics subsystem:
             · p95 latency
             · error rate
             · mttr
             · auto-resolution rate
       * SLOStatus includes:
           - passed/failed threshold per dimension
           - current vs target.

3) Monitoring & alerting:
   - Periodic job (or callable service):
       * run_slo_check_all_tenants() -> list[SLOStatus]
       * for any failures, generate alerts via notification service + log to:
           ./runtime/slo/{timestamp}_slo_status.jsonl

4) Dashboard support:
   - Provide helper for APIs to expose SLOStatus summaries for supervisor dashboard (P3-15) – just implement a reusable function, not API wiring here.

5) Tests:
   - tests/test_slo_engine.py:
       * feed synthetic metrics
       * verify SLOStatus classification
       * ensure tenant-specific configs override defaults.

🔹 Prompt 26 — Tenancy-Aware Quotas & Limits (LLM, Vector DB, Tools) (P3-26)
Phase 3: Implement tenancy-aware quotas and limits (LLM, vector DB, tool calls) (P3-26).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-26 (Tenancy-Aware Quotas and Limits)
- docs/01-architecture.md (Multi-Tenant Isolation Model)
- Phase 3: P3-20 (Expanded Safety Rules)

Goals:
- Implement hard quotas per tenant for:
   * LLM API (tokens, requests, cost)
   * vector DB operations
   * tool executions
- Connect to monitoring and enforcement.

Tasks:
1) Quota models:
   - Create src/safety/quotas.py:
       * QuotaConfig(tenant_id, llm_tokens_per_day, llm_requests_per_minute, llm_cost_per_day, vector_queries_per_minute, vector_storage_mb, tool_calls_per_minute, tool_exec_time_ms_per_minute, etc.)
       * QuotaUsage trackers (in-memory + persisted snapshots):
           - current usage counters per window.

2) Enforcement:
   - QuotaEnforcer with:
       * check_llm_quota(tenant_id, tokens, estimated_cost) -> None or raises QuotaExceeded
       * check_vector_quota(tenant_id, query_count, write_count, storage_mb_delta)
       * check_tool_quota(tenant_id, tool_name, estimated_exec_time_ms)
       * record_usage(...) for each resource type.

3) Integration:
   - Hook into:
       * LLMClient before calls (besides SafetyEnforcer).
       * VectorStore adapter methods (query, upsert).
       * ExecutionEngine before tool execution.
   - On QuotaExceeded:
       * block operation
       * log violation and emit alerts.

4) Monitoring & reporting:
   - Periodically persist quota usage to:
       ./runtime/quotas/{tenantId}_usage.jsonl
   - Provide helper to retrieve usage summaries for reporting and dashboards.

5) Tests:
   - tests/test_quota_enforcer.py:
       * simulate usage that stays under quotas
       * simulate overages and verify QuotaExceeded
       * ensure per-tenant isolation.

🔹 Prompt 27 — Operational Runbooks & Incident Playbooks (P3-27)
Phase 3: Implement operational runbooks and incident playbooks (P3-27).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-27 (Operational Runbooks)
- docs/master_project_instruction_full.md Section 8 (Safety, Compliance, and Reliability)

Goals:
- Provide structured runbooks for:
   * common error conditions
   * platform incidents
- Integrate with observability + notification.

Tasks:
1) Runbook models:
   - Create src/operations/runbooks.py:
       * Runbook(id, name, description, triggers, steps, severity, owner, tags)
       * RunbookExecution(id, runbook_id, incident_id, start_time, end_time, status, notes)
   - Load runbook definitions from:
       ./config/runbooks/*.yaml

2) Triggering:
   - Implement suggest_runbooks_for_incident(incident) -> list[Runbook]
       * matches on tags, severity, component, error codes.

3) Tracking:
   - Implement RunbookExecutor:
       * start_execution(runbook, incident) -> RunbookExecution
       * complete_execution(execution_id, notes, status)
       * persist executions to:
           ./runtime/runbooks/executions.jsonl

4) Integration hooks:
   - Connect to:
       * violation incidents (from P3-22)
       * SLO/SLA violations (P3-25)
       * major errors from observability subsystem.
   - For Phase 3 MVP, simple function calls from wherever incidents are created.

5) Tests:
   - tests/test_runbooks.py:
       * load sample runbooks
       * verify suggestion logic
       * verify execution tracking.

🔹 Prompt 28 — Human-Readable Decision Timelines (P3-28)
Phase 3: Implement human-readable decision timelines for exceptions (P3-28).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-28 (Decision Timelines)
- docs/master_project_instruction_full.md Section 8 (Explainable decisions)

Goals:
- Build a timeline representation for each exception:
   * which agents ran, when
   * what evidence was used
   * why actions/playbooks were chosen/rejected.

Tasks:
1) Timeline builder:
   - Create src/explainability/timelines.py:
       * TimelineEvent(id, timestamp, stage_name, agent_name, summary, evidence_ids, reasoning_excerpt)
       * DecisionTimeline(exception_id, events: list[TimelineEvent])
   - Implement:
       * build_timeline_for_exception(exception_id) -> DecisionTimeline
          - pulls from:
              · audit trail events
              · agent outputs (triage, policy, resolution, supervisor, feedback)
              · evidence tracking (P3-29 will enrich this further).

2) Visualization-friendly structure:
   - Ensure DecisionTimeline can be serialized to:
       * JSON for APIs
       * a simple Markdown/ASCII representation for logs.

3) Export and sharing:
   - Add helper:
       * export_timeline_markdown(timeline) -> str
       * write to:
           ./runtime/timelines/{exceptionId}.md

4) Tests:
   - tests/test_decision_timelines.py:
       * seed synthetic audit + agent outputs
       * verify correct event ordering and summaries
       * verify evidence_ids and reasoning excerpts included.

🔹 Prompt 29 — Evidence Tracking & Attribution System (P3-29)
Phase 3: Implement evidence tracking and attribution system (P3-29).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-29 (Evidence Tracking and Attribution)
- docs/master_project_instruction_full.md Section 7 (Agent Response Format - evidence field)

Goals:
- Track:
   * RAG results and similarity scores
   * tool outputs
   * policy rules and guardrails
- Provide full evidence chains for decisions.

Tasks:
1) Evidence model:
   - Create src/explainability/evidence.py:
       * EvidenceItem(id, type: ["rag","tool","policy","manual"], source_id, description, payload_ref, similarity_score?, created_at)
       * EvidenceLink(id, exception_id, agent_name, stage_name, evidence_id, influence: ["support","contradict","contextual"])
   - Provide helper functions:
       * record_evidence_item(...)
       * link_evidence_to_decision(...)

2) Integration points:
   - RAG:
       * in memory/RAG service, whenever results are returned, record:
           - each document/snippet as EvidenceItem(type="rag").
   - Tools:
       * in ToolExecutionEngine, record tool outputs as EvidenceItem(type="tool").
   - Policy:
       * in PolicyAgent, record applied rules and guardrails as EvidenceItem(type="policy").

3) Retrieval:
   - Implement:
       * get_evidence_for_exception(exception_id) -> list[EvidenceItem]
       * get_evidence_links_for_exception(exception_id) -> list[EvidenceLink]

4) Storage:
   - For MVP, store evidence in:
       ./runtime/evidence/{tenantId}_{exceptionId}_evidence.jsonl

5) Tests:
   - tests/test_evidence_tracking.py:
       * simulate RAG + tool + policy flows
       * verify evidence items and links created and retrievable
       * verify that influence types are respected.

🔹 Prompt 30 — Explanation API Endpoints (P3-30)
Phase 3: Implement Explanation API endpoints (P3-30).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-30 (Explanation API Endpoints)
- docs/master_project_instruction_full.md Section 8 (Explainable decisions)

Goals:
- Expose explanations via API:
   * by exception ID
   * by agent
   * by decision type
- Support:
   * JSON
   * natural language
   * structured formats.

Tasks:
1) API router:
   - Create src/api/router_explanations.py:
       * GET /explanations/{exception_id}
           - query: format=json|text|structured
       * GET /explanations/search
           - query params: tenant_id, agent_name?, decision_type?, from_ts?, to_ts?, text?
       * GET /explanations/{exception_id}/timeline
           - returns DecisionTimeline JSON (from P3-28)
       * GET /explanations/{exception_id}/evidence
           - returns evidence graph (from P3-29).

2) Service layer:
   - src/services/explanation_service.py:
       * get_explanation(exception_id, format) -> dict/str
           - uses:
               · decision timelines
               · agent reasoning outputs
               · evidence tracking records.
       * search_explanations(...) -> list[ExplanationSummary]

3) Natural language format:
   - Build short NL summary by:
       * composing from stored reasoning
       * optionally using LLM to rephrase, but only using existing evidence (no new facts).

4) Versioning & history:
   - Model ExplanationVersion if needed (MVP can treat each pipeline run as version).
   - Expose version info in responses.

5) Tests:
   - tests/test_explanation_apis.py:
       * synthetic data for one exception
       * verify /explanations/{id}, /timeline, /evidence shapes
       * verify search endpoint filters correctly.

🔹 Prompt 31 — Explanation Integration with Audit & Metrics (P3-31)
Phase 3: Integrate explanations with audit and metrics (P3-31).

Spec refs:
- docs/phase3-mvp-issues.md Issue P3-31 (Explanation Integration with Audit and Metrics)
- docs/master_project_instruction_full.md Section 7 (Observability)

Goals:
- Link explanations to:
   * audit trail entries
   * metrics and outcomes
- Enable explanation-based analytics and quality scoring.

Tasks:
1) Audit integration:
   - In audit subsystem (e.g., src/observability/audit.py):
       * add fields on relevant events:
           - explanation_id or explanation_hash
           - explanation_quality_score (optional)
       * when an explanation is generated (P3-30), log corresponding audit record:
           - type="EXPLANATION_GENERATED"
           - metadata: exception_id, agent_names_involved, format.

2) Metrics integration:
   - Extend metrics subsystem to track:
       * explanations_generated_total
       * explanations_per_exception
       * explanation_latency_ms
   - Add hooks in explanation_service to record metrics.

3) Explanation quality:
   - Define simple quality heuristic in src/explainability/quality.py:
       * score_explanation(explanation) -> float
         - e.g., length, presence of evidence references, avoidance of "I don't know"-style filler.
   - Store quality scores in:
       * explanation metadata
       * metrics (histograms).

4) Analytics support:
   - Provide helper:
       * get_explanation_analytics(tenant_id, domain, window) -> dict
           - aggregates:
               · average quality score
               · correlation with resolution success/failure
               · correlation with MTTR.

5) Tests:
   - tests/test_explanation_integration.py:
       * ensure audit entries created when explanations generated
       * ensure metrics counters updated
       * verify quality scoring applied and retrievable.


If you’d like, next step I can:

Propose a Phase 3 “implementation order” checklist (a short plan you can pin in docs/phase3-prompts.md like we did for Phase 1/2), or

Help you craft Cursor workspace prompts to refactor or tidy once Phase 3 coding is mostly done (e.g., consolidate safety, quotas, red-team, explainability into clean packages).




retrofit for phase 3 remaining rompt : 
Context

We are implementing Phase 3 of the Domain-Abstracted Agentic Exception Platform.

This task corresponds to:

phase3-mvp-issues.md → Issue P3-10: Implement Guardrail Adjustment Recommendation System

Guardrails are defined in Domain Packs and Tenant Policy Packs (see docs/03-data-models-apis.md – Guardrails sections).

We already have:

PolicyAgent + guardrail enforcement from Phase 1

Rich metrics and outcome collection from Phase 2

Policy learning & optimization scaffolding from Phase 3 (severity & playbook recommendation).

Use existing patterns from:

Policy learning / optimization (severity rule recommender, playbook recommender)

Metrics & audit trail (Phase 2)

JSON-bounded suggestion schema we use for other recommendation engines.

Goal

Implement a Guardrail Adjustment Recommendation System that:

Analyzes policy violations, false positives, and false negatives for guardrails.

Suggests guardrail tuning & adjustments (thresholds, conditions, scopes).

Generates impact analysis for each recommendation (what would likely change).

Supports human review and approval workflow — recommendations are proposed, not auto-applied.

Tracks effectiveness over time, attached to metrics & audit.

Follow Issue P3-10 acceptance criteria exactly.

Files & Structure

Please create / update the following:

Core recommender implementation

src/learning/guardrail_recommender.py

Implement a GuardrailRecommender class that:

Consumes:

Historical exception decisions (including policy violations & guardrail checks)

Policy/guardrail configs from DomainPack and TenantPolicyPack

Metrics: false positives, false negatives, block/allow stats by guardrail

Produces:

A list of recommendations in a structured JSON-like Python dict format:

{
  "guardrailId": "...",
  "tenantId": "...",
  "currentConfig": { ... },
  "proposedChange": { ... },
  "reason": "short natural language explanation",
  "impactAnalysis": {
    "estimatedFalsePositiveChange": ...,
    "estimatedFalseNegativeChange": ...,
    "confidence": 0.0-1.0,
  },
  "reviewRequired": True,
  "createdAt": "...",
}


Provide methods like:

analyze_guardrail_performance(...)

generate_recommendations(...)

attach_impact_analysis(...)

Use simple, explainable heuristics for MVP:

Example: if a guardrail is causing very high false positives vs. false negatives, propose relaxing criteria; vice versa for tightening.

Integration with policy learning / optimization pipeline

Update src/learning/policy_learning.py (or equivalent Phase 3 policy-learning entry point) to:

Call GuardrailRecommender alongside the existing severity and playbook recommenders.

Combine outputs into a common “policy_learning_result” structure that includes:

severitySuggestions

playbookSuggestions

guardrailSuggestions

Ensure all suggestions are:

Logged into the audit trail

Tagged with tenant, domain, and time window analyzed.

API / service boundary for recommendation retrieval (backend only)

If we already have a metrics/learning API module (e.g., src/api/learning_routes.py or similar), add:

Endpoint stub (just backend wiring, no UI) to fetch guardrail recommendations per:

tenantId

optionally filtered by guardrailId.

Response is JSON that directly returns the structured recommendation objects.

Audit & tracking hooks

In our audit logging utility (where severity / playbook recommendations are logged), add:

Support to log guardrail recommendation events with a type like:

"eventType": "GUARDRAIL_RECOMMENDATION_GENERATED".

Ensure we also support:

"GUARDRAIL_RECOMMENDATION_ACCEPTED"

"GUARDRAIL_RECOMMENDATION_REJECTED"

These acceptance/rejection events can be triggered later by UX flows; for now it’s fine to assume corresponding methods exist or are TODO.

Docs

docs/learning/guardrail_recommender.md

Document:

Purpose of the Guardrail Recommender.

Inputs: metrics, policy logs, guardrail configs.

Output schema (same structure used in code).

Examples:

Overly strict rate-limit guardrail → suggestion to relax.

Overly permissive tool-scope guardrail → suggestion to tighten.

How it connects to PolicyAgent, Domain Pack, TenantPolicyPack, and Optimization Engine.

Tests

tests/learning/test_guardrail_recommender.py

Cover at least:

Case where guardrail is clearly too strict (very high false positives) → suggestion to relax.

Case where guardrail is clearly too lax (very high false negatives) → suggestion to tighten.

Case where performance is balanced → either no recommendation or low-confidence suggestion.

Ensure recommendations include:

impactAnalysis with non-null values.

reviewRequired is True.

Use in-memory fake data for metrics/decisions — no external dependencies.

Requirements & Constraints

Language: Python (consistent with the current codebase).

Style: Follow existing patterns used for:

Severity rule recommendation

Playbook recommendation

No domain hard-coding:

All logic must work generically across finance / healthcare / other domains, using only:

Domain Pack config

Tenant Policy Pack config

Metrics data

Config-driven thresholds:

Introduce simple, configurable thresholds (e.g. in a config module or constants) for:

“High false positive ratio”

“High false negative ratio”

Do not inline magic numbers.

Deliverable

Please:

Implement GuardrailRecommender and supporting code.

Integrate it into the existing policy learning / optimization pipeline.

Wire basic retrieval + audit hooks.

Add the documentation and unit tests described above.

When you respond, list the files you created/modified and briefly summarize the behavior of the Guardrail Adjustment Recommendation System.