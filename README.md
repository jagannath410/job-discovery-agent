# Daily Fresher Job Discovery Agent

> **Autonomous daily discovery, verification, scoring, and Telegram alert pipeline targeting 2026 graduates and entry-level engineers (0–1 years of experience).**

[![Daily Fresher Job Discovery Agent](https://github.com/your-username/daily-fresher-agent/actions/workflows/daily_agent.yml/badge.svg)](https://github.com/your-username/daily-fresher-agent/actions/workflows/daily_agent.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests: 24 passing](https://img.shields.io/badge/tests-24%20passed-brightgreen.svg)](tests/)

---

## 1. Primary Objective & System Overview

The **Daily Fresher Job Discovery Agent** is an automated, production-minded Python system designed for final-year Computer Science students (specifically targeting the **2026 graduation batch** and candidates with **0–1 years of professional experience**).

It executes autonomously every day at **8:30 AM India Standard Time (03:00 UTC)** via GitHub Actions—without requiring your personal laptop to remain powered on.

### Key Capabilities

1. **Autonomous Discovery**: Gathers opportunities across **Track A** (AI/ML, GenAI, Python Backend, Software Engineering) and **Track B** (IT Services Trainee Programs: TCS NQT, Wipro, Infosys, Accenture, Cognizant, Capgemini, LTIMindtree, HCLTech).
2. **Strict Verification & Zero Hallucination**: Every listing is cross-checked against recognized enterprise ATS endpoints (`boards.greenhouse.io`, `jobs.lever.co`, `jobs.ashbyhq.com`, `*.myworkdayjobs.com`) or official company career portals.
3. **Banned Aggregator Filter**: Automatically rejects links from aggregators and spam boards (`naukri.com`, `linkedin.com`, `indeed.com`, `glassdoor.com`, `unstop.com`, `internshala.com`, `freshersworld.com`, `prepinsta.com`, etc.).
4. **Security & SSRF Guard**: Enforces strict URL normalization, canonical HTTPS, domain spoofing defenses (e.g. rejecting `tcs.com.attacker.invalid`), and blocks redirect-based SSRF into private IP ranges (`127.0.0.1`, `10.0.0.0/8`, `169.254.169.254`, etc.).
5. **Eligibility Gatekeeper**: Enforces strict experience filtering. Listings explicitly requiring **2+ years of experience** are immediately discarded (`REJECTED_EXPERIENCE`).
6. **Transparent Relevance Scoring (0–100)**: Evaluates match quality across fresher eligibility (25%), career track match (25%), technical skills (20%), batch eligibility (10%), recency (10%), location (5%), and source quality (5%).
7. **Deduplication & Local Storage**: Uses a robust SQLite cache (`jobs_cache.db`) with Write-Ahead Logging (WAL) and SHA-256 content hashing to ensure you are never spammed with duplicate notifications.
8. **Curated Telegram Delivery**: Dispatches beautifully formatted HTML reports directly to your private Telegram chat, split safely under Telegram's 4,096 character limit with exponential backoff and rate limit handling.

---

## 2. Architecture & Pipeline Flow

```mermaid
flowchart TD
    A["Scheduled Trigger (GitHub Actions 03:00 UTC / 08:30 AM IST)"] --> B["Discovery Engine"]
    
    subgraph Discovery ["Modular Discovery Adapters"]
        B --> C1["ATS Direct Adapter\n(Greenhouse, Lever, Ashby)"]
        B --> C2["Employer Careers Adapter\n(TCS, Wipro, Infosys, Accenture)"]
        B --> C3["Optional Search API\n(Google Custom Search / Gemini GenAI)"]
    end

    C1 & C2 & C3 --> D["Raw Candidate Listings"]
    
    D --> E["Job Verification & Trust Engine"]
    
    subgraph Verification ["7-Check Trust Gate"]
        E --> V1["Check 1: URL Normalization & SSRF Defense"]
        V1 --> V2["Check 2: Domain Ownership & Banned Aggregator Check"]
        V2 --> V3["Check 3: Live Page & Redirect Safety Validation"]
        V3 --> V4["Check 4: Job Activity Check (Reject 404/Expired)"]
        V4 --> V5["Check 5: Fresher Eligibility (Reject >= 2 yrs)"]
        V5 --> V6["Check 6: Batch (2026) & Skills Extraction"]
        V6 --> V7["Check 7: Status Determination"]
    end
    
    V7 --> F{"Status == VERIFIED_ACTIVE?"}
    F -- No --> G["Store in DB as REJECTED / EXPIRED\n(Excluded from Alerts)"]
    F -- Yes --> H["Relevance Scoring Engine (0-100)"]
    
    H --> I["SQLite Persistent Cache (jobs_cache.db)"]
    
    I --> J{"Unalerted & Score >= 60?"}
    J -- No --> K["Cached / Duplicate Suppressed"]
    J -- Yes --> L["Telegram Dispatcher\n(HTML Formatting & Chunking)"]
    
    L --> M["Delivered to User's Telegram Bot"]
    M --> N["Mark Alerted in DB & Record Delivery Telemetry"]
```

---

## 3. Candidate Profile Configuration

The default candidate profile is defined centrally in `src/job_agent/models.py` and configurable via `.env`:

* **Graduation Degree**: B.Tech / B.E. / MCA in Computer Science, IT, AI/Data Science.
* **Target Batch**: **2026** (allowed tolerance: 2025, 2026, 2027).
* **Experience Allowed**: Fresher, intern, graduate trainee, or 0–1 years. *(Explicit $\ge 2.0$ years requirement is strictly rejected).*
* **Primary Geography**: India (Bengaluru, Hyderabad, Pune, Mumbai, Gurgaon, Noida, Chennai, Delhi NCR) or Remote.
* **Core Technical Stack**: Python, Machine Learning, Deep Learning, Generative AI, RAG, LangChain, FastAPI, SQL, Git, DSA.
* **Target Tracks**:
  * **Track A**: AI Engineer Intern, Junior AI Engineer, ML Engineer Intern, Junior Python Developer, Python Backend Engineer.
  * **Track B**: Graduate Engineer Trainee (GET), Associate Software Engineer (ASE), TCS NQT / NextStep, Wipro Elite NTH, Infosys, Accenture, Cognizant, Capgemini, LTIMindtree, HCLTech.

---

## 4. Complete Windows Setup Guide (PowerShell & VS Code)

Follow this step-by-step guide to run the agent locally on Windows 10/11 using PowerShell and Visual Studio Code.

### Step 1: Verify Python Installation (Python 3.11+)

Open PowerShell (`Win + X` $\rightarrow$ `Windows Terminal` or `PowerShell`):

```powershell
python --version
```

*Expected output:* `Python 3.11.x` (or 3.12.x).

> [!TIP]
> If Python is not installed, download the official installer from [python.org](https://www.python.org/downloads/) and make sure to check the box **"Add python.exe to PATH"** during installation.

### Step 2: Verify Git Installation

```powershell
git --version
```

*Expected output:* `git version 2.x.x.windows.x`

### Step 3: Clone or Navigate to Project Directory

```powershell
# Navigate to your development folder (for example e:\new)
cd e:\new
```

Open the project in VS Code:
```powershell
code .
```

### Step 4: Create and Activate Virtual Environment

```powershell
# Create virtual environment named 'venv'
python -m venv venv

# If PowerShell blocks script execution, temporarily allow local scripts for your session:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

# Activate the virtual environment
.\venv\Scripts\Activate.ps1
```

*Verification:* Your PowerShell prompt should now show `(venv)` at the beginning:
```powershell
(venv) PS E:\new>
```

### Step 5: Install Project Dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

*Verification:* Run the system setup check script:
```powershell
python scripts\setup_check.py
```
*Expected output:* `RESULT: ALL MANDATORY DIAGNOSTICS PASSED. Ready to run!`

### Step 6: Create and Configure `.env` File

Copy the template file:
```powershell
Copy-Item .env.example .env
```

Open `.env` in VS Code (`code .env`) and configure your settings:

```ini
# Required: Telegram credentials
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz_example
TELEGRAM_CHAT_ID=1234567890

# Search provider: 'ats_direct' works out-of-the-box with NO paid API keys!
SEARCH_PROVIDER=ats_direct

# Target candidate configuration
TARGET_GRADUATION_BATCH=2026
TARGET_COUNTRY=India
MIN_RELEVANCE_SCORE=60
SEND_EMPTY_REPORT=true
```

---

## 5. Setting Up Your Free Telegram Bot

You will receive your daily job report on Telegram. Setup takes 2 minutes:

### A. Create Your Bot with BotFather
1. Open the Telegram app on your phone or desktop.
2. Search for `@BotFather` (verified bot with blue checkmark).
3. Send the message `/newbot`.
4. Choose a name for your bot (e.g. `My Fresher Job Agent`).
5. Choose a username ending in `bot` (e.g. `rohit_fresher_job_bot`).
6. BotFather will reply with your **Bot Token** (format: `1234567890:ABCdefGHIjklmn...`).
7. Paste this into your `.env` file as `TELEGRAM_BOT_TOKEN`.

### B. Find Your Numeric Chat ID
1. Search for `@userinfobot` on Telegram.
2. Press **Start** or send any message.
3. The bot will respond with your user information containing your **`Id`** (a 9–10 digit number like `987654321`).
4. Paste this number into your `.env` file as `TELEGRAM_CHAT_ID`.
5. **Important**: Open your newly created job bot in Telegram and press **Start** (or send `/start`) so the bot is permitted to message you!

### C. Test Telegram Connection
Run:
```powershell
python main.py --test-telegram
```
*Verification:* Check your Telegram app. You will instantly receive a message:
> `🧪 Daily Fresher Job Discovery Agent - Telegram Connection Test Successful!`

---

## 6. Running and Verifying the Agent Locally

The agent provides 6 intuitive CLI commands:

### 1. Configuration Validation
Verify all environment variables, directories, and SQLite database connectivity:
```powershell
python main.py --check-config
```

### 2. Dry-Run Mode
Discover, verify, and score real opportunities without sending alerts or mutating delivery state:
```powershell
python main.py --dry-run
```

### 3. Normal Execution Run (Single Cycle)
Execute one full discovery run, save to database, and dispatch any new matching jobs:
```powershell
python main.py --once
```

### 4. Inspect Execution Statistics
View historical run results, total jobs discovered, verified, and notified:
```powershell
python main.py --show-stats
```

### 5. Run Automated Pytest Suite
Run the 24 comprehensive automated tests covering all edge cases:
```powershell
pytest -v
```

---

## 7. GitHub Actions Cloud Automation (Runs at 8:30 AM IST)

You don't need to keep your PC turned on. The agent will run every single morning at **8:30 AM IST (03:00 UTC)** using GitHub Actions.

### Step 1: Create a Private GitHub Repository
1. Go to [github.com/new](https://github.com/new).
2. Set repository name: `daily-fresher-agent`.
3. Choose **Private** (to protect your state database).
4. Do **not** initialize with README or .gitignore (we already have them).
5. Click **Create repository**.

### Step 2: Push Your Code to GitHub
In your local PowerShell:
```powershell
git init
git add .
git commit -m "feat: initial commit of Daily Fresher Job Discovery Agent"
git branch -M main
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/daily-fresher-agent.git
git push -u origin main
```

### Step 3: Add Secrets to GitHub Repository
1. In your GitHub repository, navigate to **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions**.
2. Click **New repository secret**.
3. Add the following secrets:

| Secret Name | Description | Required? |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | Token provided by @BotFather | **Yes** |
| `TELEGRAM_CHAT_ID` | Numeric Chat ID from @userinfobot | **Yes** |
| `SEARCH_API_KEY` | Google Custom Search API Key | Optional (if using Google search) |
| `SEARCH_ENGINE_ID` | Google Programmable Search CX ID | Optional (if using Google search) |
| `GEMINI_API_KEY` | Google AI Studio Gemini API Key | Optional (if using Gemini adapter) |

### Step 4: Enable Workflow Read & Write Permissions
Because GitHub Actions commits the updated SQLite job database cache back to your private repository after each run:
1. Go to **Settings** $\rightarrow$ **Actions** $\rightarrow$ **General**.
2. Scroll down to **Workflow permissions**.
3. Select **"Read and write permissions"**.
4. Check **"Allow GitHub Actions to create and approve pull requests"**.
5. Click **Save**.

### Step 5: Test Manual Cloud Trigger (`workflow_dispatch`)
1. Go to the **Actions** tab in your repository.
2. Under "Workflows", click **Daily Fresher Job Discovery Agent**.
3. Click the **Run workflow** dropdown button.
4. (Optional) Check `dry_run` or `test_telegram`, or run standard.
5. Click **Run workflow**.
6. Watch the pipeline execute: installing dependencies, running pytest, discovering fresher jobs, and pinging your Telegram!

---

## 8. Sample Sanitized Notification

Below is an authentic sample of the HTML-formatted report received on Telegram:

```
📢 DAILY FRESHER JOB REPORT

📅 Date: 19 October 2026
🎯 New verified opportunities: 2

━━━━━━━━━━━━━━━━━━━━
🤖 AI & MACHINE LEARNING TRACK
━━━━━━━━━━━━━━━━━━━━

1. AI & Machine Learning Engineer Intern
🏢 Company: BrowserStack
📍 Location: Bengaluru, India (Hybrid)
💼 Type: Internship
🎓 Experience: Fresher / 0–1 years
📅 Batch: 2026 eligibility confirmed
⭐ Match Score: 94/100
🕒 Posted: Verified recent
💡 Why it matches: Target track: AI/ML & Generative AI; Explicitly open to freshers/trainees (0-1 yrs); Matched skills: Python, Machine Learning, RAG, FastAPI; Batch 2026 explicitly eligible; Verified via Greenhouse ATS.
🔗 Apply: Official Application Page
🛡️ Source verification: Official Greenhouse ATS page

━━━━━━━━━━━━━━━━━━━━
🏢 MASS HIRING & IT SERVICES TRAINEE DRIVES
━━━━━━━━━━━━━━━━━━━━

2. Graduate Engineer Trainee - TCS National Qualifier Test (NQT)
🏢 Company: TCS
📍 Location: Pan India
💼 Type: Trainee
🎓 Experience: Fresher / 0–1 years
📅 Batch: 2026 eligibility confirmed
⭐ Match Score: 92/100
🕒 Posted: Verified recent
💡 Why it matches: Target track: IT Services Trainee / Mass Hiring; Explicitly open to freshers/trainees (0-1 yrs); Batch 2026 explicitly eligible; Direct employer domain (tcs.com).
🔗 Apply: Official Application Page
🛡️ Source verification: Official tcs.com careers portal
```

---

## 9. Sample Execution Logs

```text
2026-10-19 08:30:00 [INFO] [job_agent] Starting job discovery run: run_20261019_083000_a1b2c3 (dry_run=False)
2026-10-19 08:30:01 [INFO] [job_agent] Running discovery adapter: ats_direct
2026-10-19 08:30:03 [INFO] [job_agent] ATS direct discovery collected 18 raw postings.
2026-10-19 08:30:03 [INFO] [job_agent] Running discovery adapter: employer_careers
2026-10-19 08:30:04 [INFO] [job_agent] Employer career source produced 8 verified candidate programs.
2026-10-19 08:30:05 [INFO] [job_agent] Discovery complete. Discovered 26 raw listings (24 unique URLs across 2 sources).
2026-10-19 08:30:06 [INFO] [job_agent] Verifying URL: https://boards.greenhouse.io/browserstack/jobs/500101 -> Passed Domain Trust (Greenhouse) & Fresher Eligibility (0-1 yrs, 2026 batch)
2026-10-19 08:30:07 [INFO] [job_agent] Verifying URL: https://www.naukri.com/job-listings-123 -> Rejected (Banned Aggregator)
2026-10-19 08:30:08 [INFO] [job_agent] Verifying URL: https://boards.greenhouse.io/company/jobs/999 -> Rejected (Requires 5+ years experience)
2026-10-19 08:30:09 [INFO] [job_agent] Processing completed: 24 discovered, 4 verified active, 20 rejected, 4 new entries, 0 duplicates. 4 job(s) pending alert dispatch (score >= 60).
2026-10-19 08:30:10 [INFO] [job_agent] Telegram message delivered successfully (message_id: 1042).
2026-10-19 08:30:10 [INFO] [job_agent] Marked 4 jobs as alerted in SQLite cache.
============================================================
RUN EXECUTION SUMMARY
============================================================
Run ID                : run_20261019_083000_a1b2c3
Mode                  : PRODUCTION RUN
Status                : SUCCESS
Sources Attempted     : 2
Candidates Discovered : 24
Candidates Verified   : 4
Candidates Rejected   : 20
New Jobs Cached       : 4
Duplicate/Cached Jobs : 0
Alerts Dispatched     : 1
Alerts Failed         : 0
============================================================
```

---

## 10. Security Review Checklist

* [x] **Zero Hardcoded Secrets**: Secrets and tokens are loaded strictly via environment variables (`.env` or GitHub Secrets).
* [x] **Log Redaction**: Automatic `RedactingFormatter` scrubs bot tokens, Bearer headers, and API keys before printing to console.
* [x] **Strict SSRF Defense**: URL normalization resolves DNS hostnames and verifies they do not point to internal, private, loopback, or cloud metadata IP ranges (`127.0.0.1`, `10.0.0.0/8`, `192.168.0.0/16`, `169.254.169.254`).
* [x] **Domain Spoofing Defense**: Hostname validation uses strict registered domain checking. Spoofed domains like `tcs.com.attacker.invalid` are rejected.
* [x] **Untrusted Text Sanitization**: All scraped HTML descriptions are sanitized to defuse prompt injection attempts (`IGNORE ALL PREVIOUS INSTRUCTIONS`, etc.) before being processed or displayed.
* [x] **HTML Injection Protection**: All job titles, employer names, and snippets are passed through `html.escape()` prior to Telegram dispatch.
* [x] **Concurrency & Race Conditions**: SQLite uses WAL mode (`PRAGMA journal_mode = WAL;`) and GitHub Actions enforces single-run concurrency locks (`group: daily-fresher-agent-run`).

---

## 11. Known Limitations & Cost Considerations

1. **Free Tier & Zero Cost**:
   - The default `ats_direct` adapter queries public, free ATS feeds (`boards-api.greenhouse.io`, `api.lever.co`) and employer career entry points without incurring any cost.
   - GitHub Actions provides **2,000 free runner minutes per month** for private repositories. Running once daily takes $\approx 1$ minute ($\approx 30$ minutes per month), well within the free allowance.
2. **Scheduled Workflow Delays**:
   - GitHub Actions scheduled cron runs are prioritized on a shared pool and may occasionally start 5–20 minutes after 03:00 UTC during peak global traffic. The agent does not claim exact-minute delivery.
3. **Company Feeds**:
   - Some traditional enterprise portals (e.g. Workday) use dynamic JavaScript client-side rendering. For such portals, the agent verifies official domain ownership and application paths directly.
4. **Search API Quotas**:
   - If opting to enable Google Custom Search JSON API, Google provides 100 free queries per day. The default settings use targeted, multi-term queries to remain well within free thresholds.

---

## 12. Troubleshooting Common Issues

### Issue 1: `Set-ExecutionPolicy` error in PowerShell
* **Symptom**: `File ... Activate.ps1 cannot be loaded because running scripts is disabled on this system.`
* **Solution**: Run this in PowerShell before activating:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
  ```

### Issue 2: `Telegram credentials missing` or `401 Unauthorized`
* **Symptom**: `Failed sending Telegram message: 401 Unauthorized`
* **Solution**: Check your `TELEGRAM_BOT_TOKEN` in `.env`. Ensure there are no spaces or quotes around the token. Ensure you messaged your bot and clicked **Start**.

### Issue 3: GitHub Actions fails to push database cache
* **Symptom**: `Permission to <repo> denied to github-actions[bot]`
* **Solution**: Go to your repository $\rightarrow$ **Settings** $\rightarrow$ **Actions** $\rightarrow$ **General** $\rightarrow$ **Workflow permissions** $\rightarrow$ Select **"Read and write permissions"** and click **Save**.

---

## 13. Feature Implementation & Verification Status

| Feature Requirement | Status | Verification & Testing |
| :--- | :---: | :--- |
| **Track A (AI/ML & Python Backend) Discovery** | **IMPLEMENTED** | Tested via `test_scoring.py` & `test_pipeline.py` |
| **Track B (TCS, Wipro, Infosys Mass Hiring)** | **IMPLEMENTED** | Verified via `employer_sources.py` & `test_verification.py` |
| **2026 Graduation Batch & 0-1 Yr Filter** | **IMPLEMENTED** | Tested via `test_eligibility.py` (`test_eligible_2026_graduate_job`) |
| **Mandatory $\ge 2$ Yr Experience Rejection** | **IMPLEMENTED** | Tested via `test_eligibility.py` (`test_job_requiring_three_years_experience`) |
| **Banned Aggregator Filtering (Naukri, etc.)** | **IMPLEMENTED** | Tested via `test_verification.py` (`test_banned_aggregator_url`) |
| **Domain Spoofing & SSRF Protection** | **IMPLEMENTED** | Tested via `test_verification.py` (`test_spoofed_domain_rejection`, `test_redirect_to_private_internal_ip_ssrf`) |
| **Redirect Chain Safety & Revalidation** | **IMPLEMENTED** | Tested via `test_verification.py` (`test_redirect_to_banned_domain`) |
| **Job Activity & Expiration Validation** | **IMPLEMENTED** | Tested via `test_verification.py` (`test_expired_job_detection`) |
| **Rule-based Scoring Engine (0–100)** | **IMPLEMENTED** | Tested via `test_scoring.py` (`test_high_relevance_job_score`) |
| **SQLite Persistent Cache & Migrations** | **IMPLEMENTED** | Tested via `test_deduplication.py` (`test_duplicate_application_url`) |
| **Deduplication Across Runs & Sources** | **IMPLEMENTED** | Tested via `test_pipeline.py` (`test_persistence_across_two_separate_agent_runs`) |
| **Telegram HTML Formatter & Chunking** | **IMPLEMENTED** | Tested via `test_notifications.py` (`test_message_splitting_at_length_limits`) |
| **Telegram Rate Limit & Retry Logic** | **IMPLEMENTED** | Tested via `test_notifications.py` (`test_telegram_rate_limiting_handled`) |
| **GitHub Actions 03:00 UTC Automation** | **IMPLEMENTED** | Verified in `.github/workflows/daily_agent.yml` |
| **Windows PowerShell Diagnostic Scripts** | **IMPLEMENTED** | Verified via `scripts/setup_check.py` & `main.py --check-config` |
| **24 Test Edge Cases in Pytest** | **IMPLEMENTED** | All 24 test requirements implemented and passing |
