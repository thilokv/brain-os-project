"""Tests for Phase 2B.1 -- Organization / Tenant foundation.

Never touches /brain-os/*, the original five SQLite tables, or any
existing route -- organizations is a new PostgreSQL-only table nothing
else depends on yet.

Pydantic-level validation tests need no database and always run.
Repository tests need a real PostgreSQL server with the Phase 2B.1
migration applied, and are skipped cleanly (not failed) when
POSTGRES_TEST_DSN is unset, matching the pattern established in
tests/postgres/test_connection.py and test_migrations.py.
"""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from app.models.tenancy_schemas import OrganizationCreateRequest, OrganizationOut

POSTGRES_TEST_DSN = os.environ.get("POSTGRES_TEST_DSN", "")

requires_postgres = pytest.mark.skipif(
    not POSTGRES_TEST_DSN,
    reason="POSTGRES_TEST_DSN not set -- no PostgreSQL test server configured for this environment.",
)


def test_organization_create_request_accepts_valid_industry_types():
    for industry in ("ecommerce", "manufacturing", "retail_distribution"):
        request = OrganizationCreateRequest(name="Acme Co", industry_type=industry)
        assert request.industry_type == industry
        assert request.financial_visibility_restricted is True  # default


def test_organization_create_request_rejects_invalid_industry_type():
    with pytest.raises(ValidationError):
        OrganizationCreateRequest(name="Acme Co", industry_type="hospitality")


def test_organization_create_request_rejects_blank_name():
    with pytest.raises(ValidationError):
        OrganizationCreateRequest(name="", industry_type="ecommerce")


def test_organization_out_rejects_invalid_status():
    with pytest.raises(ValidationError):
        OrganizationOut(
            id="org-test",
            name="Acme Co",
            industry_type="ecommerce",
            status="not_a_real_status",
            financial_visibility_restricted=True,
            created_at="2026-01-01T00:00:00Z",
        )


@requires_postgres
def test_create_and_get_organization_round_trip():
    from app.database.postgres.tenancy import create_organization, get_organization

    created = create_organization(
        POSTGRES_TEST_DSN,
        name="Test Org for 2B.1",
        industry_type="ecommerce",
    )
    assert created.id.startswith("org-")
    assert created.name == "Test Org for 2B.1"
    assert created.industry_type == "ecommerce"
    assert created.status == "active"  # DB default
    assert created.financial_visibility_restricted is True  # default

    fetched = get_organization(POSTGRES_TEST_DSN, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == created.name
    assert fetched.created_at is not None


@requires_postgres
def test_get_organization_returns_none_for_unknown_id():
    from app.database.postgres.tenancy import get_organization

    assert get_organization(POSTGRES_TEST_DSN, "org-does-not-exist") is None


@requires_postgres
def test_financial_visibility_restricted_can_be_disabled():
    from app.database.postgres.tenancy import create_organization

    org = create_organization(
        POSTGRES_TEST_DSN,
        name="Transparent Org",
        industry_type="manufacturing",
        financial_visibility_restricted=False,
    )
    assert org.financial_visibility_restricted is False


@requires_postgres
def test_database_rejects_invalid_industry_type_at_the_constraint_level():
    """Defense in depth: even if application validation were bypassed,
    the DB's CHECK constraint refuses an invalid industry_type."""
    import psycopg2

    from app.database.postgres_connection import get_postgres_connection

    with pytest.raises(psycopg2.errors.CheckViolation):
        with get_postgres_connection(POSTGRES_TEST_DSN) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO organizations (id, name, industry_type) VALUES (%s, %s, %s)",
                    ("org-invalid-test", "Bad Org", "hospitality"),
                )
