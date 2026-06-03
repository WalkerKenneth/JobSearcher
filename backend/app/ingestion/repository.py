"""
JobRepository: persists NormalizedJob objects with 3-level deduplication.

Level 1 — apply_url match (most reliable)
Level 2 — source + job_id match (same fetch cycle)
Level 3 — dedup_key fuzzy cross-source match
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

from app.db.models import JobPosting, RawSnapshot
from app.db.session import SessionLocal  # module-level so monkeypatch can replace it in tests
from app.ingestion.normalizer import build_dedup_key, normalize_url, validate_job
from app.schemas import NormalizedJob


# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------

def _compute_status(last_seen: str) -> tuple[str, int]:
    delta = datetime.now(timezone.utc) - datetime.fromisoformat(last_seen)
    if delta <= timedelta(days=7):
        return "active", 1
    if delta <= timedelta(days=30):
        return "stale", 1
    return "expired", 0


# ---------------------------------------------------------------------------
# Completeness score (determines which duplicate becomes canonical)
# ---------------------------------------------------------------------------

def _completeness_job(job: NormalizedJob) -> int:
    score = 0
    if job.salary_min is not None:
        score += 3
    if job.salary_max is not None:
        score += 3
    if job.qualifications_raw:
        score += 2
    if job.location_city is not None:
        score += 1
    if job.stack_keywords:
        score += 1
    return score


def _completeness_model(row: JobPosting) -> int:
    score = 0
    if row.salary_min is not None:
        score += 3
    if row.salary_max is not None:
        score += 3
    if json.loads(row.qualifications_raw):
        score += 2
    if row.location_city is not None:
        score += 1
    if json.loads(row.stack_keywords):
        score += 1
    return score


# ---------------------------------------------------------------------------
# Helper: build a JobPosting ORM row from a NormalizedJob
# ---------------------------------------------------------------------------

def _to_model(job: NormalizedJob, dedup_key: str, now: str) -> JobPosting:
    status, is_active = _compute_status(now)
    return JobPosting(
        job_id=job.job_id,
        source=job.source,
        dedup_key=dedup_key,
        canonical_id=None,
        duplicate_ids="[]",
        first_seen=now,
        last_seen=now,
        fetched_at=job.fetched_at,
        fetch_count=1,
        status=status,
        is_active=is_active,
        job_title=job.job_title,
        company_name=job.company_name,
        location_city=job.location_city,
        location_country=job.location_country,
        is_remote=int(job.is_remote),
        modality=json.dumps(job.modality),
        apply_url=job.apply_url,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_currency=job.salary_currency,
        salary_period=job.salary_period,
        posted_at=job.posted_at,
        description_raw=job.description_raw,
        qualifications_raw=json.dumps(job.qualifications_raw),
        stack_keywords=json.dumps(job.stack_keywords),
        seniority_signal=job.seniority_signal,
    )


def _insert_snapshot(session: Session, job_id: str, job: NormalizedJob) -> None:
    session.add(RawSnapshot(
        job_id=job_id,
        source=job.source,
        fetched_at=job.fetched_at,
        raw_response=json.dumps(job.raw_response),
    ))


def _merge_into_canonical(canonical: JobPosting, richer: NormalizedJob) -> None:
    """Enrich the canonical row with better data from a richer duplicate."""
    if richer.salary_min is not None:
        canonical.salary_min = richer.salary_min
        canonical.salary_max = richer.salary_max
        canonical.salary_currency = richer.salary_currency
        canonical.salary_period = richer.salary_period
    if richer.qualifications_raw:
        canonical.qualifications_raw = json.dumps(richer.qualifications_raw)
    if richer.location_city and not canonical.location_city:
        canonical.location_city = richer.location_city
    if richer.stack_keywords and not json.loads(canonical.stack_keywords):
        canonical.stack_keywords = json.dumps(richer.stack_keywords)


def _refresh_seen(row: JobPosting, job: NormalizedJob) -> None:
    now = job.fetched_at
    row.last_seen = now
    row.fetched_at = now
    row.fetch_count = (row.fetch_count or 0) + 1
    row.status, row.is_active = _compute_status(now)


# ---------------------------------------------------------------------------
# Core upsert (takes an open session — caller commits)
# ---------------------------------------------------------------------------

def upsert_job(session: Session, job: NormalizedJob) -> tuple[str, str]:
    """
    Upsert a single job with 3-level dedup.
    Returns (job_id, action) where action ∈ {'inserted', 'updated_seen', 'marked_duplicate'}.
    Raises ValueError if validation fails.
    """
    errors = validate_job(job)
    if errors:
        raise ValueError(f"Validation failed for {job.job_id}: {errors}")

    # ------------------------------------------------------------------
    # Level 1 — apply_url match
    # ------------------------------------------------------------------
    existing = session.execute(
        select(JobPosting).where(JobPosting.apply_url == job.apply_url)
    ).scalar_one_or_none()

    if existing:
        _refresh_seen(existing, job)
        _insert_snapshot(session, existing.job_id, job)
        return existing.job_id, "updated_seen"

    # ------------------------------------------------------------------
    # Level 2 — source + job_id match
    # ------------------------------------------------------------------
    existing = session.execute(
        select(JobPosting).where(
            JobPosting.job_id == job.job_id,
            JobPosting.source == job.source,
        )
    ).scalar_one_or_none()

    if existing:
        _refresh_seen(existing, job)
        _insert_snapshot(session, existing.job_id, job)
        return existing.job_id, "updated_seen"

    # ------------------------------------------------------------------
    # Level 3 — dedup_key cross-source match
    # ------------------------------------------------------------------
    dedup_key = build_dedup_key(job.company_name, job.job_title, job.location_country)

    canonical = session.execute(
        select(JobPosting).where(
            JobPosting.dedup_key == dedup_key,
            JobPosting.canonical_id == None,  # noqa: E711
        )
    ).scalar_one_or_none()

    if canonical:
        new_score = _completeness_job(job)
        existing_score = _completeness_model(canonical)

        if new_score > existing_score:
            # New job has richer data — merge its fields into the existing canonical
            # (avoids FK constraint issues from swapping which row is canonical)
            _merge_into_canonical(canonical, job)

        # Always insert the new job as a duplicate of the existing canonical
        dup_id = _safe_job_id(session, job)
        dup_row = _to_model(job, dedup_key, job.fetched_at)
        dup_row.job_id = dup_id
        dup_row.canonical_id = canonical.job_id
        session.add(dup_row)
        session.flush()

        existing_dups = json.loads(canonical.duplicate_ids)
        existing_dups.append(dup_id)
        canonical.duplicate_ids = json.dumps(existing_dups)
        _insert_snapshot(session, dup_id, job)

        return job.job_id, "marked_duplicate"

    # ------------------------------------------------------------------
    # New canonical insert
    # ------------------------------------------------------------------
    safe_id = _safe_job_id(session, job)
    row = _to_model(job, dedup_key, job.fetched_at)
    row.job_id = safe_id
    session.add(row)
    session.flush()
    _insert_snapshot(session, safe_id, job)
    return safe_id, "inserted"


def _safe_job_id(session: Session, job: NormalizedJob) -> str:
    """Return job.job_id, or a remapped ID if the PK is already taken by another source."""
    existing = session.get(JobPosting, job.job_id)
    if existing and existing.source != job.source:
        raw = f"{job.source}|{job.job_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    return job.job_id


# ---------------------------------------------------------------------------
# Load stored jobs back as NormalizedJob objects
# ---------------------------------------------------------------------------

def _row_to_normalized(row: JobPosting) -> NormalizedJob:
    return NormalizedJob(
        job_id=row.job_id,
        source=row.source,  # type: ignore[arg-type]
        fetched_at=row.fetched_at,
        job_title=row.job_title,
        company_name=row.company_name,
        location_city=row.location_city,
        location_country=row.location_country,
        is_remote=bool(row.is_remote),
        modality=json.loads(row.modality),
        salary_min=row.salary_min,
        salary_max=row.salary_max,
        salary_currency=row.salary_currency,
        salary_period=row.salary_period,  # type: ignore[arg-type]
        description_raw=row.description_raw,
        qualifications_raw=json.loads(row.qualifications_raw),
        posted_at=row.posted_at,
        apply_url=row.apply_url,
        stack_keywords=json.loads(row.stack_keywords),
        seniority_signal=row.seniority_signal,  # type: ignore[arg-type]
    )


def load_active_jobs(session: Session | None = None) -> list[NormalizedJob]:
    """Return all canonical active jobs from the DB as NormalizedJob objects."""
    def _query(s: Session) -> list[NormalizedJob]:
        rows = s.execute(
            select(JobPosting).where(
                JobPosting.is_active == 1,
                JobPosting.canonical_id == None,  # noqa: E711
            )
        ).scalars().all()
        return [_row_to_normalized(r) for r in rows]

    if session is not None:
        return _query(session)

    with SessionLocal() as s:
        return _query(s)


def list_all_jobs(session: Session | None = None) -> list[dict]:
    """Return all canonical job postings as display-ready dicts, newest first."""
    def _query(s: Session) -> list[dict]:
        rows = s.execute(
            select(JobPosting)
            .where(JobPosting.canonical_id == None)  # noqa: E711
            .order_by(JobPosting.last_seen.desc())
        ).scalars().all()
        return [
            {
                "job_id": r.job_id,
                "source": r.source,
                "job_title": r.job_title,
                "company_name": r.company_name,
                "location_city": r.location_city,
                "location_country": r.location_country,
                "is_remote": bool(r.is_remote),
                "status": r.status,
                "seniority_signal": r.seniority_signal,
                "stack_keywords": json.loads(r.stack_keywords),
                "apply_url": r.apply_url,
                "salary_min": r.salary_min,
                "salary_max": r.salary_max,
                "salary_currency": r.salary_currency,
                "salary_period": r.salary_period,
                "last_seen": r.last_seen,
                "fetch_count": r.fetch_count,
                "duplicate_ids": json.loads(r.duplicate_ids),
            }
            for r in rows
        ]

    if session is not None:
        return _query(session)
    with SessionLocal() as s:
        return _query(s)


def load_job(job_id: str, session: Session | None = None) -> dict | None:
    """Return full details of a single job posting, or None if not found."""
    def _query(s: Session) -> dict | None:
        row = s.get(JobPosting, job_id)
        if row is None:
            return None
        return {
            "job_id": row.job_id,
            "source": row.source,
            "job_title": row.job_title,
            "company_name": row.company_name,
            "location_city": row.location_city,
            "location_country": row.location_country,
            "is_remote": bool(row.is_remote),
            "modality": json.loads(row.modality),
            "status": row.status,
            "seniority_signal": row.seniority_signal,
            "stack_keywords": json.loads(row.stack_keywords),
            "apply_url": row.apply_url,
            "salary_min": row.salary_min,
            "salary_max": row.salary_max,
            "salary_currency": row.salary_currency,
            "salary_period": row.salary_period,
            "posted_at": row.posted_at,
            "last_seen": row.last_seen,
            "first_seen": row.first_seen,
            "fetch_count": row.fetch_count,
            "canonical_id": row.canonical_id,
            "duplicate_ids": json.loads(row.duplicate_ids),
            "qualifications_raw": json.loads(row.qualifications_raw),
            "description_raw": row.description_raw,
        }

    if session is not None:
        return _query(session)
    with SessionLocal() as s:
        return _query(s)


# ---------------------------------------------------------------------------
# Batch load by IDs (used by the API to avoid N+1 queries)
# ---------------------------------------------------------------------------

def load_jobs_by_ids(job_ids: list[str], session: Session | None = None) -> list[dict]:
    """Return display-ready dicts for the given job IDs in a single query."""
    if not job_ids:
        return []

    def _query(s: Session) -> list[dict]:
        rows = s.execute(
            select(JobPosting).where(JobPosting.job_id.in_(job_ids))
        ).scalars().all()
        return [
            {
                "job_id": r.job_id,
                "job_title": r.job_title,
                "company_name": r.company_name,
                "location_city": r.location_city,
                "location_country": r.location_country,
                "is_remote": bool(r.is_remote),
                "apply_url": r.apply_url,
            }
            for r in rows
        ]

    if session is not None:
        return _query(session)
    with SessionLocal() as s:
        return _query(s)


# ---------------------------------------------------------------------------
# Batch upsert (creates its own session)
# ---------------------------------------------------------------------------

IngestStats = dict[str, int]


def upsert_jobs(jobs: list[NormalizedJob]) -> IngestStats:
    """
    Batch upsert. Creates its own DB session.
    Returns stats: inserted / updated_seen / marked_duplicate / rejected.

    Cada job se envuelve en un savepoint (begin_nested) para que un fallo
    individual no revierta el lote completo — crítico en workers Celery donde
    reintentar la tarea completa sería costoso.
    """
    stats: IngestStats = {"inserted": 0, "updated_seen": 0, "marked_duplicate": 0, "rejected": 0}

    with SessionLocal() as session:
        for job in jobs:
            try:
                with session.begin_nested():  # SAVEPOINT por job
                    _, action = upsert_job(session, job)
                stats[action] = stats.get(action, 0) + 1
            except ValueError as exc:
                log.warning("Saltando %s: %s", job.job_id, exc)
                stats["rejected"] += 1
            except Exception as exc:
                log.error("Error al persistir %s: %s", job.job_id, exc, exc_info=True)
                stats["rejected"] += 1
        session.commit()

    return stats
