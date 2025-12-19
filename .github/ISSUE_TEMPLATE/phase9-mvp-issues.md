# Phase 9 Async, Scale & Enterprise-Grade Orchestration MVP - GitHub Issues Checklist

## Component: Message Broker Infrastructure

### Issue P9-1: Implement Message Broker Abstraction Layer
**Labels:** `component:message-broker`, `phase:9`, `priority:high`
**Description:**
- Create pluggable message broker abstraction interface:
  - Support Kafka (primary), Azure Event Hubs, AWS MSK, RabbitMQ (fallback)
  - Abstract publish/subscribe operations
  - Support topic creation and configuration
  - Handle connection management and retries
- Implement Kafka provider as primary implementation:
  - Use kafka-python or confluent-kafka library
  - Support producer and consumer configuration
  - Handle connection pooling and error recovery
- Add broker configuration in settings (env vars)
- Reference: docs/phase9-async-scale-mvp.md Section 3.1

**Dependencies:** None (foundational)

**Acceptance Criteria:**
- [ ] Message broker abstraction interface created
- [ ] Kafka provider implemented
- [ ] Broker configuration via environment variables
- [ ] Connection management and retry logic functional
- [ ] Producer and consumer abstractions working
- [ ] Unit tests for broker abstraction
- [ ] Integration tests with Kafka (or test broker)

---

### Issue P9-2: Implement Event Publisher Service
**Labels:** `component:message-broker`, `phase:9`, `priority:high`
**Description:**
- Implement EventPublisherService:
  - `publish_event(topic, event_data, partition_key=None)` method
  - Support event serialization (JSON)
  - Handle publish failures with retry logic
  - Support partitioning by tenant_id or exception_id
  - Ensure events are persisted before publishing (at-least-once semantics)
- Integrate with message broker abstraction
- Add event publishing to audit trail
- Reference: docs/phase9-async-scale-mvp.md Section 3.1, Section 4

**Dependencies:** P9-1

**Acceptance Criteria:**
- [ ] EventPublisherService implemented
- [ ] Event serialization functional
- [ ] Partitioning by tenant_id/exception_id working
- [ ] Retry logic for publish failures implemented
- [ ] Event persistence before publishing enforced
- [ ] Integration with broker abstraction working
- [ ] Unit tests for publisher service
- [ ] Integration tests for event publishing

---

## Component: Canonical Event Model

### Issue P9-3: Implement Canonical Event Schema and Event Types
**Labels:** `component:events`, `phase:9`, `priority:high`
**Description:**
- Define canonical event schema with fields:
  - event_id (uuid), event_type (string)
  - tenant_id, exception_id (nullable)
  - timestamp, correlation_id
  - payload (jsonb), metadata (jsonb)
  - version (for schema evolution)
- Implement event type definitions:
  - Inbound: ExceptionIngested, ExceptionNormalized, ManualExceptionCreated
  - Agent: TriageRequested, TriageCompleted, PolicyEvaluationRequested, PolicyEvaluationCompleted, PlaybookMatched, StepExecutionRequested, ToolExecutionRequested, ToolExecutionCompleted, FeedbackCaptured
  - Control: RetryScheduled, DeadLettered, SLAImminent, SLAExpired
- Create Pydantic models for each event type
- Ensure events are immutable and versioned
- Reference: docs/phase9-async-scale-mvp.md Section 4

**Dependencies:** None

**Acceptance Criteria:**
- [ ] Canonical event schema defined
- [ ] All event types implemented as Pydantic models
- [ ] Event immutability enforced
- [ ] Versioning support added
- [ ] Event validation functional
- [ ] Unit tests for event schemas
- [ ] Schema evolution considerations documented

---

### Issue P9-4: Implement Event Store Persistence Layer
**Labels:** `component:events`, `phase:9`, `priority:high`
**Description:**
- Enhance existing event store (from Phase 6) or create new event_log table:
  - Store all events before processing (append-only)
  - Fields: event_id, event_type, tenant_id, exception_id, timestamp, correlation_id, payload, metadata, version
  - Index on tenant_id, exception_id, event_type, timestamp
