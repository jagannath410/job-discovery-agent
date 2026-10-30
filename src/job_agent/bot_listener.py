"""
Interactive Telegram Bot command listener for on-demand job queries from your phone.
Allows users to send commands (/latest, /search, /stats, /run) directly on Telegram.
"""

from __future__ import annotations

import html
import sys
import time
from datetime import datetime, timezone
import httpx

from src.job_agent.database import Database
from src.job_agent.logging_config import logger
from src.job_agent.notifications import TelegramNotifier
from src.job_agent.settings import settings


class TelegramBotListener:
    """Secure long-polling Telegram listener for authorized user commands."""

    def __init__(self, db: Database | None = None) -> None:
        self.db = db or Database(settings.database_path)
        self.notifier = TelegramNotifier(db=self.db)
        self.token = settings.telegram_bot_token
        self.authorized_chat_id = str(settings.telegram_chat_id).strip()
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def is_configured(self) -> bool:
        return bool(self.token and self.authorized_chat_id)

    def _send_reply(self, text: str) -> None:
        """Send an HTML-formatted message to the authorized chat ID."""
        try:
            httpx.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.authorized_chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=12.0,
            )
        except Exception as exc:
            logger.error(f"Failed to send bot reply: {exc}")

    def handle_command(self, cmd_text: str) -> None:
        """Parse and execute commands from the authorized user."""
        raw = cmd_text.strip()
        parts = raw.split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        logger.info(f"Received authorized command: {command}")

        if command in ("/start", "/help"):
            msg = (
                "👋 <b>Daily Fresher Job Discovery Bot (2027 Batch)</b>\n\n"
                "Here are the commands you can use anytime from your phone:\n\n"
                "📌 <b>/latest</b> - Get top 5 newest verified fresher & CS opportunities\n"
                "🔍 <b>/search &lt;keyword&gt;</b> - Search jobs (e.g. <code>/search python</code> or <code>/search intern</code>)\n"
                "📊 <b>/stats</b> - View verified listings & database statistics\n"
                "🚀 <b>/run</b> - Trigger a live job discovery run right now\n"
                "ℹ️ <b>/help</b> - Show this help menu"
            )
            self._send_reply(msg)

        elif command == "/latest":
            jobs = self.db.get_recent_verified_jobs(limit=5)
            if not jobs:
                self._send_reply("ℹ️ No verified jobs currently in the database. Send <b>/run</b> to discover fresh jobs!")
                return

            lines = ["🔥 <b>Top Verified Fresher & CS Opportunities:</b>\n"]
            for idx, j in enumerate(jobs, 1):
                safe_title = html.escape(j.title)
                safe_emp = html.escape(j.employer_name)
                safe_loc = html.escape(j.location)
                safe_url = html.escape(j.original_url)
                lines.append(
                    f"<b>{idx}. {safe_title}</b>\n"
                    f"🏢 {safe_emp} | 📍 {safe_loc}\n"
                    f"⭐ Match: {j.relevance_score}/100 | 🎓 Batch: 2027 eligible\n"
                    f"🔗 <a href=\"{safe_url}\">Direct Apply Link</a>\n"
                )
            self._send_reply("\n".join(lines))

        elif command == "/search":
            if not arg:
                self._send_reply("ℹ️ Please provide a keyword to search. Example: <code>/search python</code> or <code>/search intern</code>")
                return

            jobs = self.db.search_jobs(arg, limit=5)
            safe_query = html.escape(arg)
            if not jobs:
                self._send_reply(f"🔍 No verified opportunities found matching '<b>{safe_query}</b>'. Try another keyword like <code>python</code>, <code>software</code>, or <code>trainee</code>.")
                return

            lines = [f"🔍 <b>Results for '{safe_query}':</b>\n"]
            for idx, j in enumerate(jobs, 1):
                safe_title = html.escape(j.title)
                safe_emp = html.escape(j.employer_name)
                safe_loc = html.escape(j.location)
                safe_url = html.escape(j.original_url)
                lines.append(
                    f"<b>{idx}. {safe_title}</b>\n"
                    f"🏢 {safe_emp} | 📍 {safe_loc}\n"
                    f"⭐ Match: {j.relevance_score}/100\n"
                    f"🔗 <a href=\"{safe_url}\">Direct Apply Link</a>\n"
                )
            self._send_reply("\n".join(lines))

        elif command == "/stats":
            stats = self.db.get_summary_stats()
            batch = settings.target_graduation_batch
            msg = (
                "📊 <b>Daily Fresher Job Discovery - System Stats</b>\n\n"
                f"• <b>Target Batch:</b> {batch} (Allowed: {batch-2}–{batch+1})\n"
                f"• <b>Total Opportunities Stored:</b> {stats.get('total_jobs_stored', 0)}\n"
                f"• <b>Verified Active Fresher Jobs:</b> {stats.get('total_verified_active', 0)}\n"
                f"• <b>Alerts Delivered to Phone:</b> {stats.get('total_alerted', 0)}\n"
                f"• <b>Total Discovery Runs:</b> {stats.get('total_runs', 0)}\n\n"
                "<i>All listings are strictly verified with zero aggregator spam.</i>"
            )
            self._send_reply(msg)

        elif command == "/run":
            self._send_reply("🚀 <b>Job Discovery Initiated!</b>\nScanning verified Indian startup & tech feeds... You will receive matches in a moment.")
            try:
                from main import run_pipeline
                exit_code = run_pipeline(dry_run=False)
                if exit_code == 0:
                    self._send_reply("✅ <b>Discovery Complete!</b>\nNew verified opportunities have been processed and dispatched to your chat.")
                else:
                    self._send_reply("⚠️ <b>Discovery Completed with notices.</b> Check system logs for details.")
            except Exception as exc:
                logger.error(f"Error during on-demand run: {exc}", exc_info=True)
                self._send_reply(f"⚠️ Error executing discovery: {html.escape(str(exc))}")
        else:
            self._send_reply("❓ Unknown command. Send <b>/help</b> to view available commands.")

    def run_polling(self, poll_interval_seconds: int = 2) -> None:
        """Poll Telegram for incoming updates and respond securely."""
        if not self.is_configured():
            print("[!] ERROR: Bot token or Chat ID is missing in .env.")
            sys.exit(1)

        print("=" * 65)
        print("  TELEGRAM INTERACTIVE BOT LISTENER ACTIVE")
        print("=" * 65)
        print(f"[*] Authorized User ID: {self.authorized_chat_id}")
        print("[*] Listening for incoming commands from your phone...")
        print("[*] Try sending /latest, /search, /stats, or /run on Telegram.")
        print("[*] Press Ctrl+C to stop listening.")

        offset = 0
        with httpx.Client(timeout=25.0) as client:
            while True:
                try:
                    res = client.get(
                        f"{self.base_url}/getUpdates",
                        params={"offset": offset, "timeout": 20},
                    )
                    if res.status_code == 200:
                        data = res.json()
                        updates = data.get("result", [])
                        for update in updates:
                            offset = max(offset, update["update_id"] + 1)
                            msg = update.get("message")
                            if not msg:
                                continue

                            sender_id = str(msg.get("chat", {}).get("id", "")).strip()
                            text = msg.get("text", "").strip()

                            # STRICT SECURITY AUTHENTICATION: Only the authorized user can command the bot!
                            if sender_id != self.authorized_chat_id:
                                logger.warning(f"Security Alert: Blocked unauthorized message from sender {sender_id}")
                                continue

                            if text.startswith("/"):
                                self.handle_command(text)
                except httpx.RequestError as exc:
                    logger.debug(f"Network polling glitch: {exc}")
                    time.sleep(3)
                except KeyboardInterrupt:
                    print("\n[*] Stopping bot listener...")
                    break
                except Exception as exc:
                    logger.error(f"Unexpected error in polling loop: {exc}")
                    time.sleep(poll_interval_seconds)


if __name__ == "__main__":
    listener = TelegramBotListener()
    listener.run_polling()
