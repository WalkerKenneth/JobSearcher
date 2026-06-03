"""JobFetcher: calls JSearch API with 24h caching and HTTP error handling."""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from app.config import JSEARCH_API_KEY, JOB_CACHE_TTL_SECONDS

log = logging.getLogger(__name__)


class RateLimitError(Exception):
    pass


# ---------------------------------------------------------------------------
# Query cache (SQLite-backed, survives between runs)
# ---------------------------------------------------------------------------

def _cache_key(params: dict) -> str:
    canonical = json.dumps(params, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:24]


def _get_cached(key: str) -> list[dict] | None:
    from app.db.session import SessionLocal
    from app.db.models import QueryCache

    with SessionLocal() as session:
        entry = session.get(QueryCache, key)
        if entry is None:
            return None
        now = datetime.now(timezone.utc).isoformat()
        if entry.expires_at < now:
            session.delete(entry)
            session.commit()
            return None
        return json.loads(entry.raw_response)


def _set_cached(key: str, data: list[dict]) -> None:
    from app.db.session import SessionLocal
    from app.db.models import QueryCache

    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=JOB_CACHE_TTL_SECONDS)
    with SessionLocal() as session:
        entry = QueryCache(
            cache_key=key,
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
            raw_response=json.dumps(data),
        )
        session.merge(entry)
        session.commit()


# ---------------------------------------------------------------------------
# JSearch HTTP call — 3 intentos con backoff exponencial para errores de red.
# Los rate limits (429) se propagan inmediatamente: Celery gestiona el retry
# a nivel de tarea con countdown mayor que el backoff interno de red.
# ---------------------------------------------------------------------------

_NETWORK_ERRORS = (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout)
_RETRY_WAITS = (5, 10, 20)  # segundos entre intentos de red


def _call_jsearch(params: dict) -> list[dict]:
    if not JSEARCH_API_KEY:
        raise ValueError("JSEARCH_API_KEY is not set — add it to .env")

    last_exc: Exception | None = None
    for attempt, wait in enumerate(_RETRY_WAITS, start=1):
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    "https://jsearch.p.rapidapi.com/search",
                    params=params,
                    headers={
                        "X-RapidAPI-Key": JSEARCH_API_KEY,
                        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
                    },
                )

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                log.warning("JSearch 429 rate limit (intento %d/%d), Retry-After: %ds",
                            attempt, len(_RETRY_WAITS), retry_after)
                raise RateLimitError(f"Rate limit — Retry-After: {retry_after}s")

            response.raise_for_status()
            return response.json().get("data", [])

        except RateLimitError:
            raise  # No reintentar aquí: Celery schedula retry con countdown apropiado

        except _NETWORK_ERRORS as exc:
            last_exc = exc
            log.warning("JSearch error de red (intento %d/%d): %s — reintentando en %ds",
                        attempt, len(_RETRY_WAITS), exc, wait)
            if attempt < len(_RETRY_WAITS):
                time.sleep(wait)

    raise last_exc  # type: ignore[misc]


def fetch_jsearch(params: dict, use_cache: bool = True) -> list[dict]:
    """
    Busca empleos en JSearch. Devuelve lista de dicts crudos.
    Cachea resultados por JOB_CACHE_TTL_SECONDS para no consumir cuota.

    Lanza RateLimitError, httpx.HTTPStatusError o ConnectionError en caso de fallo
    para que Celery gestione retries a nivel de tarea.
    """
    key = _cache_key(params)

    if use_cache:
        cached = _get_cached(key)
        if cached is not None:
            log.info("Cache hit: %d empleos (key: %s…)", len(cached), key[:8])
            return cached

    results = _call_jsearch(params)

    if results:
        _set_cached(key, results)
        log.info("Obtenidos y cacheados %d empleos (TTL: %ds)", len(results), JOB_CACHE_TTL_SECONDS)

    return results
