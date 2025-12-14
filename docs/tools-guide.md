# Tool Registry & Execution Guide

## Overview

Phase 8 introduces a comprehensive Tool Registry and Execution system that enables safe, governed tool execution within the platform. Tools are domain-abstracted, tenant-isolated, and fully audited.

## Table of Contents

1. [Tool Schema](#tool-schema)
2. [Execution APIs](#execution-apis)
3. [Enable/Disable Behavior](#enabledisable-behavior)
4. [Security Guidance](#security-guidance)
5. [Troubleshooting Runbook](#troubleshooting-runbook)

---

## Tool Schema

### Tool Definition Structure

A tool definition consists of the following required fields:

```json
{
  "name": "string (required, unique per tenant)",
  "type": "string (required, e.g., 'http', 'webhook', 'dummy')",
  "description": "string (required)",
  "inputSchema": {
    "type": "object",
    "properties": {
      "param1": {"type": "string"},
      "param2": {"type": "number"}
    },
    "required": ["param1"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "result": {"type": "string"}
    }
  },
  "authType": "none|api_key|oauth_stub",
  "endpointConfig": {
    "url": "https://api.example.com/endpoint",
    "method": "POST|GET|PUT|DELETE",
    "headers": {},
    "timeoutSeconds": 30.0
  },
  "tenantScope": "global|tenant"
}
```

### Field Descriptions

#### Required Fields

- **name**: Unique tool name within tenant scope. Must be a valid identifier.
- **type**: Tool type. Supported types:
  - `http`: HTTP/REST API tools
  - `webhook`: Webhook-based tools
  - `dummy`: Testing/demo tools
  - `email`: Email notification tools (future)
  - `workflow`: Workflow orchestration tools (future)
- **description**: Human-readable description of the tool's purpose.
- **inputSchema**: JSON Schema defining the expected input parameters. Must be a valid JSON Schema object.
- **outputSchema**: JSON Schema defining the expected output structure. Must be a valid JSON Schema object.
- **authType**: Authentication method:
  - `none`: No authentication required
  - `api_key`: API key authentication (stored in environment variables)
  - `oauth_stub`: OAuth authentication (stub implementation for MVP)

#### Optional Fields

- **endpointConfig**: Required for `http` and `webhook` type tools. Contains:
  - **url**: Endpoint URL (must be HTTPS for security)
  - **method**: HTTP method (default: POST)
  - **headers**: Additional HTTP headers (optional)
  - **timeoutSeconds**: Request timeout in seconds (optional, default: 30.0)
- **tenantScope**: Tool visibility scope:
  - `global`: Visible to all tenants (read-only config unless admin)
  - `tenant`: Visible only to the creating tenant (default)

### Example Tool Definitions

#### Example 1: HTTP Tool with API Key Authentication

```json
{
  "name": "sendNotification",
  "type": "http",
  "description": "Send notification via external API",
  "inputSchema": {
    "type": "object",
    "properties": {
      "recipient": {
        "type": "string",
        "description": "Email address or user ID"
      },
      "message": {
        "type": "string",
        "description": "Notification message"
      },
      "priority": {
        "type": "string",
        "enum": ["low", "medium", "high"],
        "default": "medium"
      }
    },
    "required": ["recipient", "message"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "notificationId": {"type": "string"},
      "status": {"type": "string"},
      "sentAt": {"type": "string", "format": "date-time"}
    }
  },
  "authType": "api_key",
  "endpointConfig": {
    "url": "https://api.notificationservice.com/v1/send",
    "method": "POST",
    "headers": {
      "Content-Type": "application/json"
    },
    "timeoutSeconds": 10.0
  },
  "tenantScope": "tenant"
}
```

**Environment Variable Setup:**
```bash
# API key stored as environment variable
export TOOL_SENDNOTIFICATION_API_KEY="sk-1234567890abcdef"
```

#### Example 2: Global HTTP Tool (No Authentication)

```json
{
  "name": "getWeather",
  "type": "http",
  "description": "Get weather information for a location",
  "inputSchema": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "City name or coordinates"
      },
      "units": {
        "type": "string",
        "enum": ["celsius", "fahrenheit"],
        "default": "celsius"
      }
    },
    "required": ["location"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "temperature": {"type": "number"},
      "condition": {"type": "string"},
      "humidity": {"type": "number"}
    }
  },
  "authType": "none",
  "endpointConfig": {
    "url": "https://api.weatherservice.com/v1/current",
    "method": "GET",
    "timeoutSeconds": 5.0
  },
  "tenantScope": "global"
}
```

#### Example 3: Dummy Tool (Testing)

```json
{
  "name": "testTool",
  "type": "dummy",
  "description": "Test tool for development and testing",
  "inputSchema": {
    "type": "object",
    "properties": {
      "input": {"type": "string"}
    }
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "output": {"type": "string"},
      "processed": {"type": "boolean"}
    }
  },
  "authType": "none",
  "tenantScope": "tenant"
}
```

### Schema Validation Rules

1. **Input Schema Validation**: All input payloads are validated against `inputSchema` before execution.
2. **Required Fields**: Fields marked as `required` in the schema must be present in the payload.
3. **Type Validation**: Payload values must match the schema types (string, number, boolean, object, array).
4. **HTTP Tools**: Must include `endpointConfig` with a valid HTTPS URL.
5. **API Key Tools**: Must have corresponding environment variable set: `TOOL_{TOOLNAME}_API_KEY` (uppercase, underscores).

---

## Execution APIs

### List Tools

**Endpoint:** `GET /api/tools`

**Query Parameters:**
- `scope`: Filter by scope (`global`, `tenant`, `all`) - default: `all`
- `enabled`: Filter by enabled status (`true`, `false`, `all`) - default: `all`
- `name`: Filter by tool name (partial match)
- `type`: Filter by tool type
- `page`: Page number (default: 1)
- `pageSize`: Items per page (default: 20)

**Response:**
```json
{
  "items": [
    {
      "toolId": 1,
      "tenantId": "TENANT_001",
      "name": "sendNotification",
      "type": "http",
      "config": {...},
      "enabled": true,
      "createdAt": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "pageSize": 20,
  "totalPages": 1
}
```

### Get Tool Detail

**Endpoint:** `GET /api/tools/{tool_id}`

**Response:**
```json
{
  "toolId": 1,
  "tenantId": "TENANT_001",
  "name": "sendNotification",
  "type": "http",
  "config": {
    "description": "Send notification via external API",
    "inputSchema": {...},
    "outputSchema": {...},
    "authType": "api_key",
    "endpointConfig": {...},
    "tenantScope": "tenant"
  },
  "enabled": true,
  "createdAt": "2024-01-15T10:30:00Z"
}
```

### Execute Tool

**Endpoint:** `POST /api/tools/{tool_id}/execute`

**Request Body:**
```json
{
  "payload": {
    "recipient": "user@example.com",
    "message": "Test notification",
    "priority": "high"
  },
  "exceptionId": "EXC_001",
  "actorType": "user",
  "actorId": "user_123"
}
```

**Response:**
```json
{
  "executionId": "550e8400-e29b-41d4-a716-446655440000",
  "tenantId": "TENANT_001",
  "toolId": 1,
  "exceptionId": "EXC_001",
  "status": "succeeded",
  "requestedByActorType": "user",
  "requestedByActorId": "user_123",
  "inputPayload": {
    "recipient": "user@example.com",
    "message": "Test notification",
    "priority": "high"
  },
  "outputPayload": {
    "notificationId": "notif_123",
    "status": "sent",
    "sentAt": "2024-01-15T10:35:00Z"
  },
  "createdAt": "2024-01-15T10:35:00Z",
  "updatedAt": "2024-01-15T10:35:00Z"
}
```

**Status Values:**
- `requested`: Execution has been requested
- `running`: Execution is in progress
- `succeeded`: Execution completed successfully
- `failed`: Execution failed with an error

### List Tool Executions

**Endpoint:** `GET /api/tools/executions`

**Query Parameters:**
- `tool_id`: Filter by tool ID
- `exception_id`: Filter by exception ID
- `status`: Filter by status (`requested`, `running`, `succeeded`, `failed`)
- `actor_type`: Filter by actor type (`user`, `agent`, `system`)
- `actor_id`: Filter by actor ID
- `page`: Page number (default: 1)
- `pageSize`: Items per page (default: 20)

**Response:**
```json
{
  "items": [
    {
      "executionId": "550e8400-e29b-41d4-a716-446655440000",
      "tenantId": "TENANT_001",
      "toolId": 1,
      "exceptionId": "EXC_001",
      "status": "succeeded",
      "requestedByActorType": "user",
      "requestedByActorId": "user_123",
      "inputPayload": {...},
      "outputPayload": {...},
      "createdAt": "2024-01-15T10:35:00Z",
      "updatedAt": "2024-01-15T10:35:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "pageSize": 20,
  "totalPages": 1
}
```

### Get Execution Detail

**Endpoint:** `GET /api/tools/executions/{execution_id}`

**Response:** Same as single execution item in list response.

---

## Enable/Disable Behavior

### Tool Enablement

Tools can be enabled or disabled per tenant. This provides fine-grained control over which tools are available for execution.

### Enable Tool

**Endpoint:** `PUT /api/tools/{tool_id}/enablement`

**Request Body:**
```json
{
  "enabled": true
}
```

**Response:**
```json
{
  "toolId": 1,
  "tenantId": "TENANT_001",
  "enabled": true,
  "updatedAt": "2024-01-15T10:40:00Z"
}
```

### Disable Tool

**Endpoint:** `PUT /api/tools/{tool_id}/enablement`

**Request Body:**
```json
{
  "enabled": false
}
```

### Get Enablement Status

**Endpoint:** `GET /api/tools/{tool_id}/enablement`

**Response:**
```json
{
  "toolId": 1,
  "tenantId": "TENANT_001",
  "enabled": true,
  "updatedAt": "2024-01-15T10:40:00Z"
}
```

### Enablement Behavior

1. **Default State**: New tools are enabled by default.
2. **Execution Blocking**: Disabled tools cannot be executed. Attempts to execute a disabled tool will return a `403 Forbidden` error.
3. **Scope Interaction**:
   - **Global Tools**: Can be enabled/disabled per tenant independently.
   - **Tenant Tools**: Enablement is tenant-specific.
4. **Playbook Integration**: Playbook steps that reference disabled tools will fail validation.
5. **UI Visibility**: Disabled tools are still visible in the UI but marked as disabled.

### Enablement Use Cases

- **Maintenance**: Temporarily disable tools during maintenance or updates.
- **Security**: Disable tools that have security vulnerabilities.
- **Testing**: Disable production tools while testing new versions.
- **Compliance**: Disable tools that don't meet compliance requirements.

---

## Security Guidance

### URL Allow-List

**Critical**: HTTP tools can only call endpoints defined in their `endpointConfig`. Arbitrary URLs are blocked for security.

**Configuration:**
Set `TOOL_ALLOWED_DOMAINS` environment variable to restrict allowed domains:
```bash
export TOOL_ALLOWED_DOMAINS="api.example.com,*.trusted-domain.com"
```

**Wildcard Support:**
- `*.example.com` matches `api.example.com`, `sub.example.com`, etc.
- Exact domain matches are also supported: `api.example.com`

**Default Behavior:**
- If `TOOL_ALLOWED_DOMAINS` is not set, all HTTPS domains are allowed (not recommended for production).
- HTTP (non-HTTPS) URLs are blocked by default.
- Localhost and private IPs are blocked unless explicitly allowed.

### API Key Management

**Storage:**
- API keys are stored as environment variables, never in the database.
- Environment variable naming: `TOOL_{TOOLNAME}_API_KEY` (uppercase, underscores).

**Example:**
```bash
# For tool named "sendNotification"
export TOOL_SENDNOTIFICATION_API_KEY="sk-1234567890abcdef"
```

**Security Best Practices:**
1. **Never log API keys**: All API keys are automatically masked in logs and events.
2. **Use secrets management**: In production, use a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.).
3. **Rotate regularly**: Rotate API keys periodically and update environment variables.
4. **Least privilege**: Use API keys with minimal required permissions.
5. **Separate keys per environment**: Use different keys for development, staging, and production.

### Secret Redaction

**Automatic Redaction:**
The system automatically redacts secrets from:
- Log messages
- Event payloads
- Audit trails
- Error messages

**Redacted Patterns:**
- `password`, `passwd`
- `api_key`, `apikey`, `api-key`
- `token`, `access_token`, `refresh_token`
- `secret`, `credential`
- `private_key`, `privatekey`
- `client_secret`
- `authorization`, `bearer`

**Example:**
```json
// Input payload
{
  "username": "user1",
  "password": "secret123",
  "api_key": "sk-123456"
}

// Redacted in logs/events
{
  "username": "user1",
  "password": "[REDACTED]",
  "api_key": "[REDACTED]"
}
```

### Tenant Isolation

**Enforcement:**
- All tool operations are scoped by tenant ID.
- Tenants cannot access tools from other tenants.
- Global tools are visible to all tenants but execution is still tenant-scoped.

**Verification:**
- All API endpoints require tenant identification via API key or authentication.
- Repository queries automatically filter by tenant ID.
- Cross-tenant access attempts are logged and blocked.

### HTTPS Enforcement

**Requirement:**
- All HTTP tool endpoints must use HTTPS.
- HTTP (non-encrypted) URLs are blocked by default.

**Exception:**
- Development/testing environments can allow HTTP by setting `allowed_schemes=["http", "https"]` in provider configuration (not recommended for production).

### Audit Logging

**Comprehensive Logging:**
- All tool executions are logged with:
  - Execution ID
  - Tenant ID
  - Tool ID
  - Actor (user/agent/system)
  - Input payload (secrets redacted)
  - Output payload (secrets redacted)
  - Status and timestamps

**Event Types:**
- `ToolExecutionRequested`: Execution has been requested
- `ToolExecutionCompleted`: Execution completed successfully
- `ToolExecutionFailed`: Execution failed with an error

**Retention:**
- Execution records are retained according to tenant retention policies.
- Events are append-only and immutable.

---

## Troubleshooting Runbook

### Common Issues and Solutions

#### 1. Tool Execution Fails with "Tool not found"

**Symptoms:**
- Error: `404 Not Found` or `Tool not found`
- Tool ID exists but execution fails

**Diagnosis:**
1. Verify tool exists: `GET /api/tools/{tool_id}`
2. Check tenant scope: Ensure tool is accessible to your tenant
3. Verify tool is enabled: `GET /api/tools/{tool_id}/enablement`

**Solutions:**
- If tool is tenant-scoped, ensure you're using the correct tenant ID
- If tool is disabled, enable it: `PUT /api/tools/{tool_id}/enablement` with `{"enabled": true}`
- Check tool visibility filters in UI

#### 2. Tool Execution Fails with "Validation Error"

**Symptoms:**
- Error: `400 Bad Request` with validation error message
- Payload doesn't match input schema

**Diagnosis:**
1. Review tool's `inputSchema`: `GET /api/tools/{tool_id}`
2. Compare payload with schema requirements
3. Check for missing required fields
4. Verify data types match schema

**Solutions:**
- Ensure all required fields are present
- Verify field types match schema (string, number, boolean, etc.)
- Check enum values if schema specifies `enum`
- Use JSON Schema validator to test payload before execution

**Example Fix:**
```json
// Schema requires:
{
  "type": "object",
  "properties": {
    "recipient": {"type": "string"},
    "message": {"type": "string"}
  },
  "required": ["recipient", "message"]
}

// Valid payload:
{
  "recipient": "user@example.com",
  "message": "Hello"
}

// Invalid payload (missing required field):
{
  "recipient": "user@example.com"
  // Missing "message"
}
```

#### 3. Tool Execution Fails with "URL validation failed"

**Symptoms:**
- Error: `URL validation failed` or `URL not in allow-list`
- HTTP tool execution fails

**Diagnosis:**
1. Check `TOOL_ALLOWED_DOMAINS` environment variable
2. Verify endpoint URL matches allowed domains
3. Check if URL uses HTTPS (required by default)

**Solutions:**
- Add domain to `TOOL_ALLOWED_DOMAINS`:
  ```bash
  export TOOL_ALLOWED_DOMAINS="api.example.com,*.trusted-domain.com"
  ```
- Ensure URL uses HTTPS (not HTTP)
- For development, explicitly allow HTTP (not recommended):
  - Modify provider configuration to allow HTTP schemes

#### 4. Tool Execution Fails with "API key required"

**Symptoms:**
- Error: `API key required for tool '{tool_name}' but not found in environment`
- Tool with `authType: "api_key"` fails

**Diagnosis:**
1. Check tool's `authType`: `GET /api/tools/{tool_id}`
2. Verify environment variable exists
3. Check environment variable naming: `TOOL_{TOOLNAME}_API_KEY`

**Solutions:**
- Set environment variable:
  ```bash
  # For tool named "sendNotification"
  export TOOL_SENDNOTIFICATION_API_KEY="your-api-key-here"
  ```
- Verify naming: Tool name is converted to uppercase with underscores
- Restart application after setting environment variable
- Check environment variable is accessible to the application process

#### 5. Tool Execution Times Out

**Symptoms:**
- Execution status remains `running` for extended period
- Eventually fails with timeout error

**Diagnosis:**
1. Check tool's `endpointConfig.timeoutSeconds`
2. Verify endpoint is accessible and responsive
3. Check network connectivity
4. Review endpoint logs for delays

**Solutions:**
- Increase timeout in tool configuration:
  ```json
  {
    "endpointConfig": {
      "url": "https://api.example.com/endpoint",
      "timeoutSeconds": 60.0  // Increase from default 30.0
    }
  }
  ```
- Verify endpoint is operational
- Check network connectivity and firewall rules
- Consider implementing retry logic (future enhancement)

#### 6. Tool Execution Returns Unexpected Output

**Symptoms:**
- Execution succeeds but output doesn't match expected schema
- Output structure differs from `outputSchema`

**Diagnosis:**
1. Review tool's `outputSchema`: `GET /api/tools/{tool_id}`
2. Compare actual output with expected schema
3. Check endpoint implementation

**Solutions:**
- Update `outputSchema` to match actual endpoint response
- Verify endpoint implementation matches tool definition
- Use schema validation to catch mismatches early

#### 7. Tool Not Visible in UI

**Symptoms:**
- Tool exists in database but doesn't appear in UI
- Tool list is empty or filtered incorrectly

**Diagnosis:**
1. Check UI filters (scope, enabled status)
2. Verify tenant ID matches
3. Check tool's `tenantScope` setting

**Solutions:**
- Clear UI filters or adjust filter settings
- For tenant tools, ensure you're viewing the correct tenant
- For global tools, ensure scope filter includes "global"
- Check tool enablement status

#### 8. Secrets Appearing in Logs

**Symptoms:**
- API keys or passwords visible in log files
- Sensitive data not redacted

**Diagnosis:**
1. Check if data is in a recognized secret field name
2. Verify redaction is working for other fields
3. Review log configuration

**Solutions:**
- Ensure secrets use recognized field names (see Secret Redaction section)
- For custom secret fields, add to redaction patterns (future enhancement)
- Report issue if redaction is not working for standard patterns

### Debugging Steps

1. **Check Tool Definition:**
   ```bash
   curl -H "X-API-Key: YOUR_API_KEY" \
        https://api.example.com/api/tools/{tool_id}
   ```

2. **Check Execution Status:**
   ```bash
   curl -H "X-API-Key: YOUR_API_KEY" \
        https://api.example.com/api/tools/executions/{execution_id}
   ```

3. **Review Application Logs:**
   - Check for validation errors
   - Look for security-related errors
   - Review execution lifecycle events

4. **Verify Environment Variables:**
   ```bash
   # Check if API key is set
   echo $TOOL_SENDNOTIFICATION_API_KEY
   
   # Check allowed domains
   echo $TOOL_ALLOWED_DOMAINS
   ```

5. **Test Tool Execution Manually:**
   ```bash
   curl -X POST \
        -H "X-API-Key: YOUR_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"payload": {...}, "actorType": "user", "actorId": "test"}' \
        https://api.example.com/api/tools/{tool_id}/execute
   ```

### Getting Help

If issues persist:
1. Review application logs for detailed error messages
2. Check execution records in database: `GET /api/tools/executions`
3. Review audit trail events for execution lifecycle
4. Contact platform support with:
   - Tool ID
   - Execution ID (if available)
   - Error message
   - Relevant logs

---

## Additional Resources

- [Phase 8 MVP Documentation](./phase8-tools-mvp.md)
- [API Reference](./03-data-models-apis.md)
- [Domain Pack Schema](./05-domain-pack-schema.md)
- [Security & Compliance](./08-security-compliance.md)

