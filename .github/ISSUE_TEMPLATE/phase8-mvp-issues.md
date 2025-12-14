# Phase 8 Tool Registry & Tool Execution MVP - GitHub Issues Checklist

## Component: Tool Definition Schema & Validation

### Issue P8-1: Enhance ToolDefinition Schema with Full Validation
**Labels:** `component:tool-registry`, `phase:8`, `priority:high`
**Description:**
- Enhance ToolDefinition schema to enforce all required fields:
  - name, type, description
  - input_schema (JSON Schema / Pydantic)
  - output_schema
  - auth_type (none, api_key, oauth_stub)
  - endpoint config (for http tools)
  - tenant scope: global or tenant-specific
- Add schema validation for tool definitions on create/update
- Ensure backward compatibility with existing tools
- Reference: docs/phase8-tools-mvp.md Section 3 (Data Model), Section 4.1

**Dependencies:** P6-15 (Tool Repository - if exists)

**Acceptance Criteria:**
- [ ] ToolDefinition schema enhanced with all required fields
- [ ] Input/output schema validation implemented
- [ ] Auth type validation functional
- [ ] Endpoint config validation for http tools
- [ ] Tenant scope validation functional
- [ ] Backward compatibility maintained
- [ ] Unit tests for schema validation
- [ ] Integration tests for tool CRUD operations

---

### Issue P8-2: Implement ToolValidationService
**Labels:** `component:tool-registry`, `phase:8`, `priority:high`
**Description:**
- Implement ToolValidationService with methods:
  - `validate_payload(tool_id, payload)` - validate payload against input_schema
  - `check_tool_enabled(tenant_id, tool_id)` - enforce tool enablement per tenant
  - `check_tenant_scope(tenant_id, tool_id)` - enforce tenant scope restrictions
  - `redact_secrets(payload, tool_definition)` - redact secrets in logs/events
- Support JSON Schema validation for input payloads
- Enforce tenant isolation in validation checks
- Reference: docs/phase8-tools-mvp.md Section 4.1

**Dependencies:** P8-1

**Acceptance Criteria:**
- [ ] ToolValidationService implemented
- [ ] Payload validation against input_schema functional
- [ ] Tool enablement check per tenant functional
- [ ] Tenant scope validation functional
- [ ] Secret redaction in logs/events implemented
- [ ] JSON Schema validation working
- [ ] Unit tests for validation service
- [ ] Edge cases tested (invalid payloads, disabled tools, scope violations)

---

## Component: Tool Execution Backend

### Issue P8-3: Implement tool_execution Database Table and Repository
**Labels:** `component:tool-execution`, `phase:8`, `priority:high`
**Description:**
- Create tool_execution database table with fields:
  - id (uuid), tenant_id, tool_id
  - exception_id (nullable)
  - status (requested|running|succeeded|failed)
  - requested_by_actor_type, requested_by_actor_id
  - input_payload (jsonb), output_payload (jsonb)
  - error_message (nullable)
  - created_at, updated_at
- Implement ToolExecutionRepository with CRUD operations
- Add database migrations
- Reference: docs/phase8-tools-mvp.md Section 3.1

**Dependencies:** P6-1 (Database Setup)

**Acceptance Criteria:**
- [ ] tool_execution table created with all required fields
- [ ] Database migration implemented
- [ ] ToolExecutionRepository implemented
- [ ] CRUD operations functional
- [ ] Tenant isolation enforced in queries
- [ ] Unit tests for repository
- [ ] Integration tests with database

---

### Issue P8-4: Implement ToolExecutionService - Core Execution Framework
**Labels:** `component:tool-execution`, `phase:8`, `priority:high`
**Description:**
- Implement ToolExecutionService with method:
  - `execute_tool(tenant_id, tool_id, payload, actor, exception_id=None)`
- Load tool definition from repository
- Validate tool via ToolValidationService
- Create tool_execution record with status "requested"
- Route to appropriate ToolProvider based on tool type
- Update execution status (running, succeeded, failed)
- Store execution results in tool_execution table
- Emit events: ToolExecutionRequested, ToolExecutionCompleted, ToolExecutionFailed
- Reference: docs/phase8-tools-mvp.md Section 4.2

**Dependencies:** P8-2, P8-3, P8-5

**Acceptance Criteria:**
- [ ] ToolExecutionService implemented
- [ ] Tool definition loading functional
- [ ] Validation integration working
- [ ] Execution record creation functional
- [ ] Status updates working (requested → running → succeeded/failed)
- [ ] Results stored in database
- [ ] Events emitted for execution lifecycle
- [ ] Unit tests for execution service
- [ ] Integration tests with providers

---

