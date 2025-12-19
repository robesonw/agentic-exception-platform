# Phase 11 Batch 1 - Local Verification Checklist

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
   VITE_ADMIN_ENABLED=false
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

## Verification Steps

### 1. Navigation & Access Control ✅

**Test Navigation:**
- [ ] Open http://localhost:5173 (or your Vite dev port)
- [ ] Verify left sidebar shows "Ops" section with sub-items:
  - Overview
  - Workers
  - SLA
  - DLQ
  - Alerts
  - Reports
- [ ] Verify "Admin" section is NOT visible (VITE_ADMIN_ENABLED=false)

**Test Route Protection:**
- [ ] Navigate to `/ops` - should load Ops Overview page
- [ ] Set `VITE_OPS_ENABLED=false` in `ui/.env` and restart dev server
- [ ] Refresh page - "Ops" section should disappear from nav
- [ ] Try navigating directly to `/ops` - should show "Not authorized" page
- [ ] Set `VITE_OPS_ENABLED=true` again and restart

### 2. Ops Overview Page (`/ops`) ✅

**Test Page Load:**
- [ ] Navigate to `/ops`
- [ ] Verify page header shows "Operations Overview"
- [ ] Verify 8 metric widgets display:
  - Worker Health (X/Y workers)
  - Throughput (events/min)
  - Error Rate (%)
  - SLA Compliance (%)
  - SLA Breached (count)
  - DLQ Size (count)
  - Alerts Fired (last 24h)
  - Report Jobs (queued/completed/failed)

**Test Widgets:**
- [ ] Click "View details →" on Worker Health widget → should navigate to `/ops/workers`
- [ ] Click "View details →" on SLA Compliance widget → should navigate to `/ops/sla`
- [ ] Click "View details →" on DLQ Size widget → should navigate to `/ops/dlq`
- [ ] Verify refresh button (top right) triggers data refetch

**Test Loading States:**
- [ ] Disconnect backend or set wrong API URL in `ui/.env`
- [ ] Refresh page - should show loading spinner, then error
- [ ] Reconnect backend - should show data

**Test Tenant Context:**
- [ ] Clear `tenantId` from localStorage
- [ ] Refresh `/ops` page - should show warning "Please select a tenant"
- [ ] Set `tenantId` in localStorage - should load data

### 3. Shared Components ✅

**DataTable:**
- [ ] Navigate to any page with a table (e.g., `/ops/dlq` when implemented)
- [ ] Verify export button (download icon) appears in table toolbar
- [ ] Click export button - should download CSV file
- [ ] Verify column visibility button (view column icon) appears
- [ ] Click column visibility - should show menu with checkboxes
- [ ] Toggle column visibility - column should show/hide

**OpsFilterBar:**
- [ ] Navigate to a page with filters (e.g., `/ops/dlq` when implemented)
- [ ] Change a filter value (e.g., status dropdown)
- [ ] Verify URL updates with query parameter (e.g., `?status=pending`)
- [ ] Refresh page - filter value should persist from URL
- [ ] Clear filter - URL parameter should be removed

**ConfirmDialog:**
- [ ] Navigate to DLQ page (when implemented)
- [ ] Click "Retry" or "Discard" button
- [ ] Verify confirmation dialog appears
- [ ] Verify dialog shows warning icon for destructive actions
- [ ] Click "Cancel" - dialog should close, no action taken
- [ ] Click "Confirm" - action should execute

**CodeViewer:**
- [ ] Navigate to DLQ detail (when implemented)
- [ ] Verify JSON payload displays with syntax highlighting
- [ ] Click "Copy" button - should copy JSON to clipboard
- [ ] Verify "Copied!" tooltip appears
- [ ] If payload is large, verify expand/collapse works

### 4. API Client ✅

**Test API Calls:**
- [ ] Open browser DevTools → Network tab
- [ ] Navigate to `/ops` page
- [ ] Verify API calls include:
  - `tenant_id` query parameter
  - `X-Tenant-Id` header
  - `X-API-KEY` header (if auth enabled)
- [ ] Verify API calls go to correct endpoints:
  - `/ops/workers/health`
  - `/ops/workers/throughput`
  - `/ops/sla/compliance`
  - `/ops/sla/at-risk`
  - `/ops/dlq`
  - `/alerts/history`
  - `/audit/reports`

