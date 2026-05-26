"""Tests for the scoring and ranking engine (subtarea 7).

Coverage:
  - Hard filters: salary, modality, location
  - Score components: stack, seniority, language, sector, company size, role title
  - Penalties: avoid_sector, salary below expected
  - Growth priority adjustments: learning, stability
  - Negative cases: wrong seniority, incompatible stack, excluded location
  - Ranking: ordering and completeness
"""

import pytest

from app.schemas import (
    Availability,
    ExpectedSalary,
    LanguageSkill,
    Preferences,
    ProfileLocation,
    Restrictions,
    Stack,
    StudentProfile,
)
from app.scoring.scorer import (
    JobMatch,
    apply_hard_filters,
    rank_jobs,
    score_job,
)
from app.schemas import NormalizedJob


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_job(**kwargs) -> NormalizedJob:
    """Factory for NormalizedJob with sensible defaults for scoring tests."""
    defaults = dict(
        job_id="test_001",
        source="jsearch",
        fetched_at="2026-05-25T14:00:00Z",
        job_title="Junior Developer",
        company_name="Empresa Ejemplo",
        location_city="San José",
        location_country="Costa Rica",
        is_remote=True,
        modality=["remote"],
        salary_min=700_000,
        salary_max=900_000,
        salary_currency="CRC",
        salary_period="monthly",
        description_raw=(
            "Buscamos un desarrollador junior para unirse a nuestro equipo de software "
            "en una startup de tecnología digital. Trabajarás en proyectos modernos."
        ),
        qualifications_raw=[],
        posted_at="2026-05-20T00:00:00Z",
        apply_url="https://example.com/jobs/test-001",
        stack_keywords=["React", "JavaScript"],
        seniority_signal="junior",
    )
    defaults.update(kwargs)
    return NormalizedJob(**defaults)


@pytest.fixture
def valentina() -> StudentProfile:
    """Junior frontend, Costa Rica, growth_priority=learning."""
    return StudentProfile(
        profile_id="lyfter-001",
        name="Valentina Torres",
        cohort="Lyfter-2025-Q1",
        stack=Stack(
            primary=["React", "JavaScript", "HTML", "CSS"],
            secondary=["TypeScript", "Git"],
            tools=["Figma", "VS Code", "GitHub"],
        ),
        seniority="junior",
        location=ProfileLocation(city="San José", country="Costa Rica", timezone="America/Costa_Rica"),
        modality=["remote", "hybrid"],
        languages=[
            LanguageSkill(language="Spanish", level="native"),
            LanguageSkill(language="English", level="intermediate"),
        ],
        availability=Availability(start_date="2026-06-01", hours_per_week=40, type="full-time"),
        expected_salary=ExpectedSalary(min=600_000, max=900_000, currency="CRC", period="monthly"),
        restrictions=Restrictions(
            min_salary=600_000,
            currency="CRC",
            excluded_modalities=["on-site"],
            excluded_locations=[],
            requires_visa_sponsorship=False,
            max_travel_percent=10,
        ),
        preferences=Preferences(
            company_size=["startup", "mid-size"],
            sectors=["tech", "edtech", "fintech"],
            roles=["Frontend Developer", "UI Developer", "React Developer"],
            avoid_sectors=["gambling", "tobacco"],
            growth_priority="learning",
        ),
    )


