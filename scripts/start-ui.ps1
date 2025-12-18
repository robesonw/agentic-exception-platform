# Start UI Script (PowerShell)
# Starts the React UI development server

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$UiDir = Join-Path $ProjectRoot "ui"

Set-Location $UiDir

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Starting UI Development Server" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Check if node_modules exists
if (-not (Test-Path "node_modules")) {
    Write-Host "Node modules not found. Installing..." -ForegroundColor Yellow
    npm install
}

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

# Set default API URL if not set
if (-not $env:VITE_API_BASE_URL) {
    $env:VITE_API_BASE_URL = "http://localhost:8000"
}

Write-Host ""
Write-Host "Starting UI development server on http://localhost:3000" -ForegroundColor Green
Write-Host "API Base URL: $env:VITE_API_BASE_URL" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

npm run dev


