"""Tests for the delivery and feedback flow (subtarea 8).

Coverage:
  - payload: build_payload, build_recommendations, location formatting, to_dict
  - repository: save_recommendations (insert, upsert, status preservation)
  - repository: record_feedback (happy path, missing rec_id, event log)
  - repository: get_recommendations (all, filtered by status)
  - repository: get_feedback_events (ordering, note)
  - load_active_jobs integration with repository
"""

import json
import pytest

from app.db.models import JobPosting, Recommendation, FeedbackEvent
from app.delivery.payload import (
    RecommendationPayload,
    build_payload,
    build_recommendations,
)
from app.delivery.repository import (
    get_feedback_events,
    get_recommendations,
    record_feedback,
    save_recommendations,
)
from app.ingestion.repository import load_active_jobs, upsert_job
from app.schemas import (
    Availability,
    ExpectedSalary,
    LanguageSkill,
    NormalizedJob,
    Preferences,
    ProfileLocation,
    Restrictions,
    Stack,
    StudentProfile,
)
from app.scoring.scorer import JobMatch, rank_jobs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_job(**kwargs) -> NormalizedJob:
    defaults = dict(
        job_id="job_001",
        source="jsearch",
        fetched_at="2026-05-25T14:00:00+00:00",
        job_title="Junior Frontend Developer",
        company_name="TechCR",
        location_city="San José",
        location_country="Costa Rica",
        is_remote=True,
        modality=["remote"],
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        salary_period=None,
        description_raw="Buscamos junior developer con React y JavaScript en startup tech.",
        qualifications_raw=[],
        posted_at="2026-05-20T00:00:00+00:00",
        apply_url="https://example.com/job/001",
        stack_keywords=["React", "JavaScript"],
        seniority_signal="junior",
    )
    defaults.update(kwargs)
    return NormalizedJob(**defaults)


def make_match(**kwargs) -> JobMatch:
    defaults = dict(
        job_id="job_001",
        title="Junior Frontend Developer",
        company="TechCR",
        match_score=75,
        hard_filters_passed=True,
        match_reasons=["Stack: react, javascript (2/2)"],
        gaps=[],
        action="Aplicar con adaptaciones menores al CV",
    )
    defaults.update(kwargs)
    return JobMatch(**defaults)


def make_profile() -> StudentProfile:
    return StudentProfile(
        profile_id="val_001",
        name="Valentina",
        cohort="lyfter-2026",
        stack=Stack(primary=["React", "JavaScript"], secondary=[], tools=[]),
        seniority="junior",
        location=ProfileLocation(city="San José", country="Costa Rica", timezone="America/Costa_Rica"),
        modality=["remote"],
        languages=[LanguageSkill(language="English", level="intermediate")],
        availability=Availability(start_date="2026-06-01", hours_per_week=40, type="full-time"),
        expected_salary=ExpectedSalary(min=700_000, max=1_000_000, currency="CRC", period="monthly"),
        restrictions=Restrictions(
            min_salary=None,
            currency="CRC",
            excluded_modalities=[],
            excluded_locations=[],
            requires_visa_sponsorship=False,
            max_travel_percent=None,
        ),
        preferences=Preferences(
            company_size=["startup"],
            sectors=["tech"],
            roles=["Frontend Developer"],
            avoid_sectors=["gambling"],
            growth_priority="learning",
        ),
    )


def _dedup_key(job: NormalizedJob) -> str:
    import re
    def norm(s: str) -> str:
        return re.sub(r"\s+", "_", s.lower().strip())
    return f"{norm(job.company_name)}|{norm(job.job_title)}|{norm(job.location_country)}"


def _insert_job_posting(db_session, job: NormalizedJob) -> None:
    db_session.add(JobPosting(
        job_id=job.job_id,
        source=job.source,
        dedup_key=_dedup_key(job),
        canonical_id=None,
        duplicate_ids="[]",
        first_seen=job.fetched_at,
        last_seen=job.fetched_at,
        fetched_at=job.fetched_at,
        fetch_count=1,
        status="active",
        is_active=1,
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
    ))
    db_session.commit()


# ---------------------------------------------------------------------------
# payload.py — build_payload
# ---------------------------------------------------------------------------

