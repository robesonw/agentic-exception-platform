# Phase 11 — Admin & Ops UI MVP (SentinAI)

## 1. Purpose
Phase 11 delivers the **enterprise-grade Admin & Ops UI** that fully represents the capabilities already implemented in the backend (Phases 1–10), especially Phase 10 **Ops & Governance** services. The goal is to remove remaining UI placeholders and provide operational dashboards and admin workflows that are **safe, tenant-aware, and governed**.

This phase is **UI-first**: **no backend behavior changes** except small, strictly necessary *UI wiring fixes* (e.g., CORS/config, minor response shaping) approved via issues.

---

## 2. Guiding Principles
1. **Use existing backend APIs** (especially Phase 10 `/ops/*`, `/admin/*`, `/usage/*`, `/rate-limits/*`, `/audit-reports/*`, `/config-governance/*`).
2. **Tenant isolation**: every UI request must include tenant context (header/query param as per current platform convention).
3. **Read-only by default**; destructive/admin actions require:
   - explicit confirmation modals,
   - role/permission checks,
   - audit visibility (who did what, when).
4. **Enterprise UX**: consistent dark theme, consistent tables/filters, predictable navigation, fast loading states, error toasts.
5. **No mock data** (except a small “demo seed” flow if already supported).
6. **Config-driven**: Packs/Playbooks/Tools pages reflect Domain Packs + Tenant Packs; UI must not embed domain logic.

---

## 3. MVP Scope Overview

### 3.1 Ops UI (Operations / Control Plane)
These pages are primarily **operational dashboards** and **triage** views.

**Routes**
- `/ops` → Overview dashboard
- `/ops/workers` → Worker health + throughput
- `/ops/sla` → SLA compliance + breaches
- `/ops/dlq` → DLQ list + detail + actions (retry/discard if enabled)
- `/ops/alerts` → Alert configurations + create/edit
- `/ops/alerts/history` → Alert history (fired/resolved)
- `/ops/reports` → Audit report generation + downloads
- `/ops/usage` → Usage metering + export
- `/ops/rate-limits` → Rate limits per tenant (view; admin actions gated)

### 3.2 Admin UI (Governance / Change Control)
These pages represent governance workflows and configuration management.

**Routes**
- `/admin` → Admin landing (quick links + approvals)
- `/admin/config-changes` → Approve / reject config changes (Phase 10 governance)
- `/admin/packs` → Domain Packs + Tenant Packs management (view/import/activate)
- `/admin/playbooks` → Playbooks list + version + activate (tenant-scoped)
- `/admin/tools` → Tool registry + enable/disable tools per tenant

> Note: If playbooks/tools admin features are partially implemented in earlier phases, Phase 11’s MVP is to **surface what exists** (list/detail) and support **safe minimal actions** with guardrails.

---

## 4. Feature Requirements (Detailed)

## 4.1 Navigation & Access Control
- Add left-nav sections:
  - **Ops**
  - **Admin**
- Gate visibility using env flags:
  - `OPS_ENABLED=true` → show Ops menu
  - `ADMIN_ENABLED=true` → show Admin menu
- If RBAC exists, further restrict:
  - `viewer` → read-only
  - `operator` → safe operational actions (retry/replay)
  - `admin` → config changes approvals, pack activation, rate limits updates

**Acceptance**
- Users without Ops access do not see Ops nav.
- Users without Admin access do not see Admin nav.
- Attempting to access pages directly without access shows a friendly “Not authorized” screen.

---

## 4.2 Shared UI Components (Foundation)
Create reusable components (or use existing ones):
- `TenantDomainBar` (tenant selector + domain selector; already present in header)
- `DataTable` with:
  - sorting, pagination, column visibility, export button (optional)
  - consistent empty/loading/error states
- `FilterBar` components:
  - date range, status, severity, system/source, etc.
- `ConfirmDialog` (for destructive actions)
- `Toast` notifications
- `CodeViewer` for JSON payloads (DLQ detail, config diff)

**Acceptance**
- All Ops/Admin pages use consistent table + filter patterns.
- No duplicated “one-off” table UI patterns across pages.

---

## 4.3 Ops Overview Dashboard (`/ops`)
Show “at-a-glance” widgets:
- Worker health summary (healthy/degraded/down)
- Throughput (events/min)
- Error rate
- SLA: breached + at-risk counts
- DLQ size
- Alerts fired (last 24h)
- Report jobs (queued/running/completed/failed)

**Acceptance**
- Loads within 2–3 seconds on local dev.
- Each widget has “View details” navigation to the relevant page.

---

## 4.4 Workers Dashboard (`/ops/workers`)
Show:
- Worker list with status, last heartbeat, version, host/pod
- Throughput, latency and error counters per worker
- Optional: sparkline charts if already available

**Acceptance**
- A refresh button re-fetches data.
- If a worker is unhealthy, highlight it and show last error reason if provided.

---

## 4.5 SLA Dashboard (`/ops/sla`)
Show:
- SLA compliance percentage
- Breached exceptions table (filters by tenant/domain/type)
- At-risk exceptions table
- Resolution time distribution (optional chart)

**Acceptance**
- Click exception id to navigate to exception detail view.
- SLA time windows are clearly shown.

---

## 4.6 DLQ Management UI (`/ops/dlq`)
Show:
- DLQ message list with filters (tenant, topic, reason, status, time range)
- DLQ detail: message payload, correlation_id/exception_id, error stack (if present)
- Actions (role gated):
  - Retry
  - Retry batch
  - Discard

