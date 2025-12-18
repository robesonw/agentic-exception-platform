#!/bin/bash
# Restart All Services Script
# Restarts all infrastructure, backend API, UI

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "Restarting Exception Platform Services"
echo "=========================================="

# Restart Docker Compose services
echo "Restarting Docker Compose services..."
docker-compose restart

echo ""
echo "Services restarted."
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""


