# Phase 4 UI MVP Implementation Plan

## Objective

Build a professional operator and supervisor UI for the Agentic Exception Processing Platform. The UI provides:

- **Operator Console**: Exception browsing, detail views with explainability, and simulation capabilities
- **Supervisor Dashboard**: Cross-tenant oversight, escalations, and policy violations
- **Config & Learning Console**: Read-only configuration browser and optimization recommendations viewer

Phase 4 focuses on **read-only** UI with simulation support. No configuration editing, authentication, or AI Co-Pilot chat interface (those are Phase 5+).

---

## Scope Overview: 4 Streams

The Phase 4 UI MVP is organized into four implementation streams:

- **Stream A: UI Foundation & Shell** - Project setup, theme, routing, layout, shared components
- **Stream B: Operator Console** - Exception list, detail pages, explainability views, simulation
- **Stream C: Supervisor Dashboard** - Overview, escalations, policy violations
- **Stream D: Config & Learning Console** - Configuration browser, diff viewer, recommendations

---

## Stream A: UI Foundation & Shell

### A1: Project Setup & Core Infrastructure
**Epic**: Create `ui/` project with Vite + React 18 + TypeScript, MUI theme, router, layout, TenantContext

**Tasks**:
- Initialize Vite + React 18 + TypeScript project in `ui/` directory
- Install dependencies: `react-router-dom`, `@mui/material`, `@mui/icons-material`, `@tanstack/react-query`, `axios`
- Configure TypeScript (`tsconfig.json`) with strict mode
- Configure Vite (`vite.config.ts`) with environment variable support (`VITE_API_BASE_URL`)
- Create MUI theme (`src/theme/theme.ts`) with light/dark mode support
- Set up React Router (`src/routes/`) with basic route structure
- Create `AppLayout` component (`src/layouts/AppLayout.tsx`) with sidebar and top bar structure
- Create `TenantContext` (`src/hooks/useTenant.ts`) for tenant/domain state management
- Create HTTP client utility (`src/utils/httpClient.ts`) with base URL, tenant injection, error handling

**Acceptance Criteria**:
- Project builds and runs (`npm run dev`)
- MUI theme applied globally
- Router navigates between placeholder pages
- TenantContext provides tenant/domain state
- HTTP client includes tenantId in all requests

---

### A2: Shared Components & Utilities
**Epic**: Build reusable components (AppLayout, PageHeader, DataTable wrapper, FilterBar), error handling

**Tasks**:
- Create `AppLayout` component with:
  - Left sidebar navigation (Exceptions, Supervisor, Config)
  - Top bar with tenant selector, domain selector, environment badge
  - Responsive drawer for mobile
- Create `PageHeader` component for consistent page titles and actions
- Create `DataTable` wrapper component using MUI Table with:
  - Pagination controls
  - Sorting
  - Loading skeleton states
- Create `FilterBar` component for exception list filters:
  - Severity dropdown
  - Status dropdown
  - Date range picker
  - Source system filter
- Create error handling utilities:
  - Error boundary component
  - Snackbar error notifications
  - Standard error message formatting
- Create loading state utilities:
  - Skeleton loaders for tables, cards
  - Loading spinners for buttons

**Acceptance Criteria**:
- AppLayout renders with sidebar and top bar
- PageHeader displays on all pages
- DataTable supports pagination and sorting
- FilterBar applies filters correctly
- Error states display user-friendly messages
- Loading states show skeletons/spinners

---

### A3: TypeScript Types & API Client Foundation
**Epic**: Define TypeScript types aligned to backend JSON schemas, create API client functions

**Tasks**:
- Define TypeScript types in `src/types/`:
  - `api.ts`: Common API response types (pagination, errors)
  - `exceptions.ts`: Exception schema types matching backend
  - `supervisor.ts`: Supervisor dashboard types
  - `config.ts`: Configuration types (Domain Pack, Tenant Policy Pack, Playbook)
  - `explanations.ts`: Explanation and timeline types
