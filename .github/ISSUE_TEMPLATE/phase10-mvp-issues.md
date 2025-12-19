# Phase 10 Ops & Governance MVP - GitHub Issues Checklist

## Component: Ops Dashboard Backend

### Issue P10-1: Implement Worker Health Aggregation Service
**Labels:** `component:ops`, `phase:10`, `priority:high`
**Description:**
- Create WorkerHealthService to aggregate health from all workers:
  - Poll worker `/healthz` and `/readyz` endpoints (ports 9001-9007)
  - Track health status per worker instance (healthy, degraded, unhealthy)
  - Cache health status with configurable TTL (default: 30s)
  - Support worker discovery via configuration or service registry
- Implement health aggregation endpoint:
  - `GET /ops/workers/health` - Returns health status of all workers
  - Include: worker_type, instance_id, status, last_check, response_time
- Handle unreachable workers gracefully (mark as unhealthy after N failures)
- Reference: docs/phase10-ops-governance-mvp.md Section 5.1

**Dependencies:** None (uses existing worker health endpoints)

**Acceptance Criteria:**
- [ ] WorkerHealthService implemented
- [ ] Worker health polling functional
- [ ] Health status caching working
- [ ] `/ops/workers/health` endpoint returns aggregated health
- [ ] Unreachable workers handled gracefully
- [ ] Unit tests for health aggregation
- [ ] Integration tests with mock worker endpoints

---

### Issue P10-2: Implement Worker Throughput Metrics API
**Labels:** `component:ops`, `phase:10`, `priority:high`
**Description:**
- Create MetricsAggregationService to compute worker throughput:
  - Events processed per second (per worker type)
  - Processing latency p50, p95, p99 (per worker type)
  - Error rate percentage (per worker type)
  - Consumer lag (events pending per topic)
- Implement metrics endpoints:
  - `GET /ops/workers/throughput` - Current throughput by worker type
  - `GET /ops/workers/latency` - Latency percentiles by worker type
  - `GET /ops/workers/errors` - Error rates by worker type
- Data sources: `event_processing` table, Prometheus metrics (if available)
- Support time range filtering (last 5m, 1h, 24h)
- Reference: docs/phase10-ops-governance-mvp.md Section 5.1

**Dependencies:** P10-1

**Acceptance Criteria:**
- [ ] MetricsAggregationService implemented
- [ ] Throughput calculation from event_processing table working
- [ ] Latency percentile calculation functional
- [ ] Error rate calculation functional
- [ ] All metrics endpoints returning data
- [ ] Time range filtering working
- [ ] Unit tests for metrics calculations
- [ ] Integration tests for metrics endpoints

---

### Issue P10-3: Implement SLA Compliance Metrics API
**Labels:** `component:ops`, `phase:10`, `priority:high`
**Description:**
- Create SLAMetricsService to compute SLA compliance:
  - SLA compliance rate (% met) by tenant
  - SLA breach count by tenant, severity, time period
  - Average time-to-resolution by severity
  - Exceptions at risk (approaching SLA deadline)
- Implement SLA metrics endpoints:
  - `GET /ops/sla/compliance?tenant_id=...&period=day` - Compliance rate
  - `GET /ops/sla/breaches?tenant_id=...&from=...&to=...` - Breach history
  - `GET /ops/sla/at-risk?tenant_id=...` - Exceptions approaching deadline
  - `GET /ops/sla/resolution-time?tenant_id=...` - Avg resolution time
- Data sources: `exception` table, `exception_event` table
- Support grouping by day, week, month
- Reference: docs/phase10-ops-governance-mvp.md Section 5.2

**Dependencies:** None (uses existing tables)

**Acceptance Criteria:**
- [ ] SLAMetricsService implemented
- [ ] Compliance rate calculation working
- [ ] Breach history query functional
- [ ] At-risk exceptions query functional
- [ ] Resolution time calculation working
- [ ] All SLA endpoints returning data
- [ ] Time period grouping working
- [ ] Unit tests for SLA calculations
- [ ] Integration tests for SLA endpoints

---

### Issue P10-4: Implement DLQ Management API
**Labels:** `component:ops`, `phase:10`, `priority:high`
**Description:**
- Enhance existing `/ops/dlq` endpoints for full DLQ management:
  - `GET /ops/dlq?tenant_id=...&event_type=...&status=...` - List with filters
  - `GET /ops/dlq/{id}` - Get full event details and failure info
  - `POST /ops/dlq/{id}/retry` - Retry single event (re-publish to original topic)
  - `POST /ops/dlq/retry-batch` - Retry multiple events
  - `POST /ops/dlq/{id}/discard` - Mark as resolved without retry
  - `GET /ops/dlq/stats` - DLQ counts by tenant, event_type, date
