# Test Plan

## Unit-Level Scenarios
- IntakeAgent: Test normalization on varied payloads; assert schema compliance.
- TriageAgent: Mock Domain Pack; test classification/severity on edge cases.
- PolicyAgent: Simulate guardrail violations; assert blocking.
- ResolutionAgent: Mock tools; test playbook execution.
- FeedbackAgent: Test RAG updates post-resolution.

## Integration-Level Test Matrix
- Pipeline: End-to-end with sample exceptions; vary tenants/domains.
- Multi-Tenant: Parallel processing; assert no data crossover.
- Tool Invocation: Success/failure scenarios; audit checks.

## Domain Pack Test Suites
- Validation: Schema checks on pack load.
- Execution: Run pack's testSuites; assert outputs match expected.

## Multi-Tenant Tests
- Isolation: Create tenants; inject data; query for leakage.
- Scaling: Load test with 100+ tenants.

## Safety/Guardrail Tests
- Block unapproved tools; enforce human approval.
- Low-confidence escalation; no unauthorized actions.

## Observability Validation
- Metrics accuracy; dashboard rendering; alert triggering.