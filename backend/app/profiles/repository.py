"""Profile repository: persist and retrieve StudentProfile objects in SQLite."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Profile
from app.db.session import SessionLocal
from app.schemas import StudentProfile


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def _to_model(profile: StudentProfile, now: str, existing: Profile | None) -> Profile:
    stack = dataclasses.asdict(profile.stack)
    location = dataclasses.asdict(profile.location)
    languages = [dataclasses.asdict(l) for l in profile.languages]
    availability = dataclasses.asdict(profile.availability)
    expected_salary = dataclasses.asdict(profile.expected_salary)
    restrictions = dataclasses.asdict(profile.restrictions)
    preferences = dataclasses.asdict(profile.preferences)

    created_at = existing.created_at if existing else now

    return Profile(
        profile_id=profile.profile_id,
        name=profile.name,
        cohort=profile.cohort,
        seniority=profile.seniority,
        modality=json.dumps(profile.modality),
        stack=json.dumps(stack),
        location=json.dumps(location),
        languages=json.dumps(languages),
        availability=json.dumps(availability),
        expected_salary=json.dumps(expected_salary),
        restrictions=json.dumps(restrictions),
        preferences=json.dumps(preferences),
        created_at=created_at,
        updated_at=now,
    )


def _from_model(row: Profile) -> StudentProfile:
    d = {
        "profile_id": row.profile_id,
        "name": row.name,
        "cohort": row.cohort,
        "seniority": row.seniority,
        "modality": json.loads(row.modality),
        "stack": json.loads(row.stack),
        "location": json.loads(row.location),
        "languages": json.loads(row.languages),
        "availability": json.loads(row.availability),
        "expected_salary": json.loads(row.expected_salary),
        "restrictions": json.loads(row.restrictions),
        "preferences": json.loads(row.preferences),
    }
    return StudentProfile.from_dict(d)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upsert_profile(profile: StudentProfile, session: Session | None = None) -> str:
    """
    Insert or update a profile.  Returns 'inserted' or 'updated'.
    """
    now = datetime.now(timezone.utc).isoformat()

    def _run(s: Session) -> str:
        existing = s.get(Profile, profile.profile_id)
        row = _to_model(profile, now, existing)
        if existing:
            s.merge(row)
            action = "updated"
        else:
            s.add(row)
            action = "inserted"
        s.commit()
        return action

    if session is not None:
        return _run(session)
    with SessionLocal() as s:
        return _run(s)


def load_profile(profile_id: str, session: Session | None = None) -> StudentProfile | None:
    """Return the profile for *profile_id*, or None if not found."""

    def _run(s: Session) -> StudentProfile | None:
        row = s.get(Profile, profile_id)
        return _from_model(row) if row else None

    if session is not None:
        return _run(session)
    with SessionLocal() as s:
        return _run(s)


def list_profiles(session: Session | None = None) -> list[StudentProfile]:
    """Return all stored profiles ordered by name."""

    def _run(s: Session) -> list[StudentProfile]:
        rows = s.execute(select(Profile).order_by(Profile.name)).scalars().all()
        return [_from_model(r) for r in rows]

    if session is not None:
        return _run(session)
    with SessionLocal() as s:
        return _run(s)


def delete_profile(profile_id: str, session: Session | None = None) -> bool:
    """Delete a profile. Returns True if it existed, False if not found."""

    def _run(s: Session) -> bool:
        row = s.get(Profile, profile_id)
        if row is None:
            return False
        s.delete(row)
        s.commit()
        return True

    if session is not None:
        return _run(session)
    with SessionLocal() as s:
        return _run(s)