- Add DLQ entry status: pending, retrying, discarded, succeeded
- Track retry attempts per DLQ entry
- Emit events for DLQ operations (for audit trail)
- Reference: docs/phase10-ops-governance-mvp.md Section 5.3

**Dependencies:** P9-15 (DLQ table exists)

**Acceptance Criteria:**
- [ ] DLQ list endpoint with filters working
- [ ] DLQ detail endpoint returning full event payload
- [ ] Single retry functional (re-publishes to Kafka)
- [ ] Batch retry functional
- [ ] Discard operation functional
- [ ] DLQ stats endpoint working
- [ ] Retry attempt tracking implemented
- [ ] Audit events emitted for DLQ operations
- [ ] Unit tests for DLQ operations
- [ ] Integration tests for retry flow

---

## Component: Alerting System

### Issue P10-5: Implement Alert Configuration Storage
**Labels:** `component:alerting`, `phase:10`, `priority:high`
**Description:**
- Create database tables for alert configuration:
  - `alert_config`: tenant_id, alert_type, enabled, threshold_value, threshold_unit, channels (jsonb), quiet_hours (jsonb), created_at, updated_at
  - `alert_channel`: id, tenant_id, channel_type (webhook, email), config (jsonb), verified, created_at
- Implement AlertConfigRepository:
  - CRUD operations for alert configs
  - CRUD operations for alert channels
  - Get enabled alerts by tenant
  - Get channels by tenant
- Support alert types: SLA_BREACH, SLA_IMMINENT, DLQ_GROWTH, WORKER_UNHEALTHY, ERROR_RATE_HIGH, THROUGHPUT_LOW
- Reference: docs/phase10-ops-governance-mvp.md Section 6.2

**Dependencies:** None

**Acceptance Criteria:**
- [ ] alert_config table created with migration
- [ ] alert_channel table created with migration
- [ ] AlertConfigRepository implemented
- [ ] CRUD operations functional
- [ ] All alert types supported
- [ ] Tenant isolation enforced
- [ ] Unit tests for repository
- [ ] Integration tests with database

---

### Issue P10-6: Implement Alert Configuration API
**Labels:** `component:alerting`, `phase:10`, `priority:high`
**Description:**
- Create alert configuration API endpoints:
  - `GET /alerts/config?tenant_id=...` - List alert configs for tenant
  - `POST /alerts/config` - Create alert config
  - `PUT /alerts/config/{id}` - Update alert config
  - `DELETE /alerts/config/{id}` - Delete alert config
  - `GET /alerts/channels?tenant_id=...` - List notification channels
  - `POST /alerts/channels` - Create notification channel
  - `POST /alerts/channels/{id}/verify` - Send test notification
  - `DELETE /alerts/channels/{id}` - Delete notification channel
- Validate threshold values per alert type
- Validate channel configuration (webhook URL, email format)
- Reference: docs/phase10-ops-governance-mvp.md Section 6.2

**Dependencies:** P10-5

**Acceptance Criteria:**
- [ ] All alert config CRUD endpoints working
- [ ] All channel CRUD endpoints working
- [ ] Channel verification (test notification) working
- [ ] Threshold validation functional
- [ ] Channel config validation functional
- [ ] Tenant isolation enforced
- [ ] Unit tests for API endpoints
- [ ] Integration tests for full flow

---

### Issue P10-7: Implement Alert Evaluation Service
**Labels:** `component:alerting`, `phase:10`, `priority:high`
**Description:**
- Create AlertEvaluationService to check alert conditions:
  - Evaluate SLA_BREACH: Check exceptions past SLA deadline
  - Evaluate SLA_IMMINENT: Check exceptions approaching deadline
  - Evaluate DLQ_GROWTH: Check DLQ count vs threshold
  - Evaluate WORKER_UNHEALTHY: Check worker health status
  - Evaluate ERROR_RATE_HIGH: Check error rate vs threshold
  - Evaluate THROUGHPUT_LOW: Check throughput vs baseline
- Run evaluation periodically (configurable interval, default: 1 minute)
- Support per-tenant thresholds
- Track alert state to avoid duplicate notifications
- Reference: docs/phase10-ops-governance-mvp.md Section 6.1

**Dependencies:** P10-1, P10-2, P10-3, P10-5

