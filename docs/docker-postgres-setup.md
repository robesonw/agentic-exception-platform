# PostgreSQL Docker Setup

This guide explains how to run PostgreSQL locally using Docker for development.

## Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- Docker Compose (usually included with Docker Desktop)

## Quick Start

### 1. Start PostgreSQL

**Windows (PowerShell):**
```powershell
.\scripts\docker_db.ps1 start
```

**Linux/Mac (Bash):**
```bash
chmod +x scripts/docker_db.sh
./scripts/docker_db.sh start
```

**Or use Docker Compose directly:**
```bash
docker-compose up -d postgres
```

### 2. Set Environment Variables

**PowerShell:**
```powershell
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai"
```

**Bash:**
```bash
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai"
```

**Or create a `.env` file:**
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai
```

### 3. Verify Connection

```bash
python scripts/check_db_connection.py
```

### 4. Run Database Migrations

```bash
# Using Alembic
alembic upgrade head

# Or using helper script
.\scripts\migrate_db.bat upgrade
```

## Connection Details

When running via Docker, use these connection details:

- **Host**: `localhost`
- **Port**: `5432`
- **Database**: `sentinai`
- **Username**: `postgres`
- **Password**: `postgres`

**Full URL:**
```
postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai
```

## Managing the Container

### Check Status

**PowerShell:**
```powershell
.\scripts\docker_db.ps1 status
```

**Bash:**
```bash
./scripts/docker_db.sh status
```

### View Logs

**PowerShell:**
```powershell
.\scripts\docker_db.ps1 logs
```

**Bash:**
```bash
./scripts/docker_db.sh logs
```

### Stop Container

**PowerShell:**
```powershell
.\scripts\docker_db.ps1 stop
```

**Bash:**
```bash
./scripts/docker_db.sh stop
```

**Or:**
```bash
docker-compose stop postgres
```

### Restart Container

**PowerShell:**
```powershell
.\scripts\docker_db.ps1 restart
```

**Bash:**
```bash
./scripts/docker_db.sh restart
```

### Open psql Shell

**PowerShell:**
```powershell
.\scripts\docker_db.ps1 shell
```

**Bash:**
```bash
./scripts/docker_db.sh shell
```

**Or directly:**
```bash
docker exec -it sentinai-postgres psql -U postgres -d sentinai
```

### Remove Container and Data

⚠️ **WARNING**: This will delete all data!

**PowerShell:**
```powershell
.\scripts\docker_db.ps1 remove
```

**Bash:**
```bash
./scripts/docker_db.sh remove
```

**Or:**
```bash
docker-compose down -v
```

## Data Persistence

Data is stored in a Docker volume named `postgres_data`. This means:

- Data persists across container restarts
- Data is removed only when you explicitly remove the volume
- To reset the database, use `docker-compose down -v`

## Troubleshooting

### Container Won't Start

1. Check if port 5432 is already in use:
   ```bash
   # Windows
   netstat -ano | findstr :5432
   
   # Linux/Mac
   lsof -i :5432
   ```

2. Check Docker logs:
   ```bash
   docker-compose logs postgres
   ```

3. Verify Docker is running:
   ```bash
   docker ps
   ```

### Connection Refused

1. Ensure container is running:
   ```bash
   docker ps | grep sentinai-postgres
   ```

2. Check container health:
   ```bash
   docker inspect sentinai-postgres | grep -A 10 Health
   ```

3. Verify port mapping:
   ```bash
   docker port sentinai-postgres
   ```

### Reset Database

To completely reset the database:

```bash
# Stop and remove container and volumes
docker-compose down -v

# Start fresh
docker-compose up -d postgres

# Run migrations
alembic upgrade head
```

## Production Considerations

⚠️ **This Docker setup is for development only!**

For production:
- Use a managed PostgreSQL service (AWS RDS, Azure Database, Google Cloud SQL)
- Use strong passwords (change from default `postgres`)
- Configure proper security groups and network isolation
- Enable SSL/TLS connections
- Set up automated backups
- Use connection pooling (PgBouncer)

## Alternative: Using Docker Run

If you prefer `docker run` instead of `docker-compose`:

```bash
# Start PostgreSQL
docker run -d \
  --name sentinai-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=sentinai \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:16-alpine

# Stop
docker stop sentinai-postgres

# Remove
docker rm -v sentinai-postgres
```

