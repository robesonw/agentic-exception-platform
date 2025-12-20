# Phase 12 Tenant & Domain Pack Onboarding MVP - GitHub Issues Checklist

## Component: Database Models & Migrations

### Issue P12-1: Implement Tenants Database Model and Migration
**Labels:** `component:database`, `phase:12`, `priority:high`
**Description:**
- Create database table for tenants:
  - `tenant_id` (PK, string)
  - `name` (string)
  - `status` (enum: ACTIVE | SUSPENDED)
  - `created_at` (timestamp)
  - `created_by` (string, user identifier)
- Create SQLAlchemy model: `Tenant`
- Create Alembic migration for tenants table
- Add indexes on tenant_id and status
- Reference: docs/phase12-onboarding-packs-mvp.md Section 4.1

**Dependencies:** None (foundational)

**Acceptance Criteria:**
- [ ] tenants table created with migration
- [ ] Tenant SQLAlchemy model implemented
- [ ] All required fields present
- [ ] Indexes created on tenant_id and status
- [ ] Migration tested and reversible
- [ ] Unit tests for Tenant model

---

### Issue P12-2: Implement Domain Packs Database Model and Migration
**Labels:** `component:database`, `phase:12`, `priority:high`
**Description:**
- Create database table for domain packs:
  - `id` (PK, auto-increment)
  - `domain` (string, indexed)
  - `version` (string, indexed)
  - `content_json` (jsonb)
  - `checksum` (string, for integrity)
  - `status` (enum: DRAFT | ACTIVE | DEPRECATED)
  - `created_at` (timestamp)
  - `created_by` (string)
- Create SQLAlchemy model: `DomainPack`
- Create Alembic migration for domain_packs table
- Add unique constraint on (domain, version)
- Reference: docs/phase12-onboarding-packs-mvp.md Section 4.2

**Dependencies:** None

**Acceptance Criteria:**
- [ ] domain_packs table created with migration
- [ ] DomainPack SQLAlchemy model implemented
- [ ] All required fields present
- [ ] Unique constraint on (domain, version)
- [ ] Indexes created on domain and version
- [ ] Migration tested and reversible
- [ ] Unit tests for DomainPack model

---

### Issue P12-3: Implement Tenant Packs Database Model and Migration
**Labels:** `component:database`, `phase:12`, `priority:high`
**Description:**
- Create database table for tenant packs:
  - `id` (PK, auto-increment)
  - `tenant_id` (FK to tenants, indexed)
  - `version` (string, indexed)
  - `content_json` (jsonb)
  - `checksum` (string, for integrity)
  - `status` (enum: DRAFT | ACTIVE | DEPRECATED)
  - `created_at` (timestamp)
  - `created_by` (string)
- Create SQLAlchemy model: `TenantPack`
- Create Alembic migration for tenant_packs table
- Add unique constraint on (tenant_id, version)
- Add foreign key constraint to tenants table
- Reference: docs/phase12-onboarding-packs-mvp.md Section 4.3

**Dependencies:** P12-1

**Acceptance Criteria:**
- [ ] tenant_packs table created with migration
- [ ] TenantPack SQLAlchemy model implemented
- [ ] All required fields present
- [ ] Unique constraint on (tenant_id, version)
- [ ] Foreign key constraint to tenants table
- [ ] Indexes created on tenant_id and version
- [ ] Migration tested and reversible
- [ ] Unit tests for TenantPack model

---

### Issue P12-4: Implement Active Configuration Database Model and Migration
**Labels:** `component:database`, `phase:12`, `priority:high`
**Description:**
- Create database table for active configuration:
  - `tenant_id` (PK, FK to tenants)
  - `active_domain_pack_version` (string, nullable)
  - `active_tenant_pack_version` (string, nullable)
  - `activated_at` (timestamp)
  - `activated_by` (string)
- Create SQLAlchemy model: `TenantActiveConfig`
- Create Alembic migration for tenant_active_config table
- Add foreign key constraint to tenants table
- Reference: docs/phase12-onboarding-packs-mvp.md Section 4.4

**Dependencies:** P12-1, P12-2, P12-3

**Acceptance Criteria:**
- [ ] tenant_active_config table created with migration
- [ ] TenantActiveConfig SQLAlchemy model implemented
- [ ] All required fields present
- [ ] Foreign key constraint to tenants table
- [ ] Migration tested and reversible
- [ ] Unit tests for TenantActiveConfig model

