# Restart All Services Script (PowerShell)
# Restarts all infrastructure, backend API, UI

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Restarting Exception Platform Services" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Restart Docker Compose services
Write-Host "Restarting Docker Compose services..."
docker-compose restart

Write-Host ""
Write-Host "Services restarted." -ForegroundColor Green
Write-Host ""
Write-Host "To view logs:"
Write-Host "  docker-compose logs -f"
Write-Host ""


