"""
Job verification and trust engine.
Performs URL normalization, SSRF protection, domain trust verification,
job activity validation, and eligibility checks.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

from src.job_agent.eligibility import (
    detect_career_track,
    detect_employment_type,
    detect_work_mode,
    evaluate_fresher_eligibility,
    extract_degrees,
    extract_experience_requirements,
    extract_graduation_batches,
    extract_matched_skills,
    sanitize_job_text,
)
from src.job_agent.logging_config import logger
from src.job_agent.models import (
    CandidateProfile,
    CareerTrack,
    RawJobPosting,
    VerificationStatus,
    VerifiedJob,
)
from src.job_agent.settings import settings

# Banned job aggregator domains (including all subdomains)
BANNED_AGGREGATORS = {
    "linkedin.com",
    "indeed.com",
    "naukri.com",
    "glassdoor.com",
    "foundit.in",
    "unstop.com",
    "internshala.com",
    "freshersworld.com",
    "prepinsta.com",
    "monster.com",
    "timesjobs.com",
    "hirist.com",
}

# Recognized trusted ATS hostnames and parent domains
TRUSTED_ATS_DOMAINS = {
    "jobs.ashbyhq.com": "Ashby",
    "boards.greenhouse.io": "Greenhouse",
    "jobs.lever.co": "Lever",
    "myworkdayjobs.com": "Workday",
    "smartrecruiters.com": "SmartRecruiters",
    "icims.com": "iCIMS",
    "workable.com": "Workable",
}

# Recognized official employer domains (and their subdomains)
RECOGNIZED_EMPLOYER_DOMAINS = {
    "tcs.com": "TCS",
    "wipro.com": "Wipro",
    "cognizant.com": "Cognizant",
    "infosys.com": "Infosys",
    "accenture.com": "Accenture",
    "capgemini.com": "Capgemini",
    "ltimindtree.com": "LTIMindtree",
    "hcltech.com": "HCLTech",
    "google.com": "Google",
    "microsoft.com": "Microsoft",
    "amazon.jobs": "Amazon",
    "apple.com": "Apple",
    "meta.com": "Meta",
    "uber.com": "Uber",
    "swiggy.in": "Swiggy",
    "zeptonow.com": "Zepto",
    "razorpay.com": "Razorpay",
    "phonepe.com": "PhonePe",
    "browserstack.com": "BrowserStack",
    "postman.com": "Postman",
    "flipkart.com": "Flipkart",
    "zomato.com": "Zomato",
    "cred.club": "CRED",
}

# Tracking and analytics query parameters stripped during normalization
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "ref", "source", "ref_id", "sub_id", "mc_cid", "mc_eid",
    "trk", "spm", "source_id", "tracking_code", "sr_source", "campaign",
}

# Regex to detect indicators that a job has expired or closed in HTML/text
EXPIRED_INDICATORS = [
    re.compile(r"this\s+(position|job|posting|vacancy)\s+is\s+(no\s+longer|closed|expired)", re.IGNORECASE),
    re.compile(r"applications?\s+are\s+now\s+closed", re.IGNORECASE),
    re.compile(r"this\s+job\s+has\s+expired", re.IGNORECASE),
    re.compile(r"posting\s+removed", re.IGNORECASE),
    re.compile(r"job\s+is\s+closed\s+by\s+recruiter", re.IGNORECASE),
]


def is_ip_private_or_internal(ip_str: str) -> bool:
    """
    Check if an IP string is loopback, private, link-local, or unspecified.
    Does NOT flag RFC 6052 NAT64 global translation prefixes (64:ff9b::/96)
    which are globally routable.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified:
            return True
        if str(ip) in ("169.254.169.254", "0.0.0.0", "127.0.0.1", "::1"):
            return True
        return False
    except ValueError:
        return False


_DNS_SAFETY_CACHE: dict[str, bool] = {}


