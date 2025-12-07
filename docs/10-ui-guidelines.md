# UI Guidelines & Working Principles

## Purpose

The frontend is a professional operator and supervisor UI for the Agentic Exception Processing Platform backend. It serves as the primary interface for:

- **Operators**: Day-to-day exception monitoring, triage, and resolution oversight
- **Supervisors**: Cross-tenant oversight, escalations, policy violations, and optimization insights
- **Config Administrators**: Viewing and understanding Domain Packs, Tenant Policy Packs, and Playbooks

The UI must be:
- **Multi-tenant**: Fully aware of tenant context and isolation
- **Domain-agnostic**: No hard-coded finance/healthcare/retail logic; all domain concepts come from Domain Packs
- **Explainability-first**: Every exception decision must be explainable with timeline, evidence, and reasoning visible

---

## Tech Stack

### Core Framework & Build Tools
- **React 18** with TypeScript
- **Vite** for build tooling and dev server
- **react-router-dom** for client-side routing

### UI Component Library
- **Material UI (MUI)** v5+ for components, theming, and accessibility
- Leverage MUI's built-in ARIA support and keyboard navigation

### Data Fetching & State Management
- **TanStack Query (React Query)** for server state management, caching, and synchronization
- Context API for global UI state (tenant context, theme)

### Folder Structure

```
ui/
├── src/
│   ├── api/              # All REST API client functions
│   │   ├── exceptions.ts
│   │   ├── supervisor.ts
│   │   ├── config.ts
│   │   ├── explanations.ts
│   │   └── simulation.ts
│   ├── components/       # Reusable UI components
│   │   ├── common/       # Buttons, cards, dialogs, etc.
│   │   ├── exceptions/   # Exception-specific components
│   │   └── supervisor/  # Supervisor-specific components
│   ├── hooks/            # Custom React hooks
│   │   ├── useTenant.ts
│   │   ├── useExceptions.ts
│   │   └── useQuery.ts
│   ├── layouts/          # Layout components
│   │   ├── AppLayout.tsx
│   │   └── PageLayout.tsx
│   ├── routes/           # Route definitions and page components
│   │   ├── LoginPage.tsx
│   │   ├── ExceptionsPage.tsx
│   │   ├── ExceptionDetailPage.tsx
│   │   ├── SupervisorPage.tsx
│   │   └── ConfigPage.tsx
│   ├── theme/            # MUI theme configuration
│   │   └── theme.ts
│   ├── types/            # TypeScript type definitions
│   │   ├── api.ts
│   │   ├── exceptions.ts
│   │   └── config.ts
│   ├── utils/            # Utility functions
│   │   ├── httpClient.ts
│   │   ├── errorHandling.ts
│   │   └── formatters.ts
│   ├── App.tsx
│   └── main.tsx
├── public/
├── package.json
├── tsconfig.json
└── vite.config.ts
```

---

## UX Principles

### Operator-First Design
- **Fast answers**: Operators need to quickly answer:
  - "What is broken?" (exception summary, severity, type)
  - "Why?" (explanation, evidence, timeline)
  - "What do I do?" (suggested actions, playbook steps, approval status)
- **Progressive disclosure**: Show summary first, details on demand
- **Keyboard shortcuts**: Common actions accessible via keyboard

### Explainability Visible
- **Timeline view**: Visual timeline showing agent stages (Intake → Triage → Policy → Resolution → Feedback)
- **Evidence display**: RAG results, tool outputs, policy rules clearly shown
- **Explanation panel**: Natural language explanations for each decision
- **Audit trail**: Complete history of actions and decisions

### Multi-Tenant Awareness
- **No hard-coded domain logic**: All domain concepts (exception types, severity levels, etc.) come from backend APIs
- **Tenant context**: Tenant ID and domain selector always visible in top bar
- **Isolation indicators**: Visual indicators when switching tenants/domains

### Consistent Layout
- **App shell**: Sidebar navigation + top bar on all pages
- **Detail pages**: Summary section (left/top) + tabbed detail sections (right/bottom)
- **Standard patterns**: Consistent use of MUI components, spacing, typography

### Backend as Source of Truth
- **Read-only in Phase 4**: UI primarily displays data; no editing of packs/policies/playbooks
- **Simulation support**: "Re-run" and "what-if" buttons trigger backend simulation endpoints
- **Real-time updates**: Use SSE or polling for live status updates

### Accessibility Basics
- **No color-only indicators**: Use icons, text labels, or patterns in addition to color
- **Keyboard-friendly**: All interactive elements keyboard accessible
- **ARIA support**: Leverage MUI's built-in ARIA attributes; add custom ARIA where needed
- **Screen reader support**: Semantic HTML and proper heading hierarchy

---

## Layout

### App Shell Structure

```
┌─────────────────────────────────────────────────────────┐
│ Top Bar: [Logo] [Tenant Selector] [Domain] [Env Badge] │
├──────────┬──────────────────────────────────────────────┤
│          │                                              │
│ Sidebar  │  Main Content Area                          │
│          │                                              │
│ - Exceptions                                           │
│ - Supervisor                                           │
│ - Config                                               │
│          │                                              │
│          │                                              │
└──────────┴──────────────────────────────────────────────┘
```

### Exception Detail Page Layout

```
┌─────────────────────────────────────────────────────────┐
│ Exception Summary (Top/Left)                           │
│ - ID, Status, Severity, Type, Timestamp                │
│ - Source System, Domain                                │
│ - Quick Actions (Re-run, Approve, Escalate)            │
├─────────────────────────────────────────────────────────┤
│ Tabs (Right/Bottom):                                    │
│ [Timeline] [Evidence] [Explanation] [Audit]            │
│                                                         │
│ Tab Content Area                                        │
│ - Timeline: Agent stages with decisions                 │
│ - Evidence: RAG results, tool outputs, policy rules    │
│ - Explanation: Natural language reasoning              │
│ - Audit: Complete action history                       │
└─────────────────────────────────────────────────────────┘
```

