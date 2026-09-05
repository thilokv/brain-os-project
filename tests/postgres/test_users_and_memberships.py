"""Tests for Phase 2B.2 -- Users and Organization Memberships.

Never touches /brain-os/*, the original five SQLite tables, or any
existing route -- users and organization_memberships are new
PostgreSQL-only tables nothing else depends on yet.

Pydantic-level validation tests need no database and always run.
Repository tests need a real PostgreSQL server with the Phase 2B.1/2B.2
migrations applied, and are skipped cleanly (not failed) when
POSTGRES_TEST_DSN is unset, matching the pattern established in
tests/postgres/test_connection.py, test_migrations.py, and
test_tenancy_repository.py.

No role/permission enforcement or authentication is exercised here --
those are explicitly later milestones. Membership tests only confirm
data is stored, retrieved, and isolated correctly.
"""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from app.models.tenancy_schemas import (
    MembershipCreateRequest,
    MembershipOut,
    UserCreateRequest,
    UserOut,
)

POSTGRES_TEST_DSN = os.environ.get("POSTGRES_TEST_DSN", "")

requires_postgres = pytest.mark.skipif(
    not POSTGRES_TEST_DSN,
    reason="POSTGRES_TEST_DSN not set -- no PostgreSQL test server configured for this environment.",
)

ALL_ROLES = ("owner", "admin", "finance", "ops_manager", "analyst", "viewer")


# ---------------------------------------------------------------------------
# Pydantic-level validation -- no database required, always run.
# ---------------------------------------------------------------------------


def test_user_create_request_accepts_valid_input():
    request = UserCreateRequest(email="alice@example.com", display_name="Alice Chen")
    assert request.email == "alice@example.com"
    assert request.display_name == "Alice Chen"


def test_user_create_request_rejects_blank_display_name():
    with pytest.raises(ValidationError):
        UserCreateRequest(email="alice@example.com", display_name="")


def test_user_create_request_rejects_blank_email():
    with pytest.raises(ValidationError):
        UserCreateRequest(email="", display_name="Alice Chen")


def test_user_out_rejects_invalid_status():
    with pytest.raises(ValidationError):
        UserOut(
            id="user-test",
            email="alice@example.com",
            display_name="Alice Chen",
            status="not_a_real_status",
            created_at="2026-01-01T00:00:00Z",
        )


def test_membership_create_request_accepts_all_six_locked_roles():
    for role in ALL_ROLES:
        request = MembershipCreateRequest(org_id="org-1", user_id="user-1", role=role)
        assert request.role == role


def test_membership_create_request_rejects_invalid_role():
    with pytest.raises(ValidationError):
        MembershipCreateRequest(org_id="org-1", user_id="user-1", role="superadmin")


def test_membership_out_rejects_invalid_status():
    with pytest.raises(ValidationError):
        MembershipOut(
            id="mem-test",
            org_id="org-1",
            user_id="user-1",
            role="owner",
            status="not_a_real_status",
            created_at="2026-01-01T00:00:00Z",
        )


# ---------------------------------------------------------------------------
# Repository tests -- require a real PostgreSQL server.
# ---------------------------------------------------------------------------


