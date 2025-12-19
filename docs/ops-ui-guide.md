# Ops UI Guide

## Overview

The Ops UI provides operational dashboards and management tools for monitoring system health, SLA compliance, DLQ management, alerting, and usage tracking. All Ops pages are protected by the `VITE_OPS_ENABLED` feature flag.

## Access Control

- **Feature Flag**: Set `VITE_OPS_ENABLED=true` in `ui/.env` to enable Ops menu and routes
- **Route Protection**: Accessing `/ops/*` routes without the flag enabled shows "Not authorized" page
- **Tenant Context**: All pages require a tenant to be selected (via tenant selector in header)

## Pages

### Ops Overview (`/ops`)

**Purpose**: At-a-glance view of system health and operational metrics

**Widgets**:
- Worker Health: Healthy/degraded/unhealthy worker counts
- Throughput: Events per minute across all workers
- Error Rate: Average error rate percentage
- SLA Compliance: Compliance percentage for current period
- SLA Breached: Count of exceptions that breached SLA
- DLQ Size: Number of failed events in Dead Letter Queue
- Alerts Fired: Count of alerts triggered in last 24 hours
- Report Jobs: Queued/completed/failed report generation jobs

**Actions**:
- Click "View details →" on any widget to navigate to the relevant detailed page
- Refresh button (top right) manually refreshes all metrics
- Auto-refresh: Metrics update every 30-60 seconds

### Workers Dashboard (`/ops/workers`)

**Purpose**: Monitor worker fleet health and performance

**Features**:
- Worker list table with status, last heartbeat, version, host
- Throughput metrics per worker type
- Latency percentiles (p50, p95, p99)
- Error counts and error rates
- Unhealthy workers highlighted with last error reason
- Refresh button to manually update data

**Usage**:
1. Navigate to `/ops/workers`
2. Review worker health status (healthy/degraded/unhealthy)
3. Check throughput and latency metrics
4. Investigate unhealthy workers by viewing error details

### SLA Dashboard (`/ops/sla`)

**Purpose**: Monitor SLA compliance and identify breaches

**Features**:
- SLA compliance percentage (prominent display)
- Breached exceptions table with filters
- At-risk exceptions table (approaching deadline)
- Optional resolution time distribution chart
- Filters: tenant, domain, exception type, date range
- Click exception ID to navigate to exception detail

**Usage**:
1. Navigate to `/ops/sla`
2. Review compliance percentage
3. Filter breached exceptions by tenant/domain/type
4. Review at-risk exceptions to take preventive action
5. Click exception ID to view full details

### DLQ Management (`/ops/dlq`)

**Purpose**: View and manage dead-lettered events

**Features**:
- DLQ entries table with filters (tenant, event type, status, date range)
- Entry detail drawer/modal showing:
  - Full message payload (JSON with syntax highlighting)
  - Correlation ID / Exception ID
  - Error stack trace (if available)
  - Retry history
- Actions (role-gated):
  - Retry single entry (with confirmation)
  - Batch retry (select multiple, retry batch)
  - Discard entry (with confirmation)

**Usage**:
1. Navigate to `/ops/dlq`
2. Apply filters to find specific entries
3. Click entry row to view full details
4. Review payload and error reason
5. Retry or discard entries as needed (requires operator/admin role)

**Best Practices**:
- Review failure reasons before retrying
- Check retry count to avoid infinite retry loops
- Discard only when entry is known to be invalid

### Alerts Configuration (`/ops/alerts`)

**Purpose**: Configure alert rules and notification channels

**Features**:
- Alert configs list table
- Create/edit alert form:
  - Alert type (SLA_BREACH, DLQ_GROWTH, WORKER_UNHEALTHY, etc.)
  - Threshold value and unit
  - Notification channels
  - Enabled toggle
- Notification channels table
- Create/edit channel form:
  - Channel type (webhook, email)
  - Configuration (URL, email address)
  - Test notification button

