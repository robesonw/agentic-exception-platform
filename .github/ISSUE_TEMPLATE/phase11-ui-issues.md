# Phase 11 Admin & Ops UI MVP - GitHub Issues Checklist

## Component: Navigation & Access Control

### Issue P11-1: Implement Ops and Admin Navigation with Feature Flags
**Labels:** `component:ui:navigation`, `phase:11`, `priority:high`
**Description:**
- Add Ops and Admin sections to left navigation sidebar
- Implement feature flag gating:
  - `OPS_ENABLED` environment variable controls Ops menu visibility
  - `ADMIN_ENABLED` environment variable controls Admin menu visibility
- Add route protection for Ops routes (`/ops/*`)
- Add route protection for Admin routes (`/admin/*`)
- Show "Not authorized" screen when accessing protected routes without access
- If RBAC exists, enforce role-based restrictions:
  - `viewer` → read-only access
  - `operator` → safe operational actions (retry/replay)
  - `admin` → full access including config changes, pack activation, rate limits
- Reference: docs/phase11-admin-ui-mvp.md Section 4.1

**Dependencies:** None (foundational)

**Acceptance Criteria:**
- [ ] Ops navigation section added to sidebar
- [ ] Admin navigation section added to sidebar
- [ ] Feature flags control menu visibility correctly
- [ ] Route protection prevents unauthorized access
- [ ] "Not authorized" screen displays for unauthorized access attempts
- [ ] RBAC restrictions enforced if RBAC exists
- [ ] Navigation links route to correct pages
- [ ] Unit tests for navigation and access control

---

## Component: Shared UI Components

### Issue P11-2: Implement Enhanced DataTable Component with Export
**Labels:** `component:ui:components`, `phase:11`, `priority:high`
**Description:**
- Enhance existing DataTable component or create new one if needed:
  - Sorting on all sortable columns with visual indicators
  - Pagination with page size selector and total count
  - Column visibility toggle (optional)
  - Export button (CSV/JSON) for table data
  - Consistent empty state (no data message)
  - Consistent loading skeleton state
  - Consistent error state display
- Ensure DataTable is reusable across all Ops/Admin pages
- Use MUI Table components for consistency
- Reference: docs/phase11-admin-ui-mvp.md Section 4.2

**Dependencies:** None (can use existing DataTable from Phase 4)

**Acceptance Criteria:**
- [ ] DataTable component supports sorting with visual indicators
- [ ] Pagination functional with page size selector
- [ ] Column visibility toggle implemented (if applicable)
- [ ] Export button functional (CSV/JSON)
- [ ] Empty state displays consistently
- [ ] Loading skeleton state displays consistently
- [ ] Error state displays consistently
- [ ] Component reusable across all pages
- [ ] Unit tests for DataTable component

---

### Issue P11-3: Implement FilterBar Components for Ops/Admin Pages
**Labels:** `component:ui:components`, `phase:11`, `priority:high`
**Description:**
- Create or enhance FilterBar components for common filter patterns:
  - Date range picker (from/to dates)
  - Status dropdown filter
  - Severity dropdown filter
  - System/source text filter
  - Tenant selector (admin only)
  - Domain selector
- Support filter state management and URL query param synchronization
- Emit filter change events for parent components
- Use MUI components (TextField, Select, DatePicker)
- Reference: docs/phase11-admin-ui-mvp.md Section 4.2

**Dependencies:** P11-2

**Acceptance Criteria:**
- [ ] Date range picker functional
- [ ] Status dropdown filter functional
- [ ] Severity dropdown filter functional
- [ ] System/source text filter functional
- [ ] Tenant selector functional (admin only)
- [ ] Domain selector functional
- [ ] Filter state syncs with URL query params
- [ ] Filter change events emitted correctly
- [ ] Filters reset properly
- [ ] Unit tests for FilterBar components

---

### Issue P11-4: Implement ConfirmDialog Component for Destructive Actions
**Labels:** `component:ui:components`, `phase:11`, `priority:high`
**Description:**
- Create ConfirmDialog component using MUI Dialog
- Support customizable title, message, and action button labels
- Support destructive action styling (red/warning colors)
- Require explicit confirmation (no accidental clicks)
- Show loading state during action execution
- Handle success and error states
- Reference: docs/phase11-admin-ui-mvp.md Section 4.2

**Dependencies:** None

