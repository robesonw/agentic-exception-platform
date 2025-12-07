# Phase 4 UI MVP - GitHub Issues Checklist

## Stream A: UI Foundation & Shell

### Issue UI-A1: Initialize UI Project with Vite, React 18, TypeScript, and Core Dependencies
**Labels:** `component:ui:foundation`, `phase:4`, `priority:high`
**Description:**
- Initialize Vite + React 18 + TypeScript project in `ui/` directory
- Install and configure core dependencies: `react-router-dom`, `@mui/material`, `@mui/icons-material`, `@tanstack/react-query`, `axios`
- Configure TypeScript (`tsconfig.json`) with strict mode
- Configure Vite (`vite.config.ts`) with environment variable support (`VITE_API_BASE_URL`)
- Set up basic project structure matching folder structure in docs/10-ui-guidelines.md
- Create initial `package.json` with scripts for dev, build, test
- Reference: docs/10-ui-guidelines.md (Tech Stack, Folder Structure), docs/11-ui-phase4-mvp-plan.md (Stream A1)

**Dependencies:** None (foundational issue)

**Acceptance Criteria:**
- [ ] `ui/` directory created with Vite + React 18 + TypeScript project
- [ ] All core dependencies installed and configured
- [ ] TypeScript configured with strict mode
- [ ] Vite configured with `VITE_API_BASE_URL` environment variable support
- [ ] Folder structure matches docs/10-ui-guidelines.md specification
- [ ] Project builds successfully (`npm run build`)
- [ ] Dev server runs (`npm run dev`)
- [ ] Basic React app renders without errors

---

### Issue UI-A2: Implement MUI Theme Configuration and App Layout Shell
**Labels:** `component:ui:layout`, `phase:4`, `priority:high`
**Description:**
- Create MUI theme (`src/theme/theme.ts`) with light/dark mode support
- Create `AppLayout` component (`src/layouts/AppLayout.tsx`) with:
  - Left sidebar navigation (Exceptions, Supervisor, Config)
  - Top bar with placeholder for tenant selector, domain selector, environment badge
  - Responsive drawer for mobile/tablet
- Wrap app with MUI ThemeProvider and CssBaseline
- Apply theme globally across application
- Reference: docs/10-ui-guidelines.md (Layout, Tech Stack), docs/11-ui-phase4-mvp-plan.md (Stream A1, A2)

**Dependencies:** UI-A1

**Acceptance Criteria:**
- [ ] MUI theme created with light/dark mode support
- [ ] ThemeProvider wraps application
- [ ] AppLayout component renders with sidebar and top bar
- [ ] Sidebar navigation shows Exceptions, Supervisor, Config links
- [ ] Top bar has placeholders for tenant/domain selectors and environment badge
- [ ] Responsive drawer works on mobile/tablet breakpoints
- [ ] Theme applies globally (colors, typography, spacing)
- [ ] Dark mode toggle functional (optional but recommended)

---

### Issue UI-A3: Implement React Router and Basic Route Structure
**Labels:** `component:ui:routing`, `phase:4`, `priority:high`
**Description:**
- Set up React Router (`react-router-dom`) with route structure
- Create placeholder route components:
  - `/login` - LoginPage (tenant/domain selector)
  - `/exceptions` - ExceptionsPage (placeholder)
  - `/exceptions/:id` - ExceptionDetailPage (placeholder)
  - `/supervisor` - SupervisorPage (placeholder)
  - `/config` - ConfigPage (placeholder)
- Implement route protection/navigation logic (basic, no real auth)
- Add navigation from sidebar links to routes
- Reference: docs/10-ui-guidelines.md (Pages), docs/11-ui-phase4-mvp-plan.md (Stream A1)

**Dependencies:** UI-A2

**Acceptance Criteria:**
- [ ] React Router configured and functional
- [ ] All placeholder routes created and accessible
- [ ] Sidebar navigation links navigate to correct routes
- [ ] Route parameters work (`/exceptions/:id`)
- [ ] Navigation between pages works without errors
- [ ] 404 handling for unknown routes

---

### Issue UI-A4: Implement TenantContext Hook for Tenant/Domain State Management
**Labels:** `component:ui:state`, `phase:4`, `priority:high`
**Description:**
- Create `TenantContext` (`src/hooks/useTenant.ts`) using React Context API
- Manage tenant ID and domain state globally
- Provide `useTenant` hook for components to access tenant/domain
- Store tenant/domain in localStorage for persistence (no real auth)
- Update top bar tenant/domain selectors to use TenantContext
- Reference: docs/10-ui-guidelines.md (API Integration, Multi-Tenant Awareness), docs/11-ui-phase4-mvp-plan.md (Stream A1)