@pytest.fixture
def andres() -> StudentProfile:
    """Junior fullstack, Costa Rica, growth_priority=stability."""
    return StudentProfile(
        profile_id="lyfter-002",
        name="Andrés Mejía",
        cohort="Lyfter-2025-Q1",
        stack=Stack(
            primary=["Node.js", "Express", "JavaScript", "PostgreSQL"],
            secondary=["React", "REST APIs", "Git", "Docker"],
            tools=["Postman", "VS Code", "GitHub", "DBeaver"],
        ),
        seniority="junior",
        location=ProfileLocation(city="Heredia", country="Costa Rica", timezone="America/Costa_Rica"),
        modality=["remote", "hybrid", "on-site"],
        languages=[
            LanguageSkill(language="Spanish", level="native"),
            LanguageSkill(language="English", level="basic"),
        ],
        availability=Availability(start_date="2026-06-15", hours_per_week=40, type="full-time"),
        expected_salary=ExpectedSalary(min=750_000, max=1_100_000, currency="CRC", period="monthly"),
        restrictions=Restrictions(
            min_salary=750_000,
            currency="CRC",
            excluded_modalities=[],
            excluded_locations=["outside Costa Rica"],
            requires_visa_sponsorship=False,
            max_travel_percent=None,
        ),
        preferences=Preferences(
            company_size=["startup", "mid-size", "enterprise"],
            sectors=["tech", "logistics", "healthtech"],
            roles=["Backend Developer", "Node.js Developer", "Fullstack Developer"],
            avoid_sectors=["gambling"],
            growth_priority="stability",
        ),
    )


# ---------------------------------------------------------------------------
# Hard filter tests
# ---------------------------------------------------------------------------

class TestApplyHardFilters:
    def test_passes_when_all_ok(self, valentina):
        job = make_job(modality=["remote"], salary_max=800_000)
        result = apply_hard_filters(job, valentina)
        assert result.passed is True
        assert result.failures == []

    def test_fails_salary_max_below_minimum(self, valentina):
        job = make_job(salary_max=500_000, salary_currency="CRC")  # below 600 000
        result = apply_hard_filters(job, valentina)
        assert result.passed is False
        assert any("salario" in f.lower() for f in result.failures)

    def test_passes_salary_exactly_at_minimum(self, valentina):
        job = make_job(salary_max=600_000)
        result = apply_hard_filters(job, valentina)
        assert result.passed is True

    def test_passes_when_salary_unknown(self, valentina):
        # Unknown salary is not grounds for elimination
        job = make_job(salary_max=None)
        result = apply_hard_filters(job, valentina)
        assert result.passed is True

    def test_fails_modality_excluded(self, valentina):
        # Valentina excluded on-site; job is on-site only
        job = make_job(modality=["on-site"])
        result = apply_hard_filters(job, valentina)
        assert result.passed is False
        assert any("modalidad" in f.lower() for f in result.failures)

    def test_passes_when_job_offers_at_least_one_accepted_modality(self, valentina):
        # Job offers both on-site and remote; remote is accepted
        job = make_job(modality=["on-site", "remote"])
        result = apply_hard_filters(job, valentina)
        assert result.passed is True

    def test_passes_hybrid_accepted_by_valentina(self, valentina):
        job = make_job(modality=["hybrid"])
        result = apply_hard_filters(job, valentina)
        assert result.passed is True

    def test_fails_location_excluded_outside_pattern(self, andres):
        # Andrés: excluded_locations = ["outside Costa Rica"]
        job = make_job(location_country="United States")
        result = apply_hard_filters(job, andres)
        assert result.passed is False
        assert any("ubicación" in f.lower() for f in result.failures)

    def test_passes_location_in_allowed_country(self, andres):
        job = make_job(location_country="Costa Rica")
        result = apply_hard_filters(job, andres)
        assert result.passed is True

    def test_multiple_failures_all_reported(self, valentina):
        job = make_job(salary_max=400_000, modality=["on-site"])
        result = apply_hard_filters(job, valentina)
        assert result.passed is False
        assert len(result.failures) == 2


# ---------------------------------------------------------------------------
# Stack scoring
# ---------------------------------------------------------------------------

