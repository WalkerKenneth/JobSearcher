"""Delivery repository: persist recommendations and record user feedback."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FeedbackEvent, Recommendation
from app.db.session import SessionLocal
from app.delivery.payload import FeedbackStatus, RecommendationPayload

TERMINAL_STATUSES = {"applied", "discarded"}


def save_recommendations(
    payloads: list[RecommendationPayload],
    session: Session | None = None,
) -> dict[str, int]:
    """Upsert recommendations, preserving user feedback status on re-runs.

    On re-run, score/reasons/gaps are updated but status is preserved unless
    it hasn't been acted on yet (still 'recommended').
    """
    def _run(s: Session) -> dict[str, int]:
        inserted = 0
        updated = 0
        now = datetime.now(timezone.utc).isoformat()

        for p in payloads:
            existing = s.get(Recommendation, p.rec_id)
            if existing is None:
                s.add(Recommendation(
                    rec_id=p.rec_id,
                    profile_id=p.profile_id,
                    job_id=p.job_id,
                    generated_at=p.generated_at,
                    match_score=p.match_score,
                    match_reasons=json.dumps(p.match_reasons),
                    gaps=json.dumps(p.gaps),
                    next_action=p.next_action,
                    status="recommended",
                    status_updated_at=now,
                ))
                inserted += 1
            else:
                existing.match_score = p.match_score
                existing.match_reasons = json.dumps(p.match_reasons)
                existing.gaps = json.dumps(p.gaps)
                existing.next_action = p.next_action
                existing.generated_at = p.generated_at
                if existing.status == "recommended":
                    existing.status_updated_at = now
                updated += 1

        s.commit()
        return {"inserted": inserted, "updated": updated}

    if session is not None:
        return _run(session)

    with SessionLocal() as s:
        return _run(s)


def record_feedback(
    rec_id: str,
    status: FeedbackStatus,
    note: str = "",
    session: Session | None = None,
) -> bool:
    """Update recommendation status and append a feedback event.

    Returns False if rec_id not found; True on success.
    """
    def _run(s: Session) -> bool:
        rec = s.get(Recommendation, rec_id)
        if rec is None:
            return False

        now = datetime.now(timezone.utc).isoformat()
        rec.status = status
        rec.status_updated_at = now

        s.add(FeedbackEvent(
            rec_id=rec_id,
            status=status,
            note=note,
            recorded_at=now,
        ))
        s.commit()
        return True

    if session is not None:
        return _run(session)

    with SessionLocal() as s:
        return _run(s)


def get_recommendations(
    profile_id: str,
    status: FeedbackStatus | None = None,
    session: Session | None = None,
) -> list[dict]:
    """Return recommendations for a profile, optionally filtered by status.

    Results are sorted by match_score descending.
    """
    def _run(s: Session) -> list[dict]:
        stmt = select(Recommendation).where(Recommendation.profile_id == profile_id)
        if status is not None:
            stmt = stmt.where(Recommendation.status == status)
        stmt = stmt.order_by(Recommendation.match_score.desc())

        recs = s.scalars(stmt).all()
        return [
            {
                "rec_id": r.rec_id,
                "job_id": r.job_id,
                "match_score": r.match_score,
                "match_reasons": json.loads(r.match_reasons),
                "gaps": json.loads(r.gaps),
                "next_action": r.next_action,
                "status": r.status,
                "status_updated_at": r.status_updated_at,
            }
            for r in recs
        ]

    if session is not None:
        return _run(session)

    with SessionLocal() as s:
        return _run(s)


def get_feedback_events(rec_id: str, session: Session | None = None) -> list[dict]:
    """Return all feedback events for a recommendation, oldest first."""
    def _run(s: Session) -> list[dict]:
        stmt = (
            select(FeedbackEvent)
            .where(FeedbackEvent.rec_id == rec_id)
            .order_by(FeedbackEvent.recorded_at)
        )
        events = s.scalars(stmt).all()
        return [
            {
                "id": e.id,
                "rec_id": e.rec_id,
                "status": e.status,
                "note": e.note,
                "recorded_at": e.recorded_at,
            }
            for e in events
        ]

    if session is not None:
        return _run(session)

    with SessionLocal() as s:
        return _run(s)