**Dependencies:** UI-A2

**Acceptance Criteria:**
- [ ] TenantContext created and exported
- [ ] `useTenant` hook provides tenant ID and domain
- [ ] Tenant/domain state persists in localStorage
- [ ] Top bar selectors update TenantContext
- [ ] Components can access tenant/domain via hook
- [ ] Tenant context updates trigger re-renders correctly

---

### Issue UI-A5: Implement HTTP Client Utility with Tenant Injection and Error Handling
**Labels:** `component:ui:api`, `phase:4`, `priority:high`
**Description:**
- Create HTTP client utility (`src/utils/httpClient.ts`) using axios or fetch
- Configure base URL from `VITE_API_BASE_URL` environment variable
- Automatically inject `tenantId` from TenantContext into all requests
- Implement request/response interceptors
- Add standard error handling and error message formatting
- Support common HTTP methods (GET, POST, PUT, DELETE)
- Reference: docs/10-ui-guidelines.md (API Integration), docs/11-ui-phase4-mvp-plan.md (Stream A1)

**Dependencies:** UI-A4

**Acceptance Criteria:**
- [ ] HTTP client utility created with axios/fetch wrapper
- [ ] Base URL read from `VITE_API_BASE_URL` environment variable
- [ ] `tenantId` automatically injected from TenantContext into all requests
- [ ] Request/response interceptors functional
- [ ] Error handling formats user-friendly error messages
- [ ] All HTTP methods supported
- [ ] Unit tests for HTTP client utility

---

### Issue UI-A6: Implement Shared PageHeader Component
**Labels:** `component:ui:components`, `phase:4`, `priority:medium`
**Description:**
- Create `PageHeader` component (`src/components/common/PageHeader.tsx`) using MUI
- Support page title, subtitle, and action buttons
- Ensure consistent styling and spacing
- Make component reusable across all pages
- Reference: docs/10-ui-guidelines.md (UX Principles, Consistent Layout), docs/11-ui-phase4-mvp-plan.md (Stream A2)

**Dependencies:** UI-A2

**Acceptance Criteria:**
- [ ] PageHeader component created with MUI
- [ ] Supports title, subtitle, and action buttons props
- [ ] Consistent styling matches design system
- [ ] Component reusable and used on multiple pages
- [ ] Responsive design works on mobile/tablet

---

### Issue UI-A7: Implement DataTable Wrapper Component with Pagination and Sorting
**Labels:** `component:ui:components`, `phase:4`, `priority:high`
**Description:**
- Create `DataTable` wrapper component (`src/components/common/DataTable.tsx`) using MUI Table
- Support pagination controls (page size selector, page navigation, total count)
- Implement column sorting (click headers to sort, visual sort indicators)
- Add loading skeleton states using MUI Skeleton
- Make component generic and reusable with configurable columns
- Reference: docs/10-ui-guidelines.md (API Integration, Standard Patterns), docs/11-ui-phase4-mvp-plan.md (Stream A2)

**Dependencies:** UI-A2

**Acceptance Criteria:**
- [ ] DataTable component created with MUI Table
- [ ] Pagination controls functional (page size, navigation, total count)
- [ ] Column sorting works with visual indicators
- [ ] Loading skeleton states display during data fetch
- [ ] Component is generic and reusable
- [ ] Responsive design works on mobile/tablet

---

### Issue UI-A8: Implement FilterBar Component for Exception List Filters
**Labels:** `component:ui:components`, `phase:4`, `priority:high`
**Description:**
- Create `FilterBar` component (`src/components/common/FilterBar.tsx`) using MUI
- Implement filters:
  - Severity dropdown (LOW, MEDIUM, HIGH, CRITICAL)
  - Status dropdown (OPEN, IN_PROGRESS, RESOLVED, ESCALATED)
  - Date range picker (from/to dates)
  - Source system text filter
- Support filter state management and URL query param synchronization
- Emit filter change events for parent components
- Reference: docs/10-ui-guidelines.md (Pages - /exceptions), docs/11-ui-phase4-mvp-plan.md (Stream A2, B1)

**Dependencies:** UI-A2

**Acceptance Criteria:**
- [ ] FilterBar component created with MUI components
- [ ] All filter types implemented (severity, status, date range, source system)
- [ ] Filter state managed correctly
- [ ] Filters sync with URL query parameters
- [ ] Filter change events emitted to parent
- [ ] Responsive design works on mobile/tablet

---