class TestScoreStack:
    def test_full_stack_match_maximises_stack_score(self, valentina):
        # React and JavaScript are both in Valentina's primary stack
        job = make_job(stack_keywords=["React", "JavaScript"])
        match = score_job(job, valentina)
        # Stack weight with learning=40; 2/2 = 40; full score should be very high
        assert match.match_score >= 80

    def test_zero_stack_match_reduces_score_significantly(self, valentina):
        # PHP, Laravel, MySQL: none in Valentina's stack.
        # Generic title/description to isolate stack contribution.
        job = make_job(
            job_title="Especialista en Sistemas",
            company_name="Servicios Generales S.R.L.",
            stack_keywords=["PHP", "Laravel", "MySQL"],
            description_raw="Se requieren conocimientos en sistemas de información básicos. " * 4,
        )
        match = score_job(job, valentina)
        assert match.match_score < 50

    def test_partial_match_scores_between_zero_and_full(self, valentina):
        full_job = make_job(job_id="full", stack_keywords=["React", "JavaScript"])
        partial_job = make_job(job_id="partial", stack_keywords=["React", "Vue.js", "Angular"])
        m_full = score_job(full_job, valentina)
        m_partial = score_job(partial_job, valentina)
        assert m_partial.match_score < m_full.match_score

    def test_missing_techs_appear_in_gaps(self, valentina):
        job = make_job(stack_keywords=["React", "Rust"])
        match = score_job(job, valentina)
        assert any("rust" in g.lower() for g in match.gaps)

    def test_matched_techs_appear_in_reasons(self, valentina):
        job = make_job(stack_keywords=["React", "JavaScript"])
        match = score_job(job, valentina)
        combined = " ".join(match.match_reasons).lower()
        assert "react" in combined

    def test_no_stack_keywords_gives_full_stack_points(self, valentina):
        job = make_job(stack_keywords=[])
        match = score_job(job, valentina)
        # Should still score well (stack contributes max)
        assert match.match_score >= 70

    def test_secondary_stack_techs_count_as_match(self, valentina):
        # TypeScript is in Valentina's secondary stack
        job = make_job(stack_keywords=["TypeScript", "JavaScript"])
        match = score_job(job, valentina)
        assert not any("typescript" in g.lower() for g in match.gaps)


# ---------------------------------------------------------------------------
# Seniority scoring — negative case: wrong seniority
# ---------------------------------------------------------------------------

class TestScoreSeniority:
    def test_junior_signal_gives_full_seniority_points(self, valentina):
        job_junior = make_job(seniority_signal="junior")
        job_senior = make_job(seniority_signal="senior")
        m_junior = score_job(job_junior, valentina)
        m_senior = score_job(job_senior, valentina)
        assert m_junior.match_score > m_senior.match_score

    def test_senior_signal_gives_zero_seniority_and_gap(self, valentina):
        job = make_job(seniority_signal="senior")
        match = score_job(job, valentina)
        assert any("senior" in g.lower() for g in match.gaps)

    def test_unknown_signal_treated_like_junior(self, valentina):
        job = make_job(seniority_signal="unknown")
        match = score_job(job, valentina)
        assert not any("senior" in g.lower() for g in match.gaps)
        combined = " ".join(match.match_reasons).lower()
        assert "seniority" in combined

    def test_mid_signal_gives_partial_seniority_points(self, valentina):
        job_mid = make_job(seniority_signal="mid")
        job_junior = make_job(seniority_signal="junior")
        m_mid = score_job(job_mid, valentina)
        m_junior = score_job(job_junior, valentina)
        assert m_mid.match_score < m_junior.match_score
        assert any("experiencia" in g.lower() for g in m_mid.gaps)


# ---------------------------------------------------------------------------
# Language scoring
# ---------------------------------------------------------------------------

