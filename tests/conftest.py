import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from collections.abc import Iterator  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture()
def session(engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@pytest.fixture()
def client(session):
    from fastapi.testclient import TestClient

    from aiqa.api.main import app
    from aiqa.db import get_session

    def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def mock_page():
    """A MagicMock standing in for a playwright.sync_api.Page."""
    page = MagicMock()
    page.url = "https://example.test/"
    return page