---

## Component: Repository Layer

### Issue P12-5: Implement Tenant Repository
**Labels:** `component:repository`, `phase:12`, `priority:high`
**Description:**
- Create TenantRepository class:
  - `create_tenant(tenant_id, name, created_by)` - Create new tenant
  - `get_tenant(tenant_id)` - Get tenant by ID
  - `list_tenants(status=None)` - List tenants with optional status filter
  - `update_tenant_status(tenant_id, status, updated_by)` - Update tenant status
- Enforce tenant isolation in all queries
- Add proper error handling for not found cases
- Reference: docs/phase12-onboarding-packs-mvp.md Section 5.1

**Dependencies:** P12-1

**Acceptance Criteria:**
- [ ] TenantRepository implemented
- [ ] Create tenant operation functional
- [ ] Get tenant operation functional
- [ ] List tenants with status filter working
- [ ] Update tenant status functional
- [ ] Tenant isolation enforced
- [ ] Error handling for not found cases
- [ ] Unit tests for repository operations
- [ ] Integration tests with database

---

### Issue P12-6: Implement Domain Pack Repository
**Labels:** `component:repository`, `phase:12`, `priority:high`
**Description:**
- Create DomainPackRepository class:
  - `create_domain_pack(domain, version, content_json, created_by)` - Create new pack version
  - `get_domain_pack(domain, version)` - Get pack by domain and version
  - `list_domain_packs(domain=None, status=None)` - List packs with filters
  - `get_latest_version(domain)` - Get latest version for domain
  - `update_pack_status(id, status)` - Update pack status
- Calculate and store checksum for content_json
- Support version comparison and ordering
- Reference: docs/phase12-onboarding-packs-mvp.md Section 5.2

**Dependencies:** P12-2

**Acceptance Criteria:**
- [ ] DomainPackRepository implemented
- [ ] Create pack operation functional
- [ ] Get pack by domain/version working
- [ ] List packs with filters working
- [ ] Get latest version functional
- [ ] Update pack status functional
- [ ] Checksum calculation and storage working
- [ ] Version ordering working
- [ ] Unit tests for repository operations
- [ ] Integration tests with database

---

### Issue P12-7: Implement Tenant Pack Repository
**Labels:** `component:repository`, `phase:12`, `priority:high`
**Description:**
- Create TenantPackRepository class:
  - `create_tenant_pack(tenant_id, version, content_json, created_by)` - Create new pack version
  - `get_tenant_pack(tenant_id, version)` - Get pack by tenant and version
  - `list_tenant_packs(tenant_id, status=None)` - List packs for tenant with status filter
  - `get_latest_version(tenant_id)` - Get latest version for tenant
  - `update_pack_status(id, status)` - Update pack status
- Calculate and store checksum for content_json
- Enforce tenant isolation in all queries
- Support version comparison and ordering
- Reference: docs/phase12-onboarding-packs-mvp.md Section 5.2

**Dependencies:** P12-3

**Acceptance Criteria:**
- [ ] TenantPackRepository implemented
- [ ] Create pack operation functional
- [ ] Get pack by tenant/version working
- [ ] List packs with filters working
- [ ] Get latest version functional
- [ ] Update pack status functional
- [ ] Checksum calculation and storage working
- [ ] Tenant isolation enforced
- [ ] Version ordering working
- [ ] Unit tests for repository operations
- [ ] Integration tests with database

---

### Issue P12-8: Implement Active Configuration Repository
**Labels:** `component:repository`, `phase:12`, `priority:high`
**Description:**
- Create TenantActiveConfigRepository class:
  - `get_active_config(tenant_id)` - Get active configuration for tenant
  - `activate_config(tenant_id, domain_pack_version, tenant_pack_version, activated_by)` - Activate configuration
  - `update_active_config(tenant_id, domain_pack_version, tenant_pack_version, activated_by)` - Update active configuration
- Validate that pack versions exist before activation
- Enforce tenant isolation
- Reference: docs/phase12-onboarding-packs-mvp.md Section 5.4

**Dependencies:** P12-4, P12-6, P12-7

**Acceptance Criteria:**
- [ ] TenantActiveConfigRepository implemented
- [ ] Get active config operation functional
- [ ] Activate config operation functional
- [ ] Update active config operation functional
- [ ] Pack version validation before activation
- [ ] Tenant isolation enforced
- [ ] Unit tests for repository operations
- [ ] Integration tests with database

