# Start All Services Script (PowerShell)
# Starts infrastructure (PostgreSQL, Kafka), backend API, UI, and workers

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Starting Exception Platform Services" -ForegroundColor Cyan
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

# Check if .env file exists
if (-not (Test-Path "$ProjectRoot\.env")) {
    Write-Host "Warning: .env file not found. Creating from template..." -ForegroundColor Yellow
    @"
# Database Configuration
DATABASE_URL=postgresql+asyncpg://sentinai:sentinai@localhost:5432/sentinai

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Worker Configuration (optional - defaults used if not set)
# WORKER_TYPE=intake
# CONCURRENCY=1
# GROUP_ID=intake-workers
"@ | Out-File -FilePath "$ProjectRoot\.env" -Encoding utf8
    Write-Host "Created .env file. Please review and update if needed." -ForegroundColor Green
}

# Load environment variables
if (Test-Path "$ProjectRoot\.env") {
    Get-Content "$ProjectRoot\.env" | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

Write-Host ""
Write-Host "Step 1: Starting Infrastructure (PostgreSQL, Kafka)..." -ForegroundColor Green
$ErrorActionPreference = "Continue"
docker-compose up -d postgres kafka kafka-ui 2>&1 | Out-Host
$ErrorActionPreference = "Stop"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to start infrastructure services" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Waiting for PostgreSQL to be ready..."
$timeout = 30
$counter = 0
do {
    Start-Sleep -Seconds 1
    $counter++
    try {
        $result = docker exec sentinai-postgres pg_isready -U sentinai 2>&1
        if ($LASTEXITCODE -eq 0) {
            break
        }
    } catch {
        # Container may not be ready yet
    }
    if ($counter -ge $timeout) {
        Write-Host "Error: PostgreSQL failed to start within $timeout seconds" -ForegroundColor Red
        exit 1
    }
} while ($true)
Write-Host "PostgreSQL is ready" -ForegroundColor Green

Write-Host ""
Write-Host "Waiting for Kafka to be ready..."
$timeout = 60
$counter = 0
do {
    Start-Sleep -Seconds 2
    $counter += 2
    try {
        $result = docker exec sentinai-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 2>&1
        if ($LASTEXITCODE -eq 0) {
            break
        }
    } catch {
        # Container may not be ready yet
    }
    if ($counter -ge $timeout) {
        Write-Host "Error: Kafka failed to start within $timeout seconds" -ForegroundColor Red
        exit 1
    }
} while ($true)
Write-Host "Kafka is ready" -ForegroundColor Green

Write-Host ""
Write-Host "Initializing Kafka topics..." -ForegroundColor Green
$ErrorActionPreference = "Continue"
docker-compose run --rm kafka-init 2>&1 | Out-Host
$ErrorActionPreference = "Stop"
if ($LASTEXITCODE -eq 0) {
    Write-Host "Kafka topics initialized" -ForegroundColor Green
} else {
    Write-Host "Warning: Kafka topic initialization may have failed. Continuing..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Step 2: Running Database Migrations..." -ForegroundColor Green

# Verify database is accessible before running migrations
Write-Host "Verifying database connection..." -ForegroundColor Cyan
$dbCheck = docker exec sentinai-postgres psql -U sentinai -d sentinai -c "SELECT 1;" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: Database connection check failed. Migrations may fail." -ForegroundColor Yellow
} else {
    Write-Host "Database connection verified" -ForegroundColor Green
}

# Check for virtual environment
$venvPath = Join-Path $ProjectRoot ".venv"
$venvAlembic = Join-Path $venvPath "Scripts\alembic.exe"

if (Test-Path $venvAlembic) {
    Write-Host "Using alembic from virtual environment..." -ForegroundColor Cyan
    # Ensure DATABASE_URL is set
    if (-not $env:DATABASE_URL) {
        Write-Host "Warning: DATABASE_URL not set. Using default..." -ForegroundColor Yellow
        $env:DATABASE_URL = "postgresql+asyncpg://sentinai:sentinai@localhost:5432/sentinai"
    }
    
    # Run migrations
    Write-Host "Running migrations..." -ForegroundColor Cyan
    $oldErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        # Run alembic directly - INFO messages go to stderr, which is normal
        & $venvAlembic upgrade head 2>&1 | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) {
                # Stderr output (INFO messages) - display as info
                Write-Host $_.ToString() -ForegroundColor Gray
            } else {
                Write-Host $_ -ForegroundColor Gray
            }
        }
        $exitCode = $LASTEXITCODE
        $ErrorActionPreference = $oldErrorAction
        if ($exitCode -eq 0) {
            Write-Host "Database migrations completed" -ForegroundColor Green
        } else {
            Write-Host "Migrations exited with code $exitCode. Continuing anyway..." -ForegroundColor Yellow
        }
    } catch {
        $ErrorActionPreference = $oldErrorAction
        Write-Host "Error running migrations: $_" -ForegroundColor Red
        Write-Host "Continuing anyway..." -ForegroundColor Yellow
    }
} elseif (Get-Command alembic -ErrorAction SilentlyContinue) {
    Write-Host "Using system alembic..." -ForegroundColor Cyan
    # Ensure DATABASE_URL is set
    if (-not $env:DATABASE_URL) {
        Write-Host "Warning: DATABASE_URL not set. Using default..." -ForegroundColor Yellow
        $env:DATABASE_URL = "postgresql+asyncpg://sentinai:sentinai@localhost:5432/sentinai"
    }
    
    $oldErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        alembic upgrade head 2>&1 | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) {
                Write-Host $_.ToString() -ForegroundColor Gray
            } else {
                Write-Host $_ -ForegroundColor Gray
            }
        }
        $exitCode = $LASTEXITCODE
        $ErrorActionPreference = $oldErrorAction
        if ($exitCode -eq 0) {
            Write-Host "Database migrations completed" -ForegroundColor Green
        } else {
            Write-Host "Migrations exited with code $exitCode. Continuing anyway..." -ForegroundColor Yellow
        }
    } catch {
        $ErrorActionPreference = $oldErrorAction
        Write-Host "Error running migrations: $_" -ForegroundColor Red
        Write-Host "Continuing anyway..." -ForegroundColor Yellow
    }
} else {
    Write-Host "Warning: alembic not found. Skipping migrations." -ForegroundColor Yellow
    Write-Host "Run 'alembic upgrade head' manually if needed."
}

