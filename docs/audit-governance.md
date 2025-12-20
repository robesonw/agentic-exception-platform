# Governance & Audit Trail - Phase 12+

This document describes the enterprise-grade governance and audit trail system implemented in Phase 12+ of the SentinAI platform.

## Overview

The governance audit system provides:
- **Comprehensive audit trail** for all governance-related actions
- **Consistent event schema** across all audited operations
- **Automatic sensitive data redaction** (API keys, tokens, PII)
- **Correlation ID propagation** for distributed tracing
- **Tenant isolation** for multi-tenant security
- **UI visibility** with filters, timeline views, and detail drawers

## Event Schema

All governance audit events use a standardized schema:

```json
{
  "id": "uuid",
  "event_type": "TENANT_CREATED",
  "actor_id": "admin@example.com",
  "actor_role": "admin",
  "tenant_id": "TENANT_001",
  "domain": "PAYMENTS",
  "entity_type": "tenant",
  "entity_id": "TENANT_001",
  "entity_version": "v1.0",
  "action": "create",
  "before_json": null,
  "after_json": { "...redacted state..." },
  "diff_summary": "Created tenant TENANT_001",
  "correlation_id": "cor_abc123def456",
  "request_id": "req_xyz789",
  "related_exception_id": null,
  "related_change_request_id": null,
  "metadata": {},
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "created_at": "2025-01-28T16:00:00Z"
}
```

### Event Types

| Event Type | Entity | Description |
|------------|--------|-------------|
| `TENANT_CREATED` | tenant | New tenant created |
| `TENANT_STATUS_CHANGED` | tenant | Tenant activated/suspended |
| `DOMAIN_PACK_IMPORTED` | domain_pack | New domain pack imported |
| `DOMAIN_PACK_UPDATED` | domain_pack | Domain pack updated (overwrite) |
| `DOMAIN_PACK_ACTIVATED` | domain_pack | Domain pack version activated |
| `TENANT_PACK_IMPORTED` | tenant_pack | New tenant pack imported |
| `TENANT_PACK_UPDATED` | tenant_pack | Tenant pack updated |
| `TENANT_PACK_ACTIVATED` | tenant_pack | Tenant pack version activated |
| `CONFIG_ACTIVATED` | active_config | Configuration activated for tenant |
| `CONFIG_ACTIVATION_REQUESTED` | active_config | Activation requested (pending approval) |
| `PLAYBOOK_CREATED` | playbook | New playbook created |
| `PLAYBOOK_LINKED` | playbook | Playbook linked to exception type |
| `TOOL_ENABLED` | tool | Tool enabled for tenant |
| `TOOL_DISABLED` | tool | Tool disabled for tenant |
| `RATE_LIMIT_CREATED` | rate_limit | Rate limit rule created |
| `RATE_LIMIT_UPDATED` | rate_limit | Rate limit rule updated |
| `ALERT_CONFIG_CREATED` | alert_config | Alert configuration created |
| `CONFIG_CHANGE_APPROVED` | config_change | Config change approved |
| `CONFIG_CHANGE_REJECTED` | config_change | Config change rejected |

### Actions

| Action | Description |
|--------|-------------|
| `create` | New entity created |
| `update` | Entity modified |
| `delete` | Entity deleted |
| `import` | Pack imported |
| `validate` | Pack validated |
| `activate` | Entity activated |
| `deprecate` | Entity deprecated |
| `enable` | Feature/tool enabled |
| `disable` | Feature/tool disabled |
| `approve` | Change approved |
| `reject` | Change rejected |
| `status_change` | Status changed |
| `link` | Entity linked |
| `unlink` | Entity unlinked |

## API Endpoints

### Query Events

```http
GET /admin/audit/events
```

Query parameters:
- `tenant_id` - Filter by tenant
- `domain` - Filter by domain
- `entity_type` - Filter by entity type
- `entity_id` - Filter by entity ID
- `event_type` - Filter by event type
- `action` - Filter by action
- `actor_id` - Filter by actor
- `correlation_id` - Filter by correlation ID
- `from_date` - Filter events after (ISO format)
- `to_date` - Filter events before (ISO format)
- `page` - Page number (1-indexed)
- `page_size` - Items per page (default 50)

### Get Single Event

```http
GET /admin/audit/events/{event_id}
```

### Entity Timeline

```http
GET /admin/audit/timeline?entity_type=tenant&entity_id=TENANT_001
```

### Recent Changes by Tenant

```http
GET /admin/audit/recent/{tenant_id}?limit=20
```

### Recent Changes for Entity

```http
GET /admin/audit/entity/{entity_type}/{entity_id}/recent?limit=5
```

### Correlated Events

```http
GET /admin/audit/correlation/{correlation_id}
```

## Sensitive Data Redaction

The system automatically redacts sensitive data from `before_json`, `after_json`, and `metadata` fields:

### Redacted Patterns
- API keys: `api_key`, `apikey`, `api-key`
- Tokens: `token`, `bearer`, `auth_token`, `access_token`, `refresh_token`
- Secrets: `secret`, `password`, `passwd`, `pwd`, `client_secret`
- Private keys: `private_key`, `signing_key`
- Connection strings: `postgres://`, `mysql://`, `mongodb://`, `redis://`

