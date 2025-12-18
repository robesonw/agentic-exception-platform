# Workers Quick Start Guide

## Why Workers Are Needed

The platform uses an **event-driven architecture** for processing exceptions:

1. **Exception Ingestion**: When you ingest an exception via the API (`POST /exceptions/{tenant_id}`), it publishes an `ExceptionIngested` event to Kafka
2. **Worker Processing**: Workers consume these events and process exceptions through the pipeline:
   - `IntakeWorker` → Normalizes exceptions
   - `TriageWorker` → Classifies exceptions
   - `PolicyWorker` → Evaluates policies
   - `PlaybookWorker` → Matches playbooks
   - `ToolWorker` → Executes tools
   - `FeedbackWorker` → Captures feedback

**If workers are not running, exceptions will be ingested but NOT processed!**

## Quick Start

### 1. Start Kafka (if not already running)

The platform requires Kafka to be running. Check if Kafka is running:

```bash
# Check Kafka status (if using Docker)
docker ps | grep kafka
```

If Kafka is not running, start it:

```bash
# Using Docker Compose (if available)
docker-compose up -d kafka

# Or start Kafka manually
# See Kafka documentation for your setup
```

### 2. Start Workers

You need to start at least one worker of each type. Open separate terminal windows for each worker:

#### Terminal 1: Intake Worker
```bash
# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Start Intake Worker
WORKER_TYPE=intake CONCURRENCY=1 GROUP_ID=intake-workers python -m src.workers
```

#### Terminal 2: Triage Worker
```bash
source .venv/bin/activate
WORKER_TYPE=triage CONCURRENCY=1 GROUP_ID=triage-workers python -m src.workers
```

#### Terminal 3: Policy Worker
```bash
source .venv/bin/activate
WORKER_TYPE=policy CONCURRENCY=1 GROUP_ID=policy-workers python -m src.workers
```

#### Terminal 4: Playbook Worker
```bash
source .venv/bin/activate
WORKER_TYPE=playbook CONCURRENCY=1 GROUP_ID=playbook-workers python -m src.workers
```

#### Terminal 5: Tool Worker (optional, only if tools need to be executed)
```bash
source .venv/bin/activate
WORKER_TYPE=tool CONCURRENCY=1 GROUP_ID=tool-workers python -m src.workers
```

#### Terminal 6: Feedback Worker (optional)
```bash
source .venv/bin/activate
WORKER_TYPE=feedback CONCURRENCY=1 GROUP_ID=feedback-workers python -m src.workers
```

### 3. Verify Workers Are Running

Check worker logs to ensure they're processing events:

```
INFO: Initialized IntakeWorker: topics=['exceptions'], group_id=intake-workers
INFO: IntakeWorker processing ExceptionIngested: tenant_id=..., exception_id=...
```

### 4. Process Existing Exceptions

If you have existing exceptions that haven't been processed, you have two options:

#### Option A: Re-ingest Exceptions (Recommended)

Re-ingest the exceptions via the API. They will be processed by the running workers.

#### Option B: Manually Trigger Processing (Advanced)

You can manually trigger processing by publishing `ExceptionIngested` events for existing exceptions. This requires direct Kafka access.

## Environment Variables

Workers require these environment variables:

- `DATABASE_URL`: PostgreSQL connection string (required)
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka broker address (default: `localhost:9092`)
- `WORKER_TYPE`: Type of worker (required)
- `CONCURRENCY`: Number of parallel processors (default: 1)
- `GROUP_ID`: Consumer group ID (default: worker_type)

Example `.env` file:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/exceptions
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
WORKER_TYPE=intake
CONCURRENCY=1
GROUP_ID=intake-workers
```

## Troubleshooting

### Workers Not Processing Events

1. **Check Kafka is running**: `docker ps | grep kafka`
2. **Check worker logs**: Look for connection errors
3. **Verify environment variables**: Ensure `DATABASE_URL` and `KAFKA_BOOTSTRAP_SERVERS` are set
4. **Check database connectivity**: Workers need database access
5. **Verify topic exists**: Kafka topic `exceptions` should exist

### Exceptions Stuck in "OPEN" Status

- Workers are not running
- Kafka is not running
- Workers are not consuming from the correct topic
- Database connection issues

### Performance Issues

- Increase `CONCURRENCY` for I/O-bound workloads
- Add more worker instances for horizontal scaling
- See `docs/worker-scaling-guide.md` for detailed scaling strategies

## Production Deployment

For production, use:
- Docker Compose (see `docs/worker-scaling-guide.md`)
- Kubernetes (see `docs/worker-scaling-guide.md`)
- Process managers (systemd, supervisor, etc.)

## Additional Resources

- `docs/worker-scaling-guide.md` - Detailed scaling guide
- `docs/phase9-async-scale-mvp.md` - Phase 9 async scaling specification
- `src/workers/__main__.py` - Worker entry point code

