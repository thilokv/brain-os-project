"""Tests for Phase 2A.1 -- PostgreSQL connection foundation.

These tests never touch /brain-os/*, the original five SQLite tables, or
any application route -- app/database/postgres_connection.py is
free-standing infrastructure nothing else depends on yet.

Tests that need a real PostgreSQL server are skipped cleanly (not
failed) when the POSTGRES_TEST_DSN environment variable is unset, since
no such server is assumed to exist in every environment this suite runs
in. The failure-path tests (invalid DSN / unreachable host) need no real
server and always run.
"""

from __future__ import annotations

import os

import pytest

from app.database.postgres_connection import PostgresConnectionError, get_postgres_connection
from app.utils.config import Settings

POSTGRES_TEST_DSN = os.environ.get("POSTGRES_TEST_DSN", "")

requires_postgres = pytest.mark.skipif(
    not POSTGRES_TEST_DSN,
    reason="POSTGRES_TEST_DSN not set -- no PostgreSQL test server configured for this environment.",
)


def test_database_backend_defaults_to_sqlite(monkeypatch):
    """Confirms the default configuration never touches Postgres."""
    monkeypatch.delenv("DATABASE_BACKEND", raising=False)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    settings = Settings()
    assert settings.database_backend == "sqlite"
    assert settings.postgres_dsn == ""


def test_invalid_dsn_raises_clear_error_without_hanging():
    """A syntactically invalid DSN fails immediately with a specific,
    catchable exception -- not a bare driver traceback, not a hang."""
    with pytest.raises(PostgresConnectionError, match="Invalid PostgreSQL DSN"):
        with get_postgres_connection("not-a-valid-dsn-at-all"):
            pass


def test_unreachable_host_fails_within_timeout_without_hanging():
    """An unreachable host fails within the configured connect timeout
    rather than blocking the caller indefinitely."""
    import time

    start = time.monotonic()
    with pytest.raises(PostgresConnectionError, match="Could not connect to PostgreSQL"):
        # TEST-NET-1 (RFC 5737): guaranteed non-routable, so this
        # reliably exercises the timeout path rather than depending on
        # a real network condition.
        with get_postgres_connection("postgresql://user:pass@192.0.2.1:5432/nonexistent"):
            pass
    elapsed = time.monotonic() - start
    assert elapsed < 10, f"connection attempt took {elapsed:.1f}s -- timeout is not being enforced"


@requires_postgres
def test_select_1_succeeds_with_valid_dsn():
    """With a real, reachable PostgreSQL server configured, a basic
    query round-trips successfully through the context manager."""
    with get_postgres_connection(POSTGRES_TEST_DSN) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 AS result")
            row = cursor.fetchone()
    assert row["result"] == 1


@requires_postgres
def test_connection_is_usable_across_multiple_statements():
    """Confirms the yielded connection supports normal multi-statement
    usage and commits cleanly on context-manager exit."""
    with get_postgres_connection(POSTGRES_TEST_DSN) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 + 1 AS result")
            first = cursor.fetchone()
            cursor.execute("SELECT 2 + 2 AS result")
            second = cursor.fetchone()
    assert first["result"] == 2
    assert second["result"] == 4
