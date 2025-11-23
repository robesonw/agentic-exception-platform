#!/bin/bash
# Test runner script with coverage reporting.
# Generates coverage reports in terminal and HTML format.

set -e

echo "Running tests with coverage..."

# Run tests with coverage
pytest \
    --cov=src \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-report=xml \
    -v

echo ""
echo "Coverage report generated:"
echo "  - Terminal: shown above"
echo "  - HTML: htmlcov/index.html"
echo "  - XML: coverage.xml"

# Check if coverage meets threshold
echo ""
echo "Checking coverage threshold (80%)..."
coverage report --fail-under=80 || {
    echo "WARNING: Coverage is below 80% threshold"
    exit 1
}

echo "All tests passed and coverage threshold met!"

