# Health check script for all workers (PowerShell)
# Checks /healthz and /readyz endpoints for each worker type

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

# Worker port mapping
$WorkerPorts = @{
    "intake" = 9001
    "triage" = 9002
    "policy" = 9003
    "playbook" = 9004
    "tool" = 9005
    "feedback" = 9006
    "sla_monitor" = 9007
}

# Function to check health endpoint
function Test-HealthEndpoint {
    param(
        [string]$WorkerType,
        [int]$Port,
        [string]$Endpoint
    )
    
    $url = "http://localhost:${Port}${Endpoint}"
    
    try {
        $response = Invoke-WebRequest -Uri $url -Method Get -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Host "[OK] $WorkerType $Endpoint : OK" -ForegroundColor Green
            return $true
        } else {
            Write-Host "[FAIL] $WorkerType $Endpoint : FAILED (HTTP $($response.StatusCode))" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "[FAIL] $WorkerType $Endpoint : FAILED ($($_.Exception.Message))" -ForegroundColor Red
        return $false
    }
}

# Function to check if port is listening
function Test-Port {
    param([int]$Port)
    
    try {
        $connection = Test-NetConnection -ComputerName localhost -Port $Port -WarningAction SilentlyContinue -ErrorAction Stop
        return $connection.TcpTestSucceeded
    } catch {
        return $false
    }
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Worker Health Check" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Track overall status
$allHealthy = $true
$allReady = $true

# Check each worker
foreach ($workerType in $WorkerPorts.Keys) {
    $port = $WorkerPorts[$workerType]
    
    Write-Host "Checking $workerType worker (port $port)..."
    
    # Check if port is listening
    if (-not (Test-Port -Port $port)) {
        Write-Host "[WARN] $workerType : Port $port not listening (worker may not be running)" -ForegroundColor Yellow
        $allHealthy = $false
        $allReady = $false
        Write-Host ""
        continue
    }
    
    # Check healthz
    if (-not (Test-HealthEndpoint -WorkerType $workerType -Port $port -Endpoint "/healthz")) {
        $allHealthy = $false
    }
    
    # Check readyz
    if (-not (Test-HealthEndpoint -WorkerType $workerType -Port $port -Endpoint "/readyz")) {
        $allReady = $false
    }
    
    Write-Host ""
}

# Summary
Write-Host "==========================================" -ForegroundColor Cyan
if ($allHealthy -and $allReady) {
    Write-Host "All workers are healthy and ready!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Some workers are not healthy or ready" -ForegroundColor Red
    if (-not $allHealthy) {
        Write-Host "  - Health check failures detected" -ForegroundColor Red
    }
    if (-not $allReady) {
        Write-Host "  - Readiness check failures detected" -ForegroundColor Red
    }
    exit 1
}
