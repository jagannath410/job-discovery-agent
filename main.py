"""
Main entry point and CLI runner for Daily Fresher Job Discovery Agent.
Supports normal scheduled runs, dry-runs, configuration verification,
Telegram connection tests, and statistics inspection.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.job_agent.database import Database
from src.job_agent.deduplication import check_existing_url
from src.job_agent.discovery import DiscoveryEngine
from src.job_agent.logging_config import logger, setup_logging
from src.job_agent.models import (
    NotificationRecord,
    RunStats,
    VerificationStatus,
    VerifiedJob,
)
from src.job_agent.notifications import TelegramNotifier
from src.job_agent.scoring import score_job
from src.job_agent.settings import settings
from src.job_agent.verification import JobVerifier


def check_configuration() -> bool:
    """Validate current configuration, environment variables, and directories."""
    print("=" * 60)
    print("DAILY FRESHER JOB DISCOVERY AGENT - CONFIGURATION CHECK")
    print("=" * 60)

    all_good = True

    # 1. Check Python version
    py_ver = sys.version.split()[0]
    print(f"[*] Python Version: {py_ver} (>= 3.11 required) -> OK")

    # 2. Check Database path
    db_path = Path(settings.database_path)
    try:
        settings.ensure_data_directory()
        db = Database(db_path)
        print(f"[*] SQLite Database Path: {db_path.resolve()} -> Initialized & Connected OK")
    except Exception as exc:
        print(f"[!] SQLite Database Error: {exc}")
        all_good = False

    # 3. Check Telegram
    if settings.telegram_bot_token and settings.telegram_chat_id:
        token_masked = settings.telegram_bot_token[:6] + "..." + settings.telegram_bot_token[-4:]
        print(f"[*] Telegram Bot Token: {token_masked} -> Configured")
        print(f"[*] Telegram Chat ID: {settings.telegram_chat_id} -> Configured")
    else:
        print("[!] Telegram Credentials: Not configured. (Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env)")
        all_good = False

    # 4. Check Search Provider
    print(f"[*] Search Provider: '{settings.search_provider}'")
    if settings.search_provider == "google_custom_search":
        if not settings.search_api_key or not settings.search_engine_id:
            print("[!] Google Custom Search requires SEARCH_API_KEY and SEARCH_ENGINE_ID")
            all_good = False
        else:
            print("[*] Google Custom Search credentials present -> OK")
    elif settings.search_provider == "gemini":
        if not settings.gemini_api_key:
            print("[!] Gemini provider requires GEMINI_API_KEY")
            all_good = False
        else:
            print(f"[*] Gemini API Key present (model: {settings.gemini_model}) -> OK")
    elif settings.search_provider == "ats_direct":
        print("[*] Using ATS direct discovery (Greenhouse, Lever, Ashby, and priority employer portals) -> No API key needed")

    # 5. Candidate Profile
    prof = settings.get_candidate_profile()
    print(f"[*] Target Graduation Batch: {prof.graduation_batch} (Allowed: {prof.allowed_batches})")
    print(f"[*] Target Country: {prof.primary_country}")
    print(f"[*] Minimum Relevance Score Gate: {settings.min_relevance_score}/100")
    print("=" * 60)

    if all_good:
        print("RESULT: ALL CONFIGURATION CHECKS PASSED.")
    else:
        print("RESULT: SOME CONFIGURATION ITEMS REQUIRE ATTENTION (see above).")

    return all_good


def show_statistics(limit: int = 5) -> None:
    """Display execution history and statistics from SQLite database."""
    db = Database(settings.database_path)
    summary = db.get_summary_stats()

    print("\n" + "=" * 60)
    print("AGENT SYSTEM STATISTICS")
    print("=" * 60)
    print(f"Total Jobs Stored in Cache : {summary['total_jobs_stored']}")
    print(f"Total Verified Active Jobs : {summary['total_verified_active']}")
    print(f"Total Jobs Alerted to User : {summary['total_alerted']}")
    print(f"Total Execution Runs       : {summary['total_runs']}")
    print("-" * 60)
    print(f"Recent Runs (Last {limit}):")

    runs = db.get_recent_runs(limit)
    if not runs:
        print("  No previous execution runs recorded.")
    else:
        for r in runs:
            print(
                f"  [{r['started_at'][:19]}] Run ID: {r['id'][:16]} | "
                f"Status: {r['run_status']} | Discovered: {r['candidates_discovered']} | "
                f"Verified: {r['candidates_verified']} | Alerts Sent: {r['alerts_sent']}"
            )
    print("=" * 60 + "\n")


def run_pipeline(dry_run: bool = False) -> int:
    """
    Execute complete end-to-end autonomous discovery, verification, scoring,
    and alert dispatch cycle.
    """
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    started_at = datetime.now(timezone.utc).isoformat()
    logger.info(f"Starting job discovery run: {run_id} (dry_run={dry_run})")

    db = Database(settings.database_path)
    if not dry_run:
        db.record_run_start(run_id)

    profile = settings.get_candidate_profile()
    discovery_engine = DiscoveryEngine()
    verifier = JobVerifier(profile=profile)
    notifier = TelegramNotifier()

    # Step 1: Discovery
    raw_candidates, source_telemetry = discovery_engine.run_discovery()

    candidates_discovered = len(raw_candidates)
    candidates_verified = 0
    candidates_rejected = 0
    duplicates_count = 0
    new_jobs_count = 0
    verified_jobs_list: list[VerifiedJob] = []

    # Step 2: Verification and Scoring
    for raw_job in raw_candidates:
        # Check deduplication
        existing_in_db = db.get_job_by_url(raw_job.original_url)

        # Run verification checks
        verified_job = verifier.verify_job_posting(raw_job)

        # Score the job
        score, breakdown, explanation = score_job(verified_job, profile)
        verified_job.relevance_score = score
        verified_job.relevance_breakdown = breakdown
        verified_job.relevance_explanation = explanation

        # Save to database
        is_new, has_changed = db.save_job(verified_job)
        if is_new:
            new_jobs_count += 1
        else:
            duplicates_count += 1

        if verified_job.verification_status == VerificationStatus.VERIFIED_ACTIVE:
            candidates_verified += 1
            verified_jobs_list.append(verified_job)
        else:
            candidates_rejected += 1

    # Step 3: Fetch Unalerted High-Relevance Opportunities
    jobs_to_alert = db.get_unalerted_verified_jobs(
        min_score=settings.min_relevance_score,
        include_unconfirmed=settings.include_unconfirmed_alerts
    )

    logger.info(
        f"Processing completed: {candidates_discovered} discovered, {candidates_verified} verified active, "
        f"{candidates_rejected} rejected, {new_jobs_count} new entries, {duplicates_count} duplicates. "
        f"{len(jobs_to_alert)} job(s) pending alert dispatch (score >= {settings.min_relevance_score})."
    )

    # Step 4: Dispatch Telegram Alerts
    alerts_sent = 0
    alerts_failed = 0

    if notifier.is_configured() or dry_run:
        sent_chunks, failed_chunks, msg_ids = notifier.dispatch_report(
            jobs=jobs_to_alert,
            dry_run=dry_run
        )
        alerts_sent = sent_chunks
        alerts_failed = failed_chunks

        # If not dry run and delivery succeeded, mark alerted
        if not dry_run and alerts_failed == 0 and jobs_to_alert:
            now_iso = datetime.now(timezone.utc).isoformat()
            chat_hash = str(hash(settings.telegram_chat_id))
            for job in jobs_to_alert:
                db.mark_job_alerted(job.id, now_iso)
                rec = NotificationRecord(
                    id=f"notif_{uuid.uuid4().hex[:12]}",
                    job_id=job.id,
                    chat_id_hash_or_reference=chat_hash,
                    sent_at=now_iso,
                    telegram_message_id=msg_ids[0] if msg_ids else None,
                    delivery_status="DELIVERED",
                    retry_count=0
                )
                db.record_notification(rec)
    else:
        logger.warning(
            "Telegram is not configured. Alerts were not sent. "
            "(Configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env)"
        )

    # Step 5: Record Run Completion Telemetry
    completed_at = datetime.now(timezone.utc).isoformat()
    run_status = "SUCCESS" if alerts_failed == 0 else "PARTIAL_FAILURE"

    stats = RunStats(
        id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        run_status=run_status,
        sources_attempted=source_telemetry.get("sources_attempted", 0),
        candidates_discovered=candidates_discovered,
        candidates_verified=candidates_verified,
        candidates_rejected=candidates_rejected,
        new_jobs=new_jobs_count,
        duplicates=duplicates_count,
        alerts_sent=alerts_sent,
        alerts_failed=alerts_failed,
        error_summary="; ".join(f"{k}: {v}" for k, v in source_telemetry.get("errors", {}).items()) or None,
        details_by_source=source_telemetry.get("raw_counts_by_source", {})
    )

    if not dry_run:
        db.record_run_completion(stats)

    # Output structured summary
    print("\n" + "=" * 60)
    print("RUN EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Run ID                : {run_id}")
    print(f"Mode                  : {'DRY RUN' if dry_run else 'PRODUCTION RUN'}")
    print(f"Status                : {run_status}")
    print(f"Sources Attempted     : {stats.sources_attempted}")
    print(f"Candidates Discovered : {stats.candidates_discovered}")
    print(f"Candidates Verified   : {stats.candidates_verified}")
    print(f"Candidates Rejected   : {stats.candidates_rejected}")
    print(f"New Jobs Cached       : {stats.new_jobs}")
    print(f"Duplicate/Cached Jobs : {stats.duplicates}")
    print(f"Alerts Dispatched     : {stats.alerts_sent}")
    print(f"Alerts Failed         : {stats.alerts_failed}")
    print("=" * 60 + "\n")

    return 0 if run_status == "SUCCESS" else 2


def main() -> None:
    """CLI argument parsing and execution router."""
    parser = argparse.ArgumentParser(
        description="Daily Fresher Job Discovery Agent for 2026 Graduates"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Execute one full discovery, verification, and alert cycle, then exit."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover, verify, and score listings without sending Telegram messages or updating alert state."
    )
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="Explicitly send a test verification message to the configured Telegram chat."
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate environment settings, database connectivity, and exit."
    )
    parser.add_argument(
        "--show-stats",
        action="store_true",
        help="Display recent execution statistics and summary metrics from SQLite."
    )
    parser.add_argument(
        "--listen",
        action="store_true",
        help="Run interactive Telegram bot poller to listen for commands (/latest, /search, /stats, /run) from your phone."
    )
    parser.add_argument(
        "--security-audit",
        action="store_true",
        help="Execute automated security and vulnerability audit suite (SSRF, SQLi, Prompt Injection, Credential Isolation)."
    )

    args = parser.parse_args()

    # Route based on provided flags
    if args.check_config:
        success = check_configuration()
        sys.exit(0 if success else 1)

    if args.security_audit:
        from src.job_agent.security_audit import run_security_audit
        passed = run_security_audit()
        sys.exit(0 if passed else 1)

    if args.listen:
        from src.job_agent.bot_listener import TelegramBotListener
        listener = TelegramBotListener()
        listener.run_polling()
        sys.exit(0)

    if args.show_stats:
        show_statistics()
        sys.exit(0)

    if args.test_telegram:
        print("[*] Testing Telegram connectivity...")
        notifier = TelegramNotifier()
        if not notifier.is_configured():
            print("[!] Error: Telegram bot token or chat ID is not set in environment or .env file.")
            sys.exit(1)
        try:
            res = notifier.send_test_message()
            print(f"[+] Success! Test message sent to chat {settings.telegram_chat_id}. Response: {res}")
            sys.exit(0)
        except Exception as exc:
            print(f"[!] Telegram test failed: {exc}")
            sys.exit(1)

    # Default action: run pipeline (--once or standard invocation)
    exit_code = run_pipeline(dry_run=args.dry_run)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
