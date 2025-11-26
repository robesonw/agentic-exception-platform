#!/bin/bash
# Startup script for Agentic Exception Processing Platform
# Starts the FastAPI development server with proper configuration

set -e

echo "=========================================="
echo "Agentic Exception Processing Platform"
echo "Starting Development Server"
echo "=========================================="

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Dependencies not installed. Installing..."
    pip install -r requirements.txt
fi

# Create necessary directories
mkdir -p runtime/logs
mkdir -p runtime/audit
mkdir -p runtime/approvals
mkdir -p runtime/simulation
mkdir -p runtime/domainpacks
mkdir -p runtime/metrics

# Check for .env file
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Using default configuration."
    echo "Create .env file for custom configuration (see TECHNICAL_README.md)"
fi

# Start server
echo ""
echo "Starting FastAPI server on http://localhost:8000"
echo "API Documentation: http://localhost:8000/docs"
echo "Press Ctrl+C to stop"
echo ""

uvicorn src.api.main:app \
    --reload \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info

