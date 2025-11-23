# MVP Build Plan

## Phase 0: Foundations
- Implement canonical schema and validation.
- Build tenant routing and isolation (e.g., DB partitioning).
- Develop tool registry with basic CRUD.
- Set up per-tenant RAG (initial empty indexes).
- Milestones: Schema validator tool; tenant router prototype. Acceptance: Unit tests pass; isolation verified via mock tenants.

## Phase 1: MVP Agent
- Implement Intake, Triage, Policy agents.
- Basic Resolution with retry playbook.
- Integrate observability (logs, basic dashboard).
- Add audit trail logging.
- Milestones: End-to-end pipeline for single exception; metrics collection. Acceptance: 80% auto-resolution in test cases; audit completeness.

## Phase 2: Multi-Domain Expansion
- Build Domain Pack loader and validator.
- Extend tool registry for domain tools.
- Add domain-specific playbooks.
- Develop Admin UI for pack management.
- Milestones: Load sample Domain Pack; multi-domain simulation. Acceptance: Successful processing for 2+ domains; no cross-domain leakage.

## Phase 3: Learning Automation
- Implement FeedbackAgent with RAG updates.
- Add auto-playbook improvement (e.g., pattern detection).
- Enable recurrence detection via RAG similarity.
- Milestones: Feedback loop demo; reduced recurrence in tests. Acceptance: Learning improves resolution rate by 20% in simulations.

Dev Milestones: Weekly sprints; CI/CD pipeline; code coverage >80%.