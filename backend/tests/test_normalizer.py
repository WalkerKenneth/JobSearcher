"""Tests for JobNormalizer: JSearch raw → NormalizedJob."""
import json
from pathlib import Path

import pytest

from app.ingestion.normalizer import (
    build_dedup_key,
    extract_stack_keywords,
    infer_modality,
    infer_seniority,
    normalize_jsearch,
    normalize_url,
    validate_job,
)

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "jobs"
FETCHED_AT = "2026-05-25T10:00:00+00:00"


# ---------------------------------------------------------------------------
# Fixtures loading
# ---------------------------------------------------------------------------

@pytest.fixture
def jsearch_raw():
    return json.loads((FIXTURES / "jsearch_raw_example.json").read_text())


@pytest.fixture
def jsearch_job_remote(jsearch_raw):
    return jsearch_raw["data"][0]  # job_is_remote=true, no salary


@pytest.fixture
def jsearch_job_hybrid(jsearch_raw):
    return jsearch_raw["data"][1]  # job_is_remote=false, has salary


# ---------------------------------------------------------------------------
# normalize_jsearch
# ---------------------------------------------------------------------------

class TestNormalizeJSearch:
    def test_maps_basic_fields(self, jsearch_job_remote):
        job = normalize_jsearch(jsearch_job_remote, FETCHED_AT)

        assert job.source == "jsearch"
        assert job.job_id == "jsearch_cr_frontend_001"
        assert job.job_title == "Junior Frontend Developer"
        assert job.company_name == "TechNova CR"
        assert job.location_city == "San José"
        assert job.location_country == "CR"
        assert job.is_remote is True
        assert "remote" in job.modality
        assert job.fetched_at == FETCHED_AT
        assert job.apply_url.startswith("https://")

    def test_null_salary_fields(self, jsearch_job_remote):
        job = normalize_jsearch(jsearch_job_remote, FETCHED_AT)

        assert job.salary_min is None
        assert job.salary_max is None
        assert job.salary_currency is None
        assert job.salary_period is None

    def test_salary_fields_present(self, jsearch_job_hybrid):
        job = normalize_jsearch(jsearch_job_hybrid, FETCHED_AT)

        assert job.salary_min == 650000
        assert job.salary_max == 850000
        assert job.salary_currency == "CRC"
        assert job.salary_period == "monthly"

    def test_description_raw_not_empty(self, jsearch_job_remote):
        job = normalize_jsearch(jsearch_job_remote, FETCHED_AT)
        assert len(job.description_raw) >= 50

    def test_qualifications_raw_empty_for_jsearch(self, jsearch_job_remote):
        # JSearch never populates job_highlights.Qualifications reliably
        job = normalize_jsearch(jsearch_job_remote, FETCHED_AT)
        assert job.qualifications_raw == []

    def test_raw_response_preserved(self, jsearch_job_remote):
        job = normalize_jsearch(jsearch_job_remote, FETCHED_AT)
        assert job.raw_response == jsearch_job_remote

    def test_generates_job_id_when_missing(self):
        raw = {
            "employer_name": "ACME",
            "job_title": "Dev",
            "job_country": "CR",
            "job_description": "x" * 60,
            "job_apply_link": "https://example.com/job/1",
            "job_is_remote": False,
        }
        job = normalize_jsearch(raw, FETCHED_AT)
        assert job.job_id  # non-empty generated hash


# ---------------------------------------------------------------------------
# URL normalisation
# ---------------------------------------------------------------------------

class TestNormalizeUrl:
    def test_strips_utm_params(self):
        url = "https://example.com/job?id=1&utm_source=google&utm_campaign=jobs"
        assert normalize_url(url) == "https://example.com/job?id=1"

    def test_strips_ref_param(self):
        url = "https://example.com/job?id=5&ref=jsearch"
        assert normalize_url(url) == "https://example.com/job?id=5"

    def test_removes_trailing_slash(self):
        assert normalize_url("https://example.com/job/123/") == "https://example.com/job/123"

    def test_preserves_non_tracking_params(self):
        url = "https://example.com/job?id=99&lang=es"
        result = normalize_url(url)
        assert "id=99" in result
        assert "lang=es" in result


