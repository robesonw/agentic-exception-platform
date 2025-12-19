# Ops UI Demo Checklist

This document provides a guide for demonstrating the Operations UI to stakeholders. It includes a suggested flow, what to click on each page, what "good" looks like, and troubleshooting tips if pages appear empty.

## Demo Flow (Suggested Order)

### 1. Operations Overview (`/ops`)
**Purpose**: High-level health dashboard

**What to Show:**
- Health Summary section showing:
  - Workers Healthy count
  - SLA Breached count
  - DLQ Size
  - Alerts Fired (24h)
- Main metrics grid with key operational metrics
- Click "Refresh" button to demonstrate real-time updates
- Click any metric widget to navigate to detail page

**What "Good" Looks Like:**
- All health summary metrics display values (not "—")
- Green indicators for healthy states
- Red/orange indicators for issues (if any)
- Last updated timestamp shows recent data
- Metric widgets are clickable and navigate correctly

**If Empty/Troubleshooting:**
- **Workers showing 0**: Start worker containers/services
- **SLA metrics showing "—"**: Ensure tenant has SLA policies configured
- **DLQ showing "—"**: Check if DLQ service is running
- **Alerts showing "—"**: Verify alerts service is running and tenant has alert configs

---

### 2. Workers Health & Status (`/ops/workers`)
**Purpose**: Monitor worker instances and throughput

**What to Show:**
- Health Status tab:
  - Click on column headers to demonstrate sorting
  - Show status chips (healthy=green, degraded=orange, unhealthy=red)
  - Demonstrate pagination
- Throughput tab:
  - Show events/sec metrics
  - Show latency percentiles (P50, P95, P99)
  - Show error rates with color coding
- Click refresh button to show data updates
- Show "Last updated" timestamp

**What "Good" Looks Like:**
- Workers table shows at least one worker with "healthy" status
- Throughput shows positive events/sec values
- Error rates are low (green chips)
- All columns sort correctly
- Empty state (if no workers): "No workers reporting. Start worker containers to see heartbeats."

**If Empty/Troubleshooting:**
- **No workers in table**: Start worker containers/services that register with the platform
- **All workers unhealthy**: Check worker service logs, verify connectivity
- **No throughput data**: Workers need to process events to generate throughput metrics

---

### 3. SLA Compliance & Breaches (`/ops/sla`)
**Purpose**: Monitor SLA compliance and breach incidents

**What to Show:**
- Compliance summary cards (Rate, Breaches, At Risk)
- Breaches tab:
  - Use FilterBar to filter by date range
  - Show severity chips (CRITICAL=red, HIGH=orange)
  - Demonstrate sorting
- At Risk tab:
  - Show exceptions approaching SLA deadline
  - Time until deadline column
- Change period dropdown (day/week/month) to show different compliance rates
- Click refresh button

**What "Good" Looks Like:**
- Compliance rate card shows a percentage (e.g., "95.2%")
- Breaches table shows exceptions that have breached SLA (if any)
- At Risk table shows exceptions nearing deadline (if any)
- All status chips color-coded appropriately
- Empty states: "No SLA breaches found in the selected time range." or "No exceptions are currently at risk of SLA breach."

**If Empty/Troubleshooting:**
- **No compliance data**: Ensure tenant has SLA policies configured and exceptions processed
- **No breaches**: This is actually good! Means SLA is being met
- **"—" in summary cards**: Verify SLA service is running and tenant context is correct

---

### 4. Dead Letter Queue (DLQ) (`/ops/dlq`)
**Purpose**: View and manage failed messages

**What to Show:**
- DLQ entries table with status chips
- Click on Event ID to open detail drawer
- Detail drawer shows:
  - Full event metadata
  - Payload (CodeViewer with JSON)
  - Event metadata (CodeViewer)
  - Retry and Discard buttons
- Use FilterBar to filter by status or event type
- Demonstrate Retry action (with ConfirmDialog)
- Demonstrate Discard action (with ConfirmDialog and toast notification)
- Show refresh button and last updated timestamp

**What "Good" Looks Like:**
- Table shows DLQ entries (if any failures occurred)
- Status chips: pending=red, retrying=orange, succeeded=green, discarded=gray
- Detail drawer opens smoothly with all metadata
- Retry/Discard actions show confirmation dialogs
- Toast notifications appear on success/failure
- Empty state: "No messages in DLQ. Trigger a failing exception to populate DLQ."

