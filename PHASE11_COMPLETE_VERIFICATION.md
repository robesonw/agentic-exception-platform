# Phase 11 Complete - Verification Checklist

## Prerequisites

1. **Backend Running:**
   ```bash
   # Ensure Phase 10 backend APIs are running
   # Backend should be accessible at http://localhost:8000
   ```

2. **Environment Variables:**
   Add to `ui/.env`:
   ```bash
   VITE_OPS_ENABLED=true
   VITE_ADMIN_ENABLED=true
   VITE_API_BASE_URL=http://localhost:8000
   ```

3. **Start UI Dev Server:**
   ```bash
   cd ui
   npm install  # If needed
   npm run dev
   ```

4. **Set Tenant Context:**
   - Open browser DevTools → Application → Local Storage
   - Set `tenantId` to a valid tenant (e.g., `tenant_001`)
   - Set `apiKey` if backend requires authentication

## Feature Flags Verification

- [ ] Set `VITE_OPS_ENABLED=false` in `ui/.env` → Ops menu disappears, `/ops` shows "Not authorized"
- [ ] Set `VITE_OPS_ENABLED=true` in `ui/.env` → Ops menu appears, `/ops` loads
- [ ] Set `VITE_ADMIN_ENABLED=false` in `ui/.env` → Admin menu disappears, `/admin` shows "Not authorized"
- [ ] Set `VITE_ADMIN_ENABLED=true` in `ui/.env` → Admin menu appears, `/admin` loads

## Ops Pages Verification

### Ops Overview (`/ops`)
- [ ] Page loads and displays 8 metric widgets
- [ ] Widgets show real data (not placeholders)
- [ ] "View details →" links navigate correctly
- [ ] Refresh button updates data
- [ ] Auto-refresh works (wait 30-60 seconds)
- [ ] Loading state shows during initial load
- [ ] Error state shows if backend unavailable

### Usage Metering (`/ops/usage`)
- [ ] Page loads and displays usage summary cards
- [ ] Period selector works (day/week/month)
- [ ] Detailed usage table displays
- [ ] Filters work (date range, resource type)
- [ ] Export CSV button downloads file
- [ ] Export JSON button downloads file
- [ ] Data is real (not mocked)

### Rate Limits (`/ops/rate-limits`)
- [ ] Page loads and displays rate limits table
- [ ] Utilization progress bars display correctly
- [ ] Non-admin users see view-only mode
- [ ] Admin users see "Edit" buttons
- [ ] Edit dialog opens and allows limit update
- [ ] Confirm dialog appears before update
- [ ] Update succeeds and table refreshes

## Admin Pages Verification

### Admin Landing (`/admin`)
- [ ] Page loads and displays quick link cards
- [ ] Pending approvals count displays (if any)
- [ ] Quick links navigate to correct pages
- [ ] Cards are clickable and navigate

### Config Change Governance (`/admin/config-changes`)
- [ ] Page loads and displays config changes list
- [ ] Filters work (status, change type)
- [ ] "View" button opens detail dialog
- [ ] Detail dialog shows:
  - [ ] Config diff (if available)
  - [ ] Proposed configuration
  - [ ] Requestor information
- [ ] "Approve" button shows confirm dialog
- [ ] Approve succeeds and list updates
- [ ] "Reject" button opens reject dialog with comment field
- [ ] Reject with comment succeeds and list updates
- [ ] Non-admin users cannot approve/reject

### Packs Management (`/admin/packs`)
- [ ] Page loads with Domain Packs / Tenant Packs tabs
- [ ] Tab switching works
- [ ] Pack list displays correctly
- [ ] Active version indicator shows
- [ ] "View" button opens detail dialog
- [ ] Detail dialog shows full pack JSON
- [ ] "Activate" button shows confirm dialog
- [ ] Activation succeeds and active indicator updates
- [ ] Filters work (domain)

### Playbooks Management (`/admin/playbooks`)
- [ ] Page loads and displays playbooks list
- [ ] Filters work (tenant, domain, exception type)
- [ ] "View" button opens detail dialog
- [ ] Detail dialog shows:
  - [ ] Match rules
  - [ ] Steps
  - [ ] Referenced tools
- [ ] "Activate"/"Deactivate" button shows confirm dialog
- [ ] Activation/deactivation succeeds and status updates

### Tools Management (`/admin/tools`)
- [ ] Page loads and displays tools list
- [ ] Filters work (provider, enabled status)
- [ ] "View" button opens detail dialog
- [ ] Detail dialog shows:
  - [ ] Tool schema
  - [ ] Provider information
  - [ ] Allowed tenants
- [ ] "Enable"/"Disable" button shows confirm dialog
- [ ] Enable/disable succeeds and status updates
- [ ] Tool name links to `/tools/:id` page

## Shared Components Verification

### DataTable
- [ ] Export button appears in toolbar
- [ ] Export CSV downloads file
- [ ] Column visibility button appears (if onColumnVisibilityChange provided)
- [ ] Column visibility menu works
- [ ] Toggling columns shows/hides columns
- [ ] Loading skeleton shows during fetch
- [ ] Empty state shows when no data

### OpsFilterBar
- [ ] Filters display correctly
- [ ] Changing filter updates URL query params
- [ ] Refreshing page restores filters from URL
- [ ] Clearing filter removes URL param

### ConfirmDialog
- [ ] Dialog appears when open
- [ ] Title and message display correctly
- [ ] "Cancel" button closes dialog without action
- [ ] "Confirm" button executes action
- [ ] Loading state disables buttons
- [ ] Destructive actions show error color

### CodeViewer
- [ ] JSON displays with syntax highlighting
- [ ] Copy button copies to clipboard
- [ ] "Copied!" tooltip appears
- [ ] Expand/collapse works (if collapsible)
- [ ] Pretty-printed JSON format

## API Integration Verification

### Tenant Context
- [ ] All API calls include `tenant_id` query parameter
- [ ] All API calls include `X-Tenant-Id` header
- [ ] API calls use correct endpoints from Phase 10

### Error Handling
- [ ] API errors show snackbar notifications
- [ ] Error messages are user-friendly
- [ ] Loading states show during API calls
- [ ] Error states display properly

## Integration Tests

Run tests:
```bash
cd ui
npm test
```

- [ ] ProtectedRoute tests pass
- [ ] ConfirmDialog tests pass
- [ ] Admin API client tests pass

## Documentation

- [ ] `docs/STATE_OF_THE_PLATFORM.md` updated with Phase 11
- [ ] `docs/ops-ui-guide.md` created and complete
- [ ] `docs/admin-ui-guide.md` created and complete
- [ ] Feature flags documented
- [ ] All new routes documented

## Final Checklist

- [ ] All pages load without errors
- [ ] All pages show real data (no placeholders)
- [ ] All filters work and sync with URL
- [ ] All admin actions require confirmation
- [ ] All admin actions are role-gated
- [ ] Tenant context applied everywhere
- [ ] Loading states consistent
- [ ] Error states consistent
- [ ] Dark theme consistent
- [ ] Navigation works correctly
- [ ] Route protection works correctly
- [ ] Tests pass

## Known Limitations

- Workers, SLA, DLQ, Alerts, Reports pages from Batch 1 are placeholders (to be implemented)
- Some backend endpoints may not be fully implemented yet (UI handles gracefully)
- RBAC integration is placeholder (feature flags are primary gate)

## Next Steps

1. Complete remaining Batch 1 pages (Workers, SLA, DLQ, Alerts, Reports)
2. Add more comprehensive integration tests
3. Enhance RBAC integration when backend RBAC is available
4. Add more advanced features (charts, real-time updates, etc.)

