# Configuration Change Governance Guide

**Phase 10: Config Change Governance**  
Reference: `docs/phase10-ops-governance-mvp.md` Section 7

## Overview

The configuration change governance system enforces an approval workflow for changes to domain packs, tenant policy packs, tool definitions, and playbooks. This ensures that configuration changes are reviewed and approved before being applied to production.

## Change Request Workflow

The configuration change workflow follows these steps:

1. **Submit**: User submits a change request with proposed configuration
2. **Review**: Approver reviews the change request and diff
3. **Approve/Reject**: Approver approves or rejects the change
4. **Apply**: Approved changes are applied (creates new version)
5. **Audit**: All actions are logged in the audit trail

## Change Types

The following resource types support governance:

| Change Type | Resource | Description |
|-------------|----------|-------------|
| **domain_pack** | Domain Pack | Changes to domain pack configuration |
| **tenant_policy** | Tenant Policy Pack | Changes to tenant policy pack |
| **tool** | Tool Definition | Changes to tool definitions |
| **playbook** | Playbook | Changes to playbook configuration |

## Submitting a Change Request

### Create a Change Request

```bash
POST /admin/config-changes?tenant_id=TENANT_001&requested_by=user@example.com
{
  "change_type": "domain_pack",
  "resource_id": "domain-pack-001",
  "resource_name": "E-commerce Domain Pack",
  "proposed_config": {
    "domain": "ecommerce",
    "exception_types": ["payment_failure", "inventory_error"],
    "severity_mapping": {
      "payment_failure": "critical",
      "inventory_error": "warning"
    }
  },
  "current_config": {
    "domain": "ecommerce",
    "exception_types": ["payment_failure"],
    "severity_mapping": {
      "payment_failure": "critical"
    }
  },
  "diff_summary": "Added inventory_error exception type with warning severity",
  "change_reason": "Need to handle inventory errors in addition to payment failures"
}
```

### Change Request Fields

- **change_type**: Type of resource being changed (`domain_pack`, `tenant_policy`, `tool`, `playbook`)
- **resource_id**: ID of the resource being changed
- **resource_name**: Human-readable name (optional, for display)
- **proposed_config**: The new configuration (JSON object)
- **current_config**: Current configuration snapshot (optional, auto-populated if not provided)
- **diff_summary**: Human-readable description of changes (optional, auto-generated if not provided)
- **change_reason**: Reason for the change (optional)

### Auto-Generated Diff

If `current_config` is not provided, the system will:
1. Fetch the current configuration from the database
2. Compare with `proposed_config`
3. Generate a `diff_summary` automatically

## Reviewing Change Requests

### List Pending Changes

```bash
# List all pending changes
GET /admin/config-changes/pending?tenant_id=TENANT_001&page=1&page_size=50

# List changes with filters
GET /admin/config-changes?tenant_id=TENANT_001&status=pending&change_type=domain_pack
```

### View Change Details

```bash
GET /admin/config-changes/{change_id}?tenant_id=TENANT_001
```

Response includes:
- Change request metadata (status, requested_by, requested_at)
- Current configuration
- Proposed configuration
- Diff summary
- Review history (if reviewed)

### View Diff

The change detail response includes a side-by-side comparison:
- **current_config**: Current configuration
- **proposed_config**: Proposed configuration
- **diff_summary**: Text summary of changes

For UI display, use a diff viewer to highlight:
- **Added fields**: Fields present in proposed but not in current
- **Removed fields**: Fields present in current but not in proposed
- **Modified fields**: Fields with different values

## Approving Changes

### Approve a Change Request

```bash
POST /admin/config-changes/{change_id}/approve?tenant_id=TENANT_001&reviewed_by=admin@example.com
{
  "comment": "Approved - changes look good, tested in staging"
}
```

**Requirements:**
- Change must be in `pending` status
- User must have ADMIN role
- Approval sets status to `approved` and records reviewer

### Reject a Change Request

```bash
POST /admin/config-changes/{change_id}/reject?tenant_id=TENANT_001&reviewed_by=admin@example.com
{
  "comment": "Rejected - proposed severity mapping conflicts with existing policy"
}
```

**Requirements:**
- Change must be in `pending` status
- User must have ADMIN role
- Rejection sets status to `rejected` and records reviewer

## Applying Approved Changes

### Apply a Change

```bash
POST /admin/config-changes/{change_id}/apply?tenant_id=TENANT_001&applied_by=admin@example.com
```

**Requirements:**
- Change must be in `approved` status
- User must have ADMIN role
- Application sets status to `applied` and records applier

### Automatic Version Creation

When a change is applied:
1. System creates a new version of the resource
2. New version uses the `proposed_config`
3. Previous version is retained for rollback
4. `applied_at` timestamp is recorded

### Change Application by Type

