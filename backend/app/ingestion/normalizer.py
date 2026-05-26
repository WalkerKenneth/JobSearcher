"""
Converts raw API responses to NormalizedJob objects.
Also provides helpers used by the repository (dedup_key, url normalisation, validation).
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.schemas import NormalizedJob


# ---------------------------------------------------------------------------
# Tech keyword extraction (lightweight; LLM-based extraction in subtask 7)
# ---------------------------------------------------------------------------

_TECH_KEYWORDS = [
    "react", "vue", "angular", "javascript", "typescript", "html", "css",
    "sass", "scss", "webpack", "vite", "next.js", "nextjs", "nuxt",
    "node.js", "nodejs", "express", "fastapi", "django", "flask",
    "python", "java", "kotlin", "go", "rust", "php", "laravel", "ruby",
    "postgresql", "postgres", "mysql", "mongodb", "redis", "sqlite",
    "graphql", "rest", "restful", "docker", "kubernetes", "aws", "gcp",
    "azure", "git", "github", "gitlab", "linux", "bash", "sql", "nosql",
    "tailwind", "bootstrap", "jest", "cypress", "playwright",
]

_TECH_RE = re.compile(
    r"\b(" + "|".join(re.escape(kw) for kw in _TECH_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def extract_stack_keywords(text: str) -> list[str]:
    found = {m.group().lower() for m in _TECH_RE.finditer(text)}
    # Preserve original casing from keyword list
    casing = {kw.lower(): kw for kw in _TECH_KEYWORDS}
    return sorted(casing.get(kw, kw) for kw in found)


# ---------------------------------------------------------------------------
# Seniority inference
# ---------------------------------------------------------------------------

_JUNIOR_RE = re.compile(
    r"\b(junior|entry[\s-]?level|recién\s+graduad[ao]|sin\s+experiencia|0[\s-]?[aà]\s*1\s+a[ñn]o)\b",
    re.IGNORECASE,
)
_MID_RE = re.compile(
    r"\b(mid[\s-]?level|semi[\s-]?senior|2[\s-]?[aà]\s*3\s+a[ñn]os?|2\+\s+a[ñn]os?)\b",
    re.IGNORECASE,
)
_SENIOR_RE = re.compile(
    r"\b(senior|lead|principal|staff|4\+\s+a[ñn]os?|5\+\s+a[ñn]os?)\b",
    re.IGNORECASE,
)


def infer_seniority(title: str, description: str) -> str:
    combined = f"{title} {description}"
    if _JUNIOR_RE.search(combined):
        return "junior"
    if _MID_RE.search(combined):
        return "mid"
    if _SENIOR_RE.search(combined):
        return "senior"
    return "unknown"


# ---------------------------------------------------------------------------
# Modality inference (JSearch has only is_remote; we check description too)
# ---------------------------------------------------------------------------

_HYBRID_RE = re.compile(r"\b(h[íi]brid[ao]|hybrid|parcialmente\s+remoto)\b", re.IGNORECASE)
_REMOTE_RE = re.compile(r"\b(remoto|remote|trabajo\s+en\s+casa|work\s+from\s+home)\b", re.IGNORECASE)


def infer_modality(is_remote: bool, description: str) -> list[str]:
    if is_remote:
        if _HYBRID_RE.search(description):
            return ["remote", "hybrid"]
        return ["remote"]
    if _HYBRID_RE.search(description):
        return ["hybrid"]
    if _REMOTE_RE.search(description):
        return ["remote", "hybrid"]
    return ["on-site"]


# ---------------------------------------------------------------------------
# URL normalisation (strip UTM + tracking params, remove trailing slash)
# ---------------------------------------------------------------------------

_TRACKING_PARAMS = {"ref", "source", "campaign", "utm_source", "utm_medium",
                    "utm_campaign", "utm_content", "utm_term"}


def normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        clean = {k: v for k, v in parse_qs(parsed.query).items()
                 if k not in _TRACKING_PARAMS and not k.startswith("utm_")}
        clean_query = urlencode(clean, doseq=True)
        return urlunparse(parsed._replace(query=clean_query)).rstrip("/")
    except Exception:
        return url.rstrip("/")


# ---------------------------------------------------------------------------
# Dedup key (cross-source fingerprint)
# ---------------------------------------------------------------------------

_COMPANY_SUFFIXES = [" s.a.s.", " s.r.l.", " s.a.", " s.l.", " inc.", " llc.", " corp.", " ltd.", " inc", " llc", " corp", " ltd"]


def _normalize_text(s: str) -> str:
    s = s.lower().strip()
    # Strip company suffixes BEFORE removing punctuation so patterns like " s.a." still match
    for suffix in _COMPANY_SUFFIXES:
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def build_dedup_key(company: str, title: str, country: str) -> str:
    raw = _normalize_text(company) + "|" + _normalize_text(title) + "|" + _normalize_text(country)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Salary period mapping
# ---------------------------------------------------------------------------

def _map_salary_period(raw: str | None) -> str | None:
    if not raw:
        return None
    upper = raw.upper()
    if "MONTH" in upper or "MES" in upper:
        return "monthly"
    if "YEAR" in upper or "ANNUAL" in upper or "AÑO" in upper:
        return "annual"
    return None


# ---------------------------------------------------------------------------
# Job ID generation (when source has no native ID)
# ---------------------------------------------------------------------------

def _generate_job_id(source: str, company: str, title: str, country: str) -> str:
    raw = f"{source}|{company}|{title}|{country}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# JSearch normaliser
# ---------------------------------------------------------------------------

def normalize_jsearch(raw: dict, fetched_at: str) -> NormalizedJob:
    job_id = raw.get("job_id") or _generate_job_id(
        "jsearch", raw.get("employer_name", ""), raw.get("job_title", ""), raw.get("job_country", "")
    )
    is_remote = bool(raw.get("job_is_remote", False))
    description = raw.get("job_description", "")

    return NormalizedJob(
        job_id=job_id,
        source="jsearch",
        fetched_at=fetched_at,
        job_title=raw.get("job_title", ""),
        company_name=raw.get("employer_name", ""),
        location_city=raw.get("job_city") or None,
        location_country=raw.get("job_country", ""),
        is_remote=is_remote,
        modality=infer_modality(is_remote, description),
        salary_min=raw.get("job_min_salary"),
        salary_max=raw.get("job_max_salary"),
        salary_currency=raw.get("job_salary_currency"),
        salary_period=_map_salary_period(raw.get("job_salary_period")),
        description_raw=description,
        qualifications_raw=[],
        posted_at=raw.get("job_posted_at_datetime_utc"),
        apply_url=normalize_url(raw.get("job_apply_link", "")),
        stack_keywords=extract_stack_keywords(description),
        seniority_signal=infer_seniority(raw.get("job_title", ""), description),
        raw_response=raw,
    )


def normalize_jsearch_batch(raw_jobs: list[dict], fetched_at: str) -> list[NormalizedJob]:
    return [normalize_jsearch(job, fetched_at) for job in raw_jobs]


# ---------------------------------------------------------------------------
# SerpAPI normaliser
# ---------------------------------------------------------------------------

def _parse_serpapi_location(location: str) -> tuple[str | None, str]:
    parts = [p.strip() for p in location.split(",")]
    if len(parts) >= 2:
        return parts[0], parts[-1]
    return None, location


def normalize_serpapi(raw: dict, fetched_at: str) -> NormalizedJob:
    title = raw.get("title", "")
    company = raw.get("company_name", "")
    location_str = raw.get("location", "")
    city, country = _parse_serpapi_location(location_str)

    job_id = _generate_job_id("serpapi", company, title, country)

    ext = raw.get("detected_extensions", {})
    is_remote = bool(ext.get("work_from_home", False))
    description = raw.get("description", "")

    highlights = raw.get("job_highlights", {})
    qualifications = highlights.get("Qualifications", [])

    apply_options = raw.get("apply_options", [])
    apply_url = normalize_url(apply_options[0]["link"] if apply_options else "")

    return NormalizedJob(
        job_id=job_id,
        source="serpapi",
        fetched_at=fetched_at,
        job_title=title,
        company_name=company,
        location_city=city,
        location_country=country,
        is_remote=is_remote,
        modality=infer_modality(is_remote, description),
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        salary_period=None,
        description_raw=description,
        qualifications_raw=qualifications,
        posted_at=ext.get("posted_at"),
        apply_url=apply_url,
        stack_keywords=extract_stack_keywords(description),
        seniority_signal=infer_seniority(title, description),
        raw_response=raw,
    )


def normalize_serpapi_batch(raw_jobs: list[dict], fetched_at: str) -> list[NormalizedJob]:
    return [normalize_serpapi(job, fetched_at) for job in raw_jobs]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_job(job: NormalizedJob) -> list[str]:
    errors: list[str] = []

    if not job.job_id:
        errors.append("job_id is empty")
    if not job.apply_url.startswith("https://"):
        errors.append(f"apply_url invalid: '{job.apply_url}'")
    if not job.job_title:
        errors.append("job_title is empty")
    if not job.company_name:
        errors.append("company_name is empty")
    if not job.location_country:
        errors.append("location_country is empty")
    if len(job.description_raw) < 50:
        errors.append(f"description_raw too short ({len(job.description_raw)} chars, min 50)")

    if job.posted_at:
        try:
            dt = datetime.fromisoformat(job.posted_at.replace("Z", "+00:00"))
            if dt > datetime.now(timezone.utc):
                errors.append(f"posted_at is in the future: {job.posted_at}")
        except ValueError:
            errors.append(f"posted_at not parseable: '{job.posted_at}'")

    return errors