**Acceptance Criteria:**
- [ ] ConfirmDialog component created with MUI Dialog
- [ ] Customizable title, message, and button labels
- [ ] Destructive action styling applied
- [ ] Explicit confirmation required
- [ ] Loading state shows during action
- [ ] Success/error states handled
- [ ] Component reusable across all pages
- [ ] Unit tests for ConfirmDialog component

---

### Issue P11-5: Implement CodeViewer Component for JSON Payloads
**Labels:** `component:ui:components`, `phase:11`, `priority:medium`
**Description:**
- Create CodeViewer component for displaying JSON payloads:
  - Syntax highlighting for JSON
  - Formatted/pretty-printed JSON display
  - Copy to clipboard button
  - Expand/collapse for large payloads
  - Read-only display
- Use library like `react-syntax-highlighter` or MUI-based solution
- Support DLQ detail view, config diff views
- Reference: docs/phase11-admin-ui-mvp.md Section 4.2

**Dependencies:** None

**Acceptance Criteria:**
- [ ] CodeViewer component created
- [ ] JSON syntax highlighting functional
- [ ] Pretty-printed JSON display
- [ ] Copy to clipboard button functional
- [ ] Expand/collapse for large payloads
- [ ] Read-only display enforced
- [ ] Component reusable across pages
- [ ] Unit tests for CodeViewer component

---

## Component: Ops UI - Batch 1

### Issue P11-6: Implement Ops Overview Dashboard
**Labels:** `component:ui:ops`, `phase:11`, `priority:high`
**Description:**
- Create Ops Overview page at `/ops` route
- Implement "at-a-glance" widget cards:
  - Worker health summary (healthy/degraded/down counts)
  - Throughput widget (events/min)
  - Error rate widget
  - SLA breached count + at-risk count
  - DLQ size widget
  - Alerts fired count (last 24h)
  - Report jobs summary (queued/running/completed/failed)
- Each widget has "View details" link to relevant page
- Use TanStack Query for data fetching
- Auto-refresh data (configurable interval, default: 30s)
- Handle loading and error states
- Reference: docs/phase11-admin-ui-mvp.md Section 4.3

**Dependencies:** P11-1, P11-2

**Acceptance Criteria:**
- [ ] Ops Overview page created at `/ops` route
- [ ] All widget cards displaying correct data
- [ ] "View details" links navigate to correct pages
- [ ] Data fetched from Phase 10 backend APIs
- [ ] Auto-refresh functional
- [ ] Loading states handled
- [ ] Error states handled
- [ ] Page loads within 2-3 seconds on local dev
- [ ] Unit tests for Ops Overview components

---

### Issue P11-7: Implement Workers Dashboard
**Labels:** `component:ui:ops`, `phase:11`, `priority:high`
**Description:**
- Create Workers Dashboard page at `/ops/workers` route
- Display worker list table with columns:
  - Worker type
  - Instance ID
  - Status (healthy/degraded/unhealthy) with color coding
  - Last heartbeat timestamp
  - Version
  - Host/pod identifier
  - Throughput (events/sec)
  - Latency (p50, p95, p99)
  - Error count
- Add refresh button to re-fetch data
- Highlight unhealthy workers with warning styling
- Show last error reason if worker is unhealthy
- Optional: Add sparkline charts if backend provides time-series data
- Use DataTable component for consistency
- Reference: docs/phase11-admin-ui-mvp.md Section 4.4

**Dependencies:** P11-6, P11-2

**Acceptance Criteria:**
- [ ] Workers Dashboard page created at `/ops/workers` route
- [ ] Worker list table displays all columns
- [ ] Status color coding functional
- [ ] Refresh button re-fetches data
- [ ] Unhealthy workers highlighted
- [ ] Last error reason displayed for unhealthy workers
- [ ] Data fetched from `/ops/workers/health` and `/ops/workers/throughput` APIs
- [ ] Loading and error states handled
- [ ] Unit tests for Workers Dashboard components

---

### Issue P11-8: Implement SLA Dashboard
**Labels:** `component:ui:ops`, `phase:11`, `priority:high`
**Description:**
- Create SLA Dashboard page at `/ops/sla` route
- Display SLA compliance percentage (prominent card)
- Display breached exceptions table:
  - Exception ID (link to detail page)
  - Tenant ID
  - Domain
  - Exception Type
  - Severity
  - Breach timestamp
  - SLA deadline
