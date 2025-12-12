#!/bin/bash
# Database migration helper script for Phase 6
# Usage: ./scripts/migrate_db.sh [upgrade|downgrade|current|history]

set -e

# Check if .venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Warning: Virtual environment not activated. Activating .venv..."
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    else
        echo "Error: .venv directory not found. Please create and activate virtual environment first."
        exit 1
    fi
fi

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL environment variable is not set."
    echo "Please set it in your .env file or export it:"
    echo "  export DATABASE_URL=postgresql+asyncpg://user:password@host:port/database"
    exit 1
fi

ACTION=${1:-upgrade}

case $ACTION in
    upgrade)
        echo "Running database migrations (upgrade to head)..."
        alembic upgrade head
        echo "Migrations completed successfully."
        ;;
    downgrade)
        REVISION=${2:-"-1"}
        echo "Rolling back database migration (downgrade $REVISION)..."
        alembic downgrade "$REVISION"
        echo "Rollback completed successfully."
        ;;
    current)
        echo "Current database revision:"
        alembic current
        ;;
    history)
        echo "Migration history:"
        alembic history
        ;;
    *)
        echo "Usage: $0 [upgrade|downgrade|current|history]"
        echo ""
        echo "Commands:"
        echo "  upgrade          Upgrade to latest migration (default)"
        echo "  downgrade [rev]  Rollback migration (default: -1 for previous)"
        echo "  current          Show current database revision"
        echo "  history          Show migration history"
        exit 1
        ;;
esac

