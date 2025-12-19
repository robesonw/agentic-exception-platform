# Phase 10 – Ops & Governance MVP
SentinAI – Multi-Tenant, Domain-Abstracted Agentic Exception Platform

---

## 1. Purpose

Phase 10 transforms SentinAI from a **functional platform** into an **enterprise-ready, operationally mature system** with:

- **Operational visibility** – dashboards showing system health, throughput, SLA compliance
- **Governance controls** – audit reports, config change approval, rate limiting
- **Production hardening** – alerting, DLQ management UI, health aggregation
- **Cost transparency** – per-tenant resource and API usage tracking

This phase builds on the async, event-driven foundation from Phase 9 to add the operational capabilities required for production deployments.

---

## 2. Prerequisites (Completed in Prior Phases)

| Phase | Capability | Status |
|-------|------------|--------|
| Phase 6 | PostgreSQL persistence, audit trail | Complete |
| Phase 7 | Playbook matching and execution | Complete |
| Phase 8 | Tool registry, execution lifecycle | Complete |
| Phase 9 | Kafka workers, async pipeline, DLQ, metrics endpoint | Complete |

**Current State (from docs/STATE_OF_THE_PLATFORM.md):**
- 7 worker types processing exceptions end-to-end
- Prometheus `/metrics` endpoint exists
- DLQ table and routing implemented
- Basic `/ops/dlq` API exists
- `exception_event` table captures full audit trail

---

## 3. Core Goals (MVP)

1. **Ops Dashboard** – Real-time view of worker health, throughput, error rates
2. **SLA Compliance Dashboard** – Trend analysis, breach history, tenant comparison
3. **DLQ Management UI** – View, filter, retry, discard dead-lettered events
4. **Alerting Webhook** – Configurable alerts for SLA breaches, DLQ growth, worker failures
5. **Config Change Governance** – Approval workflow for domain pack / policy changes
6. **Audit Reports** – Exportable compliance reports per tenant
7. **Rate Limiting** – Per-tenant API rate limits with quota tracking
8. **Usage Metering** – Track API calls, tool executions, events per tenant

---

## 4. Architecture Overview

```mermaid
flowchart TB
    subgraph Ops UI
        OpsHome[Ops Home]
        WorkerDash[Worker Dashboard]
        SLADash[SLA Dashboard]
        DLQView[DLQ Management]
        AlertConfig[Alert Config]
        AuditReport[Audit Reports]
        UsageView[Usage Metering]
    end

    subgraph Backend APIs
        OpsAPI[/ops/*]
        AlertAPI[/alerts/*]
        AuditAPI[/audit/*]
        UsageAPI[/usage/*]
        ConfigAPI[/admin/config-changes/*]
    end

    subgraph Services
        MetricsAgg[MetricsAggregationService]
        AlertSvc[AlertingService]
        AuditSvc[AuditReportService]
        UsageSvc[UsageMeteringService]
        ConfigGov[ConfigGovernanceService]
        RateLimiter[RateLimitService]
    end

    subgraph Storage
        PG[(PostgreSQL)]
        Metrics[(Prometheus/TimeSeries)]
    end

    subgraph External
        Webhook[Webhook Endpoints]
        Email[Email Service]
    end

    OpsHome --> OpsAPI
    WorkerDash --> OpsAPI
    SLADash --> OpsAPI
    DLQView --> OpsAPI
    AlertConfig --> AlertAPI
    AuditReport --> AuditAPI
    UsageView --> UsageAPI

    OpsAPI --> MetricsAgg
    OpsAPI --> PG
    AlertAPI --> AlertSvc
    AuditAPI --> AuditSvc
    UsageAPI --> UsageSvc
    ConfigAPI --> ConfigGov

    MetricsAgg --> Metrics
    AlertSvc --> Webhook
    AlertSvc --> Email
    AlertSvc --> PG

    RateLimiter --> PG
```

---

## 5. Ops Dashboard

### 5.1 Worker Health Dashboard

**Purpose:** Real-time visibility into worker fleet health.

**Metrics to Display:**
- Worker instances by type (intake, triage, policy, playbook, tool, feedback, sla_monitor)
- Health status per instance (healthy, degraded, unhealthy)
- Events processed per second (per worker type)
- Processing latency p50, p95, p99 (per worker type)
- Error rate (per worker type)
- Consumer lag (events pending per topic)