- Display at-risk exceptions table (approaching deadline):
  - Exception ID (link to detail page)
  - Tenant ID
  - Domain
  - Exception Type
  - Severity
  - Time until deadline
- Optional: Resolution time distribution chart
- Add filters: tenant, domain, exception type, date range
- Clearly show SLA time windows
- Use DataTable and FilterBar components
- Reference: docs/phase11-admin-ui-mvp.md Section 4.5

**Dependencies:** P11-6, P11-2, P11-3

**Acceptance Criteria:**
- [ ] SLA Dashboard page created at `/ops/sla` route
- [ ] SLA compliance percentage displayed
- [ ] Breached exceptions table displays correctly
- [ ] At-risk exceptions table displays correctly
- [ ] Exception ID links navigate to detail page
- [ ] Filters apply correctly
- [ ] SLA time windows clearly shown
- [ ] Data fetched from `/ops/sla/*` APIs
- [ ] Loading and error states handled
- [ ] Unit tests for SLA Dashboard components

---

### Issue P11-9: Implement DLQ Management UI
**Labels:** `component:ui:ops`, `phase:11`, `priority:high`
**Description:**
- Create DLQ Management page at `/ops/dlq` route
- Display DLQ message list table with columns:
  - DLQ entry ID
  - Tenant ID
  - Topic/event type
  - Failure reason
  - Status (pending, retrying, discarded, succeeded)
  - Retry count
  - Timestamp
- Add filters: tenant, topic/event_type, reason, status, time range
- Implement DLQ detail modal/drawer:
  - Full message payload (use CodeViewer)
  - Correlation ID / Exception ID
  - Error stack trace (if present)
  - Retry history
- Implement actions (role-gated):
  - Retry single entry button (with ConfirmDialog)
  - Batch retry checkbox selection + batch retry button
  - Discard entry button (with ConfirmDialog)
- Show retry in progress state
- Use DataTable, FilterBar, ConfirmDialog, CodeViewer components
- Reference: docs/phase11-admin-ui-mvp.md Section 4.6

**Dependencies:** P11-6, P11-2, P11-3, P11-4, P11-5

**Acceptance Criteria:**
- [ ] DLQ Management page created at `/ops/dlq` route
- [ ] DLQ list table displays all columns
- [ ] Filters apply correctly
- [ ] DLQ detail modal shows full payload
- [ ] CodeViewer displays JSON payload correctly
- [ ] Single retry functional with confirmation
- [ ] Batch retry functional with confirmation
- [ ] Discard functional with confirmation
- [ ] Retry progress state shown
- [ ] Role gating enforced for actions
- [ ] Data fetched from `/ops/dlq/*` APIs
- [ ] Loading and error states handled
- [ ] Unit tests for DLQ Management components

---

### Issue P11-10: Implement Alerts Configuration UI
**Labels:** `component:ui:ops`, `phase:11`, `priority:high`
**Description:**
- Create Alerts Configuration page at `/ops/alerts` route
- Display alert configs list table:
  - Alert name
  - Alert type (SLA_BREACH, DLQ_GROWTH, etc.)
  - Enabled status (toggle)
  - Threshold value
  - Notification channels
  - Created/updated timestamp
- Implement create/edit alert form:
  - Name (required)
  - Alert type selector (required)
  - Severity selector
  - Condition template/editor
  - Threshold value input
  - Notification channels selector (multi-select)
  - Enabled toggle
- Display notification channels table:
  - Channel name
  - Channel type (webhook, email)
  - Verified status
  - Actions (edit, delete, test)
- Implement create/edit channel form:
  - Channel name
  - Channel type selector
  - Webhook URL or email address
  - Test notification button
- Client-side validation for required fields
- Use DataTable, FilterBar components
- Reference: docs/phase11-admin-ui-mvp.md Section 4.7

**Dependencies:** P11-6, P11-2, P11-3

**Acceptance Criteria:**
- [ ] Alerts Configuration page created at `/ops/alerts` route
- [ ] Alert configs list table displays correctly
- [ ] Create/edit alert form functional
- [ ] Client-side validation working
- [ ] Notification channels table displays correctly
- [ ] Create/edit channel form functional
- [ ] Test notification button functional
- [ ] Data fetched from `/alerts/config` and `/alerts/channels` APIs
- [ ] Create/update operations functional
- [ ] Loading and error states handled
- [ ] Unit tests for Alerts Configuration components

---

