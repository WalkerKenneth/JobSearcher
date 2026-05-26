"""JobFetcher: calls JSearch API with 24h caching, retry, and rate-limit handling."""

import hashlib
import json
from datetime import datetime, timedelta, timezone

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import JSEARCH_API_KEY, JOB_CACHE_TTL_SECONDS


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
# JSearch HTTP call with tenacity retry
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception_type((RateLimitError, httpx.ConnectError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _call_jsearch(params: dict) -> list[dict]:
    if not JSEARCH_API_KEY:
        raise ValueError("JSEARCH_API_KEY is not set — add it to .env")

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
        retry_after = int(response.headers.get("Retry-After", "10"))
        print(f"  [rate-limit] JSearch 429 — waiting {retry_after}s before retry")
        raise RateLimitError(f"Rate limit exceeded (Retry-After: {retry_after}s)")

    response.raise_for_status()
    return response.json().get("data", [])


def fetch_jsearch(params: dict, use_cache: bool = True) -> list[dict]:
    """
    Fetch jobs from JSearch. Returns raw job dicts.
    Caches results for JOB_CACHE_TTL_SECONDS to avoid burning rate-limit quota.
    Returns [] on empty results, rate-limit exhaustion, or network errors.
    """
    key = _cache_key(params)

    if use_cache:
        cached = _get_cached(key)
        if cached is not None:
            print(f"  [cache-hit] {len(cached)} jobs from cache (key: {key[:8]}…)")
            return cached

    try:
        results = _call_jsearch(params)
    except RateLimitError:
        print("  [WARNING] JSearch rate limit exhausted after retries — returning []")
        return []
    except httpx.HTTPStatusError as exc:
        print(f"  [WARNING] JSearch HTTP {exc.response.status_code}: {exc}")
        return []
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        print(f"  [WARNING] JSearch network error: {exc}")
        return []
    except ValueError as exc:
        print(f"  [ERROR] {exc}")
        raise

    if results:
        _set_cached(key, results)
        print(f"  [cache-set] {len(results)} jobs stored (TTL: {JOB_CACHE_TTL_SECONDS}s)")

    return results
