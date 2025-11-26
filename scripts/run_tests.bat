@echo off
REM Test runner script for Windows with coverage reporting.
REM Generates coverage reports in terminal and HTML format.

echo Running tests with coverage...

REM Run tests with coverage
pytest --cov=src --cov-report=term-missing --cov-report=html --cov-report=xml -v

if %ERRORLEVEL% NEQ 0 (
    echo Tests failed!
    exit /b 1
)

echo.
echo Coverage report generated:
echo   - Terminal: shown above
echo   - HTML: htmlcov\index.html
echo   - XML: coverage.xml

echo.
echo Checking coverage threshold (85%%)...
python -m coverage report --fail-under=85
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Coverage is below 85%% threshold (Phase 2 requirement)
    exit /b 1
)

echo All tests passed and coverage threshold (85%%) met!