**Acceptance Criteria:**
- [ ] AlertEvaluationService implemented
- [ ] All alert type evaluations functional
- [ ] Periodic evaluation running
- [ ] Per-tenant thresholds respected
- [ ] Duplicate notification prevention working
- [ ] Unit tests for each alert type evaluation
- [ ] Integration tests for evaluation cycle

---

### Issue P10-8: Implement Alert Notification Service
**Labels:** `component:alerting`, `phase:10`, `priority:high`
**Description:**
- Create AlertNotificationService to send notifications:
  - Webhook notifications (POST JSON to URL)
  - Email notifications (via SMTP or SendGrid)
  - Support HMAC signing for webhook security
  - Retry failed notifications with exponential backoff
- Implement webhook payload format per spec
- Create alert_history table:
  - alert_id, tenant_id, alert_type, triggered_at, acknowledged_at, resolved_at, notification_status, details (jsonb)
- Track notification delivery status
- Reference: docs/phase10-ops-governance-mvp.md Section 6.3

**Dependencies:** P10-7

**Acceptance Criteria:**
- [ ] Webhook notification sending functional
- [ ] Email notification sending functional (via configurable provider)
- [ ] HMAC signing for webhooks implemented
- [ ] Retry with exponential backoff working
- [ ] alert_history table created
- [ ] Notification delivery status tracked
- [ ] Unit tests for notification sending
- [ ] Integration tests with mock webhook endpoint

---

### Issue P10-9: Implement Alert History API
**Labels:** `component:alerting`, `phase:10`, `priority:medium`
**Description:**
- Create alert history API endpoints:
  - `GET /alerts/history?tenant_id=...&type=...&from=...&to=...` - List alerts
  - `GET /alerts/history/{id}` - Get alert details
  - `POST /alerts/history/{id}/acknowledge` - Acknowledge alert
  - `POST /alerts/history/{id}/resolve` - Resolve alert
  - `GET /alerts/history/stats?tenant_id=...` - Alert counts by type, status
- Support filtering by alert type, status, date range
- Support pagination
- Reference: docs/phase10-ops-governance-mvp.md Section 6

**Dependencies:** P10-8

**Acceptance Criteria:**
- [ ] Alert history list endpoint with filters working
- [ ] Alert detail endpoint working
- [ ] Acknowledge operation functional
- [ ] Resolve operation functional
- [ ] Stats endpoint working
- [ ] Pagination implemented
- [ ] Unit tests for history API
- [ ] Integration tests for alert lifecycle

---

## Component: Config Change Governance

### Issue P10-10: Implement Config Change Request Storage
**Labels:** `component:governance`, `phase:10`, `priority:high`
**Description:**
- Create database table for config change requests:
  - `config_change_request`: id, tenant_id, change_type (domain_pack, policy_pack, tool, playbook), resource_id, current_version, proposed_config (jsonb), diff_summary (jsonb), status (pending, approved, rejected, applied), requested_by, requested_at, reviewed_by, reviewed_at, review_comment, applied_at
- Implement ConfigChangeRepository:
  - Create change request
  - List pending changes by tenant
  - Get change request by ID
  - Update status (approve, reject, apply)
  - Get change history by resource
- Generate diff_summary automatically (old vs new config)
- Reference: docs/phase10-ops-governance-mvp.md Section 7.2

**Dependencies:** None

**Acceptance Criteria:**
- [ ] config_change_request table created with migration
- [ ] ConfigChangeRepository implemented
- [ ] All CRUD operations functional
- [ ] Diff summary generation working
- [ ] Status transitions enforced
- [ ] Tenant isolation enforced
- [ ] Unit tests for repository
- [ ] Integration tests with database

---

### Issue P10-11: Implement Config Change Governance API
**Labels:** `component:governance`, `phase:10`, `priority:high`
**Description:**
- Create config change governance API endpoints:
  - `POST /admin/config-changes` - Create change request
  - `GET /admin/config-changes?tenant_id=...&status=pending` - List changes
  - `GET /admin/config-changes/{id}` - Get change with full diff
  - `POST /admin/config-changes/{id}/approve` - Approve change
  - `POST /admin/config-changes/{id}/reject` - Reject with comment
  - `GET /admin/config-changes/{id}/diff` - Get detailed diff view
- Validate proposed config against schema
- Require ADMIN role for approval/rejection
- Emit audit events for all operations
- Reference: docs/phase10-ops-governance-mvp.md Section 7.3

