"""
Spike: Flujo Mínimo de Orquestación — ADR-001 Opción C
=======================================================
Demuestra el pipeline completo con:
  - Backend determinístico: QueryBuilder → HardFilter → ScoringEngine
  - LLM (Claude API): ExtractJobSignals + GenerateAction
  - JSearch: respuesta mockeada (sin consumir créditos del free tier)

Ejecutar:
    export ANTHROPIC_API_KEY=sk-ant-...
    pip install anthropic
    python minimal_flow.py

Para correr con JSearch real:
    export JSEARCH_API_KEY=...
    python minimal_flow.py --live
"""

import json
import os
import sys
from dataclasses import dataclass, field

import anthropic

# ---------------------------------------------------------------------------
# Fixtures — se leen de los archivos del proyecto en un entorno real
# ---------------------------------------------------------------------------

STUDENT_PROFILE = {
    "profile_id": "lyfter-001",
    "name": "Valentina Torres",
    "stack": {
        "primary": ["JavaScript", "React", "HTML", "CSS"],
        "secondary": ["TypeScript", "Git"],
        "tools": ["Figma", "VS Code"],
    },
    "seniority": "junior",
    "location": {"city": "San José", "country": "Costa Rica"},
    "modality": ["remote", "hybrid"],
    "languages": [{"language": "Spanish", "level": "native"}, {"language": "English", "level": "intermediate"}],
    "restrictions": {
        "min_salary": 600000,
        "currency": "CRC",
        "excluded_modalities": ["on-site"],
        "excluded_locations": [],
        "requires_visa_sponsorship": False,
        "max_travel_percent": None,
    },
    "preferences": {
        "company_size": ["startup", "mid-size"],
        "sectors": ["tech", "fintech"],
        "roles": ["Frontend Developer", "UI Developer"],
        "avoid_sectors": ["gambling"],
        "growth_priority": "learning",
    },
}

# Respuesta mockeada de JSearch — estructura real de la API
MOCK_JSEARCH_RESPONSE = {
    "data": [
        {
            "job_id": "job-001",
            "employer_name": "FinTech CR",
            "job_title": "Junior Frontend Developer",
            "job_city": "San José",
            "job_country": "CR",
            "job_is_remote": True,
            "job_description": (
                "Buscamos un desarrollador frontend junior para unirse a nuestro equipo. "
                "Requisitos: 0-1 año de experiencia, dominio de React y JavaScript, "
                "conocimiento básico de HTML/CSS. TypeScript es un plus. "
                "Inglés intermedio requerido. Trabajo 100% remoto."
            ),
            "job_min_salary": 650000,
            "job_max_salary": 900000,
            "job_apply_link": "https://example.com/apply/001",
        },
        {
            "job_id": "job-002",
            "employer_name": "Casino Online SA",
            "job_title": "Frontend Developer",
            "job_city": "San José",
            "job_country": "CR",
            "job_is_remote": True,
            "job_description": (
                "Frontend developer para plataforma de casino en línea. "
                "Stack: React, TypeScript, Node.js. 2+ años de experiencia requeridos. "
                "Inglés avanzado. Excelente salario."
            ),
            "job_min_salary": 1200000,
            "job_max_salary": 1800000,
            "job_apply_link": "https://example.com/apply/002",
        },
        {
            "job_id": "job-003",
            "employer_name": "Startup Hub CR",
            "job_title": "UI Developer Junior",
            "job_city": "Heredia",
            "job_country": "CR",
            "job_is_remote": False,  # presencial — hard filter fail para Valentina
            "job_description": (
                "Junior UI developer para startup de tecnología educativa. "
                "Usamos React, JavaScript y CSS. No se requiere experiencia previa. "
                "Salario según tabla salarial interna."
            ),
            "job_min_salary": None,
            "job_max_salary": None,
            "job_apply_link": "https://example.com/apply/003",
        },
    ]
}


# ---------------------------------------------------------------------------
# Paso 1 — QueryBuilder (Backend determinístico)
# ---------------------------------------------------------------------------

def build_jsearch_query(profile: dict) -> dict:
    stack = profile["stack"]["primary"]
    role = profile["preferences"]["roles"][0] if profile["preferences"]["roles"] else "developer"
    location = profile["location"]["country"]
    return {
        "query": f"{profile['seniority']} {stack[0]} {role}",
        "location": location,
        "remote_jobs_only": "remote" in profile["modality"] and "on-site" not in profile["modality"],
        "num_pages": 1,
        "date_posted": "month",
    }


# ---------------------------------------------------------------------------
# Paso 2 — JobFetcher (mock o real)
# ---------------------------------------------------------------------------