- Create API client functions in `src/api/`:
  - `httpClient.ts`: Base HTTP client with interceptors
  - `exceptions.ts`: Exception API functions (list, detail, evidence, audit)
  - `supervisor.ts`: Supervisor API functions
  - `config.ts`: Config API functions
  - `explanations.ts`: Explanation API functions
  - `simulation.ts`: Simulation API functions
- Integrate TanStack Query:
  - Create query hooks in `src/hooks/` (e.g., `useExceptions.ts`)
  - Configure query client with default options
  - Set up error handling in query hooks

**Acceptance Criteria**:
- All backend API responses have matching TypeScript types
- API client functions match backend endpoint signatures
- TanStack Query hooks fetch data correctly
- Type errors caught at compile time

---

## Stream B: Operator Console

### B1: Exceptions List Page
**Epic**: `/exceptions` page wired to `GET /ui/exceptions` with filters, pagination, sorting

**Tasks**:
- Create `ExceptionsPage` component (`src/routes/ExceptionsPage.tsx`)
- Implement exception list table with columns:
  - Exception ID (link to detail)
  - Severity (with color coding)
  - Status (with badges)
  - Type
  - Source System
  - Timestamp
- Integrate FilterBar component:
  - Severity filter
  - Status filter
  - Date range filter
  - Source system filter
- Implement pagination:
  - Page size selector
  - Page navigation controls
  - Total count display
- Implement sorting:
  - Click column headers to sort
  - Visual sort indicators
- Wire to `GET /ui/exceptions` API:
  - Use TanStack Query hook
  - Pass filters, pagination, sorting as query params
  - Handle loading and error states
- Add "New Exception" button (placeholder, links to ingestion API docs)

**Acceptance Criteria**:
- Exception list displays with all columns
- Filters apply correctly and update URL query params
- Pagination works (page size, navigation)
- Sorting works on all sortable columns
- Loading skeleton shows during fetch
- Error snackbar shows on API errors
- Clicking exception ID navigates to detail page

---

### B2: Exception Detail Page - Core Views
**Epic**: `/exceptions/:id` page wired to multiple backend endpoints for timeline, evidence, explanation, audit

**Tasks**:
- Create `ExceptionDetailPage` component (`src/routes/ExceptionDetailPage.tsx`)
- Implement summary section (top/left):
  - Exception ID, status, severity, type
  - Timestamp, source system, domain
  - Quick action buttons (Re-run, Approve placeholder, Escalate placeholder)
- Implement tabbed detail sections:
  - **Timeline Tab**: Wire to `GET /explanations/{id}/timeline`
    - Display agent stages (Intake → Triage → Policy → Resolution → Feedback)
    - Show decision, confidence, timestamp for each stage
    - Visual timeline with connecting lines
  - **Evidence Tab**: Wire to `GET /ui/exceptions/{id}/evidence`
    - Display RAG results (similar exceptions, similarity scores)
    - Display tool outputs (if any)
    - Display policy rules applied
    - Show evidence attribution
  - **Explanation Tab**: Wire to `GET /explanations/{id}`
    - Display natural language explanation
    - Support format selector (JSON, text, structured)
    - Show explanation version info
  - **Audit Tab**: Wire to `GET /ui/exceptions/{id}/audit`
    - Display complete audit trail
    - Show actor, action, timestamp, details
    - Sortable by timestamp
- Wire to `GET /ui/exceptions/{id}` for exception detail:
  - Use TanStack Query hook
  - Handle loading and error states
  - Display exception schema fields

**Acceptance Criteria**:
- Exception detail page loads with summary section
- All four tabs (Timeline, Evidence, Explanation, Audit) display data correctly
- Timeline shows all agent stages with decisions
- Evidence shows RAG results, tool outputs, policy rules
- Explanation displays natural language text
- Audit trail shows complete history
- Loading states show skeletons
- Error states show error messages
- Navigation from list page works correctly

---

### B3: Simulation & Re-Run Functionality
**Epic**: Button to trigger simulation via `POST /ui/exceptions/{id}/rerun` and show diff

**Tasks**:
- Add "Re-run Simulation" button to exception detail summary section
- Create simulation dialog/modal:
  - Allow parameter overrides (severity, policies, playbook)
  - Checkbox for simulation mode (default: true)
  - Submit button triggers `POST /ui/exceptions/{id}/rerun`