**If Empty/Troubleshooting:**
- **No DLQ entries**: This is good! Means no failures. To demonstrate DLQ, trigger a failing exception or simulate an error
- **Detail drawer empty**: Check that DLQ service is running and entry details endpoint works

---

### 5. Alerts History (`/ops/alerts/history`)
**Purpose**: View alert history and manage alert status

**What to Show:**
- Alerts table with severity and status chips
- Use FilterBar to filter by date range, status, type, severity
- Click on Alert ID to open detail drawer
- Detail drawer shows:
  - Full alert metadata
  - Payload (CodeViewer)
  - Acknowledge and Resolve buttons
- Demonstrate Acknowledge action (toast notification)
- Demonstrate Resolve action (toast notification)
- Show refresh button and sorting

**What "Good" Looks Like:**
- Table shows alerts (if any have fired)
- Severity chips: CRITICAL=red, HIGH=orange
- Status chips: fired=red, acknowledged=blue, resolved=green
- Detail drawer shows complete alert information
- Actions work with toast feedback
- Empty state: "No alerts fired in selected range."

**If Empty/Troubleshooting:**
- **No alerts**: This could be good (no issues) or means alerts aren't configured. Check `/ops/alerts` to configure alert rules
- **Alerts not firing**: Verify alert configs are enabled and thresholds are set correctly

---

### 6. Audit Reports (`/ops/reports`)
**Purpose**: Generate and download audit reports

**What to Show:**
- Click "Request Report" button
- Request dialog:
  - Select report type (Exception Activity, Tool Execution, etc.)
  - Set date range
  - Select format (CSV/JSON)
  - Submit request
- Reports table shows:
  - Status chips (queued=gray, generating=orange, completed=green, failed=red)
  - Download button (enabled when completed)
- Click on Report ID to open detail drawer
- Detail drawer shows:
  - Report parameters
  - Download link
- Demonstrate download action
- Show refresh button and sorting
- Filter by status dropdown

**What "Good" Looks Like:**
- Request dialog allows creating new report requests
- Reports table shows report requests with appropriate status
- Completed reports have download buttons
- Detail drawer shows full report metadata
- Empty state: "No reports yet. Create a report request above."

**If Empty/Troubleshooting:**
- **No reports**: Click "Request Report" to create one. Reports are generated asynchronously
- **Reports stuck in "generating"**: Check report generation service/logs
- **Download fails**: Verify report storage/service is accessible

---

### 7. Usage Metering (`/ops/usage`)
**Purpose**: Track resource consumption

**What to Show:**
- Summary cards showing resource type counts
- Change period dropdown (day/week/month)
- Use FilterBar:
  - Select metric type (api_calls, exceptions, tool_executions)
  - Set date range
- Details table shows breakdown by date and resource type
- Export buttons (CSV/JSON) with toast notifications
- Show refresh button

**What "Good" Looks Like:**
- Summary cards show counts for each resource type
- Details table populates when metric type and date range selected
- Export downloads file successfully
- Empty state (if no filters): "Select a metric type and date range above to view detailed usage breakdown."

**If Empty/Troubleshooting:**
- **No summary data**: Ensure usage tracking service is running and collecting metrics
- **Details table empty**: Select both metric type AND date range in FilterBar
- **Export fails**: Check browser console and verify export service is accessible

---

### 8. Rate Limits (`/ops/rate-limits`)
**Purpose**: View/manage rate limit configurations

**What to Show:**
- Rate limits table showing:
  - Limit type, value, window
  - Current usage with progress bars
  - Utilization percentage chips
  - Status (enabled/disabled)
- For admins: Edit button to update limits
- Edit dialog:
  - Change limit value
  - Confirm update (ConfirmDialog)
  - Toast notification on success
- Show refresh button
- View-only mode for non-admins (info alert)

**What "Good" Looks Like:**
- Table shows all configured rate limits
- Usage progress bars show current utilization (green/yellow/red)
- Utilization chips color-coded appropriately
- Edit functionality works (if admin)
- Empty state: "No rate limits are currently configured for this tenant."

**If Empty/Troubleshooting:**
- **No rate limits**: Rate limits may not be configured. Check admin configuration
- **Usage not updating**: Verify rate limit tracking service is running

---

### 9. Alerts Configuration (`/ops/alerts`)
**Purpose**: Configure alert rules and channels