Write-Host ""
Write-Host "Step 3: Starting Backend API..." -ForegroundColor Green
$ErrorActionPreference = "Continue"
docker-compose up -d backend 2>&1 | Out-Host
$ErrorActionPreference = "Stop"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: Failed to start backend service. It may already be running." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Waiting for Backend API to be ready..."
$timeout = 30
$counter = 0
do {
    Start-Sleep -Seconds 1
    $counter++
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 1 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            break
        }
    } catch {
        # Continue waiting
    }
    if ($counter -ge $timeout) {
        Write-Host "Warning: Backend API health check timeout. It may still be starting..." -ForegroundColor Yellow
        break
    }
} while ($true)
Write-Host "Backend API is starting" -ForegroundColor Green

Write-Host ""
Write-Host "Step 4: Starting UI..." -ForegroundColor Green

# Load UI environment variables from ui/.env
$uiEnvPath = Join-Path $ProjectRoot "ui\.env"
if (Test-Path $uiEnvPath) {
    Write-Host "Loading UI environment variables from ui/.env..." -ForegroundColor Cyan
    Get-Content $uiEnvPath | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Set in process environment so docker-compose can use them
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
            if ($name -like "VITE_*") {
                Write-Host "  Loaded: $name" -ForegroundColor Gray
            }
        }
    }
    Write-Host "UI environment variables loaded" -ForegroundColor Green
} else {
    Write-Host "Warning: ui/.env file not found. UI will use default environment variables." -ForegroundColor Yellow
    Write-Host "  Create ui/.env with VITE_OPS_ENABLED, VITE_ADMIN_ENABLED, etc. if needed." -ForegroundColor Yellow
}

