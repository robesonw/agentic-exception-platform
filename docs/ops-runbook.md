# Operations Runbook

## Overview

This runbook provides operational procedures for running, scaling, monitoring, and troubleshooting the event-driven exception processing platform.

**Phase 9 P9-29: Operations Runbook**  
Reference: `docs/phase9-async-scale-mvp.md` Section 13

## Table of Contents

1. [Starting Kafka and Workers](#starting-kafka-and-workers)
2. [Scaling Workers](#scaling-workers)
3. [Monitoring and Metrics](#monitoring-and-metrics)
4. [Retries and DLQ Troubleshooting](#retries-and-dlq-troubleshooting)
5. [Common Issues and Solutions](#common-issues-and-solutions)

---

## Starting Kafka and Workers

### Prerequisites

- Docker and Docker Compose installed
- Python 3.11+ with virtual environment
- Database connection configured (`DATABASE_URL`)
- Kafka connection configured (`KAFKA_BOOTSTRAP_SERVERS`)

### Starting Kafka (Docker Compose)

```bash
# Start Kafka and dependencies
docker-compose up -d kafka zookeeper

# Verify Kafka is running
docker-compose ps

# Check Kafka logs
docker-compose logs -f kafka

# Verify Kafka health
docker exec -it sentinai-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092
```

### Starting Kafka (Standalone)

If using a standalone Kafka installation:

```bash
# Start Zookeeper (if not using KRaft mode)
bin/zookeeper-server-start.sh config/zookeeper.properties

# Start Kafka
bin/kafka-server-start.sh config/server.properties

# Verify Kafka is running
bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092
```

### Starting Workers

Workers are started using environment variables for configuration:

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate  # Windows

# Set environment variables
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/sentinai
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Start Intake Worker
WORKER_TYPE=intake CONCURRENCY=2 GROUP_ID=intake-workers python -m src.workers

# Start Triage Worker (in separate terminal)
WORKER_TYPE=triage CONCURRENCY=4 GROUP_ID=triage-workers python -m src.workers

# Start Policy Worker (in separate terminal)
WORKER_TYPE=policy CONCURRENCY=2 GROUP_ID=policy-workers python -m src.workers

# Start Playbook Worker (in separate terminal)
WORKER_TYPE=playbook CONCURRENCY=2 GROUP_ID=playbook-workers python -m src.workers

# Start Tool Worker (in separate terminal)
WORKER_TYPE=tool CONCURRENCY=4 GROUP_ID=tool-workers python -m src.workers

# Start Feedback Worker (in separate terminal)
WORKER_TYPE=feedback CONCURRENCY=2 GROUP_ID=feedback-workers python -m src.workers

# Start SLA Monitor Worker (in separate terminal)
WORKER_TYPE=sla_monitor CONCURRENCY=1 GROUP_ID=sla-monitors python -m src.workers
```

### Starting Workers (Docker)

```bash
# Build worker image
docker build -t exception-platform-worker:latest .

# Start Intake Worker
docker run -d \
  --name intake-worker-1 \
  -e WORKER_TYPE=intake \
  -e CONCURRENCY=2 \
  -e GROUP_ID=intake-workers \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/sentinai \
  -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
  exception-platform-worker:latest

# Start additional workers similarly
```

### Starting Workers (Kubernetes)

```bash
# Apply worker deployment
kubectl apply -f k8s/workers/intake-worker-deployment.yaml

# Scale workers
kubectl scale deployment intake-worker --replicas=3

# Check worker status
kubectl get pods -l app=intake-worker
kubectl logs -f deployment/intake-worker
```

### Verifying Workers are Running

```bash
# Check worker logs for startup messages
# Should see: "Initialized IntakeWorker worker: topics=['exceptions'], group_id=intake-workers, concurrency=2"

# Check Kafka consumer groups
docker exec -it sentinai-kafka /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --list

# Check consumer group details
docker exec -it sentinai-kafka /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group intake-workers \
  --describe
```

---

## Scaling Workers

### Horizontal Scaling (Multiple Instances)

Scale by running multiple worker instances with the same `GROUP_ID`:

```bash
# Instance 1
WORKER_TYPE=intake CONCURRENCY=2 GROUP_ID=intake-workers python -m src.workers

# Instance 2 (same group_id for load balancing)
WORKER_TYPE=intake CONCURRENCY=2 GROUP_ID=intake-workers python -m src.workers

# Instance 3
WORKER_TYPE=intake CONCURRENCY=2 GROUP_ID=intake-workers python -m src.workers
```

**How it works:**
- Kafka consumer groups automatically distribute partitions across instances
- Each instance processes a subset of partitions
- Messages are load-balanced across instances

### Vertical Scaling (Concurrency)

Scale by increasing `CONCURRENCY` within a single instance:

```bash
# Single instance with 8 concurrent processors
WORKER_TYPE=intake CONCURRENCY=8 GROUP_ID=intake-workers python -m src.workers
```

**How it works:**
- Thread pool executor processes multiple events concurrently
- Limited by CPU cores and I/O capacity
- Useful for I/O-bound workloads (database queries, API calls)

### Scaling with Docker Compose

```bash
# Scale intake workers to 5 instances
docker-compose up --scale intake-worker=5

# Scale triage workers to 3 instances
docker-compose up --scale triage-worker=3
```

### Scaling with Kubernetes

```bash
# Scale deployment
kubectl scale deployment intake-worker --replicas=5

# Use Horizontal Pod Autoscaler (HPA)
kubectl apply -f k8s/workers/intake-worker-hpa.yaml

# Check HPA status
kubectl get hpa intake-worker-hpa
```

### Scaling Recommendations

| Worker Type | Recommended Instances | Recommended Concurrency | Notes |
|------------|----------------------|----------------------|-------|
| intake | 2-5 | 2-4 | I/O-bound (database writes) |
| triage | 3-10 | 4-8 | CPU-bound (LLM calls) |
| policy | 2-5 | 2-4 | I/O-bound (policy evaluation) |
| playbook | 2-5 | 2-4 | I/O-bound (playbook execution) |
| tool | 3-10 | 4-8 | I/O-bound (tool execution) |
| feedback | 2-5 | 2-4 | I/O-bound (memory updates) |
| sla_monitor | 1-2 | 1 | Lightweight, periodic checks |

### Monitoring Scaling Effectiveness

```bash
# Check Kafka consumer lag (indicates if scaling is needed)
docker exec -it sentinai-kafka /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group intake-workers \
  --describe

# Check Prometheus metrics
curl http://localhost:8000/metrics | grep events_processed

# Check worker health
curl http://localhost:8000/health/workers
```

---

## Monitoring and Metrics

### Prometheus Metrics Endpoint

The platform exposes Prometheus-style metrics at `/metrics`:

```bash
# Query metrics
curl http://localhost:8000/metrics

# Filter specific metrics
curl http://localhost:8000/metrics | grep events_processed
curl http://localhost:8000/metrics | grep processing_latency
curl http://localhost:8000/metrics | grep failures
```

### Key Metrics

#### Event Processing Metrics

- `events_processed_total`: Total events processed (by worker_type, event_type, tenant_id, status)
- `processing_latency_seconds`: Event processing duration (histogram)
- `failures_total`: Processing failures (by worker_type, event_type, tenant_id, error_type)
- `retries_total`: Retry attempts (by worker_type, event_type, tenant_id)
- `dlq_size`: Current size of Dead Letter Queue (gauge)
- `events_in_processing`: Events currently being processed (gauge)

#### Example Queries

```promql
# Events processed per second
rate(events_processed_total[5m])

# Average processing latency
histogram_quantile(0.95, processing_latency_seconds_bucket)

# Failure rate
rate(failures_total[5m]) / rate(events_processed_total[5m])

# DLQ size
dlq_size

# Events in processing queue
events_in_processing
```

### Grafana Dashboards

Create Grafana dashboards using Prometheus metrics:

1. **Event Processing Rate**: `rate(events_processed_total[5m])`
2. **Processing Latency**: `histogram_quantile(0.95, processing_latency_seconds_bucket)`
3. **Failure Rate**: `rate(failures_total[5m]) / rate(events_processed_total[5m])`
4. **DLQ Size**: `dlq_size`
5. **Consumer Lag**: Kafka consumer lag metrics

### Distributed Tracing

Events include `correlation_id` (typically `exception_id`) for distributed tracing:

```bash
# Query trace for an exception
curl http://localhost:8000/api/exceptions/{tenant_id}/{exception_id}/trace

# Query all events for an exception
curl http://localhost:8000/api/exceptions/{exception_id}/events
```

### Logging

Workers log to stdout/stderr. In production, use structured logging:

```bash
# View worker logs
docker logs -f intake-worker-1

# Filter logs by tenant
docker logs intake-worker-1 | grep "tenant_id=TENANT_001"

# Filter logs by exception
docker logs intake-worker-1 | grep "exception_id=EXC_001"
```

### Health Checks

```bash
# API health check
curl http://localhost:8000/health

# Database health check
curl http://localhost:8000/health/db

# Worker health (if exposed)
curl http://localhost:8000/health/workers
```

---

## Retries and DLQ Management

### Understanding Retry Mechanism

Events that fail processing are automatically retried with exponential backoff:

1. **First Failure**: Retry after 1 second
2. **Second Failure**: Retry after 2 seconds
3. **Third Failure**: Retry after 4 seconds
4. **Fourth Failure**: Retry after 8 seconds
5. **After Max Retries**: Move to Dead Letter Queue (DLQ)

### DLQ Management Procedures

#### Viewing DLQ Entries

```bash
# List DLQ entries for a tenant
GET /ops/dlq?tenant_id=TENANT_001&limit=100&offset=0

# Get DLQ statistics
GET /ops/dlq/stats?tenant_id=TENANT_001

# Get specific DLQ entry details
GET /ops/dlq/{dlq_id}?tenant_id=TENANT_001
```

#### Retrying DLQ Entries

**Single Retry:**
```bash
# Retry a single DLQ entry
POST /ops/dlq/{dlq_id}/retry?tenant_id=TENANT_001
{
  "reason": "Root cause fixed, retrying event"
}
```

**Batch Retry:**
```bash
# Retry multiple DLQ entries
POST /ops/dlq/retry-batch?tenant_id=TENANT_001
{
  "dlq_ids": [1, 2, 3, 4, 5],
  "reason": "Bulk retry after system fix"
}
```

**Retry Process:**
1. Entry status changes to `retrying`
2. Event is re-published to original Kafka topic
3. Worker processes the event
4. On success: Entry status changes to `succeeded`
5. On failure: Entry status reverts to `pending`, retry_count increments

#### Discarding DLQ Entries

```bash
# Discard a DLQ entry (mark as resolved without retry)
POST /ops/dlq/{dlq_id}/discard?tenant_id=TENANT_001&actor=operator@example.com
{
  "reason": "Event is no longer relevant, safe to discard"
}
```

**When to Discard:**
- Event is no longer relevant (e.g., exception already resolved manually)
- Event is a duplicate
- Event payload is invalid and cannot be fixed
- Event is from a test/debug scenario

**Discard Process:**
1. Entry status changes to `discarded`
2. `discarded_at` timestamp is recorded
3. `discarded_by` actor is recorded
4. Entry is excluded from active DLQ counts

#### DLQ Entry Status

| Status | Description | Actions Available |
|--------|-------------|-------------------|
| **pending** | Awaiting retry or discard | Retry, Discard |
| **retrying** | Currently being retried | None (wait for completion) |
| **succeeded** | Successfully retried | None (closed) |
| **discarded** | Manually discarded | None (closed) |

#### DLQ Monitoring

**Check DLQ Growth:**
```bash
# Get DLQ stats
GET /ops/dlq/stats?tenant_id=TENANT_001

# Response includes:
# - total_entries: Total DLQ entries
# - pending_count: Entries awaiting action
# - retrying_count: Currently retrying
# - discarded_count: Discarded entries
# - succeeded_count: Successfully retried
# - by_event_type: Breakdown by event type
# - by_worker_type: Breakdown by worker type
```

**Set Up DLQ Growth Alerts:**
```bash
# Configure DLQ growth alert
PUT /alerts/config/DLQ_GROWTH?tenant_id=TENANT_001
{
  "enabled": true,
  "threshold": 100,
  "threshold_unit": "count",
  "channels": [
    {
      "type": "webhook",
      "url": "https://your-webhook.com/dlq-alerts"
    }
  ]
}
```

#### DLQ Best Practices

1. **Monitor regularly**: Check DLQ stats daily
2. **Investigate patterns**: Group failures by event_type, worker_type, error_message
3. **Fix root causes**: Don't just retry; fix underlying issues
4. **Use batch retry**: Retry multiple related entries together
5. **Document discards**: Always provide a reason when discarding
6. **Set up alerts**: Configure DLQ_GROWTH alerts to catch issues early
7. **Review retry counts**: High retry_count indicates persistent issues

### Checking Retry Status

```bash
# Query event processing repository for retry status
# (Requires database access)

# Check events in retry state
SELECT * FROM event_processing_log 
WHERE status = 'retrying' 
ORDER BY retry_count DESC;

# Check events that failed
SELECT * FROM event_processing_log 
WHERE status = 'failed' 
ORDER BY last_attempt_at DESC;
```

### Dead Letter Queue (DLQ)

Events that fail after max retries are moved to DLQ:

```bash
# Query DLQ entries
SELECT * FROM dead_letter_queue 
ORDER BY created_at DESC 
LIMIT 100;

# Get DLQ size
SELECT COUNT(*) FROM dead_letter_queue;
```

### Troubleshooting Failed Events

#### Step 1: Identify Failed Events

```bash
# Check DLQ for recent failures
SELECT 
  event_id,
  event_type,
  tenant_id,
  exception_id,
  error_message,
  retry_count,
  created_at
FROM dead_letter_queue
ORDER BY created_at DESC
LIMIT 20;
```

#### Step 2: Analyze Error Patterns

```bash
# Group failures by error type
SELECT 
  error_type,
  COUNT(*) as count
FROM dead_letter_queue
GROUP BY error_type
ORDER BY count DESC;

# Group failures by tenant
SELECT 
  tenant_id,
  COUNT(*) as count
FROM dead_letter_queue
GROUP BY tenant_id
ORDER BY count DESC;
```

#### Step 3: Investigate Root Cause

```bash
# Check worker logs for specific event
docker logs intake-worker-1 | grep "event_id=EVT_123"

# Check event store for event details
SELECT * FROM event_log WHERE event_id = 'EVT_123';

# Check exception state
SELECT * FROM exceptions WHERE exception_id = 'EXC_123';
```

#### Step 4: Resolve and Replay

**Option A: Fix Root Cause and Replay**

```bash
# After fixing the issue, replay events from DLQ
# (Requires custom script or API endpoint)

# Example: Replay single event
POST /api/admin/dlq/{dlq_id}/replay

# Example: Replay all events for tenant
POST /api/admin/dlq/replay?tenant_id=TENANT_001
```

**Option B: Manual Retry**

```bash
# Manually republish event from DLQ
# 1. Extract event from DLQ
# 2. Republish to Kafka topic
# 3. Remove from DLQ
```

### Common Failure Scenarios

#### 1. Database Connection Errors

**Symptoms:**
- Events fail with "database connection" errors
- High retry count
- Events eventually go to DLQ

**Solutions:**
- Check database connectivity: `curl http://localhost:8000/health/db`
- Verify connection pool settings
- Check database load and capacity
- Increase connection pool size if needed

#### 2. Validation Errors

**Symptoms:**
- Events fail with "validation_error" immediately
- No retries (validation errors don't retry)

**Solutions:**
- Check event schema compliance
- Verify tenant_id and exception_id are present
- Check event payload structure
- Review validation rules

#### 3. Timeout Errors

**Symptoms:**
- Events fail with "timeout" errors
- High latency metrics
- Events retry multiple times

**Solutions:**
- Increase worker timeout settings
- Check downstream service availability
- Optimize slow database queries
- Consider increasing concurrency for I/O-bound workloads

#### 4. Rate Limiting

**Symptoms:**
- Events fail with "Rate limit exceeded" errors
- Backpressure events emitted
- Events throttled

**Solutions:**
- Check per-tenant rate limits
- Adjust rate limit configuration
- Scale workers horizontally
- Review rate limit policies

### Preventing DLQ Growth

1. **Monitor DLQ Size**: Set up alerts for DLQ size thresholds
2. **Investigate Failures Early**: Review DLQ entries regularly
3. **Fix Root Causes**: Don't just replay events; fix underlying issues
4. **Tune Retry Policies**: Adjust retry counts and backoff for different error types
5. **Scale Workers**: Ensure sufficient worker capacity to handle load

## Rate Limiting

### Rate Limit Configuration

The platform supports per-tenant rate limits for:
- **API requests**: API calls per minute
- **Events ingested**: Events ingested per minute
- **Tool executions**: Tool executions per minute
- **Report generations**: Report generations per day

### Viewing Rate Limits

```bash
# Get all rate limit configurations for a tenant
GET /admin/rate-limits/{tenant_id}

# Get current usage vs limits
GET /usage/rate-limits?tenant_id=TENANT_001
```

### Adjusting Rate Limits

**Update Rate Limit:**
```bash
# Update API request rate limit
PUT /admin/rate-limits/{tenant_id}
{
  "limit_type": "api_requests",
  "limit_value": 1000,
  "window_seconds": 60,
  "enabled": true
}
```

**Rate Limit Parameters:**
- **limit_type**: One of `api_requests`, `events_ingested`, `tool_executions`, `report_generations`
- **limit_value**: Maximum allowed per window (integer, >= 1)
- **window_seconds**: Time window in seconds (default: 60 for per-minute limits)
- **enabled**: Whether the limit is active (default: true)

**Delete Rate Limit (Use Defaults):**
```bash
# Delete custom rate limit (revert to defaults)
DELETE /admin/rate-limits/{tenant_id}?limit_type=api_requests
```

### Rate Limit Enforcement

When a rate limit is exceeded:
- API returns `429 Too Many Requests`
- Response includes `Retry-After` header with seconds until reset
- Request is not processed
- Usage counter is still incremented (to prevent retry storms)

**Example Response:**
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 45
Content-Type: application/json

{
  "detail": "Rate limit exceeded: api_requests (1000/60s)",
  "limit_type": "api_requests",
  "limit": 1000,
  "current": 1001,
  "reset_at": "2025-01-15T10:31:00Z"
}
```

### Rate Limit Adjustment Procedures

#### Increasing Rate Limits

**Scenario**: Tenant needs higher API request rate

1. **Check current usage**:
   ```bash
   GET /usage/rate-limits?tenant_id=TENANT_001
   ```

2. **Review usage patterns**: Check if current limit is consistently hit

3. **Update limit**:
   ```bash
   PUT /admin/rate-limits/{tenant_id}
   {
     "limit_type": "api_requests",
     "limit_value": 2000,  # Increase from 1000 to 2000
     "window_seconds": 60,
     "enabled": true
   }
   ```

4. **Monitor after change**: Watch for any issues

#### Decreasing Rate Limits

**Scenario**: Tenant is abusing resources, need to throttle

1. **Notify tenant**: Inform tenant of rate limit reduction

2. **Update limit**:
   ```bash
   PUT /admin/rate-limits/{tenant_id}
   {
     "limit_type": "api_requests",
     "limit_value": 500,  # Decrease from 1000 to 500
     "window_seconds": 60,
     "enabled": true
   }
   ```

3. **Monitor impact**: Check for increased 429 responses

#### Resetting Usage Counters

**Scenario**: Need to reset usage counters (e.g., after incident)

```bash
# Note: There is no explicit reset endpoint in MVP
# Usage counters reset automatically when window expires
# To force reset, wait for window_seconds to elapse
```

**Workaround**: Temporarily disable and re-enable the limit:
```bash
# Disable
PUT /admin/rate-limits/{tenant_id}
{
  "limit_type": "api_requests",
  "limit_value": 1000,
  "window_seconds": 60,
  "enabled": false
}

# Wait a moment, then re-enable
PUT /admin/rate-limits/{tenant_id}
{
  "limit_type": "api_requests",
  "limit_value": 1000,
  "window_seconds": 60,
  "enabled": true
}
```

### Rate Limit Bypass

**Super-admin bypass**: Users with super-admin role can bypass rate limits for emergency access. This is handled automatically by the middleware.

### Rate Limit Best Practices

1. **Start with defaults**: Use default limits unless tenant has specific needs
2. **Monitor usage**: Regularly check usage vs limits
3. **Adjust gradually**: Increase limits incrementally, not all at once
4. **Set appropriate windows**: Use 60s for per-minute, 86400s for per-day
5. **Document changes**: Record why limits were adjusted
6. **Alert on high usage**: Set up alerts for tenants approaching limits

## Audit Report Generation

### Report Types

The platform supports the following audit report types:

| Report Type | Description | Data Source |
|-------------|-------------|-------------|
| **exception_activity** | All exceptions with status changes | `exception`, `exception_event` tables |
| **tool_execution** | All tool executions with outcomes | `tool_execution` table |
| **policy_decisions** | All policy evaluations with actions | `exception_event` table |
| **config_changes** | All config change requests and outcomes | `config_change_request` table |
| **sla_compliance** | SLA metrics summary | `exception`, `exception_event` tables |

### Generating Reports

**Request Report Generation:**
```bash
POST /audit/reports?tenant_id=TENANT_001&requested_by=operator@example.com
{
  "report_type": "exception_activity",
  "title": "Exception Activity Report - January 2025",
  "format": "csv",
  "parameters": {
    "from_date": "2025-01-01T00:00:00Z",
    "to_date": "2025-01-31T23:59:59Z"
  }
}
```

**Report Parameters:**
- **from_date**: Start date (ISO format or YYYY-MM-DD)
- **to_date**: End date (ISO format or YYYY-MM-DD)
- Additional filters vary by report type

**Response:**
```json
{
  "id": "report-001",
  "status": "generating",
  "download_url": null,
  "requested_at": "2025-01-15T10:00:00Z"
}
```

### Checking Report Status

```bash
# Get report status
GET /audit/reports/{report_id}?tenant_id=TENANT_001
```

**Report Status:**
- **pending**: Report request created, not yet started
- **generating**: Report is being generated
- **completed**: Report is ready for download
- **failed**: Report generation failed
- **expired**: Download URL has expired

### Downloading Reports

```bash
# Download completed report
GET /audit/reports/{report_id}/download?tenant_id=TENANT_001
```

**Download Details:**
- Reports are stored with expiring download URLs (default: 24 hours)
- Download URL is provided in report status response
- File format matches requested format (CSV, JSON, PDF)

### Listing Reports

```bash
# List all reports for tenant
GET /audit/reports?tenant_id=TENANT_001&status=completed&page=1&page_size=50

# Get report statistics
GET /audit/reports/stats?tenant_id=TENANT_001
```

### Report Generation Procedures

#### Generating Exception Activity Report

**Use Case**: Compliance audit of all exception processing

```bash
POST /audit/reports?tenant_id=TENANT_001&requested_by=auditor@example.com
{
  "report_type": "exception_activity",
  "title": "Q1 2025 Exception Activity",
  "format": "csv",
  "parameters": {
    "from_date": "2025-01-01",
    "to_date": "2025-03-31"
  }
}
```

**Report Contents:**
- Exception ID, tenant ID, status, severity
- Created at, resolved at, SLA deadline
- All status change events with timestamps
- Playbook assignments and completions

#### Generating Tool Execution Report

**Use Case**: Review all tool executions for security audit

```bash
POST /audit/reports?tenant_id=TENANT_001&requested_by=security@example.com
{
  "report_type": "tool_execution",
  "title": "Tool Execution Audit - January 2025",
  "format": "json",
  "parameters": {
    "from_date": "2025-01-01T00:00:00Z",
    "to_date": "2025-01-31T23:59:59Z",
    "tool_id": "optional-tool-filter"
  }
}
```

**Report Contents:**
- Tool ID, tool name, execution ID
- Input payload (sanitized), output result
- Execution status, duration
- Exception ID, tenant ID, actor

#### Generating SLA Compliance Report

**Use Case**: Monthly SLA compliance review

```bash
POST /audit/reports?tenant_id=TENANT_001&requested_by=ops@example.com
{
  "report_type": "sla_compliance",
  "title": "SLA Compliance Report - January 2025",
  "format": "pdf",
  "parameters": {
    "from_date": "2025-01-01",
    "to_date": "2025-01-31",
    "period": "month"
  }
}
```

**Report Contents:**
- SLA compliance rate by day/week/month
- Breach count and details
- Average resolution time by severity
- At-risk exceptions

### Report Generation Best Practices

1. **Use appropriate format**: CSV for data analysis, JSON for APIs, PDF for presentations
2. **Set reasonable date ranges**: Large date ranges may take longer to generate
3. **Monitor generation status**: Poll status endpoint for large reports
4. **Download promptly**: Download URLs expire after 24 hours
5. **Store reports securely**: Downloaded reports may contain sensitive data
6. **Schedule regular reports**: Generate compliance reports on a schedule
7. **Document report purpose**: Use descriptive titles for report tracking

### Troubleshooting Report Generation

**Report Stuck in "generating" Status:**
1. Check backend logs for errors
2. Verify database connectivity
3. Check for large date ranges (may take time)
4. Retry report generation if needed

**Report Generation Fails:**
1. Check error_message in report status
2. Verify date range is valid
3. Check tenant_id is correct
4. Review backend logs for specific errors

**Download URL Expired:**
1. Generate new report with same parameters
2. Download immediately after generation
3. Consider extending expiration (if configurable)

**Report Missing Data:**
1. Verify date range includes expected data
2. Check tenant_id is correct
3. Verify data exists in database for date range
4. Review report parameters for filters

---

## Common Issues and Solutions

### Issue: Workers Not Processing Events

**Symptoms:**
- Events published but not processed
- Consumer lag increasing
- No worker logs

**Solutions:**
1. Check workers are running: `docker ps | grep worker`
2. Check Kafka connectivity: `docker exec -it sentinai-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092`
3. Check consumer groups: `docker exec -it sentinai-kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list`
4. Check worker logs: `docker logs -f intake-worker-1`
5. Verify GROUP_ID matches across instances

### Issue: High Consumer Lag

**Symptoms:**
- Consumer lag increasing over time
- Events processing slowly
- Backlog of unprocessed events

**Solutions:**
1. Scale workers horizontally: Add more instances
2. Increase concurrency: Increase `CONCURRENCY` per worker
3. Check worker performance: Review metrics and logs
4. Optimize processing: Identify bottlenecks
5. Check database performance: Slow queries can cause lag

### Issue: Duplicate Event Processing

**Symptoms:**
- Same event processed multiple times
- Duplicate database records
- Idempotency not working

**Solutions:**
1. Verify EventProcessingRepository is configured
2. Check idempotency checks are enabled in workers
3. Review event_id generation (should be UUID)
4. Check database constraints for uniqueness

### Issue: Tenant Isolation Violations

**Symptoms:**
- Events from one tenant visible to another
- Cross-tenant data access
- Security concerns

**Solutions:**
1. Verify tenant_id validation in workers
2. Check database queries include tenant_id filter
3. Review event store queries for tenant isolation
4. Audit worker logs for tenant validation failures

### Issue: Memory Leaks

**Symptoms:**
- Worker memory usage increasing over time
- Workers crashing with OOM errors
- Performance degradation

**Solutions:**
1. Review worker code for memory leaks
2. Check database connection pool management
3. Monitor memory metrics: `docker stats`
4. Restart workers periodically if needed
5. Increase worker memory limits

### Issue: Kafka Connection Failures

**Symptoms:**
- Workers can't connect to Kafka
- Events not published
- Connection timeout errors

**Solutions:**
1. Check Kafka is running: `docker ps | grep kafka`
2. Verify KAFKA_BOOTSTRAP_SERVERS environment variable
3. Check network connectivity
4. Review Kafka logs: `docker logs -f sentinai-kafka`
5. Verify Kafka health: `docker exec -it sentinai-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092`

---

## Emergency Procedures

### Graceful Shutdown

```bash
# Stop workers gracefully (SIGTERM)
docker stop intake-worker-1

# Or use docker-compose
docker-compose stop intake-worker

# Workers will:
# 1. Stop consuming new messages
# 2. Finish processing current messages
# 3. Commit offsets
# 4. Close connections
```

### Force Shutdown

```bash
# Force stop workers (SIGKILL)
docker kill intake-worker-1

# Note: May cause message loss if events are in-flight
```

### Restart All Workers

```bash
# Restart all workers
docker-compose restart

# Or restart specific worker type
docker-compose restart intake-worker
```

### Clear DLQ

**Warning**: Only clear DLQ after investigating and fixing root causes.

```bash
# Clear DLQ for specific tenant
DELETE FROM dead_letter_queue WHERE tenant_id = 'TENANT_001';

# Clear all DLQ entries (use with caution)
TRUNCATE TABLE dead_letter_queue;
```

---

## References

- `docs/phase9-async-scale-mvp.md` - Phase 9 async scaling MVP specification
- `docs/worker-scaling-guide.md` - Detailed worker scaling guide
- `docs/testing-e2e-async-flow.md` - E2E testing guide
- `src/workers/config.py` - Worker configuration module
- `src/workers/base.py` - Base worker implementation