class TestScoreLanguage:
    def test_no_english_requirement_gives_full_language_points(self, valentina):
        job = make_job(description_raw="Buscamos un desarrollador React para nuestra empresa. " * 4)
        match = score_job(job, valentina)
        combined = " ".join(match.match_reasons).lower()
        assert "idioma" in combined

    def test_intermediate_english_required_and_met(self, valentina):
        job = make_job(description_raw=(
            "English required for this position. Intermediate level. "
            "Buscamos desarrollador frontend junior. " * 3
        ))
        match = score_job(job, valentina)
        # Valentina has intermediate English — should meet requirement
        assert not any("inglés requerido" in g.lower() for g in match.gaps)
        assert not any("basic" in g.lower() for g in match.gaps)

    def test_advanced_english_required_not_met_by_basic(self, andres):
        # Andrés has basic English; job requires advanced
        job = make_job(description_raw=(
            "Advanced English required. C1 level minimum. Fluent English mandatory. "
            "Buscamos desarrollador backend junior. " * 3
        ))
        match = score_job(job, andres)
        assert any("inglés" in g.lower() for g in match.gaps)

    def test_exceeding_english_level_gives_7_pts(self, valentina):
        # Valentina has intermediate; job only needs basic — but our signals only
        # detect advanced vs intermediate. Test: advanced Valentina exceeds intermediate.
        advanced_profile = StudentProfile(
            **{**valentina.__dict__,
               "languages": [
                   LanguageSkill(language="English", level="advanced"),
                   LanguageSkill(language="Spanish", level="native"),
               ]}
        )
        job = make_job(description_raw=(
            "English required. Inglés requerido nivel intermedio. " * 4
        ))
        match = score_job(job, advanced_profile)
        assert any("supera" in r.lower() for r in match.match_reasons)


# ---------------------------------------------------------------------------
# Sector scoring and avoid-sector penalty
# ---------------------------------------------------------------------------

class TestScoreSector:
    def test_preferred_sector_adds_points(self, valentina):
        tech_job = make_job(description_raw=(
            "Somos una startup de software. Desarrollamos soluciones digitales "
            "con tecnologia moderna. " * 3
        ))
        # Neutral title and company to isolate sector contribution.
        no_sector_job = make_job(
            job_title="Gerente Administrativo",
            company_name="Servicios Generales S.R.L.",
            description_raw="Se busca profesional para apoyo administrativo. " * 5,
        )
        m_tech = score_job(tech_job, valentina)
        m_generic = score_job(no_sector_job, valentina)
        assert m_tech.match_score > m_generic.match_score

    def test_avoid_sector_applies_penalty(self, valentina):
        # gambling is in valentina.preferences.avoid_sectors
        gambling_job = make_job(
            job_id="gambling_001",
            description_raw=(
                "Casino online platform. Gambling solutions and betting systems. "
                "Desarrollador para plataforma de apuestas y casino. " * 3
            ),
        )
        tech_job = make_job(
            job_id="tech_001",
            description_raw=(
                "Startup de software tecnológico. Soluciones digitales para empresas. " * 4
            ),
        )
        m_gambling = score_job(gambling_job, valentina)
        m_tech = score_job(tech_job, valentina)
        assert m_gambling.match_score < m_tech.match_score
        assert any("evitar" in g.lower() or "gambling" in g.lower() for g in m_gambling.gaps)

    def test_avoid_sector_does_not_trigger_hard_filter(self, valentina):
        # Avoid sectors are penalties, NOT hard filters
        gambling_job = make_job(description_raw=(
            "Casino platform. Gambling solutions. Online betting. " * 4
        ))
        result = apply_hard_filters(gambling_job, valentina)
        assert result.passed is True


# ---------------------------------------------------------------------------
# Company size scoring and stability growth priority
# ---------------------------------------------------------------------------

class TestScoreCompanySize:
    def test_preferred_company_size_adds_points(self, valentina):
        # Valentina prefers startup. startup_job signals "startup" via description;
        # enterprise_job signals "enterprise" — Valentina doesn't prefer enterprise.
        startup_job = make_job(
            company_name="Mi Startup S.R.L.",
            description_raw=(
                "Somos una startup en etapa inicial (early-stage). "
                "Desarrollamos software de tecnologia digital. " * 3
            ),
        )
        enterprise_job = make_job(
            company_name="Global Corp S.A.",
            description_raw="Empresa multinacional corporativa con presencia global. " * 4,
        )
        m_startup = score_job(startup_job, valentina)
        m_enterprise = score_job(enterprise_job, valentina)
        assert m_startup.match_score > m_enterprise.match_score

    def test_stability_priority_adds_enterprise_bonus(self, andres):
        # Andrés has growth_priority=stability; enterprise company earns +10 extra.
        enterprise_job = make_job(
            company_name="Global Corp S.A.",
            description_raw=(
                "Empresa multinacional enterprise con presencia en toda LATAM. "
                "Desarrollamos software para el sector de tecnologia. " * 3
            ),
        )
        match = score_job(enterprise_job, andres)
        assert any("estabilidad" in r.lower() for r in match.match_reasons)

    def test_unknown_company_size_contributes_zero(self, valentina):
        generic_job = make_job(description_raw=(
            "Se busca desarrollador. Buen ambiente laboral. "
            "Equipo de trabajo colaborativo. " * 4
        ))
        match = score_job(generic_job, valentina)
        # No company size detected — no size contribution, but no gap either
        assert not any("tamaño" in g.lower() for g in match.gaps)