@requires_postgres
def test_create_and_get_user_round_trip():
    from app.database.postgres.tenancy import create_user, get_user

    created = create_user(POSTGRES_TEST_DSN, email="bob.round-trip@example.com", display_name="Bob Webb")
    assert created.id.startswith("user-")
    assert created.email == "bob.round-trip@example.com"
    assert created.display_name == "Bob Webb"
    assert created.status == "active"  # DB default
    assert created.last_login_at is None

    fetched = get_user(POSTGRES_TEST_DSN, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.email == created.email


@requires_postgres
def test_get_user_by_email_finds_the_right_user():
    from app.database.postgres.tenancy import create_user, get_user_by_email

    created = create_user(POSTGRES_TEST_DSN, email="priya.lookup@example.com", display_name="Priya Nair")
    found = get_user_by_email(POSTGRES_TEST_DSN, "priya.lookup@example.com")
    assert found is not None
    assert found.id == created.id


@requires_postgres
def test_get_user_returns_none_for_unknown_id():
    from app.database.postgres.tenancy import get_user

    assert get_user(POSTGRES_TEST_DSN, "user-does-not-exist") is None


@requires_postgres
def test_get_user_by_email_returns_none_for_unknown_email():
    from app.database.postgres.tenancy import get_user_by_email

    assert get_user_by_email(POSTGRES_TEST_DSN, "nobody-registered@example.com") is None


@requires_postgres
def test_duplicate_email_is_rejected_at_the_database_level():
    """email is globally unique -- a real consequence of users being a
    global identity table, not org-scoped (see the schema note in
    alembic/versions/6d389c38a0c8_*.py)."""
    import psycopg2

    from app.database.postgres.tenancy import create_user

    create_user(POSTGRES_TEST_DSN, email="duplicate-test@example.com", display_name="First Account")
    with pytest.raises(psycopg2.errors.UniqueViolation):
        create_user(POSTGRES_TEST_DSN, email="duplicate-test@example.com", display_name="Second Account")


@requires_postgres
def test_create_and_get_membership_round_trip():
    from app.database.postgres.tenancy import create_membership, create_organization, create_user, get_membership

    org = create_organization(POSTGRES_TEST_DSN, name="Membership Round Trip Org", industry_type="ecommerce")
    user = create_user(POSTGRES_TEST_DSN, email="membership.roundtrip@example.com", display_name="Test User")

    created = create_membership(POSTGRES_TEST_DSN, org_id=org.id, user_id=user.id, role="ops_manager")
    assert created.id.startswith("mem-")
    assert created.org_id == org.id
    assert created.user_id == user.id
    assert created.role == "ops_manager"
    assert created.status == "active"  # DB default

    fetched = get_membership(POSTGRES_TEST_DSN, org.id, user.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.role == "ops_manager"


@requires_postgres
def test_get_membership_returns_none_when_no_membership_exists():
    """The correct "no access" signal -- not an error -- a future
    authorization dependency will check for exactly this."""
    from app.database.postgres.tenancy import create_organization, create_user, get_membership

    org = create_organization(POSTGRES_TEST_DSN, name="No Membership Org", industry_type="manufacturing")
    user = create_user(POSTGRES_TEST_DSN, email="no.membership@example.com", display_name="Outsider")

    assert get_membership(POSTGRES_TEST_DSN, org.id, user.id) is None


@requires_postgres
def test_membership_with_invalid_role_is_rejected_at_the_database_level():
    """Defense in depth: even if application validation were bypassed,
    the DB's CHECK constraint refuses an invalid role."""
    import psycopg2

    from app.database.postgres.tenancy import create_organization, create_user
    from app.database.postgres_connection import get_postgres_connection

    org = create_organization(POSTGRES_TEST_DSN, name="Bad Role Org", industry_type="ecommerce")
    user = create_user(POSTGRES_TEST_DSN, email="bad.role@example.com", display_name="Bad Role User")

    with pytest.raises(psycopg2.errors.CheckViolation):
        with get_postgres_connection(POSTGRES_TEST_DSN) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO organization_memberships (id, org_id, user_id, role) VALUES (%s, %s, %s, %s)",
                    ("mem-invalid-role", org.id, user.id, "superadmin"),
                )


@requires_postgres
def test_membership_with_nonexistent_org_is_rejected_by_foreign_key():
    import psycopg2

    from app.database.postgres.tenancy import create_membership, create_user

    user = create_user(POSTGRES_TEST_DSN, email="fk.org.test@example.com", display_name="FK Org Test")
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        create_membership(POSTGRES_TEST_DSN, org_id="org-does-not-exist", user_id=user.id, role="viewer")


@requires_postgres
def test_membership_with_nonexistent_user_is_rejected_by_foreign_key():
    import psycopg2

    from app.database.postgres.tenancy import create_membership, create_organization

    org = create_organization(POSTGRES_TEST_DSN, name="FK User Test Org", industry_type="retail_distribution")
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        create_membership(POSTGRES_TEST_DSN, org_id=org.id, user_id="user-does-not-exist", role="viewer")


@requires_postgres
def test_duplicate_membership_for_same_org_and_user_is_rejected():
    """One membership per (org, user) pair -- a role change is meant to
    be an update to the existing row (no update function exists yet
    since nothing in this milestone needs it), not a second insert."""
    import psycopg2

    from app.database.postgres.tenancy import create_membership, create_organization, create_user

    org = create_organization(POSTGRES_TEST_DSN, name="Duplicate Membership Org", industry_type="ecommerce")
    user = create_user(POSTGRES_TEST_DSN, email="duplicate.membership@example.com", display_name="Dup Test")

    create_membership(POSTGRES_TEST_DSN, org_id=org.id, user_id=user.id, role="analyst")
    with pytest.raises(psycopg2.errors.UniqueViolation):
        create_membership(POSTGRES_TEST_DSN, org_id=org.id, user_id=user.id, role="admin")


@requires_postgres
def test_a_user_can_hold_memberships_in_more_than_one_organization():
    """The entire point of the users/organization_memberships refinement
    (see PHASE2_COMMERCIAL_ARCHITECTURE.md §2 note): one global identity,
    potentially different roles in different orgs."""
    from app.database.postgres.tenancy import (
        create_membership,
        create_organization,
        create_user,
        list_memberships_for_user,
    )

    user = create_user(POSTGRES_TEST_DSN, email="multi.org@example.com", display_name="Multi Org User")
    org_a = create_organization(POSTGRES_TEST_DSN, name="Multi Org A", industry_type="ecommerce")
    org_b = create_organization(POSTGRES_TEST_DSN, name="Multi Org B", industry_type="manufacturing")

    create_membership(POSTGRES_TEST_DSN, org_id=org_a.id, user_id=user.id, role="owner")
    create_membership(POSTGRES_TEST_DSN, org_id=org_b.id, user_id=user.id, role="viewer")

    memberships = list_memberships_for_user(POSTGRES_TEST_DSN, user.id)
    by_org = {m.org_id: m.role for m in memberships}
    assert by_org[org_a.id] == "owner"
    assert by_org[org_b.id] == "viewer"


# ---------------------------------------------------------------------------
# Tenant isolation tests -- the core multi-tenancy guarantee.
# ---------------------------------------------------------------------------


@requires_postgres
def test_org_membership_list_never_includes_a_user_from_a_different_org():
    """The core tenant-isolation guarantee for this milestone: listing
    org A's members must never leak a user whose only membership is in
    org B, even though both users exist in the same global users table."""
    from app.database.postgres.tenancy import (
        create_membership,
        create_organization,
        create_user,
        list_memberships_for_org,
    )

    org_a = create_organization(POSTGRES_TEST_DSN, name="Isolation Org A", industry_type="ecommerce")
    org_b = create_organization(POSTGRES_TEST_DSN, name="Isolation Org B", industry_type="ecommerce")

    user_a = create_user(POSTGRES_TEST_DSN, email="isolation.a@example.com", display_name="Org A User")
    user_b = create_user(POSTGRES_TEST_DSN, email="isolation.b@example.com", display_name="Org B User")

    create_membership(POSTGRES_TEST_DSN, org_id=org_a.id, user_id=user_a.id, role="admin")
    create_membership(POSTGRES_TEST_DSN, org_id=org_b.id, user_id=user_b.id, role="admin")

    org_a_members = list_memberships_for_org(POSTGRES_TEST_DSN, org_a.id)
    org_a_user_ids = {m.user_id for m in org_a_members}

    assert user_a.id in org_a_user_ids
    assert user_b.id not in org_a_user_ids, "org A's membership list leaked a user belonging only to org B"


@requires_postgres
def test_get_membership_does_not_leak_across_organizations():
    """A user with a valid membership in org B must resolve to "no
    access" (None) when queried against org A -- cross-tenant lookups
    must not accidentally succeed."""
    from app.database.postgres.tenancy import create_membership, create_organization, create_user, get_membership

    org_a = create_organization(POSTGRES_TEST_DSN, name="Cross-Tenant Org A", industry_type="ecommerce")
    org_b = create_organization(POSTGRES_TEST_DSN, name="Cross-Tenant Org B", industry_type="ecommerce")
    user = create_user(POSTGRES_TEST_DSN, email="cross.tenant@example.com", display_name="Cross Tenant User")

    create_membership(POSTGRES_TEST_DSN, org_id=org_b.id, user_id=user.id, role="owner")

    assert get_membership(POSTGRES_TEST_DSN, org_b.id, user.id) is not None
    assert get_membership(POSTGRES_TEST_DSN, org_a.id, user.id) is None


@requires_postgres
def test_same_role_in_different_orgs_does_not_cross_contaminate():
    """Two unrelated orgs each having an 'owner' does not create any
    shared state between them -- each membership row is independently
    scoped by (org_id, user_id)."""
    from app.database.postgres.tenancy import create_membership, create_organization, create_user, get_membership

    org_a = create_organization(POSTGRES_TEST_DSN, name="Same Role Org A", industry_type="ecommerce")
    org_b = create_organization(POSTGRES_TEST_DSN, name="Same Role Org B", industry_type="retail_distribution")
    owner_a = create_user(POSTGRES_TEST_DSN, email="owner.a@example.com", display_name="Owner A")
    owner_b = create_user(POSTGRES_TEST_DSN, email="owner.b@example.com", display_name="Owner B")

    create_membership(POSTGRES_TEST_DSN, org_id=org_a.id, user_id=owner_a.id, role="owner")
    create_membership(POSTGRES_TEST_DSN, org_id=org_b.id, user_id=owner_b.id, role="owner")

    assert get_membership(POSTGRES_TEST_DSN, org_a.id, owner_b.id) is None
    assert get_membership(POSTGRES_TEST_DSN, org_b.id, owner_a.id) is None
    assert get_membership(POSTGRES_TEST_DSN, org_a.id, owner_a.id).role == "owner"
    assert get_membership(POSTGRES_TEST_DSN, org_b.id, owner_b.id).role == "owner"
