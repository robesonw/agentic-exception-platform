Phase 12 — Tenant & Domain Pack Onboarding MVP
1. Purpose

Phase 12 introduces first-class tenant onboarding and configuration lifecycle management for the SentinAI platform.

This phase completes the transition from:

file-based JSON configs

static bootstrap packs

to a governed, UI-driven, persisted, and auditable onboarding system suitable for enterprise SaaS.

After Phase 12, an administrator can:

onboard a new tenant

import and validate Domain Packs & Tenant Packs

version and activate configurations

link playbooks safely

operate fully without filesystem access

2. Scope & Non-Goals
In Scope

Tenant registry & lifecycle

Domain Pack persistence & versioning

Tenant Pack persistence & versioning

Pack validation and activation

UI-based onboarding & management

Auditability of changes

Explicitly Out of Scope (Future Phases)

Full visual pack editors (forms/workflow builders)

Cross-tenant pack promotion UI

Multi-environment promotion (dev → prod)

AI-generated pack authoring

Bulk tenant onboarding

3. Conceptual Model
3.1 Core Entities
Entity	Description
Tenant	A customer / client organization
Domain Pack	Domain-specific logic (classification rules, schemas, policies)
Tenant Pack	Tenant overrides & customizations
Active Configuration	Mapping of tenant → pack versions
Playbooks	Action workflows bound to tenant + domain
Config Change	Governed change request (optional approval)
4. Data Model (MVP)
4.1 Tenants

Table: tenants

tenant_id (PK)
name
status (ACTIVE | SUSPENDED)
created_at
created_by

4.2 Domain Packs

Table: domain_packs

id (PK)
domain
version
content_json
checksum
status (DRAFT | ACTIVE | DEPRECATED)
created_at
created_by

4.3 Tenant Packs

Table: tenant_packs

id (PK)
tenant_id (FK)
version
content_json
checksum
status (DRAFT | ACTIVE | DEPRECATED)
created_at
created_by

4.4 Active Configuration

Table: tenant_active_config

tenant_id (PK)
active_domain_pack_version
active_tenant_pack_version
activated_at
activated_by

5. Backend APIs (MVP)
5.1 Tenant Management
POST   /admin/tenants
GET    /admin/tenants
GET    /admin/tenants/{tenant_id}
PATCH  /admin/tenants/{tenant_id}/status

5.2 Pack Import & Validation
POST /admin/packs/domain/import
POST /admin/packs/tenant/import
POST /admin/packs/validate


Validation includes:

schema correctness

required fields

unsupported keys

cross-reference checks (playbooks/tools)

5.3 Pack Listing & Versions
GET /admin/packs/domain
GET /admin/packs/domain/{domain}/{version}

GET /admin/packs/tenant/{tenant_id}
GET /admin/packs/tenant/{tenant_id}/{version}

5.4 Activation
POST /admin/packs/activate


Payload:

{
  "tenant_id": "TENANT_FINANCE_001",
  "domain_pack_version": "v3.2",
  "tenant_pack_version": "v1.4"
}

6. UI Screens (Admin)
6.1 Admin → Tenants

List tenants

Create tenant

Enable / suspend tenant

View active configuration

6.2 Admin → Packs
Domain Packs tab

List by domain

Upload/import JSON

Validate pack

View versions

Activate version

Tenant Packs tab

Filter by tenant

Upload/import JSON

Validate pack

View versions

Activate version

6.3 Admin → Playbooks (Phase 12 extension)

Link playbooks to:

tenant

domain

active pack version

Prevent activation if pack incompatibility detected

7. Governance & Audit
MVP Level (Required)

All changes logged (who/when/what)

Activation events tracked

Validation errors stored

Optional (Toggle)

Config changes create approval requests

Approval required before activation

8. UX & Safety Rules

No direct JSON overwrite of active config

Activation always explicit

Confirm dialogs for activation

Read-only views for non-admins

Clear indication of ACTIVE vs DRAFT versions

9. Demo Flow (Marketing-Ready)

Create a new tenant from UI

Import a Domain Pack (Finance)

Validate the pack (show validation results)

Import a Tenant Pack override

Activate both packs

Link a playbook

Navigate to Ops → show live behavior using the active config

“No filesystem. No redeploy. Fully governed.”

10. Completion Criteria

Phase 12 is complete when:

Tenants can be onboarded via UI

Domain & Tenant Packs are imported, validated, versioned, and persisted

Active configuration is stored and used by runtime

Admin UI fully replaces JSON file management

All actions are auditable

System operates end-to-end without manual config edits

11. What This Unlocks Next

Phase 13: Visual Pack & Playbook Builder

Phase 14: AI-assisted onboarding

Phase 15: Multi-env promotion (dev/stage/prod)

Phase 16: Marketplace / Pack sharing