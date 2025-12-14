# Phase 8 – Tool Registry & Tool Execution MVP
SentinAI – Multi-Tenant, Domain-Abstracted Exception Platform

---

## 1. Purpose
Phase 8 turns “call_tool” from a stub into a governed, tenant-safe capability:
- A Tool Registry (global + tenant tools)
- Typed tool schemas
- Allow-list enforcement and policy gating
- Safe tool execution with audit logging
- UI for managing tools and running approved tools from playbooks

---

## 2. Scope (MVP)

### In Scope
- ToolDefinition schema enforcement:
  - name, type, description
  - input_schema (JSON Schema / Pydantic)
  - output_schema
  - auth_type (none, api_key, oauth_stub)
  - endpoint config (for http tools)
  - tenant scope: global or tenant-specific
- Tool Registry backend:
  - CRUD for tool definitions (Phase 6 API exists; add missing validations + versioning if needed)
  - Tool enable/disable per tenant (policy)
- Tool Execution backend:
  - Execute tool by tool_id with validated payload
  - Enforce allow-list and tenant scope
  - Persist ToolExecution events (requested, started, completed, failed)
  - Store execution results (DB table or event payload for MVP)
- Integration with Playbooks:
  - Playbook step type `call_tool` triggers tool execution via ToolExecutionService
  - For MVP: tools execute only when initiated by human “Complete step”
- UI:
  - Tools page: list tools (global + tenant) with filters
  - Tool detail: schemas, config, enabled status
  - “Run Tool” modal: paste payload, validate, execute, show result
  - Exception Detail: show tool execution results in timeline

### Out of Scope (Phase 8)
- Full OAuth flows (we stub credentials storage safely)
- Marketplace of tools
- Complex multi-step tool chaining
- Background/async executions (Phase 9)

---

## 3. Data Model (MVP)

### 3.1 tool_execution table (recommended)
Fields:
- id (uuid)
- tenant_id
- tool_id
- exception_id (nullable)
- status (requested|running|succeeded|failed)
- requested_by_actor_type
- requested_by_actor_id
- input_payload (jsonb)
- output_payload (jsonb)
- error_message (nullable)
- created_at, updated_at

Alternative MVP: store output in exception_event payload, but DB table is better.

---

## 4. Backend Components

### 4.1 ToolValidationService
- Validate payload against input_schema
- Enforce tool enablement and tenant scope
- Redact secrets in logs/events

### 4.2 ToolExecutionService
- execute_tool(tenant_id, tool_id, payload, actor, exception_id=None)
- For http tools:
  - safe request execution using configured endpoint
  - timeout + retry (minimal)
  - do not allow arbitrary URLs (must be from ToolDefinition)
- Emit events:
  - ToolExecutionRequested
  - ToolExecutionCompleted / ToolExecutionFailed

### 4.3 Tool Providers (MVP)
Implement at least:
- HttpToolProvider (generic REST)
- DummyToolProvider (for demo)

Optional:
- EmailNotificationToolProvider (SMTP or stub)
- WebhookToolProvider

---

## 5. API Endpoints (Phase 8)

- GET /api/tools (already exists) — ensure filters & scope
- POST /api/tools (already exists) — enforce schemas & validation
- POST /api/tools/{tool_id}/execute
  - Body: payload + optional exception_id
  - Returns: execution result
- GET /api/tools/executions
  - filter by tenant_id, tool_id, exception_id, status, date range
- GET /api/tools/executions/{execution_id}

---

## 6. UI (Phase 8)
- Add “Tools” section in sidebar
- Tools list page:
  - scope filter: global/tenant/all
  - status filter: enabled/disabled
- Tool detail:
  - schemas view
  - execute button
- Run tool modal:
  - JSON payload editor
  - validate button
  - execute button
  - output viewer
- Exception detail:
  - show tool execution events/results in timeline

---

## 7. Security & Governance (MVP)
- Tenant isolation ALWAYS
- Tool scope restrictions:
  - tenant tool visible only to tenant
  - global tool visible to all (readonly config unless admin)
- URL allow-list:
  - http tools must use endpoint from ToolDefinition only
- Secret handling:
  - secrets never logged
  - in MVP store secrets as env vars or masked placeholders only
- Audit:
  - tool execution emits events + persisted tool_execution record

---

## 8. Exit Criteria
- Tools can be created/updated with schema validation
- Tools can be executed safely with validated inputs
- Executions are persisted and visible in UI
- Playbook call_tool step executes a tool on step completion
- Timeline shows tool executions
- Unit + API tests for validation + execution
- docs updated + minimal runbook