- Implement EventStoreRepository:
  - `store_event(event)` - append event to log
  - `get_events_by_exception(exception_id, filters)` - query events for exception
  - `get_events_by_tenant(tenant_id, filters)` - query events for tenant
  - Support pagination and filtering
- Ensure events are source of truth for system state
- Reference: docs/phase9-async-scale-mvp.md Section 7.1

**Dependencies:** P9-3, P6-1 (Database Setup)

**Acceptance Criteria:**
- [ ] Event store table created/enhanced
- [ ] Database migration implemented
- [ ] EventStoreRepository implemented
- [ ] Event persistence before processing enforced
- [ ] Query methods functional with pagination
- [ ] Indexes created for performance
- [ ] Unit tests for repository
- [ ] Integration tests with database

---

## Component: Agent Workers (Async Execution)

### Issue P9-5: Implement Agent Worker Base Framework
**Labels:** `component:agent-workers`, `phase:9`, `priority:high`
**Description:**
- Create AgentWorker base class:
  - Abstract methods: `process_event(event)` - handle event processing
  - Support event subscription configuration
  - Handle event deserialization and validation
  - Implement idempotency checking (event_id tracking)
  - Support graceful shutdown and health checks
- Implement worker lifecycle management:
  - Start/stop workers
  - Health monitoring
  - Error handling and recovery
- Create worker configuration system (env vars or config file)
- Reference: docs/phase9-async-scale-mvp.md Section 5.1

**Dependencies:** P9-1, P9-2, P9-3

**Acceptance Criteria:**
- [ ] AgentWorker base class implemented
- [ ] Event subscription configuration functional
- [ ] Event deserialization and validation working
- [ ] Idempotency checking implemented
- [ ] Worker lifecycle management functional
- [ ] Health checks implemented
- [ ] Unit tests for worker framework
- [ ] Integration tests for worker lifecycle

---

### Issue P9-6: Implement IntakeWorker
**Labels:** `component:agent-workers`, `phase:9`, `priority:high`
**Description:**
- Implement IntakeWorker:
  - Subscribe to ExceptionIngested events
  - Process exception normalization (existing IntakeAgent logic)
  - Emit ExceptionNormalized event after processing
  - Store normalized exception in database
  - Handle idempotency (skip if already processed)
- Migrate existing IntakeAgent logic to async worker pattern
- Ensure tenant isolation in processing
- Reference: docs/phase9-async-scale-mvp.md Section 5.1, Section 5.2

**Dependencies:** P9-5, P2-* (IntakeAgent logic)

**Acceptance Criteria:**
- [ ] IntakeWorker implemented
- [ ] ExceptionIngested event subscription working
- [ ] Exception normalization logic migrated
- [ ] ExceptionNormalized event emission functional
- [ ] Idempotency handling working
- [ ] Tenant isolation enforced
- [ ] Unit tests for IntakeWorker
- [ ] Integration tests for intake flow

---

### Issue P9-7: Implement TriageWorker
**Labels:** `component:agent-workers`, `phase:9`, `priority:high`
**Description:**
- Implement TriageWorker:
  - Subscribe to ExceptionNormalized events
  - Process triage analysis (existing TriageAgent logic)
  - Emit TriageRequested and TriageCompleted events
  - Update exception with triage results
  - Handle idempotency
- Migrate existing TriageAgent logic to async worker pattern
- Ensure tenant isolation in processing
- Reference: docs/phase9-async-scale-mvp.md Section 5.1, Section 5.2

**Dependencies:** P9-5, P3-* (TriageAgent logic)

**Acceptance Criteria:**
- [ ] TriageWorker implemented
- [ ] ExceptionNormalized event subscription working
- [ ] Triage analysis logic migrated
- [ ] TriageRequested/TriageCompleted events emitted
- [ ] Idempotency handling working
- [ ] Tenant isolation enforced
- [ ] Unit tests for TriageWorker
- [ ] Integration tests for triage flow

