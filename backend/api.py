#!/usr/bin/env python3
"""FastAPI REST API for JobSearcher.

Usage:
    uvicorn api:app --reload --port 8000
"""

import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel

from app.delivery.repository import get_recommendations, record_feedback
from app.ingestion.repository import list_all_jobs, load_job
from app.profiles.repository import delete_profile, list_profiles, load_profile, upsert_profile
from app.schemas import StudentProfile

app = FastAPI(title="JobSearcher API", version="0.1.0")


@app.get("/api/jobs")
def jobs_list(
    status: str | None = Query(None),
    source: str | None = Query(None),
    is_remote: bool | None = Query(None),
    seniority: str | None = Query(None),
    q: str | None = Query(None),
):
    jobs = list_all_jobs()
    if status:
        jobs = [j for j in jobs if j["status"] == status]
    if source:
        jobs = [j for j in jobs if j["source"] == source]
    if is_remote is not None:
        jobs = [j for j in jobs if j["is_remote"] == is_remote]
    if seniority:
        jobs = [j for j in jobs if j["seniority_signal"] == seniority]
    if q:
        q_lower = q.lower()
        jobs = [
            j for j in jobs
            if q_lower in j["job_title"].lower() or q_lower in j["company_name"].lower()
        ]
    return jobs


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: str):
    job = load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/profiles")
def profiles_list():
    profiles = list_profiles()
    return [
        {
            "profile_id": p.profile_id,
            "name": p.name,
            "cohort": p.cohort,
            "seniority": p.seniority,
        }
        for p in profiles
    ]


@app.post("/api/profiles", status_code=201)
async def profile_create(request: Request):
    data = await request.json()
    try:
        profile = StudentProfile.from_dict(data)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    action = upsert_profile(profile)
    return {"profile_id": profile.profile_id, "action": action}


@app.get("/api/profiles/{profile_id}")
def profile_detail(profile_id: str):
    profile = load_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return dataclasses.asdict(profile)


@app.delete("/api/profiles/{profile_id}")
def profile_delete(profile_id: str):
    found = delete_profile(profile_id)
    if not found:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"ok": True}


@app.get("/api/recommendations/{profile_id}")
def recommendations_list(profile_id: str, status: str | None = Query(None)):
    recs = get_recommendations(profile_id, status=status)
    enriched = []
    for r in recs:
        job = load_job(r["job_id"])
        entry = dict(r)
        if job:
            entry["title"] = job["job_title"]
            entry["company"] = job["company_name"]
            loc_parts = [p for p in [job.get("location_city"), job.get("location_country")] if p]
            entry["location"] = ", ".join(loc_parts) if loc_parts else "Sin ubicación"
            entry["apply_url"] = job["apply_url"]
            entry["is_remote"] = job["is_remote"]
        enriched.append(entry)
    return enriched


class FeedbackBody(BaseModel):
    status: str
    note: str = ""


@app.post("/api/feedback/{rec_id}")
def post_feedback(rec_id: str, body: FeedbackBody):
    ok = record_feedback(rec_id, body.status, body.note)
    if not ok:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return {"ok": True}