**Dependencies:** P10-10

**Acceptance Criteria:**
- [ ] Create change request endpoint working
- [ ] List changes with status filter working
- [ ] Get change with diff working
- [ ] Approve operation functional (applies change)
- [ ] Reject operation functional
- [ ] Schema validation for proposed config
- [ ] RBAC enforcement (ADMIN only for approve/reject)
- [ ] Audit events emitted
- [ ] Unit tests for governance API
- [ ] Integration tests for approval workflow

---

### Issue P10-12: Implement Config Change Auto-Apply Service
**Labels:** `component:governance`, `phase:10`, `priority:medium`
**Description:**
- Create ConfigChangeApplyService to apply approved changes:
  - Apply domain pack changes (create new version)
  - Apply policy pack changes (create new version)
  - Apply tool definition changes
  - Apply playbook changes
- Integrate with existing versioning system
- Update applied_at timestamp after successful apply
- Handle apply failures gracefully (revert status to approved)
- Emit ConfigChangeApplied event for audit trail
- Reference: docs/phase10-ops-governance-mvp.md Section 7.1

**Dependencies:** P10-11

**Acceptance Criteria:**
- [ ] Domain pack apply functional
- [ ] Policy pack apply functional
- [ ] Tool definition apply functional
- [ ] Playbook apply functional
- [ ] Version creation working
- [ ] applied_at updated on success
- [ ] Failure handling implemented
- [ ] ConfigChangeApplied event emitted
- [ ] Unit tests for apply service
- [ ] Integration tests for each change type

---

## Component: Audit Reports

### Issue P10-13: Implement Audit Report Generation Service
**Labels:** `component:audit`, `phase:10`, `priority:medium`
**Description:**
- Create AuditReportService for report generation:
  - Exception Activity report (all exceptions with status changes)
  - Tool Execution report (all tool executions with outcomes)
  - Policy Decisions report (all policy evaluations)
  - Config Changes report (all config change requests)
  - SLA Compliance report (SLA metrics summary)
- Support output formats: CSV, JSON
- Generate reports asynchronously for large datasets
- Store generated reports with expiring download URLs
- Reference: docs/phase10-ops-governance-mvp.md Section 8.1

**Dependencies:** None

**Acceptance Criteria:**
- [ ] Exception Activity report generation working
- [ ] Tool Execution report generation working
- [ ] Policy Decisions report generation working
- [ ] Config Changes report generation working
- [ ] SLA Compliance report generation working
- [ ] CSV format output working
- [ ] JSON format output working
- [ ] Async generation for large reports
- [ ] Report storage with expiring URLs
- [ ] Unit tests for report generation
- [ ] Integration tests for each report type

---

### Issue P10-14: Implement Audit Report API
**Labels:** `component:audit`, `phase:10`, `priority:medium`
**Description:**
- Create audit report API endpoints:
  - `POST /audit/reports` - Request report generation (async)
  - `GET /audit/reports/{id}` - Get report status and download URL
  - `GET /audit/reports?tenant_id=...` - List generated reports
  - `DELETE /audit/reports/{id}` - Delete report
- Create report_request table:
  - id, tenant_id, report_type, parameters (jsonb), status (pending, generating, ready, failed, expired), requested_by, requested_at, completed_at, download_url, expires_at
- Support report parameters (date range, filters)
- Reference: docs/phase10-ops-governance-mvp.md Section 8.2

**Dependencies:** P10-13

**Acceptance Criteria:**
- [ ] Report request endpoint working (returns report_id)
- [ ] Report status endpoint working
- [ ] Report list endpoint working
- [ ] Report delete endpoint working
- [ ] report_request table created
- [ ] Async generation flow working
- [ ] Download URL generation working
- [ ] URL expiration enforced
- [ ] Unit tests for report API
- [ ] Integration tests for full flow

---

## Component: Rate Limiting

### Issue P10-15: Implement Rate Limit Storage and Configuration
**Labels:** `component:rate-limiting`, `phase:10`, `priority:high`
**Description:**
- Create database tables for rate limiting:
  - `rate_limit_config`: tenant_id, limit_type (api_requests, events_ingested, tool_executions, report_generations), limit_value, window_seconds, created_at, updated_at
  - `rate_limit_usage`: tenant_id, limit_type, window_start, current_count, updated_at
- Implement RateLimitRepository:
  - Get rate limit config by tenant
  - Update rate limit config
  - Increment usage counter
  - Get current usage
  - Reset expired windows