---

## Component: Pack Validation Service

### Issue P12-9: Implement Pack Validation Service
**Labels:** `component:validation`, `phase:12`, `priority:high`
**Description:**
- Create PackValidationService class:
  - Validate schema correctness (required fields, types)
  - Validate required fields are present
  - Check for unsupported keys
  - Perform cross-reference checks (playbooks/tools exist)
  - Validate domain pack structure (classification rules, schemas, policies)
  - Validate tenant pack structure (overrides, customizations)
- Return validation result with errors and warnings
- Support validation for both domain packs and tenant packs
- Reference: docs/phase12-onboarding-packs-mvp.md Section 5.2

**Dependencies:** None (can validate independently)

**Acceptance Criteria:**
- [ ] PackValidationService implemented
- [ ] Schema correctness validation working
- [ ] Required fields validation working
- [ ] Unsupported keys detection working
- [ ] Cross-reference checks functional
- [ ] Domain pack structure validation working
- [ ] Tenant pack structure validation working
- [ ] Validation result includes errors and warnings
- [ ] Unit tests for validation scenarios
- [ ] Integration tests with sample packs

---

## Component: Backend APIs - Tenant Management

### Issue P12-10: Implement Tenant Management API Endpoints
**Labels:** `component:api:tenants`, `phase:12`, `priority:high`
**Description:**
- Create tenant management API endpoints:
  - `POST /admin/tenants` - Create new tenant
  - `GET /admin/tenants` - List all tenants (with status filter)
  - `GET /admin/tenants/{tenant_id}` - Get tenant details
  - `PATCH /admin/tenants/{tenant_id}/status` - Update tenant status
- Require ADMIN role for all endpoints
- Validate tenant_id format
- Return proper error responses (404, 400, 403)
- Emit audit events for tenant operations
- Reference: docs/phase12-onboarding-packs-mvp.md Section 5.1

**Dependencies:** P12-5

**Acceptance Criteria:**
- [ ] POST /admin/tenants endpoint working
- [ ] GET /admin/tenants endpoint working with filters
- [ ] GET /admin/tenants/{tenant_id} endpoint working
- [ ] PATCH /admin/tenants/{tenant_id}/status endpoint working
- [ ] ADMIN role required for all endpoints
- [ ] Input validation functional
- [ ] Error responses correct (404, 400, 403)
- [ ] Audit events emitted
- [ ] Unit tests for API endpoints
- [ ] Integration tests for full flow

---

## Component: Backend APIs - Pack Management

### Issue P12-11: Implement Pack Import and Validation API
**Labels:** `component:api:packs`, `phase:12`, `priority:high`
**Description:**
- Create pack import API endpoints:
  - `POST /admin/packs/domain/import` - Import domain pack JSON
  - `POST /admin/packs/tenant/import` - Import tenant pack JSON
  - `POST /admin/packs/validate` - Validate pack without importing
- Accept JSON payload in request body
- Validate pack structure using PackValidationService
- Generate version automatically or accept version in request
- Calculate and store checksum
- Return validation errors if pack is invalid
- Require ADMIN role for import endpoints
- Reference: docs/phase12-onboarding-packs-mvp.md Section 5.2

**Dependencies:** P12-6, P12-7, P12-9

**Acceptance Criteria:**
- [ ] POST /admin/packs/domain/import endpoint working
- [ ] POST /admin/packs/tenant/import endpoint working
- [ ] POST /admin/packs/validate endpoint working
- [ ] Pack validation integrated
- [ ] Version generation/acceptance working
- [ ] Checksum calculation and storage working
- [ ] Validation errors returned correctly
- [ ] ADMIN role required
- [ ] Unit tests for import endpoints
- [ ] Integration tests with invalid packs

---

### Issue P12-12: Implement Pack Listing and Version API
**Labels:** `component:api:packs`, `phase:12`, `priority:high`
**Description:**
- Create pack listing API endpoints:
  - `GET /admin/packs/domain` - List domain packs (with domain filter)
  - `GET /admin/packs/domain/{domain}/{version}` - Get specific domain pack version
  - `GET /admin/packs/tenant/{tenant_id}` - List tenant packs for tenant
  - `GET /admin/packs/tenant/{tenant_id}/{version}` - Get specific tenant pack version