**What to Show:**
- Alert Rules tab:
  - Create alert rule button
  - Rules table with enabled/disabled status
  - Edit and delete actions
  - ConfirmDialog for deletions
- Channels tab:
  - Create channel button
  - Channels table with verified/unverified status
  - Verify button for unverified channels
  - Delete action
- Show refresh button
- Toast notifications for all actions

**What "Good" Looks Like:**
- Tables show configured rules and channels
- Status chips: Enabled=green, Disabled=gray, Verified=green, Unverified=orange
- Create/Edit dialogs work correctly
- Deletions require confirmation
- Empty states: "No alert rules are currently configured. Create an alert rule to get started." and "No alert channels are currently configured. Create an alert channel to receive notifications."

**If Empty/Troubleshooting:**
- **No rules/channels**: Create them using the "Create" buttons
- **Channels not verifying**: Check channel configuration (webhook URL, email address, etc.)

---

## Common UI Patterns to Highlight

### Consistent Page Shell
- Every page has: Title, Subtitle, Last Updated timestamp, Refresh button
- Refresh button invalidates queries and refetches data
- Last Updated shows when data was last fetched

### Consistent Table UX
- All tables support: sorting (click column headers), pagination, empty states
- Empty states include: icon, title, helpful description
- Error states show clear error messages

### Status Indicators
- **Worker status**: healthy (green), degraded (orange), unhealthy (red)
- **SLA**: breached (red), at-risk (orange), ok (green)
- **Alerts**: fired (red), acknowledged (blue), resolved (green)
- **Reports**: queued (gray), generating (orange), completed (green), failed (red)

### Action Safety
- Destructive actions (delete, discard) require ConfirmDialog
- All mutations show toast notifications (success/error)
- Loading states during operations
- Queries refetch after mutations

### Detail Drawers/Modals
- DLQ: Full entry details, payload viewer, actions
- Alerts History: Full alert details, payload viewer, actions
- Reports: Full report details, download link

---

## Services to Start for Full Demo

If pages appear empty, ensure these services are running:

1. **Worker Service**: For `/ops/workers` to show worker health/throughput
2. **SLA Service**: For `/ops/sla` to show compliance data
3. **DLQ Service**: For `/ops/dlq` to show failed messages
4. **Alerts Service**: For `/ops/alerts` and `/ops/alerts/history`
5. **Reports Service**: For `/ops/reports` to generate/download reports
6. **Usage Service**: For `/ops/usage` to show resource consumption
7. **Rate Limits Service**: For `/ops/rate-limits` to show limit configurations

**Quick Check**: If all services are running but data is still empty, verify:
- Tenant context is correctly set
- Tenant has data (exceptions, events, etc.)
- Date ranges are appropriate
- Feature flags are enabled (`VITE_OPS_ENABLED=true`)

---

## Demo Best Practices

1. **Start with Overview**: Always begin at `/ops` to show overall health
2. **Use Real Data**: If possible, use a tenant with actual operational data
3. **Demonstrate Actions**: Show at least one create/edit/delete action per page
4. **Show Empty States**: Demonstrate that empty != broken (helpful messages)
5. **Test Refresh**: Click refresh on a few pages to show real-time updates
6. **Navigate Between Pages**: Use the navigation links to show interconnectedness
7. **Handle Errors Gracefully**: If something fails, show how errors are displayed

---

## Troubleshooting Quick Reference

| Page | If Empty | Service to Check |
|------|----------|------------------|
| `/ops` | All metrics show "—" | All services |
| `/ops/workers` | No workers | Worker service |
| `/ops/sla` | No compliance data | SLA service + tenant config |
| `/ops/dlq` | No entries | DLQ service + trigger failures |
| `/ops/alerts/history` | No alerts | Alerts service + alert configs |
| `/ops/reports` | No reports | Reports service (create a request) |
| `/ops/usage` | No summary | Usage service |
| `/ops/rate-limits` | No limits | Rate limits service + config |
| `/ops/alerts` | No rules/channels | Create via UI |

---

## Notes for Presenters

- All pages are tenant-aware: ensure a tenant is selected
- No backend changes were made for Phase 11; all improvements are UI-only
- Empty states are demo-friendly: they explain what the data represents, not just "no data"
- All actions have user feedback: toasts for success/error, confirmations for destructive actions
- Refresh functionality works across all pages to demonstrate real-time capabilities

