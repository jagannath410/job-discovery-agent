"""
SQLite database persistence, schema initialization, and transaction management.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from src.job_agent.logging_config import logger
from src.job_agent.models import (
    CareerTrack,
    EmploymentType,
    NotificationRecord,
    RunStats,
    VerificationStatus,
    VerifiedJob,
    WorkMode,
)

SCHEMA_VERSION = 1

INIT_SQL = """
-- Jobs table storing processed and verified opportunities
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    employer_name TEXT NOT NULL,
    title TEXT NOT NULL,
    normalized_url TEXT UNIQUE NOT NULL,
    original_url TEXT NOT NULL,
    source_domain TEXT NOT NULL,
    ats_provider TEXT,
    career_track TEXT NOT NULL,
    location TEXT NOT NULL,
    work_mode TEXT NOT NULL,
    employment_type TEXT NOT NULL,
    minimum_experience REAL,
    maximum_experience REAL,
    graduation_eligibility TEXT,  -- JSON list
    degree_eligibility TEXT,        -- JSON list
    publication_date TEXT,
    deadline TEXT,
    description_summary TEXT,
    matched_skills TEXT,          -- JSON list
    relevance_score INTEGER NOT NULL,
    relevance_breakdown TEXT,     -- JSON dict
    relevance_explanation TEXT,
    verification_status TEXT NOT NULL,
    verification_evidence TEXT,   -- JSON dict
    first_seen_at TEXT NOT NULL,
    last_checked_at TEXT NOT NULL,
    alerted_at TEXT,
    content_hash TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_normalized_url ON jobs(normalized_url);
CREATE INDEX IF NOT EXISTS idx_jobs_verification_status ON jobs(verification_status);
CREATE INDEX IF NOT EXISTS idx_jobs_alerted_at ON jobs(alerted_at);
CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(relevance_score);
CREATE INDEX IF NOT EXISTS idx_jobs_content_hash ON jobs(content_hash);

-- Execution runs tracking
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    run_status TEXT NOT NULL,
    sources_attempted INTEGER DEFAULT 0,
    candidates_discovered INTEGER DEFAULT 0,
    candidates_verified INTEGER DEFAULT 0,
    candidates_rejected INTEGER DEFAULT 0,
    new_jobs INTEGER DEFAULT 0,
    duplicates INTEGER DEFAULT 0,
    alerts_sent INTEGER DEFAULT 0,
    alerts_failed INTEGER DEFAULT 0,
    error_summary TEXT,
    details_by_source TEXT        -- JSON dict
);

-- Notifications delivery log
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    chat_id_hash_or_reference TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    telegram_message_id TEXT,
    delivery_status TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);

CREATE INDEX IF NOT EXISTS idx_notifications_job_id ON notifications(job_id);

