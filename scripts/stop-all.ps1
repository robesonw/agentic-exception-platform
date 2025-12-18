# Stop All Services Script (PowerShell)
# Stops all infrastructure, backend API, UI, and workers

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Stopping Exception Platform Services" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Stop Docker Compose services
Write-Host "Stopping Docker Compose services..."
docker-compose stop

Write-Host ""
Write-Host "Services stopped." -ForegroundColor Green
Write-Host ""
Write-Host "To remove containers and volumes:"
Write-Host "  docker-compose down"
Write-Host "  docker-compose down -v  # Also removes volumes"
Write-Host ""


