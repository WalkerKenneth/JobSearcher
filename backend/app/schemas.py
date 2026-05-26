from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# StudentProfile schema
# ---------------------------------------------------------------------------

@dataclass
class Stack:
    primary: list[str]
    secondary: list[str]
    tools: list[str]

    @classmethod
    def from_dict(cls, d: dict) -> "Stack":
        return cls(
            primary=d.get("primary", []),
            secondary=d.get("secondary", []),
            tools=d.get("tools", []),
        )


@dataclass
class ProfileLocation:
    city: str
    country: str
    timezone: str

    @classmethod
    def from_dict(cls, d: dict) -> "ProfileLocation":
        return cls(
            city=d.get("city", ""),
            country=d.get("country", ""),
            timezone=d.get("timezone", ""),
        )


@dataclass
class LanguageSkill:
    language: str
    level: Literal["basic", "intermediate", "advanced", "native"]

    @classmethod
    def from_dict(cls, d: dict) -> "LanguageSkill":
        return cls(language=d["language"], level=d["level"])


@dataclass
class Availability:
    start_date: str
    hours_per_week: int
    type: Literal["full-time", "part-time"]

    @classmethod
    def from_dict(cls, d: dict) -> "Availability":
        return cls(
            start_date=d.get("start_date", ""),
            hours_per_week=d.get("hours_per_week", 40),
            type=d.get("type", "full-time"),
        )


@dataclass
class ExpectedSalary:
    min: float
    max: float
    currency: str
    period: Literal["monthly", "annual"]

    @classmethod
    def from_dict(cls, d: dict) -> "ExpectedSalary":
        return cls(
            min=float(d.get("min", 0)),
            max=float(d.get("max", 0)),
            currency=d.get("currency", ""),
            period=d.get("period", "monthly"),
        )


@dataclass
class Restrictions:
    min_salary: float | None
    currency: str
    excluded_modalities: list[str]
    excluded_locations: list[str]
    requires_visa_sponsorship: bool
    max_travel_percent: float | None

    @classmethod
    def from_dict(cls, d: dict) -> "Restrictions":
        return cls(
            min_salary=d.get("min_salary"),
            currency=d.get("currency", ""),
            excluded_modalities=d.get("excluded_modalities", []),
            excluded_locations=d.get("excluded_locations", []),
            requires_visa_sponsorship=d.get("requires_visa_sponsorship", False),
            max_travel_percent=d.get("max_travel_percent"),
        )


@dataclass
class Preferences:
    company_size: list[str]
    sectors: list[str]
    roles: list[str]
    avoid_sectors: list[str]
    growth_priority: Literal["learning", "salary", "stability", "impact"]

    @classmethod
    def from_dict(cls, d: dict) -> "Preferences":
        return cls(
            company_size=d.get("company_size", []),
            sectors=d.get("sectors", []),
            roles=d.get("roles", []),
            avoid_sectors=d.get("avoid_sectors", []),
            growth_priority=d.get("growth_priority", "learning"),
        )


@dataclass
class StudentProfile:
    profile_id: str
    name: str
    cohort: str
    stack: Stack
    seniority: Literal["junior", "mid"]
    location: ProfileLocation
    modality: list[str]
    languages: list[LanguageSkill]
    availability: Availability
    expected_salary: ExpectedSalary
    restrictions: Restrictions
    preferences: Preferences

    @classmethod
    def from_dict(cls, d: dict) -> "StudentProfile":
        return cls(
            profile_id=d["profile_id"],
            name=d["name"],
            cohort=d.get("cohort", ""),
            stack=Stack.from_dict(d["stack"]),
            seniority=d["seniority"],
            location=ProfileLocation.from_dict(d["location"]),
            modality=d.get("modality", []),
            languages=[LanguageSkill.from_dict(lang) for lang in d.get("languages", [])],
            availability=Availability.from_dict(d.get("availability", {})),
            expected_salary=ExpectedSalary.from_dict(d.get("expected_salary", {})),
            restrictions=Restrictions.from_dict(d.get("restrictions", {})),
            preferences=Preferences.from_dict(d.get("preferences", {})),
        )


# ---------------------------------------------------------------------------
# NormalizedJob schema
# ---------------------------------------------------------------------------

@dataclass
class NormalizedJob:
    job_id: str
    source: Literal["jsearch", "serpapi"]
    fetched_at: str

    job_title: str
    company_name: str
    location_city: str | None
    location_country: str
    is_remote: bool
    modality: list[str]

    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    salary_period: Literal["monthly", "annual"] | None

    description_raw: str
    qualifications_raw: list[str]
    posted_at: str | None
    apply_url: str

    stack_keywords: list[str] = field(default_factory=list)
    seniority_signal: Literal["junior", "mid", "senior", "unknown"] = "unknown"
    raw_response: dict = field(default_factory=dict)
