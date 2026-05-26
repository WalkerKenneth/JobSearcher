"""Job scoring and ranking engine.

Two-phase evaluation:
  Phase 1 — Hard filters (binary pass/fail).
  Phase 2 — Compatibility score 0–100.

Only jobs that pass Phase 1 are scored; all results are returned with
`hard_filters_passed` so the caller decides what to surface in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas import NormalizedJob, StudentProfile

_LANGUAGE_LEVELS: dict[str, int] = {
    "basic": 1,
    "intermediate": 2,
    "advanced": 3,
    "native": 4,
}

# Keywords used to detect sectors from job description + company name.
_SECTOR_KEYWORDS: dict[str, list[str]] = {
    # Narrower keywords: "developer" / "desarrollador" describe a role, not a sector.
    "tech": ["software", "tecnología", "tecnologia", "digital"],
    "fintech": ["pago", "payment", "fintech", "financiero", "bancario", "banking", "wallet", "transacción"],
    "edtech": ["educación", "educacion", "education", "aprendizaje", "learning", "edtech", "bootcamp", "academia"],
    "healthtech": ["salud", "health", "médico", "medico", "medical", "clinic", "hospital", "healthtech"],
    "logistics": ["logística", "logistica", "logistics", "delivery", "envío", "envio", "supply chain", "bodega"],
    "gambling": ["casino", "apuesta", "bet ", "betting", "gambling", "juego de azar", "lottery", "lotería"],
    "tobacco": ["tabaco", "tobacco", "cigarro", "cigarrillo"],
}

# Keywords used to infer company size from job description + company name.
_SIZE_KEYWORDS: dict[str, list[str]] = {
    "startup": ["startup", "start-up", "emprendimiento", "early-stage", "serie a", "serie b"],
    "mid-size": ["pyme", "mediana", "mid-size", "growing company", "en crecimiento"],
    "enterprise": [
        "enterprise", "corporativo", "multinacional", "multinational",
        "corporation", " s.a.", " inc.", " corp.", "grupo ", "group ", "holdings",
    ],
}


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

@dataclass
class HardFilterResult:
    passed: bool
    failures: list[str]


@dataclass
class JobMatch:
    job_id: str
    title: str
    company: str
    match_score: int           # 0–100 (clamped)
    hard_filters_passed: bool
    match_reasons: list[str]   # why this job is a good fit
    gaps: list[str]            # things missing or penalised
    action: str                # recommended next step


# ---------------------------------------------------------------------------
# Phase 1 — Hard filters
# ---------------------------------------------------------------------------

def apply_hard_filters(job: NormalizedJob, profile: StudentProfile) -> HardFilterResult:
    """Return a HardFilterResult indicating whether the job passes all hard filters."""
    failures: list[str] = []

    # 1. Salary: offer.salary_max < profile.restrictions.min_salary
    if (
        profile.restrictions.min_salary is not None
        and job.salary_max is not None
        and job.salary_max < profile.restrictions.min_salary
    ):
        failures.append(
            f"Salario máximo ({job.salary_max:,.0f} {job.salary_currency or ''}) "
            f"menor al mínimo requerido ({profile.restrictions.min_salary:,.0f} "
            f"{profile.restrictions.currency})"
        )

    # 2. Modality: job must offer at least one modality the profile accepts.
    if job.modality:
        accepted = set(profile.modality)
        if not any(m in accepted for m in job.modality):
            failures.append(
                f"Modalidad {job.modality} no compatible con tu perfil {profile.modality}"
            )

    # 3. Location: excluded_locations list (supports "outside <country>" pattern).
    if profile.restrictions.excluded_locations:
        job_country = (job.location_country or "").strip().lower()
        job_city = (job.location_city or "").strip().lower()
        for excl in profile.restrictions.excluded_locations:
            excl_norm = excl.strip().lower()
            if excl_norm.startswith("outside "):
                allowed = excl_norm[len("outside "):].strip()
                if job_country and job_country != allowed:
                    failures.append(
                        f"Ubicación '{job.location_country}' fuera de la zona permitida (solo: {excl})"
                    )
                    break
            elif excl_norm in (job_country, job_city):
                failures.append(f"Ubicación '{excl}' excluida del perfil")
                break

    return HardFilterResult(passed=len(failures) == 0, failures=failures)


# ---------------------------------------------------------------------------
# Phase 2 — Scoring helpers
# ---------------------------------------------------------------------------

def _profile_tech_set(profile: StudentProfile) -> set[str]:
    return {
        t.lower()
        for t in profile.stack.primary + profile.stack.secondary + profile.stack.tools
    }


def _score_stack(
    job: NormalizedJob, profile: StudentProfile, growth: str
) -> tuple[int, list[str], list[str]]:
    """Stack match — 35 pts base (40 with growth_priority=learning)."""
    weight = 40 if growth == "learning" else 35
    tech_set = _profile_tech_set(profile)
    job_tech = [t.lower() for t in job.stack_keywords]

    if not job_tech:
        return weight, ["Sin requerimientos de stack específicos"], []

    matched = [t for t in job_tech if t in tech_set]
    missing = [t for t in job_tech if t not in tech_set]
    score = round(len(matched) / len(job_tech) * weight)

    reasons: list[str] = []
    gaps: list[str] = []
    if matched:
        reasons.append(f"Stack: {', '.join(matched)} ({len(matched)}/{len(job_tech)})")
    if missing:
        gaps.append(f"Tecnologías faltantes en tu stack: {', '.join(missing)}")

    return score, reasons, gaps


def _score_seniority(
    job: NormalizedJob, profile: StudentProfile, growth: str
) -> tuple[int, list[str], list[str]]:
    """Seniority match — 20 pts base (15 with growth_priority=learning)."""
    weight = 15 if growth == "learning" else 20
    signal = job.seniority_signal

    if signal in ("junior", "unknown"):
        return weight, ["Seniority compatible (junior / sin experiencia mínima requerida)"], []
    if signal == "mid":
        return round(weight * 0.5), [], ["Puede requerir más experiencia de la que tienes actualmente"]
    # senior
    return 0, [], ["El puesto requiere nivel senior (3+ años de experiencia)"]


def _get_profile_english_level(profile: StudentProfile) -> int:
    for lang in profile.languages:
        if lang.language.lower() == "english":
            return _LANGUAGE_LEVELS.get(lang.level, 0)
    return 0


def _score_language(
    job: NormalizedJob, profile: StudentProfile
) -> tuple[int, list[str], list[str]]:
    """Language match — 15 pts if meets requirement, 7 if exceeds, 0 if below."""
    desc = (job.description_raw or "").lower()

    advanced_signals = [
        "advanced english", "inglés avanzado", "ingles avanzado",
        "fluent in english", "fluent english", "c1", "c2", "b2",
    ]
    intermediate_signals = [
        "intermediate english", "inglés intermedio", "ingles intermedio",
        "conversational english", "inglés conversacional",
        "english required", "inglés requerido", "ingles requerido",
        "bilingual", "bilingüe", "b1",
    ]

    if any(s in desc for s in advanced_signals):
        required_level = _LANGUAGE_LEVELS["advanced"]
        required_name = "advanced"
    elif any(s in desc for s in intermediate_signals):
        required_level = _LANGUAGE_LEVELS["intermediate"]
        required_name = "intermediate"
    else:
        return 15, ["Sin requisito de idioma específico"], []

    profile_level = _get_profile_english_level(profile)
    profile_name = next(
        (n for n, v in _LANGUAGE_LEVELS.items() if v == profile_level), "ninguno"
    )

    if profile_level > required_level:
        return 7, ["Tu nivel de inglés supera el requerido"], []
    if profile_level == required_level:
        return 15, ["Nivel de inglés cumple el requisito"], []
    return 0, [], [f"Inglés requerido: {required_name}; tu nivel: {profile_name}"]


def _detect_sectors(job: NormalizedJob) -> list[str]:
    text = " ".join([
        (job.description_raw or "").lower(),
        (job.job_title or "").lower(),
        (job.company_name or "").lower(),
    ])
    return [s for s, kws in _SECTOR_KEYWORDS.items() if any(kw in text for kw in kws)]


def _score_sector(
    job: NormalizedJob, profile: StudentProfile, growth: str
) -> tuple[int, list[str], list[str]]:
    """Sector match — 15 pts if preferred; -20 penalty if in avoid_sectors."""
    detected = _detect_sectors(job)
    score = 0
    reasons: list[str] = []
    gaps: list[str] = []

    avoid = {s.lower() for s in profile.preferences.avoid_sectors}
    avoided = [s for s in detected if s in avoid]
    if avoided:
        score -= 20
        gaps.append(f"Sector '{', '.join(avoided)}' en tu lista de sectores a evitar")

    preferred = {s.lower() for s in profile.preferences.sectors}
    matched = [s for s in detected if s in preferred]
    if matched:
        bonus = 15
        if growth == "impact":
            impact_sectors = {"ong", "govtech", "social impact", "ngo", "nonprofit"}
            if any(s in impact_sectors for s in matched):
                bonus += 10
        score += bonus
        reasons.append(f"Sector preferido: {', '.join(matched)}")

    return score, reasons, gaps


def _detect_company_size(job: NormalizedJob) -> str | None:
    text = " ".join([
        (job.description_raw or "").lower(),
        (job.company_name or "").lower(),
    ])
    for size, kws in _SIZE_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return size
    return None


def _score_company_size(
    job: NormalizedJob, profile: StudentProfile, growth: str
) -> tuple[int, list[str], list[str]]:
    """Company size match — 10 pts if preferred; +10 stability bonus for enterprise/mid-size."""
    detected = _detect_company_size(job)
    if detected is None:
        return 0, [], []

    preferred = set(profile.preferences.company_size)
    base = 10 if detected in preferred else 0
    stability_bonus = (
        10 if growth == "stability" and detected in ("mid-size", "enterprise") else 0
    )
    total = base + stability_bonus

    reasons: list[str] = []
    gaps: list[str] = []
    if total > 0:
        label = f"Empresa {detected}"
        if stability_bonus:
            label += " (bonus de estabilidad)"
        reasons.append(label)
    elif detected not in preferred:
        gaps.append(f"Tamaño de empresa ({detected}) no coincide con tus preferencias")

    return total, reasons, gaps


def _score_role_title(
    job: NormalizedJob, profile: StudentProfile
) -> tuple[int, list[str], list[str]]:
    """Role title match — 5 pts if any meaningful word from preferred roles appears in title."""
    title_lower = (job.job_title or "").lower()
    for preferred in profile.preferences.roles:
        keywords = [w for w in preferred.lower().split() if len(w) > 3]
        if keywords and any(kw in title_lower for kw in keywords):
            return 5, [f"Título '{job.job_title}' compatible con '{preferred}'"], []
    return 0, [], []


def _adjust_salary(
    job: NormalizedJob, profile: StudentProfile, growth: str
) -> tuple[int, list[str], list[str]]:
    """Salary adjustments: +10 bonus (salary priority) or -10 penalty (below expected)."""
    if job.salary_max is None:
        return 0, [], []

    adj = 0
    reasons: list[str] = []
    gaps: list[str] = []

    if growth == "salary" and job.salary_max > profile.expected_salary.max:
        adj += 10
        reasons.append("Salario supera tu rango esperado (bonus por prioridad salarial)")

    if (
        job.salary_max < profile.expected_salary.min
        and profile.restrictions.min_salary is not None
        and job.salary_max >= profile.restrictions.min_salary
    ):
        adj -= 10
        gaps.append("Salario por debajo de tu rango esperado (aunque sobre el mínimo)")

    return adj, reasons, gaps


# ---------------------------------------------------------------------------
# Score classification
# ---------------------------------------------------------------------------

def _action_label(score: int) -> str:
    if score >= 80:
        return "Aplicar de inmediato"
    if score >= 60:
        return "Aplicar con adaptaciones menores al CV"
    if score >= 40:
        return "Revisar gaps antes de aplicar"
    return "Match bajo — fuera del rango recomendado"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_job(job: NormalizedJob, profile: StudentProfile) -> JobMatch:
    """Score a single job against a profile (assumes hard filters already passed)."""
    growth = profile.preferences.growth_priority
    total = 0
    reasons: list[str] = []
    gaps: list[str] = []

    for score, r, g in [
        _score_stack(job, profile, growth),
        _score_seniority(job, profile, growth),
        _score_language(job, profile),
        _score_sector(job, profile, growth),
        _score_company_size(job, profile, growth),
        _score_role_title(job, profile),
        _adjust_salary(job, profile, growth),
    ]:
        total += score
        reasons.extend(r)
        gaps.extend(g)

    final = max(0, min(100, total))
    return JobMatch(
        job_id=job.job_id,
        title=job.job_title,
        company=job.company_name,
        match_score=final,
        hard_filters_passed=True,
        match_reasons=reasons,
        gaps=gaps,
        action=_action_label(final),
    )


def rank_jobs(jobs: list[NormalizedJob], profile: StudentProfile) -> list[JobMatch]:
    """Apply hard filters and score all jobs, returning them sorted by score descending.

    Jobs that fail hard filters are included with match_score=0 and
    hard_filters_passed=False so the caller can display a reason for exclusion.
    Passing jobs are always ranked before filtered ones.
    """
    results: list[JobMatch] = []
    for job in jobs:
        filter_result = apply_hard_filters(job, profile)
        if not filter_result.passed:
            results.append(JobMatch(
                job_id=job.job_id,
                title=job.job_title,
                company=job.company_name,
                match_score=0,
                hard_filters_passed=False,
                match_reasons=[],
                gaps=filter_result.failures,
                action="Oferta descartada por filtros obligatorios",
            ))
        else:
            results.append(score_job(job, profile))

    results.sort(key=lambda m: (m.hard_filters_passed, m.match_score), reverse=True)
    return results
