# Phase 6 Persistence & State MVP - GitHub Issues Checklist

## Component: Database Schema & Migrations

### Issue P6-1: Design and Implement Core Database Schema
**Labels:** `component:database`, `phase:6`, `priority:high`
**Description:**
- Design PostgreSQL schema for all Phase 6 tables:
  - `tenant` table (tenant metadata & lifecycle)
  - `domain_pack_version` table (versioned domain packs)
  - `tenant_policy_pack_version` table (tenant-specific logic overlays)
  - `exception` table (system of record for exceptions)
  - `exception_event` table (append-only event log)
  - `playbook` table (Phase 7 preparation)
  - `playbook_step` table (Phase 7 preparation)
  - `tool_definition` table (Phase 8 preparation)
- Define appropriate indexes for query performance
- Ensure tenant isolation at schema level
- Reference: docs/phase6-persistence-mvp.md Section 4 (Schema Overview)

**Dependencies:** None

**Acceptance Criteria:**
- [ ] All core tables designed with proper columns and types
- [ ] Primary keys and foreign keys defined
- [ ] Indexes created for common query patterns
- [ ] Tenant isolation enforced via foreign keys and indexes
- [ ] Schema supports Phase 7 and Phase 8 requirements
- [ ] Schema documentation created

---

### Issue P6-2: Implement Database Migrations with Alembic
**Labels:** `component:database`, `phase:6`, `priority:high`
**Description:**
- Set up Alembic for database migrations
- Create initial migration for Phase 6 schema
- Support migration rollback
- Include migration instructions in documentation
- Ensure migrations are idempotent and safe for production
- Reference: docs/phase6-persistence-mvp.md Section 10 (Phase 6 Exit Criteria - Deployment)

**Dependencies:** P6-1

**Acceptance Criteria:**
- [ ] Alembic configured and integrated
- [ ] Initial migration created for all Phase 6 tables
- [ ] Migration rollback tested
- [ ] Migration instructions documented
- [ ] Migrations tested in clean database environment
- [ ] `.env.example` updated with database connection settings

---

### Issue P6-3: Implement Database Connection Pool and Configuration
**Labels:** `component:database`, `phase:6`, `priority:high`
**Description:**
- Implement async database connection pool using asyncpg or async SQLAlchemy
- Configure connection pool settings (min/max connections, timeout)
- Implement connection retry logic
- Add database health check endpoint
- Support connection string configuration via environment variables
- Reference: docs/phase6-persistence-mvp.md Section 10 (Phase 6 Exit Criteria - Architecture)

**Dependencies:** P6-2

**Acceptance Criteria:**
- [ ] Async connection pool implemented
- [ ] Connection pool configuration via environment variables
- [ ] Connection retry logic functional
- [ ] Database health check endpoint implemented
- [ ] Connection timeout handling implemented
- [ ] Unit tests for connection pool behavior

---

## Component: Repository Layer - Base Infrastructure

### Issue P6-4: Implement Base Repository Interface and Abstract Repository
**Labels:** `component:repository`, `phase:6`, `priority:high`
**Description:**
- Define base repository interface/protocol for all repositories
- Implement abstract base repository with common CRUD operations
- Ensure all repositories enforce tenant isolation
- Support async operations throughout
- Implement dependency injection pattern (no global DB objects)
- Reference: docs/phase6-persistence-mvp.md Section 5 (Repository Layer Requirements)

**Dependencies:** P6-3

**Acceptance Criteria:**
- [ ] Base repository interface/protocol defined
- [ ] Abstract base repository implemented
- [ ] Tenant isolation enforced in base repository
- [ ] All operations are async
- [ ] Dependency injection pattern implemented
- [ ] Unit tests for base repository functionality

---

### Issue P6-5: Implement Idempotency Helpers for Repositories
**Labels:** `component:repository`, `phase:6`, `priority:medium`
**Description:**
- Implement idempotency helpers for safe event replay and retries:
  - `upsert_exception(exception)` - idempotent exception creation/update
  - `event_exists(event_id)` - check if event already processed
- Support idempotent writes across all repositories
- Ensure safe replaying of events in async processing
- Reference: docs/phase6-persistence-mvp.md Section 2 (Core Principles - Idempotent Writes), Section 5

**Dependencies:** P6-4

