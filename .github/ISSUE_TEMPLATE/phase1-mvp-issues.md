# Phase 1 MVP - GitHub Issues Checklist

## Component: Gateway / Tenant Router

### Issue 1: Implement Tenant Router with Authentication and Routing
**Labels:** `component:gateway`, `phase:1`, `priority:high`
**Description:**
- Implement tenant identification from incoming requests (JWT/API keys)
- Route requests to tenant-specific pipelines
- Add rate limiting per tenant
- Support API versioning
- Ensure tenant isolation at routing layer

**Acceptance Criteria:**
- [ ] Tenant ID extracted from authenticated requests
- [ ] Requests routed to correct tenant pipeline
- [ ] Rate limiting enforced per tenant
- [ ] API versioning supported
- [ ] Unit tests with mock tenants verify isolation

---

### Issue 2: Implement Request Authentication and Authorization
**Labels:** `component:gateway`, `phase:1`, `priority:high`
**Description:**
- Implement JWT token validation
- Support API key authentication
- Enforce RBAC with tenant-scoped sessions
- Add security logging for auth failures

**Acceptance Criteria:**
- [ ] JWT tokens validated and tenant ID extracted
- [ ] API key authentication supported
- [ ] Tenant-scoped sessions enforced
- [ ] Auth failures logged securely
- [ ] Unit tests for auth scenarios

---

## Component: Exception Ingestion Service

### Issue 3: Implement Exception Ingestion Service with Canonical Schema Normalization
**Labels:** `component:ingestion`, `phase:1`, `priority:high`
**Description:**
- Parse raw inputs from connectors (REST, file watchers)
- Normalize to canonical exception schema
- Extract tenantId, sourceSystem, timestamp, rawPayload
- Enqueue normalized exceptions for orchestration
- Validate schema compliance

**Acceptance Criteria:**
- [ ] Raw exceptions parsed from REST API
- [ ] Normalization to canonical schema implemented
- [ ] Required fields extracted (tenantId, sourceSystem, timestamp, rawPayload)
- [ ] Schema validation passes
- [ ] Exceptions enqueued for agent orchestrator
- [ ] Unit tests with sample exceptions

---

### Issue 4: Implement REST Ingestion API Endpoint
**Labels:** `component:ingestion`, `phase:1`, `priority:high`
**Description:**
- Implement POST /exceptions/{tenantId} endpoint
- Accept raw exception payloads
- Return exceptionId after ingestion
- Add request validation and error handling

**Acceptance Criteria:**
- [ ] POST /exceptions/{tenantId} endpoint functional
- [ ] Returns exceptionId in response
- [ ] Request validation implemented
- [ ] Error handling for invalid payloads
- [ ] Integration tests for API endpoint

---

## Component: Agent Orchestrator

### Issue 5: Implement Agent Orchestrator with Pipeline Coordination
**Labels:** `component:orchestrator`, `phase:1`, `priority:high`
**Description:**
- Coordinate agent pipeline (Intake → Triage → Policy → Resolution → Feedback)
- Invoke agents sequentially based on workflow
- Manage state between agent calls
- Handle retries and error recovery
- Support conditional branching based on agent decisions

**Acceptance Criteria:**
- [ ] Agent pipeline orchestration implemented
- [ ] Agents invoked in correct sequence
- [ ] State passed between agents
- [ ] Retry logic for failed agent calls
- [ ] Conditional branching based on nextStep decisions
- [ ] Unit tests for orchestration flow

---

### Issue 6: Implement Agent Communication Contracts
**Labels:** `component:orchestrator`, `phase:1`, `priority:medium`
**Description:**
- Define standardized agent input/output contracts
- Implement message passing between agents
- Support agent response format: {decision, confidence, evidence, nextStep}
- Handle inter-agent context passing

**Acceptance Criteria:**
- [ ] Agent contracts defined and validated
- [ ] Message passing between agents functional
- [ ] Response format matches specification
- [ ] Context preserved across agent calls
- [ ] Unit tests for contract validation

---

## Component: IntakeAgent

### Issue 7: Implement IntakeAgent with Normalization Logic
**Labels:** `component:agent:intake`, `phase:1`, `priority:high`
**Description:**
- Implement IntakeAgent following agent template
- Normalize raw exception payload to canonical schema
- Extract tenantId, sourceSystem, timestamp, rawPayload
- Infer exceptionType from Domain Pack taxonomy if possible
- Output standardized agent response format

**Acceptance Criteria:**
- [ ] IntakeAgent implemented with LLM integration
- [ ] Normalization to canonical schema works
- [ ] Required fields extracted correctly
- [ ] ExceptionType inference from Domain Pack
- [ ] Output matches agent response format
- [ ] Unit tests with sample raw exceptions

---

## Component: TriageAgent

### Issue 8: Implement TriageAgent with Classification and Severity Scoring
**Labels:** `component:agent:triage`, `phase:1`, `priority:high`
**Description:**
- Implement TriageAgent following agent template
- Classify exceptionType using Domain Pack taxonomy
- Score severity using severityRules from Domain Pack
- Query RAG for root cause analysis and similar exceptions
- Generate diagnostic summary
- Calculate confidence based on match strength