# ---------------------------------------------------------------------------
# Role title scoring
# ---------------------------------------------------------------------------

class TestScoreRoleTitle:
    def test_matching_title_adds_five_points(self, valentina):
        matching_job = make_job(job_title="Junior Frontend Developer")
        non_matching_job = make_job(job_title="Data Analyst")
        m_match = score_job(matching_job, valentina)
        m_none = score_job(non_matching_job, valentina)
        assert m_match.match_score > m_none.match_score

    def test_role_title_reason_included_on_match(self, valentina):
        job = make_job(job_title="React Developer Junior")
        match = score_job(job, valentina)
        combined = " ".join(match.match_reasons).lower()
        assert "react developer" in combined or "título" in combined


# ---------------------------------------------------------------------------
# Salary adjustments
# ---------------------------------------------------------------------------

class TestSalaryAdjustments:
    def test_salary_below_expected_but_above_minimum_penalises(self):
        # Penalty fires when: salary_max >= restriction.min_salary (passes filter)
        # but salary_max < expected_salary.min (below desired range).
        # Use a profile where expected_min (800k) > restriction_min (600k) so there
        # is a "grey zone" where penalty applies without triggering the hard filter.
        profile = StudentProfile(
            profile_id="test_sal",
            name="Test",
            cohort="C",
            stack=Stack(primary=["Python"], secondary=[], tools=[]),
            seniority="junior",
            location=ProfileLocation(city="San José", country="Costa Rica", timezone="UTC"),
            modality=["remote"],
            languages=[LanguageSkill(language="Spanish", level="native")],
            availability=Availability(start_date="2026-06-01", hours_per_week=40, type="full-time"),
            expected_salary=ExpectedSalary(min=800_000, max=1_200_000, currency="CRC", period="monthly"),
            restrictions=Restrictions(
                min_salary=600_000, currency="CRC", excluded_modalities=[],
                excluded_locations=[], requires_visa_sponsorship=False, max_travel_percent=None,
            ),
            preferences=Preferences(
                company_size=["startup"], sectors=["tech"], roles=["Developer"],
                avoid_sectors=[], growth_priority="learning",
            ),
        )
        # 700k: above hard-filter min (600k) but below expected min (800k) → penalty
        low_offer = make_job(salary_min=600_000, salary_max=700_000)
        # 900k: within expected range (800k–1 200k) → no penalty
        good_offer = make_job(salary_min=800_000, salary_max=900_000)
        m_low = score_job(low_offer, profile)
        m_good = score_job(good_offer, profile)
        assert m_low.match_score < m_good.match_score
        assert any("debajo" in g.lower() for g in m_low.gaps)

    def test_salary_bonus_for_salary_growth_priority(self):
        salary_seeker = StudentProfile(
            profile_id="x",
            name="X",
            cohort="C",
            stack=Stack(primary=["Python"], secondary=[], tools=[]),
            seniority="junior",
            location=ProfileLocation(city="San José", country="Costa Rica", timezone="UTC"),
            modality=["remote"],
            languages=[LanguageSkill(language="Spanish", level="native")],
            availability=Availability(start_date="2026-06-01", hours_per_week=40, type="full-time"),
            expected_salary=ExpectedSalary(min=500_000, max=800_000, currency="CRC", period="monthly"),
            restrictions=Restrictions(
                min_salary=500_000, currency="CRC", excluded_modalities=[],
                excluded_locations=[], requires_visa_sponsorship=False, max_travel_percent=None,
            ),
            preferences=Preferences(
                company_size=["startup"], sectors=["tech"], roles=["Developer"],
                avoid_sectors=[], growth_priority="salary",
            ),
        )
        # Offer max=1_000_000 > expected max=800_000 → +10 bonus
        job = make_job(salary_max=1_000_000)
        match = score_job(job, salary_seeker)
        assert any("salarial" in r.lower() for r in match.match_reasons)


