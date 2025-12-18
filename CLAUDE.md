# Claude Project Rules — SentinAI

You are coding an enterprise Domain-Abstracted Agentic AI Platform for multi-tenant Exception Processing.

## SOURCE OF TRUTH

- docs/master_project_instruction_full.md
- docs/01-architecture.md ... docs/09-tenant-onboarding.md
- docs/06-mvp-plan.md defines milestones and order of implementation.
- docs/phase7-playbooks-mvp.md, docs/phase8-tools-mvp.md, docs/phase9-async-scale-mvp.md (if present)

## HARD RULES (must follow)

1. Do not introduce domain-specific logic in core platform code.
2. All behavior must be config-driven via Domain Packs and Tenant Policy Packs.
3. Enforce tenant isolation in every storage/memory/tool boundary.
4. Agents must follow the workflow:
   Intake → Triage → Policy → Resolution → Feedback.
5. Tools are typed, schema-validated, allow-listed, and never called from free text.
6. Every action must generate an audit trail (EventStore + tool_execution records where relevant).
7. Output structures must match canonical schemas in docs/03-data-models-apis.md.
8. If any requirement seems missing, search the docs before inventing new behavior.
9. Prefer simple MVP implementations in Phase 1; advanced automation belongs to later phases.
10. Keep diffs minimal and consistent with existing repo patterns.

## WORKFLOW RULES

- For each issue:
  1. restate which spec section + issue you are implementing
  2. implement the smallest correct change
  3. add/adjust tests
  4. show how to run tests locally
- Never log secrets (mask/redact).
- Add deterministic tests (seeded data where needed).
