"""PostgreSQL connection management for Brain OS -- Phase 2A foundation only.

This module is additive infrastructure: nothing in the application wires
it up yet. `/brain-os/*`, the original five tables, and
`app/database/connection.py`'s SQLite path are completely unaffected by
its presence -- see PHASE2_COMMERCIAL_ARCHITECTURE.md §11/§14 ("the
original five tables ... are kept permanently, running in parallel").

Mirrors the shape of `get_connection()` in `app/database/connection.py`
(short-lived connection per call, row access by column name, commit on
success) so the eventual Postgres-backed repository layer reads the same
way the SQLite one does.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg2
import psycopg2.extras

# Prevents an unreachable/firewalled host from hanging the caller
# indefinitely -- a connection attempt fails within this many seconds
# instead of blocking forever.
_CONNECT_TIMEOUT_SECONDS = 5


class PostgresConnectionError(RuntimeError):
    """Raised when a PostgreSQL connection cannot be established.

    Wraps the underlying psycopg2 exception with a clearer message so
    callers get an unambiguous, specific failure rather than a bare
    driver traceback -- covers unreachable hosts, refused connections,
    authentication failures, and invalid DSNs alike.
    """


@contextmanager
def get_postgres_connection(dsn: str) -> Iterator["psycopg2.extensions.connection"]:
    """Yield a short-lived PostgreSQL connection with dict-style row access.

    A fresh connection per call, matching the SQLite `get_connection()`
    pattern -- safe to use from FastAPI's threadpool-executed sync request
    handlers without sharing a single connection object across threads.

    Raises `PostgresConnectionError` immediately (within
    `_CONNECT_TIMEOUT_SECONDS`) if the DSN is invalid or the server is
    unreachable, rather than hanging or raising an opaque driver error.
    """
    try:
        conn = psycopg2.connect(
            dsn,
            connect_timeout=_CONNECT_TIMEOUT_SECONDS,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    except psycopg2.OperationalError as exc:
        raise PostgresConnectionError(f"Could not connect to PostgreSQL: {exc}") from exc
    except psycopg2.ProgrammingError as exc:
        raise PostgresConnectionError(f"Invalid PostgreSQL DSN: {exc}") from exc

    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
