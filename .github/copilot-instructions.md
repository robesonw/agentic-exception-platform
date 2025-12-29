# SentinAI Exception Processing Platform — Copilot Engineering Instructions

> Purpose: Keep AI-assisted coding (Copilot/Claude) aligned to the platform’s enterprise, multi-tenant, event-driven architecture.
> These are HARD RULES unless a doc explicitly overrides them.

---

## 0) SOURCE OF TRUTH (MUST READ BEFORE CHANGES)

When uncertain, search these **before inventing**:

1. `CLAUDE.md` (project rules + current state)
2. `docs/01-architecture.md` … `docs/STATE_OF_THE_PLATFORM.md`
3. `docs/06-mvp-plan.md` (phase ordering)
4. `.github/issue_template/*` (phase issue lists)
5. `docs/phase13-copilot-intelligence-mvp.md` (pgvector + RAG + Copilot)

**If a requirement seems missing:** do NOT guess. Add a small TODO note + ask for clarification or create a doc patch proposal.

---

## 1) CRITICAL ARCHITECTURE PRINCIPLES (NON-NEGOTIABLE)

### 1.1 Multi-Tenant Isolation Everywhere

Tenant isolation is enforced across:

- Database tables / queries
- Registry keys
- Tool execution
- Event topics/partitioning
- RAG retrieval (pgvector)
- Audit access (RBAC)
- UI routing/state

**Rule:** every persisted record and query that involves customer data must include `tenant_id`.  
**Rule:** every API endpoint touching tenant data must enforce tenant scope.

### 1.2 Domain-Abstracted Core

- NO domain-specific logic in core platform code.
- All behavior must be config-driven via:
  - Domain Packs (`domainpacks/`)
  - Tenant Packs (`tenantpacks/`)
- Do not hardcode Finance/Healthcare rules in services/agents.

### 1.3 Event-Driven Processing (202 Accepted)

APIs publish events and return `202 Accepted`. Workers do the work asynchronously.

**Rule:** API endpoints must not “do the worker’s job” inline unless explicitly documented (rare).
**Rule:** events must include `tenant_id` and use `partition_key=tenant_id`.

### 1.4 Strict Pipeline Ordering

1. IntakeWorker → normalize
2. TriageWorker → classify/severity
3. PolicyWorker → tenant policy eval
4. PlaybookWorker → match playbooks
5. ToolWorker → execute allow-listed tools only
6. FeedbackWorker → capture results + close loop

**Rule:** do not reorder or bypass stages.

---

## 2) WHAT NOT TO DO (ANTI-PATTERNS)

- NEVER query or write tenant data without tenant filter.
- NEVER execute tools from free-text. Tools must be typed + allow-listed.
- NEVER log secrets or PHI/PII.
- NEVER create a second scheduler framework. Reuse the existing job/worker mechanism.
- NEVER add “domain logic” inside agent code; agents must interpret config.
- NEVER return 200 OK when an async event was published; use 202 Accepted pattern.
- NEVER create “magic defaults” that change business logic silently.

---

## 3) CODING RULES (GUARDRAILS THAT PREVENT DRIFT)

### 3.1 Repository/Service boundaries

- DB access goes through repositories (tenant-scoped methods).
- Business logic goes in services.
- API routes should be thin (validate → call service → publish event → 202).

### 3.2 Backward compatibility

If the platform supports file-based packs and DB packs:

- Keep compatibility unless a doc says to remove it.
- Prefer DB active config; file fallback only when configured.

### 3.3 Data contracts are strict

- Output structures must match canonical schemas in `docs/03-data-models-apis.md`.
- For Copilot/RAG: response must be structured (answer, bullets, citations, recommended_playbook, safety).

### 3.4 Errors and responses

- Use consistent error model (existing project pattern).
- Provide meaningful messages (no stack traces in UI).
- 403 -> Not Authorized view (UI), not generic crash.

---

## 4) SECURITY, COMPLIANCE, REDACTION (ENTERPRISE)

### 4.1 Never log secrets

Redact:

- API keys, tokens, auth headers
- credentials
- patient data/PHI
- personal identifiers if present in exceptions

### 4.2 Audit everything important

All actions that change state must create an audit trail:

- tenant create/suspend
- pack import/validate/activate
- tool enable/disable
- playbook changes
- rate limits, alert configs
- config governance approvals

### 4.3 RBAC rules