### Issue P8-5: Implement Tool Providers - HttpToolProvider and DummyToolProvider
**Labels:** `component:tool-execution`, `phase:8`, `priority:high`
**Description:**
- Implement HttpToolProvider:
  - Execute HTTP requests using configured endpoint from ToolDefinition
  - Support auth_type: none, api_key (from env/config)
  - Enforce URL allow-list (only use endpoint from ToolDefinition, no arbitrary URLs)
  - Implement timeout and basic retry logic
  - Handle HTTP errors and timeouts gracefully
- Implement DummyToolProvider:
  - Return mock success response for testing/demo
  - Support configurable delay and response payload
- Create ToolProvider interface/base class
- Reference: docs/phase8-tools-mvp.md Section 4.3

**Dependencies:** P8-1

**Acceptance Criteria:**
- [ ] HttpToolProvider implemented
- [ ] Endpoint configuration from ToolDefinition used
- [ ] Auth support (none, api_key) functional
- [ ] URL allow-list enforcement working
- [ ] Timeout and retry logic implemented
- [ ] DummyToolProvider implemented
- [ ] ToolProvider interface/base class created
- [ ] Unit tests for both providers
- [ ] Integration tests for HTTP provider

---

### Issue P8-6: Implement Tool Execution API Endpoints
**Labels:** `component:api`, `phase:8`, `priority:high`
**Description:**
- Implement POST /api/tools/{tool_id}/execute endpoint:
  - Accept payload + optional exception_id in request body
  - Validate tenant access and tool scope
  - Execute tool via ToolExecutionService
  - Return execution result with status and output
- Implement GET /api/tools/executions endpoint:
  - Filter by tenant_id, tool_id, exception_id, status, date range
  - Support pagination
  - Return list of execution records
- Implement GET /api/tools/executions/{execution_id} endpoint:
  - Return single execution record with full details
  - Validate tenant access
- Reference: docs/phase8-tools-mvp.md Section 5

**Dependencies:** P8-4

**Acceptance Criteria:**
- [ ] POST /api/tools/{tool_id}/execute endpoint functional
- [ ] GET /api/tools/executions endpoint functional
- [ ] GET /api/tools/executions/{execution_id} endpoint functional
- [ ] Tenant access validation enforced
- [ ] Filtering and pagination working
- [ ] Error handling for invalid requests
- [ ] API tests for all endpoints
- [ ] Integration tests with execution service

---

## Component: Tool Registry Enhancements

### Issue P8-7: Implement Tool Enable/Disable Per Tenant Policy
**Labels:** `component:tool-registry`, `phase:8`, `priority:medium`
**Description:**
- Add tool enablement tracking per tenant (policy table or tool_tenant_policy table)
- Support enabling/disabling tools for specific tenants
- Update ToolValidationService to check enablement status
- Add API endpoint or admin interface to manage tool enablement
- Ensure global tools can be disabled per tenant
- Reference: docs/phase8-tools-mvp.md Section 2 (Tool Registry backend)

**Dependencies:** P8-1, P8-2

**Acceptance Criteria:**
- [ ] Tool enablement tracking per tenant implemented
- [ ] Enable/disable functionality functional
- [ ] Validation service checks enablement status
- [ ] API/admin interface for managing enablement
- [ ] Global tools can be disabled per tenant
- [ ] Unit tests for enablement logic
- [ ] Integration tests for policy enforcement

---

### Issue P8-8: Enhance Tool Registry API with Scope and Filtering
**Labels:** `component:api`, `phase:8`, `priority:medium`
**Description:**
- Enhance GET /api/tools endpoint (already exists):
  - Add scope filter: global/tenant/all
  - Add status filter: enabled/disabled
  - Ensure tenant isolation (tenant tools only visible to tenant)
  - Global tools visible to all tenants (readonly config unless admin)
- Enhance POST /api/tools endpoint (already exists):
  - Enforce schema validation via ToolValidationService
  - Validate tenant scope restrictions
  - Add versioning support if needed
- Reference: docs/phase8-tools-mvp.md Section 5, Section 7

**Dependencies:** P8-1, P8-7

**Acceptance Criteria:**
- [ ] GET /api/tools supports scope and status filters
- [ ] Tenant isolation enforced in tool listing
- [ ] Global tools visible to all tenants
- [ ] POST /api/tools enforces schema validation
- [ ] Tenant scope restrictions validated
- [ ] API tests for filtering and scope
- [ ] Integration tests for tool CRUD

---

## Component: Playbook Integration

### Issue P8-9: Integrate Tool Execution with Playbook call_tool Step
**Labels:** `component:playbook`, `phase:8`, `priority:high`
**Description:**
- Update Playbook Execution Service to handle `call_tool` step type
- When playbook step with action `call_tool` is completed:
  - Extract tool_id and payload from step configuration
  - Invoke ToolExecutionService.execute_tool()
  - Pass exception_id and actor context
  - Store execution result in tool_execution table
  - Link execution to exception via exception_id
