# Pack Management Guide

This guide covers Domain Pack and Tenant Pack structure, versioning, and management.

## Overview

Packs are versioned configuration files that define:
- **Domain Packs**: Domain-specific logic (classification rules, schemas, policies, tools, playbooks)
- **Tenant Packs**: Tenant-specific overrides and customizations

## Pack Structure

### Domain Pack Structure

```json
{
  "domainName": "Finance",
  "version": "v1.0",
  "exceptionTypes": {
    "PaymentFailed": {
      "description": "Payment processing failed",
      "severity": "high"
    }
  },
  "tools": {
    "refundPayment": {
      "name": "refundPayment",
      "description": "Refund a payment",
      "endpoint": "https://api.example.com/refund"
    }
  },
  "playbooks": [
    {
      "exceptionType": "PaymentFailed",
      "steps": [
        {
          "action": "refundPayment",
          "parameters": {"paymentId": "{{paymentId}}"}
        }
      ]
    }
  ]
}
```

### Tenant Pack Structure

```json
{
  "tenantId": "TENANT_FINANCE_001",
  "domainName": "Finance",
  "approvedTools": ["refundPayment"],
  "customSeverityOverrides": [],
  "customGuardrails": null,
  "humanApprovalRules": [],
  "retentionPolicies": null,
  "customPlaybooks": []
}
```

## Versioning

### Version Format

- Use semantic versioning: `v1.0`, `v1.1`, `v2.0`
- Versions are unique per domain (domain packs) or tenant (tenant packs)
- Versions cannot be modified after import

### Version Status

- **DRAFT**: Newly imported, not yet active
- **ACTIVE**: Currently active for a tenant
- **DEPRECATED**: No longer in use

## Pack Import

### Import Process

1. **Validate**: Check pack structure and references
2. **Import**: Save pack to database with version
3. **Activate**: Make pack version active for tenant (optional)

### Validation Rules

#### Domain Pack Validation

- `domainName` is required
- `exceptionTypes` must be valid
- `tools` must have valid schema
- `playbooks` must reference valid exception types and tools

#### Tenant Pack Validation

- `tenantId` must match existing tenant
- `domainName` must match active domain pack
- `approvedTools` must exist in domain pack
- Cross-reference checks with domain pack

### Import Methods

#### Via UI

1. Navigate to `/admin/packs`
2. Select pack type (Domain or Tenant)
3. Click "Import Pack"
4. Upload JSON file or paste content
5. Validate before importing

#### Via API

```bash
# Domain Pack
POST /admin/packs/domain/import
{
  "domain": "Finance",
  "version": "v1.0",
  "content": { ... }
}

# Tenant Pack
POST /admin/packs/tenant/import
{
  "tenant_id": "TENANT_FINANCE_001",
  "version": "v1.0",
  "content": { ... }
}
```

## Pack Activation

### Activation Process

1. Select pack version to activate
2. Verify compatibility
3. Confirm activation
4. System updates active configuration

### Active Configuration

Each tenant has one active configuration:
- One active domain pack version
- One active tenant pack version

### Activation Rules

- Pack version must exist
- Pack status must be ACTIVE or DRAFT
- Domain pack domain must match tenant pack domain
- Activation is immediate (unless approval required)

### Activation Methods

#### Via UI

1. Navigate to `/admin/packs`
2. Find pack version
3. Click "View" → "Activate Version"
4. Confirm activation

#### Via API

```bash
POST /admin/packs/activate
{
  "tenant_id": "TENANT_FINANCE_001",
  "domain_pack_version": "v1.0",
  "tenant_pack_version": "v1.0",
  "require_approval": false
}
```

## Pack Listing

### List Domain Packs

```bash
GET /admin/packs/domain?domain=Finance&status=ACTIVE&page=1&page_size=50
```

### List Tenant Packs

```bash
GET /admin/packs/tenant/{tenant_id}?status=ACTIVE&page=1&page_size=50
```

### Get Specific Pack Version

```bash
# Domain Pack
GET /admin/packs/domain/{domain}/{version}

# Tenant Pack
GET /admin/packs/tenant/{tenant_id}/{version}
```

## Pack Compatibility

### Domain-Tenant Pack Compatibility

- Tenant pack `domainName` must match domain pack `domainName`
- Tenant pack `approvedTools` must exist in domain pack
- Playbooks in tenant pack must reference valid tools

### Playbook Compatibility

- Playbook domain must match active domain pack domain
- Playbook tools must be approved in tenant pack
- Playbook exception types must exist in domain pack

## Best Practices

### Versioning

1. **Semantic Versioning**: Use `v1.0`, `v1.1`, `v2.0` format
2. **Incremental Changes**: Minor changes → patch version, major changes → major version
3. **Documentation**: Document changes in version comments

### Import Workflow

1. **Validate First**: Always validate before importing
2. **Test in DRAFT**: Import as DRAFT, test, then activate
3. **Backup Active**: Note current active version before changing
4. **Rollback Plan**: Keep previous version available

### Activation Workflow

1. **Verify Compatibility**: Check domain and tool compatibility
2. **Test Activation**: Test in non-production first
3. **Monitor Runtime**: Watch for errors after activation
4. **Rollback if Needed**: Revert to previous version if issues

### Pack Organization

1. **Domain Separation**: Keep domain-specific logic in domain packs
2. **Tenant Overrides**: Only tenant-specific changes in tenant packs
3. **Tool Approval**: Explicitly approve tools in tenant packs
4. **Documentation**: Document custom overrides and reasons

## Troubleshooting

### Import Fails

- **Schema Errors**: Check JSON structure against schema
- **Missing Fields**: Verify all required fields are present
- **Invalid References**: Check tool/playbook references exist
- **Version Conflict**: Version may already exist

### Validation Fails

- **Schema Issues**: Check pack structure
- **Cross-References**: Verify referenced tools/playbooks exist
- **Domain Mismatch**: Tenant pack domain must match domain pack

### Activation Fails

- **Version Not Found**: Verify pack version exists
- **Status Issue**: Pack must be ACTIVE or DRAFT
- **Compatibility**: Check domain and tool compatibility
- **Tenant Status**: Tenant must be ACTIVE

### Runtime Issues

- **Active Config Missing**: Verify active configuration is set
- **Pack Not Found**: Check pack versions exist and are accessible
- **Version Mismatch**: Verify runtime is using correct versions

## Reference

- [Tenant Onboarding Guide](./tenant-onboarding-guide.md)
- [Phase 12 MVP Specification](./phase12-onboarding-packs-mvp.md)
- [Data Models & APIs](./03-data-models-apis.md)

