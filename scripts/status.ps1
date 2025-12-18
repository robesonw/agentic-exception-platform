# Status Check Script (PowerShell)
# Checks status of all services

$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Exception Platform Services Status" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check Docker services
Write-Host "Docker Services:" -ForegroundColor Yellow
docker-compose ps
Write-Host ""

# Check worker jobs
Write-Host "Worker Jobs:" -ForegroundColor Yellow
$LogsDir = "$ProjectRoot\logs"
if (Test-Path $LogsDir) {
    $JobFiles = Get-ChildItem "$LogsDir\worker-*.job.xml" -ErrorAction SilentlyContinue
    foreach ($JobFile in $JobFiles) {
        try {
            $Job = Import-Clixml $JobFile.FullName
            $WorkerType = $Job.WorkerType
            $State = $Job.State
            if ($State -eq "Running") {
                Write-Host "  ✓ $WorkerType worker (Job ID: $($Job.Id)) - Running" -ForegroundColor Green
            } else {
                Write-Host "  ✗ $WorkerType worker (Job ID: $($Job.Id)) - $State" -ForegroundColor Red
            }
        } catch {
            Write-Host "  ✗ $($JobFile.Name) - Error reading job file" -ForegroundColor Red
        }
    }
    if ($JobFiles.Count -eq 0) {
        Write-Host "  No worker job files found" -ForegroundColor Yellow
    }
} else {
    Write-Host "  No worker logs directory found" -ForegroundColor Yellow
}

# Check service health
Write-Host ""
Write-Host "Service Health:" -ForegroundColor Yellow

Write-Host -NoNewline "  PostgreSQL: "
try {
    $result = docker exec sentinai-postgres pg_isready -U sentinai 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Healthy" -ForegroundColor Green
    } else {
        Write-Host "✗ Unhealthy" -ForegroundColor Red
    }
} catch {
    Write-Host "✗ Unhealthy" -ForegroundColor Red
}

Write-Host -NoNewline "  Kafka: "
try {
    $result = docker exec sentinai-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Healthy" -ForegroundColor Green
    } else {
        Write-Host "✗ Unhealthy" -ForegroundColor Red
    }
} catch {
    Write-Host "✗ Unhealthy" -ForegroundColor Red
}

Write-Host -NoNewline "  Backend API: "
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Host "✓ Healthy" -ForegroundColor Green
    } else {
        Write-Host "✗ Unhealthy" -ForegroundColor Red
    }
} catch {
    Write-Host "✗ Unhealthy" -ForegroundColor Red
}

Write-Host -NoNewline "  UI: "
try {
    $response = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Host "✓ Healthy" -ForegroundColor Green
    } else {
        Write-Host "✗ Unhealthy" -ForegroundColor Red
    }
} catch {
    Write-Host "✗ Unhealthy" -ForegroundColor Red
}

Write-Host ""

