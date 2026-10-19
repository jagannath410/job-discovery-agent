"""
Setup and health diagnostic script.
Checks Python version, installed packages, SQLite directory, and environment settings.
"""

import sys
import importlib
from pathlib import Path

# Add project root to sys.path so 'src' can be imported when running script directly
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

REQUIRED_MODULES = [
    ("pydantic", "Pydantic data validation"),
    ("httpx", "HTTP client"),
    ("bs4", "BeautifulSoup HTML parsing"),
    ("dotenv", "python-dotenv"),
]

OPTIONAL_MODULES = [
    ("google.genai", "Google GenAI SDK (Gemini)"),
    ("pytest", "Pytest testing framework"),
]


def run_checks() -> bool:
    print("=" * 60)
    print("DAILY FRESHER JOB DISCOVERY AGENT - SYSTEM DIAGNOSTICS")
    print("=" * 60)

    # 1. Python check
    v = sys.version_info
    print(f"[*] Python Version: {v.major}.{v.minor}.{v.micro} (Platform: {sys.platform})")
    if v.major < 3 or (v.major == 3 and v.minor < 11):
        print("[!] ERROR: Python 3.11+ is required.")
        return False
    print("    -> OK")

    # 2. Package imports
    print("\n[*] Checking required packages:")
    all_ok = True
    for mod_name, desc in REQUIRED_MODULES:
        try:
            importlib.import_module(mod_name)
            print(f"    [+] {mod_name} ({desc}): INSTALLED")
        except ImportError:
            print(f"    [!] {mod_name} ({desc}): MISSING. Run 'pip install -r requirements.txt'")
            all_ok = False

    print("\n[*] Checking optional packages:")
    for mod_name, desc in OPTIONAL_MODULES:
        try:
            importlib.import_module(mod_name)
            print(f"    [+] {mod_name} ({desc}): INSTALLED")
        except ImportError:
            print(f"    [-] {mod_name} ({desc}): Not installed (optional)")

    # 3. Import project modules
    print("\n[*] Checking project modules:")
    try:
        from src.job_agent.settings import settings
        from src.job_agent.database import Database
        from src.job_agent.verification import JobVerifier
        db = Database(settings.database_path)
        print("    [+] src.job_agent modules loaded successfully.")
    except Exception as exc:
        print(f"    [!] Error importing project modules: {exc}")
        all_ok = False

    print("=" * 60)
    if all_ok:
        print("RESULT: ALL MANDATORY DIAGNOSTICS PASSED. Ready to run!")
    else:
        print("RESULT: DIAGNOSTIC ERRORS FOUND. Please resolve issues above.")
    print("=" * 60)
    return all_ok


if __name__ == "__main__":
    success = run_checks()
    sys.exit(0 if success else 1)
