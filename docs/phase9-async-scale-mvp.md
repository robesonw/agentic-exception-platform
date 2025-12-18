# Phase 9 – Async, Scale & Enterprise-Grade Orchestration MVP
SentinAI – Multi-Tenant, Domain-Abstracted Agentic Exception Platform

---

## 1. Purpose

Phase 9 transforms SentinAI from a synchronous, API-driven system into a **high-throughput, resilient, enterprise-scale platform** capable of:

- Processing **millions of exceptions per minute**
- Running agents **independently and horizontally scalable**
- Persisting every signal, decision, and outcome
- Supporting backpressure, retries, and failure isolation
- Preparing the platform for regulated, mission-critical environments

This phase introduces **asynchronous messaging**, **event-driven orchestration**, and **durable state guarantees**.

---

## 2. Core Goals (MVP)

1. Decouple agents using asynchronous messaging
2. Persist every inbound/outbound event durably
3. Support horizontal scaling of agent workers
4. Guarantee idempotency and ordering where required
5. Maintain tenant isolation at scale
6. Preserve the existing Actions & Playbooks semantics
7. Lay foundation for future AI learning & analytics

---

## 3. High-Level Architecture

### 3.1 Event-Driven Backbone

Introduce a message broker (pluggable):
- Kafka (primary target)
- Azure Event Hubs / AWS MSK
- Optional: RabbitMQ (non-streaming fallback)

Key idea:
> **APIs publish events; agents consume events. APIs never directly call agents.**

---

## 4. Canonical Event Model

All system activity flows through events.

### 4.1 Inbound Events
- ExceptionIngested
- ExceptionNormalized
- ManualExceptionCreated

### 4.2 Agent Events
- TriageRequested / TriageCompleted
- PolicyEvaluationRequested / Completed
- PlaybookMatched
- StepExecutionRequested
- ToolExecutionRequested / Completed
- FeedbackCaptured

### 4.3 Control & Ops Events
- RetryScheduled
- DeadLettered
- SLAImminent
- SLAExpired

Each event:
- Has a unique event_id
- Includes tenant_id, exception_id
- Is immutable
- Is persisted before processing

---

## 5. Agent Execution Model (Async)

### 5.1 Agent Workers

Each agent becomes an **independent worker service**:

- IntakeWorker
- TriageWorker
- PolicyWorker
- ResolutionWorker
- PlaybookWorker
- ToolWorker
- FeedbackWorker

Workers:
- Subscribe to specific event topics
- Are stateless
- Scale horizontally
- Use DB + Event Log for state

---

### 5.2 Agent Flow (Example)

1. ExceptionIngested → IntakeWorker
2. Intake emits ExceptionNormalized
3. TriageWorker consumes → emits TriageCompleted
4. PolicyWorker consumes → emits PlaybookMatched
5. PlaybookWorker drives step events
6. ToolWorker executes tools
7. FeedbackWorker captures metrics

No direct calls between agents.

---

## 6. Idempotency & Ordering

### 6.1 Idempotency
- Every handler must be idempotent
- Use event_id + consumer_group tracking
- Store processed event IDs per agent

### 6.2 Ordering
- Partition events by:
  - tenant_id
  - exception_id
- Ordering guaranteed per exception, not globally

---

## 7. Persistence & Reliability

### 7.1 Event Store
- Append-only event log (already exists from Phase 6)
- Events are source of truth

### 7.2 Dead Letter Queues
- Failed events after N retries go to DLQ
- DLQ entries visible in UI (Phase 10+)

### 7.3 Retry Strategy
- Exponential backoff
- Retry metadata stored with event

---

## 8. APIs in Phase 9

### 8.1 Command APIs (Fire-and-Forget)
APIs now:
- Validate request
- Persist command/event
- Publish to broker
- Return 202 Accepted

Examples:
- POST /exceptions
- POST /playbook/recalculate
- POST /tool/execute

### 8.2 Query APIs (Read Model)

**Status**: ✅ Complete (P9-19)

All GET endpoints follow the **read model pattern** - they read only from database projections without invoking agents or performing synchronous business logic.

**Key Principles:**
- **DB-only reads**: All GET endpoints use repository pattern to read from database tables
- **No agent calls**: Zero synchronous agent invocations in query endpoints
- **Fast queries**: Indexed queries with pagination for optimal performance
- **Tenant isolation**: All queries enforce tenant isolation at the database level

**Audited Endpoints:**
- `GET /api/exceptions/{tenant_id}` - Reads from `exception` table
- `GET /api/exceptions/{tenant_id}/{exception_id}` - Reads from `exception` and `exception_event` tables
- `GET /api/exceptions/{tenant_id}/{exception_id}/playbook` - Reads from `exception`, `playbook`, `playbook_step`, `exception_event` tables
- `GET /api/playbooks/{playbook_id}` - Reads from `playbook` table
- `GET /api/tools/executions` - Reads from `tool_execution` table
- `GET /api/tools/executions/{execution_id}` - Reads from `tool_execution` table

**Performance Characteristics:**
- **Single record queries** (GET by ID): < 10ms expected response time
- **List queries with filters** (GET with pagination): < 50ms expected response time
- **Complex queries** (playbook status with events): < 100ms expected response time
- **Database load**: Read-only operations, no write locks, indexed lookups

**Architecture Compliance:**
- ✅ Command-Query Separation (CQRS): Commands publish events (202 Accepted), Queries read from DB (200 OK)
- ✅ Event Sourcing Read Model: Read model built from exception table, event table, playbook/step tables, tool execution table
- ✅ No Synchronous Agent Invocations: Confirmed zero agent calls in GET endpoints

See `docs/phase9-query-apis-audit.md` for detailed audit results.
- Read from DB projections
- No synchronous agent invocation

---

## 9. Scalability Targets (MVP)

- ≥ 1M events/min sustained
- Horizontal scale per agent type
- Zero cross-tenant data leakage
- Backpressure protection per tenant

---

## 10. Observability & Ops

### 10.1 Metrics
- Events/sec per agent
- Processing latency
- Failure rates
- SLA breaches

### 10.2 Tracing
- Correlation ID = exception_id
- Trace across agents via event metadata

---

## 11. Security & Compliance

- Tenant isolation at topic + DB layer
- Encryption in transit
- PII redaction at ingestion
- Full audit trail from event store

---

## 12. Out of Scope (Phase 9)

- ML model training
- Auto-learning policies
- Cross-exception correlation
- UI for DLQ management
- Multi-region replication

---

## 13. Exit Criteria

Phase 9 is complete when:

### Backend
- Agents run asynchronously via broker
- APIs no longer call agents directly
- Event-driven orchestration works end-to-end
- Tool execution works async
- Idempotency + retry enforced

### Ops
- Horizontal scaling demonstrated
- Failure isolation validated

### Docs
- Architecture updated
- Runbook added

---

## 14. What Phase 9 Enables Next

- Phase 10: AI learning & optimization
- Phase 11: Advanced ops dashboards
- Phase 12: Marketplace & ecosystem
