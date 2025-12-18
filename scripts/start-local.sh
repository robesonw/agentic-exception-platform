#!/bin/bash
# Single command to start all services locally
# This script starts: postgres + kafka + kafka-ui + api + ui + all workers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "Starting Exception Platform (All Services)"
echo "=========================================="
echo ""

# Start Docker Compose services
echo "Starting Docker Compose services..."
docker-compose up -d

echo ""
echo "Waiting for services to be healthy (this may take 30-60 seconds)..."
sleep 10

# Wait for postgres to be ready
echo "Waiting for PostgreSQL..."
until docker-compose exec -T postgres pg_isready -U sentinai > /dev/null 2>&1; do
    echo "  PostgreSQL not ready yet, waiting..."
    sleep 2
done
echo "  PostgreSQL is ready"

# Wait for Kafka to be ready
echo "Waiting for Kafka..."
until docker-compose exec -T kafka kafka-broker-api-versions.sh --bootstrap-server localhost:9092 > /dev/null 2>&1; do
    echo "  Kafka not ready yet, waiting..."
    sleep 2
done
echo "  Kafka is ready"

echo ""
echo "Starting workers..."
bash scripts/start-workers.sh

echo ""
echo "=========================================="
echo "All services started!"
echo "=========================================="
echo ""
echo "Access points:"
echo "  UI:        http://localhost:3000"
echo "  API Docs:  http://localhost:8000/docs"
echo "  Kafka UI:  http://localhost:8080"
echo ""
echo "To view logs:"
echo "  tail -f logs/worker-*.log"
echo "  docker-compose logs -f"
echo ""
echo "To stop all:"
echo "  ./scripts/stop-local.sh"
echo "  or: make down"
echo ""

