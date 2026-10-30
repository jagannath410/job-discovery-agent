"""
Interactive helper to automatically discover your Telegram Chat ID and configure .env.
"""

import os
import re
import sys
import time
from pathlib import Path
import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"


def get_token_from_env() -> str:
    if not ENV_FILE.exists():
        return ""
    content = ENV_FILE.read_text(encoding="utf-8")
    match = re.search(r"^TELEGRAM_BOT_TOKEN\s*=\s*(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip().strip("\"'")
    return ""


def save_chat_id_to_env(chat_id: int | str) -> None:
    if not ENV_FILE.exists():
        return
    content = ENV_FILE.read_text(encoding="utf-8")
    new_content = re.sub(
        r"^TELEGRAM_CHAT_ID\s*=.*$",
        f"TELEGRAM_CHAT_ID={chat_id}",
        content,
        flags=re.MULTILINE,
    )
    ENV_FILE.write_text(new_content, encoding="utf-8")


def main() -> None:
    print("=" * 65)
    print("  TELEGRAM AUTO-CONNECT & CHAT ID DETECTION")
    print("=" * 65)

    token = get_token_from_env()
    if not token:
        print("[!] ERROR: TELEGRAM_BOT_TOKEN not found in .env file.")
        sys.exit(1)

    print("[*] Validating Bot Token with Telegram...")
    try:
        r = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15.0)
        data = r.json()
        if not data.get("ok"):
            print(f"[!] Invalid Token: {data.get('description')}")
            sys.exit(1)
        bot_info = data["result"]
        bot_username = bot_info.get("username", "your bot")
        print(f"[+] Bot Verified: @{bot_username} (ID: {bot_info.get('id')})")
    except Exception as exc:
        print(f"[!] Could not connect to Telegram: {exc}")
        sys.exit(1)

    print("\n" + "-" * 65)
    print("ACTION REQUIRED:")
    print(f"1. Open Telegram on your phone or PC.")
    print(f"2. Search for: @{bot_username}")
    print(f"3. Press 'START' (or send any message like 'hello') to the bot.")
    print("-" * 65)
    print("[*] Waiting for your message (timeout in 60s)... Press Ctrl+C to cancel.")

    start_time = time.time()
    detected_user = None

    while time.time() - start_time < 60:
        try:
            r = httpx.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=10.0)
            updates = r.json().get("result", [])
            for upd in updates:
                msg = upd.get("message") or upd.get("channel_post") or upd.get("callback_query", {}).get("message")
                if msg:
                    from_user = msg.get("from") or {}
                    if not from_user.get("is_bot", False):
                        detected_user = {
                            "chat_id": msg["chat"]["id"],
                            "name": from_user.get("first_name", "User"),
                            "username": from_user.get("username", ""),
                        }
                        break
            if detected_user:
                break
        except Exception:
            pass

        time.sleep(2)

    if not detected_user:
        print("\n[!] Timeout: No message received yet.")
        print(f"    Please ensure you sent a message to @{bot_username} and try again.")
        sys.exit(1)

    chat_id = detected_user["chat_id"]
    name = detected_user["name"]
    user_handle = f" (@{detected_user['username']})" if detected_user['username'] else ""

    print(f"\n[+] Detected message from: {name}{user_handle}!")
    print(f"[+] Your personal Chat ID is: {chat_id}")

    save_chat_id_to_env(chat_id)
    print(f"[+] Saved TELEGRAM_CHAT_ID={chat_id} to .env successfully.")

    # Send confirmation message
    print("[*] Sending welcome verification alert to your Telegram...")
    try:
        test_payload = {
            "chat_id": chat_id,
            "text": (
                "🎉 <b>Daily Fresher Job Discovery Agent Connected!</b>\n\n"
                "Hello " + name + "! Your Telegram chat is now successfully linked.\n"
                "You will receive verified fresher job alerts (0-1 yrs exp / 2026 batch) automatically.\n\n"
                "<i>No GATE exam score is required. Only real fresher tech opportunities are sent.</i>"
            ),
            "parse_mode": "HTML",
        }
        res = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage", json=test_payload, timeout=15.0)
        if res.status_code == 200:
            print("[+] Dispatched! Check your Telegram app right now.")
        else:
            print(f"[!] Telegram send returned: {res.text}")
    except Exception as exc:
        print(f"[!] Error sending test message: {exc}")

    print("=" * 65)
    print("SETUP COMPLETE! You are ready for automatic daily alerts.")
    print("=" * 65)


if __name__ == "__main__":
    main()
