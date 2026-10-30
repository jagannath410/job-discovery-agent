@echo off
setlocal enabledelayedexpansion
title Daily Fresher Job Discovery Agent (2027 Batch)

:: Ensure we are in the script's directory
cd /d "%~dp0"

:: Check if virtual environment exists
if not exist "venv\Scripts\python.exe" (
    echo [!] Virtual environment not found. Creating venv...
    python -m venv venv
    call .\venv\Scripts\activate
    echo [*] Installing dependencies...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    pip install -e .
) else (
    call .\venv\Scripts\activate
)

:: If arguments were passed, forward them directly to main.py
if not "%~1"=="" (
    python main.py %*
    goto :end
)

:menu
cls
echo ============================================================
echo   DAILY FRESHER JOB DISCOVERY AGENT (2027 Batch - CS & Tech)
echo ============================================================
echo   1. Run Daily Job Discovery ^& Send Alerts (--once)
echo   2. Run Dry-Run Mode (Test discovery without Telegram alerts)
echo   3. Start Interactive Phone Listener (Respond to /latest, /search, /run)
echo   4. Run Automated Security ^& Vulnerability Audit (6/6 Checks)
echo   5. Check System Configuration ^& Diagnostics
echo   6. Show Database Statistics ^& Historical Runs
echo   7. Test Telegram Bot Connection
echo   8. Install Daily Auto-Run (Windows Task Scheduler at 8:30 AM)
echo   9. Run All Automated Pytest Tests (31 tests)
echo   10. Exit
echo ============================================================
set /p choice="Select an option (1-10): "

if "%choice%"=="1" (
    echo.
    echo [*] Running daily discovery cycle...
    python main.py --once
    pause
    goto menu
)
if "%choice%"=="2" (
    echo.
    echo [*] Running in dry-run mode...
    python main.py --dry-run
    pause
    goto menu
)
if "%choice%"=="3" (
    echo.
    echo [*] Starting interactive bot listener...
    python main.py --listen
    pause
    goto menu
)
if "%choice%"=="4" (
    echo.
    echo [*] Running full system security audit...
    python main.py --security-audit
    pause
    goto menu
)
if "%choice%"=="5" (
    echo.
    echo [*] Checking configuration...
    python main.py --check-config
    pause
    goto menu
)
if "%choice%"=="6" (
    echo.
    echo [*] Fetching database metrics...
    python main.py --show-stats
    pause
    goto menu
)
if "%choice%"=="7" (
    echo.
    echo [*] Dispatching Telegram test notification...
    python main.py --test-telegram
    pause
    goto menu
)
if "%choice%"=="8" (
    echo.
    echo [*] Installing Windows Task Scheduler daily job...
    powershell -ExecutionPolicy Bypass -File "scripts\setup_schedule.ps1"
    pause
    goto menu
)
if "%choice%"=="9" (
    echo.
    echo [*] Executing test suite...
    pytest -v
    pause
    goto menu
)
if "%choice%"=="10" goto :end

echo Invalid choice. Please choose 1 to 10.
timeout /t 2 >nul
goto menu

:end
echo Exiting.