---

### Issue P9-8: Implement PolicyWorker
**Labels:** `component:agent-workers`, `phase:9`, `priority:high`
**Description:**
- Implement PolicyWorker:
  - Subscribe to TriageCompleted events
  - Process policy evaluation (existing PolicyAgent logic)
  - Emit PolicyEvaluationRequested and PolicyEvaluationCompleted events
  - Emit PlaybookMatched event when playbook is found
  - Update exception with policy results
  - Handle idempotency
- Migrate existing PolicyAgent logic to async worker pattern
- Ensure tenant isolation in processing
- Reference: docs/phase9-async-scale-mvp.md Section 5.1, Section 5.2

**Dependencies:** P9-5, P4-* (PolicyAgent logic)

**Acceptance Criteria:**
- [ ] PolicyWorker implemented
- [ ] TriageCompleted event subscription working
- [ ] Policy evaluation logic migrated
- [ ] PolicyEvaluationRequested/Completed events emitted
- [ ] PlaybookMatched event emission functional
- [ ] Idempotency handling working
- [ ] Tenant isolation enforced
- [ ] Unit tests for PolicyWorker
- [ ] Integration tests for policy flow

---

### Issue P9-9: Implement PlaybookWorker
**Labels:** `component:agent-workers`, `phase:9`, `priority:high`
**Description:**
- Implement PlaybookWorker:
  - Subscribe to PlaybookMatched events
  - Drive playbook step execution (existing PlaybookExecutionService logic)
  - Emit StepExecutionRequested events for each step
  - Handle step completion events
  - Update exception with playbook progress
  - Handle idempotency
- Migrate existing playbook execution logic to async worker pattern
- Ensure tenant isolation in processing
- Reference: docs/phase9-async-scale-mvp.md Section 5.1, Section 5.2

**Dependencies:** P9-5, P7-* (PlaybookExecutionService logic)

**Acceptance Criteria:**
- [ ] PlaybookWorker implemented
- [ ] PlaybookMatched event subscription working
- [ ] Playbook step execution logic migrated
- [ ] StepExecutionRequested events emitted
- [ ] Step completion handling functional
- [ ] Idempotency handling working
- [ ] Tenant isolation enforced
- [ ] Unit tests for PlaybookWorker
- [ ] Integration tests for playbook flow

---

### Issue P9-10: Implement ToolWorker
**Labels:** `component:agent-workers`, `phase:9`, `priority:high`
**Description:**
- Implement ToolWorker:
  - Subscribe to ToolExecutionRequested events
  - Execute tools via ToolExecutionService (from Phase 8)
  - Emit ToolExecutionCompleted or ToolExecutionFailed events
  - Update tool_execution records
  - Handle idempotency
- Integrate with existing ToolExecutionService
- Ensure tenant isolation in processing
- Reference: docs/phase9-async-scale-mvp.md Section 5.1, Section 5.2

**Dependencies:** P9-5, P8-4 (ToolExecutionService)

**Acceptance Criteria:**
- [ ] ToolWorker implemented
- [ ] ToolExecutionRequested event subscription working
- [ ] Tool execution via ToolExecutionService functional
- [ ] ToolExecutionCompleted/Failed events emitted
- [ ] Idempotency handling working
- [ ] Tenant isolation enforced
- [ ] Unit tests for ToolWorker
- [ ] Integration tests for tool execution flow

---

### Issue P9-11: Implement FeedbackWorker
**Labels:** `component:agent-workers`, `phase:9`, `priority:medium`
**Description:**
- Implement FeedbackWorker:
  - Subscribe to exception completion/resolution events
  - Capture feedback metrics (existing FeedbackAgent logic)
  - Emit FeedbackCaptured events
  - Update analytics/metrics tables
  - Handle idempotency
