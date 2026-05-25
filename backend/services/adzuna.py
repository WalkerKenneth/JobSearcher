import os
import httpx
from models.job import Job, JobSearchResponse

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")
BASE_URL = "https://api.adzuna.com/v1/api/jobs"

SUPPORTED_COUNTRIES: dict[str, str] = {
    "us": "Estados Unidos",
    "gb": "Reino Unido",
    "au": "Australia",
    "ca": "Canadá",
    "de": "Alemania",
    "fr": "Francia",
    "in": "India",
    "it": "Italia",
    "nl": "Países Bajos",
    "nz": "Nueva Zelanda",
    "pl": "Polonia",
    "sg": "Singapur",
    "za": "Sudáfrica",
    "br": "Brasil",
    "mx": "México",
    "at": "Austria",
    "be": "Bélgica",
    "ru": "Rusia",
}

CATEGORIES: dict[str, str] = {
    "it-jobs": "Tecnología / IT",
    "engineering-jobs": "Ingeniería",
    "accounting-finance-jobs": "Contabilidad / Finanzas",
    "healthcare-nursing-jobs": "Salud",
    "hr-jobs": "Recursos Humanos",
    "pr-advertising-marketing-jobs": "Marketing / Publicidad",
    "legal-jobs": "Legal",
    "logistics-warehouse-jobs": "Logística",
    "sales-jobs": "Ventas",
    "teaching-jobs": "Educación",
    "scientific-qa-jobs": "Ciencia / QA",
    "creative-design-jobs": "Diseño / Creatividad",
    "retail-jobs": "Retail",
    "customer-services-jobs": "Atención al Cliente",
    "manufacturing-jobs": "Manufactura",
    "energy-oil-gas-jobs": "Energía / Petróleo",
    "other-general-jobs": "Otros",
}

_MOCK_JOBS = [
    {
        "id": "mock-1",
        "title": "Software Engineer (Python)",
        "company": "TechCorp",
        "location": "Remote",
        "description": "Buscamos un Software Engineer con experiencia en Python y FastAPI para trabajar en proyectos de alto impacto.",
        "url": "#",
        "salary_min": 60000,
        "salary_max": 90000,
        "created": "2026-05-20T10:00:00Z",
        "category": "Tecnología / IT",
    },
    {
        "id": "mock-2",
        "title": "Frontend Developer (React)",
        "company": "DigitalAgency",
        "location": "Ciudad de México, MX",
        "description": "Desarrollador Frontend con al menos 2 años de experiencia en React, TypeScript y Tailwind CSS.",
        "url": "#",
        "salary_min": 45000,
        "salary_max": 75000,
        "created": "2026-05-19T08:30:00Z",
        "category": "Tecnología / IT",
    },
    {
        "id": "mock-3",
        "title": "Data Analyst",
        "company": "Finanzas SA",
        "location": "Buenos Aires, AR",
        "description": "Analista de datos para el área de finanzas. Manejo de SQL, Excel avanzado y Power BI.",
        "url": "#",
        "salary_min": 35000,
        "salary_max": 55000,
        "created": "2026-05-18T14:00:00Z",
        "category": "Contabilidad / Finanzas",
    },
    {
        "id": "mock-4",
        "title": "DevOps Engineer",
        "company": "CloudSystems",
        "location": "Remote",
        "description": "Ingeniero DevOps con experiencia en AWS, Docker, Kubernetes y CI/CD pipelines.",
        "url": "#",
        "salary_min": 80000,
        "salary_max": 120000,
        "created": "2026-05-17T09:00:00Z",
        "category": "Tecnología / IT",
    },
    {
        "id": "mock-5",
        "title": "Marketing Manager",
        "company": "BrandCo",
        "location": "São Paulo, BR",
        "description": "Gerente de Marketing Digital con experiencia en campañas digitales, SEO y redes sociales.",
        "url": "#",
        "salary_min": 50000,
        "salary_max": 70000,
        "created": "2026-05-16T11:00:00Z",
        "category": "Marketing / Publicidad",
    },
]


async def search_jobs(
    country: str,
    category: str = "",
    keyword: str = "",
    page: int = 1,
    results_per_page: int = 10,
) -> JobSearchResponse:
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        return _mock_response(page, results_per_page)

    params: dict = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "results_per_page": results_per_page,
        "content-type": "application/json",
    }
    if keyword:
        params["what"] = keyword
    if category:
        params["category"] = category

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/{country}/search/{page}",
            params=params,
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()

    jobs = [
        Job(
            id=str(r.get("id", "")),
            title=r.get("title", ""),
            company=r.get("company", {}).get("display_name", "N/A"),
            location=r.get("location", {}).get("display_name", ""),
            description=r.get("description", ""),
            url=r.get("redirect_url", ""),
            salary_min=r.get("salary_min"),
            salary_max=r.get("salary_max"),
            created=r.get("created", ""),
            category=r.get("category", {}).get("label", ""),
        )
        for r in data.get("results", [])
    ]

    total = data.get("count", 0)
    pages = max(1, (total + results_per_page - 1) // results_per_page)

    return JobSearchResponse(jobs=jobs, total=total, page=page, pages=min(pages, 50))


def _mock_response(page: int, results_per_page: int) -> JobSearchResponse:
    jobs = [Job(**j) for j in _MOCK_JOBS]
    return JobSearchResponse(jobs=jobs, total=len(jobs), page=page, pages=1)
