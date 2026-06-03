#!/usr/bin/env python3
"""
Ingestion command — fetch and persist jobs for a student profile.

Usage:
    python ingest.py fixtures/profiles/junior_frontend.json
    python ingest.py --profile-id valentina_001 --no-cache
    python ingest.py fixtures/profiles/junior_frontend.json --dry-run

Requires JSEARCH_API_KEY in .env (copy .env.example → .env and fill the key).
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import dataclasses

from app.ingestion.normalizer import validate_job
from app.ingestion.repository import upsert_jobs
from app.pipeline import fetch_and_normalize
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
        "--no-cache", action="store_true",
        help="Bypass the 24h query cache and call the API directly",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch and normalise but do NOT write to the database",
    )
    args = parser.parse_args()

    if not args.profile and not args.profile_id:
        parser.error("Proporciona un archivo de perfil o usa --profile-id <id>")

    profile = _load_profile(args.profile, args.profile_id)

    print("=" * 60)
    print("JobSearcher — Ingesta de Oportunidades")
    print("=" * 60)
    print(f"Perfil : {profile['name']} ({profile['profile_id']})")
    print(f"Cohort : {profile.get('cohort', 'N/A')}")
    print(f"Modo   : {'dry-run (sin escritura)' if args.dry_run else 'live'}")
    print("-" * 60)

    jobs = fetch_and_normalize(profile, use_cache=not args.no_cache)
    if not jobs:
        print("\nSin resultados. Verifica JSEARCH_API_KEY y la query.")
        sys.exit(0)

    valid = [j for j in jobs if not validate_job(j)]
    rejected_count = len(jobs) - len(valid)
    if rejected_count:
        print(f"  ⚠  {rejected_count} rechazados por validación")
    print(f"  ✓  {len(valid)} válidos")

    if args.dry_run:
        print("\nDry-run — sin escritura en base de datos")
        print("Muestra de trabajos normalizados:")
        for job in valid[:3]:
            print(f"  [{job.seniority_signal}] {job.job_title} @ {job.company_name}")
            print(f"   URL: {job.apply_url}")
            print(f"   Stack: {job.stack_keywords}")
    else:
        stats = upsert_jobs(valid)
        print(f"\nResultado de ingesta:")
        print(f"  ✚ Nuevos (canónicos)      : {stats['inserted']}")
        print(f"  ↻ Actualizados (vistos)   : {stats['updated_seen']}")
        print(f"  ≈ Duplicados cross-source : {stats['marked_duplicate']}")
        print(f"  ✗ Rechazados              : {stats['rejected']}")
        total = stats["inserted"] + stats["updated_seen"] + stats["marked_duplicate"]
        print(f"\n  Total procesados: {total}")

    print("=" * 60)
    print("Ingesta completada.")


if __name__ == "__main__":
    main()
