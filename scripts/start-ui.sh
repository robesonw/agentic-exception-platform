#!/bin/bash
# Start UI Script
# Starts the React UI development server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT/ui"

echo "=========================================="
echo "Starting UI Development Server"
echo "=========================================="

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Node modules not found. Installing..."
    npm install
fi

# Load environment variables from .env if it exists
if [ -f "../.env" ]; then
    export $(cat ../.env | grep -v '^#' | xargs)
fi

# Set default API URL if not set
export VITE_API_BASE_URL=${VITE_API_BASE_URL:-"http://localhost:8000"}

echo ""
echo "Starting UI development server on http://localhost:3000"
echo "API Base URL: $VITE_API_BASE_URL"
echo "Press Ctrl+C to stop"
echo ""

npm run dev