- Implement simulation result display:
  - Show simulation ID
  - Display simulated exception record
  - Display pipeline result
  - Show comparison with original (if available)
- Wire to comparison API (`GET /ui/simulation/{simulation_id}/compare`):
  - Display diff between original and simulated
  - Highlight differences (decisions, confidence scores, actions)
- Add "What-If" simulation button (optional):
  - Pre-fill common what-if scenarios (e.g., "What if severity was HIGH?")
  - Trigger simulation with pre-filled overrides

**Acceptance Criteria**:
- "Re-run Simulation" button triggers API call
- Simulation dialog allows parameter overrides
- Simulation result displays correctly
- Comparison view shows differences between original and simulated
- Error handling for simulation failures
- Loading state during simulation execution

---

## Stream C: Supervisor Dashboard

### C1: Supervisor Overview Page
**Epic**: `/supervisor` page wired to `GET /ui/supervisor/overview`

**Tasks**:
- Create `SupervisorPage` component (`src/routes/SupervisorPage.tsx`)
- Implement overview tab:
  - Wire to `GET /ui/supervisor/overview`
  - Display counts by severity and status (cards or charts)
  - Display escalations count
  - Display pending approvals count
  - Display top policy violations (list or table)
  - Display optimization suggestions summary
- Add filters:
  - Tenant selector (if multi-tenant view allowed)
  - Domain filter
  - Date range (from_ts, to_ts)
- Use TanStack Query for data fetching
- Handle loading and error states

**Acceptance Criteria**:
- Overview page displays all metrics
- Filters apply correctly
- Data refreshes on filter change
- Loading skeleton shows during fetch
- Error snackbar shows on API errors

---

### C2: Escalations & Policy Violations Tabs
**Epic**: Tabs for escalations and policy violations using `/ui/supervisor/escalations` and `/ui/supervisor/policy-violations`

**Tasks**:
- Implement Escalations tab:
  - Wire to `GET /ui/supervisor/escalations`
  - Display escalation list table:
    - Exception ID (link to detail)
    - Tenant ID
    - Domain
    - Exception Type
    - Severity
    - Timestamp
    - Escalation Reason
  - Add pagination and filters
- Implement Policy Violations tab:
  - Wire to `GET /ui/supervisor/policy-violations`
  - Display violations list table:
    - Exception ID (link to detail)
    - Tenant ID
    - Domain
    - Timestamp
    - Violation Type
    - Violated Rule
    - Decision
  - Add pagination and filters
- Add navigation from supervisor page to exception detail pages

**Acceptance Criteria**:
- Escalations tab displays escalation list
- Policy Violations tab displays violations list
- Both tabs support pagination
- Clicking exception ID navigates to detail page
- Loading and error states handled correctly

---

### C3: SLO/Quota Summary Cards (Optional)
**Epic**: Optional SLO/quota summary cards if backend endpoints exist; otherwise placeholders

**Tasks**:
- Check if backend provides SLO/quota endpoints:
  - `GET /ui/supervisor/slo-summary` (if exists)
  - `GET /ui/supervisor/quota-summary` (if exists)
- If endpoints exist:
  - Create SLO summary cards:
    - Display SLO metrics (latency, throughput, error rates, MTTR, auto-resolution rate)
    - Show compliance status (met/violated)
    - Display trend indicators
  - Create quota summary cards:
    - Display quota usage (LLM tokens, vector DB queries, tool calls)
    - Show usage percentage
    - Display warnings for approaching limits
- If endpoints don't exist:
  - Add placeholder cards with "Coming in Phase 5" message
- Add to supervisor overview page

**Acceptance Criteria**:
- SLO/quota cards display if endpoints exist
- Placeholders show if endpoints don't exist
- Cards update on filter changes
- Loading and error states handled

---

## Stream D: Config & Learning Console

### D1: Config Browser
**Epic**: `/config` page using `/admin/config/domain-packs*`, `/tenant-policies*`, `/playbooks*`

