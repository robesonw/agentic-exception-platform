# Running SentinAI Locally

This guide covers how to run the SentinAI platform locally using Docker Compose, including all required services.

## Prerequisites

- Docker and Docker Compose installed
- At least 4GB of available RAM (Kafka requires memory)
- Ports available:
  - **Docker services:** 3000 (UI), 8000 (Backend API), 5432 (PostgreSQL), 8080 (Kafka UI), 9092 (Kafka)
  - **Worker health checks:** 9001-9007 (intake, triage, policy, playbook, tool, feedback, sla_monitor)

## Services Overview

The local development environment includes:

- **PostgreSQL** (port 5432): Main database
- **Kafka** (port 9092): Message broker for event-driven architecture (Phase 9)
- **Kafka UI** (port 8080): Web interface for inspecting Kafka topics and messages
- **Backend API** (port 8000): FastAPI application
- **UI** (port 3000): React frontend application
- **Workers** (background processes): Agent workers for event processing
  - IntakeWorker (2 instances)
  - TriageWorker (4 instances)
  - PolicyWorker (2 instances)
  - PlaybookWorker (2 instances)
  - ToolWorker (4 instances)
  - FeedbackWorker (2 instances)
  - SLAMonitorWorker (1 instance)

## Quick Start (Recommended)

### Single Command Startup

The easiest way to start everything is using the provided startup scripts:

**Linux/Mac:**
```bash
./scripts/start-local.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\start-local.ps1
```

This single command will:
1. Start all Docker Compose services (postgres + kafka + kafka-ui + api + ui)
2. Wait for services to be healthy
3. Start all worker processes

### Using Makefile

If you have `make` installed, you can use these convenient targets:

**Start all services:**
```bash
make up
```

**Stop all services:**
```bash
make down
```

**View worker logs:**
```bash
make logs
```

**Check service status:**
```bash
make status
```

**Clean up everything (including data volumes):**
```bash
make clean
```

## Starting Services (Manual)

### Start All Services with Docker Compose Only

```bash
docker-compose up -d
```

This will start all Docker services in detached mode. The services will start in the correct order based on dependencies.

**Note:** This does NOT start the worker processes. You need to start workers separately (see below) or use the `start-local.sh` script.

### Start Specific Services

You can start individual services:

```bash
# Start only database and Kafka
docker-compose up -d postgres kafka kafka-ui

# Start backend after dependencies are ready
docker-compose up -d backend

# Start UI
docker-compose up -d ui
```

## Kafka Topic Initialization

When you first start Kafka, the `kafka-init` service will automatically create all required topics for Phase 9:

- **Inbound Events:**
  - `exceptions.ingested`
  - `exceptions.normalized`

- **Agent Events:**
  - `triage.requested`
  - `triage.completed`
  - `policy.requested`
  - `policy.completed`
  - `playbook.matched`
  - `step.requested`
  - `tool.requested`
  - `tool.completed`
  - `feedback.captured`

- **Control & Ops Events:**
  - `control.retry`
  - `control.dlq`
  - `sla.imminent`
  - `sla.expired`

The initialization script (`scripts/kafka-init-topics.sh`) runs automatically when Kafka becomes healthy. If you need to manually recreate topics, you can run:

```bash
docker-compose run --rm kafka-init
```

## Viewing Kafka Topics

### Using Kafka UI

1. Open your browser and navigate to: http://localhost:8080
2. You should see the "local" Kafka cluster
3. Click on "Topics" in the left sidebar to view all topics
4. Click on any topic to:
   - View topic configuration
   - Browse messages
   - View consumer groups
   - Monitor topic metrics

### Using Kafka CLI

You can also use Kafka command-line tools from within the Kafka container:

```bash
# List all topics
docker-compose exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list

# Describe a specific topic
docker-compose exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic exceptions.ingested

# Consume messages from a topic
docker-compose exec kafka kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic exceptions.ingested --from-beginning
```

## Environment Variables

### Kafka Configuration

The following environment variables are set for Kafka connectivity:

- **Inside Docker containers:** `KAFKA_BOOTSTRAP_SERVERS=kafka:9092`
- **From host machine:** `KAFKA_BOOTSTRAP_SERVERS=localhost:9092`

The backend service automatically uses `kafka:9092` when running in Docker. If you're running the backend locally (outside Docker), set:

```bash
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```

## Starting Workers

Workers are Python processes that consume events from Kafka and process exceptions asynchronously. They must be started separately from Docker Compose services.

### Start All Workers

**Linux/Mac:**
```bash
./scripts/start-workers.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\start-workers.ps1
```

This will start all worker types with their configured concurrency levels. Worker logs are saved to `logs/worker-*.log` and PIDs are saved to `logs/worker-*.pid`.

### Stop All Workers

**Linux/Mac:**
```bash
./scripts/stop-workers.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\stop-workers.ps1
```

## Stopping Services

### Stop All Services (Recommended)

Use the provided stop scripts to stop both workers and Docker services:

**Linux/Mac:**
```bash
./scripts/stop-local.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\stop-local.ps1
```

**Or using Makefile:**
```bash
make down
```

### Stop Docker Compose Only

```bash
docker-compose down
```

This stops all Docker services but preserves data volumes. **Note:** This does NOT stop worker processes.

### Stop and Remove Volumes

To completely clean up (removes all data):

```bash
docker-compose down -v
```

**Warning:** This will delete all database data and Kafka topics. Use with caution.

## Viewing Logs

### View Worker Logs

**Using Makefile (recommended):**
```bash
make logs
```

**Linux/Mac:**
```bash
tail -f logs/worker-*.log
```

**Windows (PowerShell):**
```powershell
Get-Content logs\worker-*.log -Wait
```

