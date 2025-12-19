# Start All Services Script (PowerShell)
# Starts infrastructure (PostgreSQL, Kafka), backend API, UI, and workers

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Starting Exception Platform Services" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Check prerequisites
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Docker is not installed" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Host "Error: docker-compose is not installed" -ForegroundColor Red
    exit 1
}

# Check if .env file exists
if (-not (Test-Path "$ProjectRoot\.env")) {
    Write-Host "Warning: .env file not found. Creating from template..." -ForegroundColor Yellow
    @"
# Database Configuration
DATABASE_URL=postgresql+asyncpg://sentinai:sentinai@localhost:5432/sentinai

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Worker Configuration (optional - defaults used if not set)
# WORKER_TYPE=intake
# CONCURRENCY=1
# GROUP_ID=intake-workers
"@ | Out-File -FilePath "$ProjectRoot\.env" -Encoding utf8
    Write-Host "Created .env file. Please review and update if needed." -ForegroundColor Green
}

# Load environment variables
if (Test-Path "$ProjectRoot\.env") {
    Get-Content "$ProjectRoot\.env" | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

Write-Host ""
Write-Host "Step 1: Starting Infrastructure (PostgreSQL, Kafka)..." -ForegroundColor Green
docker-compose up -d postgres kafka kafka-ui

Write-Host ""
Write-Host "Waiting for PostgreSQL to be ready..."
$timeout = 30
$counter = 0
do {
    Start-Sleep -Seconds 1
    $counter++
    $result = docker exec sentinai-postgres pg_isready -U sentinai 2>&1
    if ($LASTEXITCODE -eq 0) {
        break
    }
    if ($counter -ge $timeout) {
        Write-Host "Error: PostgreSQL failed to start within $timeout seconds" -ForegroundColor Red
        exit 1
    }
} while ($true)
Write-Host "PostgreSQL is ready" -ForegroundColor Green

Write-Host ""
Write-Host "Waiting for Kafka to be ready..."
$timeout = 60
$counter = 0
do {
    Start-Sleep -Seconds 2
    $counter += 2
    $result = docker exec sentinai-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 2>&1
    if ($LASTEXITCODE -eq 0) {
        break
    }
    if ($counter -ge $timeout) {
        Write-Host "Error: Kafka failed to start within $timeout seconds" -ForegroundColor Red
        exit 1
    }
} while ($true)
Write-Host "Kafka is ready" -ForegroundColor Green

Write-Host ""
Write-Host "Step 2: Running Database Migrations..." -ForegroundColor Green
if (Get-Command alembic -ErrorAction SilentlyContinue) {
    alembic upgrade head
    Write-Host "Database migrations completed" -ForegroundColor Green
} else {
    Write-Host "Warning: alembic not found. Skipping migrations." -ForegroundColor Yellow
    Write-Host "Run 'alembic upgrade head' manually if needed."
}

Write-Host ""
Write-Host "Step 3: Starting Backend API..." -ForegroundColor Green
docker-compose up -d backend

Write-Host ""
Write-Host "Waiting for Backend API to be ready..."
$timeout = 30
$counter = 0
do {
    Start-Sleep -Seconds 1
    $counter++
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 1 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            break
        }
    } catch {
        # Continue waiting
    }
    if ($counter -ge $timeout) {
        Write-Host "Warning: Backend API health check timeout. It may still be starting..." -ForegroundColor Yellow
        break
    }
} while ($true)
Write-Host "Backend API is starting" -ForegroundColor Green

Write-Host ""
Write-Host "Step 4: Starting UI..." -ForegroundColor Green

# Load UI environment variables from ui/.env
$uiEnvPath = Join-Path $ProjectRoot "ui\.env"
if (Test-Path $uiEnvPath) {
    Write-Host "Loading UI environment variables from ui/.env..." -ForegroundColor Cyan
    Get-Content $uiEnvPath | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Set in process environment so docker-compose can use them
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
            if ($name -like "VITE_*") {
                Write-Host "  Loaded: $name" -ForegroundColor Gray
            }
        }
    }
    Write-Host "UI environment variables loaded" -ForegroundColor Green
} else {
    Write-Host "Warning: ui/.env file not found. UI will use default environment variables." -ForegroundColor Yellow
    Write-Host "  Create ui/.env with VITE_OPS_ENABLED, VITE_ADMIN_ENABLED, etc. if needed." -ForegroundColor Yellow
}

docker-compose up -d ui

Write-Host ""
Write-Host "Waiting for UI to be ready..."
$timeout = 30
$counter = 0
do {
    Start-Sleep -Seconds 1
    $counter++
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 1 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            break
        }
    } catch {
        # Continue waiting
    }
    if ($counter -ge $timeout) {
        Write-Host "Warning: UI health check timeout. It may still be starting..." -ForegroundColor Yellow
        break
    }
} while ($true)
Write-Host "UI is starting" -ForegroundColor Green

Write-Host ""
Write-Host "Step 5: Starting Workers (optional)..." -ForegroundColor Green
Write-Host "Workers can be started manually using:"
Write-Host "  `$env:WORKER_TYPE='intake'; `$env:CONCURRENCY='2'; `$env:GROUP_ID='intake-workers'; python -m src.workers"
Write-Host ""
Write-Host "Or use the worker startup script:"
Write-Host "  .\scripts\start-workers.ps1"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "All Services Started!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:"
Write-Host "  - PostgreSQL:     localhost:5432"
Write-Host "  - Kafka:          localhost:9092"
Write-Host "  - Kafka UI:       http://localhost:8080"
Write-Host "  - Backend API:    http://localhost:8000"
Write-Host "  - UI:             http://localhost:3000"
Write-Host "  - API Docs:       http://localhost:8000/docs"
Write-Host "  - Metrics:        http://localhost:8000/metrics"
Write-Host ""
Write-Host "To view logs:"
Write-Host "  docker-compose logs -f [service_name]"
Write-Host ""
Write-Host "To stop all services:"
Write-Host "  .\scripts\stop-all.ps1"
Write-Host ""