def fetch_jobs(query_params: dict, live: bool = False) -> list[dict]:
    if live:
        # Llamada real a JSearch API (requiere JSEARCH_API_KEY en env)
        import urllib.request
        api_key = os.environ["JSEARCH_API_KEY"]
        base_url = "https://jsearch.p.rapidapi.com/search"
        q = "&".join(f"{k}={v}" for k, v in query_params.items())
        req = urllib.request.Request(
            f"{base_url}?{q}",
            headers={"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["data"]
    return MOCK_JSEARCH_RESPONSE["data"]


# ---------------------------------------------------------------------------
# Paso 3 — JobNormalizer (Backend determinístico)
# ---------------------------------------------------------------------------

@dataclass
class NormalizedJob:
    job_id: str
    title: str
    company: str
    location: str
    is_remote: bool
    description: str
    salary_min: int | None
    salary_max: int | None
    apply_link: str
    extracted_stack: list[str] = field(default_factory=list)
    extracted_seniority: str = ""


def normalize_jobs(raw_jobs: list[dict]) -> list[NormalizedJob]:
    normalized = []
    for job in raw_jobs:
        normalized.append(NormalizedJob(
            job_id=job["job_id"],
            title=job["job_title"],
            company=job["employer_name"],
            location=f"{job.get('job_city', '')}, {job.get('job_country', '')}",
            is_remote=job.get("job_is_remote", False),
            description=job.get("job_description", ""),
            salary_min=job.get("job_min_salary"),
            salary_max=job.get("job_max_salary"),
            apply_link=job.get("job_apply_link", ""),
        ))
    return normalized


# ---------------------------------------------------------------------------
# Paso 4 — HardFilterEngine (Backend determinístico)
# ---------------------------------------------------------------------------

def apply_hard_filters(jobs: list[NormalizedJob], profile: dict) -> list[NormalizedJob]:
    restrictions = profile["restrictions"]
    passed = []
    for job in jobs:
        # Modalidad
        if not job.is_remote and "on-site" in restrictions.get("excluded_modalities", []):
            print(f"  [FILTRADO] {job.title} @ {job.company} — modalidad excluida (presencial)")
            continue
        # Salario mínimo (solo aplica si el dato existe)
        if job.salary_max is not None and restrictions.get("min_salary"):
            if job.salary_max < restrictions["min_salary"]:
                print(f"  [FILTRADO] {job.title} @ {job.company} — salario máximo ({job.salary_max}) < mínimo requerido ({restrictions['min_salary']})")
                continue
        passed.append(job)
    return passed


# ---------------------------------------------------------------------------
# Paso 5 — ExtractJobSignals (Claude API — tool_use)
# ---------------------------------------------------------------------------

EXTRACT_SIGNALS_TOOL = {
    "name": "extract_job_signals",
    "description": "Extrae el stack de tecnologías requeridas y el nivel de seniority de la descripción de un puesto.",
    "input_schema": {
        "type": "object",
        "properties": {
            "stack": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Lista de tecnologías/frameworks mencionados como requisitos",
            },
            "seniority": {
                "type": "string",
                "enum": ["junior", "mid", "senior", "unknown"],
                "description": "Nivel de seniority inferido de la descripción",
            },
            "years_experience_required": {
                "type": "integer",
                "description": "Años de experiencia requeridos (0 si no se especifica)",
            },
            "english_required": {
                "type": "string",
                "enum": ["none", "basic", "intermediate", "advanced"],
                "description": "Nivel de inglés requerido",
            },
        },
        "required": ["stack", "seniority", "years_experience_required", "english_required"],
    },
}


def extract_job_signals(client: anthropic.Anthropic, job: NormalizedJob) -> dict:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",  # Haiku: rápido y barato para extracción
        max_tokens=256,
        tools=[EXTRACT_SIGNALS_TOOL],
        tool_choice={"type": "tool", "name": "extract_job_signals"},
        messages=[
            {
                "role": "user",
                "content": f"Extrae las señales de este puesto:\n\n{job.description}",
            }
        ],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_job_signals":
            return block.input
    return {"stack": [], "seniority": "unknown", "years_experience_required": 0, "english_required": "none"}


# ---------------------------------------------------------------------------
# Paso 6 — ScoringEngine (Backend determinístico, según match-rubric.md)
# ---------------------------------------------------------------------------

def score_job(job: NormalizedJob, profile: dict) -> int:
    score = 0
    student_stack = set(
        s.lower() for s in profile["stack"]["primary"] + profile["stack"]["secondary"]
    )
    job_stack = set(s.lower() for s in job.extracted_stack)

    # Stack match (35 pts)
    if job_stack:
        overlap = len(student_stack & job_stack) / len(job_stack)
        score += round(overlap * 35)

    # Seniority match (20 pts)
    if job.extracted_seniority == "junior":
        score += 20
    elif job.extracted_seniority == "mid":
        score += 10

    # Sector preferido (15 pts)
    preferred_sectors = profile["preferences"].get("sectors", [])
    avoid_sectors = profile["preferences"].get("avoid_sectors", [])
    company_lower = job.company.lower()
    for sector in preferred_sectors:
        if sector.lower() in company_lower or sector.lower() in job.title.lower():
            score += 15
            break
    for sector in avoid_sectors:
        if sector.lower() in company_lower or sector.lower() in job.description.lower():
            score -= 20
            break

    # Tamaño empresa (10 pts) — heurística por nombre
    score += 10 if any(w in job.company.lower() for w in ["startup", "hub", "cr"]) else 0

    # Título del rol (5 pts)
    preferred_roles = [r.lower() for r in profile["preferences"].get("roles", [])]
    if any(r in job.title.lower() for r in preferred_roles):
        score += 5

    # Ajuste por growth_priority=learning: stack match +5, seniority -5
    if profile["preferences"].get("growth_priority") == "learning":
        if job_stack and student_stack:
            score += 5
        score = max(score - 5, 0)

    return max(0, min(score, 100))


# ---------------------------------------------------------------------------
# Paso 7 — GenerateAction (Claude API — Sonnet para síntesis final)
# ---------------------------------------------------------------------------

def generate_action(client: anthropic.Anthropic, job: NormalizedJob, profile: dict, score: int) -> dict:
    prompt = f"""Eres un coach de empleabilidad para Lyfter. Dado este match, genera:
1. match_reasons: lista de 2-3 razones por las que el estudiante aplica bien
2. gaps: lista de 0-2 gaps concretos entre el perfil y el puesto
3. action: una acción concreta y específica (máximo 2 oraciones)

Estudiante: {profile['name']}, {profile['seniority']}, stack: {profile['stack']['primary']}
Puesto: {job.title} @ {job.company}
Stack requerido por el puesto: {job.extracted_stack}
Match score: {score}/100

Responde SOLO con JSON válido, sin explicaciones adicionales."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    # Limpiar posible markdown fence
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


# ---------------------------------------------------------------------------
# Pipeline completo
# ---------------------------------------------------------------------------

def run_pipeline(live: bool = False) -> None:
    print("=" * 60)
    print("JobSearcher — Flujo Mínimo de Orquestación")
    print(f"Perfil: {STUDENT_PROFILE['name']} ({STUDENT_PROFILE['profile_id']})")
    print("=" * 60)

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # Paso 1: Construir query
    query_params = build_jsearch_query(STUDENT_PROFILE)
    print(f"\n[1] QueryBuilder → query: '{query_params['query']}' | location: {query_params['location']}")

    # Paso 2: Buscar empleos
    raw_jobs = fetch_jobs(query_params, live=live)
    print(f"[2] JobFetcher → {len(raw_jobs)} resultados {'(live)' if live else '(mock)'}")

    # Paso 3: Normalizar
    jobs = normalize_jobs(raw_jobs)
    print(f"[3] JobNormalizer → {len(jobs)} trabajos normalizados")

    # Paso 4: Hard filters
    print("\n[4] HardFilterEngine:")
    jobs_passed = apply_hard_filters(jobs, STUDENT_PROFILE)
    print(f"    → {len(jobs_passed)}/{len(jobs)} trabajos pasaron los filtros")

    # Paso 5 + 6: Extraer señales y calcular score
    print("\n[5+6] ExtractJobSignals (Claude) + ScoringEngine:")
    scored_jobs = []
    for job in jobs_passed:
        signals = extract_job_signals(client, job)
        job.extracted_stack = signals.get("stack", [])
        job.extracted_seniority = signals.get("seniority", "unknown")
        score = score_job(job, STUDENT_PROFILE)
        scored_jobs.append((job, score))
        print(f"    [{score:3d}/100] {job.title} @ {job.company}")
        print(f"           Stack extraído: {job.extracted_stack}")
        print(f"           Seniority: {job.extracted_seniority}")

    # Ordenar por score
    scored_jobs.sort(key=lambda x: x[1], reverse=True)

    # Paso 7: Generar acciones para top 3
    print("\n[7] GenerateAction (Claude) — top matches:")
    results = []
    for job, score in scored_jobs[:3]:
        if score < 40:
            print(f"    Omitiendo {job.title} (score {score} < 40)")
            continue
        action_data = generate_action(client, job, STUDENT_PROFILE, score)
        results.append({
            "job_id": job.job_id,
            "title": job.title,
            "company": job.company,
            "match_score": score,
            "hard_filters_passed": True,
            **action_data,
        })

    # Output final
    print("\n" + "=" * 60)
    print("RESULTADO FINAL — RankedJobList")
    print("=" * 60)
    print(json.dumps(results, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    live_mode = "--live" in sys.argv
    if live_mode and not os.environ.get("JSEARCH_API_KEY"):
        print("Error: --live requiere JSEARCH_API_KEY en el entorno")
        sys.exit(1)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: requiere ANTHROPIC_API_KEY en el entorno")
        sys.exit(1)
    run_pipeline(live=live_mode)
