from sqlalchemy import (
    Column, Integer, Float, Text, ForeignKey, CheckConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship

_FEEDBACK_STATUS_CHECK = (
    "status IN ('recommended', 'seen', 'discarded', 'applied', 'needs_coach')"
)


class Base(DeclarativeBase):
    pass


class JobPosting(Base):
    __tablename__ = "job_postings"

    job_id = Column(Text, primary_key=True)
    source = Column(Text, nullable=False)
    dedup_key = Column(Text, nullable=False)
    canonical_id = Column(Text, ForeignKey("job_postings.job_id"), nullable=True)
    duplicate_ids = Column(Text, nullable=False, default="[]")

    first_seen = Column(Text, nullable=False)
    last_seen = Column(Text, nullable=False)
    fetched_at = Column(Text, nullable=False)
    fetch_count = Column(Integer, nullable=False, default=1)
    status = Column(Text, nullable=False, default="active")
    is_active = Column(Integer, nullable=False, default=1)

    job_title = Column(Text, nullable=False)
    company_name = Column(Text, nullable=False)
    location_city = Column(Text, nullable=True)
    location_country = Column(Text, nullable=False)
    is_remote = Column(Integer, nullable=False)
    modality = Column(Text, nullable=False, default="[]")
    apply_url = Column(Text, nullable=False)

    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    salary_currency = Column(Text, nullable=True)
    salary_period = Column(Text, nullable=True)

    posted_at = Column(Text, nullable=True)
    description_raw = Column(Text, nullable=False)
    qualifications_raw = Column(Text, nullable=False, default="[]")
    stack_keywords = Column(Text, nullable=False, default="[]")
    seniority_signal = Column(Text, nullable=False, default="unknown")

    snapshots = relationship(
        "RawSnapshot", back_populates="posting", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("source IN ('jsearch', 'serpapi')", name="ck_job_source"),
        CheckConstraint("status IN ('active', 'stale', 'expired')", name="ck_job_status"),
        CheckConstraint(
            "seniority_signal IN ('junior', 'mid', 'senior', 'unknown')",
            name="ck_job_seniority",
        ),
        CheckConstraint("salary_period IN ('monthly', 'annual') OR salary_period IS NULL", name="ck_job_salary_period"),
    )


class RawSnapshot(Base):
    __tablename__ = "raw_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Text, ForeignKey("job_postings.job_id"), nullable=False)
    source = Column(Text, nullable=False)
    fetched_at = Column(Text, nullable=False)
    raw_response = Column(Text, nullable=False)

    posting = relationship("JobPosting", back_populates="snapshots")


class QueryCache(Base):
    __tablename__ = "query_cache"

    cache_key = Column(Text, primary_key=True)
    created_at = Column(Text, nullable=False)
    expires_at = Column(Text, nullable=False)
    raw_response = Column(Text, nullable=False)


class Recommendation(Base):
    __tablename__ = "recommendations"

    rec_id = Column(Text, primary_key=True)
    profile_id = Column(Text, nullable=False)
    job_id = Column(Text, ForeignKey("job_postings.job_id"), nullable=False)
    generated_at = Column(Text, nullable=False)
    match_score = Column(Integer, nullable=False)
    match_reasons = Column(Text, nullable=False, default="[]")
    gaps = Column(Text, nullable=False, default="[]")
    next_action = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="recommended")
    status_updated_at = Column(Text, nullable=False)

    feedback_events = relationship(
        "FeedbackEvent", back_populates="recommendation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(_FEEDBACK_STATUS_CHECK, name="ck_rec_status"),
    )


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rec_id = Column(Text, ForeignKey("recommendations.rec_id"), nullable=False)
    status = Column(Text, nullable=False)
    note = Column(Text, nullable=False, default="")
    recorded_at = Column(Text, nullable=False)

    recommendation = relationship("Recommendation", back_populates="feedback_events")

    __table_args__ = (
        CheckConstraint(_FEEDBACK_STATUS_CHECK, name="ck_feedback_status"),
    )
