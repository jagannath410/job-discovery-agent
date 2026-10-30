# PowerShell Launcher for Daily Fresher Job Discovery Agent
[CmdletBinding()]
param(
    [string[]]$ForwardArgs
)

Set-Location $PSScriptRoot

# Activate virtual environment if present
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    & ".\venv\Scripts\Activate.ps1"
} else {
    Write-Host "[!] Virtual environment not found. Using system Python..." -ForegroundColor Yellow
}

if ($args.Count -gt 0) {
    & python main.py $args
    exit $LASTEXITCODE
}

function Show-Menu {
    Clear-Host
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  DAILY FRESHER JOB DISCOVERY AGENT (2027 Batch - CS & Tech)" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  1. Run Daily Job Discovery & Send Alerts (--once)"
    Write-Host "  2. Run Dry-Run Mode (Test discovery without alerts)"
    Write-Host "  3. Start Interactive Phone Listener (Respond to /latest, /search, /run)"
    Write-Host "  4. Run Automated Security & Vulnerability Audit (6/6 Checks)"
    Write-Host "  5. Check System Configuration & Diagnostics"
    Write-Host "  6. Show Database Statistics & Cached Jobs"
    Write-Host "  7. Test Telegram Bot Connection"
    Write-Host "  8. Install Daily Auto-Run (Windows Task Scheduler at 8:30 AM)"
    Write-Host "  9. Run Automated Tests (31 Pytest Tests)"
    Write-Host "  10. Exit"
    Write-Host "============================================================" -ForegroundColor Cyan
}

do {
    Show-Menu
    $choice = Read-Host "Select an option (1-10)"
    switch ($choice) {
        "1" {
            Write-Host "`n[*] Running daily discovery cycle..." -ForegroundColor Green
            python main.py --once
            Read-Host "Press Enter to continue..."
        }
        "2" {
            Write-Host "`n[*] Running in dry-run mode..." -ForegroundColor Green
            python main.py --dry-run
            Read-Host "Press Enter to continue..."
        }
        "3" {
            Write-Host "`n[*] Starting interactive bot listener..." -ForegroundColor Green
            python main.py --listen
            Read-Host "Press Enter to continue..."
        }
        "4" {
            Write-Host "`n[*] Executing system security audit..." -ForegroundColor Green
            python main.py --security-audit
            Read-Host "Press Enter to continue..."
        }
        "5" {
            Write-Host "`n[*] Checking configuration..." -ForegroundColor Green
            python main.py --check-config
            Read-Host "Press Enter to continue..."
        }
        "6" {
            Write-Host "`n[*] Fetching system statistics..." -ForegroundColor Green
            python main.py --show-stats
            Read-Host "Press Enter to continue..."
        }
        "7" {
            Write-Host "`n[*] Sending test notification..." -ForegroundColor Green
            python main.py --test-telegram
            Read-Host "Press Enter to continue..."
        }
        "8" {
            Write-Host "`n[*] Installing Windows Task Scheduler daily job..." -ForegroundColor Green
            & ".\scripts\setup_schedule.ps1"
            Read-Host "Press Enter to continue..."
        }
        "9" {
            Write-Host "`n[*] Executing automated test suite..." -ForegroundColor Green
            pytest -v
            Read-Host "Press Enter to continue..."
        }
        "10" {
            Write-Host "Exiting."
            break
        }
        default {
            Write-Host "Invalid option. Please choose 1-10." -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }
} while ($choice -ne "10")
