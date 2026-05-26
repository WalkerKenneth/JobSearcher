"""RecommendationPayload — converts JobMatch + NormalizedJob into a delivery-ready struct."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from app.schemas import NormalizedJob
from app.scoring.scorer import JobMatch

FeedbackStatus = Literal["recommended", "seen", "discarded", "applied", "needs_coach"]
VALID_STATUSES: tuple[str, ...] = ("recommended", "seen", "discarded", "applied", "needs_coach")


@dataclass
class RecommendationPayload:
    rec_id: str
    profile_id: str
    generated_at: str

    job_id: str
    title: str
    company: str
    apply_url: str
    modality: list[str]
    location: str
    match_score: int
    match_reasons: list[str]
    gaps: list[str]
    next_action: str
    status: FeedbackStatus = "recommended"

    def to_dict(self) -> dict:
        return {
            "rec_id": self.rec_id,
            "profile_id": self.profile_id,
            "generated_at": self.generated_at,
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "apply_url": self.apply_url,
            "modality": self.modality,
            "location": self.location,
            "match_score": self.match_score,
            "match_reasons": self.match_reasons,
            "gaps": self.gaps,
            "next_action": self.next_action,
            "status": self.status,
        }


def _build_location(job: NormalizedJob) -> str:
    parts = [p for p in [job.location_city, job.location_country] if p]
    base = ", ".join(parts) if parts else ""
    if job.is_remote:
        return f"Remoto ({base})" if base else "Remoto"
    return base or "Sin ubicación"


def build_payload(
    match: JobMatch,
    job: NormalizedJob,
    profile_id: str,
    generated_at: str | None = None,
) -> RecommendationPayload:
    """Build one RecommendationPayload from a scored match and its source job."""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat()

    return RecommendationPayload(
        rec_id=f"{profile_id}_{match.job_id}",
        profile_id=profile_id,
        generated_at=generated_at,
        job_id=match.job_id,
        title=match.title,
        company=match.company,
        apply_url=job.apply_url,
        modality=job.modality,
        location=_build_location(job),
        match_score=match.match_score,
        match_reasons=match.match_reasons,
        gaps=match.gaps,
        next_action=match.action,
    )


def build_recommendations(
    matches: list[JobMatch],
    jobs: list[NormalizedJob],
    profile_id: str,
    top_n: int = 10,
) -> list[RecommendationPayload]:
    """Build top-N payloads from a ranked match list. Only includes jobs that passed hard filters."""
    job_map: dict[str, NormalizedJob] = {j.job_id: j for j in jobs}
    generated_at = datetime.now(timezone.utc).isoformat()

    passing = [m for m in matches if m.hard_filters_passed][:top_n]

    return [
        build_payload(match, job_map[match.job_id], profile_id, generated_at)
        for match in passing
        if match.job_id in job_map
    ]
