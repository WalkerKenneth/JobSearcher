"""
Integration tests for the full ingestion pipeline (mocked HTTP).
Validates the spec acceptance criteria:
  - N >= 1 jobs fetched and stored with source + date
  - Re-running does not create duplicates
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, JobPosting
from app.db.session import create_indexes
from app.ingestion.normalizer import normalize_jsearch_batch
from app.ingestion.query_builder import build_jsearch_params
from app.ingestion.repository import upsert_jobs

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# DB fixture that wires upsert_jobs to an in-memory database
# ---------------------------------------------------------------------------

@pytest.fixture()
def isolated_db(monkeypatch):
    """
    Replace the real SessionLocal with one backed by an in-memory SQLite.
    Patches app.ingestion.repository.SessionLocal so upsert_jobs uses test DB.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    create_indexes(engine)
    TestSession = sessionmaker(bind=engine, autoflush=True, autocommit=False)

    monkeypatch.setattr("app.ingestion.repository.SessionLocal", TestSession)
    yield TestSession
    engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_jsearch_fixture() -> list[dict]:
    raw = json.loads((FIXTURES / "jobs" / "jsearch_raw_example.json").read_text())
    return raw["data"]


def _load_profile(name: str) -> dict:
    return json.loads((FIXTURES / "profiles" / name).read_text())


# ---------------------------------------------------------------------------
# QueryBuilder tests
# ---------------------------------------------------------------------------

class TestQueryBuilder:
    def test_builds_query_from_frontend_profile(self):
        profile = _load_profile("junior_frontend.json")
        params = build_jsearch_params(profile)

        assert "junior" in params["query"].lower()
        assert params["location"] == "Costa Rica"
        assert params["date_posted"] == "month"
        assert params["num_pages"] == "2"

    def test_remote_only_when_hybrid_excluded(self):
        profile = _load_profile("junior_frontend.json")
        profile["restrictions"]["excluded_modalities"] = ["on-site", "hybrid"]
        params = build_jsearch_params(profile)
        assert params["remote_jobs_only"] == "true"

    def test_remote_not_forced_when_hybrid_accepted(self):
        profile = _load_profile("junior_frontend.json")
        # junior_frontend only excludes on-site, not hybrid
        params = build_jsearch_params(profile)
        assert params["remote_jobs_only"] == "false"


# ---------------------------------------------------------------------------
# Full pipeline: fixture → normalise → persist
# ---------------------------------------------------------------------------

class TestIngestionPipeline:
    def test_jobs_stored_with_source_and_date(self, isolated_db):
        raw_jobs = _load_jsearch_fixture()
        from datetime import datetime, timezone
        fetched_at = datetime.now(timezone.utc).isoformat()

        normalized = normalize_jsearch_batch(raw_jobs, fetched_at)
        stats = upsert_jobs(normalized)

        with isolated_db() as session:
            rows = session.query(JobPosting).all()

        assert len(rows) >= 1
        for row in rows:
            assert row.source == "jsearch"
            assert row.fetched_at  # non-empty
            assert row.first_seen

        # Spec: at least 1 inserted
        assert stats["inserted"] >= 1
        assert stats["rejected"] == 0

    def test_repeated_run_does_not_duplicate(self, isolated_db):
        raw_jobs = _load_jsearch_fixture()
        from datetime import datetime, timezone
        fetched_at = datetime.now(timezone.utc).isoformat()

        normalized = normalize_jsearch_batch(raw_jobs, fetched_at)

        stats1 = upsert_jobs(normalized)
        stats2 = upsert_jobs(normalized)  # exact same batch

        with isolated_db() as session:
            total = session.query(JobPosting).count()

        # Second run must not create new canonical rows
        assert total == stats1["inserted"] + stats1["marked_duplicate"]
        assert stats2["inserted"] == 0
        assert stats2["updated_seen"] == stats1["inserted"] + stats1["marked_duplicate"]

    def test_validation_rejects_malformed_jobs(self, isolated_db):
        raw_jobs = _load_jsearch_fixture()
        from datetime import datetime, timezone
        fetched_at = datetime.now(timezone.utc).isoformat()

        # Inject a malformed job
        bad_job = dict(raw_jobs[0])
        bad_job["job_id"] = "bad-001"
        bad_job["job_apply_link"] = "http://insecure.com/job"  # http, not https
        bad_job["job_description"] = "short"  # < 50 chars

        normalized = normalize_jsearch_batch([bad_job], fetched_at)
        stats = upsert_jobs(normalized)

        assert stats["rejected"] == 1
        assert stats["inserted"] == 0

    def test_mocked_api_returns_fixture_results(self, isolated_db):
        """End-to-end: mock fetch_jsearch to return fixture, then ingest."""
        raw_jobs = _load_jsearch_fixture()
        profile = _load_profile("junior_frontend.json")

        with patch("app.ingestion.fetcher.fetch_jsearch", return_value=raw_jobs):
            from app.ingestion.fetcher import fetch_jsearch
            params = build_jsearch_params(profile)
            result = fetch_jsearch(params, use_cache=False)

        assert len(result) == len(raw_jobs)

        from datetime import datetime, timezone
        fetched_at = datetime.now(timezone.utc).isoformat()
        normalized = normalize_jsearch_batch(result, fetched_at)
        stats = upsert_jobs(normalized)

        assert stats["inserted"] >= 1
