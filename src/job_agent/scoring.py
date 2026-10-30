"""
Rule-based relevance scoring engine for job listings.
Produces a transparent 0-100 score, a detailed breakdown, and an explanation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.job_agent.eligibility import is_non_tech_role
from src.job_agent.models import (
    CandidateProfile,
    CareerTrack,
    EmploymentType,
    VerificationStatus,
    VerifiedJob,
    WorkMode,
)
from src.job_agent.settings import ScoringWeights, settings


def score_job(
    job: VerifiedJob,
    profile: CandidateProfile | None = None,
    weights: ScoringWeights | None = None
) -> tuple[int, dict[str, int], str]:
    """
    Score a verified job on a 0-100 scale using configurable weights.

    Returns:
        (total_score, breakdown_dict, explanation_string)
    """
    cand_profile = profile or settings.get_candidate_profile()
    scoring_w = weights or settings.scoring_weights

    # Mandatory gate: if job failed verification or was rejected, score must be 0
    if job.verification_status in (
        VerificationStatus.REJECTED_DOMAIN,
        VerificationStatus.REJECTED_EXPERIENCE,
        VerificationStatus.REJECTED_PROFILE,
        VerificationStatus.EXPIRED,
    ):
        return 0, {}, f"Verification failed ({job.verification_status.value}): {job.description_summary}"

    breakdown: dict[str, int] = {}
    explanation_parts: list[str] = []

    # 1. Fresher & Experience Eligibility (max: scoring_w.fresher_eligibility, default 25)
    w_exp = scoring_w.fresher_eligibility
    if job.employment_type in (EmploymentType.INTERNSHIP, EmploymentType.TRAINEE) or job.minimum_experience_years == 0.0:
        breakdown["fresher_eligibility"] = w_exp
        explanation_parts.append("Explicitly open to freshers/trainees (0-1 yrs)")
    elif job.minimum_experience_years is not None and job.minimum_experience_years <= 1.0:
        breakdown["fresher_eligibility"] = int(w_exp * 0.9)
        explanation_parts.append(f"Entry-level requirement ({job.minimum_experience_years:g} yrs)")
    elif job.minimum_experience_years is None:
        # Unknown experience requirement: neutral middle score
        breakdown["fresher_eligibility"] = int(w_exp * 0.6)
        explanation_parts.append("Experience requirement unspecified")
    else:
        breakdown["fresher_eligibility"] = 0
        explanation_parts.append("Experience requirement borderline")

    # 2. Role & Career Track Match (max: scoring_w.role_track_match, default 25)
    w_role = scoring_w.role_track_match
    if job.career_track == CareerTrack.AI_ML:
        breakdown["role_track_match"] = w_role
        explanation_parts.append("Target track: AI/ML & Generative AI")
    elif job.career_track == CareerTrack.MASS_HIRING:
        breakdown["role_track_match"] = w_role
        explanation_parts.append("Target track: IT Services Trainee / Mass Hiring")
    elif job.career_track == CareerTrack.SOFTWARE_BACKEND:
        breakdown["role_track_match"] = int(w_role * 0.95)
        explanation_parts.append("Target track: Software Engineering & Developer")
    else:
        if is_non_tech_role(job.title):
            breakdown["role_track_match"] = 0
            explanation_parts.append("Non-technical role")
        else:
            breakdown["role_track_match"] = int(w_role * 0.75)
            explanation_parts.append("General Tech & Engineering role")

    # 3. Technical Skills Alignment (max: scoring_w.technical_skills, default 20)
    w_skills = scoring_w.technical_skills
    matched_count = len(job.matched_skills)
    has_core_cs = any(s in job.matched_skills for s in ("Python", "Java", "C/C++", "SQL / Database", "DSA & Problem Solving", "JavaScript / Web", "OOP & Core CS", "Git"))
    has_ml = any(s in job.matched_skills for s in ("Machine Learning", "Deep Learning", "Generative AI", "LLM", "RAG"))

    skill_score = min(w_skills, matched_count * 5)
    if has_core_cs and skill_score < w_skills:
        skill_score = min(w_skills, skill_score + 3)
    if has_ml and skill_score < w_skills:
        skill_score = min(w_skills, skill_score + 2)

    breakdown["technical_skills"] = skill_score
    if job.matched_skills:
        explanation_parts.append(f"Matched skills: {', '.join(job.matched_skills[:4])}")

    # 4. Graduation Batch & Degree (max: scoring_w.graduation_batch_degree, default 10)
    w_batch = scoring_w.graduation_batch_degree
    if cand_profile.graduation_batch in job.graduation_eligibility:
        breakdown["graduation_batch_degree"] = w_batch
        explanation_parts.append(f"Batch {cand_profile.graduation_batch} explicitly eligible")
    elif any(b in cand_profile.allowed_batches for b in job.graduation_eligibility):
        breakdown["graduation_batch_degree"] = int(w_batch * 0.8)
        explanation_parts.append(f"Eligible batches: {job.graduation_eligibility}")
    elif job.degree_eligibility:
        breakdown["graduation_batch_degree"] = int(w_batch * 0.7)
        explanation_parts.append(f"Degree eligible: {', '.join(job.degree_eligibility[:2])}")
    else:
        breakdown["graduation_batch_degree"] = int(w_batch * 0.5)

    # 5. Publication Recency (max: scoring_w.publication_recency, default 10)
    w_recency = scoring_w.publication_recency
    # Default to modern recency if publication date is today/yesterday
    breakdown["publication_recency"] = int(w_recency * 0.8)
    if job.publication_date:
        try:
            pub_date = datetime.fromisoformat(job.publication_date.replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - pub_date).total_seconds() / 3600.0
            if age_hours <= 24:
                breakdown["publication_recency"] = w_recency
                explanation_parts.append("Published within 24h")
            elif age_hours <= 48:
                breakdown["publication_recency"] = int(w_recency * 0.8)
                explanation_parts.append("Published within 48h")
            else:
                breakdown["publication_recency"] = int(w_recency * 0.4)
        except (ValueError, TypeError):
            breakdown["publication_recency"] = int(w_recency * 0.7)

    # 6. Location & Work Mode (max: scoring_w.location_work_mode, default 5)
    w_loc = scoring_w.location_work_mode
    loc_lower = (job.location or "").lower()
    if job.work_mode == WorkMode.REMOTE or "remote" in loc_lower:
        breakdown["location_work_mode"] = w_loc
        explanation_parts.append("Remote friendly")
    elif any(city in loc_lower for city in ["india", "bengaluru", "bangalore", "hyderabad", "pune", "mumbai", "noida", "gurgaon", "chennai"]):
        breakdown["location_work_mode"] = w_loc
        explanation_parts.append("India location")
    else:
        breakdown["location_work_mode"] = int(w_loc * 0.6)

    # 7. Source & Evidence Quality (max: scoring_w.source_evidence_quality, default 5)
    w_source = scoring_w.source_evidence_quality
    if job.ats_provider:
        breakdown["source_evidence_quality"] = w_source
        explanation_parts.append(f"Verified via {job.ats_provider} ATS")
    elif job.source_domain:
        breakdown["source_evidence_quality"] = int(w_source * 0.8)
        explanation_parts.append(f"Direct employer domain ({job.source_domain})")
    else:
        breakdown["source_evidence_quality"] = int(w_source * 0.4)

    total_score = sum(breakdown.values())
    total_score = max(0, min(100, total_score))

    explanation = "; ".join(explanation_parts) + "."
    return total_score, breakdown, explanation