**Acceptance Criteria:**
- [ ] `upsert_exception()` implemented with idempotency
- [ ] `event_exists()` implemented
- [ ] Idempotency helpers tested with duplicate operations
- [ ] Safe event replay verified
- [ ] Unit tests for idempotency scenarios

---

## Component: Exception Repository

### Issue P6-6: Implement Exception Repository with CRUD Operations
**Labels:** `component:repository`, `phase:6`, `priority:high`
**Description:**
- Implement `ExceptionRepository` with full CRUD operations
- Support operations:
  - `create_exception(exception)` - create new exception
  - `get_exception(exception_id, tenant_id)` - retrieve by ID
  - `update_exception(exception_id, tenant_id, updates)` - update exception state
  - `list_exceptions(tenant_id, filters, pagination)` - list with filtering
- Enforce tenant isolation on all queries
- Support filtering by domain, status, severity, date range
- Support pagination for large result sets
- Reference: docs/phase6-persistence-mvp.md Section 4.4 (exception Table), Section 5

**Dependencies:** P6-4

**Acceptance Criteria:**
- [ ] `ExceptionRepository` implemented with all CRUD operations
- [ ] Tenant isolation enforced on all queries
- [ ] Filtering by domain, status, severity, date range supported
- [ ] Pagination implemented
- [ ] Unit tests for all repository methods
- [ ] Integration tests with real database

---

### Issue P6-7: Implement Exception Query Helpers for Co-Pilot
**Labels:** `component:repository`, `phase:6`, `priority:medium`
**Description:**
- Implement query helpers for Co-Pilot contextual retrieval:
  - Find similar exceptions by domain/type
  - Get exceptions by entity (counterparty, patient, account)
  - Get exceptions by source system
  - Get exceptions by SLA deadline proximity
- Support semantic search preparation (for Phase 10)
- Reference: docs/phase6-persistence-mvp.md Section 5 (Co-Pilot Query Helpers)

**Dependencies:** P6-6

**Acceptance Criteria:**
- [ ] Query helpers for similar exceptions implemented
- [ ] Entity-based queries functional
- [ ] Source system queries functional
- [ ] SLA deadline queries functional
- [ ] Unit tests for query helpers
- [ ] Query performance validated with indexes

---

## Component: Exception Event Repository

### Issue P6-8: Implement Exception Event Repository with Append-Only Log
**Labels:** `component:repository`, `phase:6`, `priority:high`
**Description:**
- Implement `ExceptionEventRepository` for append-only event log
- Support operations:
  - `append_event(event)` - append event to log (idempotent)
  - `get_events(exception_id, tenant_id, filters)` - retrieve event timeline
  - `get_events_by_tenant(tenant_id, date_range)` - tenant event queries
  - `event_exists(event_id)` - check for duplicate events
- Support filtering by event_type, actor_type, date range
- Ensure append-only semantics (no updates or deletes)
- Reference: docs/phase6-persistence-mvp.md Section 4.5 (exception_event Table), Section 5

**Dependencies:** P6-4

**Acceptance Criteria:**
- [ ] `ExceptionEventRepository` implemented
- [ ] Append-only semantics enforced
- [ ] Idempotent event appending functional
- [ ] Event timeline retrieval functional
- [ ] Tenant event queries supported
- [ ] Unit tests for event repository
- [ ] Integration tests verify append-only behavior

---

### Issue P6-9: Implement Standard Event Types and Payload Schemas
**Labels:** `component:repository`, `phase:6`, `priority:high`
**Description:**
- Define standard event types:
  - `ExceptionCreated`
  - `ExceptionNormalized`
  - `TriageCompleted`
  - `PolicyEvaluated`
  - `ResolutionSuggested`
  - `ResolutionApproved`
  - `FeedbackCaptured`
  - `LLMDecisionProposed`
  - `CopilotQuestionAsked`
  - `CopilotAnswerGiven`
- Define payload schemas for each event type
- Ensure event structure supports future migration to Kafka (Phase 9)
- Reference: docs/phase6-persistence-mvp.md Section 6.2 (Agent event types), Section 9

**Dependencies:** P6-8

**Acceptance Criteria:**
- [ ] All standard event types defined
- [ ] Payload schemas documented and validated
- [ ] Event structure compatible with future Kafka migration
- [ ] Event type constants/enums created
- [ ] Payload validation implemented
- [ ] Unit tests for event type handling