**Tasks**:
- Create `ConfigPage` component (`src/routes/ConfigPage.tsx`)
- Implement config type selector (tabs or dropdown):
  - Domain Packs
  - Tenant Policy Packs
  - Playbooks
- Implement Domain Packs view:
  - Wire to `GET /admin/config/domain-packs`
  - Display pack list table:
    - Pack ID, Name, Version
    - Tenant ID, Domain
    - Timestamp
  - Add filters (tenant, domain)
  - Click pack → Navigate to detail view
- Implement Tenant Policy Packs view:
  - Wire to `GET /admin/config/tenant-policies`
  - Display policy list table (similar structure)
  - Add filters
  - Click policy → Navigate to detail view
- Implement Playbooks view:
  - Wire to `GET /admin/config/playbooks`
  - Display playbook list table
  - Add filters
  - Click playbook → Navigate to detail view
- Create config detail view:
  - Wire to `GET /admin/config/{type}/{id}`
  - Display full configuration JSON (formatted, syntax-highlighted)
  - Read-only display (no edit buttons)
- Add pagination for all list views

**Acceptance Criteria**:
- Config browser displays all three config types
- List views show correct data
- Filters apply correctly
- Detail views display formatted JSON
- All views are read-only
- Loading and error states handled

---

### D2: Diff Viewer
**Epic**: Diff view using `GET /admin/config/diff`

**Tasks**:
- Add "Compare Versions" button to config detail view
- Create diff dialog/modal:
  - Select two versions (left and right)
  - Trigger `GET /admin/config/diff` with version IDs
  - Display diff result:
    - Side-by-side comparison (left vs right)
    - Highlight differences (added, removed, changed)
    - Show structured differences summary
- Use a diff library (e.g., `react-diff-viewer` or MUI-based solution)
- Display diff summary:
  - Number of additions
  - Number of deletions
  - Number of changes

**Acceptance Criteria**:
- Diff viewer displays side-by-side comparison
- Differences highlighted correctly
- Diff summary shows change counts
- Diff API call includes correct parameters
- Loading and error states handled

---

### D3: Recommendations View (Read-Only)
**Epic**: Read-only recommendations view for policy/severity/playbook/guardrail suggestions

**Tasks**:
- Create recommendations tab/section in ConfigPage
- Wire to backend recommendation endpoints (if available):
  - `GET /admin/config/recommendations/policy` (if exists)
  - `GET /admin/config/recommendations/severity` (if exists)
  - `GET /admin/config/recommendations/playbook` (if exists)
  - `GET /admin/config/recommendations/guardrail` (if exists)
- Display recommendations list:
  - Recommendation type
  - Description/summary
  - Confidence score
  - Suggested change
  - Impact analysis (if available)
- Mark recommendations as read-only:
  - No "Apply" buttons (Phase 4)
  - Display "Review in Phase 5" message
- If endpoints don't exist:
  - Show placeholder: "Recommendations API coming in Phase 5"

**Acceptance Criteria**:
- Recommendations view displays if endpoints exist
- Placeholder shows if endpoints don't exist
- All recommendations marked as read-only
- Loading and error states handled

---

## Out-of-Scope for Phase 4

### Authentication & Authorization
- **No real authentication**: Simple tenant/domain selector only
- **No SSO integration**: No OAuth, SAML, or other SSO providers
- **No RBAC**: No role-based access control or permission checks
- **No session management**: No secure session storage or token refresh

### Configuration Editing
- **No pack upload**: Cannot upload Domain Packs or Tenant Policy Packs via UI
- **No policy editing**: Cannot edit Tenant Policy Packs via UI
- **No playbook editing**: Cannot edit Playbooks via UI
- **No config creation**: Cannot create new configurations via UI

### AI Co-Pilot Assistant
- **No chat interface**: Natural language query API exists in backend but no UI
- **No conversational assistant**: No chat-based interaction with agents
- **No AI suggestions in UI**: Recommendations are read-only, no interactive AI

