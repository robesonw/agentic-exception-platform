# Phase 1 Stabilization Plan (Urgent)

## Goal

Make Phase 1 fully testable and orchestrated end-to-end with deterministic behavior.

## Scope checklist

1. Agents pipeline runs in correct order:
   Intake → Triage → Policy → Resolution → Feedback
2. Each stage produces durable events (audit trail)
3. Tenant isolation verified in services + repos
4. Deterministic tests:
   - unit tests for each agent stage
   - integration test for full pipeline
5. Stable local run instructions

## Deliverables

- tests/integration/test_phase1_e2e.py
- scripts/run_phase1_smoke.py (optional helper)
- docs/run-local.md updated with Phase 1 smoke steps

## Acceptance criteria

- `pytest -q` passes consistently
- End-to-end test creates an exception and verifies:
  - classification fields present
  - policy decision recorded
  - resolution suggestion present
  - feedback metrics recorded
  - events written for each stage
