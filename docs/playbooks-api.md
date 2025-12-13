# Playbooks API Reference

This document provides comprehensive API reference for playbook-related endpoints in the Agentic Exception Processing Platform.

## Table of Contents

1. [Overview](#overview)
2. [Base URL](#base-url)
3. [Authentication](#authentication)
4. [Endpoints](#endpoints)
   - [Recalculate Playbook](#recalculate-playbook)
   - [Get Playbook Status](#get-playbook-status)
   - [Complete Playbook Step](#complete-playbook-step)
5. [Error Responses](#error-responses)
6. [Examples](#examples)
   - [cURL Examples](#curl-examples)
   - [UI Flow Examples](#ui-flow-examples)

---

## Overview

The Playbooks API provides endpoints for managing playbook assignments and execution state for exceptions. All endpoints are tenant-scoped and require tenant isolation.

### Key Features

- **Recalculate Playbook**: Re-run playbook matching to assign or update the playbook for an exception
- **Get Playbook Status**: Retrieve current playbook assignment and step statuses
- **Complete Playbook Step**: Mark a playbook step as completed and advance execution

---

## Base URL

All endpoints are relative to the API base URL:

```
http://localhost:8000/api/v1/exceptions
```

---

## Authentication

All endpoints require tenant authentication. The `tenant_id` must be provided in the URL path, and the request must include valid authentication credentials (API key or session token).

**Headers:**
```
X-API-Key: <api_key>
# OR
Authorization: Bearer <token>
```

---

## Endpoints

### Recalculate Playbook

Re-runs playbook matching logic for an exception and updates the playbook assignment.

**Endpoint:** `POST /exceptions/{tenant_id}/{exception_id}/playbook/recalculate`

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `exception_id` (string, required): Exception identifier

**Request Body:** None (no request body required)

**Response:** `200 OK` with `PlaybookRecalculationResponse`

#### Response Schema

```typescript
interface PlaybookRecalculationResponse {
  exceptionId: string;              // Exception identifier
  currentPlaybookId?: number | null; // Current playbook ID (null if no playbook matched)
  currentStep?: number | null;       // Current step number (null if no playbook matched)
  playbookName?: string | null;      // Name of the selected playbook
  playbookVersion?: number | null;   // Version of the selected playbook
  reasoning?: string | null;         // Reasoning for playbook selection
}
```

#### Behavior

1. Loads the exception from the database
2. Re-runs playbook matching using the Playbook Matching Service
3. Updates `exception.current_playbook_id` and `exception.current_step`
4. Emits a `PlaybookRecalculated` event (idempotent - only if assignment changed)
5. Returns updated playbook assignment information

#### Error Responses

- `400 Bad Request`: Missing or invalid `tenant_id`
- `403 Forbidden`: Tenant ID mismatch (authenticated tenant doesn't match path tenant)
- `404 Not Found`: Exception not found or doesn't belong to tenant
- `500 Internal Server Error`: Database or matching service error

---

### Get Playbook Status

Retrieves the current playbook assignment and step statuses for an exception.

**Endpoint:** `GET /exceptions/{tenant_id}/{exception_id}/playbook`

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `exception_id` (string, required): Exception identifier

**Response:** `200 OK` with `PlaybookStatusResponse`

#### Response Schema

```typescript
interface PlaybookStepStatus {
  stepOrder: number;      // Step order number (1-indexed)
  name: string;           // Step name
  actionType: string;     // Action type (notify, assign_owner, set_status, add_comment, call_tool)
  status: string;         // Status: "pending", "completed", or "skipped"
}

interface PlaybookStatusResponse {
  exceptionId: string;                    // Exception identifier
  playbookId?: number | null;             // Playbook identifier (null if no playbook assigned)
  playbookName?: string | null;           // Playbook name
  playbookVersion?: number | null;        // Playbook version
  conditions?: Record<string, unknown> | null; // Playbook matching conditions
  steps: PlaybookStepStatus[];            // List of playbook steps with status
  currentStep?: number | null;            // Current step number (1-indexed)
}
```

#### Step Status Logic

Step status is derived from exception events:

- **"completed"**: If `PlaybookStepCompleted` event exists for the step, or if `PlaybookCompleted` event exists (all steps completed), or if step order is less than `currentStep`
- **"pending"**: Step has no completion events and is at or after `currentStep`
- **"skipped"**: Not implemented in MVP (reserved for future use)

#### Behavior

1. Loads the exception and verifies tenant ownership
2. Loads the current playbook (if any) and its ordered steps
3. Derives per-step status from events (`PlaybookStarted`, `PlaybookStepCompleted`, `PlaybookCompleted`)
4. Returns playbook metadata and step statuses

#### Error Responses

- `400 Bad Request`: Missing or invalid `tenant_id`
- `403 Forbidden`: Tenant ID mismatch (authenticated tenant doesn't match path tenant)
- `404 Not Found`: Exception not found or doesn't belong to tenant
- `500 Internal Server Error`: Database error

---

### Complete Playbook Step

Marks a playbook step as completed and advances the exception's current step.

**Endpoint:** `POST /exceptions/{tenant_id}/{exception_id}/playbook/steps/{step_order}/complete`

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `exception_id` (string, required): Exception identifier
- `step_order` (integer, required): Step order number to complete (1-indexed)

**Request Body:** `StepCompletionRequest`

```typescript
interface StepCompletionRequest {
  actorType: string;    // Actor type: "human", "agent", or "system"
  actorId: string;      // Actor identifier (user ID or agent name)
  notes?: string | null; // Optional notes about step completion
}
```

**Response:** `200 OK` with `PlaybookStatusResponse` (same structure as Get Playbook Status)

#### Behavior

1. Validates tenant ownership of the exception
2. Validates the step exists and is the next expected step (or allows out-of-order completion)
3. Calls `PlaybookExecutionService` to complete the step
4. Executes safe actions for the step (if applicable, based on action type)
5. Emits `PlaybookStepCompleted` event
6. Updates `exception.current_step` to the next step
7. If all steps are completed, emits `PlaybookCompleted` event
8. Returns updated playbook status

#### Error Responses

- `400 Bad Request`: 
  - Invalid request body or `actor_type` (must be "human", "agent", or "system")
  - `step_order` must be >= 1
  - No playbook is assigned to the exception
  - Step order is invalid or step is not the next expected step
- `403 Forbidden`: 
  - Tenant ID mismatch
  - Step requires human approval (for future implementation)
- `404 Not Found`: 
  - Exception not found or doesn't belong to tenant
  - Step not found in playbook
- `500 Internal Server Error`: Execution service error

---

## Error Responses

All endpoints return errors in a consistent format:

```typescript
interface ErrorResponse {
  detail: string;  // Human-readable error message
}
```

### HTTP Status Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid input parameters |
| 403 | Forbidden - Tenant mismatch or insufficient permissions |
| 404 | Not Found - Resource doesn't exist or doesn't belong to tenant |
| 500 | Internal Server Error - Server-side error |

### Example Error Response

```json
{
  "detail": "Exception exc_12345 not found for tenant TENANT_001"
}
```

---

## Examples

### cURL Examples

#### Recalculate Playbook

```bash
# Recalculate playbook for an exception
curl -X POST "http://localhost:8000/api/v1/exceptions/TENANT_001/exc_12345/playbook/recalculate" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json"

# Response
{
  "exceptionId": "exc_12345",
  "currentPlaybookId": 1,
  "currentStep": 1,
  "playbookName": "PaymentFailurePlaybook",
  "playbookVersion": 1,
  "reasoning": "Selected playbook 'PaymentFailurePlaybook' (priority=100, playbook_id=1): Playbook matches: matched domain, matched exception_type, matched severity"
}
```

#### Get Playbook Status

```bash
# Get playbook status for an exception
curl -X GET "http://localhost:8000/api/v1/exceptions/TENANT_001/exc_12345/playbook" \
  -H "X-API-Key: your-api-key"

# Response
{
  "exceptionId": "exc_12345",
  "playbookId": 1,
  "playbookName": "PaymentFailurePlaybook",
  "playbookVersion": 1,
  "conditions": {
    "match": {
      "domain": "Finance",
      "exception_type": "PaymentFailure",
      "severity_in": ["high", "critical"]
    },
    "priority": 100
  },
  "steps": [
    {
      "stepOrder": 1,
      "name": "Notify Operations Team",
      "actionType": "notify",
      "status": "completed"
    },
    {
      "stepOrder": 2,
      "name": "Assign to Billing Queue",
      "actionType": "assign_owner",
      "status": "pending"
    },
    {
      "stepOrder": 3,
      "name": "Retry Payment",
      "actionType": "call_tool",
      "status": "pending"
    }
  ],
  "currentStep": 2
}
```

#### Complete Playbook Step

```bash
# Complete step 1 for an exception
curl -X POST "http://localhost:8000/api/v1/exceptions/TENANT_001/exc_12345/playbook/steps/1/complete" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "actorType": "human",
    "actorId": "user_123",
    "notes": "Notification sent successfully"
  }'

# Response (same structure as Get Playbook Status)
{
  "exceptionId": "exc_12345",
  "playbookId": 1,
  "playbookName": "PaymentFailurePlaybook",
  "playbookVersion": 1,
  "conditions": {
    "match": {
      "domain": "Finance",
      "exception_type": "PaymentFailure",
      "severity_in": ["high", "critical"]
    },
    "priority": 100
  },
  "steps": [
    {
      "stepOrder": 1,
      "name": "Notify Operations Team",
      "actionType": "notify",
      "status": "completed"
    },
    {
      "stepOrder": 2,
      "name": "Assign to Billing Queue",
      "actionType": "assign_owner",
      "status": "pending"
    },
    {
      "stepOrder": 3,
      "name": "Retry Payment",
      "actionType": "call_tool",
      "status": "pending"
    }
  ],
  "currentStep": 2
}
```

#### Error Example - Exception Not Found

```bash
curl -X GET "http://localhost:8000/api/v1/exceptions/TENANT_001/nonexistent/playbook" \
  -H "X-API-Key: your-api-key"

# Response (404 Not Found)
{
  "detail": "Exception nonexistent not found for tenant TENANT_001"
}
```

#### Error Example - Invalid Actor Type

```bash
curl -X POST "http://localhost:8000/api/v1/exceptions/TENANT_001/exc_12345/playbook/steps/1/complete" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "actorType": "invalid",
    "actorId": "user_123"
  }'

# Response (400 Bad Request)
{
  "detail": "Invalid actor_type: invalid. Must be one of: human, agent, system"
}
```

---

### UI Flow Examples

#### Example 1: User Views Playbook Status

**Scenario:** User opens exception detail page and views the recommended playbook.

**UI Code (React + TanStack Query):**

```typescript
import { useExceptionPlaybook } from '@/hooks/useExceptions'

function RecommendedPlaybookPanel({ exceptionId }: { exceptionId: string }) {
  const { data: playbookStatus, isLoading, error } = useExceptionPlaybook(exceptionId)

  if (isLoading) {
    return <CircularProgress />
  }

  if (error) {
    return <Alert severity="error">Failed to load playbook: {error.message}</Alert>
  }

  if (!playbookStatus?.playbookId) {
    return <Alert>No playbook assigned to this exception</Alert>
  }

  return (
    <Paper>
      <Typography variant="h6">
        {playbookStatus.playbookName} (v{playbookStatus.playbookVersion})
      </Typography>
      <List>
        {playbookStatus.steps.map((step) => (
          <ListItem key={step.stepOrder}>
            <ListItemIcon>
              {step.status === 'completed' ? <CheckCircleIcon /> : <RadioButtonUncheckedIcon />}
            </ListItemIcon>
            <ListItemText
              primary={step.name}
              secondary={`${step.actionType} - ${step.status}`}
            />
            {step.stepOrder === playbookStatus.currentStep && (
              <Chip label="Current" color="primary" size="small" />
            )}
          </ListItem>
        ))}
      </List>
    </Paper>
  )
}
```

**API Calls Made:**

1. `GET /exceptions/{tenant_id}/{exception_id}/playbook`
   - Returns playbook status with steps
   - Automatically retries on failure
   - Cached for 30 seconds

---

#### Example 2: User Triggers Playbook Recalculation

**Scenario:** User clicks "Recalculate" button to re-run playbook matching.

**UI Code (React + TanStack Query):**

```typescript
import { useRecalculatePlaybook } from '@/hooks/useExceptions'

function RecalculateButton({ exceptionId }: { exceptionId: string }) {
  const recalculateMutation = useRecalculatePlaybook(exceptionId)

  const handleRecalculate = async () => {
    try {
      const result = await recalculateMutation.mutateAsync()
      
      // Show success message
      console.log(`Playbook recalculated: ${result.playbookName}`)
      console.log(`Reasoning: ${result.reasoning}`)
      
      // UI automatically updates because query is invalidated
    } catch (error) {
      console.error('Recalculation failed:', error)
    }
  }

  return (
    <Button
      onClick={handleRecalculate}
      disabled={recalculateMutation.isPending}
      variant="outlined"
    >
      {recalculateMutation.isPending ? 'Recalculating...' : 'Recalculate Playbook'}
    </Button>
  )
}
```

**API Calls Made:**

1. `POST /exceptions/{tenant_id}/{exception_id}/playbook/recalculate`
   - Re-runs playbook matching
   - Updates exception playbook assignment
   - Returns new assignment details

2. `GET /exceptions/{tenant_id}/{exception_id}/playbook` (automatic refetch)
   - Triggered automatically after recalculation succeeds
   - Updates UI with new playbook status

3. `GET /exceptions/{exception_id}/events` (automatic refetch)
   - Triggered automatically after recalculation succeeds
   - Updates timeline with `PlaybookRecalculated` event

---

#### Example 3: User Completes a Playbook Step

**Scenario:** User completes step 1 by clicking "Mark Completed" button.

**UI Code (React + TanStack Query):**

```typescript
import { useCompletePlaybookStep } from '@/hooks/useExceptions'
import { useTenant } from '@/contexts/TenantContext'

function PlaybookStepItem({ 
  exceptionId, 
  step, 
  currentStep 
}: { 
  exceptionId: string
  step: PlaybookStepStatus
  currentStep?: number | null
}) {
  const completeMutation = useCompletePlaybookStep(exceptionId)
  const { user } = useTenant()

  const handleComplete = async () => {
    try {
      const result = await completeMutation.mutateAsync({
        stepOrder: step.stepOrder,
        request: {
          actorType: 'human',
          actorId: user.id,
          notes: `Step completed by ${user.name}`,
        },
      })

      // Show success message
      console.log(`Step ${step.stepOrder} completed`)
      console.log(`Current step now: ${result.currentStep}`)
      
      // UI automatically updates because queries are invalidated
    } catch (error) {
      console.error('Step completion failed:', error)
      // Show error toast
    }
  }

  const canComplete = step.stepOrder === currentStep && step.status === 'pending'

  return (
    <ListItem>
      <ListItemIcon>
        {step.status === 'completed' ? (
          <CheckCircleIcon color="success" />
        ) : (
          <RadioButtonUncheckedIcon />
        )}
      </ListItemIcon>
      <ListItemText primary={step.name} secondary={step.actionType} />
      {canComplete && (
        <Button
          onClick={handleComplete}
          disabled={completeMutation.isPending}
          size="small"
          variant="contained"
        >
          {completeMutation.isPending ? 'Completing...' : 'Mark Completed'}
        </Button>
      )}
    </ListItem>
  )
}
```

**API Calls Made:**

1. `POST /exceptions/{tenant_id}/{exception_id}/playbook/steps/{step_order}/complete`
   - Completes the step
   - Executes step action (if applicable)
   - Emits `PlaybookStepCompleted` event
   - Updates `current_step`
   - Returns updated playbook status

2. `GET /exceptions/{tenant_id}/{exception_id}/playbook` (automatic refetch)
   - Triggered automatically after completion succeeds
   - Updates UI with new step statuses and current step

3. `GET /exceptions/{exception_id}/events` (automatic refetch)
   - Triggered automatically after completion succeeds
   - Updates timeline with `PlaybookStepCompleted` event

---

#### Example 4: Complete Playbook Flow

**Scenario:** User completes all steps in a playbook, triggering playbook completion.

**Sequence of API Calls:**

1. **Initial Load:**
   ```
   GET /exceptions/TENANT_001/exc_12345/playbook
   → Returns playbook with 3 steps, currentStep: 1
   ```

2. **Complete Step 1:**
   ```
   POST /exceptions/TENANT_001/exc_12345/playbook/steps/1/complete
   → Returns playbook status with currentStep: 2
   → Emits PlaybookStepCompleted event
   ```

3. **Complete Step 2:**
   ```
   POST /exceptions/TENANT_001/exc_12345/playbook/steps/2/complete
   → Returns playbook status with currentStep: 3
   → Emits PlaybookStepCompleted event
   ```

4. **Complete Step 3 (Final Step):**
   ```
   POST /exceptions/TENANT_001/exc_12345/playbook/steps/3/complete
   → Returns playbook status with all steps completed
   → Emits PlaybookStepCompleted event
   → Emits PlaybookCompleted event
   ```

**Timeline Events Generated:**

```json
[
  {
    "eventType": "PlaybookStepCompleted",
    "actorType": "user",
    "actorId": "user_123",
    "payload": {
      "step_order": 1,
      "playbook_id": 1,
      "playbook_name": "PaymentFailurePlaybook"
    }
  },
  {
    "eventType": "PlaybookStepCompleted",
    "actorType": "user",
    "actorId": "user_123",
    "payload": {
      "step_order": 2,
      "playbook_id": 1,
      "playbook_name": "PaymentFailurePlaybook"
    }
  },
  {
    "eventType": "PlaybookStepCompleted",
    "actorType": "user",
    "actorId": "user_123",
    "payload": {
      "step_order": 3,
      "playbook_id": 1,
      "playbook_name": "PaymentFailurePlaybook"
    }
  },
  {
    "eventType": "PlaybookCompleted",
    "actorType": "system",
    "actorId": "PlaybookExecutionService",
    "payload": {
      "playbook_id": 1,
      "playbook_name": "PaymentFailurePlaybook",
      "total_steps": 3,
      "completed_by": "user_123"
    }
  }
]
```

---

## Related Documentation

- [Playbooks Configuration Guide](./playbooks-configuration.md) - How to configure playbooks
- [Phase 7 Playbooks MVP](./phase7-playbooks-mvp.md) - Detailed playbook implementation guide
- [Data Models & APIs](./03-data-models-apis.md) - General API documentation
- [E2E Test Guide](./e2e-test-playbook-lifecycle.md) - Testing playbook lifecycle

