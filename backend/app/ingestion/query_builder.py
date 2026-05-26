"""Translates a StudentProfile dict into API query parameters."""

_COUNTRY_GL: dict[str, str] = {
    "Costa Rica": "cr",
    "Mexico": "mx",
    "Colombia": "co",
    "Argentina": "ar",
    "Brasil": "br",
    "Brazil": "br",
}


def _query_term(profile: dict) -> str:
    seniority = profile.get("seniority", "junior")
    role = profile["preferences"]["roles"][0]
    tech = profile["stack"]["primary"][0]
    return f"{seniority} {role} {tech}"


def build_jsearch_params(profile: dict) -> dict:
    excluded = profile["restrictions"].get("excluded_modalities", [])
    remote_only = "on-site" in excluded and "hybrid" in excluded
    return {
        "query": _query_term(profile),
        "location": profile["location"]["country"],
        "remote_jobs_only": str(remote_only).lower(),
        "date_posted": "month",
        "num_pages": "2",
    }


def build_serpapi_params(profile: dict) -> dict:
    country = profile["location"]["country"]
    return {
        "engine": "google_jobs",
        "q": _query_term(profile),
        "location": country,
        "gl": _COUNTRY_GL.get(country, "cr"),
        "hl": "es",
        "chips": "date_posted:month",
    }