- Support filtering by domain, status, tenant_id
- Return pack metadata and content_json
- Support pagination for large result sets
- Require ADMIN role for all endpoints
- Reference: docs/phase12-onboarding-packs-mvp.md Section 5.3

**Dependencies:** P12-6, P12-7

**Acceptance Criteria:**
- [ ] GET /admin/packs/domain endpoint working with filters
- [ ] GET /admin/packs/domain/{domain}/{version} endpoint working
- [ ] GET /admin/packs/tenant/{tenant_id} endpoint working
- [ ] GET /admin/packs/tenant/{tenant_id}/{version} endpoint working
- [ ] Filtering by domain/status/tenant_id working
- [ ] Pagination supported
- [ ] ADMIN role required
- [ ] Unit tests for listing endpoints
- [ ] Integration tests with multiple packs

---

### Issue P12-13: Implement Pack Activation API
**Labels:** `component:api:packs`, `phase:12`, `priority:high`
**Description:**
- Create pack activation API endpoint:
  - `POST /admin/packs/activate` - Activate pack versions for tenant
- Accept payload:
  ```json
  {
    "tenant_id": "TENANT_FINANCE_001",
    "domain_pack_version": "v3.2",
    "tenant_pack_version": "v1.4"
  }
  ```
- Validate that pack versions exist and are in ACTIVE or DRAFT status
- Validate pack compatibility (if applicable)
- Update tenant_active_config table
- Emit activation audit event
- Require ADMIN role
- Reference: docs/phase12-onboarding-packs-mvp.md Section 5.4

**Dependencies:** P12-8, P12-6, P12-7

**Acceptance Criteria:**
- [ ] POST /admin/packs/activate endpoint working
- [ ] Pack version existence validation working
- [ ] Pack status validation working
- [ ] Active configuration updated correctly
- [ ] Activation audit event emitted
- [ ] ADMIN role required
- [ ] Proper error responses for invalid versions
- [ ] Unit tests for activation endpoint
- [ ] Integration tests for activation flow

---

## Component: Runtime Integration

### Issue P12-14: Integrate Active Configuration with Runtime
**Labels:** `component:runtime`, `phase:12`, `priority:high`
**Description:**
- Update runtime components to use active configuration from database:
  - Modify agent orchestrator to load active config per tenant
  - Update domain pack loader to read from database instead of files
  - Update tenant pack loader to read from database instead of files
  - Cache active configuration with TTL to reduce database queries
- Ensure backward compatibility with file-based configs (if still needed)
- Support hot-reload of active configuration (optional, for MVP)
- Reference: docs/phase12-onboarding-packs-mvp.md Section 10

**Dependencies:** P12-8

**Acceptance Criteria:**
- [ ] Agent orchestrator loads active config from database
- [ ] Domain pack loader reads from database
- [ ] Tenant pack loader reads from database
- [ ] Active configuration caching implemented
- [ ] Backward compatibility maintained (if applicable)
- [ ] Runtime uses active configuration correctly
- [ ] Unit tests for configuration loading
- [ ] Integration tests for runtime with active config

---

## Component: UI - Tenant Management

### Issue P12-15: Implement Admin Tenants Management UI
**Labels:** `component:ui:admin`, `phase:12`, `priority:high`
**Description:**
- Create Admin Tenants page at `/admin/tenants` route
- Display tenants list table with columns:
  - Tenant ID
  - Name
  - Status (ACTIVE | SUSPENDED) with color coding
  - Created at
  - Created by
  - Actions (view, edit status)
- Implement create tenant form:
  - Tenant ID input (required, validated)
  - Name input (required)
  - Submit button
- Implement status update:
  - Enable/suspend tenant button (with ConfirmDialog)
- Display active configuration for each tenant (if exists)
- Add filters: status
- Use DataTable, FilterBar, ConfirmDialog components
- Reference: docs/phase12-onboarding-packs-mvp.md Section 6.1

**Dependencies:** P12-10, P11-2, P11-3, P11-4

**Acceptance Criteria:**
- [ ] Admin Tenants page created at `/admin/tenants` route
- [ ] Tenants list table displays all columns
- [ ] Create tenant form functional
- [ ] Status update functional with confirmation
- [ ] Active configuration displayed
- [ ] Filters apply correctly
- [ ] Data fetched from `/admin/tenants` API
- [ ] Loading and error states handled
- [ ] Unit tests for Tenants Management components

---

## Component: UI - Pack Management

