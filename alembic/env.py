"""Alembic migration environment for Brain OS -- Phase 2A.2.

Deliberately does NOT wire up SQLAlchemy ORM metadata/autogenerate
(`target_metadata` stays `None`): per the locked Phase 2 architecture
decision, migrations are hand-written using Alembic's `op.execute()`
with raw SQL, mirroring the style already used in
`app/database/connection.py`'s SCHEMA string. Alembic depends on
SQLAlchemy internally for its `op.*` directives and connection handling,
but the application itself never adopts the ORM.

The PostgreSQL connection string comes from the same `Settings.postgres_dsn`
introduced in Phase 2A.1 -- not a second, separately configured value in
alembic.ini -- so there is exactly one place this is set.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No ORM models, no autogenerate support -- migrations are hand-written.
target_metadata = None


def _resolve_postgres_dsn() -> str:
    """Reads postgres_dsn from the app's existing Settings object rather
    than a static alembic.ini value, so Phase 2A.1's configuration is the
    single source of truth for PostgreSQL connection info."""
    # Imported lazily so `alembic` command-line usage (e.g. `alembic
    # history`, which never touches the DB) doesn't require the full app
    # package to be importable in every invocation context.
    from app.utils.config import get_settings

    dsn = get_settings().postgres_dsn
    if not dsn:
        raise RuntimeError(
            "postgres_dsn is not configured. Set POSTGRES_DSN (or postgres_dsn "
            "in .env) before running Alembic migrations -- see "
            "PHASE2_COMMERCIAL_ARCHITECTURE.md §14 and app/utils/config.py. "
            "This does not affect /brain-os/* or the SQLite MVP path, which "
            "never use Alembic."
        )
    return dsn


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL, don't connect).

    Still requires postgres_dsn to be set, since the emitted SQL is
    dialect-specific (Alembic needs to know it's targeting PostgreSQL).
    """
    url = _resolve_postgres_dsn()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a real PostgreSQL connection."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _resolve_postgres_dsn()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