### Issue P11-11: Implement Alerts History UI
**Labels:** `component:ui:ops`, `phase:11`, `priority:high`
**Description:**
- Create Alerts History page at `/ops/alerts/history` route
- Display alerts history table with columns:
  - Alert ID
  - Alert type
  - Severity
  - Status (fired, acknowledged, resolved)
  - Triggered timestamp
  - Tenant ID
  - Domain
  - Payload excerpt
- Add filters: time range, severity, status, alert type
- Implement alert detail modal:
  - Full alert details
  - Condition that fired
  - Notification delivery status
  - Acknowledge button (if not acknowledged)
  - Resolve button (if not resolved)
- Support pagination
- Use DataTable, FilterBar components
- Reference: docs/phase11-admin-ui-mvp.md Section 4.7

**Dependencies:** P11-10, P11-2, P11-3

**Acceptance Criteria:**
- [ ] Alerts History page created at `/ops/alerts/history` route
- [ ] Alerts history table displays all columns
- [ ] Filters apply correctly
- [ ] Alert detail modal shows full details
- [ ] Acknowledge button functional
- [ ] Resolve button functional
- [ ] Pagination works correctly
- [ ] Data fetched from `/alerts/history` API
- [ ] Loading and error states handled
- [ ] Unit tests for Alerts History components

---

### Issue P11-12: Implement Audit Reports UI
**Labels:** `component:ui:ops`, `phase:11`, `priority:high`
**Description:**
- Create Audit Reports page at `/ops/reports` route
- Implement report request form:
  - Report type selector (Exception Activity, Tool Execution, Policy Decisions, Config Changes, SLA Compliance)
  - Tenant selector (admin only)
  - Domain selector
  - Date range picker
  - Format selector (CSV, JSON)
  - Generate report button
- Display generated reports table:
  - Report ID
  - Report type
  - Status (queued, generating, completed, failed)
  - Requested timestamp
  - Completed timestamp
  - Download link (if completed)
  - Expires timestamp
  - Actions (download, delete)
- Show progress indicator for generating reports
- Handle download of completed reports
- Display error reason for failed reports
- Use DataTable, FilterBar components
- Reference: docs/phase11-admin-ui-mvp.md Section 4.8

**Dependencies:** P11-6, P11-2, P11-3

**Acceptance Criteria:**
- [ ] Audit Reports page created at `/ops/reports` route
- [ ] Report request form functional
- [ ] Report type selector working
- [ ] Date range picker working
- [ ] Generate report button triggers API call
- [ ] Generated reports table displays correctly
- [ ] Progress indicator shows for generating reports
- [ ] Download link functional for completed reports
- [ ] Error reason displayed for failed reports
- [ ] Data fetched from `/audit/reports` API
- [ ] Loading and error states handled
- [ ] Unit tests for Audit Reports components

---

## Component: Ops UI - Batch 2

### Issue P11-13: Implement Usage Metering UI
**Labels:** `component:ui:ops`, `phase:11`, `priority:high`
**Description:**
- Create Usage Metering page at `/ops/usage` route
- Display usage summary cards:
  - API calls (today/period)
  - Exceptions ingested (today/period)
  - Tool executions (today/period)
  - LLM calls (today/period)
- Display usage breakdown table:
  - Resource type
  - Count
  - Date/period
  - Tenant (if admin view)
- Add filters: tenant (admin only), date range, resource type
- Display usage trend chart (optional, if backend provides)
- Add export button (CSV/JSON) if backend supports export
- Support time period selector (day, week, month)
- Use DataTable, FilterBar components
- Reference: docs/phase11-admin-ui-mvp.md Section 4.9

**Dependencies:** P11-6, P11-2, P11-3

**Acceptance Criteria:**
- [ ] Usage Metering page created at `/ops/usage` route
- [ ] Usage summary cards display correctly
- [ ] Usage breakdown table displays correctly
- [ ] Filters apply correctly
- [ ] Date range selection clear and functional
- [ ] Export button functional (if backend supports)
- [ ] Time period selector working
- [ ] Data fetched from `/usage/*` APIs
- [ ] Data displayed is not mocked
- [ ] Loading and error states handled
- [ ] Unit tests for Usage Metering components

---

### Issue P11-14: Implement Rate Limits UI
**Labels:** `component:ui:ops`, `phase:11`, `priority:high`
**Description:**
- Create Rate Limits page at `/ops/rate-limits` route
- Display rate limit configuration table:
  - Tenant ID
  - Limit type (api_requests, events_ingested, tool_executions, report_generations)
  - Limit value
  - Window (seconds)
  - Current utilization (if available)
  - Status (enabled/disabled)