### Issue P12-16: Implement Domain Packs Management UI
**Labels:** `component:ui:admin`, `phase:12`, `priority:high`
**Description:**
- Create Domain Packs tab in Admin Packs page (`/admin/packs`)
- Display domain packs list table:
  - Pack ID / Domain
  - Version
  - Status (DRAFT | ACTIVE | DEPRECATED) with color coding
  - Created at
  - Created by
  - Actions (view, activate)
- Implement pack import/upload:
  - File upload button or JSON textarea
  - Validate button (calls validation API)
  - Import button (calls import API)
  - Show validation results (errors/warnings)
- Implement pack detail view:
  - Full pack JSON (use CodeViewer)
  - Version history
  - Checksum display
- Implement activate version button (admin only, with ConfirmDialog)
- Show current active version indicator
- Add filters: domain, status
- Use DataTable, FilterBar, ConfirmDialog, CodeViewer components
- Reference: docs/phase12-onboarding-packs-mvp.md Section 6.2

**Dependencies:** P12-11, P12-12, P12-13, P11-2, P11-3, P11-4, P11-5

**Acceptance Criteria:**
- [ ] Domain Packs tab created in `/admin/packs` page
- [ ] Domain packs list table displays correctly
- [ ] Pack import/upload functional
- [ ] Validation results displayed
- [ ] Pack detail view shows full JSON
- [ ] Activate version button functional (admin only)
- [ ] Current active version indicator displayed
- [ ] Filters apply correctly
- [ ] Data fetched from `/admin/packs/domain` API
- [ ] Loading and error states handled
- [ ] Unit tests for Domain Packs components

---

### Issue P12-17: Implement Tenant Packs Management UI
**Labels:** `component:ui:admin`, `phase:12`, `priority:high`
**Description:**
- Create Tenant Packs tab in Admin Packs page (`/admin/packs`)
- Display tenant packs list table:
  - Tenant ID
  - Pack ID
  - Version
  - Status (DRAFT | ACTIVE | DEPRECATED) with color coding
  - Created at
  - Created by
  - Actions (view, activate)
- Implement pack import/upload:
  - Tenant selector (required)
  - File upload button or JSON textarea
  - Validate button (calls validation API)
  - Import button (calls import API)
  - Show validation results (errors/warnings)
- Implement pack detail view:
  - Full pack JSON (use CodeViewer)
  - Version history
  - Checksum display
- Implement activate version button (admin only, with ConfirmDialog)
- Show current active version indicator
- Add filters: tenant, status
- Use DataTable, FilterBar, ConfirmDialog, CodeViewer components
- Reference: docs/phase12-onboarding-packs-mvp.md Section 6.2

**Dependencies:** P12-11, P12-12, P12-13, P11-2, P11-3, P11-4, P11-5

**Acceptance Criteria:**
- [ ] Tenant Packs tab created in `/admin/packs` page
- [ ] Tenant packs list table displays correctly
- [ ] Pack import/upload functional with tenant selector
- [ ] Validation results displayed
- [ ] Pack detail view shows full JSON
- [ ] Activate version button functional (admin only)
- [ ] Current active version indicator displayed
- [ ] Filters apply correctly
- [ ] Data fetched from `/admin/packs/tenant/{tenant_id}` API
- [ ] Loading and error states handled
- [ ] Unit tests for Tenant Packs components

---

## Component: UI - Playbook Linking (Phase 12 Extension)

### Issue P12-18: Implement Playbook Linking UI
**Labels:** `component:ui:admin`, `phase:12`, `priority:medium`
**Description:**
- Extend Admin Playbooks page (`/admin/playbooks`) with pack linking:
  - Display linked pack information for each playbook
  - Link playbooks to:
    - Tenant
    - Domain
    - Active pack version
  - Prevent activation if pack incompatibility detected
  - Show pack compatibility warnings
- Add playbook linking form:
  - Tenant selector
  - Domain selector
  - Pack version selector (from active config)
  - Link button
- Display compatibility status
- Use existing DataTable, FilterBar components
- Reference: docs/phase12-onboarding-packs-mvp.md Section 6.3

**Dependencies:** P12-13, P11-18