### Issue UI-A9: Implement Error Handling Utilities (Error Boundary, Snackbars)
**Labels:** `component:ui:utilities`, `phase:4`, `priority:high`
**Description:**
- Create error boundary component (`src/components/common/ErrorBoundary.tsx`) using React error boundaries
- Implement Snackbar error notifications using MUI Snackbar
- Create error message formatting utility (`src/utils/errorHandling.ts`)
- Integrate error handling into HTTP client and TanStack Query hooks
- Display user-friendly error messages (no raw API errors)
- Reference: docs/10-ui-guidelines.md (API Integration, Standard Patterns), docs/11-ui-phase4-mvp-plan.md (Stream A2)

**Dependencies:** UI-A5

**Acceptance Criteria:**
- [ ] ErrorBoundary component catches React errors
- [ ] Snackbar notifications display API errors
- [ ] Error message formatting utility formats errors user-friendly
- [ ] HTTP client errors trigger snackbar notifications
- [ ] TanStack Query errors handled via snackbars
- [ ] Error boundary displays fallback UI for React errors

---

### Issue UI-A10: Implement Loading State Utilities (Skeletons, Spinners)
**Labels:** `component:ui:utilities`, `phase:4`, `priority:medium`
**Description:**
- Create loading skeleton components for tables (`src/components/common/TableSkeleton.tsx`)
- Create loading skeleton components for cards (`src/components/common/CardSkeleton.tsx`)
- Create loading spinner component for buttons (`src/components/common/LoadingButton.tsx`)
- Integrate loading states into DataTable and other components
- Reference: docs/10-ui-guidelines.md (API Integration, Standard Patterns), docs/11-ui-phase4-mvp-plan.md (Stream A2)

**Dependencies:** UI-A2

**Acceptance Criteria:**
- [ ] TableSkeleton component created with MUI Skeleton
- [ ] CardSkeleton component created
- [ ] LoadingButton component shows spinner during loading
- [ ] Loading states integrated into DataTable
- [ ] Loading states used consistently across app

---

### Issue UI-A11: Define TypeScript Types Matching Backend API Schemas
**Labels:** `component:ui:types`, `phase:4`, `priority:high`
**Description:**
- Define TypeScript types in `src/types/` directory:
  - `api.ts`: Common API response types (pagination, errors)
  - `exceptions.ts`: Exception schema types matching backend (docs/03-data-models-apis.md)
  - `supervisor.ts`: Supervisor dashboard types
  - `config.ts`: Configuration types (Domain Pack, Tenant Policy Pack, Playbook)
  - `explanations.ts`: Explanation and timeline types
- Ensure types match backend API response schemas exactly
- Reference: docs/10-ui-guidelines.md (Folder Structure), docs/11-ui-phase4-mvp-plan.md (Stream A3), docs/03-data-models-apis.md

**Dependencies:** None (can be done in parallel)

**Acceptance Criteria:**
- [ ] All TypeScript type files created in `src/types/`
- [ ] Types match backend API response schemas
- [ ] Common API types (pagination, errors) defined
- [ ] Exception types match canonical exception schema
- [ ] Supervisor types match supervisor API responses
- [ ] Config types match Domain Pack, Tenant Policy Pack, Playbook schemas
- [ ] Explanation types match explanation API responses
- [ ] TypeScript compiles without errors

---

### Issue UI-A12: Implement API Client Functions for All Backend Endpoints
**Labels:** `component:ui:api`, `phase:4`, `priority:high`
**Description:**
- Create API client functions in `src/api/` directory:
  - `exceptions.ts`: Exception API functions (list, detail, evidence, audit)
  - `supervisor.ts`: Supervisor API functions (overview, escalations, policy-violations)
  - `config.ts`: Config API functions (domain-packs, tenant-policies, playbooks, diff)
  - `explanations.ts`: Explanation API functions (get explanation, timeline)
  - `simulation.ts`: Simulation API functions (rerun, compare)
- Use HTTP client utility for all API calls
- Ensure all functions are typed with TypeScript types from UI-A11
- Reference: docs/10-ui-guidelines.md (API Integration, API Endpoints), docs/11-ui-phase4-mvp-plan.md (Stream A3), backend API routes

**Dependencies:** UI-A5, UI-A11

**Acceptance Criteria:**
- [ ] All API client files created in `src/api/`
- [ ] Exception API functions match backend endpoints (`GET /ui/exceptions`, etc.)
- [ ] Supervisor API functions match backend endpoints
- [ ] Config API functions match backend endpoints
- [ ] Explanation API functions match backend endpoints
- [ ] Simulation API functions match backend endpoints
- [ ] All functions use HTTP client utility
- [ ] All functions properly typed with TypeScript
- [ ] Unit tests for API client functions

---