- Add filters: tenant, limit type
- For admin users, implement edit actions:
  - Update limit value (with ConfirmDialog)
  - Enable/disable limiting (with ConfirmDialog)
- For non-admin users, show view-only mode
- Display current utilization vs limit (progress bar or percentage)
- Use DataTable, FilterBar, ConfirmDialog components
- Reference: docs/phase11-admin-ui-mvp.md Section 4.10

**Dependencies:** P11-6, P11-2, P11-3, P11-4

**Acceptance Criteria:**
- [ ] Rate Limits page created at `/ops/rate-limits` route
- [ ] Rate limit configuration table displays correctly
- [ ] Current utilization displayed (if available)
- [ ] Non-admin users see view-only mode
- [ ] Admin users can update limits with confirmation
- [ ] Admin users can enable/disable with confirmation
- [ ] Filters apply correctly
- [ ] Data fetched from `/admin/rate-limits/*` APIs
- [ ] Loading and error states handled
- [ ] Unit tests for Rate Limits components

---

## Component: Admin UI - Batch 2

### Issue P11-15: Implement Admin Landing Page
**Labels:** `component:ui:admin`, `phase:11`, `priority:high`
**Description:**
- Create Admin landing page at `/admin` route
- Display quick links cards:
  - Config Changes (pending count)
  - Packs Management
  - Playbooks Management
  - Tools Management
- Display pending approvals summary:
  - Pending config changes count
  - Link to config changes page
- Display recent activity (optional):
  - Recent config changes
  - Recent pack activations
- Use MUI Grid/Card components for layout
- Reference: docs/phase11-admin-ui-mvp.md Section 3.2

**Dependencies:** P11-1

**Acceptance Criteria:**
- [ ] Admin landing page created at `/admin` route
- [ ] Quick links cards display correctly
- [ ] Pending approvals summary displays
- [ ] Links navigate to correct pages
- [ ] Data fetched from backend APIs
- [ ] Loading and error states handled
- [ ] Unit tests for Admin Landing components

---

### Issue P11-16: Implement Config Change Governance UI
**Labels:** `component:ui:admin`, `phase:11`, `priority:high`
**Description:**
- Create Config Changes page at `/admin/config-changes` route
- Display pending changes table:
  - Change ID
  - Change type (domain_pack, policy_pack, tool, playbook)
  - Resource ID
  - Requested by
  - Requested timestamp
  - Status (pending, approved, rejected, applied)
- Add filters: status, change type, date range
- Implement change detail view:
  - Config diff (before/after) using CodeViewer or diff component
  - Requestor information
  - Timestamp
  - Review comments
  - Diff summary (additions, deletions, changes)
- Implement actions (admin only, with ConfirmDialog):
  - Approve button
  - Reject button (with comment input)
- Display change history table (all statuses)
- Update list immediately after approve/reject
- Use DataTable, FilterBar, ConfirmDialog, CodeViewer components
- Reference: docs/phase11-admin-ui-mvp.md Section 4.11

**Dependencies:** P11-15, P11-2, P11-3, P11-4, P11-5

**Acceptance Criteria:**
- [ ] Config Changes page created at `/admin/config-changes` route
- [ ] Pending changes table displays correctly
- [ ] Filters apply correctly
- [ ] Change detail view shows config diff
- [ ] Diff highlighting works correctly
- [ ] Approve button functional with confirmation
- [ ] Reject button functional with comment
- [ ] Change history table displays correctly
- [ ] List updates immediately after approve/reject
- [ ] Unauthorized role cannot approve/reject
- [ ] Data fetched from `/admin/config-changes` API
- [ ] Loading and error states handled
- [ ] Unit tests for Config Changes components

---

### Issue P11-17: Implement Packs Management UI
**Labels:** `component:ui:admin`, `phase:11`, `priority:high`
**Description:**
- Create Packs Management page at `/admin/packs` route
- Implement tab selector: Domain Packs / Tenant Packs
- Domain Packs view:
  - List table: Pack ID, Name, Version, Domain, Timestamp
  - Filters: domain, version
  - Detail view: Full pack JSON (use CodeViewer)
  - Activate version button (admin only, with ConfirmDialog)
