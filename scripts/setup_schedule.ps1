# Registers Windows Task Scheduler for Daily Fresher Job Discovery Agent
$ProjectDir = (Resolve-Path "$PSScriptRoot\..").Path
$VbsPath = "$ProjectDir\scripts\run_silent.vbs"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  INSTALLING DAILY AUTOMATIC SCHEDULE (Silent Background Mode)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "[*] Script target: $VbsPath"
Write-Host "[*] Scheduled time: Daily at 8:30 AM"
Write-Host "[*] Execution mode: 100% Invisible Background (Zero Popups)"
Write-Host "[*] Setting 'StartWhenAvailable': If PC is off at 8:30 AM, runs when turned on."

try {
    $Action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VbsPath`"" -WorkingDirectory $ProjectDir
    $Trigger = New-ScheduledTaskTrigger -Daily -At "08:30AM"
    $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    
    Register-ScheduledTask -TaskName "DailyFresherJobDiscoveryAgent" `
                           -Action $Action `
                           -Trigger $Trigger `
                           -Settings $Settings `
                           -Description "Autonomously discovers verified fresher jobs and sends Telegram alerts silently." `
                           -Force | Out-Null
                           
    Write-Host "`n[+] SUCCESS! Windows Task 'DailyFresherJobDiscoveryAgent' registered successfully!" -ForegroundColor Green
    Write-Host "[+] The agent will run 100% silently in the background every morning." -ForegroundColor Green
} catch {
    Write-Host "`n[!] Notice: PowerShell Task registration failed ($($_.Exception.Message))." -ForegroundColor Yellow
    Write-Host "[*] Falling back to schtasks.exe..."
    schtasks /create /tn "DailyFresherJobDiscoveryAgent" /tr "wscript.exe \"$VbsPath\"" /sc daily /st 08:30 /f
}