### Advanced Features
- **No real-time collaboration**: No multi-user editing or live updates
- **No mobile app**: Web UI only (responsive design for tablets)
- **No offline mode**: Requires backend connection at all times
- **No export/import**: Cannot export or import configurations
- **No bulk operations**: No bulk editing or bulk actions

---

## Deliverables Checklist

### Stream A: Foundation
- [ ] `ui/` project initialized with Vite + React 18 + TypeScript
- [ ] MUI theme configured and applied
- [ ] React Router set up with route structure
- [ ] `AppLayout` component with sidebar and top bar
- [ ] `TenantContext` hook for tenant/domain state
- [ ] HTTP client utility with tenant injection
- [ ] Shared components (PageHeader, DataTable, FilterBar)
- [ ] Error handling utilities (error boundary, snackbars)
- [ ] Loading state utilities (skeletons, spinners)
- [ ] TypeScript types matching backend schemas
- [ ] API client functions for all backend endpoints
- [ ] TanStack Query hooks integrated

### Stream B: Operator Console
- [ ] `/exceptions` page with list, filters, pagination, sorting
- [ ] `/exceptions/:id` page with summary section
- [ ] Timeline tab displaying agent stages and decisions
- [ ] Evidence tab displaying RAG results, tool outputs, policy rules
- [ ] Explanation tab displaying natural language explanations
- [ ] Audit tab displaying complete audit trail
- [ ] Re-run simulation button and dialog
- [ ] Simulation result display and comparison view

### Stream C: Supervisor Dashboard
- [ ] `/supervisor` page with overview tab
- [ ] Overview displaying counts, escalations, violations, suggestions
- [ ] Escalations tab with escalation list
- [ ] Policy Violations tab with violations list
- [ ] Filters (tenant, domain, date range) on supervisor page
- [ ] SLO/quota summary cards (if endpoints exist) or placeholders

### Stream D: Config & Learning Console
- [ ] `/config` page with config type selector
- [ ] Domain Packs list and detail views
- [ ] Tenant Policy Packs list and detail views
- [ ] Playbooks list and detail views
- [ ] Diff viewer for version comparison
- [ ] Recommendations view (read-only) or placeholder

### Testing & Quality
- [ ] Unit tests for utility functions and hooks
- [ ] Component tests for shared components
- [ ] Integration tests for API client functions
- [ ] E2E tests for critical user flows (list → detail → simulation)
- [ ] Accessibility testing (keyboard navigation, screen readers)
- [ ] Cross-browser testing (Chrome, Firefox, Safari, Edge)

### Documentation
- [ ] README in `ui/` directory with setup instructions
- [ ] API integration guide documenting all API calls
- [ ] Component documentation (Storybook optional but recommended)
- [ ] Deployment guide for production build

---

## Success Metrics

- **Functionality**: All pages load and display data correctly
- **Performance**: Page load times < 2 seconds, smooth interactions
- **Accessibility**: WCAG 2.1 AA compliance (basic level)
- **Type Safety**: Zero TypeScript errors in production build
- **Error Handling**: All API errors display user-friendly messages
- **Responsiveness**: UI works on desktop and tablet (mobile optional)

---

## Dependencies

### Backend APIs Required
- `/ui/exceptions` (list, detail, evidence, audit)
- `/explanations/{id}` and `/explanations/{id}/timeline`
- `/ui/supervisor/overview`, `/escalations`, `/policy-violations`
- `/admin/config/domain-packs*`, `/tenant-policies*`, `/playbooks*`
- `/admin/config/diff`
- `/ui/exceptions/{id}/rerun` (simulation)

### External Dependencies
- React 18
- TypeScript 5+
- Vite 5+
- Material UI (MUI) 5+
- TanStack Query (React Query) 5+
- react-router-dom 6+
- axios or fetch API wrapper

---

## Timeline Estimate

- **Stream A**: 2-3 weeks (foundation and shared components)
- **Stream B**: 3-4 weeks (operator console)
- **Stream C**: 1-2 weeks (supervisor dashboard)
- **Stream D**: 2-3 weeks (config console)
- **Testing & Polish**: 1-2 weeks

**Total**: ~9-14 weeks for complete Phase 4 UI MVP


