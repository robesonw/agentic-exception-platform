#!/bin/bash
# Single command to stop all services locally
# This script stops: all workers + docker-compose services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "Stopping Exception Platform (All Services)"
echo "=========================================="
echo ""

# Stop workers
echo "Stopping workers..."
if [ -f "scripts/stop-workers.sh" ]; then
    bash scripts/stop-workers.sh
else
    echo "Warning: scripts/stop-workers.sh not found, skipping worker shutdown"
fi

echo ""
echo "Stopping Docker Compose services..."
docker-compose down

echo ""
echo "=========================================="
echo "All services stopped."
echo "=========================================="
echo ""

