# End-to-End Async Flow Testing Guide

## Overview

This guide explains how to run end-to-end integration tests for the async event-driven flow in Phase 9.

**Phase 9 P9-28: End-to-End Async Flow Tests**  
Reference: `docs/phase9-async-scale-mvp.md` Section 13

## Prerequisites

1. **Docker and Docker Compose** - Required for running Kafka and PostgreSQL
2. **Python 3.11+** - Required for running tests
3. **Test dependencies** - Install with `pip install -r requirements.txt`

## Quick Start

### 1. Start Test Infrastructure (Docker Compose)

Start Kafka and PostgreSQL for integration tests:

```bash
# Start test infrastructure
docker-compose -f docker-compose.test.yml up -d

# Verify services are running
docker-compose -f docker-compose.test.yml ps

# Check logs
docker-compose -f docker-compose.test.yml logs -f
```

### 2. Set Environment Variables

```bash
# Windows (PowerShell)
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/sentinai_test"
$env:KAFKA_BOOTSTRAP_SERVERS = "localhost:9093"
$env:SKIP_KAFKA_INTEGRATION_TESTS = "false"

# Linux/Mac
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/sentinai_test
export KAFKA_BOOTSTRAP_SERVERS=localhost:9093
export SKIP_KAFKA_INTEGRATION_TESTS=false
```

### 3. Run Database Migrations

```bash
# Set database URL for migrations
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/sentinai_test

# Run migrations
alembic upgrade head
```

### 4. Run E2E Tests

```bash
# Run all E2E async flow tests
pytest tests/integration/test_e2e_async_flow.py -v

# Run specific test
pytest tests/integration/test_e2e_async_flow.py::TestE2EAsyncFlow::test_post_exception_worker_chain_playbook_tool_exec -v

# Run with coverage
pytest tests/integration/test_e2e_async_flow.py --cov=src --cov-report=html
```

## Test Structure

### Test File: `tests/integration/test_e2e_async_flow.py`

The E2E test suite includes:

1. **`test_post_exception_worker_chain_playbook_tool_exec`**
   - Tests complete flow: POST exception -> worker chain -> playbook -> tool exec
   - Verifies 202 Accepted response
   - Verifies events flow through workers

2. **`test_ordering_per_exception`**
   - Verifies events for the same exception are processed in order
   - Tests event ordering across worker chain

3. **`test_idempotency_duplicate_events`**
   - Verifies duplicate events are handled correctly
   - Tests idempotency checks

4. **`test_retry_dlq_path`**
   - Verifies retry mechanism for failed events
   - Tests DLQ (Dead Letter Queue) path

5. **`test_tenant_isolation`**
   - Verifies tenant isolation
   - Tests that one tenant's events don't affect others

## Test Infrastructure

### Docker Compose Configuration

The test infrastructure is defined in `docker-compose.test.yml`:

- **PostgreSQL** (port 5433) - Test database
- **Zookeeper** (port 2182) - Kafka coordination
- **Kafka** (port 9093) - Message broker for tests

### Port Configuration

Test services use different ports to avoid conflicts with main services:

| Service | Main Port | Test Port |
|---------|-----------|-----------|
| PostgreSQL | 5432 | 5433 |
| Zookeeper | 2181 | 2182 |
| Kafka | 9092 | 9093 |

## Running Tests Locally

### Option 1: Full E2E Test (Recommended)

```bash
# 1. Start infrastructure
docker-compose -f docker-compose.test.yml up -d

# 2. Set environment variables
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/sentinai_test
export KAFKA_BOOTSTRAP_SERVERS=localhost:9093

# 3. Run migrations
alembic upgrade head

# 4. Run tests
pytest tests/integration/test_e2e_async_flow.py -v
```

### Option 2: Skip Kafka Tests

If Kafka is not available, skip Kafka-dependent tests:

```bash
export SKIP_KAFKA_INTEGRATION_TESTS=true
pytest tests/integration/test_e2e_async_flow.py -v
```

### Option 3: Use Existing Kafka

If you have Kafka running locally:

```bash
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
pytest tests/integration/test_e2e_async_flow.py -v
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Async Flow Tests

on:
  pull_request:
    paths:
      - 'src/**'
      - 'tests/integration/test_e2e_async_flow.py'
  push:
    branches: [main]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: sentinai_test
        ports:
          - 5433:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      zookeeper:
        image: confluentinc/cp-zookeeper:7.5.0
        env:
          ZOOKEEPER_CLIENT_PORT: 2181
        ports:
          - 2182:2181
      
      kafka:
        image: confluentinc/cp-kafka:7.5.0
        depends-on: zookeeper
        env:
          KAFKA_BROKER_ID: 1
          KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
          KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9093
          KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
        ports:
          - 9093:9093
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov
      
      - name: Run database migrations
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5433/sentinai_test
        run: alembic upgrade head
      
      - name: Run E2E tests
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5433/sentinai_test
          KAFKA_BOOTSTRAP_SERVERS: localhost:9093
          SKIP_KAFKA_INTEGRATION_TESTS: false
        run: |
          pytest tests/integration/test_e2e_async_flow.py -v --cov=src --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

## Troubleshooting

### Kafka Connection Issues

If tests fail with Kafka connection errors:

1. **Check Kafka is running:**
   ```bash
   docker-compose -f docker-compose.test.yml ps
   ```

2. **Check Kafka logs:**
   ```bash
   docker-compose -f docker-compose.test.yml logs kafka-test
   ```

3. **Verify Kafka is accessible:**
   ```bash
   # Test Kafka connection
   docker exec -it exception-platform-kafka-test kafka-broker-api-versions --bootstrap-server localhost:9093
   ```

### Database Connection Issues

If tests fail with database connection errors:

1. **Check PostgreSQL is running:**
   ```bash
   docker-compose -f docker-compose.test.yml ps
   ```

2. **Verify database exists:**
   ```bash
   docker exec -it exception-platform-postgres-test psql -U postgres -l
   ```

3. **Check migrations:**
   ```bash
   alembic current
   alembic upgrade head
   ```

### Test Timeouts

If tests timeout:

1. **Increase wait times** in test code
2. **Check worker processing** - ensure workers are processing events
3. **Check Kafka consumer lag** - verify events are being consumed

## Test Coverage

The E2E tests verify:

- ✅ Exception ingestion (POST /exceptions returns 202)
- ✅ Event publishing to Kafka
- ✅ Worker chain processing (Intake -> Triage -> Policy -> Playbook -> Tool)
- ✅ Event ordering per exception
- ✅ Idempotency (duplicate event handling)
- ✅ Retry mechanism
- ✅ DLQ (Dead Letter Queue) path
- ✅ Tenant isolation

## Next Steps

1. **Add more test scenarios:**
   - Multiple exceptions in parallel
   - High-volume load testing
   - Worker scaling scenarios

2. **Add performance benchmarks:**
   - Measure event processing latency
   - Track throughput (events/second)
   - Monitor resource usage

3. **Add monitoring:**
   - Prometheus metrics collection
   - Distributed tracing
   - Error rate monitoring

## References

- `docs/phase9-async-scale-mvp.md` - Phase 9 async scaling MVP specification
- `tests/integration/test_e2e_async_flow.py` - E2E test implementation
- `docker-compose.test.yml` - Test infrastructure configuration