---

## Component: Tenant & Pack Repositories

### Issue P6-10: Implement Tenant Repository
**Labels:** `component:repository`, `phase:6`, `priority:high`
**Description:**
- Implement `TenantRepository` for tenant metadata management
- Support operations:
  - `get_tenant(tenant_id)` - retrieve tenant by ID
  - `list_tenants(filters)` - list tenants with filtering
  - `update_tenant_status(tenant_id, status)` - update tenant lifecycle
- Support tenant status: active, suspended, archived
- Reference: docs/phase6-persistence-mvp.md Section 4.1 (tenant Table), Section 5

**Dependencies:** P6-4

**Acceptance Criteria:**
- [ ] `TenantRepository` implemented
- [ ] Tenant retrieval by ID functional
- [ ] Tenant listing with filters supported
- [ ] Tenant status updates functional
- [ ] Unit tests for tenant repository

---

### Issue P6-11: Implement Domain Pack Repository
**Labels:** `component:repository`, `phase:6`, `priority:high`
**Description:**
- Implement `DomainPackRepository` for versioned domain packs
- Support operations:
  - `get_domain_pack(domain, version)` - retrieve specific version
  - `get_latest_domain_pack(domain)` - get latest version
  - `create_domain_pack_version(domain, version, pack_json)` - create new version
  - `list_domain_packs(domain)` - list all versions for domain
- Support versioning and rollback
- Reference: docs/phase6-persistence-mvp.md Section 4.2 (domain_pack_version Table), Section 5

**Dependencies:** P6-4

**Acceptance Criteria:**
- [ ] `DomainPackRepository` implemented
- [ ] Version retrieval functional
- [ ] Latest version retrieval functional
- [ ] Version creation functional
- [ ] Version listing functional
- [ ] Unit tests for domain pack repository

---

### Issue P6-12: Implement Tenant Policy Pack Repository
**Labels:** `component:repository`, `phase:6`, `priority:high`
**Description:**
- Implement `TenantPolicyPackRepository` for tenant-specific logic overlays
- Support operations:
  - `get_tenant_policy_pack(tenant_id, version)` - retrieve specific version
  - `get_latest_tenant_policy_pack(tenant_id)` - get latest version
  - `create_tenant_policy_pack_version(tenant_id, version, pack_json)` - create new version
  - `list_tenant_policy_packs(tenant_id)` - list all versions for tenant
- Enforce tenant isolation
- Support versioning and rollback
- Reference: docs/phase6-persistence-mvp.md Section 4.3 (tenant_policy_pack_version Table), Section 5

**Dependencies:** P6-4

**Acceptance Criteria:**
- [ ] `TenantPolicyPackRepository` implemented
- [ ] Tenant isolation enforced
- [ ] Version retrieval functional
- [ ] Latest version retrieval functional
- [ ] Version creation functional
- [ ] Version listing functional
- [ ] Unit tests for tenant policy pack repository

---

## Component: Playbook Repository (Phase 7 Preparation)

### Issue P6-13: Implement Playbook Repository Scaffolding
**Labels:** `component:repository`, `phase:6`, `priority:medium`
**Description:**
- Implement `PlaybookRepository` scaffolding for Phase 7
- Support basic operations:
  - `get_playbook(playbook_id, tenant_id)` - retrieve playbook
  - `list_playbooks(tenant_id, filters)` - list playbooks
  - `create_playbook(tenant_id, playbook_data)` - create playbook
- Enforce tenant isolation
- Prepare schema for Phase 7 playbook engine
- Reference: docs/phase6-persistence-mvp.md Section 4.6 (playbook & playbook_step Tables), Section 5

**Dependencies:** P6-4

**Acceptance Criteria:**
- [ ] `PlaybookRepository` scaffolding implemented
- [ ] Basic CRUD operations functional
- [ ] Tenant isolation enforced
- [ ] Schema ready for Phase 7 expansion
- [ ] Unit tests for playbook repository scaffolding

---

### Issue P6-14: Implement Playbook Step Repository Scaffolding
**Labels:** `component:repository`, `phase:6`, `priority:medium`
**Description:**
- Implement `PlaybookStepRepository` scaffolding for Phase 7
- Support operations:
  - `get_steps(playbook_id, tenant_id)` - retrieve steps for playbook
  - `create_step(playbook_id, step_data)` - create step
  - `update_step_order(playbook_id, steps)` - update step ordering