- Tenant Packs view:
  - List table: Pack ID, Name, Version, Tenant ID, Domain, Timestamp
  - Filters: tenant, domain, version
  - Detail view: Full pack JSON (use CodeViewer)
  - Activate version button (admin only, with ConfirmDialog)
- Optional: Import/upload pack JSON button (if backend supports; otherwise show "coming soon" message)
- Show current active version indicator
- Use DataTable, FilterBar, ConfirmDialog, CodeViewer components
- Reference: docs/phase11-admin-ui-mvp.md Section 4.12

**Dependencies:** P11-15, P11-2, P11-3, P11-4, P11-5

**Acceptance Criteria:**
- [ ] Packs Management page created at `/admin/packs` route
- [ ] Tab selector functional (Domain Packs / Tenant Packs)
- [ ] Domain Packs list displays correctly
- [ ] Tenant Packs list displays correctly
- [ ] Filters apply correctly
- [ ] Detail view shows full pack JSON
- [ ] Activate version button functional (admin only)
- [ ] Current active version indicator displayed
- [ ] Activation updates UI immediately
- [ ] Import button shows "coming soon" if backend doesn't support
- [ ] Data fetched from `/admin/config/domain-packs` and `/admin/config/tenant-policies` APIs
- [ ] Loading and error states handled
- [ ] Unit tests for Packs Management components

---

### Issue P11-18: Implement Playbooks Management UI
**Labels:** `component:ui:admin`, `phase:11`, `priority:high`
**Description:**
- Create Playbooks Management page at `/admin/playbooks` route
- Display playbooks list table:
  - Playbook ID
  - Name
  - Version
  - Tenant ID
  - Domain
  - Match rules summary
  - Active status (enabled/disabled)
  - Created/updated timestamp
- Add filters: tenant, domain, active status
- Implement playbook detail view:
  - Match rules (full JSON or formatted display)
  - Steps (list with details)
  - Referenced tools (list)
  - Version information
- Implement actions (admin only, with ConfirmDialog):
  - Activate/deactivate toggle button
- Show confirmation before activation/deactivation
- Use DataTable, FilterBar, ConfirmDialog, CodeViewer components
- Reference: docs/phase11-admin-ui-mvp.md Section 4.13

**Dependencies:** P11-15, P11-2, P11-3, P11-4, P11-5

**Acceptance Criteria:**
- [ ] Playbooks Management page created at `/admin/playbooks` route
- [ ] Playbooks list table displays correctly
- [ ] Filters apply correctly
- [ ] Playbook detail view shows match rules, steps, tools
- [ ] Activate/deactivate toggle functional (admin only)
- [ ] Confirmation required before activation/deactivation
- [ ] Status updates immediately after toggle
- [ ] Data fetched from `/admin/config/playbooks` API
- [ ] Loading and error states handled
- [ ] Unit tests for Playbooks Management components

---

### Issue P11-19: Implement Tools Management UI
**Labels:** `component:ui:admin`, `phase:11`, `priority:high`
**Description:**
- Create Tools Management page at `/admin/tools` route
- Display tool registry list table:
  - Tool ID
  - Name
  - Description
  - Provider
  - Schema (summary or link to detail)
  - Allowed tenants (list or count)
  - Enabled status per tenant (if applicable)
- Add filters: provider, enabled status
- Implement tool detail view:
  - Full tool schema (use CodeViewer)
  - Provider information
  - Allowed tenants list
  - Recent executions link (if available)
- Implement actions (admin only, with ConfirmDialog):
  - Enable/disable tool for tenant
- Show recent tool executions (optional link to existing views)
- Use DataTable, FilterBar, ConfirmDialog, CodeViewer components
- Reference: docs/phase11-admin-ui-mvp.md Section 4.14

**Dependencies:** P11-15, P11-2, P11-3, P11-4, P11-5

**Acceptance Criteria:**
- [ ] Tools Management page created at `/admin/tools` route
- [ ] Tool registry list table displays correctly
- [ ] Filters apply correctly
- [ ] Tool detail view shows full schema
- [ ] Enable/disable for tenant functional (admin only)
- [ ] Recent executions link works (if available)
- [ ] Data fetched from tool registry APIs
- [ ] Loading and error states handled
- [ ] Unit tests for Tools Management components

---

## Component: API Integration

