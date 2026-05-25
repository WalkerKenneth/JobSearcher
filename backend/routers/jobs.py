from fastapi import APIRouter, HTTPException, Query
from models.job import Category, Country, JobSearchResponse
from services import adzuna

router = APIRouter()


@router.get("/jobs", response_model=JobSearchResponse)
async def get_jobs(
    country: str = Query(..., description="Código de país (ej: us, gb, mx)"),
    category: str = Query("", description="Categoría / rubro"),
    keyword: str = Query("", description="Palabra clave"),
    page: int = Query(1, ge=1, le=50),
):
    if country not in adzuna.SUPPORTED_COUNTRIES:
        raise HTTPException(
            status_code=400,
            detail=f"País '{country}' no soportado. Países válidos: {', '.join(adzuna.SUPPORTED_COUNTRIES)}",
        )
    return await adzuna.search_jobs(country, category, keyword, page)


@router.get("/countries", response_model=list[Country])
async def get_countries():
    return [Country(code=k, name=v) for k, v in adzuna.SUPPORTED_COUNTRIES.items()]


@router.get("/categories", response_model=list[Category])
async def get_categories():
    return [Category(code=k, name=v) for k, v in adzuna.CATEGORIES.items()]
