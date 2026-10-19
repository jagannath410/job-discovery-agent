"""
Standalone script to send a test alert to your Telegram bot.
Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from .env or environment variables.
"""

import sys
from pathlib import Path

# Add project root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.job_agent.notifications import TelegramNotifier
from src.job_agent.settings import settings


def main() -> None:
    print("=" * 60)
    print("TELEGRAM BOT CONNECTIVITY TEST")
    print("=" * 60)

    notifier = TelegramNotifier()
    if not notifier.is_configured():
        print("[!] ERROR: Telegram credentials missing.")
        print("    Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your .env file.")
        sys.exit(1)

    print(f"[*] Target Chat ID: {settings.telegram_chat_id}")
    print("[*] Sending test notification...")

    try:
        res = notifier.send_test_message()
        print("[+] SUCCESS! Telegram message dispatched.")
        print(f"    Message ID: {res.get('result', {}).get('message_id')}")
        print("    Please check your Telegram app to verify arrival!")
        sys.exit(0)
    except Exception as exc:
        print(f"[!] FAILED: Could not send Telegram message: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
