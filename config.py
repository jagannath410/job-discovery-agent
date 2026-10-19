"""
Top-level configuration module importing and exposing settings and candidate profiles.
"""

from src.job_agent.settings import Settings, ScoringWeights, settings
from src.job_agent.models import CandidateProfile, CareerTrack, WorkMode, EmploymentType

__all__ = [
    "Settings",
    "ScoringWeights",
    "settings",
    "CandidateProfile",
    "CareerTrack",
    "WorkMode",
    "EmploymentType",
]
