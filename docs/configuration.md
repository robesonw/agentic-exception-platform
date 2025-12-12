# Configuration Guide

This document describes all environment variables and configuration options for the Agentic Exception Processing Platform.

## Quick Start

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Update `.env` with your actual values (especially database credentials)

3. Load environment variables:
   ```bash
   # Linux/Mac
   export $(cat .env | xargs)
   
   # Windows (PowerShell)
   Get-Content .env | ForEach-Object { if ($_ -match '^([^#][^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') } }
   ```

## Phase 6: Database Configuration

### Required Variables

#### `DATABASE_URL`

**Description**: Complete PostgreSQL connection URL.

**Format**: `postgresql+asyncpg://user:password@host:port/database`

**Examples**:
```bash
# Local development
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai

# Production (example)
DATABASE_URL=postgresql+asyncpg://app_user:secure_password@db.example.com:5432/sentinai_prod

# With SSL
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/db?ssl=require
```

**Notes**:
- If `DATABASE_URL` is set, it takes precedence over individual `DB_*` variables
- The driver (`+asyncpg`) is automatically added if missing
- **Never commit real credentials to version control**

#### Alternative: Individual Components

If `DATABASE_URL` is not set, the system constructs the URL from these variables:

- **`DB_USER`** (default: `postgres`): Database username
- **`DB_PASSWORD`** (default: empty): Database password
- **`DB_HOST`** (default: `localhost`): Database hostname
- **`DB_PORT`** (default: `5432`): Database port
- **`DB_NAME`** (default: `sentinai`): Database name

**Example**:
```bash
DB_USER=app_user
DB_PASSWORD=secure_password
DB_HOST=db.example.com
DB_PORT=5432
DB_NAME=sentinai
```

### Connection Pool Settings

#### `DB_POOL_SIZE`

**Description**: Number of connections to maintain in the connection pool.

**Default**: `5`

**Recommended Values**:
- **Local Development**: `5` (sufficient for single developer)
- **CI/CD**: `2-3` (minimal for test runs)
- **Production**: `10-20` (depends on expected load)

**Example**:
```bash
DB_POOL_SIZE=10
```

#### `DB_MAX_OVERFLOW`

**Description**: Maximum number of connections to create beyond `DB_POOL_SIZE` when pool is exhausted.

**Default**: `5`

**Recommended Values**:
- **Local Development**: `5`
- **CI/CD**: `2-3`
- **Production**: `10-20` (should match or exceed `DB_POOL_SIZE`)

**Example**:
```bash
DB_MAX_OVERFLOW=10
```

**Note**: Total maximum connections = `DB_POOL_SIZE + DB_MAX_OVERFLOW`

#### `DB_POOL_TIMEOUT`

**Description**: Seconds to wait before giving up on getting a connection from the pool.

**Default**: `30`

**Recommended Values**:
- **Local Development**: `30` (generous timeout for debugging)
- **CI/CD**: `10` (fail fast in tests)
- **Production**: `30-60` (depends on expected load spikes)

**Example**:
```bash
DB_POOL_TIMEOUT=30
```

#### `DB_ECHO`

**Description**: Enable SQL query logging to console (useful for debugging).

**Default**: `false`

**Values**: `true`, `1`, `yes` (case-insensitive) to enable; anything else to disable

**Recommended Values**:
- **Local Development**: `true` (helpful for debugging)
- **CI/CD**: `false` (reduces log noise)
- **Production**: `false` (never enable in production - security and performance)

**Example**:
```bash
DB_ECHO=true  # Enable SQL logging
```

**Warning**: Enabling `DB_ECHO` in production can:
- Expose sensitive data in logs
- Impact performance
- Generate excessive log volume

## Environment-Specific Recommendations