**Acceptance Criteria:**
- [ ] TriageAgent implemented with LLM integration
- [ ] ExceptionType classification functional
- [ ] Severity scoring using Domain Pack rules
- [ ] RAG query integration for root cause
- [ ] Diagnostic summary generated
- [ ] Confidence score calculated
- [ ] Unit tests with sample exceptions

---

## Component: PolicyAgent

### Issue 9: Implement PolicyAgent with Guardrail Enforcement
**Labels:** `component:agent:policy`, `phase:1`, `priority:high`
**Description:**
- Implement PolicyAgent following agent template
- Evaluate triage output against Tenant Policy Pack guardrails
- Check allow-lists and block-lists
- Apply humanApprovalRules based on severity
- Approve or block suggested actions
- Output decision with evidence

**Acceptance Criteria:**
- [ ] PolicyAgent implemented with LLM integration
- [ ] Guardrail evaluation functional
- [ ] Allow-list/block-list checks implemented
- [ ] Human approval rules applied
- [ ] Approval/blocking decisions made correctly
- [ ] Evidence provided for decisions
- [ ] Unit tests with various policy scenarios

---

## Component: ResolutionAgent

### Issue 10: Implement Basic ResolutionAgent with Retry Playbook
**Labels:** `component:agent:resolution`, `phase:1`, `priority:high`
**Description:**
- Implement ResolutionAgent following agent template
- Select playbook from Domain/Tenant Packs matching exceptionType
- Execute basic retry playbook
- Invoke approved tools sequentially
- Update resolutionStatus
- Handle tool failures with retry logic

**Acceptance Criteria:**
- [ ] ResolutionAgent implemented with LLM integration
- [ ] Playbook selection from packs functional
- [ ] Basic retry playbook implemented
- [ ] Tool invocation via registry works
- [ ] Resolution status updated correctly
- [ ] Retry logic handles failures
- [ ] Unit tests for resolution scenarios

---

## Component: Skill/Tool Registry

### Issue 11: Implement Tool Registry with Basic CRUD Operations
**Labels:** `component:tool-registry`, `phase:1`, `priority:high`
**Description:**
- Implement tenant-scoped tool registry (key-value store)
- Support tool registration with name, description, parameters, endpoint
- Implement allow-list status tracking
- Add tool lookup and invocation interfaces
- Validate tools against Domain Pack tool definitions

**Acceptance Criteria:**
- [ ] Tool registry implemented with tenant isolation
- [ ] CRUD operations for tools functional
- [ ] Tool definitions stored with required fields
- [ ] Allow-list status tracked
- [ ] Tool lookup and invocation interfaces work
- [ ] Validation against Domain Pack tools
- [ ] Unit tests for registry operations

---

### Issue 12: Implement Tool Invocation Interface
**Labels:** `component:tool-registry`, `phase:1`, `priority:medium`
**Description:**
- Implement tool invocation via HTTP/gRPC
- Support sandboxed execution
- Handle tool responses and errors
- Integrate with ResolutionAgent for tool calls
- Add tool execution audit logging

**Acceptance Criteria:**
- [ ] Tool invocation interface implemented
- [ ] HTTP/gRPC calls functional
- [ ] Sandboxed execution supported
- [ ] Error handling for tool failures
- [ ] Integration with ResolutionAgent
- [ ] Audit logging for tool executions
- [ ] Unit tests for tool invocation

---

## Component: Memory Layer (RAG)

### Issue 13: Implement Per-Tenant RAG Index Setup
**Labels:** `component:memory`, `phase:1`, `priority:high`
**Description:**
- Set up per-tenant vector database (e.g., FAISS or in-memory for MVP)
- Create namespaced indexes per tenant
- Implement basic embedding generation for exceptions
- Support initial empty indexes for new tenants
- Ensure tenant isolation in memory layer

**Acceptance Criteria:**
- [ ] Per-tenant vector database setup
- [ ] Namespaced indexes per tenant
- [ ] Embedding generation for exceptions
- [ ] Empty index creation for new tenants
- [ ] Tenant isolation verified
- [ ] Unit tests for RAG operations

---

### Issue 14: Implement RAG Query Interface for TriageAgent
**Labels:** `component:memory`, `phase:1`, `priority:medium`
**Description:**
- Implement similarity search in RAG index
- Support querying for similar exceptions
- Return relevant historical exceptions and resolutions
- Integrate with TriageAgent for root cause analysis
- Add query result ranking

**Acceptance Criteria:**
- [ ] Similarity search implemented
- [ ] Query interface for similar exceptions
- [ ] Historical exceptions and resolutions returned
- [ ] Integration with TriageAgent functional
- [ ] Query results ranked by relevance
- [ ] Unit tests for RAG queries

---

## Component: Audit & Observability System