# ---------------------------------------------------------------------------
# Growth priority: learning
# ---------------------------------------------------------------------------

class TestGrowthPriorityLearning:
    def test_learning_increases_stack_weight(self, valentina):
        # Valentina has learning priority → stack weight=40 instead of 35
        # 2/2 match: 40 pts stack + 15 seniority + 15 language + 0 size + 5 role ≥ 75
        job = make_job(
            job_title="Frontend Developer",
            stack_keywords=["React", "JavaScript"],
            seniority_signal="junior",
            description_raw="Startup de tecnología digital. Buscamos desarrollador junior. " * 3,
        )
        match = score_job(job, valentina)
        assert match.match_score >= 75

    def test_learning_reduces_seniority_weight(self, valentina):
        # With learning: seniority weight=15 (not 20)
        junior_job = make_job(seniority_signal="junior")
        match_learning = score_job(junior_job, valentina)

        # Simulate a non-learning profile with same stack
        stability_profile = StudentProfile(
            **{**valentina.__dict__,
               "preferences": Preferences(
                   **{**valentina.preferences.__dict__,
                      "growth_priority": "stability"}
               )}
        )
        match_stability = score_job(junior_job, stability_profile)

        # Stability has seniority weight=20 vs learning=15.
        # Stack weight flips (35 vs 40). Net: stability gets +5 seniority, learning gets +5 stack.
        # They should be equal OR differ by exactly 0 (since the weights cancel).
        # What matters: learning does NOT penalise compared to stability on same input.
        assert abs(match_learning.match_score - match_stability.match_score) <= 5


# ---------------------------------------------------------------------------
# Negative cases — incompatible stack, location, seniority
# ---------------------------------------------------------------------------

class TestNegativeCases:
    def test_incompatible_stack_results_in_low_score(self, valentina):
        # PHP/COBOL job for a React developer — passes hard filters, stack score = 0.
        # Neutral title and description to avoid sector/size bonuses masking the low score.
        job = make_job(
            job_title="Analista de Sistemas Legacy",
            company_name="Empresa Ejemplo S.R.L.",
            stack_keywords=["PHP", "COBOL", "Delphi", "Fortran"],
            description_raw="Mantenimiento de sistemas heredados. Soporte administrativo. " * 4,
            modality=["remote"],
            seniority_signal="junior",
        )
        results = rank_jobs([job], valentina)
        assert results[0].hard_filters_passed is True
        assert results[0].match_score < 40

    def test_incompatible_location_triggers_hard_filter(self, andres):
        # Andrés: excluded_locations = ["outside Costa Rica"]
        job = make_job(location_country="Spain")
        results = rank_jobs([job], andres)
        assert results[0].hard_filters_passed is False
        assert results[0].match_score == 0
        assert "Oferta descartada" in results[0].action

    def test_wrong_seniority_reduces_score_not_filters(self, valentina):
        # Senior job: passes hard filters but loses seniority points
        job = make_job(seniority_signal="senior", modality=["remote"])
        results = rank_jobs([job], valentina)
        assert results[0].hard_filters_passed is True   # not a hard filter
        assert any("senior" in g.lower() for g in results[0].gaps)


# ---------------------------------------------------------------------------
# rank_jobs — ordering and completeness
# ---------------------------------------------------------------------------

