# Single command to stop all services locally (PowerShell)
# This script stops: all workers + docker-compose services

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Stopping Exception Platform (All Services)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Stop workers
Write-Host "Stopping workers..."
if (Test-Path "$ScriptDir\stop-workers.ps1") {
    & "$ScriptDir\stop-workers.ps1"
} else {
    Write-Host "Warning: scripts/stop-workers.ps1 not found, skipping worker shutdown" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Stopping Docker Compose services..."
docker-compose down

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "All services stopped." -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