### Issue P11-20: Implement Ops API Client Functions
**Labels:** `component:ui:api`, `phase:11`, `priority:high`
**Description:**
- Create API client functions in `ui/src/api/ops.ts`:
  - Worker health: `GET /ops/workers/health`
  - Worker throughput: `GET /ops/workers/throughput`
  - SLA compliance: `GET /ops/sla/compliance`
  - SLA breaches: `GET /ops/sla/breaches`
  - SLA at-risk: `GET /ops/sla/at-risk`
  - DLQ list: `GET /ops/dlq`
  - DLQ detail: `GET /ops/dlq/{id}`
  - DLQ retry: `POST /ops/dlq/{id}/retry`
  - DLQ batch retry: `POST /ops/dlq/retry-batch`
  - DLQ discard: `POST /ops/dlq/{id}/discard`
  - Alert configs: `GET /alerts/config`, `POST /alerts/config`, `PUT /alerts/config/{id}`, `DELETE /alerts/config/{id}`
  - Alert channels: `GET /alerts/channels`, `POST /alerts/channels`, `POST /alerts/channels/{id}/verify`, `DELETE /alerts/channels/{id}`
  - Alert history: `GET /alerts/history`, `POST /alerts/history/{id}/acknowledge`, `POST /alerts/history/{id}/resolve`
  - Audit reports: `POST /audit/reports`, `GET /audit/reports/{id}`, `GET /audit/reports`
  - Usage: `GET /usage/summary`, `GET /usage/details`, `GET /usage/export`
  - Rate limits: `GET /admin/rate-limits/{tenant_id}`, `PUT /admin/rate-limits/{tenant_id}`, `GET /admin/rate-limits/{tenant_id}/usage`
- Ensure all functions include tenant context (header or query param)
- Use existing HTTP client utility
- Add TypeScript types for all request/response models
- Central error handling (toast notifications)
- Reference: docs/phase11-admin-ui-mvp.md Section 5

**Dependencies:** None (can use existing HTTP client from Phase 4)

**Acceptance Criteria:**
- [ ] Ops API client file created in `ui/src/api/ops.ts`
- [ ] All worker health/throughput functions implemented
- [ ] All SLA functions implemented
- [ ] All DLQ functions implemented
- [ ] All alert functions implemented
- [ ] All audit report functions implemented
- [ ] All usage functions implemented
- [ ] All rate limit functions implemented
- [ ] Tenant context included in all requests
- [ ] TypeScript types defined for all models
- [ ] Central error handling functional
- [ ] Unit tests for API client functions

---

### Issue P11-21: Implement Admin API Client Functions
**Labels:** `component:ui:api`, `phase:11`, `priority:high`
**Description:**
- Create API client functions in `ui/src/api/admin.ts`:
  - Config changes: `GET /admin/config-changes`, `GET /admin/config-changes/{id}`, `POST /admin/config-changes/{id}/approve`, `POST /admin/config-changes/{id}/reject`, `GET /admin/config-changes/{id}/diff`
  - Domain packs: `GET /admin/config/domain-packs`, `GET /admin/config/domain-packs/{id}`
  - Tenant packs: `GET /admin/config/tenant-policies`, `GET /admin/config/tenant-policies/{id}`
  - Playbooks: `GET /admin/config/playbooks`, `GET /admin/config/playbooks/{id}`
  - Tool registry: Tool registry endpoints (as per existing implementation)
- Ensure all functions include tenant context (header or query param)
- Use existing HTTP client utility
- Add TypeScript types for all request/response models
- Central error handling (toast notifications)
- Reference: docs/phase11-admin-ui-mvp.md Section 5

**Dependencies:** None (can use existing HTTP client from Phase 4)

**Acceptance Criteria:**
- [ ] Admin API client file created in `ui/src/api/admin.ts`
- [ ] All config change functions implemented
- [ ] All domain pack functions implemented
- [ ] All tenant pack functions implemented
- [ ] All playbook functions implemented
- [ ] All tool registry functions implemented
- [ ] Tenant context included in all requests
- [ ] TypeScript types defined for all models
- [ ] Central error handling functional
- [ ] Unit tests for API client functions

---

## Component: Testing & Documentation

### Issue P11-22: Implement Phase 11 UI Integration Tests
**Labels:** `component:testing`, `phase:11`, `priority:high`
**Description:**
- Write integration tests for Phase 11 UI components:
  - Navigation and access control tests
  - Ops pages load with real data
  - Admin pages load with real data
  - Filters work and update queries
  - Error states render properly
  - Confirm dialogs prevent accidental actions
  - Download report works
  - Tenant selector updates all pages
  - Route protection tests
  - RBAC enforcement tests (if applicable)
