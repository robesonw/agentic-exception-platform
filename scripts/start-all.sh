#!/bin/bash
# Start All Services Script
# Starts infrastructure (PostgreSQL, Kafka), backend API, UI, and workers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "Starting Exception Platform Services"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
if ! command_exists docker; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

if ! command_exists docker-compose; then
    echo -e "${RED}Error: docker-compose is not installed${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}Warning: .env file not found. Creating from template...${NC}"
    cat > "$PROJECT_ROOT/.env" << EOF
# Database Configuration
DATABASE_URL=postgresql+asyncpg://sentinai:sentinai@localhost:5432/sentinai

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Worker Configuration (optional - defaults used if not set)
# WORKER_TYPE=intake
# CONCURRENCY=1
# GROUP_ID=intake-workers
EOF
    echo -e "${GREEN}Created .env file. Please review and update if needed.${NC}"
fi

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(cat "$PROJECT_ROOT/.env" | grep -v '^#' | xargs)
fi

echo ""
echo -e "${GREEN}Step 1: Starting Infrastructure (PostgreSQL, Kafka)...${NC}"
docker-compose up -d postgres kafka kafka-ui

echo ""
echo "Waiting for PostgreSQL to be ready..."
timeout=30
counter=0
until docker exec sentinai-postgres pg_isready -U sentinai >/dev/null 2>&1; do
    sleep 1
    counter=$((counter + 1))
    if [ $counter -ge $timeout ]; then
        echo -e "${RED}Error: PostgreSQL failed to start within $timeout seconds${NC}"
        exit 1
    fi
done
echo -e "${GREEN}PostgreSQL is ready${NC}"

echo ""
echo "Waiting for Kafka to be ready..."
timeout=60
counter=0
until docker exec sentinai-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 >/dev/null 2>&1; do
    sleep 2
    counter=$((counter + 2))
    if [ $counter -ge $timeout ]; then
        echo -e "${RED}Error: Kafka failed to start within $timeout seconds${NC}"
        exit 1
    fi
done
echo -e "${GREEN}Kafka is ready${NC}"

echo ""
echo -e "${GREEN}Step 2: Running Database Migrations...${NC}"
if command_exists alembic; then
    alembic upgrade head
    echo -e "${GREEN}Database migrations completed${NC}"
else
    echo -e "${YELLOW}Warning: alembic not found. Skipping migrations.${NC}"
    echo "Run 'alembic upgrade head' manually if needed."
fi

echo ""
echo -e "${GREEN}Step 3: Starting Backend API...${NC}"
docker-compose up -d backend

echo ""
echo "Waiting for Backend API to be ready..."
timeout=30
counter=0
until curl -s http://localhost:8000/health >/dev/null 2>&1; do
    sleep 1
    counter=$((counter + 1))
    if [ $counter -ge $timeout ]; then
        echo -e "${YELLOW}Warning: Backend API health check timeout. It may still be starting...${NC}"
        break
    fi
done
echo -e "${GREEN}Backend API is starting${NC}"

echo ""
echo -e "${GREEN}Step 4: Starting UI...${NC}"
docker-compose up -d ui

echo ""
echo "Waiting for UI to be ready..."
timeout=30
counter=0
until curl -s http://localhost:3000 >/dev/null 2>&1; do
    sleep 1
    counter=$((counter + 1))
    if [ $counter -ge $timeout ]; then
        echo -e "${YELLOW}Warning: UI health check timeout. It may still be starting...${NC}"
        break
    fi
done
echo -e "${GREEN}UI is starting${NC}"

echo ""
echo -e "${GREEN}Step 5: Starting Workers (optional)...${NC}"
echo "Workers can be started manually using:"
echo "  WORKER_TYPE=intake CONCURRENCY=2 GROUP_ID=intake-workers python -m src.workers"
echo ""
echo "Or use the worker startup script:"
echo "  ./scripts/start-workers.sh"

echo ""
echo "=========================================="
echo -e "${GREEN}All Services Started!${NC}"
echo "=========================================="
echo ""
echo "Services:"
echo "  - PostgreSQL:     localhost:5432"
echo "  - Kafka:          localhost:9092"
echo "  - Kafka UI:       http://localhost:8080"
echo "  - Backend API:    http://localhost:8000"
echo "  - UI:             http://localhost:3000"
echo "  - API Docs:       http://localhost:8000/docs"
echo "  - Metrics:        http://localhost:8000/metrics"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f [service_name]"
echo ""
echo "To stop all services:"
echo "  ./scripts/stop-all.sh"
echo ""