### Redacted PII
- Email addresses: `user@example.com` → `[EMAIL_REDACTED]`
- Phone numbers: `555-123-4567` → `[PHONE_REDACTED]`
- SSN patterns: `123-45-6789` → `[SSN_REDACTED]`
- Credit card numbers: `4111-1111-1111-1111` → `[CARD_REDACTED]`

## UI Components

### Admin Audit Page (`/admin/audit`)

Full audit event viewer with:
- Filter panel (tenant, entity type, action, date range)
- Sortable data table
- Detail drawer showing before/after JSON
- Correlation ID tracing
- Export capabilities

### Recent Changes Panel

Reusable component for embedding in detail views:

```tsx
<RecentChangesPanel
  entityType="tenant"
  entityId="TENANT_001"
  tenantId="TENANT_001"
  limit={5}
/>
```

## Database Schema

### governance_audit_event Table

```sql
CREATE TABLE governance_audit_event (
    id UUID PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    actor_id VARCHAR(255) NOT NULL,
    actor_role VARCHAR(50),
    tenant_id VARCHAR(255),
    domain VARCHAR(100),
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    entity_version VARCHAR(50),
    action VARCHAR(50) NOT NULL,
    before_json JSONB,
    after_json JSONB,
    diff_summary TEXT,
    correlation_id VARCHAR(100),
    request_id VARCHAR(100),
    related_exception_id VARCHAR(255),
    related_change_request_id VARCHAR(36),
    metadata JSONB,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX idx_gov_audit_tenant_created ON governance_audit_event(tenant_id, created_at);
CREATE INDEX idx_gov_audit_entity_type_id ON governance_audit_event(entity_type, entity_id);
CREATE INDEX idx_gov_audit_correlation ON governance_audit_event(correlation_id);
```

## Demo Verification Steps

1. **Create Tenant → Import Domain Pack → Validate → Activate**

   ```bash
   # 1. Create tenant
   curl -X POST http://localhost:8000/admin/tenants \
     -H "Content-Type: application/json" \
     -H "X-API-KEY: admin-key" \
     -d '{"tenant_id": "AUDIT_TEST", "name": "Audit Test Tenant"}'

   # 2. Import domain pack
   curl -X POST http://localhost:8000/admin/packs/domain/import \
     -H "Content-Type: application/json" \
     -H "X-API-KEY: admin-key" \
     -d '{"domain": "TEST", "version": "v1.0", "content": {"domainName": "TEST"}}'

   # 3. Activate
   curl -X POST http://localhost:8000/admin/packs/activate \
     -H "Content-Type: application/json" \
     -H "X-API-KEY: admin-key" \
     -d '{"tenant_id": "AUDIT_TEST", "domain": "TEST", "domain_pack_version": "v1.0"}'
   ```

2. **Verify Audit Events**

   ```bash
   curl "http://localhost:8000/admin/audit/events?tenant_id=AUDIT_TEST" \
     -H "X-API-KEY: admin-key"
   ```

   Should show 4 events:
   - TENANT_CREATED
   - DOMAIN_PACK_IMPORTED
   - DOMAIN_PACK_ACTIVATED
   - CONFIG_ACTIVATED

3. **UI Verification**

   - Navigate to `/admin/audit`
   - Filter by tenant "AUDIT_TEST"
   - Click on events to see detail drawer
   - Verify before/after JSON is redacted

## Files Changed

### Backend
- `src/infrastructure/db/models.py` - GovernanceAuditEvent model
- `alembic/versions/014_add_governance_audit_event_table.py` - Migration
- `src/services/governance_audit.py` - Audit utilities
- `src/infrastructure/repositories/governance_audit_repository.py` - Data access
- `src/api/routes/admin_audit.py` - API endpoints
- `src/api/routes/onboarding.py` - Audit emission
- `src/api/main.py` - Router registration

### Frontend
- `ui/src/api/governanceAudit.ts` - API client
- `ui/src/routes/admin/AuditPage.tsx` - Main audit page
- `ui/src/components/admin/RecentChangesPanel.tsx` - Reusable panel
- `ui/src/routes/admin/TenantsPage.tsx` - Recent changes integration
- `ui/src/routes/admin/AdminLandingPage.tsx` - Navigation link
- `ui/src/App.tsx` - Route registration

### Tests
- `tests/test_governance_audit.py` - Unit tests

## RBAC

- **Admin**: Full access to all audit events
- **Supervisor**: View events for their tenant
- **Tenant Admin**: View events for their own tenant only

All queries enforce tenant isolation via the `tenant_id` filter.

## Compliance Notes

1. **Immutable Audit Trail**: Events are append-only; no updates or deletes
2. **Timestamp Accuracy**: All timestamps are UTC with timezone
3. **Actor Traceability**: Every event includes actor ID and role
4. **Correlation Support**: Distributed tracing via correlation IDs
5. **Sensitive Data Protection**: Automatic redaction of secrets and PII
6. **Retention**: Consider implementing archival for old audit logs
