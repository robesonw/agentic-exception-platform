#!/bin/bash
# Start Workers Script
# Starts all worker types for event processing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Starting Exception Platform Workers"
echo "=========================================="

# Check if virtual environment exists
if [ ! -d "$PROJECT_ROOT/.venv" ]; then
    echo -e "${YELLOW}Warning: Virtual environment not found. Creating...${NC}"
    python -m venv .venv
fi

# Activate virtual environment
source "$PROJECT_ROOT/.venv/bin/activate"

# Check if .env file exists and load it
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(cat "$PROJECT_ROOT/.env" | grep -v '^#' | xargs)
fi

# Set default values if not set
export DATABASE_URL=${DATABASE_URL:-"postgresql+asyncpg://sentinai:sentinai@localhost:5432/sentinai"}
export KAFKA_BOOTSTRAP_SERVERS=${KAFKA_BOOTSTRAP_SERVERS:-"localhost:9092"}

# Worker configurations
declare -A WORKERS=(
    ["intake"]="2:intake-workers"
    ["triage"]="4:triage-workers"
    ["policy"]="2:policy-workers"
    ["playbook"]="2:playbook-workers"
    ["tool"]="4:tool-workers"
    ["feedback"]="2:feedback-workers"
    ["sla_monitor"]="1:sla-monitors"
)

# Function to start a worker
start_worker() {
    local worker_type=$1
    local concurrency=$2
    local group_id=$3
    
    echo ""
    echo -e "${GREEN}Starting $worker_type worker (concurrency=$concurrency, group_id=$group_id)...${NC}"
    
    # Start worker in background
    WORKER_TYPE=$worker_type \
    CONCURRENCY=$concurrency \
    GROUP_ID=$group_id \
    DATABASE_URL=$DATABASE_URL \
    KAFKA_BOOTSTRAP_SERVERS=$KAFKA_BOOTSTRAP_SERVERS \
    python -m src.workers > "logs/worker-${worker_type}.log" 2>&1 &
    
    local pid=$!
    echo "  Started with PID: $pid"
    echo $pid > "logs/worker-${worker_type}.pid"
}

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/logs"

# Start all workers
for worker_type in "${!WORKERS[@]}"; do
    IFS=':' read -r concurrency group_id <<< "${WORKERS[$worker_type]}"
    start_worker "$worker_type" "$concurrency" "$group_id"
done

echo ""
echo "=========================================="
echo -e "${GREEN}All Workers Started!${NC}"
echo "=========================================="
echo ""
echo "Worker PIDs saved to logs/worker-*.pid"
echo "Worker logs saved to logs/worker-*.log"
echo ""
echo "To stop workers:"
echo "  ./scripts/stop-workers.sh"
echo ""
echo "To view worker logs:"
echo "  tail -f logs/worker-*.log"
echo ""


