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

## Retries and DLQ Troubleshooting

### Understanding Retry Mechanism

Events that fail processing are automatically retried with exponential backoff:

1. **First Failure**: Retry after 1 second
2. **Second Failure**: Retry after 2 seconds
3. **Third Failure**: Retry after 4 seconds
4. **Fourth Failure**: Retry after 8 seconds
5. **After Max Retries**: Move to Dead Letter Queue (DLQ)

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


