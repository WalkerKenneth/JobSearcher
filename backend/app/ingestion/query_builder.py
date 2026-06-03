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


def build_jsearch_params_all(profile: dict) -> list[dict]:
    """Genera un dict de params por cada combinación rol × tech primaria (máx 3 × 2).

    Usado por pipeline.fetch_and_normalize para cubrir el perfil completo en lugar de
    solo roles[0]/primary[0]. Cada query usa num_pages=1 para no multiplicar la cuota.
    Cae a build_jsearch_params si el perfil no tiene roles o tech definidos.
    """
    seniority = profile.get("seniority", "junior")
    roles = profile["preferences"]["roles"][:3]
    techs = profile["stack"]["primary"][:2]

    if not roles or not techs:
        return [build_jsearch_params(profile)]

    excluded = profile["restrictions"].get("excluded_modalities", [])
    remote_only = "on-site" in excluded and "hybrid" in excluded
    location = profile["location"]["country"]

    seen: set[str] = set()
    params_list: list[dict] = []
    for role in roles:
        for tech in techs:
            query = f"{seniority} {role} {tech}"
            if query in seen:
                continue
            seen.add(query)
            params_list.append({
                "query": query,
                "location": location,
                "remote_jobs_only": str(remote_only).lower(),
                "date_posted": "month",
                "num_pages": "1",
            })
    return params_list


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