**Data Sources:**
- Worker `/healthz` and `/readyz` endpoints (ports 9001-9007)
- Prometheus metrics (if available)
- `event_processing` table (processed counts)

### 5.2 SLA Compliance Dashboard

**Purpose:** Track SLA performance across tenants and time.

**Metrics to Display:**
- SLA compliance rate (% met) by tenant, by day/week/month
- SLA breach count and trend
- Average time-to-resolution by severity
- Exceptions at risk (approaching SLA deadline)
- Historical comparison (vs previous period)

**Data Sources:**
- `exception` table (created_at, resolved_at, sla_deadline)
- `exception_event` table (SLAImminent, SLAExpired events)

### 5.3 DLQ Management UI

**Purpose:** Allow operators to inspect, retry, or discard failed events.

**Features:**
- List DLQ entries with filters (tenant, event_type, date range, failure_reason)
- View full event payload and failure details
- Retry single event (re-publish to original topic)
- Retry batch (selected events)
- Discard event (mark as resolved without retry)
- DLQ growth chart over time

**Data Sources:**
- `dead_letter_events` table

---

## 6. Alerting System

### 6.1 Alert Types

| Alert Type | Trigger Condition | Default Threshold |
|------------|-------------------|-------------------|
| SLA_BREACH | Exception SLA expired | Immediate |
| SLA_IMMINENT | Exception approaching SLA | 80% of SLA window |
| DLQ_GROWTH | DLQ entries exceed threshold | 100 entries |
| WORKER_UNHEALTHY | Worker health check fails | 3 consecutive failures |
| ERROR_RATE_HIGH | Error rate exceeds threshold | 5% over 5 minutes |
| THROUGHPUT_LOW | Events/sec below threshold | 50% drop from baseline |

### 6.2 Alert Configuration

**Per-tenant configurable:**
- Alert types enabled/disabled
- Thresholds per alert type
- Notification channels (webhook URL, email addresses)
- Quiet hours (suppress non-critical alerts)
- Escalation policy (if not acknowledged in N minutes)

**Storage:**
- `alert_config` table: tenant_id, alert_type, enabled, threshold, channels, quiet_hours
- `alert_history` table: alert_id, tenant_id, alert_type, triggered_at, acknowledged_at, resolved_at, details

### 6.3 Notification Channels

**MVP Scope:**
- Webhook (POST JSON to configured URL)
- Email (via configurable SMTP or SendGrid)

**Webhook Payload:**
```json
{
  "alert_id": "ALT-001",
  "alert_type": "SLA_BREACH",
  "tenant_id": "TENANT_A",
  "severity": "critical",
  "title": "SLA Breach: Exception EXC-123",
  "message": "Exception EXC-123 exceeded SLA deadline by 2 hours",
  "timestamp": "2025-01-15T10:30:00Z",
  "details": {
    "exception_id": "EXC-123",
    "sla_deadline": "2025-01-15T08:30:00Z",
    "current_status": "open"
  }
}
```

---

## 7. Config Change Governance

### 7.1 Change Request Workflow

**Purpose:** Require approval before applying changes to domain packs or tenant policies.

**Workflow:**
1. User submits config change via API or UI
2. System creates pending change request
3. Approver reviews diff (old vs new)
4. Approver approves or rejects
5. If approved, system applies change and creates new version
6. Audit trail captures who requested, who approved, when applied

**Change Types:**
- Domain Pack update
- Tenant Policy Pack update
- Tool definition update
- Playbook update

### 7.2 Change Request Model

```
config_change_request:
  - id (uuid)
  - tenant_id
  - change_type (domain_pack, policy_pack, tool, playbook)
  - resource_id
  - current_version
  - proposed_config (jsonb)
  - diff_summary (jsonb)
  - status (pending, approved, rejected, applied)
  - requested_by
  - requested_at
  - reviewed_by
  - reviewed_at
  - review_comment
  - applied_at
```

### 7.3 Approval API

- `POST /admin/config-changes` – Create change request
- `GET /admin/config-changes?status=pending` – List pending changes
- `GET /admin/config-changes/{id}` – Get change details with diff
- `POST /admin/config-changes/{id}/approve` – Approve change
- `POST /admin/config-changes/{id}/reject` – Reject change

---

## 8. Audit Reports

### 8.1 Report Types