- Support sliding window rate limiting
- Reference: docs/phase10-ops-governance-mvp.md Section 9.1

**Dependencies:** None

**Acceptance Criteria:**
- [ ] rate_limit_config table created with migration
- [ ] rate_limit_usage table created with migration
- [ ] RateLimitRepository implemented
- [ ] Get/update config operations working
- [ ] Usage counter increment working
- [ ] Sliding window calculation working
- [ ] Expired window cleanup working
- [ ] Unit tests for repository
- [ ] Integration tests with database

---

### Issue P10-16: Implement Rate Limit Enforcement Middleware
**Labels:** `component:rate-limiting`, `phase:10`, `priority:high`
**Description:**
- Create RateLimitService for rate limit enforcement:
  - Check rate limit before processing request
  - Return 429 Too Many Requests if exceeded
  - Include Retry-After header with reset time
  - Support bypass for super-admin role
- Implement FastAPI middleware for rate limiting:
  - Apply to configured endpoints
  - Extract tenant_id from request
  - Check and increment usage atomically
- Track rate limit hits for monitoring
- Reference: docs/phase10-ops-governance-mvp.md Section 9.2

**Dependencies:** P10-15

**Acceptance Criteria:**
- [ ] RateLimitService implemented
- [ ] Rate limit checking functional
- [ ] 429 response with Retry-After header working
- [ ] Super-admin bypass working
- [ ] FastAPI middleware implemented
- [ ] Atomic check-and-increment working
- [ ] Rate limit hits tracked
- [ ] Unit tests for service
- [ ] Integration tests for middleware

---

### Issue P10-17: Implement Rate Limit Admin API
**Labels:** `component:rate-limiting`, `phase:10`, `priority:medium`
**Description:**
- Create rate limit admin API endpoints:
  - `GET /admin/rate-limits/{tenant_id}` - Get tenant rate limits
  - `PUT /admin/rate-limits/{tenant_id}` - Update tenant rate limits
  - `GET /admin/rate-limits/{tenant_id}/usage` - Get current usage
  - `POST /admin/rate-limits/{tenant_id}/reset` - Reset usage counters
- Create tenant-facing usage endpoint:
  - `GET /usage/rate-limits` - Get own usage vs limits
- Require ADMIN role for admin endpoints
- Reference: docs/phase10-ops-governance-mvp.md Section 9.3

**Dependencies:** P10-16

**Acceptance Criteria:**
- [ ] Get rate limits endpoint working
- [ ] Update rate limits endpoint working
- [ ] Get usage endpoint working
- [ ] Reset usage endpoint working
- [ ] Tenant-facing usage endpoint working
- [ ] RBAC enforcement (ADMIN only for admin endpoints)
- [ ] Unit tests for admin API
- [ ] Integration tests for full flow

---

## Component: Usage Metering

### Issue P10-18: Implement Usage Metering Storage
**Labels:** `component:usage`, `phase:10`, `priority:medium`
**Description:**
- Create database tables for usage metering:
  - `usage_record`: id, tenant_id, resource_type, resource_id (nullable), count, recorded_at, metadata (jsonb)
  - `usage_daily_rollup`: tenant_id, resource_type, date, total_count, metadata (jsonb)
- Implement UsageRepository:
  - Record usage event
  - Get usage by tenant, resource type, time range
  - Rollup minute data to daily aggregates
  - Get daily/monthly summaries
- Resource types: api_calls, exceptions_ingested, tool_executions, events_processed
- Reference: docs/phase10-ops-governance-mvp.md Section 10.1

**Dependencies:** None

**Acceptance Criteria:**
- [ ] usage_record table created with migration
- [ ] usage_daily_rollup table created with migration
- [ ] UsageRepository implemented
- [ ] Record usage functional
- [ ] Get usage with filters working
- [ ] Daily rollup aggregation working
- [ ] Summary queries working
- [ ] Unit tests for repository
- [ ] Integration tests with database

---

### Issue P10-19: Implement Usage Metering Service
**Labels:** `component:usage`, `phase:10`, `priority:medium`
**Description:**
- Create UsageMeteringService to track usage:
  - Instrument API endpoints to record calls
  - Instrument exception ingestion to record counts
  - Instrument tool executions to record counts
  - Instrument event processing to record counts
- Use lightweight async recording (non-blocking)
- Run periodic rollup job (aggregate minute → daily)
- Support usage export for billing integration
- Reference: docs/phase10-ops-governance-mvp.md Section 10

**Dependencies:** P10-18

