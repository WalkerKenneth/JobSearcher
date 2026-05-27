#!/usr/bin/env python3
"""
Ingestion command — fetch and persist jobs for a student profile.

Usage:
    python ingest.py fixtures/profiles/junior_frontend.json
    python ingest.py fixtures/profiles/junior_fullstack.json --no-cache
    python ingest.py fixtures/profiles/junior_frontend.json --dry-run

Requires JSEARCH_API_KEY in .env (copy .env.example → .env and fill the key).
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend/ is in sys.path when executed from any cwd
sys.path.insert(0, str(Path(__file__).parent))

import dataclasses

from app.ingestion.fetcher import fetch_jsearch
from app.ingestion.normalizer import normalize_jsearch_batch, validate_job
from app.ingestion.query_builder import build_jsearch_params
from app.ingestion.repository import upsert_jobs
from app.profiles.repository import load_profile


def _load_profile(path: str | None, profile_id: str | None) -> dict:
    if profile_id:
        profile = load_profile(profile_id)
        if profile is None:
            print(f"Error: perfil '{profile_id}' no encontrado en la base de datos.")
            print("Importa el perfil primero: python profiles.py import <archivo.json>")
            sys.exit(1)
        return dataclasses.asdict(profile)
    p = Path(path)
    if not p.exists():
        print(f"Error: profile not found: {p}")
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def _print_separator(char: str = "─", width: int = 60) -> None:
    print(char * width)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest job postings for a Lyfter student profile.",
    )
    parser.add_argument(
        "profile", nargs="?", default=None,
        help="Ruta a un JSON de StudentProfile (o usa --profile-id)",
    )
    parser.add_argument(
        "--profile-id", metavar="ID",
        help="ID del perfil almacenado en la base de datos",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass the 24h query cache and call the API directly",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and normalise but do NOT write to the database",
    )
    args = parser.parse_args()

    if not args.profile and not args.profile_id:
        parser.error("Proporciona un archivo de perfil o usa --profile-id <id>")

    profile = _load_profile(args.profile, args.profile_id)

    _print_separator("=")
    print("JobSearcher — Ingesta de Oportunidades (subtarea 6)")
    _print_separator("=")
    print(f"Perfil : {profile['name']} ({profile['profile_id']})")
    print(f"Cohort : {profile.get('cohort', 'N/A')}")
    print(f"Modo   : {'dry-run (sin escritura)' if args.dry_run else 'live'}")
    _print_separator()

    # ── Step 1: Build query ────────────────────────────────────────────
    params = build_jsearch_params(profile)
    print(f"[1] QueryBuilder")
    print(f"    query    : \"{params['query']}\"")
    print(f"    location : {params['location']}")
    print(f"    remote   : {params['remote_jobs_only']}")
    print(f"    pages    : {params['num_pages']}")

    # ── Step 2: Fetch from JSearch ─────────────────────────────────────
    print(f"\n[2] JobFetcher → JSearch API {'(bypass cache)' if args.no_cache else '(cache: 24h)'}")
    raw_jobs = fetch_jsearch(params, use_cache=not args.no_cache)
    print(f"    {len(raw_jobs)} resultados obtenidos")

    if not raw_jobs:
        print("\nSin resultados. Verifica JSEARCH_API_KEY y la query.")
        sys.exit(0)

    # ── Step 3: Normalise ──────────────────────────────────────────────
    fetched_at = datetime.now(timezone.utc).isoformat()
    jobs = normalize_jsearch_batch(raw_jobs, fetched_at)
    print(f"\n[3] JobNormalizer → {len(jobs)} NormalizedJob objects")

    # Validation summary
    valid, rejected = [], []
    for job in jobs:
        errs = validate_job(job)
        if errs:
            rejected.append((job, errs))
        else:
            valid.append(job)

    if rejected:
        print(f"    ⚠  {len(rejected)} rechazados por validación:")
        for job, errs in rejected:
            print(f"       {job.job_id}: {errs}")

    print(f"    ✓  {len(valid)} válidos para persistir")

    # ── Step 4: Persist (unless dry-run) ──────────────────────────────
    if args.dry_run:
        print("\n[4] Dry-run — sin escritura en base de datos")
        print("    Muestra de trabajos normalizados:")
        for job in valid[:3]:
            print(f"      [{job.seniority_signal}] {job.job_title} @ {job.company_name}")
            print(f"       URL: {job.apply_url}")
            print(f"       Stack: {job.stack_keywords}")
    else:
        print(f"\n[4] JobRepository → persistiendo {len(valid)} trabajos")
        stats = upsert_jobs(valid)

        _print_separator()
        print("Resultado de ingesta:")
        print(f"  ✚ Nuevos (canónicos)    : {stats['inserted']}")
        print(f"  ↻ Actualizados (vistos)  : {stats['updated_seen']}")
        print(f"  ≈ Duplicados cross-source : {stats['marked_duplicate']}")
        print(f"  ✗ Rechazados             : {stats['rejected']}")
        total = stats["inserted"] + stats["updated_seen"] + stats["marked_duplicate"]
        print(f"\n  Total procesados: {total} (+ {stats['rejected']} rechazados)")

    _print_separator("=")
    print("Ingesta completada.")


if __name__ == "__main__":
    main()
