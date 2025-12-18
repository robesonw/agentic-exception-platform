# Start Workers Script (PowerShell)
# Starts all worker types for event processing

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Starting Exception Platform Workers" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Check if virtual environment exists
if (-not (Test-Path "$ProjectRoot\.venv")) {
    Write-Host "Warning: Virtual environment not found. Creating..." -ForegroundColor Yellow
    python -m venv .venv
}

# Activate virtual environment
& "$ProjectRoot\.venv\Scripts\Activate.ps1"

# Load environment variables from .env if it exists
if (Test-Path "$ProjectRoot\.env") {
    Get-Content "$ProjectRoot\.env" | ForEach-Object {
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
    $env:KAFKA_BOOTSTRAP_SERVERS = "localhost:29092"
}

# Worker configurations
# Note: Tool worker skipped - requires session-based repositories
$Workers = @{
    "intake" = @{ Concurrency = 1; GroupId = "intake-workers-v3" }
    "triage" = @{ Concurrency = 1; GroupId = "triage-workers-v2" }
    "policy" = @{ Concurrency = 1; GroupId = "policy-workers-v2" }
    "playbook" = @{ Concurrency = 1; GroupId = "playbook-workers-v2" }
    "tool" = @{ Concurrency = 1; GroupId = "tool-workers-v2" }
    "feedback" = @{ Concurrency = 1; GroupId = "feedback-workers-v2" }
    "sla_monitor" = @{ Concurrency = 1; GroupId = "sla-monitors" }
}

# Function to start a worker
function Start-Worker {
    param(
        [string]$WorkerType,
        [int]$Concurrency,
        [string]$GroupId
    )
    
    Write-Host ""
    Write-Host "Starting $WorkerType worker (concurrency=$Concurrency, group_id=$GroupId)..." -ForegroundColor Green
    
    # Create logs directory if it doesn't exist
    $LogsDir = "$ProjectRoot\logs"
    if (-not (Test-Path $LogsDir)) {
        New-Item -ItemType Directory -Path $LogsDir | Out-Null
    }
    
    # Start worker in background job with proper environment
    $Job = Start-Job -ScriptBlock {
        param($WorkerType, $Concurrency, $GroupId, $DatabaseUrl, $KafkaBootstrapServers, $ProjectRoot)
        
        Set-Location $ProjectRoot
        $env:WORKER_TYPE = $WorkerType
        $env:CONCURRENCY = $Concurrency.ToString()
        $env:GROUP_ID = $GroupId
        $env:DATABASE_URL = $DatabaseUrl
        $env:KAFKA_BOOTSTRAP_SERVERS = $KafkaBootstrapServers
        $env:PYTHONUNBUFFERED = "1"
        
        # Redirect output to log file
        $logFile = "$ProjectRoot\logs\worker-${WorkerType}.log"
        $logDir = Split-Path $logFile -Parent
        if (-not (Test-Path $logDir)) {
            New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        }
        
        & "$ProjectRoot\.venv\Scripts\python.exe" -m src.workers *> $logFile
    } -ArgumentList $WorkerType, $Concurrency, $GroupId, $env:DATABASE_URL, $env:KAFKA_BOOTSTRAP_SERVERS, $ProjectRoot
    
    # Set environment variables for the job
    $Job | Add-Member -NotePropertyName WorkerType -NotePropertyValue $WorkerType
    $Job | Add-Member -NotePropertyName Concurrency -NotePropertyValue $Concurrency
    $Job | Add-Member -NotePropertyName GroupId -NotePropertyValue $GroupId
    
    Write-Host "  Started with Job ID: $($Job.Id)" -ForegroundColor Green
    
    # Save job info
    $Job | Export-Clixml "$ProjectRoot\logs\worker-${WorkerType}.job.xml"
    
    return $Job
}

# Start all workers
$Jobs = @{}
foreach ($WorkerType in $Workers.Keys) {
    $Config = $Workers[$WorkerType]
    $Job = Start-Worker -WorkerType $WorkerType -Concurrency $Config.Concurrency -GroupId $Config.GroupId
    $Jobs[$WorkerType] = $Job
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "All Workers Started!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Worker Jobs:"
foreach ($WorkerType in $Jobs.Keys) {
    Write-Host "  - $WorkerType : Job ID $($Jobs[$WorkerType].Id)"
}
Write-Host ""
Write-Host "To stop workers:"
Write-Host "  .\scripts\stop-workers.ps1"
Write-Host ""
Write-Host "To view worker status:"
Write-Host "  Get-Job"
Write-Host ""
Write-Host "To view worker output:"
Write-Host "  Receive-Job -Id [JobId]"
Write-Host ""

