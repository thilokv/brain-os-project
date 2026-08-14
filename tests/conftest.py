"""Shared pytest fixtures for the Brain OS test suite.

Each test gets a fully isolated SQLite/Chroma/checkpoint stack under
pytest's per-test tmp_path, driven through a real FastAPI TestClient so
the whole app.main lifespan (schema creation, checkpointer, vector
memory) exercises exactly what runs in production.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.utils.config import get_settings

# Test-only credential -- never a real secret, never read from the
# environment or any .env file. Exists solely so tests can authenticate
# against the same bearer-token mechanism production uses.
TEST_API_TOKEN = "test-only-brain-os-token-do-not-use-in-prod"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "brain_os.db"))
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "checkpoints.db"))
    monkeypatch.setenv("CHROMA_PERSIST_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "")
    monkeypatch.setenv("BRAIN_OS_API_TOKEN", TEST_API_TOKEN)
    get_settings.cache_clear()

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()


@pytest.fixture
def auth_headers():
    """Authorization header for the test-only token set on the `client` fixture."""
    return {"Authorization": f"Bearer {TEST_API_TOKEN}"}