| Report | Contents | Format |
|--------|----------|--------|
| Exception Activity | All exceptions with status changes, by date range | CSV, JSON |
| Tool Execution | All tool executions with outcomes, by date range | CSV, JSON |
| Policy Decisions | All policy evaluations with actions taken | CSV, JSON |
| Config Changes | All config change requests and outcomes | CSV, JSON |
| SLA Compliance | SLA metrics summary by period | CSV, JSON, PDF |

### 8.2 Report API

- `POST /audit/reports` – Generate report (async, returns report_id)
- `GET /audit/reports/{id}` – Get report status and download URL
- `GET /audit/reports?tenant_id=...` – List generated reports

**Report Generation:**
- Large reports generated asynchronously
- Stored in file storage (local or S3)
- Download URL valid for configurable period (default: 24 hours)

---

## 9. Rate Limiting

### 9.1 Rate Limit Model

**Per-tenant limits:**
- API requests per minute
- Events ingested per minute
- Tool executions per minute
- Report generations per day

**Storage:**
- `rate_limit_config` table: tenant_id, limit_type, limit_value, window_seconds
- `rate_limit_usage` table: tenant_id, limit_type, window_start, current_count

### 9.2 Rate Limit Enforcement

- Check rate limit before processing request
- Return 429 Too Many Requests if limit exceeded
- Include `Retry-After` header with seconds until reset
- Track usage in sliding window

### 9.3 Rate Limit API

- `GET /admin/rate-limits/{tenant_id}` – Get tenant rate limits
- `PUT /admin/rate-limits/{tenant_id}` – Update tenant rate limits
- `GET /usage/rate-limits` – Get current usage vs limits (for tenant)

---

## 10. Usage Metering

### 10.1 Metered Resources

| Resource | Metric | Granularity |
|----------|--------|-------------|
| API Calls | Count by endpoint | Per minute, rolled up daily |
| Exceptions | Count ingested | Per minute, rolled up daily |
| Tool Executions | Count by tool_id | Per minute, rolled up daily |
| Events | Count by event_type | Per minute, rolled up daily |
| Storage | Bytes used | Daily snapshot |

### 10.2 Usage API

- `GET /usage/summary?tenant_id=...&period=day` – Usage summary
- `GET /usage/details?tenant_id=...&resource=api_calls&from=...&to=...` – Detailed usage
- `GET /usage/export?tenant_id=...&period=month` – Export usage for billing

---

## 11. UI Screens (Phase 10)

| Screen | Route | Purpose |
|--------|-------|---------|
| Ops Home | `/ops` | Overview with key metrics, alerts, DLQ summary |
| Worker Dashboard | `/ops/workers` | Worker fleet health and throughput |
| SLA Dashboard | `/ops/sla` | SLA compliance trends and breaches |
| DLQ Management | `/ops/dlq` | View, retry, discard dead-lettered events |
| Alerts Config | `/ops/alerts` | Configure alert rules and channels |
| Alert History | `/ops/alerts/history` | View past alerts and status |
| Audit Reports | `/ops/reports` | Generate and download reports |
| Usage Metering | `/ops/usage` | View resource usage by tenant |
| Config Changes | `/admin/config-changes` | Review and approve config changes |

---

## 12. Security Considerations

- **RBAC:** Only ADMIN and OPERATOR roles can access `/ops/*` endpoints
- **Tenant isolation:** Usage and reports scoped to tenant (except super-admin)
- **Audit trail:** All config changes, alert acknowledgments logged
- **Webhook security:** Support HMAC signing for webhook payloads
- **Rate limit bypass:** Super-admin can bypass rate limits for emergency access

---

## 13. Out of Scope (Phase 10)

- ML-based anomaly detection
- Auto-scaling worker fleet
- Multi-region deployment
- Cost allocation / billing integration
- Custom report builder
- Slack/Teams integrations (webhook covers general case)

---

## 14. Exit Criteria

Phase 10 is complete when:

### Backend
- [x] Ops APIs return worker health, throughput, error rates
- [x] SLA compliance APIs return trends and breach history
- [x] DLQ management APIs support retry and discard
- [x] Alerting service sends webhooks for configured alerts
- [x] Config change workflow enforces approval before apply
- [x] Audit report generation works asynchronously
- [x] Rate limiting enforced per tenant
- [x] Usage metering tracks API calls, events, tool executions