### Issue UI-A13: Integrate TanStack Query and Create Query Hooks
**Labels:** `component:ui:state`, `phase:4`, `priority:high`
**Description:**
- Configure TanStack Query client with default options
- Create query hooks in `src/hooks/`:
  - `useExceptions.ts`: Hooks for exception list, detail, evidence, audit
  - `useSupervisor.ts`: Hooks for supervisor data
  - `useConfig.ts`: Hooks for config data
  - `useExplanations.ts`: Hooks for explanations
- Set up error handling in query hooks (integrate with snackbars)
- Configure query caching and refetch strategies
- Reference: docs/10-ui-guidelines.md (Tech Stack, Data Fetching), docs/11-ui-phase4-mvp-plan.md (Stream A3)

**Dependencies:** UI-A12, UI-A9

**Acceptance Criteria:**
- [ ] TanStack Query client configured
- [ ] Query hooks created for all API endpoints
- [ ] Error handling integrated with snackbars
- [ ] Query caching configured appropriately
- [ ] Refetch strategies configured
- [ ] Hooks return loading, error, data states
- [ ] Unit tests for query hooks

---

## Stream B: Operator Console

### Issue UI-B1: Implement Exceptions List Page with Filters, Pagination, and Sorting
**Labels:** `component:ui:operator`, `phase:4`, `priority:high`
**Description:**
- Create `ExceptionsPage` component (`src/routes/ExceptionsPage.tsx`)
- Implement exception list table with columns:
  - Exception ID (link to detail page)
  - Severity (with color coding/badges)
  - Status (with badges)
  - Exception Type
  - Source System
  - Timestamp (formatted)
- Integrate FilterBar component (UI-A8) for filtering
- Integrate DataTable component (UI-A7) for pagination and sorting
- Wire to `GET /ui/exceptions` API using TanStack Query hook
- Handle loading and error states
- Add "New Exception" button (placeholder, links to ingestion API docs)
- Reference: docs/10-ui-guidelines.md (Pages - /exceptions), docs/11-ui-phase4-mvp-plan.md (Stream B1)

**Dependencies:** UI-A7, UI-A8, UI-A13

**Acceptance Criteria:**
- [ ] ExceptionsPage component created and routed
- [ ] Exception list table displays all columns correctly
- [ ] Filters apply correctly and update URL query params
- [ ] Pagination works (page size selector, navigation, total count)
- [ ] Sorting works on all sortable columns with visual indicators
- [ ] Loading skeleton shows during data fetch
- [ ] Error snackbar shows on API errors
- [ ] Clicking exception ID navigates to detail page (`/exceptions/:id`)
- [ ] Empty state displays when no exceptions found

---

### Issue UI-B2: Implement Exception Detail Page Summary Section
**Labels:** `component:ui:operator`, `phase:4`, `priority:high`
**Description:**
- Create `ExceptionDetailPage` component (`src/routes/ExceptionDetailPage.tsx`)
- Implement summary section (top/left) displaying:
  - Exception ID, status, severity, type
  - Timestamp, source system, domain
  - Quick action buttons (Re-run simulation placeholder, Approve placeholder, Escalate placeholder)
- Wire to `GET /ui/exceptions/{id}` API using TanStack Query hook
- Handle loading and error states
- Display exception schema fields in summary
- Reference: docs/10-ui-guidelines.md (Pages - /exceptions/:id, Layout), docs/11-ui-phase4-mvp-plan.md (Stream B2)

**Dependencies:** UI-A13, UI-B1

**Acceptance Criteria:**
- [ ] ExceptionDetailPage component created and routed
- [ ] Summary section displays all key fields
- [ ] Status and severity displayed with badges/color coding
- [ ] Quick action buttons render (functionality in UI-B5)
- [ ] Data fetched from `GET /ui/exceptions/{id}` API
- [ ] Loading skeleton shows during fetch
- [ ] Error snackbar shows on API errors
- [ ] Navigation from list page works correctly
- [ ] 404 handling for non-existent exceptions

---

### Issue UI-B3: Implement Timeline Tab for Exception Detail Page
**Labels:** `component:ui:operator`, `phase:4`, `priority:high`
**Description:**
- Create Timeline tab component for ExceptionDetailPage
- Wire to `GET /explanations/{id}/timeline` API using TanStack Query hook
- Display agent stages (Intake → Triage → Policy → Resolution → Feedback) in visual timeline
- Show for each stage:
  - Stage name
  - Decision/outcome
  - Confidence score
  - Timestamp
- Create visual timeline with connecting lines between stages
- Use MUI components for timeline visualization
- Reference: docs/10-ui-guidelines.md (Pages - /exceptions/:id, Explainability Visible), docs/11-ui-phase4-mvp-plan.md (Stream B2)