- Migrate existing FeedbackAgent logic to async worker pattern
- Ensure tenant isolation in processing
- Reference: docs/phase9-async-scale-mvp.md Section 5.1, Section 5.2

**Dependencies:** P9-5, P5-* (FeedbackAgent logic)

**Acceptance Criteria:**
- [ ] FeedbackWorker implemented
- [ ] Event subscription working
- [ ] Feedback capture logic migrated
- [ ] FeedbackCaptured events emitted
- [ ] Idempotency handling working
- [ ] Tenant isolation enforced
- [ ] Unit tests for FeedbackWorker
- [ ] Integration tests for feedback flow

---

## Component: Idempotency & Ordering

### Issue P9-12: Implement Event Processing Idempotency System
**Labels:** `component:reliability`, `phase:9`, `priority:high`
**Description:**
- Implement idempotency tracking:
  - Create event_processing table: event_id, worker_type, tenant_id, exception_id, processed_at, status
  - Track processed event IDs per worker type
  - Check idempotency before processing events
  - Store processing status (processing, completed, failed)
- Implement idempotency check in AgentWorker base class:
  - `is_already_processed(event_id, worker_type)` method
  - `mark_as_processing(event_id, worker_type)` method
  - `mark_as_completed(event_id, worker_type)` method
- Ensure handlers are idempotent (safe to retry)
- Reference: docs/phase9-async-scale-mvp.md Section 6.1

**Dependencies:** P9-5, P6-1 (Database Setup)

**Acceptance Criteria:**
- [ ] event_processing table created
- [ ] Database migration implemented
- [ ] Idempotency tracking methods implemented
- [ ] Idempotency checks in worker base class functional
- [ ] Event handlers are idempotent
- [ ] Unit tests for idempotency system
- [ ] Integration tests for duplicate event handling

---

### Issue P9-13: Implement Event Partitioning and Ordering
**Labels:** `component:reliability`, `phase:9`, `priority:high`
**Description:**
- Implement event partitioning strategy:
  - Partition events by tenant_id and exception_id
  - Ensure ordering per exception (not globally)
  - Configure Kafka partitions or equivalent for ordering guarantees
- Implement partition key generation:
  - `get_partition_key(tenant_id, exception_id)` method
  - Use consistent hashing for partition assignment
- Ensure events for same exception are processed in order
- Document ordering guarantees and limitations
- Reference: docs/phase9-async-scale-mvp.md Section 6.2

**Dependencies:** P9-1, P9-2

**Acceptance Criteria:**
- [ ] Event partitioning strategy implemented
- [ ] Partition key generation functional
- [ ] Ordering per exception guaranteed
- [ ] Kafka partition configuration working
- [ ] Consistent hashing for partition assignment
- [ ] Unit tests for partitioning logic
- [ ] Integration tests for ordering guarantees
- [ ] Documentation on ordering guarantees

---

## Component: Retry & Dead Letter Queue

### Issue P9-14: Implement Retry Strategy with Exponential Backoff
**Labels:** `component:reliability`, `phase:9`, `priority:high`
**Description:**
- Implement retry mechanism:
  - Exponential backoff strategy (configurable delays)
  - Max retry count per event type (configurable)
  - Retry metadata stored with event
  - Emit RetryScheduled events
- Implement retry scheduler:
  - Track retry attempts in event_processing table
  - Schedule retries with delay
  - Re-publish events to broker after delay
- Support configurable retry policies per event type
- Reference: docs/phase9-async-scale-mvp.md Section 7.3

**Dependencies:** P9-2, P9-12

**Acceptance Criteria:**
- [ ] Retry mechanism with exponential backoff implemented
- [ ] Max retry count configuration functional
- [ ] Retry metadata stored with events
- [ ] RetryScheduled events emitted
- [ ] Retry scheduler functional
- [ ] Configurable retry policies per event type
- [ ] Unit tests for retry logic
- [ ] Integration tests for retry flow

---