---

## API Integration

### Base Configuration
- **Single base URL**: Read from environment variable `VITE_API_BASE_URL`
- **All REST calls**: Centralized in `ui/src/api/*.ts` files
- **Tenant context**: All API calls must include `tenantId` (from context, not hard-coded)

### HTTP Client Pattern
```typescript
// ui/src/utils/httpClient.ts
// Centralized axios/fetch wrapper with:
// - Base URL from env
// - Tenant ID injection
// - Error handling
// - Request/response interceptors
```

### Standard Patterns
- **Loading states**: Use MUI Skeleton components during data fetching
- **Error states**: Use MUI Snackbar for error notifications
- **Empty states**: Clear messaging when no data available
- **Pagination**: Standard pagination controls for list views

### API Endpoints (from Backend)

#### Operator UI APIs (`/ui/*`)
- `GET /ui/exceptions` - List exceptions with filters, pagination
- `GET /ui/exceptions/{exception_id}` - Exception detail with agent decisions
- `GET /ui/exceptions/{exception_id}/evidence` - Evidence chain (RAG, tools, policies)
- `GET /ui/exceptions/{exception_id}/audit` - Audit trail
- `POST /ui/exceptions/{exception_id}/rerun` - Trigger simulation rerun

#### Explanation APIs (`/explanations/*`)
- `GET /explanations/{exception_id}` - Get explanation in various formats
- `GET /explanations/{exception_id}/timeline` - Decision timeline

#### Supervisor APIs (`/ui/supervisor/*`)
- `GET /ui/supervisor/overview` - Overview dashboard
- `GET /ui/supervisor/escalations` - Escalated exceptions
- `GET /ui/supervisor/policy-violations` - Policy violations

#### Config APIs (`/admin/config/*`)
- `GET /admin/config/domain-packs` - List Domain Packs
- `GET /admin/config/domain-packs/{id}` - Domain Pack detail
- `GET /admin/config/tenant-policies` - List Tenant Policy Packs
- `GET /admin/config/playbooks` - List Playbooks
- `GET /admin/config/diff` - Diff two config versions

---

## Pages

### `/login`
- **Purpose**: Tenant and domain selection (no real auth in Phase 4)
- **Components**: Tenant dropdown, Domain dropdown, Environment selector
- **Flow**: Select tenant/domain → Set context → Navigate to `/exceptions`

### `/exceptions`
- **Purpose**: Exception list with filtering and search
- **Features**:
  - Filters: Severity, Status, Type, Date range, Source System
  - Pagination
  - Sort by timestamp, severity
  - Click row → Navigate to `/exceptions/:id`

### `/exceptions/:id`
- **Purpose**: Exception detail with full explainability
- **Sections**:
  - **Summary**: Key fields, status, quick actions
  - **Timeline Tab**: Agent stages with decisions and timestamps
  - **Evidence Tab**: RAG results, tool outputs, policy rules
  - **Explanation Tab**: Natural language explanation
  - **Audit Tab**: Complete audit trail
- **Actions**: Re-run simulation button (triggers POST `/ui/exceptions/{id}/rerun`)

### `/supervisor`
- **Purpose**: Supervisor dashboard
- **Tabs**:
  - **Overview**: High-level metrics, counts, optimization suggestions summary
  - **Escalations**: List of escalated exceptions
  - **Policy Violations**: List of policy violations
- **Optional**: SLO/quota summary cards if backend endpoints exist

### `/config`
- **Purpose**: Configuration browser and diff viewer
- **Features**:
  - Browse Domain Packs, Tenant Policy Packs, Playbooks
  - View configuration details (read-only)
  - Diff viewer for version comparison
  - Read-only recommendations view (policy/severity/playbook/guardrail suggestions)

---

## Non-Goals (Phase 4)

### Authentication & Authorization
- **No real auth/SSO**: Phase 4 uses simple tenant/domain selector
- **No RBAC**: All users see all data for selected tenant
- **No session management**: Context stored in memory/localStorage only

### Configuration Editing
- **No editing**: All config views are read-only
- **No pack upload**: Pack management remains backend/admin API only
- **No policy editing**: Policy changes remain backend/admin API only

### AI Co-Pilot
- **No chat interface**: Natural language interaction API exists in backend but no UI in Phase 4
- **No conversational assistant**: This is Phase 5 scope

### Advanced Features
- **No real-time collaboration**: No multi-user editing or live updates
- **No mobile app**: Web UI only, responsive design for tablets
- **No offline mode**: Requires backend connection

---

## How Cursor Should Use This Doc

When implementing UI features:

1. **Reference this doc first**: Check tech stack, folder structure, and UX principles before coding
2. **Follow folder structure**: Place files in correct directories (`api/`, `components/`, `routes/`, etc.)
3. **Use MUI components**: Prefer MUI over custom components unless MUI doesn't meet requirements
4. **Tenant context**: Always include `tenantId` in API calls; use TenantContext hook
5. **Explainability**: Every exception detail page must show timeline, evidence, explanation, audit
6. **Read-only in Phase 4**: Don't add edit/delete buttons for configs unless explicitly requested
7. **Accessibility**: Use MUI's accessibility features; test keyboard navigation
8. **Error handling**: Use standard loading/error patterns (skeletons, snackbars)
9. **Type safety**: Define TypeScript types in `types/` matching backend API responses
10. **API integration**: Add new API client functions in `api/` directory, use TanStack Query for data fetching