$ErrorActionPreference = "Continue"
docker-compose up -d ui 2>&1 | Out-Host
$ErrorActionPreference = "Stop"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: Failed to start UI service. It may already be running." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Waiting for UI to be ready..."
$timeout = 30
$counter = 0
do {
    Start-Sleep -Seconds 1
    $counter++
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 1 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            break
        }
    } catch {
        # Continue waiting
    }
    if ($counter -ge $timeout) {
        Write-Host "Warning: UI health check timeout. It may still be starting..." -ForegroundColor Yellow
        break
    }
} while ($true)
Write-Host "UI is starting" -ForegroundColor Green

Write-Host ""
Write-Host "Step 5: Starting Workers..." -ForegroundColor Green
$ErrorActionPreference = "Continue"
docker-compose up -d intake-worker triage-worker policy-worker playbook-worker feedback-worker tool-worker sla-monitor 2>&1 | Out-Host
$ErrorActionPreference = "Stop"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: Some workers may have failed to start. Check logs for details." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Waiting for workers to be ready..."
$workerServices = @(
    @{Name="intake-worker"; Port=9001},
    @{Name="triage-worker"; Port=9002},
    @{Name="policy-worker"; Port=9003},
    @{Name="playbook-worker"; Port=9004},
    @{Name="tool-worker"; Port=9005},
    @{Name="feedback-worker"; Port=9006},
    @{Name="sla-monitor"; Port=9007}
)

$allWorkersReady = $false
$timeout = 60
$counter = 0

do {
    Start-Sleep -Seconds 2
    $counter += 2
    $readyCount = 0
    
    foreach ($worker in $workerServices) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:$($worker.Port)/readyz" -UseBasicParsing -TimeoutSec 1 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $readyCount++
            }
        } catch {
            # Worker not ready yet
        }
    }
    
    if ($readyCount -eq $workerServices.Count) {
        $allWorkersReady = $true
        break
    }
    
    if ($counter -ge $timeout) {
        Write-Host "Warning: Some workers may not be ready yet. $readyCount/$($workerServices.Count) workers are ready." -ForegroundColor Yellow
        break
    }
} while ($true)

if ($allWorkersReady) {
    Write-Host "All workers are ready" -ForegroundColor Green
} else {
    Write-Host "Workers are starting (some may still be initializing)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "All Services Started!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:"
Write-Host "  - PostgreSQL:     localhost:5432"
Write-Host "  - Kafka:          localhost:9092"
Write-Host "  - Kafka UI:       http://localhost:8080"
Write-Host "  - Backend API:    http://localhost:8000"
Write-Host "  - UI:             http://localhost:3000"
Write-Host "  - API Docs:       http://localhost:8000/docs"
Write-Host "  - Metrics:        http://localhost:8000/metrics"
Write-Host ""
Write-Host "Workers:"
Write-Host "  - Intake Worker:  http://localhost:9001/healthz"
Write-Host "  - Triage Worker:  http://localhost:9002/healthz"
Write-Host "  - Policy Worker:  http://localhost:9003/healthz"
Write-Host "  - Playbook Worker: http://localhost:9004/healthz"
Write-Host "  - Tool Worker:    http://localhost:9005/healthz"
Write-Host "  - Feedback Worker: http://localhost:9006/healthz"
Write-Host "  - SLA Monitor:    http://localhost:9007/healthz"
Write-Host ""
Write-Host "To view logs:"
Write-Host "  docker-compose logs -f [service_name]"
Write-Host ""
Write-Host "To stop all services:"
Write-Host "  .\scripts\stop-all.ps1"
Write-Host ""

