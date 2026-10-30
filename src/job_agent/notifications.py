"""
Telegram notification formatter and dispatcher with retry logic, rate limit handling,
and HTML escaping.
"""

from __future__ import annotations

import html
import time
from datetime import datetime, timezone
from typing import Any
import httpx

from src.job_agent.logging_config import logger
from src.job_agent.models import (
    CareerTrack,
    NotificationRecord,
    VerifiedJob,
)
from src.job_agent.settings import settings

TELEGRAM_MAX_MESSAGE_LENGTH = 4096
SAFE_CHUNK_LENGTH = 3800


def escape_html(text: str | None) -> str:
    """Safely escape HTML entities to prevent malformed tags in Telegram."""
    if not text:
        return ""
    return html.escape(str(text))


def format_single_job(job: VerifiedJob, index: int) -> str:
    """Format an individual verified job into an attractive, structured HTML block."""
    emp = escape_html(job.employer_name)
    title = escape_html(job.title)
    loc = escape_html(job.location)
    emp_type = escape_html(job.employment_type.value.replace("_", " ").title())

    # Experience string
    if job.minimum_experience_years is not None:
        if job.minimum_experience_years == 0.0:
            exp_str = "Fresher / 0–1 years"
        else:
            exp_str = f"Min {job.minimum_experience_years:g} years"
    else:
        exp_str = "Fresher / Not specified"

    # Batch string
    if job.graduation_eligibility:
        batch_str = f"{', '.join(str(b) for b in job.graduation_eligibility)} eligibility confirmed"
    else:
        batch_str = "2026 / Fresher eligible"

    # Source & verification evidence
    if job.ats_provider:
        src_verif = f"Official {job.ats_provider} ATS page"
    elif job.source_domain:
        src_verif = f"Official {job.source_domain} careers portal"
    else:
        src_verif = "Verified application destination"

    # Posted date
    posted_str = escape_html(job.publication_date) if job.publication_date else "Verified recent"

    # Why it matches
    why = escape_html(job.relevance_explanation or "Matched career track and fresher profile.")

    url = job.normalized_url

    block = (
        f"<b>{index}. {title}</b>\n"
        f"🏢 <b>Company:</b> {emp}\n"
        f"📍 <b>Location:</b> {loc}\n"
        f"💼 <b>Type:</b> {emp_type}\n"
        f"🎓 <b>Experience:</b> {exp_str}\n"
        f"📅 <b>Batch:</b> {batch_str}\n"
        f"⭐ <b>Match Score:</b> {job.relevance_score}/100\n"
        f"🕒 <b>Posted:</b> {posted_str}\n"
        f"💡 <b>Why it matches:</b> {why}\n"
        f"🔗 <b>Apply:</b> <a href=\"{url}\">Official Application Page</a>\n"
        f"🛡️ <b>Source verification:</b> {src_verif}\n"
    )
    return block


def format_daily_report(jobs: list[VerifiedJob], date_str: str | None = None) -> list[str]:
    """
    Format the complete daily report grouped by track and split across messages
    if exceeding Telegram length limits.
    """
    date_display = date_str or datetime.now(timezone.utc).strftime("%d %B %Y")

    if not jobs:
        empty_msg = (
            f"📢 <b>DAILY FRESHER JOB REPORT</b>\n\n"
            f"📅 <b>Date:</b> {date_display}\n"
            f"🎯 <b>New verified opportunities:</b> 0\n\n"
            f"ℹ️ <i>No newly verified fresher jobs matching your profile today. "
            f"All discovered listings were verified against strict fresher eligibility and official career domains. "
            f"Next scheduled check: Tomorrow at 8:30 AM IST.</i>"
        )
        return [empty_msg]

    # Group jobs by track
    track_ai = [j for j in jobs if j.career_track == CareerTrack.AI_ML]
    track_backend = [j for j in jobs if j.career_track == CareerTrack.SOFTWARE_BACKEND]
    track_mass = [j for j in jobs if j.career_track == CareerTrack.MASS_HIRING]
    track_other = [j for j in jobs if j not in track_ai and j not in track_backend and j not in track_mass]

    header = (
        f"📢 <b>DAILY FRESHER JOB REPORT</b>\n\n"
        f"📅 <b>Date:</b> {date_display}\n"
        f"🎯 <b>New verified opportunities:</b> {len(jobs)}\n\n"
    )

    sections: list[tuple[str, list[VerifiedJob]]] = [
        ("🤖 <b>AI & MACHINE LEARNING TRACK</b>", track_ai),
        ("💻 <b>PYTHON BACKEND & SOFTWARE ENGINEERING</b>", track_backend),
        ("🏢 <b>MASS HIRING & IT SERVICES TRAINEE DRIVES</b>", track_mass),
        ("📌 <b>ADDITIONAL FRESHER OPPORTUNITIES</b>", track_other),
    ]

    messages: list[str] = []
    current_message = header
    global_index = 1

    for title, group_jobs in sections:
        if not group_jobs:
            continue

        section_header = f"━━━━━━━━━━━━━━━━━━━━\n{title}\n━━━━━━━━━━━━━━━━━━━━\n\n"
        if len(current_message) + len(section_header) > SAFE_CHUNK_LENGTH:
            messages.append(current_message.strip())
            current_message = section_header
        else:
            current_message += section_header

        for job in group_jobs:
            job_block = format_single_job(job, global_index) + "\n"
            global_index += 1

            if len(current_message) + len(job_block) > SAFE_CHUNK_LENGTH:
                messages.append(current_message.strip())
                current_message = job_block
            else:
                current_message += job_block

    if current_message.strip():
        messages.append(current_message.strip())

    return messages