**Acceptance Criteria:**
- [ ] UsageMeteringService implemented
- [ ] API call tracking working
- [ ] Exception ingestion tracking working
- [ ] Tool execution tracking working
- [ ] Event processing tracking working
- [ ] Async recording (non-blocking)
- [ ] Periodic rollup job working
- [ ] Usage export functional
- [ ] Unit tests for metering service
- [ ] Integration tests for instrumentation

---

### Issue P10-20: Implement Usage Metering API
**Labels:** `component:usage`, `phase:10`, `priority:medium`
**Description:**
- Create usage metering API endpoints:
  - `GET /usage/summary?tenant_id=...&period=day` - Usage summary
  - `GET /usage/details?tenant_id=...&resource=api_calls&from=...&to=...` - Detailed usage
  - `GET /usage/export?tenant_id=...&period=month&format=csv` - Export usage
- Support grouping by resource type, day, week, month
- Support export formats: CSV, JSON
- Tenant can only see own usage; admin can see all
- Reference: docs/phase10-ops-governance-mvp.md Section 10.2

**Dependencies:** P10-19

**Acceptance Criteria:**
- [ ] Summary endpoint working
- [ ] Details endpoint with filters working
- [ ] Export endpoint working
- [ ] Grouping by period working
- [ ] CSV export format working
- [ ] JSON export format working
- [ ] Tenant isolation enforced
- [ ] Admin access to all tenants working
- [ ] Unit tests for usage API
- [ ] Integration tests for export flow

---

## Component: UI - Ops Dashboard

### Issue P10-21: Implement Ops Home Dashboard UI
**Labels:** `component:ui`, `phase:10`, `priority:high`
**Description:**
- Create Ops Home page (`/ops`):
  - Key metrics summary cards (exceptions today, SLA compliance, DLQ count, active alerts)
  - Recent alerts list (last 10, with severity indicators)
  - Worker health status overview (healthy/degraded/unhealthy counts)
  - Quick links to detailed dashboards
- Use TanStack Query for data fetching
- Auto-refresh data (configurable interval, default: 30s)
- Follow enterprise dark theme
- Reference: docs/phase10-ops-governance-mvp.md Section 11

**Dependencies:** P10-1, P10-3, P10-4, P10-9

**Acceptance Criteria:**
- [ ] Ops Home page created at /ops route
- [ ] Key metrics summary cards displaying
- [ ] Recent alerts list working
- [ ] Worker health overview working
- [ ] Quick links navigation working
- [ ] Auto-refresh functional
- [ ] Dark theme consistent
- [ ] Loading and error states handled
- [ ] Unit tests for components

---

### Issue P10-22: Implement Worker Dashboard UI
**Labels:** `component:ui`, `phase:10`, `priority:high`
**Description:**
- Create Worker Dashboard page (`/ops/workers`):
  - Worker type cards with health status, instance count
  - Throughput chart (events/sec over time, per worker type)
  - Latency chart (p50, p95, p99 over time)
  - Error rate chart (% over time)
  - Worker instance details table (expandable)
- Support time range selector (5m, 1h, 24h)
- Use TanStack Query with polling
- Reference: docs/phase10-ops-governance-mvp.md Section 5.1

**Dependencies:** P10-1, P10-2

**Acceptance Criteria:**
- [ ] Worker Dashboard page created at /ops/workers
- [ ] Worker type cards with health status
- [ ] Throughput chart working
- [ ] Latency chart working
- [ ] Error rate chart working
- [ ] Instance details table expandable
- [ ] Time range selector working
- [ ] Auto-refresh functional
- [ ] Unit tests for components

---

### Issue P10-23: Implement SLA Dashboard UI
**Labels:** `component:ui`, `phase:10`, `priority:high`
**Description:**
- Create SLA Dashboard page (`/ops/sla`):
  - SLA compliance rate trend chart (by day/week/month)
  - SLA breach count trend chart
  - Time-to-resolution chart by severity
  - At-risk exceptions table (approaching deadline)
  - Breach history table with details
- Support tenant selector (admin only)
- Support time period selector
- Reference: docs/phase10-ops-governance-mvp.md Section 5.2

**Dependencies:** P10-3

**Acceptance Criteria:**
- [ ] SLA Dashboard page created at /ops/sla
- [ ] Compliance rate trend chart working
- [ ] Breach count trend chart working
- [ ] Resolution time chart working
- [ ] At-risk exceptions table working
- [ ] Breach history table working
- [ ] Tenant selector working (admin)
- [ ] Time period selector working
- [ ] Unit tests for components