# ---------------------------------------------------------------------------
# Dedup key
# ---------------------------------------------------------------------------

class TestBuildDedupKey:
    def test_case_insensitive(self):
        k1 = build_dedup_key("TechNova CR", "Junior Frontend Developer", "CR")
        k2 = build_dedup_key("technova cr", "JUNIOR FRONTEND DEVELOPER", "cr")
        assert k1 == k2

    def test_ignores_company_suffix(self):
        k1 = build_dedup_key("Startup Tica S.A.", "Backend Dev", "Costa Rica")
        k2 = build_dedup_key("Startup Tica", "Backend Dev", "Costa Rica")
        assert k1 == k2

    def test_different_companies_produce_different_keys(self):
        k1 = build_dedup_key("CompanyA", "Junior Dev", "CR")
        k2 = build_dedup_key("CompanyB", "Junior Dev", "CR")
        assert k1 != k2

    def test_returns_16_char_hex(self):
        key = build_dedup_key("Test Corp", "Developer", "CR")
        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)


# ---------------------------------------------------------------------------
# Stack keyword extraction
# ---------------------------------------------------------------------------

class TestExtractStackKeywords:
    def test_finds_common_tech(self):
        desc = "We need React, Node.js and PostgreSQL experience."
        keywords = extract_stack_keywords(desc)
        lower = [k.lower() for k in keywords]
        assert "react" in lower
        assert "node.js" in lower
        assert "postgresql" in lower

    def test_case_insensitive_detection(self):
        desc = "REACT and JAVASCRIPT are required."
        keywords = [k.lower() for k in extract_stack_keywords(desc)]
        assert "react" in keywords
        assert "javascript" in keywords

    def test_no_duplicates(self):
        desc = "React React React React"
        keywords = extract_stack_keywords(desc)
        assert len(keywords) == len(set(keywords))

    def test_empty_description(self):
        assert extract_stack_keywords("") == []


# ---------------------------------------------------------------------------
# Seniority inference
# ---------------------------------------------------------------------------

class TestInferSeniority:
    def test_detects_junior_from_title(self):
        assert infer_seniority("Junior Frontend Developer", "") == "junior"

    def test_detects_senior_from_description(self):
        assert infer_seniority("Developer", "We need a senior engineer with 5+ años.") == "senior"

    def test_detects_mid_level(self):
        assert infer_seniority("Developer", "mid-level, 2 a 3 años de experiencia") == "mid"

    def test_unknown_when_no_signal(self):
        assert infer_seniority("Developer", "Build web applications.") == "unknown"


# ---------------------------------------------------------------------------
# Modality inference
# ---------------------------------------------------------------------------

class TestInferModality:
    def test_remote_flag_true(self):
        assert infer_modality(True, "fully remote position") == ["remote"]

    def test_remote_plus_hybrid_mention(self):
        modality = infer_modality(True, "trabajo remoto, modalidad híbrida")
        assert "remote" in modality
        assert "hybrid" in modality

    def test_on_site_when_not_remote(self):
        assert infer_modality(False, "office in San José") == ["on-site"]

    def test_hybrid_detected_from_description(self):
        modality = infer_modality(False, "Modalidad híbrida, 3 días en oficina.")
        assert modality == ["hybrid"]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidateJob:
    def test_valid_job_returns_no_errors(self, jsearch_job_remote):
        job = normalize_jsearch(jsearch_job_remote, FETCHED_AT)
        assert validate_job(job) == []

    def test_invalid_apply_url_detected(self, jsearch_job_remote):
        job = normalize_jsearch(jsearch_job_remote, FETCHED_AT)
        job.apply_url = "http://not-secure.com"
        errors = validate_job(job)
        assert any("apply_url" in e for e in errors)

    def test_short_description_rejected(self, jsearch_job_remote):
        job = normalize_jsearch(jsearch_job_remote, FETCHED_AT)
        job.description_raw = "Too short"
        errors = validate_job(job)
        assert any("description_raw" in e for e in errors)

    def test_future_posted_at_rejected(self, jsearch_job_remote):
        job = normalize_jsearch(jsearch_job_remote, FETCHED_AT)
        job.posted_at = "2099-01-01T00:00:00+00:00"
        errors = validate_job(job)
        assert any("future" in e for e in errors)
