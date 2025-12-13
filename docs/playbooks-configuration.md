# Playbooks Configuration Guide

This guide provides comprehensive documentation for configuring playbooks in the Agentic Exception Processing Platform. Playbooks define sequences of steps that are automatically matched to exceptions and executed to resolve them.

## Table of Contents

1. [Playbook Schema](#playbook-schema)
2. [Conditions Syntax](#conditions-syntax)
3. [Step Action Types](#step-action-types)
4. [Placeholder Templating](#placeholder-templating)
5. [Domain Examples](#domain-examples)
6. [Versioning & Management](#versioning--management)

---

## Playbook Schema

### Database Schema

Playbooks are stored in the `playbook` table with the following structure:

```sql
CREATE TABLE playbook (
    playbook_id INTEGER PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    conditions TEXT NOT NULL,  -- JSON
    created_at TIMESTAMP NOT NULL
);
```

### JSON Schema

When working with playbooks via API or configuration files, use this JSON structure:

```json
{
  "tenant_id": "TENANT_001",
  "name": "PaymentFailurePlaybook",
  "version": 1,
  "conditions": {
    "match": {
      "domain": "Finance",
      "exception_type": "PaymentFailure",
      "severity_in": ["high", "critical"],
      "sla_minutes_remaining_lt": 60,
      "policy_tags": ["urgent"]
    },
    "priority": 100
  },
  "steps": [
    {
      "step_order": 1,
      "name": "Notify Team",
      "action_type": "notify",
      "params": {
        "channel": "email",
        "subject": "Payment Failure Alert",
        "message": "Payment failed for {exception.entity}"
      }
    },
    {
      "step_order": 2,
      "name": "Retry Payment",
      "action_type": "call_tool",
      "params": {
        "tool_id": "retry_payment",
        "payload": {
          "entity": "{exception.entity}",
          "amount": "{exception.amount}"
        }
      }
    }
  ]
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | string | Yes | Tenant identifier (ensures tenant isolation) |
| `name` | string | Yes | Human-readable playbook name |
| `version` | integer | Yes | Version number (used for versioning and updates) |
| `conditions` | object | Yes | Matching conditions (see [Conditions Syntax](#conditions-syntax)) |
| `steps` | array | Yes | Ordered list of steps (see [Step Action Types](#step-action-types)) |

---

## Conditions Syntax

Playbook conditions determine when a playbook is matched to an exception. The matching engine evaluates all conditions and selects the highest-priority matching playbook.

### Condition Structure

```json
{
  "match": {
    "domain": "Finance",
    "exception_type": "PaymentFailure",
    "severity_in": ["high", "critical"],
    "sla_minutes_remaining_lt": 60,
    "policy_tags": ["urgent", "billing"]
  },
  "priority": 100
}
```

### Supported Condition Types

#### 1. `domain` (Exact Match)

Matches exceptions with a specific domain value.

```json
{
  "match": {
    "domain": "Finance"
  }
}
```

**Examples:**
- `"domain": "Finance"` - Matches Finance domain only
- `"domain": "Healthcare"` - Matches Healthcare domain only

#### 2. `exception_type` (Exact or Pattern Match)

Matches exceptions by exception type. Supports exact matching and wildcard patterns.

```json
{
  "match": {
    "exception_type": "PaymentFailure"
  }
}
```

**Wildcard Support:**
- `*` matches any characters
- `?` matches a single character

```json
{
  "match": {
    "exception_type": "Payment*"  // Matches PaymentFailure, PaymentTimeout, etc.
  }
}
```

#### 3. `severity` (Single Value)

Matches exceptions with a specific severity.

```json
{
  "match": {
    "severity": "high"
  }
}
```

**Valid values:** `"low"`, `"medium"`, `"high"`, `"critical"`

#### 4. `severity_in` (Array)

Matches exceptions with severity in the provided list.

```json
{
  "match": {
    "severity_in": ["high", "critical"]
  }
}
```

#### 5. `sla_minutes_remaining_lt` (Numeric Comparison)

Matches exceptions where the SLA deadline is less than the specified minutes away.

```json
{
  "match": {
    "sla_minutes_remaining_lt": 60  // Matches if less than 60 minutes until SLA deadline
  }
}
```

**Note:** This condition only applies if the exception has an `sla_deadline` in its normalized context.

#### 6. `policy_tags` (Array Subset Match)

Matches exceptions that have all of the specified policy tags.

```json
{
  "match": {
    "policy_tags": ["urgent", "billing"]
  }
}
```

**Behavior:** All specified tags must be present in the exception's `policy_tags`. The exception may have additional tags.

### Priority

The `priority` field (integer) determines which playbook is selected when multiple playbooks match:

- **Higher priority = better match** (e.g., `priority: 100` beats `priority: 50`)
- If priorities are equal, the playbook with the higher `playbook_id` (newer) is selected
- Default priority is `0` if not specified

```json
{
  "conditions": {
    "match": { ... },
    "priority": 100
  }
}
```

### Condition Nesting

Conditions can be specified in two ways:

**Option 1: Nested under "match" key (recommended)**
```json
{
  "conditions": {
    "match": {
      "domain": "Finance",
      "exception_type": "PaymentFailure"
    },
    "priority": 100
  }
}
```

**Option 2: At root level (legacy support)**
```json
{
  "conditions": {
    "domain": "Finance",
    "exception_type": "PaymentFailure",
    "priority": 100
  }
}
```

### Condition Evaluation Logic

- **All specified conditions must match** for a playbook to be selected
- Conditions are evaluated in order: domain → exception_type → severity → SLA → policy_tags
- If any condition fails, the playbook is excluded from consideration
- The matching service returns the highest-priority matching playbook

---

## Step Action Types

Each playbook step has an `action_type` that determines what action is executed. The `params` field contains action-specific parameters.

### 1. `notify`

Sends a notification to a team, user, or system.

**Parameters:**
- `channel` (string, optional): Notification channel (`"email"`, `"slack"`, `"sms"`, `"log"`). Default: `"log"`
- `subject` (string, required): Notification subject (supports placeholders)
- `message` (string, required): Notification message (supports placeholders)
- `template_id` (string, optional): Reference to a notification template
- `group` (string, optional): Target group/team. Default: `"DefaultOps"`

**Example:**
```json
{
  "step_order": 1,
  "name": "Notify Operations Team",
  "action_type": "notify",
  "params": {
    "channel": "email",
    "subject": "Alert: {exception.exception_type} for {exception.entity}",
    "message": "Exception {exception.exception_id} requires attention. Severity: {exception.severity}",
    "group": "OperationsTeam"
  }
}
```

### 2. `assign_owner`

Assigns the exception to a specific user or queue.

**Parameters:**
- `user_id` (string, optional): User identifier to assign to
- `queue` (string, optional): Queue name to assign to

**Note:** Either `user_id` or `queue` must be provided.

**Example:**
```json
{
  "step_order": 2,
  "name": "Assign to Billing Queue",
  "action_type": "assign_owner",
  "params": {
    "queue": "BillingOpsQueue"
  }
}
```

### 3. `set_status`

Updates the exception's resolution status.

**Parameters:**
- `status` (string, required): New status value. Valid values: `"open"`, `"analyzing"`, `"resolved"`, `"escalated"`

**Example:**
```json
{
  "step_order": 3,
  "name": "Mark as Escalated",
  "action_type": "set_status",
  "params": {
    "status": "escalated"
  }
}
```

### 4. `add_comment`

Adds a comment/note to the exception's event log.

**Parameters:**
- `text` (string, optional): Direct text content
- `text_template` (string, optional): Text template with placeholders

**Note:** Either `text` or `text_template` must be provided. Use `text_template` for dynamic content.

**Example:**
```json
{
  "step_order": 4,
  "name": "Add Investigation Note",
  "action_type": "add_comment",
  "params": {
    "text_template": "Investigation started for {exception.exception_id}. Entity: {exception.entity}, Amount: {exception.amount}"
  }
}
```

### 5. `call_tool`

Invokes an allow-listed tool from the Domain Pack.

**Parameters:**
- `tool_id` (string, required): Tool identifier from Domain Pack
- `payload` (object, optional): Tool invocation payload (supports placeholders)
- `payload_template` (object, optional): Payload template with placeholders

**Note:** In MVP, tool execution is logged/stubbed. Actual execution requires tool approval and tenant policy validation.

**Example:**
```json
{
  "step_order": 5,
  "name": "Retry Payment",
  "action_type": "call_tool",
  "params": {
    "tool_id": "retry_payment",
    "payload": {
      "entity": "{exception.entity}",
      "amount": "{exception.amount}",
      "order_id": "{exception.normalized_context.order_id}"
    }
  }
}
```

---

## Placeholder Templating

Playbook step parameters support placeholder templating to dynamically insert exception data into messages, notifications, and tool payloads.

### Placeholder Syntax

Placeholders use the format: `{context.field}`

**Available Contexts:**

1. **Exception Context** (`{exception.*}`)
   - `{exception.exception_id}` - Exception identifier
   - `{exception.tenant_id}` - Tenant identifier
   - `{exception.source_system}` - Source system name
   - `{exception.exception_type}` - Exception type
   - `{exception.severity}` - Severity level
   - `{exception.timestamp}` - Exception timestamp (ISO format)
   - `{exception.resolution_status}` - Current resolution status
   - `{exception.entity}` - Entity identifier (if available in DB model)
   - `{exception.amount}` - Amount (if available in DB model)
   - `{exception.owner}` - Current owner (if available in DB model)

2. **Normalized Context** (`{exception.normalized_context.*}`)
   - Access any field in the exception's `normalized_context` dictionary
   - Example: `{exception.normalized_context.domain}`
   - Example: `{exception.normalized_context.entity}`
   - Example: `{exception.normalized_context.order_id}`

3. **Domain Pack Context** (`{domain_pack.*}`)
   - `{domain_pack.domain_name}` - Domain name

4. **Policy Pack Context** (`{policy_pack.*}`)
   - `{policy_pack.tenant_id}` - Tenant identifier
   - `{policy_pack.domain_name}` - Domain name

### Placeholder Examples

#### Simple Field Access
```json
{
  "message": "Exception {exception.exception_id} requires attention"
}
```

**Resolved to:**
```
"Exception exc-12345-abc requires attention"
```

#### Nested Field Access
```json
{
  "subject": "Alert for {exception.normalized_context.entity} in {exception.normalized_context.domain}"
}
```

**Resolved to:**
```
"Alert for ACC-001 in Finance"
```

#### Multiple Placeholders
```json
{
  "message": "Payment failure for {exception.entity}. Amount: {exception.amount}, Severity: {exception.severity}"
}
```

**Resolved to:**
```
"Payment failure for ACC-001. Amount: 1000.0, Severity: HIGH"
```

#### In Nested Objects (Tool Payloads)
```json
{
  "payload": {
    "order_id": "{exception.normalized_context.order_id}",
    "amount": "{exception.amount}",
    "entity": "{exception.entity}",
    "metadata": {
      "exception_id": "{exception.exception_id}",
      "severity": "{exception.severity}"
    }
  }
}
```

**Resolved to:**
```json
{
  "order_id": "ORD-123",
  "amount": 1000.0,
  "entity": "ACC-001",
  "metadata": {
    "exception_id": "exc-12345-abc",
    "severity": "HIGH"
  }
}
```

#### Complex Templates
```json
{
  "text_template": "Investigation started at {exception.timestamp} for exception {exception.exception_id}. Entity: {exception.normalized_context.entity}, Type: {exception.exception_type}, Severity: {exception.severity}. Domain: {domain_pack.domain_name}."
}
```

### Placeholder Resolution Behavior

- **Missing fields:** If a placeholder references a missing field, it is replaced with an empty string or left as-is (depending on the implementation)
- **Null values:** Null values are converted to empty strings
- **Nested objects/arrays:** Complex objects and arrays are JSON-stringified
- **Recursive resolution:** Placeholders are resolved recursively in nested structures

---

## Domain Examples

### Finance Domain Examples

#### Example 1: Payment Failure Playbook

```json
{
  "tenant_id": "TENANT_FINANCE_001",
  "name": "PaymentFailurePlaybook",
  "version": 1,
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
      "step_order": 1,
      "name": "Notify Operations Team",
      "action_type": "notify",
      "params": {
        "channel": "email",
        "subject": "Payment Failure: {exception.entity}",
        "message": "Payment failed for entity {exception.entity}. Amount: {exception.amount}. Exception ID: {exception.exception_id}",
        "group": "PaymentOpsTeam"
      }
    },
    {
      "step_order": 2,
      "name": "Assign to Billing Queue",
      "action_type": "assign_owner",
      "params": {
        "queue": "BillingOpsQueue"
      }
    },
    {
      "step_order": 3,
      "name": "Retry Payment",
      "action_type": "call_tool",
      "params": {
        "tool_id": "retry_payment",
        "payload": {
          "entity": "{exception.entity}",
          "amount": "{exception.amount}",
          "order_id": "{exception.normalized_context.order_id}"
        }
      }
    },
    {
      "step_order": 4,
      "name": "Add Investigation Note",
      "action_type": "add_comment",
      "params": {
        "text_template": "Payment retry initiated for {exception.entity}. Original exception: {exception.exception_id}"
      }
    },
    {
      "step_order": 5,
      "name": "Update Status to Resolved",
      "action_type": "set_status",
      "params": {
        "status": "resolved"
      }
    }
  ]
}
```

#### Example 2: Trade Settlement Failure Playbook (High Priority)

```json
{
  "tenant_id": "TENANT_FINANCE_001",
  "name": "TradeSettlementFailurePlaybook",
  "version": 1,
  "conditions": {
    "match": {
      "domain": "Finance",
      "exception_type": "TradeSettlementFailure",
      "severity_in": ["critical"],
      "sla_minutes_remaining_lt": 120,
      "policy_tags": ["urgent", "settlement"]
    },
    "priority": 150
  },
  "steps": [
    {
      "step_order": 1,
      "name": "Escalate to Settlement Team",
      "action_type": "set_status",
      "params": {
        "status": "escalated"
      }
    },
    {
      "step_order": 2,
      "name": "Notify Settlement Team",
      "action_type": "notify",
      "params": {
        "channel": "email",
        "subject": "URGENT: Settlement Failure - {exception.entity}",
        "message": "Critical settlement failure for {exception.entity}. SLA deadline in {exception.normalized_context.sla_minutes_remaining} minutes.",
        "group": "SettlementOpsTeam"
      }
    },
    {
      "step_order": 3,
      "name": "Assign to Settlement Queue",
      "action_type": "assign_owner",
      "params": {
        "queue": "SettlementTier2Queue"
      }
    }
  ]
}
```

#### Example 3: Generic Finance Playbook (Lower Priority)

```json
{
  "tenant_id": "TENANT_FINANCE_001",
  "name": "GenericFinancePlaybook",
  "version": 1,
  "conditions": {
    "match": {
      "domain": "Finance"
    },
    "priority": 50
  },
  "steps": [
    {
      "step_order": 1,
      "name": "Notify Default Team",
      "action_type": "notify",
      "params": {
        "channel": "log",
        "subject": "Finance Exception: {exception.exception_type}",
        "message": "Exception {exception.exception_id} of type {exception.exception_type} requires attention."
      }
    },
    {
      "step_order": 2,
      "name": "Assign to General Queue",
      "action_type": "assign_owner",
      "params": {
        "queue": "FinanceGeneralQueue"
      }
    }
  ]
}
```

### Healthcare Domain Examples

#### Example 1: Missing Authorization Playbook

```json
{
  "tenant_id": "TENANT_HEALTHCARE_001",
  "name": "ClaimMissingAuthPlaybook",
  "version": 1,
  "conditions": {
    "match": {
      "domain": "Healthcare",
      "exception_type": "CLAIM_MISSING_AUTH",
      "severity_in": ["high", "critical"]
    },
    "priority": 100
  },
  "steps": [
    {
      "step_order": 1,
      "name": "Notify Claims Team",
      "action_type": "notify",
      "params": {
        "channel": "email",
        "subject": "Claim Missing Authorization: {exception.normalized_context.claim_id}",
        "message": "Claim {exception.normalized_context.claim_id} for patient {exception.normalized_context.patient_id} is missing required authorization.",
        "group": "ClaimsReviewTeam"
      }
    },
    {
      "step_order": 2,
      "name": "Assign to Authorization Queue",
      "action_type": "assign_owner",
      "params": {
        "queue": "AuthorizationReviewQueue"
      }
    },
    {
      "step_order": 3,
      "name": "Add Review Comment",
      "action_type": "add_comment",
      "params": {
        "text_template": "Authorization review initiated for claim {exception.normalized_context.claim_id}. Patient: {exception.normalized_context.patient_id}, Provider: {exception.normalized_context.provider_id}"
      }
    },
    {
      "step_order": 4,
      "name": "Mark as Analyzing",
      "action_type": "set_status",
      "params": {
        "status": "analyzing"
      }
    }
  ]
}
```

#### Example 2: Pharmacy Safety Playbook (Critical)

```json
{
  "tenant_id": "TENANT_HEALTHCARE_001",
  "name": "PharmacyDuplicateTherapyPlaybook",
  "version": 1,
  "conditions": {
    "match": {
      "domain": "Healthcare",
      "exception_type": "PHARMACY_DUPLICATE_THERAPY",
      "severity": "critical"
    },
    "priority": 200
  },
  "steps": [
    {
      "step_order": 1,
      "name": "Immediate Escalation",
      "action_type": "set_status",
      "params": {
        "status": "escalated"
      }
    },
    {
      "step_order": 2,
      "name": "Notify Pharmacy Safety Team",
      "action_type": "notify",
      "params": {
        "channel": "sms",
        "subject": "CRITICAL: Duplicate Therapy Alert",
        "message": "CRITICAL: Duplicate therapy detected for patient {exception.normalized_context.patient_id}. Order ID: {exception.normalized_context.order_id}. Immediate review required.",
        "group": "PharmacySafetyTeam"
      }
    },
    {
      "step_order": 3,
      "name": "Flag Medication Order",
      "action_type": "call_tool",
      "params": {
        "tool_id": "flagMedicationOrder",
        "payload": {
          "order_id": "{exception.normalized_context.order_id}",
          "patient_id": "{exception.normalized_context.patient_id}",
          "risk": "high"
        }
      }
    },
    {
      "step_order": 4,
      "name": "Document Safety Review",
      "action_type": "add_comment",
      "params": {
        "text_template": "Safety review initiated for duplicate therapy. Patient: {exception.normalized_context.patient_id}, Order: {exception.normalized_context.order_id}, Severity: {exception.severity}"
      }
    }
  ]
}
```

#### Example 3: Provider Credential Expiration Playbook

```json
{
  "tenant_id": "TENANT_HEALTHCARE_001",
  "name": "ProviderCredentialExpiredPlaybook",
  "version": 1,
  "conditions": {
    "match": {
      "domain": "Healthcare",
      "exception_type": "PROVIDER_CREDENTIAL_EXPIRED",
      "severity_in": ["high", "critical"]
    },
    "priority": 100
  },
  "steps": [
    {
      "step_order": 1,
      "name": "Notify Credentialing Team",
      "action_type": "notify",
      "params": {
        "channel": "email",
        "subject": "Provider Credential Expired: {exception.normalized_context.provider_id}",
        "message": "Provider {exception.normalized_context.provider_id} (NPI: {exception.normalized_context.npi}) has expired credentials. Expiry date: {exception.normalized_context.credential_expiry_date}",
        "group": "CredentialingTeam"
      }
    },
    {
      "step_order": 2,
      "name": "Assign to Credentialing Queue",
      "action_type": "assign_owner",
      "params": {
        "queue": "CredentialingReviewQueue"
      }
    },
    {
      "step_order": 3,
      "name": "Add Compliance Note",
      "action_type": "add_comment",
      "params": {
        "text_template": "Credential review required for provider {exception.normalized_context.provider_id}. Compliance risk identified."
      }
    }
  ]
}
```

---

## Versioning & Management

### Versioning Strategy

Playbooks use integer version numbers (`version` field) to track changes and updates.

#### Best Practices

1. **Semantic Versioning Approach**
   - Start with `version: 1` for new playbooks
   - Increment version when making changes
   - **Minor changes** (parameter tweaks, message updates): Increment by 1
   - **Major changes** (step additions/removals, condition changes): Increment by 10+ to signal significance

2. **Version Compatibility**
   - Newer versions of the same playbook (same `name`, higher `version`) replace older versions
   - The matching service selects the latest version when multiple versions exist
   - Keep old versions for audit/historical reference (they remain in the database)

3. **Backward Compatibility**
   - When updating conditions, ensure they don't break existing exception matches unexpectedly
   - Test playbook matching with sample exceptions before deploying new versions
   - Consider creating a new playbook (different `name`) instead of updating if the change is too disruptive

#### Versioning Workflow

1. **Create Initial Version**
   ```json
   {
     "name": "PaymentFailurePlaybook",
     "version": 1,
     ...
   }
   ```

2. **Update Existing Playbook**
   ```json
   {
     "name": "PaymentFailurePlaybook",
     "version": 2,  // Incremented version
     ...
   }
   ```

3. **Major Revision (New Playbook)**
   ```json
   {
     "name": "PaymentFailurePlaybookV2",  // New name to avoid confusion
     "version": 1,
     ...
   }
   ```

### Playbook Management

#### Creating Playbooks

**Via API:**
```bash
POST /api/playbooks
{
  "tenant_id": "TENANT_001",
  "name": "MyPlaybook",
  "version": 1,
  "conditions": { ... },
  "steps": [ ... ]
}
```

**Via Database:**
```sql
INSERT INTO playbook (tenant_id, name, version, conditions)
VALUES ('TENANT_001', 'MyPlaybook', 1, '{"match": {...}, "priority": 100}');
```

#### Updating Playbooks

**Best Practice:** Create a new version rather than updating in place.

1. **Load existing playbook**
2. **Create new version with updated fields**
3. **Test matching with sample exceptions**
4. **Deploy new version**
5. **Monitor for conflicts** (ensure old version doesn't still match unexpectedly)

#### Deleting Playbooks

**Important:** 
- Deleting a playbook removes it from future matching
- Exceptions already assigned to the playbook remain assigned (they keep `current_playbook_id`)
- Consider deprecation workflow: set low priority or narrow conditions before deletion

#### Testing Playbooks

Before deploying:

1. **Test Condition Matching**
   - Create test exceptions with various attributes
   - Verify playbook matches expected exceptions
   - Verify playbook doesn't match unexpected exceptions

2. **Test Step Execution**
   - Verify placeholders resolve correctly
   - Verify action executors handle parameters properly
   - Verify tool calls reference valid tool IDs

3. **Test Priority Logic**
   - Create multiple playbooks with overlapping conditions
   - Verify highest-priority playbook is selected

### Common Patterns

#### Pattern 1: Domain-Specific Default Playbook

Create a low-priority catch-all playbook for a domain:

```json
{
  "name": "GenericFinancePlaybook",
  "conditions": {
    "match": {
      "domain": "Finance"
    },
    "priority": 10  // Low priority - only matches if nothing else does
  },
  "steps": [
    {
      "step_order": 1,
      "name": "Assign to General Queue",
      "action_type": "assign_owner",
      "params": { "queue": "FinanceGeneralQueue" }
    }
  ]
}
```

#### Pattern 2: Severity-Based Escalation

Create playbooks with severity-specific handling:

```json
{
  "name": "CriticalExceptionPlaybook",
  "conditions": {
    "match": {
      "domain": "Finance",
      "severity": "critical"
    },
    "priority": 200
  },
  "steps": [
    {
      "step_order": 1,
      "name": "Immediate Escalation",
      "action_type": "set_status",
      "params": { "status": "escalated" }
    }
  ]
}
```

#### Pattern 3: SLA-Based Routing

Route exceptions based on SLA urgency:

```json
{
  "name": "UrgentSlaPlaybook",
  "conditions": {
    "match": {
      "domain": "Finance",
      "sla_minutes_remaining_lt": 30
    },
    "priority": 150
  },
  "steps": [
    {
      "step_order": 1,
      "name": "Escalate Urgent",
      "action_type": "set_status",
      "params": { "status": "escalated" }
    }
  ]
}
```

### Troubleshooting

#### Playbook Not Matching

**Check:**
1. Condition syntax is correct (valid JSON, correct field names)
2. Exception attributes match condition requirements
3. Priority is high enough (other playbooks may have higher priority)
4. Tenant ID matches (playbooks are tenant-scoped)

#### Placeholders Not Resolving

**Check:**
1. Placeholder syntax is correct: `{exception.field}` not `{{exception.field}}`
2. Field exists in exception (check normalized_context for nested fields)
3. Field is not null/empty (null values become empty strings)

#### Steps Not Executing

**Check:**
1. Playbook is assigned to exception (`current_playbook_id` is set)
2. Current step matches step order
3. Action executor supports the action type
4. Parameters are correctly formatted (valid JSON)

### Best Practices Summary

1. **Start Simple:** Create basic playbooks first, iterate based on results
2. **Use Priorities Wisely:** Reserve high priorities (100+) for specific, important playbooks
3. **Document Conditions:** Add comments/notes explaining why conditions are set
4. **Test Before Deploy:** Always test with sample exceptions before production deployment
5. **Version Carefully:** Increment versions for changes, but don't create versions unnecessarily
6. **Monitor Performance:** Track which playbooks match most often and adjust priorities accordingly
7. **Keep It Deterministic:** Avoid conditions that change over time (e.g., date-based conditions)
8. **Tenant Isolation:** Always verify `tenant_id` is set correctly for multi-tenant deployments

---

## Related Documentation

- [Phase 7 Playbooks MVP](./phase7-playbooks-mvp.md) - Detailed playbook implementation guide
- [Playbooks API Reference](./playbooks-api.md) - API endpoints for playbook operations
- [Domain Pack Schema](./05-domain-pack-schema.md) - Domain Pack structure and schema
- [Data Models & APIs](./03-data-models-apis.md) - API endpoints and data models
- [E2E Test Guide](./e2e-test-playbook-lifecycle.md) - Testing playbook lifecycle

