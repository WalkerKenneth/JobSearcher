from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import DATABASE_URL
from app.db.models import Base


def _ensure_data_dir(url: str) -> None:
    if "sqlite:///" not in url:
        return
    path_str = url.split("sqlite:///", 1)[1]
    if not path_str or path_str == ":memory:":
        return
    Path(path_str).parent.mkdir(parents=True, exist_ok=True)


def create_indexes(engine) -> None:
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_job_dedup_key "
            "ON job_postings(dedup_key) WHERE canonical_id IS NULL"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_job_apply_url ON job_postings(apply_url)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_job_last_seen ON job_postings(last_seen)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_job_status ON job_postings(status)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_job_source ON job_postings(source)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_snapshot_job_id ON raw_snapshots(job_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_snapshot_fetched ON raw_snapshots(fetched_at)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_rec_profile ON recommendations(profile_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_rec_status ON recommendations(status)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_feedback_rec ON feedback_events(rec_id)"
        ))
        conn.commit()


def build_engine(url: str):
    _ensure_data_dir(url)
    # NullPool para SQLite: cada operación obtiene su propia conexión y la libera
    # inmediatamente. Evita errores "database is locked" cuando múltiples workers
    # Celery comparten el mismo proceso padre al hacer fork.
    pool_kwargs = {"poolclass": NullPool} if "sqlite" in url else {}
    eng = create_engine(url, connect_args={"check_same_thread": False}, **pool_kwargs)

    @event.listens_for(eng, "connect")
    def _set_pragmas(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(eng)
    create_indexes(eng)
    return eng


engine = build_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=True, autocommit=False)