### Issue P9-15: Implement Dead Letter Queue (DLQ)
**Labels:** `component:reliability`, `phase:9`, `priority:high`
**Description:**
- Implement Dead Letter Queue:
  - Create dead_letter_events table: event_id, event_type, tenant_id, exception_id, original_topic, failure_reason, retry_count, failed_at, payload, metadata
  - Move failed events to DLQ after max retries
  - Emit DeadLettered events
  - Support manual retry from DLQ (future: via API)
- Implement DLQ handler:
  - Track failed events
  - Store failure reasons and context
  - Support querying DLQ entries
- Ensure tenant isolation in DLQ
- Reference: docs/phase9-async-scale-mvp.md Section 7.2

**Dependencies:** P9-14, P6-1 (Database Setup)

**Acceptance Criteria:**
- [ ] dead_letter_events table created
- [ ] Database migration implemented
- [ ] DLQ handler implemented
- [ ] Failed events moved to DLQ after max retries
- [ ] DeadLettered events emitted
- [ ] Failure reasons and context stored
- [ ] DLQ querying functional
- [ ] Tenant isolation enforced
- [ ] Unit tests for DLQ system
- [ ] Integration tests for DLQ flow

---

## Component: API Transformation (Command/Query Separation)

### Issue P9-16: Transform Exception APIs to Command Pattern
**Labels:** `component:api`, `phase:9`, `priority:high`
**Description:**
- Transform POST /api/exceptions endpoint:
  - Validate request
  - Persist command/event (ExceptionIngested)
  - Publish to message broker
  - Return 202 Accepted (not synchronous result)
- Remove direct agent calls from API endpoints
- Ensure APIs are fire-and-forget (async)
- Update API documentation
- Reference: docs/phase9-async-scale-mvp.md Section 8.1

**Dependencies:** P9-2, P9-3

**Acceptance Criteria:**
- [ ] POST /api/exceptions transformed to command pattern
- [ ] Event persisted before publishing
- [ ] 202 Accepted response returned
- [ ] Direct agent calls removed
- [ ] API documentation updated
- [ ] Unit tests for API transformation
- [ ] Integration tests for async flow
- [ ] Backward compatibility considerations documented

---

### Issue P9-17: Transform Playbook APIs to Command Pattern
**Labels:** `component:api`, `phase:9`, `priority:high`
**Description:**
- Transform playbook-related APIs:
  - POST /api/playbook/recalculate → publish event, return 202
  - POST /api/playbook/{id}/execute → publish event, return 202
  - Remove direct playbook execution calls
- Ensure all playbook operations are async
- Update API documentation
- Reference: docs/phase9-async-scale-mvp.md Section 8.1

**Dependencies:** P9-2, P9-3, P9-9

**Acceptance Criteria:**
- [ ] Playbook APIs transformed to command pattern
- [ ] Events published for playbook operations
- [ ] 202 Accepted responses returned
- [ ] Direct execution calls removed
- [ ] API documentation updated
- [ ] Unit tests for API transformation
- [ ] Integration tests for async flow

---

### Issue P9-18: Transform Tool Execution APIs to Command Pattern
**Labels:** `component:api`, `phase:9`, `priority:high`
**Description:**
- Transform POST /api/tools/{tool_id}/execute endpoint:
  - Validate request
  - Persist command/event (ToolExecutionRequested)
  - Publish to message broker
  - Return 202 Accepted with execution_id
- Remove direct tool execution calls from API
- Ensure tool execution is async
- Update API documentation
- Reference: docs/phase9-async-scale-mvp.md Section 8.1

**Dependencies:** P9-2, P9-3, P9-10

**Acceptance Criteria:**
- [ ] Tool execution API transformed to command pattern
- [ ] ToolExecutionRequested event published
- [ ] 202 Accepted response with execution_id returned
- [ ] Direct execution calls removed
- [ ] API documentation updated
- [ ] Unit tests for API transformation
- [ ] Integration tests for async flow

---

