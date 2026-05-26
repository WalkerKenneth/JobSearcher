"""
Tests for 3-level deduplication in JobRepository.

Level 1 — apply_url match
Level 2 — source + job_id match
Level 3 — dedup_key cross-source match
"""
import json
from datetime import datetime, timezone

import pytest

from app.db.models import JobPosting, RawSnapshot
from app.ingestion.repository import upsert_job
from app.schemas import NormalizedJob

NOW = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def make_job(
    *,
    job_id: str = "job-001",
    source: str = "jsearch",
    company: str = "TechNova CR",
    title: str = "Junior Frontend Developer",
    country: str = "Costa Rica",
    apply_url: str = "https://linkedin.com/jobs/1001",
    salary_min: float | None = None,
    salary_max: float | None = None,
    qualifications: list[str] | None = None,
) -> NormalizedJob:
    return NormalizedJob(
        job_id=job_id,
        source=source,
        fetched_at=NOW,
        job_title=title,
        company_name=company,
        location_city="San José",
        location_country=country,
        is_remote=True,
        modality=["remote"],
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency="CRC" if salary_min else None,
        salary_period="monthly" if salary_min else None,
        description_raw="We need a junior React and JavaScript developer. Remote team, great culture.",
        qualifications_raw=qualifications or [],
        posted_at=None,
        apply_url=apply_url,
        stack_keywords=["react", "javascript"],
        seniority_signal="junior",
        raw_response={"job_id": job_id, "source": source},
    )


# ---------------------------------------------------------------------------
# Fresh insert
# ---------------------------------------------------------------------------

class TestFreshInsert:
    def test_new_job_inserted_as_canonical(self, db_session):
        job = make_job()
        _, action = upsert_job(db_session, job)
        db_session.commit()

        assert action == "inserted"
        row = db_session.get(JobPosting, job.job_id)
        assert row is not None
        assert row.canonical_id is None
        assert row.fetch_count == 1

    def test_raw_snapshot_created(self, db_session):
        job = make_job()
        job_id, _ = upsert_job(db_session, job)
        db_session.commit()

        snap = db_session.query(RawSnapshot).filter_by(job_id=job_id).first()
        assert snap is not None
        assert snap.source == "jsearch"
        assert json.loads(snap.raw_response)["job_id"] == "job-001"

    def test_two_distinct_jobs_both_inserted(self, db_session):
        job_a = make_job(job_id="job-A", apply_url="https://linkedin.com/jobs/A")
        job_b = make_job(
            job_id="job-B",
            company="OtherCorp",
            title="Node.js Developer",
            apply_url="https://linkedin.com/jobs/B",
        )
        upsert_job(db_session, job_a)
        upsert_job(db_session, job_b)
        db_session.commit()

        assert db_session.query(JobPosting).count() == 2


# ---------------------------------------------------------------------------
# Level 1 — apply_url dedup
# ---------------------------------------------------------------------------

class TestLevel1ApplyUrl:
    def test_same_url_updates_seen_not_inserts(self, db_session):
        job1 = make_job(job_id="job-001", apply_url="https://example.com/apply/1")
        job2 = make_job(job_id="job-002", apply_url="https://example.com/apply/1")  # same URL

        _, a1 = upsert_job(db_session, job1)
        _, a2 = upsert_job(db_session, job2)
        db_session.commit()

        assert a1 == "inserted"
        assert a2 == "updated_seen"
        assert db_session.query(JobPosting).count() == 1

    def test_fetch_count_increments(self, db_session):
        url = "https://example.com/apply/99"
        job = make_job(apply_url=url)
        upsert_job(db_session, job)
        upsert_job(db_session, make_job(job_id="job-x", apply_url=url))
        upsert_job(db_session, make_job(job_id="job-y", apply_url=url))
        db_session.commit()

        row = db_session.query(JobPosting).filter_by(apply_url=url).one()
        assert row.fetch_count == 3

    def test_snapshot_added_on_update(self, db_session):
        url = "https://example.com/apply/55"
        upsert_job(db_session, make_job(apply_url=url))
        upsert_job(db_session, make_job(job_id="job-b", apply_url=url))
        db_session.commit()

        snaps = db_session.query(RawSnapshot).all()
        assert len(snaps) == 2

    def test_url_tracking_params_stripped(self, db_session):
        url_a = "https://example.com/job?id=7&utm_source=google"
        url_b = "https://example.com/job?id=7&utm_medium=cpc"  # same base, different tracking
        from app.ingestion.normalizer import normalize_url

        job1 = make_job(apply_url=normalize_url(url_a))
        job2 = make_job(job_id="job-b", apply_url=normalize_url(url_b))

        upsert_job(db_session, job1)
        _, action = upsert_job(db_session, job2)
        db_session.commit()

        assert action == "updated_seen"
        assert db_session.query(JobPosting).count() == 1


