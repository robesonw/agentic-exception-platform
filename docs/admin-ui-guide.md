# Admin UI Guide

## Overview

The Admin UI provides governance and configuration management workflows for administrators. All Admin pages are protected by the `VITE_ADMIN_ENABLED` feature flag and require admin role.

## Access Control

- **Feature Flag**: Set `VITE_ADMIN_ENABLED=true` in `ui/.env` to enable Admin menu and routes
- **Route Protection**: Accessing `/admin/*` routes without the flag enabled shows "Not authorized" page
- **Role Gating**: Admin actions (approve, activate, enable/disable) require admin role
- **Tenant Context**: All pages require a tenant to be selected (via tenant selector in header)

## Pages

### Admin Landing (`/admin`)

**Purpose**: Central hub for admin workflows

**Features**:
- Quick link cards to all admin pages
- Pending approvals summary:
  - Count of pending configuration changes
  - Link to config changes page
- Recent activity (optional)

**Usage**:
1. Navigate to `/admin`
2. Review pending approvals count
3. Click quick link cards to navigate to specific admin pages

### Config Change Governance (`/admin/config-changes`)

**Purpose**: Review and approve configuration change requests

**Features**:
- Pending changes list table
- Change detail view with:
  - Config diff (before/after) with highlighting
  - Requestor information and timestamp
  - Review comments
- Actions (admin only):
  - Approve change (with confirmation)
  - Reject change (with comment required)

**Usage**:
1. Navigate to `/admin/config-changes`
2. Review pending changes list
3. Click "View" to see change details and diff
4. Review proposed configuration changes
5. Approve or reject with comment:
   - Click "Approve" → Confirm in dialog
   - Click "Reject" → Enter rejection reason → Confirm

**Best Practices**:
- Always review diff before approving
- Provide clear comments when rejecting
- Check impact on other tenants/domains

### Packs Management (`/admin/packs`)

**Purpose**: View and manage Domain Packs and Tenant Policy Packs

**Features**:
- Tab selector: Domain Packs / Tenant Packs
- Pack list table:
  - Pack name, version, domain, tenant (for tenant packs)
  - Active version indicator
- Pack detail view:
  - Full pack JSON configuration
  - Version information
- Actions (admin only):
  - Activate pack version (with confirmation)

**Usage**:
1. Navigate to `/admin/packs`
2. Select tab (Domain Packs or Tenant Packs)
3. Review pack list
4. Click "View" to see full pack configuration
5. To activate a version:
   - Click "Activate" on pack row or in detail view
   - Confirm activation in dialog
   - Verify active indicator updates

**Note**: Import/upload functionality shows "coming soon" if backend doesn't support it.

### Playbooks Management (`/admin/playbooks`)

**Purpose**: View and manage playbook configurations

**Features**:
- Playbooks list table:
  - Name, exception type, domain, version
  - Active status indicator
- Playbook detail view:
  - Match rules (JSON)
  - Steps (array)
  - Referenced tools (list)
- Actions (admin only):
  - Activate/deactivate playbook (with confirmation)

**Usage**:
1. Navigate to `/admin/playbooks`
2. Apply filters (tenant, domain, exception type)
3. Review playbook list
4. Click "View" to see full playbook details
5. To activate/deactivate:
   - Click "Activate" or "Deactivate" button
   - Confirm in dialog
   - Verify status updates

**Best Practices**:
- Review match rules before activating
- Verify referenced tools are enabled
- Test playbook in simulation mode first

### Tools Management (`/admin/tools`)

**Purpose**: View and manage tool registry and tenant enablement

**Features**:
- Tool registry list table:
  - Name, description, provider
  - Enabled status per tenant
  - Allowed tenants list
- Tool detail view:
  - Full tool schema (JSON)
  - Provider information
  - Allowed tenants
- Actions (admin only):
  - Enable/disable tool for tenant (with confirmation)

**Usage**:
1. Navigate to `/admin/tools`
2. Apply filters (provider, enabled status)
3. Review tool list
4. Click "View" to see full tool schema
5. To enable/disable for tenant:
   - Click "Enable" or "Disable" button
   - Confirm in dialog
   - Verify status updates

**Note**: Tool detail links to existing tool detail page (`/tools/:id`).

## Common Patterns

### Admin Actions
- All destructive/admin actions require `ConfirmDialog`
- Actions are role-gated (admin only)
- Changes update UI immediately after success
- Error states show clear messages

### Configuration Viewing
- All configs displayed in `CodeViewer` with syntax highlighting
- JSON formatted and pretty-printed
- Copy to clipboard available
- Expand/collapse for large configs

### Diff Viewing
- Config changes show before/after diff
- Differences highlighted with color coding
- Side-by-side or unified view (depending on backend)

### Version Management
- Active versions clearly marked with "Active" chip
- Version history available (if backend supports)
- Activation requires confirmation

## Feature Flags

Set in `ui/.env`:
```bash
VITE_ADMIN_ENABLED=true
VITE_API_BASE_URL=http://localhost:8000
```

## Security Considerations

- **Admin Actions**: All admin actions (approve, activate, enable/disable) require explicit confirmation
- **Audit Trail**: All admin actions are logged in backend audit trail
- **Role Gating**: Front-end role checks complement backend RBAC
- **Tenant Isolation**: All operations are tenant-scoped

## Troubleshooting

**Issue**: Admin menu not showing
- **Solution**: Check `VITE_ADMIN_ENABLED=true` in `ui/.env` and restart dev server

**Issue**: "Not authorized" page
- **Solution**: Ensure `VITE_ADMIN_ENABLED=true` in `ui/.env` and tenantId is set in localStorage

**Issue**: Cannot approve/reject changes
- **Solution**: Verify admin role and feature flag enabled

**Issue**: Activation not working
- **Solution**: Check backend API response, verify tenant context is included

**Issue**: Diff not showing
- **Solution**: Verify backend supports diff endpoint, check browser console for errors