- Enforce tenant isolation
- Prepare for Phase 7 step execution logic
- Reference: docs/phase6-persistence-mvp.md Section 4.6 (playbook_step Table), Section 5

**Dependencies:** P6-13

**Acceptance Criteria:**
- [ ] `PlaybookStepRepository` scaffolding implemented
- [ ] Step retrieval functional
- [ ] Step creation functional
- [ ] Step ordering updates functional
- [ ] Tenant isolation enforced
- [ ] Unit tests for playbook step repository

---

## Component: Tool Definition Repository (Phase 8 Preparation)

### Issue P6-15: Implement Tool Definition Repository Scaffolding
**Labels:** `component:repository`, `phase:6`, `priority:medium`
**Description:**
- Implement `ToolDefinitionRepository` scaffolding for Phase 8
- Support operations:
  - `get_tool(tool_id, tenant_id)` - retrieve tool definition
  - `list_tools(tenant_id, filters)` - list tools (tenant-scoped or global)
  - `create_tool(tenant_id, tool_data)` - create tool definition
- Support both tenant-scoped and global tools
- Enforce tenant isolation for tenant-scoped tools
- Reference: docs/phase6-persistence-mvp.md Section 4.7 (tool_definition Table), Section 5

**Dependencies:** P6-4

**Acceptance Criteria:**
- [ ] `ToolDefinitionRepository` scaffolding implemented
- [ ] Tool retrieval functional
- [ ] Tool listing with tenant/global filtering functional
- [ ] Tool creation functional
- [ ] Tenant isolation enforced for tenant-scoped tools
- [ ] Unit tests for tool definition repository

---

## Component: Agent Integration

### Issue P6-16: Integrate Exception Repository into Intake Agent
**Labels:** `component:agent`, `phase:6`, `priority:high`
**Description:**
- Modify IntakeAgent to use `ExceptionRepository` instead of in-memory storage
- Implement standardized persistence pattern:
  1. Load exception from repository (if exists)
  2. Append event record (`ExceptionCreated` or `ExceptionNormalized`)
  3. Update exception state
  4. Return updated state
- Ensure idempotent exception creation
- Reference: docs/phase6-persistence-mvp.md Section 6.1 (Persistence Rules for Agents)

**Dependencies:** P6-6, P6-8

**Acceptance Criteria:**
- [ ] IntakeAgent uses `ExceptionRepository`
- [ ] Standardized persistence pattern implemented
- [ ] Event logging functional
- [ ] Idempotent exception creation verified
- [ ] Existing tests updated and passing
- [ ] Integration tests with database

---

### Issue P6-17: Integrate Repositories into Triage Agent
**Labels:** `component:agent`, `phase:6`, `priority:high`
**Description:**
- Modify TriageAgent to use `ExceptionRepository` and `ExceptionEventRepository`
- Implement standardized persistence pattern:
  1. Load exception from repository
  2. Append `TriageCompleted` event
  3. Update exception state (severity, status, etc.)
  4. Return updated state
- Ensure event logging captures triage decisions
- Reference: docs/phase6-persistence-mvp.md Section 6.1, Section 6.2

**Dependencies:** P6-6, P6-8

**Acceptance Criteria:**
- [ ] TriageAgent uses repositories
- [ ] `TriageCompleted` events logged
- [ ] Exception state updates persisted
- [ ] Existing tests updated and passing
- [ ] Integration tests verify persistence

---

### Issue P6-18: Integrate Repositories into Policy Agent
**Labels:** `component:agent`, `phase:6`, `priority:high`
**Description:**
- Modify PolicyAgent to use `ExceptionRepository` and `ExceptionEventRepository`
- Implement standardized persistence pattern:
  1. Load exception from repository
  2. Append `PolicyEvaluated` event
  3. Update exception state (playbook_id, current_step, etc.)
  4. Return updated state
- Ensure event logging captures policy decisions
- Reference: docs/phase6-persistence-mvp.md Section 6.1, Section 6.2

**Dependencies:** P6-6, P6-8