class TelegramNotifier:
    """Telegram Bot API dispatcher with bounded backoff and rate limit handling."""

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
        client: httpx.Client | None = None
    ) -> None:
        self.bot_token = bot_token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_chat_id
        self.client = client or httpx.Client(timeout=15.0)

    def is_configured(self) -> bool:
        """Check if Telegram credentials are provided."""
        return bool(self.bot_token and self.chat_id)

    def send_raw_message(self, html_text: str) -> dict[str, Any]:
        """
        Send a single HTML message to the configured Telegram chat.
        Includes bounded exponential backoff for transient errors and respects HTTP 429 rate limits.
        """
        if not self.is_configured():
            raise ValueError("Telegram credentials missing (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID).")

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": html_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        retries = settings.telegram_max_retries
        for attempt in range(1, retries + 1):
            try:
                resp = self.client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    msg_id = str(data.get("result", {}).get("message_id", ""))
                    logger.info(f"Telegram message delivered successfully (message_id: {msg_id}).")
                    return data

                # Handle rate limiting (HTTP 429)
                if resp.status_code == 429:
                    retry_after = 2
                    try:
                        err_json = resp.json()
                        retry_after = err_json.get("parameters", {}).get("retry_after", 2)
                    except Exception:
                        pass
                    sleep_time = min(retry_after, 10)
                    logger.warning(f"Telegram rate limited (429). Retrying after {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue

                # Transient server errors (5xx)
                if resp.status_code >= 500:
                    backoff = attempt * 1.5
                    logger.warning(f"Telegram server error (HTTP {resp.status_code}). Backoff {backoff}s...")
                    time.sleep(backoff)
                    continue

                # Client error (4xx like 400 Bad Request, invalid chat ID, bad HTML)
                logger.error(f"Telegram API error {resp.status_code}: {resp.text}")
                resp.raise_for_status()

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == retries:
                    logger.error(f"Telegram dispatch failed after {retries} attempts: {exc}")
                    raise
                backoff = attempt * 1.5
                logger.warning(f"Network error sending Telegram message (attempt {attempt}/{retries}): {exc}. Backing off {backoff}s...")
                time.sleep(backoff)

        raise RuntimeError("Telegram message dispatch failed after exhausting retries.")

    def send_test_message(self) -> dict[str, Any]:
        """Send a lightweight test message to verify credentials and connectivity."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        test_msg = (
            f"🧪 <b>Daily Fresher Job Discovery Agent</b>\n\n"
            f"✅ <b>Telegram Connection Test Successful!</b>\n"
            f"🕒 <b>Timestamp:</b> {now_str}\n"
            f"🎯 <b>Target Profile:</b> {settings.target_graduation_batch} Graduates | CS & Tech | 0-1 yrs exp\n\n"
            f"The agent is properly configured to send daily alerts."
        )
        return self.send_raw_message(test_msg)

    def dispatch_report(
        self,
        jobs: list[VerifiedJob],
        dry_run: bool = False
    ) -> tuple[int, int, list[str]]:
        """
        Format and send daily notifications.
        Returns:
            (messages_sent, messages_failed, list_of_message_ids)
        """
        if not jobs and not settings.send_empty_report:
            logger.info("No jobs to alert and SEND_EMPTY_REPORT is false. Skipping dispatch.")
            return 0, 0, []

        messages = format_daily_report(jobs)
        sent_count = 0
        failed_count = 0
        msg_ids: list[str] = []

        if dry_run:
            logger.info(f"[DRY RUN] Would send {len(messages)} Telegram message(s):")
            for idx, msg in enumerate(messages, 1):
                logger.info(f"[DRY RUN Message {idx}/{len(messages)}]:\n{msg}\n")
            return len(messages), 0, ["mock_msg_dry_run"]

        for idx, msg in enumerate(messages, 1):
            try:
                result = self.send_raw_message(msg)
                msg_id = str(result.get("result", {}).get("message_id", ""))
                msg_ids.append(msg_id)
                sent_count += 1
            except Exception as exc:
                logger.error(f"Failed sending Telegram message chunk {idx}: {exc}")
                failed_count += 1

        return sent_count, failed_count, msg_ids