### Issue P9-19: Implement Query APIs (Read Model)
**Labels:** `component:api`, `phase:9`, `priority:high`
**Description:**
- Ensure all GET endpoints read from database projections (not agents):
  - GET /api/exceptions/{id} - read from exception table
  - GET /api/exceptions - read from exception table with filters
  - GET /api/playbooks/{id} - read from playbook table
  - GET /api/tools/executions - read from tool_execution table
- Remove any synchronous agent invocations from query endpoints
- Ensure query endpoints are fast and read-only
- Update API documentation
- Reference: docs/phase9-async-scale-mvp.md Section 8.2

**Dependencies:** P9-16, P9-17, P9-18

**Acceptance Criteria:**
- [ ] All GET endpoints read from database only
- [ ] No synchronous agent invocations in queries
- [ ] Query endpoints are fast and read-only
- [ ] API documentation updated
- [ ] Unit tests for query endpoints
- [ ] Integration tests for read model
- [ ] Performance benchmarks documented

---

## Component: Observability & Operations

### Issue P9-20: Implement Event Processing Metrics
**Labels:** `component:observability`, `phase:9`, `priority:medium`
**Description:**
- Implement metrics collection:
  - Events/sec per agent worker type
  - Processing latency per event type
  - Failure rates per worker type
  - Retry counts and DLQ sizes
- Integrate with metrics system (Prometheus or similar):
  - Expose metrics endpoint
  - Track key performance indicators
- Support metrics querying via API
- Reference: docs/phase9-async-scale-mvp.md Section 10.1

**Dependencies:** P9-5, P9-14, P9-15

**Acceptance Criteria:**
- [ ] Metrics collection implemented
- [ ] Events/sec tracking functional
- [ ] Processing latency tracking functional
- [ ] Failure rates tracking functional
- [ ] Metrics exposed via endpoint
- [ ] Metrics querying via API functional
- [ ] Unit tests for metrics collection
- [ ] Integration tests for metrics exposure

---

### Issue P9-21: Implement Distributed Tracing
**Labels:** `component:observability`, `phase:9`, `priority:medium`
**Description:**
- Implement distributed tracing:
  - Correlation ID = exception_id (primary) or event_id
  - Propagate correlation ID through all events
  - Trace across agents via event metadata
  - Store trace information in event metadata
- Support trace querying:
  - Get all events for an exception (trace)
  - Visualize event flow across workers
- Integrate with tracing system (OpenTelemetry or similar) if available
- Reference: docs/phase9-async-scale-mvp.md Section 10.2

**Dependencies:** P9-3, P9-4

**Acceptance Criteria:**
- [ ] Correlation ID propagation implemented
- [ ] Trace information stored in event metadata
- [ ] Trace querying functional
- [ ] Event flow visualization support
- [ ] Integration with tracing system (if available)
- [ ] Unit tests for tracing
- [ ] Integration tests for trace propagation

---

### Issue P9-22: Implement SLA Monitoring and Alerts
**Labels:** `component:observability`, `phase:9`, `priority:medium`
**Description:**
- Implement SLA monitoring:
  - Track SLA deadlines per exception
  - Emit SLAImminent events (configurable threshold, e.g., 80% of SLA)
  - Emit SLAExpired events when SLA is breached
  - Store SLA status in exception records
- Support configurable SLA thresholds per tenant
- Integrate with alerting system (if available)
- Reference: docs/phase9-async-scale-mvp.md Section 4.2, Section 10.1

**Dependencies:** P9-3, P9-4

**Acceptance Criteria:**
- [ ] SLA monitoring implemented
- [ ] SLA deadline tracking functional
- [ ] SLAImminent events emitted
- [ ] SLAExpired events emitted
- [ ] SLA status stored in exceptions
- [ ] Configurable thresholds per tenant
- [ ] Unit tests for SLA monitoring
- [ ] Integration tests for SLA events

---

## Component: Security & Compliance

