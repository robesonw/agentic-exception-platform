# Tenant Onboarding Guide

This guide covers the complete tenant onboarding process for the SentinAI platform.

## Overview

Tenant onboarding is the process of:
1. Creating a new tenant in the system
2. Importing and validating Domain Packs
3. Importing and validating Tenant Packs
4. Activating pack configurations
5. Linking playbooks to active configurations

## Prerequisites

- Admin access to the platform
- Domain Pack JSON file (if using custom domain)
- Tenant Pack JSON file (tenant-specific overrides)

## Step 1: Create Tenant

### Via UI

1. Navigate to `/admin/tenants`
2. Click "Create Tenant"
3. Enter:
   - **Tenant ID**: Unique identifier (e.g., `TENANT_FINANCE_001`)
   - **Name**: Display name for the tenant
4. Click "Create"

### Via API

```bash
POST /admin/tenants
{
  "tenant_id": "TENANT_FINANCE_001",
  "name": "Finance Department"
}
```

### Tenant Status

- **ACTIVE**: Tenant can process exceptions
- **SUSPENDED**: Tenant is temporarily disabled

## Step 2: Import Domain Pack

Domain Packs define domain-specific logic (classification rules, schemas, policies).

### Via UI

1. Navigate to `/admin/packs`
2. Select "Domain Packs" tab
3. Click "Import Pack"
4. Enter:
   - **Domain**: Domain name (e.g., "Finance")
   - **Version**: Version string (e.g., "v1.0")
   - **Pack JSON**: Upload file or paste JSON content
5. Click "Validate" to check for errors
6. Click "Import" to save

### Via API

```bash
POST /admin/packs/domain/import
{
  "domain": "Finance",
  "version": "v1.0",
  "content": { ... }
}
```

### Validation

Before importing, validate the pack:

```bash
POST /admin/packs/validate
{
  "pack_type": "domain",
  "content": { ... }
}
```

Validation checks:
- Schema correctness
- Required fields
- Unsupported keys
- Cross-reference checks (playbooks/tools)

## Step 3: Import Tenant Pack

Tenant Packs define tenant-specific overrides and customizations.

### Via UI

1. Navigate to `/admin/packs`
2. Select "Tenant Packs" tab
3. Click "Import Pack"
4. Enter:
   - **Tenant ID**: Select or enter tenant ID
   - **Version**: Version string (e.g., "v1.0")
   - **Pack JSON**: Upload file or paste JSON content
5. Click "Validate" to check for errors
6. Click "Import" to save

### Via API

```bash
POST /admin/packs/tenant/import
{
  "tenant_id": "TENANT_FINANCE_001",
  "version": "v1.0",
  "content": { ... }
}
```

### Validation

Validate tenant pack with domain context:

```bash
POST /admin/packs/validate
{
  "pack_type": "tenant",
  "content": { ... },
  "domain": "Finance"
}
```

## Step 4: Activate Pack Configuration

Activation makes pack versions active for a tenant. Only one version of each pack type can be active per tenant.

### Via UI

1. Navigate to `/admin/packs`
2. Find the pack version you want to activate
3. Click "View" to see details
4. Click "Activate Version"
5. Confirm activation

### Via API

```bash
POST /admin/packs/activate
{
  "tenant_id": "TENANT_FINANCE_001",
  "domain_pack_version": "v1.0",
  "tenant_pack_version": "v1.0",
  "require_approval": false
}
```

### Approval Workflow

If `require_approval` is `true`, activation creates a config change request that must be approved before taking effect.

## Step 5: Link Playbooks

Playbooks are automatically linked to tenants and domains through their configuration. You can verify compatibility:

1. Navigate to `/admin/playbooks`
2. Click "View" on a playbook
3. Check "Linked Pack Information" section
4. Verify compatibility warnings

## Active Configuration

View the active configuration for a tenant:

### Via UI

1. Navigate to `/admin/tenants`
2. Click "View" on a tenant
3. See "Active Configuration" section

### Via API

```bash
GET /admin/tenants/{tenant_id}/active-config
```

## Best Practices

1. **Version Naming**: Use semantic versioning (v1.0, v1.1, v2.0)
2. **Validation First**: Always validate packs before importing
3. **Test Activation**: Test pack activation in a non-production environment first
4. **Documentation**: Document custom overrides in tenant packs
5. **Audit Trail**: All operations are logged - check audit logs for changes

## Troubleshooting

### Pack Validation Fails

- Check schema against documentation
- Verify required fields are present
- Check for unsupported keys
- Verify cross-references (playbooks/tools exist)

### Activation Fails

- Verify pack versions exist
- Check pack status (must be ACTIVE or DRAFT)
- Verify tenant exists and is ACTIVE
- Check domain compatibility between domain and tenant packs

### Runtime Not Using Active Config

- Verify active configuration is set
- Check tenant status (must be ACTIVE)
- Verify pack versions are ACTIVE (not DRAFT)
- Check runtime logs for errors

## Reference

- [Pack Management Guide](./pack-management-guide.md)
- [Phase 12 MVP Specification](./phase12-onboarding-packs-mvp.md)
- [API Documentation](./03-data-models-apis.md)