**Acceptance**
- No accidental destructive action: confirm modal required.
- Audit event appears in history (if surfaced) after action.

---

## 4.7 Alerts UI (`/ops/alerts`, `/ops/alerts/history`)
Alerts Config page:
- List configs
- Create/edit basic fields:
  - name, severity, condition (template), channels (webhook)
  - enabled toggle

Alerts History page:
- Fired/resolved list
- Details: which condition fired, when, which tenant/domain, payload excerpt

**Acceptance**
- Create/edit is validated client-side (required fields).
- History supports filtering by time range + severity + status.

---

## 4.8 Reports UI (`/ops/reports`)
- Create report request:
  - choose tenant/domain, date range, report type
- View report jobs list:
  - queued/running/completed/failed
- Download:
  - show expiring URL and “Download” button

**Acceptance**
- A completed report can be downloaded successfully (local dev).
- Failed report shows error reason.

---

## 4.9 Usage Metering UI (`/ops/usage`)
Show:
- usage summary by tenant and by capability (events processed, tool calls, LLM calls)
- export button (CSV/JSON) if backend supports export

**Acceptance**
- Clear date range selection.
- Data displayed is not mocked.

---

## 4.10 Rate Limits UI (`/ops/rate-limits`)
Show:
- per-tenant rate limit config
- current utilization (if available)
- admin actions:
  - update limits
  - enable/disable limiting

**Acceptance**
- Non-admin users see view-only.
- Admin update requires confirmation and audit visibility.

---

## 4.11 Config Change Governance UI (`/admin/config-changes`)
Show:
- pending changes list
- detail view:
  - config diff (before/after)
  - requestor + timestamp
  - comments
- actions:
  - approve
  - reject

**Acceptance**
- Approve/reject updates list immediately.
- Unauthorized role cannot approve/reject.

---

## 4.12 Packs UI (`/admin/packs`)
MVP features:
- View Domain Packs (list + detail)
- View Tenant Packs (list + detail)
- Activate a pack version (admin only)
- Import/upload pack JSON (optional; if backend supports; otherwise show “coming soon”)

**Acceptance**
- Packs pages show real files/data from backend.
- Activation updates current active config shown in UI.

---

## 4.13 Playbooks UI (`/admin/playbooks`)
MVP features:
- List playbooks by tenant/domain
- View playbook detail:
  - match rules
  - steps
  - referenced tools
- Activate/deactivate (admin only)

**Acceptance**
- A playbook can be toggled active/inactive safely with confirmation.

---

## 4.14 Tools UI (`/admin/tools`)
MVP features:
- Tool registry list + detail (name, schema, provider, allowed tenants)
- Enable/disable tools for a tenant (admin only)
- Show recent tool executions (optional link to existing views)

**Acceptance**
- Tools show real registry content and tenant enablement.

---

## 5. API Integration Requirements
- All requests must pass tenant context using the current platform convention (header or query param).
- Standardize API clients in UI:
  - `ui/src/api/*` with typed request/response models
  - central error handling (toast)
  - auth header injection if present
- Avoid ad-hoc `fetch` calls in components.

---

## 6. Non-Goals (Explicitly Out of Scope)
- Full onboarding wizard for new tenants (may be Phase 12+).
- Automatic Copilot-driven config creation/activation without approval.
- Multi-region deployment UI.
- Full BI / PowerBI integration UI (future).

---

## 7. Copilot Alignment (Do Not Replace Floating Copilot)
- Keep the existing **floating Copilot** UI.
- Phase 11 adds only **context hooks**:
  - “Ask Copilot about this page” (pre-filled prompt with context)
  - Copilot can explain dashboards and anomalies (read-only)
- No “execute actions” from Copilot in Phase 11.

---

## 8. Implementation Plan (Two-shot Friendly)

### Batch 1 — Ops UI (Read-only dashboards + DLQ + Alerts + Reports)
Deliver:
- `/ops` `/ops/workers` `/ops/sla` `/ops/dlq`
- `/ops/alerts` `/ops/alerts/history` `/ops/reports`
- Shared components: DataTable, FilterBar, ConfirmDialog, CodeViewer
- Navigation + flags (OPS_ENABLED)

### Batch 2 — Admin UI + Remaining Ops (Usage/Rate Limits) + Placeholder Completion
Deliver:
- `/ops/usage` `/ops/rate-limits`
- `/admin` `/admin/config-changes`
- `/admin/packs` `/admin/playbooks` `/admin/tools`
- Navigation + flags (ADMIN_ENABLED)
- Minimal RBAC gating (front-end) consistent with backend

---

## 9. Testing & Verification
### 9.1 UI Verification Checklist
- Ops pages load with real data.
- Filters work and update query.
- Error states render properly.
- Confirm dialogs prevent accidental actions.
- Download report works.
- Tenant selector updates all pages.

### 9.2 Automated Tests (MVP)
- At minimum:
  - route renders without crash
  - API client handles errors
  - admin pages hidden when flags off

---

## 10. Completion Criteria
Phase 11 is complete when:
1. All Phase 10 backend capabilities are **visible and usable** via Ops/Admin UI.
2. Packs/Playbooks/Tools placeholders are replaced with real screens wired to backend.
3. Tenant/domain context is consistently applied to all queries.
4. Read-only by default; admin actions are gated and audited.
5. UI styling is consistent and professional (enterprise-grade dark theme).
