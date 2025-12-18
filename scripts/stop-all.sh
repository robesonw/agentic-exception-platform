#!/bin/bash
# Stop All Services Script
# Stops all infrastructure, backend API, UI, and workers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "Stopping Exception Platform Services"
echo "=========================================="

# Stop Docker Compose services
echo "Stopping Docker Compose services..."
docker-compose stop

echo ""
echo "Services stopped."
echo ""
echo "To remove containers and volumes:"
echo "  docker-compose down"
echo "  docker-compose down -v  # Also removes volumes"
echo ""


