#!/usr/bin/env python3
"""
Profile management command — import, list, show, and delete student profiles.

Usage:
    python profiles.py import fixtures/profiles/junior_frontend.json
    python profiles.py list
    python profiles.py show lyfter-001
    python profiles.py delete lyfter-001
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.profiles.repository import delete_profile, list_profiles, load_profile, upsert_profile
from app.schemas import StudentProfile


def _print_separator(char: str = "─", width: int = 60) -> None:
    print(char * width)


def cmd_import(args) -> None:
    path = Path(args.file)
    if not path.exists():
        print(f"Error: archivo no encontrado: {path}")
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    profile = StudentProfile.from_dict(data)
    action = upsert_profile(profile)

    verb = "importado" if action == "inserted" else "actualizado"
    print(f"Perfil {verb}: {profile.name} ({profile.profile_id})")


def cmd_list(args) -> None:
    profiles = list_profiles()
    if not profiles:
        print("No hay perfiles en la base de datos.")
        return

    _print_separator("=")
    print(f"{'ID':<20} {'Nombre':<25} {'Cohort':<20} {'Seniority'}")
    _print_separator()
    for p in profiles:
        print(f"{p.profile_id:<20} {p.name:<25} {p.cohort:<20} {p.seniority}")
    _print_separator()
    print(f"Total: {len(profiles)} perfil(es)")


def cmd_show(args) -> None:
    profile = load_profile(args.profile_id)
    if profile is None:
        print(f"Error: perfil '{args.profile_id}' no encontrado.")
        sys.exit(1)

    _print_separator("=")
    print(f"Perfil: {profile.name} ({profile.profile_id})")
    _print_separator()
    print(f"  Cohort    : {profile.cohort}")
    print(f"  Seniority : {profile.seniority}")
    print(f"  Ubicación : {profile.location.city}, {profile.location.country}")
    print(f"  Modalidad : {', '.join(profile.modality)}")
    print(f"  Stack     : {', '.join(profile.stack.primary)}")
    print(f"  Idiomas   : {', '.join(f'{l.language} ({l.level})' for l in profile.languages)}")
    print(f"  Salario   : {profile.expected_salary.min}–{profile.expected_salary.max} "
          f"{profile.expected_salary.currency}/{profile.expected_salary.period}")
    print(f"  Roles     : {', '.join(profile.preferences.roles)}")
    _print_separator("=")


def cmd_delete(args) -> None:
    found = delete_profile(args.profile_id)
    if found:
        print(f"Perfil '{args.profile_id}' eliminado.")
    else:
        print(f"Error: perfil '{args.profile_id}' no encontrado.")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gestión de perfiles de estudiantes en la base de datos.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import", help="Importar perfil desde JSON")
    p_import.add_argument("file", help="Ruta al JSON del StudentProfile")

    sub.add_parser("list", help="Listar todos los perfiles")

    p_show = sub.add_parser("show", help="Mostrar detalles de un perfil")
    p_show.add_argument("profile_id", help="ID del perfil")

    p_delete = sub.add_parser("delete", help="Eliminar un perfil")
    p_delete.add_argument("profile_id", help="ID del perfil")

    args = parser.parse_args()

    commands = {
        "import": cmd_import,
        "list": cmd_list,
        "show": cmd_show,
        "delete": cmd_delete,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