-- Schema metadata table
CREATE TABLE IF NOT EXISTS schema_meta (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""


class Database:
    """SQLite wrapper handling schema setup, transactions, and CRUD operations."""

    def __init__(self, db_path: str | Path = "data/jobs_cache.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provide a transactional SQLite database connection with row factory enabled."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=15.0,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")  # Write-Ahead Logging for concurrency safety
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        """Initialize database tables and run lightweight migrations if needed."""
        with self.get_connection() as conn:
            conn.executescript(INIT_SQL)
            cur = conn.cursor()
            cur.execute("SELECT version FROM schema_meta ORDER BY version DESC LIMIT 1")
            row = cur.fetchone()
            if not row:
                cur.execute(
                    "INSERT INTO schema_meta (version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat())
                )

    def save_job(self, job: VerifiedJob) -> tuple[bool, bool]:
        """
        Insert or update a job posting.
        Returns:
            (is_new, has_changed)
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, content_hash, alerted_at FROM jobs WHERE normalized_url = ?", (job.normalized_url,))
            existing = cur.fetchone()

            if existing is None:
                # Insert brand new job
                cur.execute(
                    """
                    INSERT INTO jobs (
                        id, employer_name, title, normalized_url, original_url,
                        source_domain, ats_provider, career_track, location,
                        work_mode, employment_type, minimum_experience, maximum_experience,
                        graduation_eligibility, degree_eligibility, publication_date,
                        deadline, description_summary, matched_skills, relevance_score,
                        relevance_breakdown, relevance_explanation, verification_status,
                        verification_evidence, first_seen_at, last_checked_at,
                        alerted_at, content_hash
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        job.id,
                        job.employer_name,
                        job.title,
                        job.normalized_url,
                        job.original_url,
                        job.source_domain,
                        job.ats_provider,
                        job.career_track.value,
                        job.location,
                        job.work_mode.value,
                        job.employment_type.value,
                        job.minimum_experience_years,
                        job.maximum_experience_years,
                        json.dumps(job.graduation_eligibility),
                        json.dumps(job.degree_eligibility),
                        job.publication_date,
                        job.deadline,
                        job.description_summary,
                        json.dumps(job.matched_skills),
                        job.relevance_score,
                        json.dumps(job.relevance_breakdown),
                        job.relevance_explanation,
                        job.verification_status.value,
                        json.dumps(job.verification_evidence),
                        job.first_seen_at,
                        job.last_checked_at,
                        job.alerted_at,
                        job.content_hash,
                    )
                )
                return True, False
            else:
                # Existing job found
                has_changed = existing["content_hash"] != job.content_hash
                cur.execute(
                    """
                    UPDATE jobs SET
                        employer_name = ?,
                        title = ?,
                        ats_provider = ?,
                        career_track = ?,
                        location = ?,
                        work_mode = ?,
                        employment_type = ?,
                        minimum_experience = ?,
                        maximum_experience = ?,
                        graduation_eligibility = ?,
                        degree_eligibility = ?,
                        publication_date = COALESCE(?, publication_date),
                        deadline = COALESCE(?, deadline),
                        description_summary = ?,
                        matched_skills = ?,
                        relevance_score = ?,
                        relevance_breakdown = ?,
                        relevance_explanation = ?,
                        verification_status = ?,
                        verification_evidence = ?,
                        last_checked_at = ?,
                        content_hash = ?
                    WHERE normalized_url = ?
                    """,
                    (
                        job.employer_name,
                        job.title,
                        job.ats_provider,
                        job.career_track.value,
                        job.location,
                        job.work_mode.value,
                        job.employment_type.value,
                        job.minimum_experience_years,
                        job.maximum_experience_years,
                        json.dumps(job.graduation_eligibility),
                        json.dumps(job.degree_eligibility),
                        job.publication_date,
                        job.deadline,
                        job.description_summary,
                        json.dumps(job.matched_skills),
                        job.relevance_score,
                        json.dumps(job.relevance_breakdown),
                        job.relevance_explanation,
                        job.verification_status.value,
                        json.dumps(job.verification_evidence),
                        job.last_checked_at,
                        job.content_hash,
                        job.normalized_url,
                    )
                )
                return False, has_changed

    def get_job_by_url(self, normalized_url: str) -> VerifiedJob | None:
        """Retrieve a job by its normalized URL."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM jobs WHERE normalized_url = ?", (normalized_url,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_verified_job(row)

    def get_job_by_id(self, job_id: str) -> VerifiedJob | None:
        """Retrieve a job by its unique ID."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_verified_job(row)

    def get_unalerted_verified_jobs(
        self,
        min_score: int = 60,
        include_unconfirmed: bool = False
    ) -> list[VerifiedJob]:
        """Fetch active verified jobs that have not yet been sent to Telegram."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            allowed_statuses = [VerificationStatus.VERIFIED_ACTIVE.value]
            if include_unconfirmed:
                allowed_statuses.append(VerificationStatus.UNCONFIRMED.value)

            placeholders = ",".join("?" for _ in allowed_statuses)
            query = f"""
                SELECT * FROM jobs
                WHERE alerted_at IS NULL
                  AND verification_status IN ({placeholders})
                  AND relevance_score >= ?
                ORDER BY relevance_score DESC, publication_date DESC
            """
            cur.execute(query, (*allowed_statuses, min_score))
            rows = cur.fetchall()
            return [self._row_to_verified_job(r) for r in rows]

    def mark_job_alerted(self, job_id: str, timestamp_utc: str | None = None) -> None:
        """Mark a job as notified so it is not re-sent in future runs."""
        ts = timestamp_utc or datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute("UPDATE jobs SET alerted_at = ? WHERE id = ?", (ts, job_id))

    def record_run_start(self, run_id: str) -> None:
        """Record beginning of an agent discovery run."""
        started = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO runs (id, started_at, run_status) VALUES (?, ?, 'RUNNING')",
                (run_id, started)
            )

    def record_run_completion(self, stats: RunStats) -> None:
        """Record completed statistics for a run."""
        completed = stats.completed_at or datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE runs SET
                    completed_at = ?,
                    run_status = ?,
                    sources_attempted = ?,
                    candidates_discovered = ?,
                    candidates_verified = ?,
                    candidates_rejected = ?,
                    new_jobs = ?,
                    duplicates = ?,
                    alerts_sent = ?,
                    alerts_failed = ?,
                    error_summary = ?,
                    details_by_source = ?
                WHERE id = ?
                """,
                (
                    completed,
                    stats.run_status,
                    stats.sources_attempted,
                    stats.candidates_discovered,
                    stats.candidates_verified,
                    stats.candidates_rejected,
                    stats.new_jobs,
                    stats.duplicates,
                    stats.alerts_sent,
                    stats.alerts_failed,
                    stats.error_summary,
                    json.dumps(stats.details_by_source),
                    stats.id,
                )
            )

    def record_notification(self, rec: NotificationRecord) -> None:
        """Save a Telegram notification delivery attempt."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO notifications (
                    id, job_id, chat_id_hash_or_reference, sent_at,
                    telegram_message_id, delivery_status, retry_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec.id,
                    rec.job_id,
                    rec.chat_id_hash_or_reference,
                    rec.sent_at,
                    rec.telegram_message_id,
                    rec.delivery_status,
                    rec.retry_count,
                )
            )

    def get_recent_runs(self, limit: int = 5) -> list[dict[str, Any]]:
        """Retrieve recent run records for observability."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def get_summary_stats(self) -> dict[str, Any]:
        """Compute aggregate system statistics."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS total_jobs FROM jobs")
            total = cur.fetchone()["total_jobs"]

            cur.execute(
                "SELECT COUNT(*) AS verified_count FROM jobs WHERE verification_status = ?",
                (VerificationStatus.VERIFIED_ACTIVE.value,)
            )
            verified = cur.fetchone()["verified_count"]

            cur.execute(
                "SELECT COUNT(*) AS alerted_count FROM jobs WHERE alerted_at IS NOT NULL"
            )
            alerted = cur.fetchone()["alerted_count"]

            cur.execute("SELECT COUNT(*) AS total_runs FROM runs")
            runs = cur.fetchone()["total_runs"]

            return {
                "total_jobs_stored": total,
                "total_verified_active": verified,
                "total_alerted": alerted,
                "total_runs": runs,
            }

    @staticmethod
    def _row_to_verified_job(row: sqlite3.Row) -> VerifiedJob:
        """Convert a sqlite3.Row into a typed VerifiedJob instance."""
        return VerifiedJob(
            id=row["id"],
            employer_name=row["employer_name"],
            title=row["title"],
            normalized_url=row["normalized_url"],
            original_url=row["original_url"],
            source_domain=row["source_domain"],
            ats_provider=row["ats_provider"],
            career_track=CareerTrack(row["career_track"]),
            location=row["location"],
            work_mode=WorkMode(row["work_mode"]),
            employment_type=EmploymentType(row["employment_type"]),
            minimum_experience_years=row["minimum_experience"],
            maximum_experience_years=row["maximum_experience"],
            graduation_eligibility=json.loads(row["graduation_eligibility"] or "[]"),
            degree_eligibility=json.loads(row["degree_eligibility"] or "[]"),
            publication_date=row["publication_date"],
            deadline=row["deadline"],
            description_summary=row["description_summary"] or "",
            matched_skills=json.loads(row["matched_skills"] or "[]"),
            relevance_score=row["relevance_score"],
            relevance_breakdown=json.loads(row["relevance_breakdown"] or "{}"),
            relevance_explanation=row["relevance_explanation"] or "",
            verification_status=VerificationStatus(row["verification_status"]),
            verification_evidence=json.loads(row["verification_evidence"] or "{}"),
            first_seen_at=row["first_seen_at"],
            last_checked_at=row["last_checked_at"],
            alerted_at=row["alerted_at"],
            content_hash=row["content_hash"],
        )