**Acceptance Criteria:**
- [ ] Playbook linking UI added to `/admin/playbooks` page
- [ ] Linked pack information displayed
- [ ] Playbook linking form functional
- [ ] Pack compatibility detection working
- [ ] Activation prevention for incompatible packs
- [ ] Compatibility warnings displayed
- [ ] Data fetched from playbook and pack APIs
- [ ] Loading and error states handled
- [ ] Unit tests for Playbook Linking components

---

## Component: API Integration

### Issue P12-19: Implement Onboarding API Client Functions
**Labels:** `component:ui:api`, `phase:12`, `priority:high`
**Description:**
- Create API client functions in `ui/src/api/onboarding.ts`:
  - Tenant management: `POST /admin/tenants`, `GET /admin/tenants`, `GET /admin/tenants/{tenant_id}`, `PATCH /admin/tenants/{tenant_id}/status`
  - Domain pack import: `POST /admin/packs/domain/import`
  - Tenant pack import: `POST /admin/packs/tenant/import`
  - Pack validation: `POST /admin/packs/validate`
  - Domain pack listing: `GET /admin/packs/domain`, `GET /admin/packs/domain/{domain}/{version}`
  - Tenant pack listing: `GET /admin/packs/tenant/{tenant_id}`, `GET /admin/packs/tenant/{tenant_id}/{version}`
  - Pack activation: `POST /admin/packs/activate`
- Ensure all functions include tenant context (header or query param)
- Use existing HTTP client utility
- Add TypeScript types for all request/response models
- Central error handling (toast notifications)
- Reference: docs/phase12-onboarding-packs-mvp.md Section 5

**Dependencies:** None (can use existing HTTP client from Phase 4)

**Acceptance Criteria:**
- [ ] Onboarding API client file created in `ui/src/api/onboarding.ts`
- [ ] All tenant management functions implemented
- [ ] All pack import functions implemented
- [ ] All pack validation functions implemented
- [ ] All pack listing functions implemented
- [ ] Pack activation function implemented
- [ ] Tenant context included in all requests
- [ ] TypeScript types defined for all models
- [ ] Central error handling functional
- [ ] Unit tests for API client functions

---

## Component: Governance & Audit

### Issue P12-20: Implement Pack Change Audit Logging
**Labels:** `component:audit`, `phase:12`, `priority:high`
**Description:**
- Log all pack operations to audit trail:
  - Pack import events (who/when/what)
  - Pack activation events (who/when/what versions)
  - Pack status changes (who/when/what)
  - Tenant creation events
  - Tenant status changes
- Store audit events in audit_log table or existing audit system
- Include pack version, checksum, and change summary
- Support querying audit trail by tenant, pack, date range
- Reference: docs/phase12-onboarding-packs-mvp.md Section 7

**Dependencies:** P12-10, P12-11, P12-13

**Acceptance Criteria:**
- [ ] Pack import events logged
- [ ] Pack activation events logged
- [ ] Pack status changes logged
- [ ] Tenant creation events logged
- [ ] Tenant status changes logged
- [ ] Audit events include required metadata
- [ ] Audit trail queryable by filters
- [ ] Unit tests for audit logging
- [ ] Integration tests for audit trail

---

### Issue P12-21: Implement Optional Config Change Approval (Toggle)
**Labels:** `component:governance`, `phase:12`, `priority:medium`
**Description:**
- Add optional approval workflow for pack activations:
  - Config change requests create approval requests (if toggle enabled)
  - Approval required before activation
  - Integrate with existing config change governance system (Phase 10)
- Make approval workflow toggleable via feature flag or tenant policy
- If disabled, activation happens immediately
- If enabled, activation requires approval from admin
- Reference: docs/phase12-onboarding-packs-mvp.md Section 7

**Dependencies:** P12-13, P10-11

**Acceptance Criteria:**
- [ ] Approval workflow toggleable
- [ ] Config change requests created when enabled
- [ ] Approval required before activation when enabled
- [ ] Immediate activation when disabled
- [ ] Integration with Phase 10 config change system working
- [ ] Unit tests for approval workflow
- [ ] Integration tests for both modes

---

## Component: Testing & Documentation

### Issue P12-22: Implement Phase 12 Integration Tests
**Labels:** `component:testing`, `phase:12`, `priority:high`
**Description:**
- Write integration tests for Phase 12 components:
  - Tenant creation and lifecycle tests
  - Pack import and validation tests
  - Pack activation flow tests
  - Active configuration loading tests
  - Runtime integration with active config tests
  - Audit trail completeness tests
