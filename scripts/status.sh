#!/bin/bash
# Status Check Script
# Checks status of all services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "Exception Platform Services Status"
echo "=========================================="
echo ""

# Check Docker services
echo "Docker Services:"
docker-compose ps
echo ""

# Check worker processes
echo "Worker Processes:"
if [ -d "$PROJECT_ROOT/logs" ]; then
    for pid_file in "$PROJECT_ROOT/logs"/worker-*.pid; do
        if [ -f "$pid_file" ]; then
            worker_type=$(basename "$pid_file" .pid | sed 's/worker-//')
            pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                echo "  ✓ $worker_type worker (PID: $pid) - Running"
            else
                echo "  ✗ $worker_type worker (PID: $pid) - Not running"
            fi
        fi
    done
else
    echo "  No worker PID files found"
fi

# Check service health
echo ""
echo "Service Health:"
echo -n "  PostgreSQL: "
if docker exec sentinai-postgres pg_isready -U sentinai >/dev/null 2>&1; then
    echo "✓ Healthy"
else
    echo "✗ Unhealthy"
fi

echo -n "  Kafka: "
if docker exec sentinai-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 >/dev/null 2>&1; then
    echo "✓ Healthy"
else
    echo "✗ Unhealthy"
fi

echo -n "  Backend API: "
if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo "✓ Healthy"
else
    echo "✗ Unhealthy"
fi

echo -n "  UI: "
if curl -s http://localhost:3000 >/dev/null 2>&1; then
    echo "✓ Healthy"
else
    echo "✗ Unhealthy"
fi

echo ""