**Usage**:
1. Navigate to `/ops/alerts`
2. Review existing alert configurations
3. Create new alert rule:
   - Click "Create" button
   - Select alert type
   - Set threshold
   - Select notification channels
   - Enable and save
4. Configure notification channels:
   - Add webhook URL or email address
   - Test notification to verify
   - Save channel

### Alerts History (`/ops/alerts/history`)

**Purpose**: View past alerts and manage their status

**Features**:
- Alerts history table with filters (time range, severity, status, alert type)
- Alert detail modal showing:
  - Full alert details
  - Condition that fired
  - Notification delivery status
- Actions:
  - Acknowledge alert
  - Resolve alert

**Usage**:
1. Navigate to `/ops/alerts/history`
2. Apply filters to find specific alerts
3. Click alert row to view details
4. Acknowledge or resolve alerts as appropriate

### Audit Reports (`/ops/reports`)

**Purpose**: Generate and download compliance reports

**Features**:
- Report request form:
  - Report type selector (Exception Activity, Tool Execution, Policy Decisions, Config Changes, SLA Compliance)
  - Tenant selector (admin only)
  - Domain selector
  - Date range picker
  - Format selector (CSV, JSON)
- Generated reports table:
  - Status (queued, generating, completed, failed)
  - Download link (when completed)
  - Expiration timestamp
- Progress indicator for generating reports

**Usage**:
1. Navigate to `/ops/reports`
2. Select report type
3. Choose date range and format
4. Click "Generate Report"
5. Wait for report to complete (check status)
6. Click "Download" to download completed report

**Note**: Large reports are generated asynchronously. Download URLs expire after 24 hours.

### Usage Metering (`/ops/usage`)

**Purpose**: Track resource consumption by tenant

**Features**:
- Usage summary cards by resource type (API calls, exceptions, tool executions, LLM calls)
- Detailed usage table with breakdown
- Period selector (day, week, month)
- Export buttons (CSV, JSON)
- Filters: date range, resource type

**Usage**:
1. Navigate to `/ops/usage`
2. Select time period (day/week/month)
3. Review summary cards for high-level metrics
4. Review detailed table for granular data
5. Export data for billing or analysis

### Rate Limits (`/ops/rate-limits`)

**Purpose**: View and manage rate limits per tenant

**Features**:
- Rate limit configuration table:
  - Limit type (API requests, events ingested, tool executions, report generations)
  - Limit value and window
  - Current utilization
  - Status (enabled/disabled)
- Utilization progress bars
- Admin actions (admin only):
  - Update limit value (with confirmation)
  - Enable/disable limiting (with confirmation)

**Usage**:
1. Navigate to `/ops/rate-limits`
2. Review current limits and utilization
3. For admins: Click "Edit" to update limits
4. Confirm changes in dialog
5. Verify updated limits in table

**Note**: Non-admin users see view-only mode.

## Common Patterns

### Filtering
- All list pages support filtering via `OpsFilterBar`
- Filters sync with URL query parameters
- Refresh page to restore filters from URL

### Exporting Data
- Tables with export enabled show download icon in toolbar
- Click to download CSV or JSON
- Export includes current filtered data

### Loading States
- All pages show loading skeletons during data fetch
- Auto-refresh updates data without full page reload
- Manual refresh available via refresh button

### Error Handling
- API errors display as snackbar notifications
- Error states show user-friendly messages
- Retry available for failed operations

## Feature Flags

Set in `ui/.env`:
```bash
VITE_OPS_ENABLED=true
VITE_API_BASE_URL=http://localhost:8000
```

## Troubleshooting

**Issue**: Ops menu not showing
- **Solution**: Check `VITE_OPS_ENABLED=true` in `ui/.env` and restart dev server

**Issue**: "Not authorized" page
- **Solution**: Ensure `VITE_OPS_ENABLED=true` and tenantId is set in localStorage

**Issue**: No data loading
- **Solution**: Check browser console for errors, verify backend is running, check Network tab for API responses

**Issue**: Filters not persisting
- **Solution**: Ensure `syncWithUrl={true}` is set on FilterBar (default)