# ---------------------------------------------------------------------------
# Level 2 — source + job_id dedup
# ---------------------------------------------------------------------------

class TestLevel2SourceJobId:
    def test_same_source_and_id_updates_seen(self, db_session):
        job1 = make_job(job_id="jsrc-100", apply_url="https://example.com/a")
        job2 = make_job(job_id="jsrc-100", apply_url="https://example.com/b")  # same id, different URL

        upsert_job(db_session, job1)
        _, action = upsert_job(db_session, job2)
        db_session.commit()

        assert action == "updated_seen"
        assert db_session.query(JobPosting).count() == 1

    def test_different_source_same_id_proceeds_to_level3(self, db_session):
        job_jsearch = make_job(job_id="shared-001", source="jsearch",
                                apply_url="https://example.com/jsearch")
        job_serp = make_job(job_id="shared-001", source="serpapi",
                             apply_url="https://example.com/serpapi")

        upsert_job(db_session, job_jsearch)
        _, action = upsert_job(db_session, job_serp)
        db_session.commit()

        # Should NOT be updated_seen — different source means Level 2 doesn't match;
        # falls through to Level 3 (marked_duplicate because same company+title+country)
        assert action in ("marked_duplicate", "inserted")


# ---------------------------------------------------------------------------
# Level 3 — dedup_key cross-source
# ---------------------------------------------------------------------------

class TestLevel3DedupKey:
    def test_cross_source_same_job_marked_duplicate(self, db_session):
        job_jsearch = make_job(
            source="jsearch",
            job_id="jid-001",
            apply_url="https://linkedin.com/jobs/001",
        )
        job_serp = make_job(
            source="serpapi",
            job_id="sid-001",
            apply_url="https://glassdoor.com/job/001",  # different URL
        )

        _, a1 = upsert_job(db_session, job_jsearch)
        _, a2 = upsert_job(db_session, job_serp)
        db_session.commit()

        assert a1 == "inserted"
        assert a2 == "marked_duplicate"

    def test_canonical_tracks_duplicate_ids(self, db_session):
        job1 = make_job(source="jsearch", job_id="jid-A",
                         apply_url="https://link.a/job")
        job2 = make_job(source="serpapi", job_id="sid-A",
                         apply_url="https://link.b/job")

        upsert_job(db_session, job1)
        _, _ = upsert_job(db_session, job2)
        db_session.commit()

        canonical = db_session.query(JobPosting).filter_by(canonical_id=None).one()
        dup_ids = json.loads(canonical.duplicate_ids)
        assert len(dup_ids) == 1

    def test_richer_job_enriches_canonical(self, db_session):
        job_poor = make_job(
            source="jsearch", job_id="poor-001",
            apply_url="https://example.com/poor",
            salary_min=None, salary_max=None,
        )
        job_rich = make_job(
            source="serpapi", job_id="rich-001",
            apply_url="https://example.com/rich",
            salary_min=800000, salary_max=1200000,
            qualifications=["Node.js", "PostgreSQL"],
        )

        upsert_job(db_session, job_poor)
        upsert_job(db_session, job_rich)
        db_session.commit()

        # Canonical row (first inserted jsearch job) must have been enriched with
        # salary data from the richer serpapi job via merge
        canonical = db_session.query(JobPosting).filter_by(canonical_id=None).one()
        assert canonical.salary_min == 800000
        assert canonical.salary_max == 1200000
        assert json.loads(canonical.qualifications_raw) == ["Node.js", "PostgreSQL"]


# ---------------------------------------------------------------------------
# Idempotency — repeated runs must not create duplicates
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_same_batch_twice_no_duplicates(self, db_session):
        jobs = [
            make_job(job_id=f"job-{i:03d}", apply_url=f"https://example.com/job/{i}")
            for i in range(5)
        ]

        for job in jobs:
            upsert_job(db_session, job)
        db_session.commit()

        # Run the exact same batch again
        for job in jobs:
            upsert_job(db_session, job)
        db_session.commit()

        assert db_session.query(JobPosting).count() == 5

    def test_fetch_count_reflects_repeat_runs(self, db_session):
        job = make_job()
        upsert_job(db_session, job)
        upsert_job(db_session, job)
        upsert_job(db_session, job)
        db_session.commit()

        row = db_session.get(JobPosting, job.job_id)
        assert row.fetch_count == 3

    def test_spec_example_N_jobs_stored_with_source_and_date(self, db_session):
        """Acceptance: N jobs stored, each with source and fetched_at."""
        N = 10
        jobs = [
            make_job(job_id=f"job-{i:03d}", apply_url=f"https://example.com/job/{i}")
            for i in range(N)
        ]
        for job in jobs:
            upsert_job(db_session, job)
        db_session.commit()

        rows = db_session.query(JobPosting).all()
        assert len(rows) == N
        for row in rows:
            assert row.source in ("jsearch", "serpapi")
            assert row.fetched_at  # non-empty ISO datetime
            assert row.first_seen