**Acceptance Criteria:**
- [ ] PolicyAgent uses repositories
- [ ] `PolicyEvaluated` events logged
- [ ] Exception state updates persisted
- [ ] Existing tests updated and passing
- [ ] Integration tests verify persistence

---

### Issue P6-19: Integrate Repositories into Resolution Agent
**Labels:** `component:agent`, `phase:6`, `priority:high`
**Description:**
- Modify ResolutionAgent to use `ExceptionRepository` and `ExceptionEventRepository`
- Implement standardized persistence pattern:
  1. Load exception from repository
  2. Append `ResolutionSuggested` or `ResolutionApproved` event
  3. Update exception state (status, owner, etc.)
  4. Return updated state
- Ensure event logging captures resolution actions
- Reference: docs/phase6-persistence-mvp.md Section 6.1, Section 6.2

**Dependencies:** P6-6, P6-8

**Acceptance Criteria:**
- [ ] ResolutionAgent uses repositories
- [ ] Resolution events logged
- [ ] Exception state updates persisted
- [ ] Existing tests updated and passing
- [ ] Integration tests verify persistence

---

### Issue P6-20: Integrate Repositories into Feedback Agent
**Labels:** `component:agent`, `phase:6`, `priority:high`
**Description:**
- Modify FeedbackAgent to use `ExceptionRepository` and `ExceptionEventRepository`
- Implement standardized persistence pattern:
  1. Load exception from repository
  2. Append `FeedbackCaptured` event
  3. Update exception state if needed
  4. Return updated state
- Ensure event logging captures feedback data
- Reference: docs/phase6-persistence-mvp.md Section 6.1, Section 6.2

**Dependencies:** P6-6, P6-8

**Acceptance Criteria:**
- [ ] FeedbackAgent uses repositories
- [ ] `FeedbackCaptured` events logged
- [ ] Exception state updates persisted
- [ ] Existing tests updated and passing
- [ ] Integration tests verify persistence

---

### Issue P6-21: Integrate Repositories into Co-Pilot
**Labels:** `component:copilot`, `phase:6`, `priority:high`
**Description:**
- Modify Co-Pilot to use DB-backed repositories for contextual retrieval
- Use `ExceptionRepository` query helpers for similar exceptions
- Use `ExceptionEventRepository` for event timeline retrieval
- Ensure Co-Pilot queries respect tenant isolation
- Reference: docs/phase6-persistence-mvp.md Section 5 (Co-Pilot Query Helpers), Section 10

**Dependencies:** P6-6, P6-7, P6-8

**Acceptance Criteria:**
- [ ] Co-Pilot uses DB-backed repositories
- [ ] Contextual retrieval from database functional
- [ ] Tenant isolation enforced in Co-Pilot queries
- [ ] Existing Co-Pilot tests updated and passing
- [ ] Integration tests verify database queries

---

## Component: API Modifications

