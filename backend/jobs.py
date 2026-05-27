#!/usr/bin/env python3
"""
Job management command — list and inspect stored job postings.

Usage:
    python jobs.py list
    python jobs.py list --status active
    python jobs.py list --source jsearch
    python jobs.py show <job_id>
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.ingestion.repository import list_all_jobs, load_job


def _print_separator(char: str = "─", width: int = 70) -> None:
    print(char * width)


def cmd_list(args) -> None:
    jobs = list_all_jobs()

    if args.status:
        jobs = [j for j in jobs if j["status"] == args.status]
    if args.source:
        jobs = [j for j in jobs if j["source"] == args.source]

    if not jobs:
        print("No hay ofertas laborales en la base de datos.")
        return

    _print_separator("=")
    print(f"{'ID':<18} {'Título':<30} {'Empresa':<22} {'País':<6} {'Rem':<4} {'Estado':<8} {'Seniority'}")
    _print_separator()
    for j in jobs:
        remote = "Sí" if j["is_remote"] else "No"
        country = (j["location_country"] or "")[:5]
        title = j["job_title"][:29]
        company = j["company_name"][:21]
        job_id = j["job_id"][:17]
        print(
            f"{job_id:<18} {title:<30} {company:<22} {country:<6} {remote:<4} "
            f"{j['status']:<8} {j['seniority_signal']}"
        )
    _print_separator()
    print(f"Total: {len(jobs)} oferta(s) canónica(s)")


def cmd_show(args) -> None:
    job = load_job(args.job_id)
    if job is None:
        print(f"Error: oferta '{args.job_id}' no encontrada.")
        sys.exit(1)

    location = ", ".join(filter(None, [job["location_city"], job["location_country"]]))
    remote = "Sí" if job["is_remote"] else "No"

    salary = "N/A"
    if job["salary_min"] is not None:
        salary = f"{job['salary_min']:,.0f}–{job['salary_max']:,.0f} {job['salary_currency'] or ''}/{job['salary_period'] or ''}"

    stack = ", ".join(job["stack_keywords"]) if job["stack_keywords"] else "N/A"
    dups = len(job["duplicate_ids"])

    _print_separator("=")
    print(f"Oferta: {job['job_title']} @ {job['company_name']} ({job['job_id']})")
    _print_separator()
    print(f"  Fuente       : {job['source']}")
    print(f"  Ubicación    : {location or 'N/A'}")
    print(f"  Remoto       : {remote}")
    print(f"  Modalidad    : {', '.join(job['modality']) or 'N/A'}")
    print(f"  Seniority    : {job['seniority_signal']}")
    print(f"  Stack        : {stack}")
    print(f"  Salario      : {salary}")
    print(f"  URL          : {job['apply_url']}")
    print(f"  Publicado    : {job['posted_at'] or 'N/A'}")
    print(f"  Último visto : {job['last_seen'][:10]}  ({job['fetch_count']} vez/veces)")
    print(f"  Primer visto : {job['first_seen'][:10]}")
    print(f"  Estado       : {job['status']}")
    print(f"  Duplicados   : {dups}")
    if job["qualifications_raw"]:
        print(f"  Requisitos   :")
        for q in job["qualifications_raw"]:
            print(f"    • {q}")
    _print_separator("=")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspección de ofertas laborales almacenadas en la base de datos.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="Listar todas las ofertas canónicas")
    p_list.add_argument("--status", choices=["active", "stale", "expired"], help="Filtrar por estado")
    p_list.add_argument("--source", choices=["jsearch", "serpapi"], help="Filtrar por fuente")

    p_show = sub.add_parser("show", help="Ver detalle de una oferta")
    p_show.add_argument("job_id", help="ID de la oferta")

    args = parser.parse_args()

    commands = {
        "list": cmd_list,
        "show": cmd_show,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