**View specific worker logs:**
```bash
# Linux/Mac
tail -f logs/worker-intake.log
tail -f logs/worker-triage.log

# Windows (PowerShell)
Get-Content logs\worker-intake.log -Wait
Get-Content logs\worker-triage.log -Wait
```

### View Docker Compose Logs

**View all Docker service logs:**
```bash
docker-compose logs -f
```

**View specific service logs:**
```bash
# Kafka logs
docker-compose logs -f kafka

# Backend logs
docker-compose logs -f backend

# Kafka UI logs
docker-compose logs -f kafka-ui

# PostgreSQL logs
docker-compose logs -f postgres
```

## Health Checks

### Worker Health Endpoints

Each worker exposes health check endpoints on dedicated ports:

| Worker Type | Port | Health Endpoint | Ready Endpoint |
|------------|------|----------------|----------------|
| intake | 9001 | http://localhost:9001/healthz | http://localhost:9001/readyz |
| triage | 9002 | http://localhost:9002/healthz | http://localhost:9002/readyz |
| policy | 9003 | http://localhost:9003/healthz | http://localhost:9003/readyz |
| playbook | 9004 | http://localhost:9004/healthz | http://localhost:9004/readyz |
| tool | 9005 | http://localhost:9005/healthz | http://localhost:9005/readyz |
| feedback | 9006 | http://localhost:9006/healthz | http://localhost:9006/readyz |
| sla_monitor | 9007 | http://localhost:9007/healthz | http://localhost:9007/readyz |

**Healthz Endpoint (`/healthz`):**
- Returns `200 OK` if: process is alive + broker is reachable
- Returns `503 Service Unavailable` if unhealthy

**Readyz Endpoint (`/readyz`):**
- Returns `200 OK` if: database is reachable + worker is subscribed to topics
- Returns `503 Service Unavailable` if not ready

### Quick Health Check Script

**Linux/Mac:**
```bash
./scripts/health_check.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\health_check.ps1
```

This script checks all worker health and readiness endpoints and provides a summary.

### Manual Health Checks

**Check a specific worker:**
```bash
# Health check
curl http://localhost:9001/healthz

# Readiness check
curl http://localhost:9001/readyz
```

**Check all workers (Linux/Mac):**
```bash
for port in 9001 9002 9003 9004 9005 9006 9007; do
  echo "Checking port $port..."
  curl -s http://localhost:$port/healthz && echo " - OK" || echo " - FAILED"
done
```

### Check Service Status

**Using Makefile (shows both Docker and worker status):**
```bash
make status
```

**Check Docker services only:**
```bash
docker-compose ps
```

All Docker services should show as "Up" and healthy.

**Check worker processes (Linux/Mac):**
```bash
# Check if worker processes are running
ps aux | grep "src.workers"

# Or check PID files
ls -la logs/worker-*.pid
```

**Check worker processes (Windows PowerShell):**
```powershell
# Check PowerShell background jobs
Get-Job

# View worker job output
Receive-Job -Id <JobId>
```

### Verify Kafka is Ready

```bash
docker-compose exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092
```

If Kafka is ready, this command will return broker API version information.

### Verify Database Connection

```bash
docker-compose exec postgres psql -U sentinai -d sentinai -c "SELECT version();"
```

## Troubleshooting

### Kafka Not Starting

If Kafka fails to start:

1. Check Kafka logs: `docker-compose logs kafka`
2. Ensure port 9092 is not in use: `netstat -an | grep 9092` (Linux/Mac) or `netstat -an | findstr 9092` (Windows)
3. Try removing Kafka volume and restarting: `docker-compose down -v` then `docker-compose up -d`

### Topics Not Created

If topics are not automatically created:

1. Check kafka-init logs: `docker-compose logs kafka-init`
2. Manually run initialization: `docker-compose run --rm kafka-init`
3. Verify Kafka is healthy before running init: `docker-compose ps kafka`

### Connection Issues

If the backend cannot connect to Kafka:

1. Verify Kafka is running: `docker-compose ps kafka`
2. Check backend logs: `docker-compose logs backend`
3. Ensure `KAFKA_BOOTSTRAP_SERVERS` environment variable is set correctly
4. Test connectivity from backend container: `docker-compose exec backend ping kafka`

### Port Conflicts

If you get port binding errors:

1. Check which process is using the port
2. Stop conflicting services
3. Or modify port mappings in `docker-compose.yml`

## Development Workflow

### Hot Reload

The backend and UI services are configured with volume mounts for hot reload during development:

- Backend: `./src` is mounted to `/app/src`
- UI: `./ui/src` is mounted to `/app/src`

Changes to source files will automatically trigger reloads (if your development server supports it).

### Running Tests

Tests should be run outside Docker to avoid conflicts:

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# Run tests
pytest
```

### Database Migrations

Run migrations using Alembic:

```bash
# Inside Docker
docker-compose exec backend alembic upgrade head

# Or locally (with DATABASE_URL set)
alembic upgrade head
```

## Next Steps

Once all services are running:

1. Access the UI at: http://localhost:3000
2. Access the API docs at: http://localhost:8000/docs
3. Access Kafka UI at: http://localhost:8080
4. Start developing Phase 9 async features using the Kafka topics

## Phase 9 Integration

For Phase 9 development, the Kafka infrastructure is ready:

- All required topics are created automatically
- Kafka UI is available for inspecting events
- Backend is configured to connect to Kafka
- Environment variables are set for both Docker and local development

When implementing Phase 9 features:

1. Use `KAFKA_BOOTSTRAP_SERVERS` environment variable for broker connection
2. Publish events to the appropriate topics (see topic list above)
3. Monitor events in Kafka UI at http://localhost:8080
4. Use the event schemas defined in Phase 9 documentation