class TestRankJobs:
    def test_returns_all_jobs(self, valentina):
        jobs = [
            make_job(job_id="j1", modality=["remote"]),
            make_job(job_id="j2", modality=["on-site"]),
        ]
        results = rank_jobs(jobs, valentina)
        assert len(results) == 2

    def test_passing_jobs_ranked_before_filtered_jobs(self, valentina):
        filtered = make_job(job_id="j_filtered", modality=["on-site"])
        passing = make_job(job_id="j_passing", modality=["remote"])
        results = rank_jobs([filtered, passing], valentina)
        assert results[0].job_id == "j_passing"
        assert results[0].hard_filters_passed is True
        assert results[1].hard_filters_passed is False

    def test_filtered_jobs_have_zero_score_and_correct_action(self, valentina):
        job = make_job(modality=["on-site"])
        results = rank_jobs([job], valentina)
        assert results[0].match_score == 0
        assert results[0].hard_filters_passed is False
        assert "Oferta descartada" in results[0].action

    def test_jobs_sorted_by_score_descending(self, valentina):
        low = make_job(job_id="j_low", stack_keywords=["PHP", "COBOL", "Perl"])
        high = make_job(job_id="j_high", stack_keywords=["React", "JavaScript"])
        results = rank_jobs([low, high], valentina)
        assert results[0].job_id == "j_high"
        assert results[0].match_score >= results[1].match_score

    def test_match_reasons_not_empty_for_passing_job(self, valentina):
        job = make_job(stack_keywords=["React"])
        results = rank_jobs([job], valentina)
        assert len(results[0].match_reasons) > 0

    def test_filtered_job_reasons_contain_filter_cause(self, valentina):
        job = make_job(salary_max=100_000)  # way below 600k minimum
        results = rank_jobs([job], valentina)
        assert results[0].hard_filters_passed is False
        assert any("salario" in g.lower() for g in results[0].gaps)

    def test_empty_job_list_returns_empty_results(self, valentina):
        assert rank_jobs([], valentina) == []

    def test_score_clamped_to_100(self, valentina):
        # Job matching everything should not exceed 100
        job = make_job(
            job_title="React Developer Junior",
            stack_keywords=["React", "JavaScript", "HTML", "CSS", "TypeScript", "Git"],
            seniority_signal="junior",
            description_raw=(
                "Startup de tecnología digital. React developer junior. "
                "Buen salario y ambiente. " * 4
            ),
            salary_min=700_000,
            salary_max=1_200_000,
        )
        results = rank_jobs([job], valentina)
        assert results[0].match_score <= 100

    def test_score_never_negative(self, valentina):
        # Job in avoided sector, wrong stack, wrong seniority — score must be ≥ 0
        job = make_job(
            stack_keywords=["COBOL", "Fortran"],
            seniority_signal="senior",
            description_raw="Casino online gambling apuestas tabaco cigarro. " * 4,
        )
        results = rank_jobs([job], valentina)
        assert results[0].match_score >= 0

    def test_happy_path_valentina_frontend_job(self, valentina):
        """Valentina + ideal frontend job should produce excellent match."""
        job = make_job(
            job_id="frontend_ideal",
            job_title="Desarrollador Frontend Junior (React)",
            company_name="Startup Tica S.A.",
            modality=["hybrid"],
            salary_min=650_000,
            salary_max=850_000,
            stack_keywords=["React", "JavaScript", "HTML5", "CSS3", "Git"],
            seniority_signal="junior",
            description_raw=(
                "Únete a nuestra startup de tecnología digital como desarrollador "
                "frontend junior. Requisitos: React o Vue.js, JavaScript, HTML5, CSS3, Git. "
                "Ofrecemos: modalidad híbrida, seguro médico, plan dental. "
                "Salario: ₡650,000 – ₡850,000 mensuales. " * 2
            ),
        )
        results = rank_jobs([job], valentina)
        match = results[0]
        assert match.hard_filters_passed is True
        assert match.match_score >= 80
        assert match.action == "Aplicar de inmediato"
        assert len(match.match_reasons) >= 3