### Issue P9-23: Enforce Tenant Isolation at Message Broker Layer
**Labels:** `component:security`, `phase:9`, `priority:high`
**Description:**
- Implement tenant isolation in message broker:
  - Topic naming with tenant_id prefix or suffix (or use topic per tenant)
  - Access control at broker level (if supported)
  - Validate tenant_id in all event handlers
  - Prevent cross-tenant event processing
- Ensure tenant isolation in event partitioning
- Add tenant validation in all workers
- Reference: docs/phase9-async-scale-mvp.md Section 11

**Dependencies:** P9-1, P9-5

**Acceptance Criteria:**
- [ ] Tenant isolation at broker layer implemented
- [ ] Topic naming strategy enforces isolation
- [ ] Tenant validation in event handlers functional
- [ ] Cross-tenant event processing prevented
- [ ] Tenant isolation in partitioning enforced
- [ ] Unit tests for tenant isolation
- [ ] Security tests for cross-tenant prevention

---

### Issue P9-24: Implement Encryption in Transit and PII Redaction
**Labels:** `component:security`, `phase:9`, `priority:high`
**Description:**
- Implement encryption in transit:
  - TLS/SSL for message broker connections
  - Encrypted event payloads (if required)
- Implement PII redaction:
  - Redact PII fields at event ingestion
  - Store redaction metadata
  - Support configurable PII fields per tenant
- Ensure secrets are never logged in events
- Reference: docs/phase9-async-scale-mvp.md Section 11

**Dependencies:** P9-1, P9-3

**Acceptance Criteria:**
- [ ] Encryption in transit implemented
- [ ] TLS/SSL for broker connections functional
- [ ] PII redaction at ingestion implemented
- [ ] Redaction metadata stored
- [ ] Configurable PII fields per tenant
- [ ] Secrets never logged in events
- [ ] Unit tests for encryption
- [ ] Security tests for PII redaction

---

### Issue P9-25: Enhance Audit Trail with Event Store Integration
**Labels:** `component:audit`, `phase:9`, `priority:high`
**Description:**
- Enhance audit trail to use event store:
  - All events are source of truth for audit
  - Query audit trail from event store
  - Support full event history per exception
  - Support full event history per tenant
- Ensure audit trail is immutable and append-only
- Support audit trail querying via API
- Reference: docs/phase9-async-scale-mvp.md Section 11

**Dependencies:** P9-4

**Acceptance Criteria:**
- [ ] Audit trail integrated with event store
- [ ] Event store as source of truth for audit
- [ ] Event history querying functional
- [ ] Audit trail immutability enforced
- [ ] Audit trail querying via API functional
- [ ] Unit tests for audit trail
- [ ] Integration tests for audit queries

---

## Component: Horizontal Scaling & Operations

### Issue P9-26: Implement Worker Scaling Configuration
**Labels:** `component:operations`, `phase:9`, `priority:medium`
**Description:**
- Implement worker scaling configuration:
  - Support multiple worker instances per agent type
  - Configure worker concurrency (number of parallel event processors)
  - Support horizontal scaling via environment variables
  - Ensure workers are stateless (no shared state)
- Document scaling strategy:
  - How to scale each worker type independently
  - Resource requirements per worker type
  - Scaling best practices
- Reference: docs/phase9-async-scale-mvp.md Section 9

**Dependencies:** P9-5

**Acceptance Criteria:**
- [ ] Worker scaling configuration implemented
- [ ] Multiple worker instances per type supported
- [ ] Worker concurrency configuration functional
- [ ] Horizontal scaling via env vars supported
- [ ] Workers are stateless
- [ ] Scaling strategy documented
- [ ] Unit tests for scaling configuration
- [ ] Integration tests for multiple workers

---

### Issue P9-27: Implement Backpressure Protection
**Labels:** `component:operations`, `phase:9`, `priority:medium`
**Description:**
- Implement backpressure protection:
  - Per-tenant rate limiting
  - Per-tenant queue size limits
  - Throttle event publishing when queues are full
  - Emit backpressure events for monitoring
- Support configurable limits per tenant
- Prevent system overload from single tenant
- Reference: docs/phase9-async-scale-mvp.md Section 9

