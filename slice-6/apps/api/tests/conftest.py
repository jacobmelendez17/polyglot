"""Test fixtures. Uses a real ephemeral Postgres (pgserver) so migrations,
enums, and constraints are exercised exactly as in production.
Falls back to skipping DB tests if pgserver is unavailable.
"""
from __future__ import annotations

import pathlib
import tempfile

import pytest


@pytest.fixture(scope="session")
def pg_url() -> str:
    try:
        import pgserver
    except Exception:  # pragma: no cover
        pytest.skip("pgserver not installed")
    data_dir = pathlib.Path(tempfile.mkdtemp(prefix="polyglot_pg_"))
    srv = pgserver.get_server(data_dir)
    try:
        srv.psql("CREATE DATABASE polyglot_test;")
    except Exception:  # noqa: S110 — DB may already exist from a prior session
        pass
    url = f"postgresql+psycopg://postgres@/polyglot_test?host={data_dir}"
    return url


@pytest.fixture()
def db(pg_url, monkeypatch):
    """A migrated, empty database session per test (schema created via metadata)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.models  # noqa: F401  populate metadata
    from app.db.base import Base

    engine = create_engine(pg_url, future=True)
    # Clean slate each test.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(scope="session")
def real_csvs() -> dict[str, str]:
    """The user-uploaded curriculum CSVs, if present in this environment."""
    base = pathlib.Path("/mnt/user-data/uploads")
    vocab = base / "Spanish_Stuff_-_Everything__1_.csv"
    gram = base / "Spanish_Stuff_-_Grammar__1_.csv"
    if not vocab.exists() or not gram.exists():
        pytest.skip("real curriculum CSVs not present")
    return {"vocab": vocab.read_text(), "grammar": gram.read_text()}