### Issue P6-22: Update Exception API Endpoints to Use DB Repositories
**Labels:** `component:api`, `phase:6`, `priority:high`
**Description:**
- Update `/api/exceptions/*` endpoints to use `ExceptionRepository` instead of mock repos
- Implement pagination support for list endpoints
- Ensure all endpoints filter by tenant
- Add exception detail endpoint with event timeline
- Support filtering by domain, status, severity, date range
- Reference: docs/phase6-persistence-mvp.md Section 7.1 (/api/exceptions/* endpoints)

**Dependencies:** P6-6, P6-8

**Acceptance Criteria:**
- [ ] All exception endpoints use DB repositories
- [ ] Pagination implemented for list endpoints
- [ ] Tenant filtering enforced on all endpoints
- [ ] Exception detail endpoint includes event timeline
- [ ] Filtering by domain, status, severity, date range supported
- [ ] API tests updated and passing
- [ ] Integration tests with database

---

### Issue P6-23: Implement Event Timeline API Endpoint
**Labels:** `component:api`, `phase:6`, `priority:medium`
**Description:**
- Implement `/api/exceptions/{exception_id}/events` endpoint
- Return event timeline for exception detail screen
- Support filtering by event_type, actor_type, date range
- Ensure tenant isolation
- Support pagination for large event histories
- Reference: docs/phase6-persistence-mvp.md Section 7.1, Section 8.2

**Dependencies:** P6-8

**Acceptance Criteria:**
- [ ] Event timeline endpoint implemented
- [ ] Event filtering functional
- [ ] Tenant isolation enforced
- [ ] Pagination supported
- [ ] API tests for event timeline endpoint
- [ ] Integration tests verify event retrieval

---

### Issue P6-24: Scaffold Playbook API Endpoints for Phase 7
**Labels:** `component:api`, `phase:6`, `priority:low`
**Description:**
- Create basic scaffolding for `/api/playbooks/*` endpoints
- Implement basic CRUD operations using `PlaybookRepository`
- Ensure tenant isolation
- Prepare for Phase 7 playbook engine integration
- Reference: docs/phase6-persistence-mvp.md Section 7.2 (/api/playbooks/*)

**Dependencies:** P6-13

**Acceptance Criteria:**
- [ ] Playbook API endpoints scaffolded
- [ ] Basic CRUD operations functional
- [ ] Tenant isolation enforced
- [ ] API tests for playbook endpoints
- [ ] Ready for Phase 7 expansion

---

### Issue P6-25: Scaffold Tool API Endpoints for Phase 8
**Labels:** `component:api`, `phase:6`, `priority:low`
**Description:**
- Create basic scaffolding for `/api/tools/*` endpoints
- Implement basic CRUD operations using `ToolDefinitionRepository`
- Support both tenant-scoped and global tools
- Ensure tenant isolation for tenant-scoped tools
- Prepare for Phase 8 tool registry integration
- Reference: docs/phase6-persistence-mvp.md Section 7.3 (/api/tools/*)

**Dependencies:** P6-15

**Acceptance Criteria:**
- [ ] Tool API endpoints scaffolded
- [ ] Basic CRUD operations functional
- [ ] Tenant/global tool filtering supported
- [ ] Tenant isolation enforced
- [ ] API tests for tool endpoints
- [ ] Ready for Phase 8 expansion

---

## Component: UI Integration

### Issue P6-26: Update Exceptions Table to Use DB-Backed API
**Labels:** `component:ui`, `phase:6`, `priority:high`
**Description:**
- Update Exceptions Table component to fetch from DB-backed API
- Implement pagination in UI
- Support filtering by domain, status, severity
- Display severity, status, and other DB attributes
- Ensure tenant context is passed to API
- Reference: docs/phase6-persistence-mvp.md Section 8.1 (Exceptions Table)

**Dependencies:** P6-22

**Acceptance Criteria:**
- [ ] Exceptions Table uses DB-backed API
- [ ] Pagination implemented in UI
- [ ] Filtering functional
- [ ] DB attributes displayed correctly
- [ ] Tenant context passed to API
- [ ] UI tests updated and passing

---

### Issue P6-27: Update Exception Detail View with Event Timeline
**Labels:** `component:ui`, `phase:6`, `priority:high`
**Description:**
- Update Exception Detail View to display event timeline
- Integrate event timeline from `/api/exceptions/{id}/events` endpoint
- Display events in chronological order
- Show event type, actor, timestamp, and payload details
- Ensure tenant isolation in UI queries
- Reference: docs/phase6-persistence-mvp.md Section 8.2 (Exception Detail View)

**Dependencies:** P6-23

**Acceptance Criteria:**
- [ ] Event timeline displayed in Exception Detail View
- [ ] Events shown in chronological order
- [ ] Event details (type, actor, timestamp, payload) displayed
- [ ] Tenant isolation enforced
- [ ] UI tests for event timeline
- [ ] Integration tests verify event display

---

### Issue P6-28: Update Supervisor View to Use DB Queries
**Labels:** `component:ui`, `phase:6`, `priority:medium`
**Description:**
- Update Supervisor View to use aggregated DB queries
- Implement basic aggregations (counts by status, severity, domain)
- Support date range filtering
- Ensure tenant-scoped aggregations
- Prepare for future OLAP warehouse upgrade (Phase 9+)
- Reference: docs/phase6-persistence-mvp.md Section 8.3 (Supervisor View)

**Dependencies:** P6-22

**Acceptance Criteria:**
- [ ] Supervisor View uses DB queries
- [ ] Basic aggregations functional
- [ ] Date range filtering supported
- [ ] Tenant-scoped aggregations enforced
- [ ] UI tests for supervisor view
- [ ] Performance acceptable for MVP scale

---

## Component: Testing

### Issue P6-29: Implement Comprehensive Repository Tests
**Labels:** `component:testing`, `phase:6`, `priority:high`
**Description:**
- Write comprehensive test suite for all repositories:
  - ExceptionRepository tests
  - ExceptionEventRepository tests
  - TenantRepository tests
  - DomainPackRepository tests
  - TenantPolicyPackRepository tests
  - PlaybookRepository tests
  - ToolDefinitionRepository tests
- Test tenant isolation enforcement
- Test idempotency helpers
- Test pagination and filtering
- Use test database with proper setup/teardown
- Reference: docs/phase6-persistence-mvp.md Section 10 (Phase 6 Exit Criteria - Backend)

**Dependencies:** P6-6 through P6-15

**Acceptance Criteria:**
- [ ] Comprehensive test suite for all repositories
- [ ] Tenant isolation tests passing
- [ ] Idempotency tests passing
- [ ] Pagination and filtering tests passing
- [ ] Test coverage >80% for repository layer
- [ ] All tests use test database with proper isolation

---

### Issue P6-30: Implement Agent Integration Tests with Database
**Labels:** `component:testing`, `phase:6`, `priority:high`
**Description:**
- Write integration tests for agents with database:
  - IntakeAgent integration tests
  - TriageAgent integration tests
  - PolicyAgent integration tests
  - ResolutionAgent integration tests
  - FeedbackAgent integration tests
- Verify agents persist state and events correctly
- Verify event timeline is complete
- Test idempotent agent operations
- Reference: docs/phase6-persistence-mvp.md Section 10 (Phase 6 Exit Criteria - Backend)

**Dependencies:** P6-16 through P6-20

**Acceptance Criteria:**
- [ ] Integration tests for all agents with database
- [ ] State persistence verified
- [ ] Event logging verified
- [ ] Event timeline completeness verified
- [ ] Idempotent operations tested
- [ ] All integration tests passing

---

### Issue P6-31: Implement API Integration Tests with Database
**Labels:** `component:testing`, `phase:6`, `priority:high`
**Description:**
- Write integration tests for API endpoints with database:
  - Exception API endpoint tests
  - Event timeline API endpoint tests
  - Playbook API endpoint tests (scaffolding)
  - Tool API endpoint tests (scaffolding)
- Verify tenant isolation in API responses
- Test pagination and filtering
- Test error handling
- Reference: docs/phase6-persistence-mvp.md Section 10 (Phase 6 Exit Criteria - Backend)

**Dependencies:** P6-22 through P6-25

**Acceptance Criteria:**
- [ ] API integration tests with database implemented
- [ ] Tenant isolation verified in API tests
- [ ] Pagination and filtering tested
- [ ] Error handling tested
- [ ] All API integration tests passing

---

### Issue P6-32: Update Existing Tests to Use Database
**Labels:** `component:testing`, `phase:6`, `priority:high`
**Description:**
- Update all existing tests to work with database repositories
- Replace in-memory mocks with test database fixtures
- Ensure all existing tests pass with new persistence layer
- Maintain test performance with proper database setup/teardown
- Reference: docs/phase6-persistence-mvp.md Section 10 (Phase 6 Exit Criteria - Backend)

**Dependencies:** P6-29, P6-30, P6-31

**Acceptance Criteria:**
- [ ] All existing tests updated to use database
- [ ] All existing tests passing
- [ ] Test performance acceptable
- [ ] Test database fixtures properly isolated
- [ ] No test regressions introduced

---

## Component: Documentation & Deployment

### Issue P6-33: Create Database Migration and Setup Documentation
**Labels:** `component:documentation`, `phase:6`, `priority:high`
**Description:**
- Create comprehensive documentation for:
  - Database setup instructions
  - Migration execution steps
  - Database connection configuration
  - Environment variable setup
  - Docker Compose setup (optional)
- Update `.env.example` with database settings
- Include troubleshooting guide
- Reference: docs/phase6-persistence-mvp.md Section 10 (Phase 6 Exit Criteria - Deployment)

**Dependencies:** P6-2, P6-3

**Acceptance Criteria:**
- [ ] Database setup documentation created
- [ ] Migration instructions documented
- [ ] Connection configuration documented
- [ ] `.env.example` updated
- [ ] Docker Compose setup documented (if implemented)
- [ ] Troubleshooting guide included

---

### Issue P6-34: Create Repository Layer Documentation
**Labels:** `component:documentation`, `phase:6`, `priority:medium`
**Description:**
- Document repository layer architecture:
  - Repository interface and patterns
  - Tenant isolation enforcement
  - Idempotency helpers
  - Query helpers for Co-Pilot
- Include code examples for common operations
- Document event types and payload schemas
- Reference: docs/phase6-persistence-mvp.md Section 5, Section 6.2

**Dependencies:** P6-4 through P6-9

**Acceptance Criteria:**
- [ ] Repository layer architecture documented
- [ ] Code examples included
- [ ] Event types and schemas documented
- [ ] Tenant isolation patterns documented
- [ ] Idempotency patterns documented

---

### Issue P6-35: Update Architecture Documentation for Persistence
**Labels:** `component:documentation`, `phase:6`, `priority:medium`
**Description:**
- Update main architecture documentation to reflect persistence layer
- Document database schema and relationships
- Update data flow diagrams to include persistence
- Document event sourcing considerations for Phase 9
- Reference: docs/phase6-persistence-mvp.md Section 9 (Event Sourcing Considerations)

**Dependencies:** P6-1, P6-8

**Acceptance Criteria:**
- [ ] Architecture documentation updated
- [ ] Database schema documented
- [ ] Data flow diagrams updated
- [ ] Event sourcing considerations documented
- [ ] Phase 9 migration path documented

---

### Issue P6-36: Create Optional Docker Compose Setup
**Labels:** `component:deployment`, `phase:6`, `priority:low`
**Description:**
- Create optional Docker Compose configuration for:
  - PostgreSQL database
  - Backend service
  - UI service
- Include database initialization and migration steps
- Support development and testing environments
- Reference: docs/phase6-persistence-mvp.md Section 10 (Phase 6 Exit Criteria - Deployment)

**Dependencies:** P6-2, P6-3

**Acceptance Criteria:**
- [ ] Docker Compose configuration created
- [ ] PostgreSQL service configured
- [ ] Backend service configured
- [ ] UI service configured
- [ ] Database initialization automated
- [ ] Migration execution automated
- [ ] Documentation for Docker Compose setup

---

## Summary

**Total Issues:** 36
**High Priority:** 22
**Medium Priority:** 8
**Low Priority:** 6

**Components Covered:**
- Database Schema & Migrations (3 issues)
- Repository Layer - Base Infrastructure (2 issues)
- Exception Repository (2 issues)
- Exception Event Repository (2 issues)
- Tenant & Pack Repositories (3 issues)
- Playbook Repository (Phase 7 Preparation) (2 issues)
- Tool Definition Repository (Phase 8 Preparation) (1 issue)
- Agent Integration (6 issues)
- API Modifications (4 issues)
- UI Integration (3 issues)
- Testing (4 issues)
- Documentation & Deployment (4 issues)

**Phase 6 Persistence MVP Milestones (from docs/phase6-persistence-mvp.md):**
- System of Record First (every exception has durable truth source)
- Append-Only Event Log (every agent action recorded)
- Tenant Isolation (enforced at every storage boundary)
- Idempotent Writes (safe replaying of events)
- Repository Abstraction (domain logic calls repositories, not raw DB)
- Future-proof for Async (schema anticipates Phase 9 event-driven architecture)

**Key Phase 6 Persistence Focus Areas:**
1. **Database Foundation**: PostgreSQL schema with all core tables, indexes, and tenant isolation
2. **Repository Layer**: DB-backed repositories for all entities with async operations and tenant isolation
3. **Event Logging**: Append-only event log capturing all agent actions and state changes
4. **Agent Integration**: All agents persist state and events to database
5. **API Integration**: All APIs read from and write to database repositories
6. **UI Integration**: UI components fetch from DB-backed APIs with pagination and filtering
7. **Testing**: Comprehensive test coverage for repositories, agents, and APIs with database
8. **Documentation**: Complete setup, migration, and architecture documentation

**Spec References:**
- docs/phase6-persistence-mvp.md - Phase 6 Persistence & State MVP specification
- docs/01-architecture.md - Overall architecture document
- docs/03-data-models-apis.md - Backend API schemas and data models
- docs/06-mvp-plan.md - MVP milestones and implementation order