**Test Error Handling:**
- [ ] Set wrong API URL in `ui/.env`
- [ ] Navigate to `/ops`
- [ ] Verify error snackbar/toast appears
- [ ] Verify error message is user-friendly (not raw API error)

### 5. Remaining Pages (To Be Implemented)

**Workers Dashboard (`/ops/workers`):**
- [ ] Navigate to `/ops/workers`
- [ ] Verify worker list table displays
- [ ] Verify columns: worker type, instance ID, status, last check, version, host
- [ ] Verify unhealthy workers highlighted
- [ ] Click refresh button - data should refetch

**SLA Dashboard (`/ops/sla`):**
- [ ] Navigate to `/ops/sla`
- [ ] Verify SLA compliance percentage displayed
- [ ] Verify breached exceptions table
- [ ] Verify at-risk exceptions table
- [ ] Click exception ID - should navigate to exception detail
- [ ] Test filters (tenant, domain, exception type, date range)

**DLQ Management (`/ops/dlq`):**
- [ ] Navigate to `/ops/dlq`
- [ ] Verify DLQ entries table
- [ ] Click entry row - detail drawer should open
- [ ] Verify payload displayed in CodeViewer
- [ ] Click "Retry" - ConfirmDialog should appear
- [ ] Confirm retry - entry should retry
- [ ] Click "Discard" - ConfirmDialog should appear
- [ ] Confirm discard - entry should be discarded
- [ ] Test batch retry (select multiple, retry batch)

**Alerts Config (`/ops/alerts`):**
- [ ] Navigate to `/ops/alerts`
- [ ] Verify alert configs table
- [ ] Click "Create" - form should open
- [ ] Fill form and submit - config should be created
- [ ] Click "Edit" - form should open with existing values
- [ ] Verify notification channels table
- [ ] Click "Test" on channel - test notification should send

**Alerts History (`/ops/alerts/history`):**
- [ ] Navigate to `/ops/alerts/history`
- [ ] Verify alerts history table
- [ ] Click alert row - detail modal should open
- [ ] Click "Acknowledge" - alert status should update
- [ ] Click "Resolve" - alert status should update
- [ ] Test filters (time range, severity, status)

**Audit Reports (`/ops/reports`):**
- [ ] Navigate to `/ops/reports`
- [ ] Fill report request form (type, date range, format)
- [ ] Click "Generate Report" - report job should be created
- [ ] Verify report appears in jobs list
- [ ] Wait for report to complete (or check status)
- [ ] Click "Download" on completed report - file should download
- [ ] Verify failed reports show error reason

## Common Issues & Solutions

**Issue: Ops menu not showing**
- Solution: Check `VITE_OPS_ENABLED=true` in `ui/.env` and restart dev server

**Issue: "Not authorized" page when accessing `/ops`**
- Solution: Ensure `VITE_OPS_ENABLED=true` in `ui/.env` and tenantId is set in localStorage

**Issue: API calls failing with 401/403**
- Solution: Set `apiKey` in localStorage or check backend authentication config

**Issue: API calls missing tenant_id**
- Solution: Set `tenantId` in localStorage (should be set automatically via TenantProvider)

**Issue: Data not loading**
- Solution: Check browser console for errors, verify backend is running, check Network tab for API responses

## Performance Checks

- [ ] Ops Overview page loads within 2-3 seconds
- [ ] Auto-refresh doesn't cause UI flicker
- [ ] Table pagination works smoothly
- [ ] Filters update without full page reload
- [ ] Export downloads complete quickly

## Browser Compatibility

Test in:
- [ ] Chrome/Edge (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest) - if Mac available

## Mobile Responsiveness

- [ ] Test on mobile viewport (DevTools device emulation)
- [ ] Verify navigation drawer works on mobile
- [ ] Verify filters stack vertically on mobile
- [ ] Verify tables scroll horizontally on mobile

## Next Steps After Verification

1. Implement remaining pages (P11-7 through P11-12) following patterns in `PHASE11_BATCH1_IMPLEMENTATION.md`
2. Add unit tests for core components
3. Implement Batch 2 (Admin UI + Usage/Rate Limits)