### Local Development

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=5
DB_POOL_TIMEOUT=30
DB_ECHO=true  # Enable for debugging
```

### CI/CD (GitHub Actions, GitLab CI, etc.)

```bash
# Use test database (in-memory SQLite or dedicated test instance)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai_test
DB_POOL_SIZE=2
DB_MAX_OVERFLOW=2
DB_POOL_TIMEOUT=10
DB_ECHO=false
```

**CI Test Database Options**:

1. **In-Memory SQLite** (fastest, no setup):
   ```bash
   # Tests use sqlite+aiosqlite:///:memory: automatically
   # No DATABASE_URL needed for tests
   ```

2. **Docker PostgreSQL Container** (recommended for integration tests):
   ```yaml
   # .github/workflows/test.yml example
   services:
     postgres:
       image: postgres:15
       env:
         POSTGRES_PASSWORD: postgres
         POSTGRES_DB: sentinai_test
       options: >-
         --health-cmd pg_isready
         --health-interval 10s
         --health-timeout 5s
         --health-retries 5
   ```

3. **Dedicated Test Database Instance**:
   ```bash
   DATABASE_URL=postgresql+asyncpg://test_user:test_pass@test-db.example.com:5432/sentinai_test
   ```

### Production

```bash
# Use secure credentials from secrets management
DATABASE_URL=postgresql+asyncpg://app_user:${DB_PASSWORD}@prod-db.example.com:5432/sentinai_prod
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_ECHO=false  # Never enable in production
```

**Production Best Practices**:
- Use secrets management (AWS Secrets Manager, HashiCorp Vault, Kubernetes Secrets)
- Enable SSL/TLS connections
- Use connection pooling appropriate for your load
- Monitor connection pool metrics
- Set up database connection retry logic (handled automatically)

## Docker Configuration

### docker-compose.yml

```yaml
services:
  api:
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/sentinai
      - DB_POOL_SIZE=10
      - DB_MAX_OVERFLOW=10
      - DB_POOL_TIMEOUT=30
      - DB_ECHO=false
    depends_on:
      - postgres
  
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=sentinai
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Docker Run

```bash
docker run -d \
  -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@host.docker.internal:5432/sentinai \
  -e DB_POOL_SIZE=10 \
  -e DB_MAX_OVERFLOW=10 \
  agentic-exception-platform
```

### Using .env File with Docker

```bash
# Docker Compose automatically loads .env file
docker-compose up

# Docker run with env file
docker run --env-file .env agentic-exception-platform
```

## Kubernetes Configuration

### ConfigMap Example

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  DB_POOL_SIZE: "20"
  DB_MAX_OVERFLOW: "20"
  DB_POOL_TIMEOUT: "30"
  DB_ECHO: "false"
```

### Secret Example

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
type: Opaque
stringData:
  DATABASE_URL: "postgresql+asyncpg://user:password@db.example.com:5432/sentinai"
```

### Deployment Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agentic-exception-platform
spec:
  template:
    spec:
      containers:
      - name: api
        envFrom:
        - configMapRef:
            name: app-config
        - secretRef:
            name: app-secrets
```

## Testing Configuration

### Running Tests

Tests use in-memory SQLite by default (no configuration needed):

```bash
# Tests automatically use sqlite+aiosqlite:///:memory:
pytest tests/repository -v
```

### Integration Tests with PostgreSQL

For integration tests that require real PostgreSQL:

```bash
# Set test database URL
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai_test

# Run integration tests
pytest tests/api -v -m integration
```

### CI/CD Test Database Setup

**GitHub Actions Example**:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: sentinai_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -e ".[dev]"
      
      - name: Run migrations
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai_test
        run: |
          alembic upgrade head
      
      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai_test
          DB_POOL_SIZE: 2
          DB_MAX_OVERFLOW: 2
          DB_POOL_TIMEOUT: 10
          DB_ECHO: false
        run: |
          pytest tests -v --cov=src --cov-report=term-missing
```

## Security Best Practices

1. **Never commit secrets**:
   - Add `.env` to `.gitignore`
   - Use `.env.example` as a template
   - Use secrets management in production

2. **Use strong passwords**:
   - Generate random passwords for production
   - Rotate passwords regularly

3. **Enable SSL/TLS**:
   ```bash
   DATABASE_URL=postgresql+asyncpg://user:password@host:5432/db?ssl=require
   ```

4. **Limit connection pool size**:
   - Don't set pool size too high (can exhaust database connections)
   - Monitor connection usage

5. **Disable SQL logging in production**:
   - Always set `DB_ECHO=false` in production
   - SQL logs may contain sensitive data

## Troubleshooting

### Connection Issues

1. **Check DATABASE_URL format**:
   ```bash
   echo $DATABASE_URL
   # Should be: postgresql+asyncpg://user:password@host:port/database
   ```

2. **Test connection**:
   ```bash
   python scripts/check_db_connection.py
   ```

3. **Check database is running**:
   ```bash
   # Docker
   docker ps | grep postgres
   
   # Local
   pg_isready -h localhost -p 5432
   ```

### Pool Exhaustion

If you see "pool exhausted" errors:

1. Increase `DB_POOL_SIZE` and `DB_MAX_OVERFLOW`
2. Check for connection leaks (connections not being closed)
3. Monitor database connection count

### Migration Issues

See [`docs/database-migrations.md`](database-migrations.md) for migration troubleshooting.

## Related Documentation

- **Database Setup**: [`docs/docker-postgres-setup.md`](docker-postgres-setup.md)
- **Migrations**: [`docs/database-migrations.md`](database-migrations.md)
- **Phase 6 Details**: [`docs/phase6-persistence-mvp.md`](phase6-persistence-mvp.md)
- **Architecture**: [`docs/01-architecture.md`](01-architecture.md)

