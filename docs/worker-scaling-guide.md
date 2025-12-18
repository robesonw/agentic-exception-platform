# Worker Scaling Guide

## Overview

This guide explains how to scale workers horizontally using environment-driven configuration and container orchestration (Docker/Kubernetes).

**Phase 9 P9-26: Worker Scaling Configuration**  
Reference: `docs/phase9-async-scale-mvp.md` Section 9

## Worker Configuration

Workers are configured via environment variables:

- **WORKER_TYPE**: Type of worker to run (required)
  - Supported types: `intake`, `triage`, `policy`, `playbook`, `tool`, `feedback`, `sla_monitor`
- **CONCURRENCY**: Number of parallel event processors (default: 1)
- **GROUP_ID**: Consumer group ID for load balancing (default: worker_type)

### Example Configuration

```bash
# Single-threaded intake worker
WORKER_TYPE=intake CONCURRENCY=1 GROUP_ID=intake-workers python -m src.workers

# Multi-threaded triage worker with 4 concurrent processors
WORKER_TYPE=triage CONCURRENCY=4 GROUP_ID=triage-workers python -m src.workers

# SLA monitor worker
WORKER_TYPE=sla_monitor CONCURRENCY=1 GROUP_ID=sla-monitors python -m src.workers
```

## Stateless Workers

All workers are **stateless** by design:

- No shared in-memory state between worker instances
- All state is persisted in the database (event store, exception records, etc.)
- Workers can be scaled horizontally without coordination
- Idempotency is enforced via `EventProcessingRepository`

### Stateless Design Principles

1. **No Shared State**: Workers don't share memory or filesystem state
2. **Database as Source of Truth**: All state is in the database
3. **Idempotent Processing**: Events can be processed multiple times safely
4. **Tenant Isolation**: Each worker validates tenant_id before processing

## Scaling Strategies

### 1. Horizontal Scaling (Multiple Instances)

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

### 2. Vertical Scaling (Concurrency)

Scale by increasing `CONCURRENCY` within a single instance:

```bash
# Single instance with 8 concurrent processors
WORKER_TYPE=intake CONCURRENCY=8 GROUP_ID=intake-workers python -m src.workers
```

**How it works:**
- Thread pool executor processes multiple events concurrently
- Limited by CPU cores and I/O capacity
- Useful for I/O-bound workloads (database queries, API calls)

### 3. Hybrid Scaling

Combine both strategies:

```bash
# 3 instances, each with 4 concurrent processors = 12 total processors
WORKER_TYPE=intake CONCURRENCY=4 GROUP_ID=intake-workers python -m src.workers  # Instance 1
WORKER_TYPE=intake CONCURRENCY=4 GROUP_ID=intake-workers python -m src.workers  # Instance 2
WORKER_TYPE=intake CONCURRENCY=4 GROUP_ID=intake-workers python -m src.workers  # Instance 3
```

## Docker Deployment

### Dockerfile Example

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Set default environment variables
ENV WORKER_TYPE=intake
ENV CONCURRENCY=1
ENV GROUP_ID=intake-workers

# Run worker
CMD ["python", "-m", "src.workers"]
```

### Docker Compose Example

```yaml
version: '3.8'

services:
  intake-worker-1:
    build: .
    environment:
      - WORKER_TYPE=intake
      - CONCURRENCY=2
      - GROUP_ID=intake-workers
      - DATABASE_URL=postgresql://user:pass@db:5432/exceptions
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    depends_on:
      - db
      - kafka

  intake-worker-2:
    build: .
    environment:
      - WORKER_TYPE=intake
      - CONCURRENCY=2
      - GROUP_ID=intake-workers
      - DATABASE_URL=postgresql://user:pass@db:5432/exceptions
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    depends_on:
      - db
      - kafka

  triage-worker:
    build: .
    environment:
      - WORKER_TYPE=triage
      - CONCURRENCY=4
      - GROUP_ID=triage-workers
      - DATABASE_URL=postgresql://user:pass@db:5432/exceptions
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    depends_on:
      - db
      - kafka

  policy-worker:
    build: .
    environment:
      - WORKER_TYPE=policy
      - CONCURRENCY=2
      - GROUP_ID=policy-workers
      - DATABASE_URL=postgresql://user:pass@db:5432/exceptions
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    depends_on:
      - db
      - kafka
```

### Scaling with Docker Compose

```bash
# Scale intake workers to 5 instances
docker-compose up --scale intake-worker=5

