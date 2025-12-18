# Claude Context – How to Work in This Repo

## What this system is

SentinAI is a multi-tenant, domain-abstracted exception processing platform.
It uses:

- DB persistence (Postgres)
- Append-only event log as audit trail
- Agents pipeline: Intake → Triage → Policy → Resolution → Feedback
- Playbooks for step-based resolution
- Tool Registry + Tool Execution with schema validation and allow-lists
- (Later) async event-driven workers via Kafka

## Key invariants

- Tenant isolation everywhere (API, DB queries, events, tools)
- No domain-specific logic in core services
- Domain/Tenant configuration lives in Domain Packs and Tenant Policy Packs
- All side effects must be auditable (events + persisted records)

## Preferred engineering style

- Keep changes minimal and consistent with existing patterns
- Add tests for every behavior change
- Favor explicit types and Pydantic models for payload boundaries
- Use repositories/services; avoid direct DB access in routes

## Test commands (adjust based on repo)

- Backend: pytest -q
- UI: npm test (or pnpm/yarn equivalent)
- Lint/typecheck if configured

## Local run

See docs/run-local.md (if present). Prefer docker-compose for dependencies.
