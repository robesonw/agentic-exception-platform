# Stop Workers Script (PowerShell)
# Stops all running workers

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Stopping Exception Platform Workers" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Stop workers by job files
$LogsDir = "$ProjectRoot\logs"
if (Test-Path $LogsDir) {
    $JobFiles = Get-ChildItem "$LogsDir\worker-*.job.xml" -ErrorAction SilentlyContinue
    foreach ($JobFile in $JobFiles) {
        $DeserializedJob = Import-Clixml $JobFile.FullName
        $JobId = $DeserializedJob.Id
        $WorkerType = $DeserializedJob.WorkerType
        
        # Get the actual job object from the current session
        $ActualJob = Get-Job -Id $JobId -ErrorAction SilentlyContinue
        if ($ActualJob) {
            if ($ActualJob.State -eq "Running" -or $ActualJob.State -eq "NotStarted") {
                Write-Host "Stopping $WorkerType worker (Job ID: $JobId)..." -ForegroundColor Yellow
                Stop-Job -Id $JobId -ErrorAction SilentlyContinue
            }
            Remove-Job -Id $JobId -ErrorAction SilentlyContinue
        } else {
            Write-Host "Job $WorkerType (Job ID: $JobId) not found in current session, cleaning up job file..." -ForegroundColor Gray
        }
        Remove-Item $JobFile.FullName -ErrorAction SilentlyContinue
    }
}

# Also stop any remaining jobs
Get-Job | Where-Object { $_.Command -like "*src.workers*" } | Stop-Job
Get-Job | Where-Object { $_.Command -like "*src.workers*" } | Remove-Job

# Kill any remaining python worker processes
Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*src.workers*"
} | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "All workers stopped." -ForegroundColor Green
Write-Host ""


