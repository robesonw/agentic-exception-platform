# PowerShell script to manage PostgreSQL Docker container
# Usage:
#   .\scripts\docker_db.ps1 start    - Start PostgreSQL container
#   .\scripts\docker_db.ps1 stop     - Stop PostgreSQL container
#   .\scripts\docker_db.ps1 restart   - Restart PostgreSQL container
#   .\scripts\docker_db.ps1 status   - Check container status
#   .\scripts\docker_db.ps1 logs     - Show container logs
#   .\scripts\docker_db.ps1 shell     - Open psql shell in container
#   .\scripts\docker_db.ps1 remove    - Remove container and volumes

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "restart", "status", "logs", "shell", "remove")]
    [string]$Command = "status"
)

$ContainerName = "sentinai-postgres"

function Show-Status {
    Write-Host "`n=== PostgreSQL Docker Container Status ===" -ForegroundColor Cyan
    docker ps -a --filter "name=$ContainerName" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    Write-Host ""
}

function Start-Container {
    Write-Host "Starting PostgreSQL container..." -ForegroundColor Green
    docker-compose up -d postgres
    
    Write-Host "Waiting for PostgreSQL to be ready..." -ForegroundColor Yellow
    $maxAttempts = 30
    $attempt = 0
    
    while ($attempt -lt $maxAttempts) {
        $health = docker inspect --format='{{.State.Health.Status}}' $ContainerName 2>$null
        if ($health -eq "healthy") {
            Write-Host "[OK] PostgreSQL is ready!" -ForegroundColor Green
            Write-Host "`nConnection details:" -ForegroundColor Cyan
            Write-Host "  Host: localhost"
            Write-Host "  Port: 5432"
            Write-Host "  Database: sentinai"
            Write-Host "  Username: postgres"
            Write-Host "  Password: postgres"
            Write-Host "`nDATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai" -ForegroundColor Yellow
            return
        }
        Start-Sleep -Seconds 1
        $attempt++
        Write-Host "." -NoNewline
    }
    
    Write-Host "`n[WARNING] Container started but health check timed out" -ForegroundColor Yellow
    Write-Host "Check logs with: docker-compose logs postgres" -ForegroundColor Yellow
}

function Stop-Container {
    Write-Host "Stopping PostgreSQL container..." -ForegroundColor Yellow
    docker-compose stop postgres
    Write-Host "[OK] Container stopped" -ForegroundColor Green
}

function Restart-Container {
    Write-Host "Restarting PostgreSQL container..." -ForegroundColor Yellow
    docker-compose restart postgres
    Start-Sleep -Seconds 2
    Show-Status
}

function Show-Logs {
    Write-Host "=== PostgreSQL Container Logs ===" -ForegroundColor Cyan
    docker-compose logs -f postgres
}

function Open-Shell {
    Write-Host "Opening psql shell..." -ForegroundColor Cyan
    docker exec -it $ContainerName psql -U postgres -d sentinai
}

function Remove-Container {
    Write-Host "WARNING: This will remove the container and all data!" -ForegroundColor Red
    $confirm = Read-Host "Type 'yes' to confirm"
    if ($confirm -eq "yes") {
        Write-Host "Removing container and volumes..." -ForegroundColor Yellow
        docker-compose down -v
        Write-Host "[OK] Container and volumes removed" -ForegroundColor Green
    } else {
        Write-Host "Cancelled" -ForegroundColor Yellow
    }
}

switch ($Command) {
    "start"   { Start-Container }
    "stop"    { Stop-Container }
    "restart" { Restart-Container }
    "status"  { Show-Status }
    "logs"    { Show-Logs }
    "shell"   { Open-Shell }
    "remove"  { Remove-Container }
    default   { Show-Status }
}

