import os
from pathlib import Path

_dotenv = Path(__file__).parent.parent / ".env"
if _dotenv.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_dotenv)
    except ImportError:
        pass

JSEARCH_API_KEY: str = os.environ.get("JSEARCH_API_KEY", "")
SERPAPI_API_KEY: str = os.environ.get("SERPAPI_API_KEY", "")

_default_db = str(Path(__file__).parent.parent / "data" / "jobs.db")
DATABASE_URL: str = os.environ.get("DATABASE_URL", f"sqlite:///{_default_db}")
JOB_CACHE_TTL_SECONDS: int = int(os.environ.get("JOB_CACHE_TTL_SECONDS", "86400"))