**Dependencies:** P9-1, P9-2

**Acceptance Criteria:**
- [ ] Backpressure protection implemented
- [ ] Per-tenant rate limiting functional
- [ ] Per-tenant queue size limits functional
- [ ] Event publishing throttling working
- [ ] Backpressure events emitted
- [ ] Configurable limits per tenant
- [ ] Unit tests for backpressure
- [ ] Integration tests for rate limiting

---

## Component: Testing & Documentation

### Issue P9-28: Implement End-to-End Async Flow Tests
**Labels:** `component:testing`, `phase:9`, `priority:high`
**Description:**
- Write end-to-end integration tests:
  - Exception ingestion → normalization → triage → policy → playbook → tool execution
  - Verify events flow through all workers
  - Verify idempotency (duplicate events handled)
  - Verify ordering (events for same exception processed in order)
  - Verify retry and DLQ handling
  - Verify tenant isolation
- Test horizontal scaling:
  - Multiple workers processing events
  - Load testing (target: ≥1M events/min sustained)
- Achieve >80% code coverage for async components
- Reference: docs/phase9-async-scale-mvp.md Section 13

**Dependencies:** All P9 issues

**Acceptance Criteria:**
- [ ] End-to-end async flow tests implemented
- [ ] Event flow through workers verified
- [ ] Idempotency tests passing
- [ ] Ordering tests passing
- [ ] Retry and DLQ tests passing
- [ ] Tenant isolation tests passing
- [ ] Horizontal scaling tests passing
- [ ] Load tests achieving ≥1M events/min
- [ ] Code coverage >80%

---

### Issue P9-29: Update Architecture Documentation and Create Runbook
**Labels:** `component:documentation`, `phase:9`, `priority:high`
**Description:**
- Update main architecture documentation:
  - Document event-driven architecture
  - Document message broker integration
  - Document agent worker model
  - Document event flow diagrams
- Create operations runbook:
  - How to deploy and scale workers
  - How to monitor event processing
  - How to handle DLQ entries
  - How to troubleshoot event processing failures
  - How to configure retry policies
  - How to manage tenant isolation
- Update API documentation with async patterns
- Reference: docs/phase9-async-scale-mvp.md Section 13

**Dependencies:** All P9 issues

**Acceptance Criteria:**
- [ ] Architecture documentation updated
- [ ] Event-driven architecture documented
- [ ] Message broker integration documented
- [ ] Agent worker model documented
- [ ] Event flow diagrams created
- [ ] Operations runbook created with all sections
- [ ] API documentation updated
- [ ] Troubleshooting guides included

---

## Summary

**Total Issues:** 29
**High Priority:** 20
**Medium Priority:** 9

**Components Covered:**
- Message Broker Infrastructure (2 issues)
- Canonical Event Model (2 issues)
- Agent Workers (Async Execution) (7 issues)
- Idempotency & Ordering (2 issues)
- Retry & Dead Letter Queue (2 issues)
- API Transformation (Command/Query Separation) (4 issues)
- Observability & Operations (3 issues)
- Security & Compliance (3 issues)
- Horizontal Scaling & Operations (2 issues)
- Testing & Documentation (2 issues)

**Implementation Order:**
1. P9-1: Message broker abstraction
2. P9-3: Canonical event schema
3. P9-4: Event store persistence
4. P9-2: Event publisher service
5. P9-5: Agent worker base framework
6. P9-12: Idempotency system
7. P9-13: Event partitioning and ordering
8. P9-6 to P9-11: Individual agent workers (can be parallel)
9. P9-14: Retry strategy
10. P9-15: Dead letter queue
11. P9-16 to P9-19: API transformations (can be parallel)
12. P9-20 to P9-22: Observability (can be parallel)
13. P9-23 to P9-25: Security and compliance (can be parallel)
14. P9-26 to P9-27: Scaling and operations
15. P9-28: End-to-end testing
16. P9-29: Documentation and runbook







