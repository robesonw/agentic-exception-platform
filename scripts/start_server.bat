@echo off
REM Startup script for Agentic Exception Processing Platform (Windows)
REM Starts the FastAPI development server with proper configuration

echo ==========================================
echo Agentic Exception Processing Platform
echo Starting Development Server
echo ==========================================
echo.

REM Check if virtual environment exists
if not exist ".venv" (
    echo Virtual environment not found. Creating...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Check if dependencies are installed
python -c "import fastapi" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Dependencies not installed. Installing...
    pip install -r requirements.txt
)

REM Create necessary directories
if not exist "runtime\logs" mkdir runtime\logs
if not exist "runtime\audit" mkdir runtime\audit
if not exist "runtime\approvals" mkdir runtime\approvals
if not exist "runtime\simulation" mkdir runtime\simulation
if not exist "runtime\domainpacks" mkdir runtime\domainpacks
if not exist "runtime\metrics" mkdir runtime\metrics

REM Check for .env file
if not exist ".env" (
    echo Warning: .env file not found. Using default configuration.
    echo Create .env file for custom configuration (see TECHNICAL_README.md)
    echo.
)

REM Set DATABASE_URL environment variable (matches docker-compose.yml)
set DATABASE_URL=postgresql+asyncpg://sentinai:sentinai@localhost:5432/sentinai

REM Start server
echo.
echo Starting FastAPI server on http://localhost:8000
echo API Documentation: http://localhost:8000/docs
echo Press Ctrl+C to stop
echo.

uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000 --log-level info