**Dependencies:** UI-B2, UI-A13

**Acceptance Criteria:**
- [ ] Timeline tab component created
- [ ] Timeline displays all agent stages
- [ ] Each stage shows decision, confidence, timestamp
- [ ] Visual timeline with connecting lines renders correctly
- [ ] Data fetched from `GET /explanations/{id}/timeline` API
- [ ] Loading skeleton shows during fetch
- [ ] Error handling displays error message
- [ ] Timeline is responsive on mobile/tablet

---

### Issue UI-B4: Implement Evidence Tab for Exception Detail Page
**Labels:** `component:ui:operator`, `phase:4`, `priority:high`
**Description:**
- Create Evidence tab component for ExceptionDetailPage
- Wire to `GET /ui/exceptions/{id}/evidence` API using TanStack Query hook
- Display evidence sections:
  - RAG results (similar exceptions, similarity scores)
  - Tool outputs (if any)
  - Policy rules applied
- Show evidence attribution (source, timestamp, relevance)
- Use MUI components for organized display (cards, lists, tables)
- Reference: docs/10-ui-guidelines.md (Pages - /exceptions/:id, Explainability Visible), docs/11-ui-phase4-mvp-plan.md (Stream B2)

**Dependencies:** UI-B2, UI-A13

**Acceptance Criteria:**
- [ ] Evidence tab component created
- [ ] RAG results displayed with similarity scores
- [ ] Tool outputs displayed (if available)
- [ ] Policy rules displayed
- [ ] Evidence attribution shown (source, timestamp)
- [ ] Data fetched from `GET /ui/exceptions/{id}/evidence` API
- [ ] Loading skeleton shows during fetch
- [ ] Error handling displays error message
- [ ] Empty states handled (no evidence available)

---

### Issue UI-B5: Implement Explanation Tab for Exception Detail Page
**Labels:** `component:ui:operator`, `phase:4`, `priority:high`
**Description:**
- Create Explanation tab component for ExceptionDetailPage
- Wire to `GET /explanations/{id}` API using TanStack Query hook
- Display natural language explanation
- Support format selector (JSON, text, structured) - use query param or dropdown
- Show explanation version info
- Use MUI Typography and Code components for formatted display
- Reference: docs/10-ui-guidelines.md (Pages - /exceptions/:id, Explainability Visible), docs/11-ui-phase4-mvp-plan.md (Stream B2)

**Dependencies:** UI-B2, UI-A13

**Acceptance Criteria:**
- [ ] Explanation tab component created
- [ ] Natural language explanation displays correctly
- [ ] Format selector allows switching between JSON, text, structured
- [ ] Explanation version info displayed
- [ ] Data fetched from `GET /explanations/{id}` API with format parameter
- [ ] Loading skeleton shows during fetch
- [ ] Error handling displays error message
- [ ] JSON format displays with syntax highlighting

---

### Issue UI-B6: Implement Audit Tab for Exception Detail Page
**Labels:** `component:ui:operator`, `phase:4`, `priority:high`
**Description:**
- Create Audit tab component for ExceptionDetailPage
- Wire to `GET /ui/exceptions/{id}/audit` API using TanStack Query hook
- Display complete audit trail in table format:
  - Actor (agent/user)
  - Action performed
  - Timestamp
  - Details/notes
- Support sorting by timestamp (newest first by default)
- Use MUI Table component
- Reference: docs/10-ui-guidelines.md (Pages - /exceptions/:id, Explainability Visible), docs/11-ui-phase4-mvp-plan.md (Stream B2)

**Dependencies:** UI-B2, UI-A13

**Acceptance Criteria:**
- [ ] Audit tab component created
- [ ] Audit trail table displays all columns
- [ ] Sorting by timestamp works
- [ ] Data fetched from `GET /ui/exceptions/{id}/audit` API
- [ ] Loading skeleton shows during fetch
- [ ] Error handling displays error message
- [ ] Empty state handled (no audit entries)

---

### Issue UI-B7: Implement Re-Run Simulation Button and Dialog
**Labels:** `component:ui:operator`, `phase:4`, `priority:high`
**Description:**
- Add "Re-run Simulation" button to exception detail summary section
- Create simulation dialog/modal component (`src/components/exceptions/SimulationDialog.tsx`)
- Dialog allows parameter overrides:
  - Severity selector
  - Policy overrides (if applicable)
  - Playbook selector
  - Checkbox for simulation mode (default: true)
