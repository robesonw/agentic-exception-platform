# Data Models, Schemas & APIs

## Canonical Exception Schema
```json
{
  "exceptionId": "unique string",
  "tenantId": "string",
  "sourceSystem": "string (e.g., 'ERP')",
  "exceptionType": "string (from Domain Pack taxonomy)",
  "severity": "string (LOW|MEDIUM|HIGH|CRITICAL)",
  "timestamp": "ISO datetime",
  "rawPayload": "object (arbitrary source data)",
  "normalizedContext": "object (key-value pairs from normalization)",
  "detectedRules": ["array of violated rules"],
  "suggestedActions": ["array of potential resolutions"],
  "resolutionStatus": "string (OPEN|IN_PROGRESS|RESOLVED|ESCALATED)",
  "auditTrail": ["array of {action: string, timestamp: datetime, actor: string}"]
}

Domain Pack Schema

{
  "domainName": "string",
  "entities": "object (key: entityName, value: {attributes: object, relations: array})",
  "exceptionTypes": "object (key: typeName, value: {description: string, detectionRules: array})",
  "severityRules": ["array of {condition: string, severity: string}"],
  "tools": "object (key: toolName, value: {description: string, parameters: object, endpoint: string})",
  "playbooks": ["array of {exceptionType: string, steps: array of actions}"],
  "guardrails": "object ({allowLists: array, blockLists: array, humanApprovalThreshold: float})",
  "testSuites": ["array of {input: object, expectedOutput: object}"]
}


Tenant Policy Pack Schema


{
  "tenantId": "string",
  "domainName": "string (references Domain Pack)",
  "customSeverityOverrides": ["array of {exceptionType: string, severity: string}"],
  "customGuardrails": "object (similar to Domain Pack guardrails)",
  "approvedTools": ["array of toolNames"],
  "humanApprovalRules": ["array of {severity: string, requireApproval: boolean}"],
  "retentionPolicies": "object ({dataTTL: integer days})",
  "customPlaybooks": ["array similar to Domain Pack playbooks"]
}

Agent Message Contracts

As defined in Section 7: Input is exception + prior outputs; output is the standardized JSON with decision, confidence, evidence, nextStep.

Tools API Specification (Phase 8)

**List Tools:** GET /api/tools
- Query params: scope, enabled, name, type, page, pageSize
- Returns: List of tool definitions with enablement status

**Get Tool:** GET /api/tools/{tool_id}
- Returns: Tool definition with full configuration

**Execute Tool:** POST /api/tools/{tool_id}/execute
- Request Body: {payload: object, exceptionId?: string, actorType: string, actorId: string}
- Returns: Execution result with status (requested|running|succeeded|failed)

**List Executions:** GET /api/tools/executions
- Query params: tool_id, exception_id, status, actor_type, actor_id, page, pageSize
- Returns: Paginated list of tool executions

**Get Execution:** GET /api/tools/executions/{execution_id}
- Returns: Execution detail with input/output payloads

**Enable/Disable Tool:** PUT /api/tools/{tool_id}/enablement
- Request Body: {enabled: boolean}
- Returns: Enablement status

**Get Enablement:** GET /api/tools/{tool_id}/enablement
- Returns: Current enablement status for tenant

Security: API key + tenant scoping. All executions are audited.
See `docs/tools-guide.md` for complete API documentation and examples.

System-Level REST APIs

## Exception Ingestion API (Phase 9: Async Command Pattern)

**POST /exceptions/{tenantId}**
- **Request Body**: `{exception: object, source_system: string, ingestion_method: string}`
- **Response**: `202 Accepted` with `{exceptionId: string, status: "accepted", message: string}`
- **Behavior**: 
  - Validates request and redacts PII
  - Creates `ExceptionIngested` event
  - Stores event in EventStore (append-only)
  - Publishes event to Kafka topic "exceptions"
  - Returns `202 Accepted` immediately (does not wait for processing)
- **Phase 9**: Transformed to async command pattern. Processing happens asynchronously via workers.

**GET /exceptions/{tenantId}/{exceptionId}**
- **Response**: Full exception schema with current state
- **Behavior**: Reads from database only (no agent calls)
- **Phase 9**: Query API - reads from materialized views (database tables)

**GET /exceptions/{exceptionId}/events**
- **Response**: List of events for exception (trace)
- **Query Params**: `page`, `page_size`, `event_type`, `start_timestamp`, `end_timestamp`
- **Behavior**: Queries EventStoreRepository by correlation_id (exception_id)

**GET /exceptions/{tenantId}/{exceptionId}/trace**
- **Response**: Trace summary for exception
- **Behavior**: Uses TraceService to aggregate events

## Playbook APIs (Phase 9: Async Command Pattern)

**POST /exceptions/{tenantId}/{exceptionId}/playbook/recalculate**
- **Response**: `202 Accepted` with `{exceptionId: string, status: "accepted", message: string}`
- **Behavior**: 
  - Creates `PlaybookRecalculationRequested` event
  - Publishes event to Kafka
  - Returns `202 Accepted` immediately
- **Phase 9**: Transformed to async command pattern

**POST /exceptions/{tenantId}/{exceptionId}/playbook/steps/{step_order}/complete**
- **Response**: `202 Accepted` with `{exceptionId: string, status: "accepted", message: string}`
- **Behavior**: 
  - Creates `PlaybookStepCompletionRequested` event
  - Publishes event to Kafka
  - Returns `202 Accepted` immediately
- **Phase 9**: Transformed to async command pattern

**GET /exceptions/{tenantId}/{exceptionId}/playbook**
- **Response**: Playbook status with steps
- **Behavior**: Reads from database only (no agent calls)
- **Phase 9**: Query API - reads from materialized views

## Tool Execution API (Phase 9: Async Command Pattern)

**POST /api/tools/{tool_id}/execute**
- **Request Body**: `{payload: object, exceptionId?: string, actorType: string, actorId: string}`
- **Response**: `202 Accepted` with `{executionId: string, status: "accepted", message: string}`
- **Behavior**: 
  - Validates request
  - Creates `tool_execution` record in "requested" state
  - Creates `ToolExecutionRequested` event
  - Publishes event to Kafka
  - Returns `202 Accepted` immediately
- **Phase 9**: Transformed to async command pattern

**GET /api/tools/executions**
- **Response**: Paginated list of tool executions
- **Behavior**: Reads from database only (no agent calls)
- **Phase 9**: Query API - reads from materialized views

## Audit API (Phase 9)

**GET /api/audit/exceptions/{tenantId}/{exceptionId}**
- **Response**: Paginated audit trail for exception
- **Query Params**: `page`, `page_size`, `event_type`, `start_timestamp`, `end_timestamp`
- **Behavior**: Queries EventStoreRepository (source of truth for audit)

**GET /api/audit/tenants/{tenantId}**
- **Response**: Paginated audit trail for tenant
- **Query Params**: `page`, `page_size`, `event_type`, `exception_id`, `correlation_id`, `start_timestamp`, `end_timestamp`
- **Behavior**: Queries EventStoreRepository with tenant isolation

## Admin APIs

**POST /tenants/{tenantId}/packs/domain** - Body: Domain Pack JSON.
**GET /metrics/{tenantId}** - Returns: `{autoResolutionRate: float, mttr: float, etc.}`

## API Patterns (Phase 9)

### Command Pattern (Write Operations)
- **POST** endpoints that modify state return `202 Accepted`
- Events are published to Kafka for asynchronous processing
- Response includes `exceptionId` or `executionId` for tracking
- Processing happens asynchronously via workers

### Query Pattern (Read Operations)
- **GET** endpoints read from database only (no agent calls)
- No event publishing or worker processing
- Fast, consistent reads from materialized views

### Authentication and Security
- All APIs use HTTPS, JWT auth, and rate limiting
- Tenant isolation enforced at API, broker, and worker levels
- PII redaction at ingestion point

## API Response Codes

- **202 Accepted**: Command accepted, processing asynchronously
- **200 OK**: Query successful, data returned
- **400 Bad Request**: Invalid request format or parameters
- **403 Forbidden**: Tenant isolation violation or unauthorized access
- **404 Not Found**: Resource not found
- **500 Internal Server Error**: Server error (check logs)