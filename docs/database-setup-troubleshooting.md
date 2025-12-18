# Database Setup Troubleshooting

## Issue: Password Authentication Failed

If you're seeing the error:
```
password authentication failed for user "postgres"
```

This means the application cannot connect to PostgreSQL with the configured credentials.

## Quick Fix Options

### Option 1: Use Default PostgreSQL User (Quickest)

If you have PostgreSQL installed with the default `postgres` user, update your `.env` file:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/sentinai
```

Replace `YOUR_POSTGRES_PASSWORD` with your actual PostgreSQL password.

### Option 2: Create the `sentinai` User and Database

If you want to use the `sentinai` user as configured in `.env`, you need to create it:

1. **Connect to PostgreSQL as superuser:**
   ```bash
   psql -U postgres
   ```

2. **Create the user and database:**
   ```sql
   CREATE USER sentinai WITH PASSWORD 'sentinai';
   CREATE DATABASE sentinai OWNER sentinai;
   GRANT ALL PRIVILEGES ON DATABASE sentinai TO sentinai;
   \q
   ```

3. **Verify the connection:**
   ```bash
   psql -U sentinai -d sentinai -h localhost
   ```

### Option 3: Check PostgreSQL is Running

**Windows:**
```powershell
# Check if PostgreSQL service is running
Get-Service -Name postgresql*

# Start PostgreSQL if not running
Start-Service -Name postgresql-x64-XX  # Replace XX with your version
```

**Linux/Mac:**
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Start PostgreSQL if not running
sudo systemctl start postgresql
```

## Verify Your Setup

1. **Test the connection:**
   ```bash
   python scripts/test_db_connection.py
   ```

2. **Check your `.env` file:**
   ```bash
   # Windows PowerShell
   Get-Content .env | Select-String DATABASE_URL
   
   # Linux/Mac
   grep DATABASE_URL .env
   ```

3. **Set environment variable manually (for testing):**
   ```powershell
   # Windows PowerShell
   $env:DATABASE_URL = "postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/sentinai"
   
   # Linux/Mac
   export DATABASE_URL="postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/sentinai"
   ```

## Common Connection String Formats

```bash
# With password
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname

# Without password (trust authentication)
DATABASE_URL=postgresql+asyncpg://user@localhost:5432/dbname

# With SSL
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname?ssl=require
```

## After Fixing

1. **Restart your API server** to pick up the new environment variable
2. **Run database migrations** if needed:
   ```bash
   alembic upgrade head
   ```
3. **Test the connection again:**
   ```bash
   python scripts/test_db_connection.py
   ```





