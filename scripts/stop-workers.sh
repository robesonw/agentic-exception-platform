#!/bin/bash
# Stop Workers Script
# Stops all running workers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "Stopping Exception Platform Workers"
echo "=========================================="

# Stop workers by PID files
if [ -d "$PROJECT_ROOT/logs" ]; then
    for pid_file in "$PROJECT_ROOT/logs"/worker-*.pid; do
        if [ -f "$pid_file" ]; then
            worker_type=$(basename "$pid_file" .pid | sed 's/worker-//')
            pid=$(cat "$pid_file")
            
            if kill -0 "$pid" 2>/dev/null; then
                echo "Stopping $worker_type worker (PID: $pid)..."
                kill "$pid"
                rm "$pid_file"
            else
                echo "Worker $worker_type (PID: $pid) is not running"
                rm "$pid_file"
            fi
        fi
    done
fi

# Also kill any remaining python worker processes
pkill -f "python -m src.workers" || true

echo ""
echo "All workers stopped."
echo ""


