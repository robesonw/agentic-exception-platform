# Start Backend API Script (PowerShell)
# Starts the FastAPI backend server

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Starting Backend API" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Check if virtual environment exists
if (-not (Test-Path ".venv")) {
    Write-Host "Virtual environment not found. Creating..." -ForegroundColor Yellow
    python -m venv .venv
}

# Activate virtual environment
& ".venv\Scripts\Activate.ps1"

# Check if dependencies are installed
try {
    python -c "import fastapi" 2>&1 | Out-Null
} catch {
    Write-Host "Dependencies not installed. Installing..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

# Load environment variables from .env if it exists
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

# Set default values if not set
if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "postgresql+asyncpg://sentinai:sentinai@localhost:5432/sentinai"
}
if (-not $env:KAFKA_BOOTSTRAP_SERVERS) {
    $env:KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
}

# Create necessary directories
$Dirs = @("runtime/logs", "runtime/audit", "runtime/approvals", "runtime/simulation", "runtime/domainpacks", "runtime/metrics")
foreach ($Dir in $Dirs) {
    if (-not (Test-Path $Dir)) {
        New-Item -ItemType Directory -Path $Dir -Force | Out-Null
    }
}

Write-Host ""
Write-Host "Starting FastAPI server on http://localhost:8000" -ForegroundColor Green
Write-Host "API Documentation: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Metrics: http://localhost:8000/metrics" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000 --log-level info


