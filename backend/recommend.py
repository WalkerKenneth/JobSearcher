#!/usr/bin/env python3
"""
Recommendation command — score and deliver job recommendations for a student profile.

Usage:
    python recommend.py fixtures/profiles/junior_frontend.json
    python recommend.py --profile-id valentina_001 --top 5
    python recommend.py --profile-id valentina_001 --format json

Si se pasa un archivo JSON, el perfil se importa automáticamente a la DB antes de recomendar.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.pipeline import recommend_for_profile
from app.profiles.repository import upsert_profile
from app.schemas import StudentProfile


def _resolve_profile_id(path: str | None, profile_id: str | None) -> str:
    """Devuelve el profile_id a usar. Si se pasa un archivo, lo importa a la DB primero."""
    if profile_id:
        return profile_id
    p = Path(path)
    if not p.exists():
        print(f"Error: perfil no encontrado: {p}")
        sys.exit(1)
    profile = StudentProfile.from_dict(json.loads(p.read_text(encoding="utf-8")))
    upsert_profile(profile)
    return profile.profile_id


def _score_bar(score: int, width: int = 20) -> str:
    filled = round(score / 100 * width)
    return f"[{'█' * filled}{'░' * (width - filled)}] {score:3d}"


def _print_table(payloads: list) -> None:
    for i, p in enumerate(payloads, 1):
        print("-" * 60)
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
    parser.add_argument(
        "profile", nargs="?", default=None,
        help="Ruta al JSON del StudentProfile (o usa --profile-id)",
    )
    parser.add_argument(
        "--profile-id", metavar="ID",
        help="ID del perfil almacenado en la base de datos",
    )
    parser.add_argument(
        "--top", type=int, default=10, metavar="N",
        help="Número máximo de recomendaciones (default: 10)",
    )
    parser.add_argument(
        "--format", choices=["table", "json"], default="table",
        help="Formato de salida: table (default) o json",
    )
    args = parser.parse_args()

    if not args.profile and not args.profile_id:
        parser.error("Proporciona un archivo de perfil o usa --profile-id <id>")

    profile_id = _resolve_profile_id(args.profile, args.profile_id)

    print("=" * 60)
    print("JobSearcher — Recomendaciones")
    print("=" * 60)
    print(f"Perfil : {profile_id}")
    print(f"Top    : {args.top}")
    print("-" * 60)

    try:
        payloads = recommend_for_profile(profile_id, top_n=args.top)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    if not payloads:
        print("\nSin recomendaciones para este perfil con los jobs disponibles.")
        print("Ejecuta ingest.py primero para cargar ofertas.")
        sys.exit(0)

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"recommendations_{profile_id}.json"
    out_path.write_text(
        json.dumps([p.to_dict() for p in payloads], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print(f"TOP {len(payloads)} RECOMENDACIONES — {profile_id}")
    print("=" * 60)

    if args.format == "json":
        print(json.dumps([p.to_dict() for p in payloads], indent=2, ensure_ascii=False))
    else:
        _print_table(payloads)

    print("=" * 60)
    print(f"\nPara registrar feedback:")
    print(f"  python feedback.py <rec_id> <seen|applied|discarded|needs_coach>")


if __name__ == "__main__":
    main()
