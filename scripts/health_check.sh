#!/bin/bash
# Health check script for all workers
# Checks /healthz and /readyz endpoints for each worker type

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Worker port mapping
declare -A WORKER_PORTS=(
    ["intake"]=9001
    ["triage"]=9002
    ["policy"]=9003
    ["playbook"]=9004
    ["tool"]=9005
    ["feedback"]=9006
    ["sla_monitor"]=9007
)

# Function to check health endpoint
check_health() {
    local worker_type=$1
    local port=$2
    local endpoint=$3
    
    local url="http://localhost:${port}${endpoint}"
    local response=$(curl -s -w "\n%{http_code}" "$url" 2>/dev/null || echo -e "\n000")
    local body=$(echo "$response" | head -n -1)
    local status_code=$(echo "$response" | tail -n 1)
    
    if [ "$status_code" = "200" ]; then
        echo -e "${GREEN}✓${NC} ${worker_type} ${endpoint}: OK"
        return 0
    else
        echo -e "${RED}✗${NC} ${worker_type} ${endpoint}: FAILED (HTTP ${status_code})"
        if [ -n "$body" ]; then
            echo "  Response: $body"
        fi
        return 1
    fi
}

# Function to check if port is listening
check_port() {
    local port=$1
    if command -v nc >/dev/null 2>&1; then
        nc -z localhost "$port" >/dev/null 2>&1
    elif command -v netcat >/dev/null 2>&1; then
        netcat -z localhost "$port" >/dev/null 2>&1
    else
        # Fallback: try curl
        curl -s "http://localhost:${port}/" >/dev/null 2>&1
    fi
}

echo "=========================================="
echo "Worker Health Check"
echo "=========================================="
echo ""

# Check if curl is available
if ! command -v curl >/dev/null 2>&1; then
    echo -e "${RED}Error: curl is required for health checks${NC}"
    exit 1
fi

# Track overall status
all_healthy=true
all_ready=true

# Check each worker
for worker_type in "${!WORKER_PORTS[@]}"; do
    port=${WORKER_PORTS[$worker_type]}
    
    echo "Checking ${worker_type} worker (port ${port})..."
    
    # Check if port is listening
    if ! check_port "$port"; then
        echo -e "${YELLOW}⚠${NC} ${worker_type}: Port ${port} not listening (worker may not be running)"
        all_healthy=false
        all_ready=false
        echo ""
        continue
    fi
    
    # Check healthz
    if ! check_health "$worker_type" "$port" "/healthz"; then
        all_healthy=false
    fi
    
    # Check readyz
    if ! check_health "$worker_type" "$port" "/readyz"; then
        all_ready=false
    fi
    
    echo ""
done

# Summary
echo "=========================================="
if [ "$all_healthy" = true ] && [ "$all_ready" = true ]; then
    echo -e "${GREEN}All workers are healthy and ready!${NC}"
    exit 0
else
    echo -e "${RED}Some workers are not healthy or ready${NC}"
    if [ "$all_healthy" = false ]; then
        echo -e "${RED}  - Health check failures detected${NC}"
    fi
    if [ "$all_ready" = false ]; then
        echo -e "${RED}  - Readiness check failures detected${NC}"
    fi
    exit 1
fi