---

### Issue P10-24: Implement DLQ Management UI
**Labels:** `component:ui`, `phase:10`, `priority:high`
**Description:**
- Create DLQ Management page (`/ops/dlq`):
  - DLQ entries table with filters (tenant, event_type, status, date range)
  - Entry detail modal (full payload, failure reason, retry count)
  - Retry single entry button
  - Batch retry checkbox selection
  - Discard entry button with confirmation
  - DLQ growth chart over time
- Support pagination
- Show retry in progress state
- Reference: docs/phase10-ops-governance-mvp.md Section 5.3

**Dependencies:** P10-4

**Acceptance Criteria:**
- [ ] DLQ Management page created at /ops/dlq
- [ ] Entries table with filters working
- [ ] Entry detail modal working
- [ ] Single retry functional
- [ ] Batch retry functional
- [ ] Discard with confirmation working
- [ ] DLQ growth chart working
- [ ] Pagination working
- [ ] Retry progress state shown
- [ ] Unit tests for components

---

### Issue P10-25: Implement Alert Configuration UI
**Labels:** `component:ui`, `phase:10`, `priority:medium`
**Description:**
- Create Alert Config page (`/ops/alerts`):
  - Alert rules table (type, enabled, threshold, channels)
  - Create/edit alert rule form (type, threshold, enabled toggle)
  - Notification channels table
  - Create/edit channel form (webhook URL or email)
  - Test notification button
- Create Alert History page (`/ops/alerts/history`):
  - Alerts table with filters (type, status, date range)
  - Alert detail modal
  - Acknowledge and resolve buttons
- Reference: docs/phase10-ops-governance-mvp.md Section 6

**Dependencies:** P10-6, P10-9

**Acceptance Criteria:**
- [ ] Alert Config page created at /ops/alerts
- [ ] Alert rules table working
- [ ] Create/edit rule form working
- [ ] Channels table working
- [ ] Create/edit channel form working
- [ ] Test notification button working
- [ ] Alert History page created at /ops/alerts/history
- [ ] Alerts table with filters working
- [ ] Alert detail modal working
- [ ] Acknowledge/resolve buttons working
- [ ] Unit tests for components

---

### Issue P10-26: Implement Audit Reports UI
**Labels:** `component:ui`, `phase:10`, `priority:medium`
**Description:**
- Create Audit Reports page (`/ops/reports`):
  - Report type selector (Exception Activity, Tool Execution, etc.)
  - Date range picker
  - Format selector (CSV, JSON)
  - Generate report button
  - Generated reports table (status, download link, expires)
  - Progress indicator for generating reports
- Handle download of generated reports
- Reference: docs/phase10-ops-governance-mvp.md Section 8

**Dependencies:** P10-14

**Acceptance Criteria:**
- [ ] Audit Reports page created at /ops/reports
- [ ] Report type selector working
- [ ] Date range picker working
- [ ] Format selector working
- [ ] Generate report button working
- [ ] Generated reports table working
- [ ] Progress indicator for generation
- [ ] Download link functional
- [ ] Expiration shown
- [ ] Unit tests for components

---

### Issue P10-27: Implement Usage Metering UI
**Labels:** `component:ui`, `phase:10`, `priority:medium`
**Description:**
- Create Usage Metering page (`/ops/usage`):
  - Usage summary cards (API calls, exceptions, tool executions today)
  - Usage trend chart by resource type
  - Usage vs rate limit comparison (if limits configured)
  - Detailed usage table with breakdown
  - Export usage button (CSV)
- Support time period selector (day, week, month)
- Support tenant selector (admin only)
- Reference: docs/phase10-ops-governance-mvp.md Section 10

**Dependencies:** P10-20

**Acceptance Criteria:**
- [ ] Usage Metering page created at /ops/usage
- [ ] Usage summary cards working
- [ ] Usage trend chart working
- [ ] Usage vs limit comparison working
- [ ] Detailed usage table working
- [ ] Export button functional
- [ ] Time period selector working
- [ ] Tenant selector working (admin)
- [ ] Unit tests for components

---

### Issue P10-28: Implement Config Changes UI
**Labels:** `component:ui`, `phase:10`, `priority:medium`
**Description:**
- Create Config Changes page (`/admin/config-changes`):
  - Pending changes table (resource, type, requested by, date)
  - Change detail view with diff (side-by-side old vs new)
  - Approve button with confirmation
  - Reject button with comment input
  - Change history table (all statuses)
