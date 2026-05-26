#!/usr/bin/env python3
"""
Feedback command — register user feedback on a recommendation.

Usage:
    python feedback.py <rec_id> <status> [--note "Texto opcional"]

Status values: seen | applied | discarded | needs_coach

Examples:
    python feedback.py valentina_001_jsearch_abc123 applied
    python feedback.py valentina_001_jsearch_abc123 needs_coach --note "Revisar con coach de inglés"
    python feedback.py valentina_001_jsearch_abc123 discarded --note "Empresa en sector gambling"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.delivery.payload import VALID_STATUSES
from app.delivery.repository import get_feedback_events, get_recommendations, record_feedback


def _list_recommendations(profile_id: str) -> None:
    recs = get_recommendations(profile_id)
    if not recs:
        print(f"Sin recomendaciones para el perfil '{profile_id}'.")
        return
    print(f"\nRecomendaciones para '{profile_id}':")
    for r in recs:
        print(f"  [{r['status']:12s}] score={r['match_score']:3d}  {r['rec_id']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Registrar feedback sobre una recomendación de empleo.",
    )
    parser.add_argument("rec_id", help="ID de la recomendación (e.g. valentina_001_jobid)")
    parser.add_argument(
        "status",
        choices=list(VALID_STATUSES),
        help="Nuevo estado de la recomendación",
    )
    parser.add_argument(
        "--note", default="", metavar="TEXTO",
        help="Nota opcional sobre la decisión",
    )
    parser.add_argument(
        "--history", action="store_true",
        help="Mostrar historial de feedback tras registrar",
    )
    args = parser.parse_args()

    success = record_feedback(args.rec_id, args.status, note=args.note)

    if not success:
        print(f"Error: recomendación '{args.rec_id}' no encontrada.")
        profile_id = args.rec_id.split("_")[0] if "_" in args.rec_id else ""
        if profile_id:
            _list_recommendations(profile_id)
        sys.exit(1)

    print(f"✓ Feedback registrado: '{args.rec_id}' → {args.status}")
    if args.note:
        print(f"  Nota: {args.note}")

    if args.history:
        events = get_feedback_events(args.rec_id)
        if events:
            print(f"\nHistorial de feedback:")
            for e in events:
                note_str = f"  — {e['note']}" if e["note"] else ""
                print(f"  {e['recorded_at'][:19]}  {e['status']}{note_str}")


if __name__ == "__main__":
    main()
