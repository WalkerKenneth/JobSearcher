#!/usr/bin/env python3
"""
Recommendation command — score and deliver job recommendations for a student profile.

Usage:
    python recommend.py fixtures/profiles/junior_frontend.json
    python recommend.py fixtures/profiles/junior_frontend.json --top 5
    python recommend.py fixtures/profiles/junior_frontend.json --format json

Reads active jobs from the local DB (run ingest.py first).
Saves recommendations to DB and writes data/recommendations_{profile_id}.json.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.delivery.payload import build_recommendations
from app.delivery.repository import save_recommendations
from app.ingestion.repository import load_active_jobs
from app.schemas import StudentProfile
from app.scoring.scorer import rank_jobs


def _load_profile(path: str) -> StudentProfile:
    p = Path(path)
    if not p.exists():
        print(f"Error: perfil no encontrado: {p}")
        sys.exit(1)
    return StudentProfile.from_dict(json.loads(p.read_text(encoding="utf-8")))


def _print_separator(char: str = "─", width: int = 60) -> None:
    print(char * width)


def _score_bar(score: int, width: int = 20) -> str:
    filled = round(score / 100 * width)
    return f"[{'█' * filled}{'░' * (width - filled)}] {score:3d}"


def _print_table(payloads: list) -> None:
    for i, p in enumerate(payloads, 1):
        _print_separator()
        print(f"#{i:02d}  {p.title}")
        print(f"     {p.company}  |  {p.location}")
        print(f"     Score: {_score_bar(p.match_score)}")
        print(f"     Acción: {p.next_action}")
        print(f"     Link:   {p.apply_url}")
        if p.match_reasons:
            print(f"     ✓ {'; '.join(p.match_reasons[:3])}")
        if p.gaps:
            print(f"     ✗ {'; '.join(p.gaps[:2])}")
        print(f"     ID: {p.rec_id}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generar recomendaciones de empleo para un perfil Lyfter.",
    )
    parser.add_argument("profile", help="Ruta al JSON del StudentProfile")
    parser.add_argument(
        "--top", type=int, default=10, metavar="N",
        help="Número máximo de recomendaciones (default: 10)",
    )
    parser.add_argument(
        "--format", choices=["table", "json"], default="table",
        help="Formato de salida: table (default) o json",
    )
    args = parser.parse_args()

    profile = _load_profile(args.profile)

    _print_separator("=")
    print("JobSearcher — Recomendaciones (subtarea 8)")
    _print_separator("=")
    print(f"Perfil : {profile.name} ({profile.profile_id})")
    print(f"Top    : {args.top}")
    _print_separator()

    # ── Step 1: Load stored jobs ───────────────────────────────────────
    print("[1] Cargando jobs activos desde DB...")
    jobs = load_active_jobs()
    print(f"    {len(jobs)} jobs encontrados")

    if not jobs:
        print("\nSin jobs en la base de datos. Ejecuta ingest.py primero.")
        sys.exit(0)

    # ── Step 2: Score and rank ─────────────────────────────────────────
    print(f"\n[2] Scoring y ranking ({len(jobs)} jobs)...")
    matches = rank_jobs(jobs, profile)
    passing = [m for m in matches if m.hard_filters_passed]
    filtered_out = len(matches) - len(passing)
    print(f"    ✓ {len(passing)} pasan filtros obligatorios")
    if filtered_out:
        print(f"    ✗ {filtered_out} descartados por filtros obligatorios")

    # ── Step 3: Build payloads ─────────────────────────────────────────
    payloads = build_recommendations(matches, jobs, profile.profile_id, top_n=args.top)
    print(f"    → {len(payloads)} recomendaciones generadas")

    if not payloads:
        print("\nSin recomendaciones para este perfil con los jobs disponibles.")
        sys.exit(0)

    # ── Step 4: Persist to DB ──────────────────────────────────────────
    print(f"\n[3] Guardando en DB...")
    stats = save_recommendations(payloads)
    print(f"    ✚ Nuevas: {stats['inserted']}  ↻ Actualizadas: {stats['updated']}")

    # ── Step 5: Write JSON output ──────────────────────────────────────
    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"recommendations_{profile.profile_id}.json"
    out_path.write_text(
        json.dumps([p.to_dict() for p in payloads], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"    JSON: {out_path}")

    # ── Step 6: Display ────────────────────────────────────────────────
    print()
    _print_separator("=")
    print(f"TOP {len(payloads)} RECOMENDACIONES — {profile.name}")
    _print_separator("=")

    if args.format == "json":
        print(json.dumps([p.to_dict() for p in payloads], indent=2, ensure_ascii=False))
    else:
        _print_table(payloads)

    _print_separator("=")
    print(f"\nPara registrar feedback:")
    print(f"  python feedback.py <rec_id> <seen|applied|discarded|needs_coach>")


if __name__ == "__main__":
    main()