# Scale triage workers to 3 instances
docker-compose up --scale triage-worker=3
```

## Kubernetes Deployment

### Deployment Manifest Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: intake-worker
spec:
  replicas: 3  # 3 instances for horizontal scaling
  selector:
    matchLabels:
      app: intake-worker
  template:
    metadata:
      labels:
        app: intake-worker
    spec:
      containers:
      - name: worker
        image: your-registry/exception-platform-worker:latest
        env:
        - name: WORKER_TYPE
          value: "intake"
        - name: CONCURRENCY
          value: "4"  # 4 concurrent processors per instance
        - name: GROUP_ID
          value: "intake-workers"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        - name: KAFKA_BOOTSTRAP_SERVERS
          value: "kafka:9092"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "2000m"
        livenessProbe:
          exec:
            command:
            - python
            - -c
            - "import sys; sys.exit(0)"  # Simple health check
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command:
            - python
            - -c
            - "import sys; sys.exit(0)"
          initialDelaySeconds: 10
          periodSeconds: 5
```

### Horizontal Pod Autoscaler (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: intake-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: intake-worker
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Scaling Commands

```bash
# Scale intake workers to 5 replicas
kubectl scale deployment intake-worker --replicas=5

# Scale triage workers to 3 replicas
kubectl scale deployment triage-worker --replicas=3

# Auto-scale based on CPU/memory (requires HPA)
kubectl apply -f intake-worker-hpa.yaml
```

## Resource Requirements

### Per Worker Type

| Worker Type | CPU (requests) | Memory (requests) | Recommended Concurrency |
|------------|----------------|-------------------|-------------------------|
| intake      | 500m           | 512Mi             | 2-4                     |
| triage      | 1000m          | 1Gi               | 4-8                     |
| policy      | 500m           | 512Mi             | 2-4                     |
| playbook    | 500m           | 512Mi             | 2-4                     |
| tool        | 1000m          | 1Gi               | 4-8                     |
| feedback    | 500m           | 512Mi             | 2-4                     |
| sla_monitor | 200m           | 256Mi             | 1                       |

### Scaling Recommendations

1. **Start Small**: Begin with 1 instance per worker type, concurrency=1
2. **Monitor Metrics**: Use Prometheus metrics (`/metrics` endpoint) to track:
   - Events processed per second
   - Processing latency
   - Error rates
   - Events in processing queue
3. **Scale Gradually**: Increase replicas/concurrency based on metrics
4. **Consider Workload**: 
   - I/O-bound (database queries): Higher concurrency
   - CPU-bound (LLM calls): Lower concurrency, more instances

## Best Practices

1. **Use Consumer Groups**: Always use the same `GROUP_ID` for instances of the same worker type
2. **Monitor Lag**: Track Kafka consumer lag to detect bottlenecks
3. **Graceful Shutdown**: Workers handle SIGTERM/SIGINT for graceful shutdown
4. **Health Checks**: Implement health check endpoints for Kubernetes liveness/readiness probes
5. **Resource Limits**: Set CPU/memory limits to prevent resource exhaustion
6. **Idempotency**: Rely on database idempotency checks, not worker coordination

## Troubleshooting

### Workers Not Processing Messages

- Check `GROUP_ID` matches across instances
- Verify Kafka connectivity (`KAFKA_BOOTSTRAP_SERVERS`)
- Check database connectivity (`DATABASE_URL`)
- Review worker logs for errors

### High Latency

- Increase `CONCURRENCY` for I/O-bound workloads
- Add more instances for CPU-bound workloads
- Check database connection pool size
- Monitor Kafka consumer lag

### Memory Issues

- Reduce `CONCURRENCY` if memory usage is high
- Increase memory limits in Kubernetes
- Check for memory leaks in worker code

## Example: Full Stack Deployment

```yaml
# Kubernetes deployment for all worker types
apiVersion: apps/v1
kind: Deployment
metadata:
  name: exception-workers
spec:
  replicas: 1
  selector:
    matchLabels:
      app: exception-worker
  template:
    metadata:
      labels:
        app: exception-worker
    spec:
      containers:
      - name: worker
        image: your-registry/exception-platform-worker:latest
        env:
        - name: WORKER_TYPE
          value: "intake"  # Change per deployment
        - name: CONCURRENCY
          value: "4"
        - name: GROUP_ID
          value: "intake-workers"  # Change per deployment
        # ... other env vars
```

Deploy multiple deployments, one per worker type:

```bash
# Deploy intake workers
kubectl apply -f intake-worker-deployment.yaml

# Deploy triage workers
kubectl apply -f triage-worker-deployment.yaml

# Deploy policy workers
kubectl apply -f policy-worker-deployment.yaml
```

## References

- `docs/phase9-async-scale-mvp.md` - Phase 9 async scaling MVP specification
- `src/workers/config.py` - Worker configuration module
- `src/workers/base.py` - Base worker implementation
- `src/workers/__main__.py` - Worker entry point