- Test API client error handling
- Test admin pages hidden when flags off
- Achieve >80% code coverage for Phase 11 UI code
- Reference: docs/phase11-admin-ui-mvp.md Section 9

**Dependencies:** P11-1 through P11-21

**Acceptance Criteria:**
- [ ] Navigation and access control tests passing
- [ ] Ops pages integration tests passing
- [ ] Admin pages integration tests passing
- [ ] Filter functionality tests passing
- [ ] Error state tests passing
- [ ] Confirm dialog tests passing
- [ ] Download functionality tests passing
- [ ] Tenant context tests passing
- [ ] Route protection tests passing
- [ ] RBAC tests passing (if applicable)
- [ ] Code coverage >80%

---

### Issue P11-23: Update Documentation for Phase 11
**Labels:** `component:documentation`, `phase:11`, `priority:high`
**Description:**
- Update docs/STATE_OF_THE_PLATFORM.md with Phase 11 capabilities
- Update docs/10-ui-guidelines.md if new patterns introduced
- Create or update docs/ops-ui-guide.md:
  - Ops dashboard usage
  - DLQ management procedures
  - Alert configuration guide
  - Report generation guide
- Create or update docs/admin-ui-guide.md:
  - Config change approval workflow
  - Pack management procedures
  - Playbook management procedures
  - Tool management procedures
- Document feature flags (OPS_ENABLED, ADMIN_ENABLED)
- Document all new routes and pages
- Reference: docs/phase11-admin-ui-mvp.md Section 10

**Dependencies:** All P11 issues

**Acceptance Criteria:**
- [ ] STATE_OF_THE_PLATFORM.md updated
- [ ] 10-ui-guidelines.md updated if needed
- [ ] ops-ui-guide.md created/updated
- [ ] admin-ui-guide.md created/updated
- [ ] Feature flags documented
- [ ] All new routes documented
- [ ] All new pages documented

---

## Summary

**Total Issues:** 23
**High Priority:** 22
**Medium Priority:** 1

**Components Covered:**
- Navigation & Access Control (1 issue)
- Shared UI Components (4 issues)
- Ops UI - Batch 1 (7 issues)
- Ops UI - Batch 2 (2 issues)
- Admin UI - Batch 2 (5 issues)
- API Integration (2 issues)
- Testing & Documentation (2 issues)

**Implementation Order:**

### Batch 1 — Ops UI (Read-only dashboards + DLQ + Alerts + Reports)
1. P11-1: Navigation & Access Control
2. P11-2: Enhanced DataTable Component
3. P11-3: FilterBar Components
4. P11-4: ConfirmDialog Component
5. P11-5: CodeViewer Component
6. P11-6: Ops Overview Dashboard
7. P11-7: Workers Dashboard
8. P11-8: SLA Dashboard
9. P11-9: DLQ Management UI
10. P11-10: Alerts Configuration UI
11. P11-11: Alerts History UI
12. P11-12: Audit Reports UI
13. P11-20: Ops API Client Functions

### Batch 2 — Admin UI + Remaining Ops (Usage/Rate Limits) + Placeholder Completion
14. P11-13: Usage Metering UI
15. P11-14: Rate Limits UI
16. P11-15: Admin Landing Page
17. P11-16: Config Change Governance UI
18. P11-17: Packs Management UI
19. P11-18: Playbooks Management UI
20. P11-19: Tools Management UI
21. P11-21: Admin API Client Functions

### Finalization
22. P11-22: Integration Tests
23. P11-23: Documentation

**Key Dependencies:**
- P11-1 through P11-5 must be completed before Batch 1 pages
- P11-20 must be completed before Batch 1 pages (API integration)
- P11-21 must be completed before Batch 2 Admin pages (API integration)
- All UI issues depend on Phase 10 backend APIs being available

**Spec References:**
- docs/phase11-admin-ui-mvp.md - Phase 11 Admin & Ops UI MVP specification
- docs/10-ui-guidelines.md - UI working principles and tech stack
- docs/03-data-models-apis.md - Backend API schemas and data models
- Phase 10 backend API routes: `/ops/*`, `/admin/*`, `/usage/*`, `/rate-limits/*`, `/audit-reports/*`, `/config-governance/*`

