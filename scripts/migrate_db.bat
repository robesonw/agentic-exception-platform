@echo off
REM Database migration helper script for Phase 6 (Windows)
REM Usage: scripts\migrate_db.bat [upgrade|downgrade|current|history]

setlocal

REM Check if .venv is activated
if "%VIRTUAL_ENV%"=="" (
    echo Warning: Virtual environment not activated. Activating .venv...
    if exist ".venv\Scripts\activate.bat" (
        call .venv\Scripts\activate.bat
    ) else (
        echo Error: .venv directory not found. Please create and activate virtual environment first.
        exit /b 1
    )
)

REM Check if DATABASE_URL is set
if "%DATABASE_URL%"=="" (
    echo Error: DATABASE_URL environment variable is not set.
    echo Please set it in your .env file or set it:
    echo   set DATABASE_URL=postgresql+asyncpg://user:password@host:port/database
    exit /b 1
)

set ACTION=%1
if "%ACTION%"=="" set ACTION=upgrade

if "%ACTION%"=="upgrade" (
    echo Running database migrations (upgrade to head)...
    alembic upgrade head
    echo Migrations completed successfully.
) else if "%ACTION%"=="downgrade" (
    set REVISION=%2
    if "%REVISION%"=="" set REVISION=-1
    echo Rolling back database migration (downgrade %REVISION%)...
    alembic downgrade %REVISION%
    echo Rollback completed successfully.
) else if "%ACTION%"=="current" (
    echo Current database revision:
    alembic current
) else if "%ACTION%"=="history" (
    echo Migration history:
    alembic history
) else (
    echo Usage: %0 [upgrade^|downgrade^|current^|history]
    echo.
    echo Commands:
    echo   upgrade          Upgrade to latest migration (default)
    echo   downgrade [rev]  Rollback migration (default: -1 for previous)
    echo   current          Show current database revision
    echo   history          Show migration history
    exit /b 1
)

endlocal