class TestBuildPayload:
    def test_basic_fields(self):
        job = make_job()
        match = make_match()
        p = build_payload(match, job, "val_001", "2026-05-25T10:00:00+00:00")

        assert p.rec_id == "val_001_job_001"
        assert p.profile_id == "val_001"
        assert p.job_id == "job_001"
        assert p.title == "Junior Frontend Developer"
        assert p.company == "TechCR"
        assert p.match_score == 75
        assert p.apply_url == "https://example.com/job/001"
        assert p.next_action == "Aplicar con adaptaciones menores al CV"
        assert p.status == "recommended"

    def test_remote_location_with_city(self):
        job = make_job(is_remote=True, location_city="San José", location_country="Costa Rica")
        match = make_match()
        p = build_payload(match, job, "val_001")
        assert p.location == "Remoto (San José, Costa Rica)"

    def test_remote_without_city(self):
        job = make_job(is_remote=True, location_city=None, location_country="Costa Rica")
        match = make_match()
        p = build_payload(match, job, "val_001")
        assert p.location == "Remoto (Costa Rica)"

    def test_remote_no_location(self):
        job = make_job(is_remote=True, location_city=None, location_country="")
        match = make_match()
        p = build_payload(match, job, "val_001")
        assert p.location == "Remoto"

    def test_on_site_location(self):
        job = make_job(is_remote=False, location_city="Bogotá", location_country="Colombia")
        match = make_match()
        p = build_payload(match, job, "val_001")
        assert p.location == "Bogotá, Colombia"

    def test_generated_at_auto_set(self):
        job = make_job()
        match = make_match()
        p = build_payload(match, job, "val_001")
        assert p.generated_at  # not empty
        assert "T" in p.generated_at  # looks like ISO datetime

    def test_to_dict_keys(self):
        job = make_job()
        match = make_match()
        p = build_payload(match, job, "val_001")
        d = p.to_dict()
        expected_keys = {
            "rec_id", "profile_id", "generated_at", "job_id", "title", "company",
            "apply_url", "modality", "location", "match_score", "match_reasons",
            "gaps", "next_action", "status",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_values(self):
        job = make_job()
        match = make_match(gaps=["Falta TypeScript"])
        p = build_payload(match, job, "val_001", "2026-05-25T10:00:00+00:00")
        d = p.to_dict()
        assert d["match_score"] == 75
        assert d["gaps"] == ["Falta TypeScript"]
        assert d["status"] == "recommended"


# ---------------------------------------------------------------------------
# payload.py — build_recommendations
# ---------------------------------------------------------------------------

class TestBuildRecommendations:
    def test_returns_top_n_passing(self):
        jobs = [make_job(job_id=f"job_{i:03d}", apply_url=f"https://ex.com/{i}") for i in range(5)]
        matches = [
            make_match(job_id=f"job_{i:03d}", match_score=80 - i * 5, hard_filters_passed=True)
            for i in range(5)
        ]
        recs = build_recommendations(matches, jobs, "val_001", top_n=3)
        assert len(recs) == 3
        assert recs[0].match_score == 80
        assert recs[1].match_score == 75

    def test_excludes_failed_hard_filters(self):
        jobs = [make_job(job_id="job_001"), make_job(job_id="job_002", apply_url="https://ex.com/2")]
        matches = [
            make_match(job_id="job_001", hard_filters_passed=True, match_score=70),
            make_match(job_id="job_002", hard_filters_passed=False, match_score=0),
        ]
        recs = build_recommendations(matches, jobs, "val_001")
        assert len(recs) == 1
        assert recs[0].job_id == "job_001"

    def test_all_profile_ids_correct(self):
        jobs = [make_job(job_id=f"job_{i}", apply_url=f"https://ex.com/{i}") for i in range(3)]
        matches = [
            make_match(job_id=f"job_{i}", hard_filters_passed=True, match_score=70 - i)
            for i in range(3)
        ]
        recs = build_recommendations(matches, jobs, "andres_002")
        assert all(r.profile_id == "andres_002" for r in recs)

    def test_shared_generated_at(self):
        jobs = [make_job(job_id=f"job_{i}", apply_url=f"https://ex.com/{i}") for i in range(2)]
        matches = [
            make_match(job_id=f"job_{i}", hard_filters_passed=True) for i in range(2)
        ]
        recs = build_recommendations(matches, jobs, "val_001")
        assert recs[0].generated_at == recs[1].generated_at

    def test_empty_when_all_filtered(self):
        jobs = [make_job()]
        matches = [make_match(hard_filters_passed=False, match_score=0)]
        recs = build_recommendations(matches, jobs, "val_001")
        assert recs == []


# ---------------------------------------------------------------------------
# repository.py — save_recommendations
# ---------------------------------------------------------------------------

class TestSaveRecommendations:
    def test_inserts_new(self, db_session):
        _insert_job_posting(db_session, make_job())
        p = build_payload(make_match(), make_job(), "val_001", "2026-05-25T10:00:00+00:00")
        stats = save_recommendations([p], session=db_session)
        assert stats["inserted"] == 1
        assert stats["updated"] == 0

    def test_stored_status_is_recommended(self, db_session):
        _insert_job_posting(db_session, make_job())
        p = build_payload(make_match(), make_job(), "val_001", "2026-05-25T10:00:00+00:00")
        save_recommendations([p], session=db_session)

        rec = db_session.get(Recommendation, p.rec_id)
        assert rec.status == "recommended"

    def test_upsert_updates_score(self, db_session):
        _insert_job_posting(db_session, make_job())
        p = build_payload(make_match(match_score=60), make_job(), "val_001", "2026-05-25T10:00:00+00:00")
        save_recommendations([p], session=db_session)

        p2 = build_payload(make_match(match_score=80), make_job(), "val_001", "2026-05-25T11:00:00+00:00")
        stats = save_recommendations([p2], session=db_session)
        assert stats["updated"] == 1

        rec = db_session.get(Recommendation, p.rec_id)
        assert rec.match_score == 80

    def test_upsert_preserves_non_recommended_status(self, db_session):
        _insert_job_posting(db_session, make_job())
        p = build_payload(make_match(), make_job(), "val_001", "2026-05-25T10:00:00+00:00")
        save_recommendations([p], session=db_session)

        # user marks as applied
        rec = db_session.get(Recommendation, p.rec_id)
        rec.status = "applied"
        db_session.commit()

        # re-run recommendation
        p2 = build_payload(make_match(match_score=90), make_job(), "val_001", "2026-05-25T12:00:00+00:00")
        save_recommendations([p2], session=db_session)

        rec = db_session.get(Recommendation, p.rec_id)
        assert rec.status == "applied"
        assert rec.match_score == 90

    def test_saves_reasons_as_json(self, db_session):
        _insert_job_posting(db_session, make_job())
        reasons = ["Stack: react (1/1)", "Seniority compatible"]
        p = build_payload(
            make_match(match_reasons=reasons), make_job(), "val_001", "2026-05-25T10:00:00+00:00"
        )
        save_recommendations([p], session=db_session)

        rec = db_session.get(Recommendation, p.rec_id)
        assert json.loads(rec.match_reasons) == reasons


# ---------------------------------------------------------------------------
# repository.py — record_feedback
# ---------------------------------------------------------------------------

class TestRecordFeedback:
    def _setup(self, db_session) -> str:
        _insert_job_posting(db_session, make_job())
        p = build_payload(make_match(), make_job(), "val_001", "2026-05-25T10:00:00+00:00")
        save_recommendations([p], session=db_session)
        return p.rec_id

    def test_updates_status(self, db_session):
        rec_id = self._setup(db_session)
        result = record_feedback(rec_id, "applied", session=db_session)
        assert result is True
        rec = db_session.get(Recommendation, rec_id)
        assert rec.status == "applied"

    def test_returns_false_for_unknown_rec(self, db_session):
        result = record_feedback("nonexistent_id", "seen", session=db_session)
        assert result is False

    def test_creates_feedback_event(self, db_session):
        rec_id = self._setup(db_session)
        record_feedback(rec_id, "seen", note="Lo vi pero necesito pensarlo", session=db_session)

        events = db_session.query(FeedbackEvent).filter_by(rec_id=rec_id).all()
        assert len(events) == 1
        assert events[0].status == "seen"
        assert events[0].note == "Lo vi pero necesito pensarlo"

    def test_multiple_feedback_events_accumulate(self, db_session):
        rec_id = self._setup(db_session)
        record_feedback(rec_id, "seen", session=db_session)
        record_feedback(rec_id, "needs_coach", note="Revisar inglés", session=db_session)
        record_feedback(rec_id, "applied", session=db_session)

        events = db_session.query(FeedbackEvent).filter_by(rec_id=rec_id).all()
        assert len(events) == 3
        statuses = [e.status for e in events]
        assert "seen" in statuses
        assert "applied" in statuses

    def test_status_updated_at_changes(self, db_session):
        rec_id = self._setup(db_session)
        rec_before = db_session.get(Recommendation, rec_id)
        old_ts = rec_before.status_updated_at

        record_feedback(rec_id, "discarded", session=db_session)
        rec_after = db_session.get(Recommendation, rec_id)
        # timestamp is refreshed
        assert rec_after.status_updated_at >= old_ts


# ---------------------------------------------------------------------------
# repository.py — get_recommendations
# ---------------------------------------------------------------------------

class TestGetRecommendations:
    def _populate(self, db_session) -> list[str]:
        jobs = [
            make_job(job_id="job_001", apply_url="https://ex.com/1", company_name="AlphaCR"),
            make_job(job_id="job_002", apply_url="https://ex.com/2", company_name="BetaCR"),
            make_job(job_id="job_003", apply_url="https://ex.com/3", company_name="GammaCR"),
        ]
        for job in jobs:
            _insert_job_posting(db_session, job)

        payloads = [
            build_payload(make_match(job_id="job_001", match_score=80), jobs[0], "val_001", "2026-05-25T10:00:00+00:00"),
            build_payload(make_match(job_id="job_002", match_score=60), jobs[1], "val_001", "2026-05-25T10:00:00+00:00"),
            build_payload(make_match(job_id="job_003", match_score=40), jobs[2], "val_001", "2026-05-25T10:00:00+00:00"),
        ]
        save_recommendations(payloads, session=db_session)
        return [p.rec_id for p in payloads]

    def test_returns_all_for_profile(self, db_session):
        rec_ids = self._populate(db_session)
        recs = get_recommendations("val_001", session=db_session)
        assert len(recs) == 3

    def test_sorted_by_score_desc(self, db_session):
        self._populate(db_session)
        recs = get_recommendations("val_001", session=db_session)
        scores = [r["match_score"] for r in recs]
        assert scores == sorted(scores, reverse=True)

    def test_filter_by_status(self, db_session):
        rec_ids = self._populate(db_session)
        record_feedback(rec_ids[0], "applied", session=db_session)
        record_feedback(rec_ids[1], "discarded", session=db_session)

        applied = get_recommendations("val_001", status="applied", session=db_session)
        assert len(applied) == 1
        assert applied[0]["status"] == "applied"

    def test_empty_for_unknown_profile(self, db_session):
        self._populate(db_session)
        recs = get_recommendations("unknown_999", session=db_session)
        assert recs == []

    def test_result_has_required_keys(self, db_session):
        self._populate(db_session)
        recs = get_recommendations("val_001", session=db_session)
        required = {"rec_id", "job_id", "match_score", "match_reasons", "gaps", "next_action", "status", "status_updated_at"}
        assert required.issubset(recs[0].keys())


# ---------------------------------------------------------------------------
# repository.py — get_feedback_events
# ---------------------------------------------------------------------------

class TestGetFeedbackEvents:
    def test_empty_for_new_recommendation(self, db_session):
        _insert_job_posting(db_session, make_job())
        p = build_payload(make_match(), make_job(), "val_001", "2026-05-25T10:00:00+00:00")
        save_recommendations([p], session=db_session)

        events = get_feedback_events(p.rec_id, session=db_session)
        assert events == []

    def test_returns_events_in_order(self, db_session):
        _insert_job_posting(db_session, make_job())
        p = build_payload(make_match(), make_job(), "val_001", "2026-05-25T10:00:00+00:00")
        save_recommendations([p], session=db_session)

        record_feedback(p.rec_id, "seen", session=db_session)
        record_feedback(p.rec_id, "applied", note="Apliqué hoy", session=db_session)

        events = get_feedback_events(p.rec_id, session=db_session)
        assert len(events) == 2
        assert events[0]["status"] == "seen"
        assert events[1]["status"] == "applied"
        assert events[1]["note"] == "Apliqué hoy"

    def test_empty_for_unknown_rec(self, db_session):
        events = get_feedback_events("nonexistent", session=db_session)
        assert events == []


# ---------------------------------------------------------------------------
# load_active_jobs integration
# ---------------------------------------------------------------------------

class TestLoadActiveJobs:
    def test_returns_active_canonical_jobs(self, db_session):
        job = make_job()
        upsert_job(db_session, job)
        db_session.commit()

        jobs = load_active_jobs(session=db_session)
        assert len(jobs) == 1
        assert jobs[0].job_id == job.job_id

    def test_excludes_duplicates(self, db_session):
        job1 = make_job(job_id="job_001", apply_url="https://ex.com/1")
        job2 = make_job(
            job_id="job_002",
            apply_url="https://ex.com/2",
            company_name="TechCR",
            job_title="Junior Frontend Developer",
            location_country="Costa Rica",
            description_raw="Buscamos junior developer con React y JavaScript en startup tech. Segunda oferta.",
        )
        upsert_job(db_session, job1)
        upsert_job(db_session, job2)
        db_session.commit()

        jobs = load_active_jobs(session=db_session)
        canonical_ids = [j.job_id for j in jobs]
        assert "job_001" in canonical_ids

    def test_returns_empty_when_db_empty(self, db_session):
        jobs = load_active_jobs(session=db_session)
        assert jobs == []

    def test_reconstructed_job_is_valid_normalized_job(self, db_session):
        job = make_job()
        upsert_job(db_session, job)
        db_session.commit()

        loaded = load_active_jobs(session=db_session)
        j = loaded[0]
        assert j.job_title == job.job_title
        assert j.stack_keywords == job.stack_keywords
        assert j.modality == job.modality
        assert j.is_remote == job.is_remote
