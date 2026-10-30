# setup_github_cloud.ps1 - Helper to connect local repo to GitHub
param (
    [string]$RepoUrl = ""
)

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Daily Fresher Job Discovery Agent - GitHub Cloud Setup " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

if (-not $RepoUrl) {
    $RepoUrl = Read-Host "Enter your GitHub Repository URL (e.g. https://github.com/username/job-agent.git)"
}

if (-not $RepoUrl) {
    Write-Host "[!] No repository URL provided. Aborting." -ForegroundColor Red
    exit 1
}

# Verify git remote
$existingRemote = git remote get-url origin 2>$null
if ($existingRemote) {
    Write-Host "[*] Updating existing remote origin to: $RepoUrl" -ForegroundColor Yellow
    git remote set-url origin $RepoUrl
} else {
    Write-Host "[*] Adding remote origin: $RepoUrl" -ForegroundColor Green
    git remote add origin $RepoUrl
}

Write-Host "[*] Pushing branch 'main' to GitHub..." -ForegroundColor Green
git branch -M main
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[SUCCESS] Repository uploaded to GitHub Cloud successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "NEXT STEP on GitHub Website:" -ForegroundColor Yellow
    Write-Host "1. Go to your repo -> Settings -> Secrets and variables -> Actions" -ForegroundColor White
    Write-Host "2. Add Secrets:" -ForegroundColor White
    Write-Host "   - TELEGRAM_BOT_TOKEN : (Your bot token from .env)" -ForegroundColor Gray
    Write-Host "   - TELEGRAM_CHAT_ID   : (Your chat ID: 788849244)" -ForegroundColor Gray
    Write-Host "3. Go to Settings -> Actions -> General -> Workflow permissions -> Select 'Read and write permissions'" -ForegroundColor White
    Write-Host "4. Go to Actions tab -> Click 'Daily Fresher Job Discovery Agent' -> Click 'Run workflow'" -ForegroundColor White
} else {
    Write-Host "[!] Git push failed. Please make sure you are authenticated with GitHub." -ForegroundColor Red
}
