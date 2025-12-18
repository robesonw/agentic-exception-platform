# Startup Scripts

This directory contains scripts to start, stop, restart, and check the status of all platform services.

## Quick Start

### Start All Services (Infrastructure + Backend + UI)

**Linux/Mac:**
```bash
./scripts/start-all.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\start-all.ps1
```

### Start Workers

**Linux/Mac:**
```bash
./scripts/start-workers.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\start-workers.ps1
```

### Stop All Services

**Linux/Mac:**
```bash
./scripts/stop-all.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\stop-all.ps1
```

### Stop Workers

**Linux/Mac:**
```bash
./scripts/stop-workers.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\stop-workers.ps1
```

### Restart All Services

**Linux/Mac:**
```bash
./scripts/restart-all.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\restart-all.ps1
```

### Check Status

**Linux/Mac:**
```bash
./scripts/status.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\status.ps1
```

## Scripts Overview

### Infrastructure Scripts

- **start-all.sh / start-all.ps1**: Starts all infrastructure (PostgreSQL, Kafka), backend API, and UI
- **stop-all.sh / stop-all.ps1**: Stops all Docker Compose services
- **restart-all.sh / restart-all.ps1**: Restarts all Docker Compose services
- **status.sh / status.ps1**: Checks status of all services

### Worker Scripts

- **start-workers.sh / start-workers.ps1**: Starts all worker types (intake, triage, policy, playbook, tool, feedback, sla_monitor)
- **stop-workers.sh / stop-workers.ps1**: Stops all running workers

### Database Scripts

- **docker_db.sh / docker_db.ps1**: Manage PostgreSQL Docker container
- **migrate_db.sh / migrate_db.bat**: Run database migrations

## Service Ports

| Service | Port | URL |
|---------|------|-----|
| PostgreSQL | 5432 | localhost:5432 |
| Kafka | 9092 | localhost:9092 |
| Kafka UI | 8080 | http://localhost:8080 |
| Backend API | 8000 | http://localhost:8000 |
| API Docs | 8000 | http://localhost:8000/docs |
| Metrics | 8000 | http://localhost:8000/metrics |
| UI | 3000 | http://localhost:3000 |

## Worker Configuration

Workers are configured via environment variables:

- **WORKER_TYPE**: Type of worker (intake, triage, policy, playbook, tool, feedback, sla_monitor)
- **CONCURRENCY**: Number of parallel event processors (default: 1)
- **GROUP_ID**: Consumer group ID for load balancing (default: worker_type)
- **DATABASE_URL**: PostgreSQL connection string
- **KAFKA_BOOTSTRAP_SERVERS**: Kafka broker address

Default worker configurations:
- **intake**: concurrency=2, group_id=intake-workers
- **triage**: concurrency=4, group_id=triage-workers
- **policy**: concurrency=2, group_id=policy-workers
- **playbook**: concurrency=2, group_id=playbook-workers
- **tool**: concurrency=4, group_id=tool-workers
- **feedback**: concurrency=2, group_id=feedback-workers
- **sla_monitor**: concurrency=1, group_id=sla-monitors

## Environment Variables

Create a `.env` file in the project root with:

```bash
# Database Configuration
DATABASE_URL=postgresql+asyncpg://sentinai:sentinai@localhost:5432/sentinai

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Worker Configuration (optional)
WORKER_TYPE=intake
CONCURRENCY=2
GROUP_ID=intake-workers
```

## Troubleshooting

### Services Not Starting

1. Check Docker is running: `docker ps`
2. Check ports are available: `netstat -an | grep -E '5432|9092|8000|3000'`
3. Check logs: `docker-compose logs -f [service_name]`

### Workers Not Processing Events

1. Check workers are running: `./scripts/status.sh`
2. Check Kafka connectivity: `docker exec sentinai-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092`
3. Check worker logs: `tail -f logs/worker-*.log`

### Database Connection Issues

1. Check PostgreSQL is running: `docker ps | grep postgres`
2. Verify connection string: `echo $DATABASE_URL`
3. Test connection: `docker exec sentinai-postgres psql -U sentinai -d sentinai -c "SELECT 1;"`

## Manual Service Management

### Start Individual Services

```bash
# Start only infrastructure
docker-compose up -d postgres kafka kafka-ui

# Start only backend
docker-compose up -d backend

# Start only UI
docker-compose up -d ui
```

### Start Individual Workers

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate  # Windows

# Start specific worker
WORKER_TYPE=intake CONCURRENCY=2 GROUP_ID=intake-workers python -m src.workers
```

### View Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f kafka

# View worker logs
tail -f logs/worker-*.log
```

## References

- `docs/ops-runbook.md` - Complete operations runbook
- `docs/worker-scaling-guide.md` - Worker scaling guide
- `docker-compose.yml` - Docker Compose configuration


