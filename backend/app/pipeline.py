"""
Pipeline steps — one function per future Hermes handler boundary.

  fetch_and_normalize   → Hermes: search_task (fetch) + normalize_task
  ingest_for_profile    → llama a fetch_and_normalize y persiste
  recommend_for_profile → Hermes: score_task → delivery_task
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.delivery.payload import RecommendationPayload, build_recommendations
from app.delivery.repository import save_recommendations
from app.ingestion.fetcher import fetch_jsearch
from app.ingestion.normalizer import normalize_jsearch_batch
from app.ingestion.query_builder import build_jsearch_params_all
from app.ingestion.repository import IngestStats, load_active_jobs, upsert_jobs
from app.profiles.repository import load_profile
from app.schemas import NormalizedJob
from app.scoring.scorer import rank_jobs


def fetch_and_normalize(profile: dict, use_cache: bool = True) -> list[NormalizedJob]:
    """
    Busca trabajos en JSearch para todas las combinaciones rol×tech del perfil y los normaliza.
    Hermes: boundary entre search_task y normalize_task.
    """
    all_params = build_jsearch_params_all(profile)
    fetched_at = datetime.now(timezone.utc).isoformat()
    raw_jobs: list[dict] = []
    for params in all_params:
        raw_jobs.extend(fetch_jsearch(params, use_cache=use_cache))
    return normalize_jsearch_batch(raw_jobs, fetched_at) if raw_jobs else []


def ingest_for_profile(profile: dict, use_cache: bool = True) -> IngestStats:
    """
    Fetch, normaliza y persiste trabajos para un perfil.
    Hermes dividirá esto en: search_task → normalize_task → persist.
    """
    jobs = fetch_and_normalize(profile, use_cache=use_cache)
    if not jobs:
        return {"inserted": 0, "updated_seen": 0, "marked_duplicate": 0, "rejected": 0}
    return upsert_jobs(jobs)


def recommend_for_profile(profile_id: str, top_n: int = 10) -> list[RecommendationPayload]:
    """
    Scoreea los jobs activos contra un perfil almacenado y persiste las recomendaciones.
    Hermes dividirá esto en: score_task → delivery_task.
    Lanza ValueError si el profile_id no existe.
    """
    profile = load_profile(profile_id)
    if profile is None:
        raise ValueError(f"Profile '{profile_id}' not found")

    jobs = load_active_jobs()
    if not jobs:
        return []

    matches = rank_jobs(jobs, profile)
    payloads = build_recommendations(matches, jobs, profile_id, top_n=top_n)
    save_recommendations(payloads)
    return payloads
