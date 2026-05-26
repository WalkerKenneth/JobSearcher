"""Shared pytest fixtures."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.session import create_indexes


@pytest.fixture
def db_session():
    """
    In-memory SQLite session shared across all queries in a single test.
    StaticPool ensures all sessions share the same connection.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    create_indexes(engine)

    Session = sessionmaker(bind=engine, autoflush=True, autocommit=False)
    session = Session()
    yield session
    session.close()
    engine.dispose()
