from pydantic import BaseModel
from typing import Optional


class Job(BaseModel):
    id: str
    title: str
    company: str
    location: str
    description: str
    url: str
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    created: str
    category: str


class JobSearchResponse(BaseModel):
    jobs: list[Job]
    total: int
    page: int
    pages: int


class Country(BaseModel):
    code: str
    name: str


class Category(BaseModel):
    code: str
    name: str