- For MVP: tools execute only when initiated by human "Complete step" action
- Update step completion logic to handle tool execution results
- Reference: docs/phase8-tools-mvp.md Section 2 (Integration with Playbooks)

**Dependencies:** P8-4, P7-4 (Playbook Step Action Executors)

**Acceptance Criteria:**
- [ ] Playbook Execution Service handles call_tool step type
- [ ] Tool execution triggered on step completion
- [ ] Exception context passed to tool execution
- [ ] Execution results stored and linked to exception
- [ ] Human-initiated execution only (no auto-execution)
- [ ] Unit tests for playbook-tool integration
- [ ] Integration tests with playbook execution

---

## Component: UI - Tools Management

### Issue P8-10: Implement Tools List Page
**Labels:** `component:ui`, `phase:8`, `priority:high`
**Description:**
- Add "Tools" section in sidebar navigation
- Create Tools list page:
  - Display tools (global + tenant) in table/list view
  - Scope filter: global/tenant/all
  - Status filter: enabled/disabled
  - Show tool name, type, description, scope, status
  - Link to tool detail page
- Use TanStack Query for data fetching
- Implement loading and error states
- Reference: docs/phase8-tools-mvp.md Section 6

**Dependencies:** P8-8

**Acceptance Criteria:**
- [ ] Tools section added to sidebar
- [ ] Tools list page implemented
- [ ] Scope and status filters functional
- [ ] Tool information displayed correctly
- [ ] Loading and error states handled
- [ ] Navigation to tool detail works
- [ ] Responsive layout (desktop-first acceptable)
- [ ] Unit tests for components

---

### Issue P8-11: Implement Tool Detail Page
**Labels:** `component:ui`, `phase:8`, `priority:high`
**Description:**
- Create Tool detail page showing:
  - Tool name, type, description
  - Input schema (JSON Schema viewer/formatted display)
  - Output schema (JSON Schema viewer/formatted display)
  - Auth type and endpoint config
  - Tenant scope and enabled status
  - "Execute Tool" button
- Display tool execution history (recent executions)
- Link to execution detail pages
- Reference: docs/phase8-tools-mvp.md Section 6

**Dependencies:** P8-10, P8-6

**Acceptance Criteria:**
- [ ] Tool detail page implemented
- [ ] All tool information displayed
- [ ] Schema viewer/formatter functional
- [ ] Execute Tool button present
- [ ] Execution history displayed
- [ ] Navigation to execution detail works
- [ ] Loading and error states handled
- [ ] Unit tests for components

---

### Issue P8-12: Implement Run Tool Modal
**Labels:** `component:ui`, `phase:8`, `priority:high`
**Description:**
- Create "Run Tool" modal dialog:
  - JSON payload editor (with syntax highlighting)
  - "Validate" button to check payload against input_schema
  - "Execute" button to run tool
  - Output viewer to display execution results
  - Show execution status (requested, running, succeeded, failed)
  - Display error messages if execution fails
  - Optional: link to exception if exception_id provided
- Integrate with POST /api/tools/{tool_id}/execute endpoint
- Handle async execution status updates (polling or websocket)
- Reference: docs/phase8-tools-mvp.md Section 6

**Dependencies:** P8-11, P8-6

**Acceptance Criteria:**
- [ ] Run Tool modal implemented
- [ ] JSON payload editor functional
- [ ] Validate button checks payload against schema
- [ ] Execute button triggers tool execution
- [ ] Output viewer displays results
- [ ] Execution status displayed
- [ ] Error handling functional
- [ ] Exception linking works (if applicable)
- [ ] Unit tests for modal component

---

### Issue P8-13: Integrate Tool Executions in Exception Detail Timeline
**Labels:** `component:ui`, `phase:8`, `priority:medium`
**Description:**
- Update Exception Detail page to show tool execution events in timeline
- Display tool execution results:
  - Tool name and execution status
  - Execution timestamp
  - Link to execution detail page
  - Show execution output summary (truncated if long)
- Integrate with GET /api/tools/executions?exception_id={id} endpoint
- Style tool execution events distinctively in timeline
- Reference: docs/phase8-tools-mvp.md Section 6

**Dependencies:** P8-6, P4-* (Exception Detail page)

**Acceptance Criteria:**
- [ ] Tool executions displayed in exception timeline
- [ ] Execution information shown correctly
- [ ] Links to execution detail functional
- [ ] Output summary displayed
- [ ] Distinctive styling for tool events
- [ ] Loading and error states handled
- [ ] Unit tests for timeline integration

---

## Component: Security & Audit