### Issue 15: Implement Audit Trail Logging
**Labels:** `component:audit`, `phase:1`, `priority:high`
**Description:**
- Log all agent decisions and actions
- Capture timestamps, tenantId, actor for each action
- Store audit trail in exception schema
- Ensure audit completeness for all pipeline steps
- Support audit trail querying

**Acceptance Criteria:**
- [ ] All agent decisions logged
- [ ] Timestamps and tenantId captured
- [ ] Actor identification for actions
- [ ] Audit trail stored in exception schema
- [ ] Completeness verified for all steps
- [ ] Query interface for audit trails
- [ ] Unit tests for audit logging

---

### Issue 16: Implement Basic Observability (Logs and Metrics)
**Labels:** `component:observability`, `phase:1`, `priority:medium`
**Description:**
- Implement structured logging for all components
- Expose metrics (e.g., Prometheus format): autoResolutionRate, MTTR, exception counts
- Add basic metrics collection for agent performance
- Support log aggregation and querying
- Ensure tenant-scoped metrics

**Acceptance Criteria:**
- [ ] Structured logging implemented
- [ ] Metrics exposed in Prometheus format
- [ ] Auto-resolution rate tracked
- [ ] MTTR (Mean Time To Resolution) calculated
- [ ] Agent performance metrics collected
- [ ] Tenant-scoped metrics isolation
- [ ] Unit tests for metrics collection

---

### Issue 17: Implement Basic Dashboard for Metrics Visualization
**Labels:** `component:observability`, `phase:1`, `priority:low`
**Description:**
- Create basic dashboard (e.g., simple HTML/JS or Grafana)
- Display key metrics: autoResolutionRate, MTTR, exception counts
- Show per-tenant metrics
- Support real-time updates
- Add basic charts and visualizations

**Acceptance Criteria:**
- [ ] Basic dashboard implemented
- [ ] Key metrics displayed
- [ ] Per-tenant metrics shown
- [ ] Real-time updates functional
- [ ] Charts and visualizations added
- [ ] Integration tests for dashboard

---

## Component: System APIs

### Issue 18: Implement Status API Endpoint
**Labels:** `component:api`, `phase:1`, `priority:medium`
**Description:**
- Implement GET /exceptions/{tenantId}/{exceptionId} endpoint
- Return full exception schema with current status
- Include audit trail in response
- Add proper error handling for not found cases

**Acceptance Criteria:**
- [ ] GET /exceptions/{tenantId}/{exceptionId} endpoint functional
- [ ] Full exception schema returned
- [ ] Audit trail included in response
- [ ] Error handling for missing exceptions
- [ ] Integration tests for status API

---

### Issue 19: Implement Metrics API Endpoint
**Labels:** `component:api`, `phase:1`, `priority:medium`
**Description:**
- Implement GET /metrics/{tenantId} endpoint
- Return metrics: {autoResolutionRate, mttr, exceptionCounts, etc.}
- Support tenant-scoped metrics
- Add proper authentication and authorization

**Acceptance Criteria:**
- [ ] GET /metrics/{tenantId} endpoint functional
- [ ] Required metrics returned
- [ ] Tenant-scoped metrics isolation
- [ ] Authentication and authorization enforced
- [ ] Integration tests for metrics API

---

## Component: Testing & Quality

### Issue 20: Implement End-to-End Pipeline Test
**Labels:** `component:testing`, `phase:1`, `priority:high`
**Description:**
- Create end-to-end test for single exception processing
- Test full pipeline: Intake → Triage → Policy → Resolution → Feedback
- Verify 80% auto-resolution rate in test cases
- Validate audit trail completeness
- Test with sample Domain Pack and Tenant Policy Pack

**Acceptance Criteria:**
- [ ] End-to-end test implemented
- [ ] Full pipeline tested
- [ ] 80% auto-resolution rate achieved in tests
- [ ] Audit trail completeness verified
- [ ] Tests use sample packs
- [ ] Test results documented

---

### Issue 21: Implement Unit Tests for All Components
**Labels:** `component:testing`, `phase:1`, `priority:high`
**Description:**
- Write unit tests for all Phase 1 components
- Achieve >80% code coverage
- Test tenant isolation in all components
- Mock external dependencies (LLM, vector DB, etc.)
- Ensure all tests pass

**Acceptance Criteria:**
- [ ] Unit tests for all components
- [ ] Code coverage >80%
- [ ] Tenant isolation tested
- [ ] External dependencies mocked
- [ ] All tests passing
- [ ] Test coverage report generated

---

## Summary

**Total Issues:** 21
**High Priority:** 13
**Medium Priority:** 6
**Low Priority:** 2

**Components Covered:**
- Gateway / Tenant Router (2 issues)
- Exception Ingestion Service (2 issues)
- Agent Orchestrator (2 issues)
- IntakeAgent (1 issue)
- TriageAgent (1 issue)
- PolicyAgent (1 issue)
- ResolutionAgent (1 issue)
- Skill/Tool Registry (2 issues)
- Memory Layer / RAG (2 issues)
- Audit & Observability System (3 issues)
- System APIs (2 issues)
- Testing & Quality (2 issues)

