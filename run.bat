@echo off
setlocal enabledelayedexpansion
title Daily Fresher Job Discovery Agent

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
echo   DAILY FRESHER JOB DISCOVERY AGENT (2026 Batch)
echo ============================================================
echo   1. Run Daily Job Discovery ^& Send Alerts (--once)
echo   2. Run Dry-Run Mode (Test discovery without Telegram alerts)
echo   3. Check System Configuration ^& Diagnostics
echo   4. Show Database Statistics ^& Historical Runs
echo   5. Test Telegram Bot Connection
echo   6. Run All Automated Pytest Tests (27 tests)
echo   7. Exit
echo ============================================================
set /p choice="Select an option (1-7): "

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
    echo [*] Checking configuration...
    python main.py --check-config
    pause
    goto menu
)
if "%choice%"=="4" (
    echo.
    echo [*] Fetching database metrics...
    python main.py --show-stats
    pause
    goto menu
)
if "%choice%"=="5" (
    echo.
    echo [*] Dispatching Telegram test notification...
    python main.py --test-telegram
    pause
    goto menu
)
if "%choice%"=="6" (
    echo.
    echo [*] Executing test suite...
    python -m pytest -v
    pause
    goto menu
)
if "%choice%"=="7" goto :end

echo Invalid choice. Please choose 1 to 7.
timeout /t 2 >nul
goto menu

:end
echo Exiting.
