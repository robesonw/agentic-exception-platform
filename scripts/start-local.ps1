# Single command to start all services locally (PowerShell)
# This script starts: postgres + kafka + kafka-ui + api + ui + all workers

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Starting Exception Platform (All Services)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Start Docker Compose services
Write-Host "Starting Docker Compose services..."
docker-compose up -d

Write-Host ""
Write-Host "Waiting for services to be healthy (this may take 30-60 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Wait for postgres to be ready
Write-Host "Waiting for PostgreSQL..."
do {
    $result = docker-compose exec -T postgres pg_isready -U sentinai 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  PostgreSQL not ready yet, waiting..." -ForegroundColor Yellow
        Start-Sleep -Seconds 2
    }
} while ($LASTEXITCODE -ne 0)
Write-Host "  PostgreSQL is ready" -ForegroundColor Green

# Wait for Kafka to be ready
Write-Host "Waiting for Kafka..."
do {
    $result = docker-compose exec -T kafka kafka-broker-api-versions.sh --bootstrap-server localhost:9092 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Kafka not ready yet, waiting..." -ForegroundColor Yellow
        Start-Sleep -Seconds 2
    }
} while ($LASTEXITCODE -ne 0)
Write-Host "  Kafka is ready" -ForegroundColor Green

Write-Host ""
Write-Host "Starting workers..."
& "$ScriptDir\start-workers.ps1"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "All services started!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Access points:"
Write-Host "  UI:        http://localhost:3000"
Write-Host "  API Docs:  http://localhost:8000/docs"
Write-Host "  Kafka UI:  http://localhost:8080"
Write-Host ""
Write-Host "To view logs:"
Write-Host "  Get-Content logs\worker-*.log -Wait"
Write-Host "  docker-compose logs -f"
Write-Host ""
Write-Host "To stop all:"
Write-Host "  .\scripts\stop-local.ps1"
Write-Host "  or: make down"
Write-Host ""