### Issue P8-14: Implement Secret Handling and Security Controls
**Labels:** `component:security`, `phase:8`, `priority:high`
**Description:**
- Implement secret handling:
  - Secrets never logged in plain text
  - Store secrets as env vars or masked placeholders in MVP
  - Redact secrets in audit logs and events
  - Support api_key auth type with secure storage
- Enforce URL allow-list:
  - Http tools must use endpoint from ToolDefinition only
  - Block arbitrary URLs in tool execution
- Add security logging for tool execution attempts
- Reference: docs/phase8-tools-mvp.md Section 7

**Dependencies:** P8-4, P8-5

**Acceptance Criteria:**
- [ ] Secret redaction in logs implemented
- [ ] Secrets stored securely (env vars or masked)
- [ ] API key auth with secure storage functional
- [ ] URL allow-list enforcement working
- [ ] Arbitrary URLs blocked
- [ ] Security logging for execution attempts
- [ ] Unit tests for secret handling
- [ ] Security tests for URL validation

---

### Issue P8-15: Implement Tool Execution Audit Trail
**Labels:** `component:audit`, `phase:8`, `priority:medium`
**Description:**
- Ensure all tool executions generate audit trail:
  - ToolExecutionRequested event with actor, tool_id, payload (redacted)
  - ToolExecutionCompleted/ToolExecutionFailed events with results
  - Persisted tool_execution records in database
- Link tool executions to exception events when applicable
- Support audit trail querying via API
- Ensure tenant isolation in audit queries
- Reference: docs/phase8-tools-mvp.md Section 7

**Dependencies:** P8-4, P8-3

**Acceptance Criteria:**
- [ ] Tool execution events emitted
- [ ] Audit trail persisted in database
- [ ] Events linked to exceptions when applicable
- [ ] Audit trail querying functional
- [ ] Tenant isolation in audit queries enforced
- [ ] Unit tests for audit trail
- [ ] Integration tests for event emission

---

## Component: Testing & Documentation

### Issue P8-16: Implement Unit and Integration Tests for Tool Execution
**Labels:** `component:testing`, `phase:8`, `priority:high`
**Description:**
- Write unit tests for:
  - ToolValidationService (validation, enablement, scope checks)
  - ToolExecutionService (execution flow, status updates, error handling)
  - Tool Providers (HttpToolProvider, DummyToolProvider)
  - Tool Repository operations
- Write integration tests for:
  - Tool execution end-to-end flow
  - API endpoints (execute, executions list/detail)
  - Playbook-tool integration
  - Tenant isolation in tool operations
- Achieve >80% code coverage for tool execution components
- Reference: docs/phase8-tools-mvp.md Section 8

**Dependencies:** P8-4, P8-5, P8-6, P8-9

**Acceptance Criteria:**
- [ ] Unit tests for all tool execution components
- [ ] Integration tests for execution flow
- [ ] API endpoint tests implemented
- [ ] Playbook integration tests functional
- [ ] Tenant isolation tests passing
- [ ] Code coverage >80%
- [ ] All tests passing
- [ ] Test coverage report generated

---

### Issue P8-17: Update Documentation and Create Runbook
**Labels:** `component:documentation`, `phase:8`, `priority:medium`
**Description:**
- Update main project documentation with Phase 8 tool execution capabilities
- Document tool definition schema and examples
- Create runbook for:
  - Creating and configuring tools
  - Enabling/disabling tools per tenant
  - Executing tools manually
  - Troubleshooting tool execution failures
  - Security best practices for tool configuration
- Update API documentation with tool execution endpoints
- Reference: docs/phase8-tools-mvp.md Section 8

**Dependencies:** All P8 issues

**Acceptance Criteria:**
- [ ] Main documentation updated
- [ ] Tool schema documented with examples
- [ ] Runbook created with all sections
- [ ] API documentation updated
- [ ] Security best practices documented
- [ ] Examples and troubleshooting guides included

---

## Summary

**Total Issues:** 17
**High Priority:** 12
**Medium Priority:** 5

**Components Covered:**
- Tool Definition Schema & Validation (2 issues)
- Tool Execution Backend (4 issues)
- Tool Registry Enhancements (2 issues)
- Playbook Integration (1 issue)
- UI - Tools Management (4 issues)
- Security & Audit (2 issues)
- Testing & Documentation (2 issues)

**Implementation Order:**
1. P8-1: ToolDefinition schema enhancement
2. P8-2: ToolValidationService
3. P8-3: tool_execution database table
4. P8-5: Tool Providers (needed for execution)
5. P8-4: ToolExecutionService (depends on validation and providers)
6. P8-6: Tool Execution API endpoints
7. P8-7: Tool enable/disable per tenant
8. P8-8: Tool Registry API enhancements
9. P8-9: Playbook integration
10. P8-10-P8-13: UI components (can be parallel)
11. P8-14-P8-15: Security and audit
12. P8-16-P8-17: Testing and documentation