- Submit button triggers `POST /ui/exceptions/{id}/rerun` API
- Display loading state during simulation execution
- Handle success and error responses
- Reference: docs/10-ui-guidelines.md (Pages - /exceptions/:id), docs/11-ui-phase4-mvp-plan.md (Stream B3)

**Dependencies:** UI-B2, UI-A13

**Acceptance Criteria:**
- [ ] "Re-run Simulation" button added to summary section
- [ ] SimulationDialog component created with MUI Dialog
- [ ] Parameter overrides form functional
- [ ] Simulation mode checkbox defaults to true
- [ ] API call to `POST /ui/exceptions/{id}/rerun` works correctly
- [ ] Loading state shows during simulation
- [ ] Success response handled (navigate to simulation result or show message)
- [ ] Error handling displays error message in snackbar

---

### Issue UI-B8: Implement Simulation Result Display and Comparison View
**Labels:** `component:ui:operator`, `phase:4`, `priority:high`
**Description:**
- Create simulation result display component (`src/components/exceptions/SimulationResult.tsx`)
- Display simulation result:
  - Simulation ID
  - Simulated exception record
  - Pipeline result
- Wire to comparison API (`GET /ui/simulation/{simulation_id}/compare`) if available
- Display diff between original and simulated:
  - Highlight differences (decisions, confidence scores, actions)
  - Side-by-side or unified diff view
- Use MUI components for organized display
- Reference: docs/10-ui-guidelines.md (Pages - /exceptions/:id), docs/11-ui-phase4-mvp-plan.md (Stream B3)

**Dependencies:** UI-B7, UI-A13

**Acceptance Criteria:**
- [ ] SimulationResult component created
- [ ] Simulation ID, exception record, pipeline result displayed
- [ ] Comparison API called if available
- [ ] Diff view displays differences between original and simulated
- [ ] Differences highlighted clearly
- [ ] Loading skeleton shows during fetch
- [ ] Error handling displays error message
- [ ] Navigation back to original exception works

---

## Stream C: Supervisor Dashboard

### Issue UI-C1: Implement Supervisor Overview Page
**Labels:** `component:ui:supervisor`, `phase:4`, `priority:high`
**Description:**
- Create `SupervisorPage` component (`src/routes/SupervisorPage.tsx`)
- Implement overview tab:
  - Wire to `GET /ui/supervisor/overview` API using TanStack Query hook
  - Display counts by severity and status (cards or charts using MUI)
  - Display escalations count
  - Display pending approvals count
  - Display top policy violations (list or table)
  - Display optimization suggestions summary
- Add filters:
  - Tenant selector (if multi-tenant view allowed)
  - Domain filter dropdown
  - Date range picker (from_ts, to_ts)
- Handle loading and error states
- Reference: docs/10-ui-guidelines.md (Pages - /supervisor), docs/11-ui-phase4-mvp-plan.md (Stream C1)

**Dependencies:** UI-A13, UI-A2

**Acceptance Criteria:**
- [ ] SupervisorPage component created and routed
- [ ] Overview tab displays all metrics correctly
- [ ] Counts by severity/status displayed (cards or charts)
- [ ] Escalations count displayed
- [ ] Pending approvals count displayed
- [ ] Top policy violations displayed
- [ ] Optimization suggestions summary displayed
- [ ] Filters apply correctly and update API calls
- [ ] Loading skeleton shows during fetch
- [ ] Error snackbar shows on API errors

---

### Issue UI-C2: Implement Escalations Tab for Supervisor Page
**Labels:** `component:ui:supervisor`, `phase:4`, `priority:high`
**Description:**
- Create Escalations tab component for SupervisorPage
- Wire to `GET /ui/supervisor/escalations` API using TanStack Query hook
- Display escalation list table:
  - Exception ID (link to detail page)
  - Tenant ID
  - Domain
  - Exception Type
  - Severity
  - Timestamp
  - Escalation Reason
- Integrate DataTable component (UI-A7) for pagination and sorting
- Add filters (tenant, domain, date range)
- Handle loading and error states
- Reference: docs/10-ui-guidelines.md (Pages - /supervisor), docs/11-ui-phase4-mvp-plan.md (Stream C2)

**Dependencies:** UI-C1, UI-A7, UI-A13

**Acceptance Criteria:**
- [ ] Escalations tab component created
- [ ] Escalation list table displays all columns
- [ ] Pagination works correctly
- [ ] Sorting works on sortable columns
- [ ] Filters apply correctly
- [ ] Clicking exception ID navigates to exception detail page
- [ ] Data fetched from `GET /ui/supervisor/escalations` API
- [ ] Loading skeleton shows during fetch
- [ ] Error handling displays error message

---