- Admin endpoints require admin role.
- Tenant admin can only view/manage their tenant.
- Audit must be tenant-scoped (unless global admin dashboard).

---

## 5) EVENT-DRIVEN PROCESSING PATTERNS

### API Pattern (Publish then 202)

```python
await event_publisher.publish_event(
    topic="exceptions",
    event=payload,
    partition_key=tenant_id
)
return {"status": "accepted"}, 202
```

Worker Pattern (Kafka consumer)

Workers must be scalable and idempotent.

Consumer groups per stage

Idempotency keys where applicable

Retry/backoff consistent with existing infrastructure

6. DOMAIN PACKS / TENANT PACKS RULES
   6.1 Loading

Always load packs via registry with tenant context:

DomainPackRegistry.get(domain_name, tenant_id=...)

6.2 Validation

Packs must be validated before activation:

schema validation

required fields

unsupported keys

cross references (playbooks/tools/classifiers)

6.3 Versioning

Multiple versions may exist

Activation must be explicit + auditable

Never overwrite a previous version

7. TOOLS & PLAYBOOKS RULES
   7.1 Tools

typed

allow-listed

never invoked from free text

execution requires explicit approval path if policy demands

7.2 Playbooks

playbooks are config-driven workflows

Phase 13 adds a read-only workflow viewer (graph), not an editor

step execution events must map cleanly to playbook steps

8. COPILOT / RAG / PGVECTOR RULES (PHASE 13+)
   8.1 Retrieval is tenant-scoped

All similarity searches must filter by tenant.
Domain scoping is optional but preferred when available.

8.2 Citations are mandatory

Any Copilot response must include citations when using retrieved evidence:

policy_doc

resolved_exception

audit_event

tool_registry

playbook

8.3 Safe-by-default Copilot

Copilot is READ_ONLY by default.

It may suggest actions but cannot execute.

Any “actionable step” must go through approvals/governance.

8.4 Embeddings and dimensions

Keep embedding dimension consistent with DB schema.

Provider is pluggable; do not hardcode to one model.

Batch embeddings and cache when possible.

8.5 Indexing

Use existing worker/job mechanism (no new scheduler framework).

Indexing must be incremental, based on content hash/version.

Never index secrets/PHI.

9. UI RULES (REACT)

No placeholders/“Under Construction” in routes that exist in sidebar.

Always implement loading + empty + error states.

Use existing UI components (tables, dialogs, code viewer, toasts).

API client must be typed and centralized.

For admin ops pages: always show filters and tenant scoping clearly.

10. TESTING REQUIREMENTS (DO NOT SKIP)

Minimum for any meaningful change:

Unit tests for new services/repositories

Multi-tenant test coverage (at least 2 tenants) for:

isolation

RAG retrieval

audit queries

Integration test for “happy path” per phase (E2E async flow when relevant)

Rule: do not merge if tests are failing.

11. DATABASE + MIGRATIONS

Use Alembic migrations only.

Add indexes for tenant-scoped queries.

For pgvector: ensure proper index strategy is planned (IVFFlat/HNSW later if needed).

Never change existing columns/types without a migration and data migration plan.

12. PERFORMANCE & SCALE GUIDELINES

The platform must support high throughput:

API returns quickly (publish event + 202)

Workers scale horizontally

DB queries must be indexed on (tenant_id, created_at) and similar

Avoid synchronous fan-out calls in worker hot paths

Prefer batching for embeddings and indexing

13. WORKING STYLE FOR AI ASSISTANTS (COPILOT/CLAUDE)

When asked to implement:

Restate which spec/issue you are implementing (file + section).

List files you will change.

Implement minimal, correct solution.

Add tests.

Provide a manual verification checklist.

If a requirement is ambiguous:

Do NOT invent behavior.

Add a short doc note or TODO and surface the question.

Essential Commands
Local Dev
make up

Start Workers
WORKER_TYPE=intake CONCURRENCY=1 GROUP_ID=intake-workers python -m src.workers
WORKER_TYPE=triage CONCURRENCY=1 GROUP_ID=triage-workers python -m src.workers

Run E2E Test
pytest tests/integration/test_e2e_async_flow.py -k tenant_isolation

Debugging

Worker logs: docker-compose logs -f

Kafka UI (if enabled): http://localhost:8080

Verify tenants: use existing scripts/tests

Missing processing? Ensure workers are running for each stage

Read CLAUDE.md, docs/01-architecture.md, and docs/WORKERS_QUICK_START.md for detailed specifications.