- Test tenant isolation for all endpoints
- Test RBAC enforcement for admin endpoints
- Test pack validation with invalid packs
- Test activation with non-existent versions
- Achieve >80% code coverage for Phase 12 code
- Reference: docs/phase12-onboarding-packs-mvp.md Section 10

**Dependencies:** P12-1 through P12-21

**Acceptance Criteria:**
- [ ] Tenant lifecycle integration tests passing
- [ ] Pack import/validation integration tests passing
- [ ] Pack activation integration tests passing
- [ ] Active configuration integration tests passing
- [ ] Runtime integration tests passing
- [ ] Audit trail tests passing
- [ ] Tenant isolation tests passing
- [ ] RBAC tests passing
- [ ] Code coverage >80%

---

### Issue P12-23: Update Documentation for Phase 12
**Labels:** `component:documentation`, `phase:12`, `priority:high`
**Description:**
- Update docs/STATE_OF_THE_PLATFORM.md with Phase 12 capabilities
- Create or update docs/tenant-onboarding-guide.md:
  - Tenant creation procedures
  - Pack import procedures
  - Pack validation guide
  - Pack activation procedures
  - Active configuration management
- Create or update docs/pack-management-guide.md:
  - Domain pack structure and format
  - Tenant pack structure and format
  - Versioning best practices
  - Activation workflow
- Document all new API endpoints
- Document all new UI screens
- Reference: docs/phase12-onboarding-packs-mvp.md Section 10

**Dependencies:** All P12 issues

**Acceptance Criteria:**
- [ ] STATE_OF_THE_PLATFORM.md updated
- [ ] tenant-onboarding-guide.md created/updated
- [ ] pack-management-guide.md created/updated
- [ ] All new API endpoints documented
- [ ] All new UI screens documented
- [ ] Demo flow documented (Section 9)

---

## Summary

**Total Issues:** 23
**High Priority:** 20
**Medium Priority:** 3

**Components Covered:**
- Database Models & Migrations (4 issues)
- Repository Layer (4 issues)
- Pack Validation Service (1 issue)
- Backend APIs - Tenant Management (1 issue)
- Backend APIs - Pack Management (3 issues)
- Runtime Integration (1 issue)
- UI - Tenant Management (1 issue)
- UI - Pack Management (2 issues)
- UI - Playbook Linking (1 issue)
- API Integration (1 issue)
- Governance & Audit (2 issues)
- Testing & Documentation (2 issues)

**Implementation Order:**

### Foundation (Week 1)
1. P12-1: Tenants database model
2. P12-2: Domain Packs database model
3. P12-3: Tenant Packs database model
4. P12-4: Active Configuration database model
5. P12-5: Tenant Repository
6. P12-6: Domain Pack Repository
7. P12-7: Tenant Pack Repository
8. P12-8: Active Configuration Repository

### Validation & APIs (Week 2)
9. P12-9: Pack Validation Service
10. P12-10: Tenant Management API
11. P12-11: Pack Import and Validation API
12. P12-12: Pack Listing and Version API
13. P12-13: Pack Activation API

### Runtime & UI (Week 3)
14. P12-14: Runtime Integration
15. P12-19: Onboarding API Client Functions
16. P12-15: Admin Tenants Management UI
17. P12-16: Domain Packs Management UI
18. P12-17: Tenant Packs Management UI

### Extensions & Finalization (Week 4)
19. P12-18: Playbook Linking UI
20. P12-20: Pack Change Audit Logging
21. P12-21: Optional Config Change Approval
22. P12-22: Integration Tests
23. P12-23: Documentation

**Key Dependencies:**
- P12-1 through P12-4 must be completed before repository layer
- P12-5 through P12-8 must be completed before API layer
- P12-9 must be completed before pack import APIs
- P12-14 depends on P12-8 (active config repository)
- UI issues depend on backend APIs being available
- P12-19 must be completed before UI pages
- All UI issues depend on Phase 11 shared components (P11-2, P11-3, P11-4, P11-5)

**Spec References:**
- docs/phase12-onboarding-packs-mvp.md - Phase 12 Tenant & Domain Pack Onboarding MVP specification
- docs/03-data-models-apis.md - Backend API schemas and data models
- docs/10-ui-guidelines.md - UI working principles and tech stack
- Phase 10 config change governance APIs (for optional approval workflow)
- Phase 11 shared UI components (DataTable, FilterBar, ConfirmDialog, CodeViewer)

