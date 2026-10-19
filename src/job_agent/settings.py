"""
Central configuration settings for the Daily Fresher Job Discovery Agent.
Reads environment variables, `.env` file, and provides strong typing with Pydantic.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.job_agent.models import CandidateProfile, CareerTrack


class ScoringWeights(BaseSettings):
    """Configurable weights for the relevance scoring engine (sum = 100)."""
    fresher_eligibility: int = 25
    role_track_match: int = 25
    technical_skills: int = 20
    graduation_batch_degree: int = 10
    publication_recency: int = 10
    location_work_mode: int = 5
    source_evidence_quality: int = 5


class Settings(BaseSettings):
    """Application-wide settings loaded from environment or .env file."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # 1. Telegram Notifications
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")

    # 2. Search & Discovery Provider
    search_provider: Literal["ats_direct", "google_custom_search", "gemini", "mock"] = Field(
        default="ats_direct",
        alias="SEARCH_PROVIDER"
    )
    search_api_key: str | None = Field(default=None, alias="SEARCH_API_KEY")
    search_engine_id: str | None = Field(default=None, alias="SEARCH_ENGINE_ID")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.8-flash", alias="GEMINI_MODEL")

    # 3. Storage and Cache
    database_path: str = Field(default="data/jobs_cache.db", alias="DATABASE_PATH")
    lookback_hours: int = Field(default=48, alias="LOOKBACK_HOURS")

    # 4. Filters & Delivery
    min_relevance_score: int = Field(default=60, alias="MIN_RELEVANCE_SCORE")
    send_empty_report: bool = Field(default=True, alias="SEND_EMPTY_REPORT")
    include_unconfirmed_alerts: bool = Field(default=False, alias="INCLUDE_UNCONFIRMED_ALERTS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # 5. Candidate Profile Customization
    target_graduation_batch: int = Field(default=2026, alias="TARGET_GRADUATION_BATCH")
    target_country: str = Field(default="India", alias="TARGET_COUNTRY")

    # 6. Scoring Weights
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)

    # Request limits & timeouts
    http_timeout_seconds: float = 12.0
    max_redirects: int = 5
    telegram_max_retries: int = 3

    def get_candidate_profile(self) -> CandidateProfile:
        """Construct the candidate profile reflecting user configuration."""
        profile = CandidateProfile(
            graduation_batch=self.target_graduation_batch,
            allowed_batches=[
                self.target_graduation_batch - 1,
                self.target_graduation_batch,
                self.target_graduation_batch + 1
            ],
            primary_country=self.target_country,
            target_tracks=[
                CareerTrack.AI_ML,
                CareerTrack.SOFTWARE_BACKEND,
                CareerTrack.MASS_HIRING
            ]
        )
        return profile

    def ensure_data_directory(self) -> Path:
        """Ensure the parent directory for the database exists."""
        db_path = Path(self.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path


# Global cached settings instance
settings = Settings()
