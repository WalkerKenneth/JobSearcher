"""Tests for the profile repository (upsert, load, list, delete)."""
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.session import create_indexes
from app.profiles.repository import delete_profile, list_profiles, load_profile, upsert_profile
from app.schemas import StudentProfile

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "profiles"


# ---------------------------------------------------------------------------
# DB fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def db(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    create_indexes(engine)
    TestSession = sessionmaker(bind=engine, autoflush=True, autocommit=False)

    monkeypatch.setattr("app.profiles.repository.SessionLocal", TestSession)
    session = TestSession()
    yield session
    session.close()
    engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_fixture(filename: str) -> StudentProfile:
    return StudentProfile.from_dict(
        json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
    )


# ---------------------------------------------------------------------------
# upsert_profile
# ---------------------------------------------------------------------------

def test_upsert_inserts_new_profile(db):
    profile = _load_fixture("junior_frontend.json")
    action = upsert_profile(profile, session=db)
    assert action == "inserted"


def test_upsert_updates_existing_profile(db):
    profile = _load_fixture("junior_frontend.json")
    upsert_profile(profile, session=db)

    updated = StudentProfile.from_dict({
        **{
            "profile_id": profile.profile_id,
            "name": "Valentina Torres Updated",
            "cohort": profile.cohort,
            "seniority": profile.seniority,
            "modality": profile.modality,
            "stack": {"primary": profile.stack.primary, "secondary": profile.stack.secondary, "tools": profile.stack.tools},
            "location": {"city": profile.location.city, "country": profile.location.country, "timezone": profile.location.timezone},
            "languages": [{"language": l.language, "level": l.level} for l in profile.languages],
            "availability": {"start_date": profile.availability.start_date, "hours_per_week": profile.availability.hours_per_week, "type": profile.availability.type},
            "expected_salary": {"min": profile.expected_salary.min, "max": profile.expected_salary.max, "currency": profile.expected_salary.currency, "period": profile.expected_salary.period},
            "restrictions": {
                "min_salary": profile.restrictions.min_salary,
                "currency": profile.restrictions.currency,
                "excluded_modalities": profile.restrictions.excluded_modalities,
                "excluded_locations": profile.restrictions.excluded_locations,
                "requires_visa_sponsorship": profile.restrictions.requires_visa_sponsorship,
                "max_travel_percent": profile.restrictions.max_travel_percent,
            },
            "preferences": {
                "company_size": profile.preferences.company_size,
                "sectors": profile.preferences.sectors,
                "roles": profile.preferences.roles,
                "avoid_sectors": profile.preferences.avoid_sectors,
                "growth_priority": profile.preferences.growth_priority,
            },
        }
    })
    action = upsert_profile(updated, session=db)
    assert action == "updated"

    loaded = load_profile(profile.profile_id, session=db)
    assert loaded.name == "Valentina Torres Updated"


# ---------------------------------------------------------------------------
# load_profile
# ---------------------------------------------------------------------------

def test_load_returns_none_for_unknown_id(db):
    assert load_profile("nonexistent", session=db) is None


def test_load_roundtrips_all_fields(db):
    profile = _load_fixture("junior_frontend.json")
    upsert_profile(profile, session=db)

    loaded = load_profile(profile.profile_id, session=db)

    assert loaded.profile_id == profile.profile_id
    assert loaded.name == profile.name
    assert loaded.cohort == profile.cohort
    assert loaded.seniority == profile.seniority
    assert loaded.modality == profile.modality
    assert loaded.stack.primary == profile.stack.primary
    assert loaded.stack.secondary == profile.stack.secondary
    assert loaded.stack.tools == profile.stack.tools
    assert loaded.location.city == profile.location.city
    assert loaded.location.country == profile.location.country
    assert len(loaded.languages) == len(profile.languages)
    assert loaded.languages[0].language == profile.languages[0].language
    assert loaded.languages[0].level == profile.languages[0].level
    assert loaded.availability.hours_per_week == profile.availability.hours_per_week
    assert loaded.expected_salary.min == profile.expected_salary.min
    assert loaded.expected_salary.currency == profile.expected_salary.currency
    assert loaded.restrictions.excluded_modalities == profile.restrictions.excluded_modalities
    assert loaded.preferences.growth_priority == profile.preferences.growth_priority
    assert loaded.preferences.avoid_sectors == profile.preferences.avoid_sectors


# ---------------------------------------------------------------------------
# list_profiles
# ---------------------------------------------------------------------------

def test_list_empty_returns_empty(db):
    assert list_profiles(session=db) == []


def test_list_returns_all_profiles(db):
    p1 = _load_fixture("junior_frontend.json")
    p2 = _load_fixture("junior_fullstack.json")
    upsert_profile(p1, session=db)
    upsert_profile(p2, session=db)

    profiles = list_profiles(session=db)
    assert len(profiles) == 2
    ids = {p.profile_id for p in profiles}
    assert p1.profile_id in ids
    assert p2.profile_id in ids


# ---------------------------------------------------------------------------
# delete_profile
# ---------------------------------------------------------------------------

def test_delete_existing_profile(db):
    profile = _load_fixture("junior_frontend.json")
    upsert_profile(profile, session=db)

    result = delete_profile(profile.profile_id, session=db)
    assert result is True
    assert load_profile(profile.profile_id, session=db) is None


def test_delete_nonexistent_returns_false(db):
    result = delete_profile("does-not-exist", session=db)
    assert result is False
