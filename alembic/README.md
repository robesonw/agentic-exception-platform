# Alembic Migrations

This directory contains Alembic database migration scripts for the SentinAI platform.

## Quick Start

1. **Set database URL:**
   ```bash
   export DATABASE_URL=postgresql+asyncpg://user:password@host:port/database
   ```

2. **Run migrations:**
   ```bash
   alembic upgrade head
   ```

3. **Check current version:**
   ```bash
   alembic current
   ```

4. **Rollback:**
   ```bash
   alembic downgrade -1
   ```

## Files

- `env.py` - Alembic environment configuration (async SQLAlchemy support)
- `script.py.mako` - Migration file template
- `versions/` - Migration version files

## Helper Scripts

Use the helper scripts in `scripts/` directory:
- `migrate_db.sh` (Linux/Mac)
- `migrate_db.bat` (Windows)

## Documentation

See `docs/database-migrations.md` for complete migration guide.

