# Claude Project Rules — SentinAI

SentinAI is an enterprise-grade, multi-tenant, domain-abstracted exception processing platform.
Current system is **persisted + event-driven + async** (Kafka + workers) with UI + APIs.

## CURRENT SYSTEM TRUTH (read first)

- docs/STATE_OF_THE_PLATFORM.md ← authoritative description of what exists today
- docs/run-local.md ← how to run API/UI/Kafka/workers locally

## DESIGN / CONTRACTS

- docs/01-architecture.md
- docs/03-data-models-apis.md
- docs/phase7-playbooks-mvp.md
- docs/phase8-tools-mvp.md
- docs/phase9-async-scale-mvp.md
- .github/issue_template/phase\*.md

## NON-NEGOTIABLE RULES

1. No domain-specific logic in core platform code.
2. Behavior must be config-driven via Domain Packs and Tenant Policy Packs.
3. Enforce tenant isolation everywhere (API, DB, events, tools).
4. Agent pipeline order remains: Intake → Triage → Policy → Resolution → Feedback
   (now implemented as async workers consuming/publishing events).
5. APIs are command/query separated:
   - Commands persist event + publish to Kafka and return 202
   - Queries read DB only (no agent calls)
6. Tools are schema-validated, allow-listed, and executed via ToolExecutionService/ToolWorker.
7. Every decision/side effect must be auditable (EventStore + tool_execution etc).
8. Never log secrets/PII (mask/redact).

## WORKFLOW

For each task:

- Restate issue + relevant spec section
- Reuse existing repo patterns; minimal diffs
- Add deterministic tests
- Provide exact commands to run tests
- Update docs when behavior changes

## OUTPUT FORMAT

End each implementation with:

- Changed files
- How to test
- Risks/follow-ups
