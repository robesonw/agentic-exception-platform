# Restart UI Script (PowerShell)
# Stops and restarts the UI service, loading environment variables from ui/.env

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Restarting UI Service" -ForegroundColor Cyan
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

Write-Host ""
Write-Host "Step 1: Stopping UI service..." -ForegroundColor Yellow
docker-compose stop ui
if ($LASTEXITCODE -eq 0) {
    Write-Host "UI service stopped" -ForegroundColor Green
} else {
    Write-Host "Warning: UI service may not have been running" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Step 2: Removing UI container..." -ForegroundColor Yellow
docker-compose rm -f ui
Write-Host "UI container removed" -ForegroundColor Green

Write-Host ""
Write-Host "Step 3: Loading UI environment variables from ui/.env..." -ForegroundColor Cyan

# Load UI environment variables from ui/.env
$uiEnvPath = Join-Path $ProjectRoot "ui\.env"
if (Test-Path $uiEnvPath) {
    Get-Content $uiEnvPath | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Set in process environment so docker-compose can use them
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
            if ($name -like "VITE_*") {
                Write-Host "  Loaded: $name = $value" -ForegroundColor Gray
            }
        }
    }
    Write-Host "UI environment variables loaded" -ForegroundColor Green
} else {
    Write-Host "Warning: ui/.env file not found. UI will use default environment variables." -ForegroundColor Yellow
    Write-Host "  Create ui/.env with VITE_OPS_ENABLED, VITE_ADMIN_ENABLED, etc. if needed." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Step 4: Starting UI service..." -ForegroundColor Green
docker-compose up -d ui

Write-Host ""
Write-Host "Waiting for UI to be ready..." -ForegroundColor Cyan
$timeout = 30
$counter = 0
do {
    Start-Sleep -Seconds 1
    $counter++
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 1 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "UI is ready!" -ForegroundColor Green
            break
        }
    } catch {
        # Continue waiting
    }
    if ($counter -ge $timeout) {
        Write-Host "Warning: UI health check timeout. It may still be starting..." -ForegroundColor Yellow
        Write-Host "  Check logs with: docker-compose logs -f ui" -ForegroundColor Yellow
        break
    }
} while ($true)

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "UI Restart Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "UI: http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Yellow
Write-Host "  docker-compose logs -f ui" -ForegroundColor Gray
Write-Host ""
Write-Host "To stop UI:" -ForegroundColor Yellow
Write-Host "  docker-compose stop ui" -ForegroundColor Gray
Write-Host ""

