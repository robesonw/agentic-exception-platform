# Database Migrations Guide

This document explains how to manage database migrations for the SentinAI platform using Alembic.

## Overview

Phase 6 introduces PostgreSQL as the system of record. All database schema changes are managed through Alembic migrations, which provide version control and rollback capabilities.

## Prerequisites

1. **PostgreSQL Database**: Ensure PostgreSQL is installed and running
2. **Python Dependencies**: Install requirements including Alembic:
   ```bash
   pip install -r requirements.txt
   ```
3. **Database URL**: Set the `DATABASE_URL` environment variable (see Configuration below)

## Configuration

### Environment Variables

The migration system reads database connection information from environment variables.

**See [`docs/configuration.md`](configuration.md) for complete configuration reference.**

**Quick Setup:**

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env  # Linux/Mac
   copy .env.example .env  # Windows
   ```

2. Update `.env` with your database credentials

**Primary Method (Recommended):**
```bash
export DATABASE_URL=postgresql+asyncpg://user:password@host:port/database
```

**Alternative Method (Individual Components):**
```bash
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=sentinai
```

The `DATABASE_URL` takes precedence if both are set.

## Initial Setup

### 1. Create Database

First, create the PostgreSQL database:

```bash
# Using psql
psql -U postgres
CREATE DATABASE sentinai;
\q

# Or using createdb command
createdb -U postgres sentinai
```

### 2. Run Initial Migration

Run the initial migration to create all Phase 6 tables:

**Using helper script (recommended):**
```bash
# Linux/Mac
./scripts/migrate_db.sh upgrade

# Windows
scripts\migrate_db.bat upgrade
```

**Using Alembic directly:**
```bash
alembic upgrade head
```

This will create the following tables:
- `tenant`
- `domain_pack_version`
- `tenant_policy_pack_version`
- `exception`
- `exception_event`
- `playbook`
- `playbook_step`
- `tool_definition`

## Common Operations

### Check Current Migration Version

```bash
# Using helper script
./scripts/migrate_db.sh current

# Using Alembic directly
alembic current
```

### View Migration History

```bash
# Using helper script
./scripts/migrate_db.sh history

# Using Alembic directly
alembic history
```

### Upgrade to Latest Migration

```bash
# Using helper script
./scripts/migrate_db.sh upgrade

# Using Alembic directly
alembic upgrade head
```

### Rollback Migration

Rollback to previous migration:
```bash
# Using helper script
./scripts/migrate_db.sh downgrade

# Using Alembic directly
alembic downgrade -1
```

Rollback to specific revision:
```bash
# Using helper script
./scripts/migrate_db.sh downgrade <revision_id>

# Using Alembic directly
alembic downgrade <revision_id>
```

**Example:**
```bash
# Rollback to initial schema (before Phase 6)
alembic downgrade base
```

## Creating New Migrations

When you modify the SQLAlchemy models in `src/infrastructure/db/models.py`, create a new migration:

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Description of changes"

# Or create empty migration template
alembic revision -m "Description of changes"
```

**Important:** Always review auto-generated migrations before applying them. Alembic may not detect all changes correctly.

## Migration Files

Migrations are stored in `alembic/versions/` directory. Each migration file contains:

- `revision`: Unique identifier for this migration
- `down_revision`: Previous migration (forms a chain)
- `upgrade()`: Function that applies the migration
- `downgrade()`: Function that rolls back the migration

## Troubleshooting

### Migration Fails

If a migration fails:

1. **Check database connection:**
   ```bash
   echo $DATABASE_URL
   # Or on Windows: echo %DATABASE_URL%
   ```

2. **Check current migration state:**
   ```bash
   alembic current
   ```

3. **Review migration file** in `alembic/versions/` for errors

4. **Manual rollback** if needed:
   ```bash
   alembic downgrade -1
   ```

### Database Out of Sync

If the database schema doesn't match migrations:

1. **Check migration status:**
   ```bash
   alembic current
   alembic history
   ```

2. **Stamped migration** (if database was created manually):
   ```bash
   alembic stamp head
   ```

3. **Manual fix:** Edit the database or create a migration to align schema

### Connection Errors

- Verify PostgreSQL is running: `pg_isready` or `psql -U postgres -c "SELECT 1"`
- Check connection string format: `postgresql+asyncpg://user:password@host:port/dbname`
- Verify credentials and database exists
- Check firewall/network settings

## Best Practices

1. **Always test migrations** in a development environment first
2. **Backup database** before running migrations in production
3. **Review auto-generated migrations** before committing
4. **Use descriptive migration messages**: `alembic revision -m "Add user_email_index"`
5. **Keep migrations small and focused** - one logical change per migration
6. **Never edit existing migrations** that have been applied to production
7. **Test rollback** procedures regularly

## Phase 6 Schema

The initial migration creates the following schema structure:

```
tenant (tenant_id PK)
├── domain_pack_version (id PK)
├── tenant_policy_pack_version (id PK, tenant_id FK)
├── exception (exception_id PK, tenant_id FK)
│   └── exception_event (event_id PK, exception_id FK, tenant_id FK)
├── playbook (playbook_id PK, tenant_id FK)
│   └── playbook_step (step_id PK, playbook_id FK)
└── tool_definition (tool_id PK, tenant_id FK nullable)
```

All tables include proper indexes, foreign keys with CASCADE/SET NULL, and enum types as specified in `docs/phase6-persistence-mvp.md`.

## References

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- Phase 6 Specification: `docs/phase6-persistence-mvp.md`
- Database Models: `src/infrastructure/db/models.py`

