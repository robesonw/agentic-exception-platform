# Tenant Isolation at Message Broker Layer

## Overview

Phase 9 P9-23: Enforce tenant isolation at the message broker layer to prevent cross-tenant event processing and ensure data security.

## Topic Naming Strategies

### Option A: Shared Topics + Strict Tenant Validation (MVP)

**Strategy:**
- Use shared topics across all tenants (e.g., `exceptions`, `sla`, `playbooks`)
- Enforce tenant isolation through strict validation in event handlers
- Validate `tenant_id` in every worker before processing events

**Topics:**
- `exceptions` - All exception-related events
- `sla` - SLA monitoring events
- `playbooks` - Playbook-related events
- `tools` - Tool execution events

**Advantages:**
- Simple to implement and maintain
- Lower operational overhead (fewer topics)
- Easier to monitor and debug
- Works with any message broker

**Disadvantages:**
- Requires strict validation in all handlers
- Potential for cross-tenant data leakage if validation fails
- All tenants share the same topic partitions

**Implementation:**
- All workers validate `tenant_id` in `_handle_message` before processing
- Reject events with mismatched or missing `tenant_id`
- Log security violations for audit

### Option B: Per-Tenant Topics (Enhanced Isolation)

**Strategy:**
- Create separate topics per tenant (e.g., `exceptions.tenant_001`, `exceptions.tenant_002`)
- Use topic-level access control (if supported by broker)
- Workers subscribe to tenant-specific topics

**Topic Naming Pattern:**
- `{topic_base}.{tenant_id}` (e.g., `exceptions.tenant_001`)
- Or: `{tenant_id}.{topic_base}` (e.g., `tenant_001.exceptions`)

**Advantages:**
- Stronger isolation at broker level
- Can leverage broker-level access control
- Easier to scale per tenant
- Clear separation of concerns

**Disadvantages:**
- Higher operational overhead (many topics)
- Requires dynamic topic creation/management
- More complex subscription logic
- May hit broker topic limits at scale

**Implementation (Future):**
- Topic creation service for new tenants
- Dynamic worker subscription based on tenant assignment
- Broker-level ACL configuration
- Topic cleanup for deactivated tenants

## Current Implementation (Option A - MVP)

All workers implement tenant validation in `_handle_message`:

1. **Deserialize event** - Extract `tenant_id` from event
2. **Validate tenant_id** - Ensure it matches expected tenant (if worker is tenant-scoped)
3. **Reject cross-tenant events** - Log security violation and skip processing
4. **Process event** - Only if tenant validation passes

## Security Considerations

### Validation Points

1. **Worker Level:**
   - Validate `tenant_id` in `_handle_message` before processing
   - Reject events with missing or invalid `tenant_id`

2. **Event Publisher:**
   - Ensure `tenant_id` is always present in events
   - Validate `tenant_id` format before publishing

3. **Partition Key:**
   - Include `tenant_id` in partition key to ensure tenant-level ordering
   - Prevents cross-tenant message mixing in partitions

### Audit Trail

- Log all tenant validation failures
- Track cross-tenant event attempts
- Alert on suspicious patterns

## Migration Path to Option B

When migrating to per-tenant topics:

1. **Phase 1:** Implement topic naming utility
2. **Phase 2:** Create topic management service
3. **Phase 3:** Update workers to support dynamic subscriptions
4. **Phase 4:** Migrate tenants gradually
5. **Phase 5:** Deprecate shared topics

## References

- `docs/phase9-async-scale-mvp.md` Section 11
- `src/workers/base.py` - Tenant validation implementation
- `src/messaging/partitioning.py` - Partition key generation