- Diff view should highlight added/removed/changed fields
- Reference: docs/phase10-ops-governance-mvp.md Section 7

**Dependencies:** P10-11

**Acceptance Criteria:**
- [ ] Config Changes page created at /admin/config-changes
- [ ] Pending changes table working
- [ ] Change detail view with diff working
- [ ] Diff highlighting working
- [ ] Approve with confirmation working
- [ ] Reject with comment working
- [ ] Change history table working
- [ ] Unit tests for components

---

## Component: Testing & Documentation

### Issue P10-29: Implement Phase 10 Integration Tests
**Labels:** `component:testing`, `phase:10`, `priority:high`
**Description:**
- Write integration tests for Phase 10 components:
  - Worker health aggregation tests
  - SLA metrics calculation tests
  - DLQ retry flow tests
  - Alert evaluation and notification tests
  - Config change approval workflow tests
  - Rate limiting enforcement tests
  - Usage metering accuracy tests
- Test tenant isolation for all new endpoints
- Test RBAC enforcement for admin endpoints
- Achieve >80% code coverage for Phase 10 code
- Reference: docs/phase10-ops-governance-mvp.md Section 14

**Dependencies:** P10-1 through P10-28

**Acceptance Criteria:**
- [ ] Worker health integration tests passing
- [ ] SLA metrics integration tests passing
- [ ] DLQ flow integration tests passing
- [ ] Alert workflow integration tests passing
- [ ] Config change workflow integration tests passing
- [ ] Rate limiting integration tests passing
- [ ] Usage metering integration tests passing
- [ ] Tenant isolation tests passing
- [ ] RBAC tests passing
- [ ] Code coverage >80%

---

### Issue P10-30: Update Documentation and Runbook
**Labels:** `component:documentation`, `phase:10`, `priority:high`
**Description:**
- Update docs/STATE_OF_THE_PLATFORM.md with Phase 10 capabilities
- Update docs/run-local.md if any new services added
- Create docs/ops-alerting-guide.md:
  - Alert types and thresholds
  - Channel configuration
  - Troubleshooting alerts
- Create docs/config-governance-guide.md:
  - Change request workflow
  - Approval process
  - Best practices
- Update docs/ops-runbook.md:
  - DLQ management procedures
  - Rate limit adjustment procedures
  - Report generation procedures
- Reference: docs/phase10-ops-governance-mvp.md Section 14

**Dependencies:** All P10 issues

**Acceptance Criteria:**
- [ ] STATE_OF_THE_PLATFORM.md updated
- [ ] run-local.md updated if needed
- [ ] ops-alerting-guide.md created
- [ ] config-governance-guide.md created
- [ ] ops-runbook.md updated
- [ ] All new API endpoints documented
- [ ] All new UI screens documented

---

## Summary

**Total Issues:** 30
**High Priority:** 18
**Medium Priority:** 12

**Components Covered:**
- Ops Dashboard Backend (4 issues)
- Alerting System (5 issues)
- Config Change Governance (3 issues)
- Audit Reports (2 issues)
- Rate Limiting (3 issues)
- Usage Metering (3 issues)
- UI - Ops Dashboard (8 issues)
- Testing & Documentation (2 issues)

**Implementation Order:**

### Foundation (Week 1)
1. P10-1: Worker health aggregation
2. P10-2: Worker throughput metrics
3. P10-3: SLA compliance metrics
4. P10-4: DLQ management API
5. P10-5: Alert config storage

### Alerting & Governance (Week 2)
6. P10-6: Alert config API
7. P10-7: Alert evaluation service
8. P10-8: Alert notification service
9. P10-9: Alert history API
10. P10-10: Config change storage
11. P10-11: Config change API
12. P10-12: Config change apply service

### Audit, Limits, Metering (Week 3)
13. P10-13: Audit report service
14. P10-14: Audit report API
15. P10-15: Rate limit storage
16. P10-16: Rate limit middleware
17. P10-17: Rate limit admin API
18. P10-18: Usage metering storage
19. P10-19: Usage metering service
20. P10-20: Usage metering API

### UI (Week 4)
21. P10-21: Ops home dashboard
22. P10-22: Worker dashboard
23. P10-23: SLA dashboard
24. P10-24: DLQ management UI
25. P10-25: Alert config UI
26. P10-26: Audit reports UI
27. P10-27: Usage metering UI
28. P10-28: Config changes UI

### Finalization (Week 5)
29. P10-29: Integration tests
30. P10-30: Documentation
