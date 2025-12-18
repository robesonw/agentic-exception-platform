#!/bin/bash
# Start Backend API Script
# Starts the FastAPI backend server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "Starting Backend API"
echo "=========================================="

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Dependencies not installed. Installing..."
    pip install -r requirements.txt
fi

# Load environment variables from .env if it exists
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set default values if not set
export DATABASE_URL=${DATABASE_URL:-"postgresql+asyncpg://sentinai:sentinai@localhost:5432/sentinai"}
export KAFKA_BOOTSTRAP_SERVERS=${KAFKA_BOOTSTRAP_SERVERS:-"localhost:9092"}

# Create necessary directories
mkdir -p runtime/logs
mkdir -p runtime/audit
mkdir -p runtime/approvals
mkdir -p runtime/simulation
mkdir -p runtime/domainpacks
mkdir -p runtime/metrics

echo ""
echo "Starting FastAPI server on http://localhost:8000"
echo "API Documentation: http://localhost:8000/docs"
echo "Metrics: http://localhost:8000/metrics"
echo "Press Ctrl+C to stop"
echo ""

uvicorn src.api.main:app \
    --reload \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info


