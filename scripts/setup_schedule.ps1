# Registers Windows Task Scheduler for Daily Fresher Job Discovery Agent
$ProjectDir = (Resolve-Path "$PSScriptRoot\..").Path
$BatPath = "$ProjectDir\run.bat"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  INSTALLING DAILY AUTOMATIC SCHEDULE (Windows Task Scheduler)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "[*] Script target: $BatPath"
Write-Host "[*] Scheduled time: Daily at 8:30 AM"
Write-Host "[*] Setting 'StartWhenAvailable': If PC is off at 8:30 AM, it runs when turned on."

try {
    $Action = New-ScheduledTaskAction -Execute $BatPath -Argument "--once" -WorkingDirectory $ProjectDir
    $Trigger = New-ScheduledTaskTrigger -Daily -At "08:30AM"
    $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    
    Register-ScheduledTask -TaskName "DailyFresherJobDiscoveryAgent" `
                           -Action $Action `
                           -Trigger $Trigger `
                           -Settings $Settings `
                           -Description "Autonomously discovers verified fresher jobs and sends Telegram alerts." `
                           -Force | Out-Null
                           
    Write-Host "`n[+] SUCCESS! Windows Task 'DailyFresherJobDiscoveryAgent' registered successfully!" -ForegroundColor Green
    Write-Host "[+] The agent will now run automatically every morning without manual triggering." -ForegroundColor Green
} catch {
    Write-Host "`n[!] Notice: PowerShell Task registration failed ($($_.Exception.Message))." -ForegroundColor Yellow
    Write-Host "[*] Falling back to schtasks.exe..."
    schtasks /create /tn "DailyFresherJobDiscoveryAgent" /tr "\"$BatPath\" --once" /sc daily /st 08:30 /f
}