### Issue UI-C3: Implement Policy Violations Tab for Supervisor Page
**Labels:** `component:ui:supervisor`, `phase:4`, `priority:high`
**Description:**
- Create Policy Violations tab component for SupervisorPage
- Wire to `GET /ui/supervisor/policy-violations` API using TanStack Query hook
- Display violations list table:
  - Exception ID (link to detail page)
  - Tenant ID
  - Domain
  - Timestamp
  - Violation Type
  - Violated Rule
  - Decision
- Integrate DataTable component (UI-A7) for pagination and sorting
- Add filters (tenant, domain, date range)
- Handle loading and error states
- Reference: docs/10-ui-guidelines.md (Pages - /supervisor), docs/11-ui-phase4-mvp-plan.md (Stream C2)

**Dependencies:** UI-C1, UI-A7, UI-A13

**Acceptance Criteria:**
- [ ] Policy Violations tab component created
- [ ] Violations list table displays all columns
- [ ] Pagination works correctly
- [ ] Sorting works on sortable columns
- [ ] Filters apply correctly
- [ ] Clicking exception ID navigates to exception detail page
- [ ] Data fetched from `GET /ui/supervisor/policy-violations` API
- [ ] Loading skeleton shows during fetch
- [ ] Error handling displays error message

---

### Issue UI-C4: Implement SLO/Quota Summary Cards (Optional)
**Labels:** `component:ui:supervisor`, `phase:4`, `priority:low`
**Description:**
- Check if backend provides SLO/quota endpoints:
  - `GET /ui/supervisor/slo-summary` (if exists)
  - `GET /ui/supervisor/quota-summary` (if exists)
- If endpoints exist:
  - Create SLO summary cards displaying:
    - SLO metrics (latency, throughput, error rates, MTTR, auto-resolution rate)
    - Compliance status (met/violated) with color coding
    - Trend indicators
  - Create quota summary cards displaying:
    - Quota usage (LLM tokens, vector DB queries, tool calls)
    - Usage percentage with progress bars
    - Warnings for approaching limits
- If endpoints don't exist:
  - Add placeholder cards with "Coming in Phase 5" message
- Add cards to supervisor overview page
- Reference: docs/10-ui-guidelines.md (Pages - /supervisor), docs/11-ui-phase4-mvp-plan.md (Stream C3)

**Dependencies:** UI-C1, UI-A13

**Acceptance Criteria:**
- [ ] SLO/quota cards display if endpoints exist
- [ ] Placeholders show if endpoints don't exist
- [ ] SLO metrics displayed correctly (if available)
- [ ] Quota usage displayed correctly (if available)
- [ ] Cards update on filter changes
- [ ] Loading skeleton shows during fetch
- [ ] Error handling displays error message

---

## Stream D: Config & Learning Console

### Issue UI-D1: Implement Config Browser with Domain Packs, Tenant Policy Packs, and Playbooks Views
**Labels:** `component:ui:config`, `phase:4`, `priority:high`
**Description:**
- Create `ConfigPage` component (`src/routes/ConfigPage.tsx`)
- Implement config type selector (tabs or dropdown):
  - Domain Packs tab
  - Tenant Policy Packs tab
  - Playbooks tab
- Implement Domain Packs view:
  - Wire to `GET /admin/config/domain-packs` API
  - Display pack list table: Pack ID, Name, Version, Tenant ID, Domain, Timestamp
  - Add filters (tenant, domain)
  - Click pack → Navigate to detail view
- Implement Tenant Policy Packs view:
  - Wire to `GET /admin/config/tenant-policies` API
  - Display policy list table (similar structure)
  - Add filters
  - Click policy → Navigate to detail view
- Implement Playbooks view:
  - Wire to `GET /admin/config/playbooks` API
  - Display playbook list table
  - Add filters
  - Click playbook → Navigate to detail view
- Integrate DataTable component (UI-A7) for pagination
- Reference: docs/10-ui-guidelines.md (Pages - /config), docs/11-ui-phase4-mvp-plan.md (Stream D1)

**Dependencies:** UI-A7, UI-A13

**Acceptance Criteria:**
- [ ] ConfigPage component created and routed
- [ ] Config type selector (tabs/dropdown) functional
- [ ] Domain Packs view displays list correctly
- [ ] Tenant Policy Packs view displays list correctly
- [ ] Playbooks view displays list correctly
- [ ] Filters apply correctly for each view
- [ ] Clicking item navigates to detail view
- [ ] Pagination works for all list views
- [ ] Loading skeleton shows during fetch
- [ ] Error handling displays error message

---