def is_hostname_safe(hostname: str) -> bool:
    """
    Validate that hostname is not an internal/private address or SSRF destination.
    Rejects localhost, local domains, and hostnames resolving to private IPs.
    Caches results to avoid repetitive DNS lookups across bulk job processing.
    """
    if not hostname:
        return False

    clean_host = hostname.strip().lower()
    if clean_host in _DNS_SAFETY_CACHE:
        return _DNS_SAFETY_CACHE[clean_host]

    # Reject localhost & common private internal domain suffixes
    if clean_host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        _DNS_SAFETY_CACHE[clean_host] = False
        return False
    if clean_host.endswith((".localhost", ".local", ".internal", ".test", ".invalid")):
        _DNS_SAFETY_CACHE[clean_host] = False
        return False

    # Check if host is an IP literal
    if is_ip_private_or_internal(clean_host):
        _DNS_SAFETY_CACHE[clean_host] = False
        return False

    # Try resolving hostname via DNS to ensure it does not resolve to an internal IP (SSRF guard)
    try:
        addr_info = socket.getaddrinfo(clean_host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _, _, _, _, sockaddr in addr_info:
            resolved_ip = sockaddr[0]
            if is_ip_private_or_internal(resolved_ip):
                _DNS_SAFETY_CACHE[clean_host] = False
                return False
    except (socket.gaierror, socket.herror, OSError):
        pass

    _DNS_SAFETY_CACHE[clean_host] = True
    return True


def normalize_job_url(raw_url: str, base_url: str | None = None) -> tuple[str | None, str | None]:
    """
    Safely normalize URL, removing tracking parameters, normalizing scheme & port.
    Returns:
        (normalized_url, error_message)
    """
    if not raw_url:
        return None, "Empty URL"

    try:
        # Resolve relative URLs against base
        full_url = urljoin(base_url or "", raw_url.strip())
        parsed = urlsplit(full_url)

        # Accept only HTTP and HTTPS
        if parsed.scheme.lower() not in ("http", "https"):
            return None, f"Unsupported URL scheme: {parsed.scheme}"

        hostname = parsed.hostname
        if not hostname:
            return None, "Missing hostname in URL"

        hostname = hostname.lower()

        # Reject credentials in URL (user:pass@host)
        if parsed.username or parsed.password:
            return None, "URLs containing embedded user credentials are rejected"

        # Validate hostname safety (SSRF)
        if not is_hostname_safe(hostname):
            return None, f"Host rejected by SSRF guard: {hostname}"

        # Strip default ports
        netloc = hostname
        if parsed.port and parsed.port not in (80, 443):
            netloc = f"{hostname}:{parsed.port}"

        # Filter out tracking query parameters while preserving job identifiers
        clean_query_params = []
        if parsed.query:
            for key, val in parse_qsl(parsed.query, keep_blank_values=False):
                if key.lower() not in TRACKING_PARAMS:
                    clean_query_params.append((key, val))

        new_query = urlencode(clean_query_params)
        # Strip trailing slashes on path for consistency, unless path is empty
        path = parsed.path
        if path.endswith("/") and len(path) > 1:
            path = path.rstrip("/")

        # Prefer HTTPS
        normalized = urlunsplit(("https", netloc, path, new_query, ""))
        return normalized, None

    except Exception as exc:
        return None, f"Malformed URL: {exc}"


def check_domain_trust(hostname: str) -> tuple[bool, str, str | None, str]:
    """
    Verify whether the domain belongs to a banned aggregator, a recognized ATS,
    an official employer career domain, or an untrusted third party.

    Returns:
        (is_allowed, category, provider_or_employer, reason)
    """
    clean_host = hostname.strip().lower()

    # 1. Banned Aggregator Check (exact match or subdomain)
    for banned in BANNED_AGGREGATORS:
        if clean_host == banned or clean_host.endswith("." + banned):
            return (
                False,
                "BANNED_AGGREGATOR",
                None,
                f"Domain '{clean_host}' is a banned job aggregator ({banned})"
            )

    # 2. Trusted ATS Domain Check
    for ats_domain, ats_name in TRUSTED_ATS_DOMAINS.items():
        if clean_host == ats_domain or clean_host.endswith("." + ats_domain):
            return (
                True,
                "TRUSTED_ATS",
                ats_name,
                f"Verified enterprise ATS: {ats_name} ({clean_host})"
            )

    # 3. Recognized Employer Domain Check
    for employer_domain, employer_name in RECOGNIZED_EMPLOYER_DOMAINS.items():
        if clean_host == employer_domain or clean_host.endswith("." + employer_domain):
            return (
                True,
                "OFFICIAL_EMPLOYER",
                employer_name,
                f"Official employer domain: {employer_name} ({clean_host})"
            )

    return (
        False,
        "UNVERIFIED_DOMAIN",
        None,
        f"Domain '{clean_host}' is not a recognized employer or trusted ATS"
    )


class JobVerifier:
    """Verification engine implementing deep safety and legitimacy checks."""

    def __init__(
        self,
        profile: CandidateProfile | None = None,
        http_client: httpx.Client | None = None
    ) -> None:
        self.profile = profile or settings.get_candidate_profile()
        self.client = http_client or httpx.Client(
            timeout=settings.http_timeout_seconds,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36 JobDiscoveryBot/1.0"
                ),
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            },
            follow_redirects=False  # Handled manually to inspect redirect chain
        )

    def verify_job_posting(self, raw_job: RawJobPosting) -> VerifiedJob:
        """
        Run the complete 7-check verification pipeline for a raw job posting.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        evidence: dict[str, Any] = {
            "source_adapter": raw_job.source_adapter,
            "original_url": raw_job.original_url,
            "verification_timestamp": now_utc,
            "checks_passed": [],
            "rejection_reasons": [],
        }

        # -------------------------------------------------------------
        # Check 1: URL Normalization
        # -------------------------------------------------------------
        norm_url, norm_err = normalize_job_url(raw_job.original_url)
        if not norm_url:
            evidence["rejection_reasons"].append(f"URL Normalization Failed: {norm_err}")
            return self._build_rejected_job(
                raw_job,
                raw_job.original_url,
                "unknown",
                VerificationStatus.REJECTED_DOMAIN,
                evidence,
                "Malformed or unsafe URL."
            )

        evidence["normalized_url"] = norm_url
        evidence["checks_passed"].append("URL_NORMALIZATION")
        parsed_url = urlsplit(norm_url)
        source_domain = parsed_url.hostname or ""

        # -------------------------------------------------------------
        # Check 2: Domain Ownership and Trust
        # -------------------------------------------------------------
        is_allowed, domain_cat, ats_or_emp, domain_reason = check_domain_trust(source_domain)
        evidence["domain_category"] = domain_cat
        evidence["domain_trust_reason"] = domain_reason

        if not is_allowed:
            evidence["rejection_reasons"].append(f"Domain rejected: {domain_reason}")
            return self._build_rejected_job(
                raw_job,
                norm_url,
                source_domain,
                VerificationStatus.REJECTED_DOMAIN,
                evidence,
                domain_reason
            )

        evidence["checks_passed"].append("DOMAIN_TRUST")
        ats_provider = ats_or_emp if domain_cat == "TRUSTED_ATS" else None

        # -------------------------------------------------------------
        # Fast Pre-Filter: Check if title explicitly indicates senior/lead role
        # -------------------------------------------------------------
        lower_title = raw_job.title.lower()
        senior_indicators = [
            r"\bsenior\b", r"\bsr\.?\b", r"\blead\b", r"\bprincipal\b", r"\bstaff\b",
            r"\barchitect\b", r"\bdirector\b", r"\bmanager\b", r"\bvp\b", r"\bvice president\b",
            r"\bhead of\b", r"\b5\+\s*years?\b", r"\b4\+\s*years?\b", r"\b3\+\s*years?\b"
        ]
        has_fresher_term = any(t in lower_title for t in ("intern", "fresher", "trainee", "entry", "graduate", "0-1", "junior", "ase", "get"))
        if not has_fresher_term and any(re.search(pat, lower_title) for pat in senior_indicators):
            evidence["rejection_reasons"].append(f"Title indicates senior role: '{raw_job.title}'")
            return self._build_rejected_job(
                raw_job,
                norm_url,
                source_domain,
                VerificationStatus.REJECTED_EXPERIENCE,
                evidence,
                f"Senior role: {raw_job.title}"
            )

        # -------------------------------------------------------------
        # Check 3 & 4: Live Activity & Redirect Safety Validation
        # -------------------------------------------------------------
        # If posting is from a verified direct ATS API (Greenhouse, Lever, Ashby),
        # validate host safety without redundant slow HTTP re-fetching:
        if domain_cat == "TRUSTED_ATS" and raw_job.source_adapter in ("greenhouse_api", "lever_api", "ashby_api"):
            final_url = norm_url
            active_status = VerificationStatus.VERIFIED_ACTIVE
            page_content = raw_job.description or ""
            evidence["checks_passed"].append("DIRECT_ATS_API_VERIFIED")
        else:
            final_url, active_status, page_content, fetch_evidence = self._check_activity_and_redirects(norm_url)
            evidence.update(fetch_evidence)

        if active_status == VerificationStatus.EXPIRED:
            evidence["rejection_reasons"].append("Job page reported closed or expired.")
            return self._build_rejected_job(
                raw_job,
                final_url,
                source_domain,
                VerificationStatus.EXPIRED,
                evidence,
                "Job has expired or is no longer accepting applications."
            )
        elif active_status == VerificationStatus.REJECTED_DOMAIN:
            evidence["rejection_reasons"].append("Redirected to banned or unsafe domain.")
            return self._build_rejected_job(
                raw_job,
                final_url,
                source_domain,
                VerificationStatus.REJECTED_DOMAIN,
                evidence,
                "Redirect destination was banned or unsafe."
            )

        # -------------------------------------------------------------
        # Check 5: Fresher Eligibility & Experience Extraction
        # -------------------------------------------------------------
        combined_text = f"{raw_job.title}\n{raw_job.description}\n{page_content}"
        is_eligible, elig_reason, min_exp, batches, skills = evaluate_fresher_eligibility(
            raw_job.title,
            combined_text,
            self.profile
        )

        evidence["eligibility_reason"] = elig_reason
        evidence["detected_min_experience"] = min_exp
        evidence["detected_batches"] = batches
        evidence["matched_skills"] = skills

        if not is_eligible:
            evidence["rejection_reasons"].append(f"Eligibility rejected: {elig_reason}")
            status = VerificationStatus.REJECTED_EXPERIENCE if (min_exp is not None and min_exp >= 2.0) else VerificationStatus.REJECTED_PROFILE
            return self._build_rejected_job(
                raw_job,
                final_url,
                source_domain,
                status,
                evidence,
                elig_reason
            )

        evidence["checks_passed"].append("FRESHER_ELIGIBILITY")

        # -------------------------------------------------------------
        # Check 6 & 7: Categorization, Recency & Final Verified Active Status
        # -------------------------------------------------------------
        career_track = detect_career_track(raw_job.title, combined_text)
        work_mode = detect_work_mode(combined_text)
        employment_type = detect_employment_type(raw_job.title + " " + combined_text)
        degrees = extract_degrees(combined_text)

        final_status = (
            VerificationStatus.VERIFIED_ACTIVE
            if active_status == VerificationStatus.VERIFIED_ACTIVE
            else VerificationStatus.UNCONFIRMED
        )

        from src.job_agent.deduplication import compute_content_hash, compute_job_id

        stable_id = compute_job_id(raw_job.employer_name, final_url)
        content_hash = compute_content_hash(
            raw_job.title,
            raw_job.employer_name,
            raw_job.description or page_content,
            raw_job.location or "Unknown",
            str(min_exp)
        )

        return VerifiedJob(
            id=stable_id,
            employer_name=raw_job.employer_name,
            title=raw_job.title,
            normalized_url=final_url,
            original_url=raw_job.original_url,
            source_domain=source_domain,
            ats_provider=ats_provider,
            career_track=career_track,
            location=raw_job.location or "India (Flexible)",
            work_mode=work_mode,
            employment_type=employment_type,
            minimum_experience_years=min_exp,
            graduation_eligibility=batches,
            degree_eligibility=degrees,
            publication_date=raw_job.publication_date or now_utc[:10],
            deadline=None,
            description_summary=sanitize_job_text(raw_job.description or page_content)[:600],
            matched_skills=skills,
            verification_status=final_status,
            verification_evidence=evidence,
            first_seen_at=now_utc,
            last_checked_at=now_utc,
            content_hash=content_hash,
        )

    def _check_activity_and_redirects(
        self,
        url: str
    ) -> tuple[str, VerificationStatus, str, dict[str, Any]]:
        """
        Validate live accessibility and follow redirects with SSRF & domain checks.
        Returns:
            (final_url, status, page_text_snippet, evidence_dict)
        """
        current_url = url
        evidence: dict[str, Any] = {"redirect_chain": []}

        for hop in range(settings.max_redirects):
            parsed = urlsplit(current_url)
            hostname = parsed.hostname or ""

            # Check SSRF on each hop
            if not is_hostname_safe(hostname):
                evidence["redirect_chain"].append({
                    "hop": hop,
                    "url": current_url,
                    "error": f"SSRF violation on host {hostname}"
                })
                return current_url, VerificationStatus.REJECTED_DOMAIN, "", evidence

            # Check domain trust on each hop
            is_allowed, cat, _, reason = check_domain_trust(hostname)
            if not is_allowed:
                evidence["redirect_chain"].append({
                    "hop": hop,
                    "url": current_url,
                    "error": f"Banned or unverified domain in redirect: {reason}"
                })
                return current_url, VerificationStatus.REJECTED_DOMAIN, "", evidence

            try:
                resp = self.client.get(current_url, timeout=settings.http_timeout_seconds)
                evidence["redirect_chain"].append({
                    "hop": hop,
                    "url": current_url,
                    "status_code": resp.status_code
                })

                # Handle redirect responses
                if resp.is_redirect or resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location")
                    if not location:
                        break
                    next_url, err = normalize_job_url(location, base_url=current_url)
                    if not next_url:
                        return current_url, VerificationStatus.REJECTED_DOMAIN, "", evidence
                    current_url = next_url
                    continue

                # Handle standard responses
                if resp.status_code in (404, 410):
                    return current_url, VerificationStatus.EXPIRED, "", evidence
                elif resp.status_code >= 400:
                    return current_url, VerificationStatus.UNCONFIRMED, "", evidence

                # Content examination
                text_content = resp.text
                for pattern in EXPIRED_INDICATORS:
                    if pattern.search(text_content):
                        return current_url, VerificationStatus.EXPIRED, text_content[:500], evidence

                return current_url, VerificationStatus.VERIFIED_ACTIVE, text_content[:2000], evidence

            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException):
                evidence["fetch_error"] = "HTTP timeout during verification"
                return current_url, VerificationStatus.UNCONFIRMED, "", evidence
            except (httpx.ConnectError, httpx.RequestError) as exc:
                evidence["fetch_error"] = str(exc)
                return current_url, VerificationStatus.UNCONFIRMED, "", evidence

        return current_url, VerificationStatus.VERIFIED_ACTIVE, "", evidence

    def _build_rejected_job(
        self,
        raw_job: RawJobPosting,
        normalized_url: str,
        source_domain: str,
        status: VerificationStatus,
        evidence: dict[str, Any],
        reason: str
    ) -> VerifiedJob:
        """Construct a VerifiedJob representation for a rejected or expired opportunity."""
        from src.job_agent.deduplication import compute_content_hash, compute_job_id
        now_utc = datetime.now(timezone.utc).isoformat()
        stable_id = compute_job_id(raw_job.employer_name, normalized_url)
        content_hash = compute_content_hash(raw_job.title, raw_job.employer_name, "", "")

        return VerifiedJob(
            id=stable_id,
            employer_name=raw_job.employer_name,
            title=raw_job.title,
            normalized_url=normalized_url,
            original_url=raw_job.original_url,
            source_domain=source_domain,
            career_track=detect_career_track(raw_job.title),
            location=raw_job.location or "Unknown",
            description_summary=reason,
            verification_status=status,
            verification_evidence=evidence,
            first_seen_at=now_utc,
            last_checked_at=now_utc,
            content_hash=content_hash,
            relevance_score=0,
            relevance_explanation=f"Rejected: {reason}",
        )
