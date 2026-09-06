"""Tests for Phase 2A.2 -- PostgreSQL migration foundation (Alembic).

Never touches /brain-os/*, the original five SQLite tables, or
app/database/connection.py's SQLite schema -- Alembic only ever operates
against `postgres_dsn`, a completely separate database engine.

Config-loading checks need no database and always run. Upgrade/downgrade
checks need a real PostgreSQL server and are skipped cleanly (not
failed) when POSTGRES_TEST_DSN is unset, matching the pattern already
established in tests/postgres/test_connection.py.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.utils.config import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI_PATH = REPO_ROOT / "alembic.ini"
BOOTSTRAP_REVISION = "b95ff6be48e7"
ORGANIZATIONS_REVISION = "fbc84c7b682e"  # added in Phase 2B.1, chained after BOOTSTRAP_REVISION
USERS_AND_MEMBERSHIPS_REVISION = "6d389c38a0c8"  # added in Phase 2B.2, chained after ORGANIZATIONS_REVISION
PASSWORD_CREDENTIALS_REVISION = "01401ec64495"  # added in Phase 2B.4, chained after USERS_AND_MEMBERSHIPS_REVISION

# Every migration added so far, in chain order. This list is the only
# thing that needs a new line when a future milestone adds a migration
# -- unlike a hardcoded "the current head is X" assertion, which broke
# twice in a row (2B.1 then 2B.2) for the same structural reason. The
# tests below check chain *health* (linear, no branches, every expected
# revision present and correctly ordered), not which specific revision
# happens to be the head today.
ALL_REVISIONS_IN_ORDER = [
    BOOTSTRAP_REVISION,
    ORGANIZATIONS_REVISION,
    USERS_AND_MEMBERSHIPS_REVISION,
    PASSWORD_CREDENTIALS_REVISION,
]

POSTGRES_TEST_DSN = os.environ.get("POSTGRES_TEST_DSN", "")

requires_postgres = pytest.mark.skipif(
    not POSTGRES_TEST_DSN,
    reason="POSTGRES_TEST_DSN not set -- no PostgreSQL test server configured for this environment.",
)


def _alembic_config() -> Config:
    """Builds an Alembic Config pointing at the repo's real alembic.ini,
    independent of the pytest invocation's current working directory."""
    return Config(str(ALEMBIC_INI_PATH))


def test_alembic_ini_exists_at_repo_root():
    assert ALEMBIC_INI_PATH.is_file()


def test_alembic_configuration_loads():
    """Config parses and the script directory resolves -- no database
    connection required for this."""
    cfg = _alembic_config()
    script_dir = ScriptDirectory.from_config(cfg)
    assert Path(script_dir.dir).resolve() == (REPO_ROOT / "alembic").resolve()


def test_migration_chain_has_a_single_linear_head():
    """No accidental branching -- exactly one head, regardless of how
    many migrations have been added. This assertion never needs to
    change as new milestones add migrations (unlike asserting which
    specific revision is currently the head, which broke twice in a
    row for that exact reason)."""
    cfg = _alembic_config()
    script_dir = ScriptDirectory.from_config(cfg)
    assert len(script_dir.get_heads()) == 1


def test_all_expected_revisions_are_present_and_correctly_chained():
    """Confirms every migration added so far exists and each one's
    down_revision correctly points to its predecessor -- bootstrap ->
    organizations -> users_and_memberships, in that order."""
    cfg = _alembic_config()
    script_dir = ScriptDirectory.from_config(cfg)

    revisions = [script_dir.get_revision(rev_id) for rev_id in ALL_REVISIONS_IN_ORDER]
    assert all(rev is not None for rev in revisions), "one or more expected revisions is missing from the chain"

    assert revisions[0].down_revision is None, "the first migration should have no parent"
    for parent, child in zip(revisions, revisions[1:]):
        assert child.down_revision == parent.revision, (
            f"{child.revision} should be chained directly after {parent.revision}"
        )

    assert script_dir.get_heads() == [ALL_REVISIONS_IN_ORDER[-1]], (
        "the last entry in ALL_REVISIONS_IN_ORDER should be the current head -- "
        "update this list when a new migration is added"
    )


def test_running_a_db_command_without_postgres_dsn_fails_clearly(monkeypatch):
    """Exercises the real alembic/env.py code path (via Alembic's own
    command API, not a reimplemented check) and confirms it fails fast
    with an actionable message rather than hanging or raising an opaque
    driver error when postgres_dsn is unset."""
    from alembic import command

    monkeypatch.setenv("POSTGRES_DSN", "")
    get_settings.cache_clear()
    cfg = _alembic_config()
    try:
        with pytest.raises(RuntimeError, match="postgres_dsn is not configured"):
            command.current(cfg)
    finally:
        get_settings.cache_clear()


@requires_postgres
def test_upgrade_and_downgrade_round_trip(monkeypatch):
    """The full pipeline: config -> connect via postgres_dsn -> upgrade
    creates the bootstrap table -> downgrade removes it -> the database
    ends up in exactly the state it started in."""
    from app.database.postgres_connection import get_postgres_connection

    monkeypatch.setenv("POSTGRES_DSN", POSTGRES_TEST_DSN)
    get_settings.cache_clear()
    cfg = _alembic_config()

    def _table_exists() -> bool:
        with get_postgres_connection(POSTGRES_TEST_DSN) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = '_migration_foundation_check')"
                )
                return bool(cursor.fetchone()["exists"])

    from alembic import command

    # Best-effort cleanup in case a previous failed run left state behind.
    try:
        command.downgrade(cfg, "base")
    except Exception:
        pass

    try:
        assert not _table_exists(), "bootstrap table already present before upgrade -- test environment not clean"

        command.upgrade(cfg, "head")
        assert _table_exists(), "upgrade did not create the bootstrap table"

        command.downgrade(cfg, "base")
        assert not _table_exists(), "downgrade did not remove the bootstrap table"
    finally:
        get_settings.cache_clear()


@requires_postgres
def test_downgrade_is_idempotent_safe_at_base(monkeypatch):
    """Downgrading when already at base is a documented no-op, not an
    error -- confirms the rollback path is safe to run defensively."""
    monkeypatch.setenv("POSTGRES_DSN", POSTGRES_TEST_DSN)
    get_settings.cache_clear()
    cfg = _alembic_config()

    from alembic import command

    try:
        command.downgrade(cfg, "base")  # ensure starting state
        command.downgrade(cfg, "base")  # calling again must not raise
    finally:
        get_settings.cache_clear()