#### Domain Pack Changes
- Creates new `domain_pack_version` record
- Links to tenant if tenant-specific
- Updates active version reference

#### Tenant Policy Pack Changes
- Creates new `tenant_policy_pack_version` record
- Links to specific tenant
- Updates active version reference

#### Tool Definition Changes
- Updates `tool_definition` record
- Preserves tool history
- Updates tool registry

#### Playbook Changes
- Updates `playbook` and `playbook_step` records
- Preserves playbook history
- Updates playbook registry

## Change Request Status

| Status | Description | Next Actions |
|--------|-------------|--------------|
| **pending** | Awaiting review | Approve or Reject |
| **approved** | Approved, ready to apply | Apply |
| **rejected** | Rejected, not applied | None (closed) |
| **applied** | Applied to production | None (closed) |

## Change History

### View Change History for a Resource

```bash
GET /admin/config-changes/resource/{resource_id}?tenant_id=TENANT_001
```

Returns all change requests for a specific resource, ordered by `requested_at` (newest first).

### Get Change Statistics

```bash
GET /admin/config-changes/stats?tenant_id=TENANT_001
```

Returns:
- Total change requests
- Counts by status (pending, approved, rejected, applied)
- Counts by change type

## Best Practices

### For Change Submitters

1. **Provide clear change reason**: Explain why the change is needed
2. **Include current config**: Helps reviewers understand context
3. **Test in staging first**: Verify changes work before submitting
4. **Keep changes focused**: Submit separate requests for unrelated changes
5. **Document breaking changes**: Note any backward-incompatible changes

### For Approvers

1. **Review diff carefully**: Understand what is changing
2. **Check for conflicts**: Ensure changes don't conflict with other configs
3. **Verify schema compliance**: Ensure proposed config matches schema
4. **Test in staging**: Test approved changes before applying
5. **Add review comments**: Document approval rationale

### For Operators

1. **Apply during maintenance windows**: Apply changes during low-traffic periods
2. **Monitor after application**: Watch for errors after applying changes
3. **Keep audit trail**: All changes are logged automatically
4. **Rollback plan**: Know how to rollback if issues occur
5. **Communicate changes**: Notify team of applied changes

## Schema Validation

Before approval, the system validates:
- **JSON Schema**: Proposed config must match resource schema
- **Required fields**: All required fields must be present
- **Field types**: Field values must match expected types
- **Constraints**: Business rules and constraints are enforced

Validation errors are returned in the API response.

## Rollback

If a change causes issues:

1. **View previous version**: Check change history for previous config
2. **Submit rollback change**: Create new change request with previous config
3. **Fast-track approval**: Expedite approval for rollback
4. **Apply rollback**: Apply the rollback change

The system retains all previous versions for rollback purposes.

## Audit Trail

All configuration changes are logged with:
- **Who**: User who requested, reviewed, applied
- **When**: Timestamps for each action
- **What**: Full configuration diff
- **Why**: Change reason and review comments

Query audit trail:
```bash
GET /audit?tenant_id=TENANT_001&resource_type=config_change
```

## Troubleshooting

### Change Request Not Appearing

1. **Check tenant_id**: Ensure correct tenant_id is used
2. **Check status filter**: Verify status filter is correct
3. **Check permissions**: Ensure user has access to tenant

### Approval Fails

1. **Check status**: Change must be in `pending` status
2. **Check permissions**: User must have ADMIN role
3. **Check validation**: Proposed config must pass validation

### Application Fails

1. **Check status**: Change must be in `approved` status
2. **Check permissions**: User must have ADMIN role
3. **Check resource exists**: Resource must exist in database
4. **Review logs**: Check backend logs for specific errors

### Diff Not Showing

1. **Check current_config**: Ensure current_config was provided or exists
2. **Check proposed_config**: Verify proposed_config is valid JSON
3. **Use UI diff viewer**: UI provides better diff visualization

## API Reference

### Change Requests

- `POST /admin/config-changes` - Submit change request
- `GET /admin/config-changes` - List change requests
- `GET /admin/config-changes/pending` - List pending changes
- `GET /admin/config-changes/{change_id}` - Get change details
- `GET /admin/config-changes/resource/{resource_id}` - Get resource change history
- `GET /admin/config-changes/stats` - Get change statistics

### Change Actions

- `POST /admin/config-changes/{change_id}/approve` - Approve change
- `POST /admin/config-changes/{change_id}/reject` - Reject change
- `POST /admin/config-changes/{change_id}/apply` - Apply change

## Related Documentation

- `docs/phase10-ops-governance-mvp.md` - Phase 10 specification
- `docs/05-domain-pack-schema.md` - Domain pack schema
- `docs/playbooks-configuration.md` - Playbook configuration
- `docs/tools-guide.md` - Tool configuration
- API documentation: `http://localhost:8000/docs` (when running locally)