### Issue UI-D2: Implement Config Detail View with Formatted JSON Display
**Labels:** `component:ui:config`, `phase:4`, `priority:high`
**Description:**
- Create config detail view component (`src/components/config/ConfigDetailView.tsx`)
- Wire to `GET /admin/config/{type}/{id}` API (domain-packs, tenant-policies, playbooks)
- Display full configuration JSON:
  - Formatted with proper indentation
  - Syntax highlighting (use library like `react-syntax-highlighter`)
  - Read-only display (no edit buttons)
- Support navigation from list views
- Handle loading and error states
- Reference: docs/10-ui-guidelines.md (Pages - /config), docs/11-ui-phase4-mvp-plan.md (Stream D1)

**Dependencies:** UI-D1, UI-A13

**Acceptance Criteria:**
- [ ] ConfigDetailView component created
- [ ] Config detail displays formatted JSON
- [ ] Syntax highlighting works correctly
- [ ] Read-only display (no edit buttons visible)
- [ ] Data fetched from correct API endpoint based on config type
- [ ] Loading skeleton shows during fetch
- [ ] Error handling displays error message
- [ ] Navigation from list views works correctly

---

### Issue UI-D3: Implement Diff Viewer for Config Version Comparison
**Labels:** `component:ui:config`, `phase:4`, `priority:high`
**Description:**
- Add "Compare Versions" button to config detail view
- Create diff dialog/modal component (`src/components/config/ConfigDiffDialog.tsx`)
- Dialog allows selecting two versions (left and right dropdowns)
- Trigger `GET /admin/config/diff` API with version IDs and config type
- Display diff result:
  - Side-by-side comparison (left vs right)
  - Highlight differences (added, removed, changed) with color coding
  - Show structured differences summary
- Use diff library (e.g., `react-diff-viewer` or MUI-based solution)
- Display diff summary:
  - Number of additions
  - Number of deletions
  - Number of changes
- Reference: docs/10-ui-guidelines.md (Pages - /config), docs/11-ui-phase4-mvp-plan.md (Stream D2)

**Dependencies:** UI-D2, UI-A13

**Acceptance Criteria:**
- [ ] "Compare Versions" button added to config detail view
- [ ] ConfigDiffDialog component created
- [ ] Version selector dropdowns functional
- [ ] Diff API called with correct parameters
- [ ] Side-by-side comparison displays correctly
- [ ] Differences highlighted with color coding
- [ ] Diff summary shows change counts
- [ ] Loading skeleton shows during fetch
- [ ] Error handling displays error message

---

### Issue UI-D4: Implement Recommendations View (Read-Only)
**Labels:** `component:ui:config`, `phase:4`, `priority:medium`
**Description:**
- Create recommendations tab/section in ConfigPage
- Check if backend provides recommendation endpoints:
  - `GET /admin/config/recommendations/policy` (if exists)
  - `GET /admin/config/recommendations/severity` (if exists)
  - `GET /admin/config/recommendations/playbook` (if exists)
  - `GET /admin/config/recommendations/guardrail` (if exists)
- If endpoints exist:
  - Wire to recommendation APIs using TanStack Query hooks
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
- Reference: docs/10-ui-guidelines.md (Pages - /config), docs/11-ui-phase4-mvp-plan.md (Stream D3)

**Dependencies:** UI-D1, UI-A13

**Acceptance Criteria:**
- [ ] Recommendations tab/section created
- [ ] Recommendations display if endpoints exist
- [ ] Placeholder shows if endpoints don't exist
- [ ] Recommendation list displays all fields correctly
- [ ] All recommendations marked as read-only (no Apply buttons)
- [ ] "Review in Phase 5" message displayed
- [ ] Loading skeleton shows during fetch
- [ ] Error handling displays error message

---

## Summary

**Total Issues:** 34
**High Priority:** 28
**Medium Priority:** 4
**Low Priority:** 2

**Streams Covered:**
- Stream A: UI Foundation & Shell (13 issues)
- Stream B: Operator Console (8 issues)
- Stream C: Supervisor Dashboard (4 issues)
- Stream D: Config & Learning Console (4 issues)

**Key Dependencies:**
- UI-A1 through UI-A13 must be completed before Streams B, C, D
- Stream B depends on Stream A foundation
- Stream C depends on Stream A foundation
- Stream D depends on Stream A foundation

**Spec References:**
- docs/10-ui-guidelines.md - UI working principles and tech stack
- docs/11-ui-phase4-mvp-plan.md - Phase 4 UI MVP implementation plan
- docs/03-data-models-apis.md - Backend API schemas and data models
- Backend API routes: `src/api/routes/router_operator.py`, `router_supervisor_dashboard.py`, `router_config_view.py`, `router_explanations.py`, `router_simulation.py`


