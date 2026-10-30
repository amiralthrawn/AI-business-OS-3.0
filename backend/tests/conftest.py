import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.entities import Base
from app.core.events.bus import InProcessEventBus


@pytest.fixture()
def db_engine():
    """An in-memory SQLite database, schema built directly from the ORM models
    rather than via Alembic (the right tool for real migrations, unnecessary
    overhead for test setup).

    StaticPool forces every checkout to reuse the same underlying connection:
    without it, a new connection to ":memory:" is a distinct, schema-less
    database, which breaks as soon as more than one connection is opened (e.g.
    a FastAPI TestClient request running in its own thread, or a handler that
    opens its own session via a session factory)."""

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session_factory(db_engine):
    """A callable that opens a new Session bound to the test database, for
    handlers that manage their own session lifetime (see
    app.core.events.log_handler and app.intelligence.risks.handlers)."""

    return sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db_session(session_factory):
    """A single session for setting up test fixtures and asserting on results,
    backed by the same connection as `session_factory`."""

    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def event_bus():
    return InProcessEventBus()