### UI (Backend APIs Complete)
- [x] Ops home shows key metrics and alerts (`/ops/dashboard/home`)
- [x] Worker dashboard shows health and throughput (`/ops/dashboard/workers`)
- [x] SLA dashboard shows compliance trends (`/ops/dashboard/sla`)
- [x] DLQ management allows view, retry, discard (`/ops/dashboard/dlq`)
- [x] Alert config allows rule and channel setup (`/alerts/*`)
- [x] Audit reports can be generated and downloaded (`/audit/reports/*`)
- [x] Usage metering shows resource consumption (`/usage/*`)

### Docs
- [x] Phase 10 implementation documented in this file
- [ ] Ops runbook updated with new capabilities
- [ ] Alert configuration guide created
- [ ] Rate limit configuration documented
- [ ] Config change governance workflow documented

### Tests
- [x] Unit tests for all new services (50 tests passing)
- [x] Integration tests for alert webhooks
- [ ] E2E tests for config change workflow
- [x] Rate limit enforcement tests

---

## 15. What Phase 10 Enables Next

- Phase 11: AI learning & optimization (using collected metrics)
- Phase 12: Marketplace & ecosystem (usage-based billing)
- Phase 13: Multi-region deployment (ops tooling ready)

---

## 16. Implementation Summary

### Implemented Components

#### Services
| Service | File | Description |
|---------|------|-------------|
| WorkerHealthService | `src/services/worker_health_service.py` | Monitors worker fleet health via HTTP probes |
| MetricsAggregationService | `src/services/metrics_aggregation_service.py` | Computes throughput, latency, error rates |
| SLAMetricsService | `src/services/sla_metrics_service.py` | Calculates SLA compliance and breach metrics |
| AlertingService | `src/services/alerting_service.py` | Evaluates alerts, dispatches webhooks/emails |
| AuditReportService | `src/services/audit_report_service.py` | Generates async audit reports |
| RateLimitService | `src/services/rate_limit_service.py` | Enforces per-tenant rate limits |
| UsageMeteringService | `src/services/usage_metering_service.py` | Tracks resource usage per tenant |

#### API Routes
| Route Prefix | File | Endpoints |
|--------------|------|-----------|
| `/ops/*` | `src/api/routes/ops.py` | Worker health, metrics, SLA |
| `/ops/dlq/*` | `src/api/routes/dlq.py` | DLQ management |
| `/ops/dashboard/*` | `src/api/routes/ops_dashboard.py` | Dashboard APIs |
| `/alerts/*` | `src/api/routes/alerts.py` | Alert config and history |
| `/admin/config-changes/*` | `src/api/routes/config_governance.py` | Config change approval |
| `/audit/reports/*` | `src/api/routes/audit_reports.py` | Audit report generation |
| `/admin/rate-limits/*` | `src/api/routes/rate_limits.py` | Rate limit management |
| `/usage/*` | `src/api/routes/usage.py` | Usage metering |

#### Database Models
| Model | Description |
|-------|-------------|
| AlertConfig | Alert configuration per tenant |
| AlertHistory | Alert trigger and resolution history |
| ConfigChangeRequest | Config change approval workflow |
| AuditReport | Generated audit report tracking |
| RateLimitConfig | Per-tenant rate limit configuration |
| RateLimitUsage | Rate limit usage tracking |
| UsageMetric | Usage metering records |

#### Repositories
| Repository | Description |
|------------|-------------|
| AlertConfigRepository | Alert configuration CRUD |
| AlertHistoryRepository | Alert history management |
| ConfigChangeRepository | Config change workflow |
| AuditReportRepository | Audit report tracking |
| DeadLetterEventRepository | DLQ management |

### Database Migrations
- `006_add_ops_tables.py` - Worker health, alerts, DLQ tables
- `007_add_audit_dlq_tables.py` - Additional audit tables
- `008_add_ops_governance_tables.py` - Alert config/history
- `009_add_config_change_request_table.py` - Config governance
- `010_add_audit_report_table.py` - Audit reports
- `011_add_rate_limit_tables.py` - Rate limiting
- `012_add_usage_metering_tables.py` - Usage metering

### Test Coverage
- 50 tests passing for Phase 10 components
- Service tests in `tests/services/`
- API tests in `tests/api/test_ops_routes.py`
