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

Ingestion API: POST /exceptions/{tenantId} - Body: raw exception; Returns: exceptionId.
Status API: GET /exceptions/{tenantId}/{exceptionId} - Returns: full exception schema.
Admin API: POST /tenants/{tenantId}/packs/domain - Body: Domain Pack JSON.
Metrics API: GET /metrics/{tenantId} - Returns: {autoResolutionRate: float, mttr: float, etc.}
All APIs use HTTPS, JWT auth, and rate limiting.