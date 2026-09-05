"""Repository functions for the multi-tenancy foundation -- Phase 2B.

Mirrors the discipline of app/database/repository.py (the SQLite
repository backing /brain-os/*): one function per operation, explicit
parameterized SQL, no ORM. The only difference is the connection source
-- app/database/postgres_connection.get_postgres_connection() instead
of SQLite's get_connection().

Phase 2B.1 added organization functions. Phase 2B.2 adds user and
membership functions. Role/permission *enforcement* and authentication
are explicitly later milestones -- get_membership() below only resolves
"what role does this user have in this org, if any", it does not gate
anything by itself.
"""

from __future__ import annotations

import uuid
from typing import Optional

from app.database.postgres_connection import get_postgres_connection
from app.models.tenancy_schemas import (
    IndustryType,
    MembershipOut,
    MembershipRole,
    OrganizationOut,
    UserOut,
)


def _generate_organization_id() -> str:
    """Server-generated identifier -- never client-supplied. Matches the
    existing workflow_id convention (f"wf-{uuid...}") in app/workflows/graph.py."""
    return f"org-{uuid.uuid4().hex[:12]}"


def _generate_user_id() -> str:
    return f"user-{uuid.uuid4().hex[:12]}"


def _generate_membership_id() -> str:
    return f"mem-{uuid.uuid4().hex[:12]}"


def create_organization(
    postgres_dsn: str,
    name: str,
    industry_type: IndustryType,
    financial_visibility_restricted: bool = True,
) -> OrganizationOut:
    """Creates a new organization (tenant/client) and returns it as persisted."""
    org_id = _generate_organization_id()
    with get_postgres_connection(postgres_dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO organizations (id, name, industry_type, financial_visibility_restricted)
                VALUES (%s, %s, %s, %s)
                RETURNING id, name, industry_type, status, financial_visibility_restricted, created_at
                """,
                (org_id, name, industry_type, financial_visibility_restricted),
            )
            row = cursor.fetchone()
    return OrganizationOut(**dict(row))


def get_organization(postgres_dsn: str, org_id: str) -> Optional[OrganizationOut]:
    """Fetches an organization by id, or None if it doesn't exist."""
    with get_postgres_connection(postgres_dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, industry_type, status, financial_visibility_restricted, created_at
                FROM organizations
                WHERE id = %s
                """,
                (org_id,),
            )
            row = cursor.fetchone()
    return OrganizationOut(**dict(row)) if row else None


# ---------------------------------------------------------------------------
# Users -- global identities, not org-scoped (see the schema note in
# alembic/versions/6d389c38a0c8_*.py and PHASE2_COMMERCIAL_ARCHITECTURE.md §2).
# ---------------------------------------------------------------------------


def create_user(postgres_dsn: str, email: str, display_name: str) -> UserOut:
    """Creates a new user (global identity) and returns it as persisted.

    Raises psycopg2.errors.UniqueViolation if the email is already in use
    -- callers should catch this to return a clean "email already
    registered" error once a real signup flow exists (a later milestone).
    """
    user_id = _generate_user_id()
    with get_postgres_connection(postgres_dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (id, email, display_name)
                VALUES (%s, %s, %s)
                RETURNING id, email, display_name, status, last_login_at, created_at
                """,
                (user_id, email, display_name),
            )
            row = cursor.fetchone()
    return UserOut(**dict(row))


def get_user(postgres_dsn: str, user_id: str) -> Optional[UserOut]:
    """Fetches a user by id, or None if it doesn't exist."""
    with get_postgres_connection(postgres_dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, email, display_name, status, last_login_at, created_at
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
    return UserOut(**dict(row)) if row else None


def get_user_by_email(postgres_dsn: str, email: str) -> Optional[UserOut]:
    """Fetches a user by email, or None if no account uses it. The natural
    lookup a future login/invite flow needs; email is globally unique."""
    with get_postgres_connection(postgres_dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, email, display_name, status, last_login_at, created_at
                FROM users
                WHERE email = %s
                """,
                (email,),
            )
            row = cursor.fetchone()
    return UserOut(**dict(row)) if row else None


# ---------------------------------------------------------------------------
# Organization memberships -- the org<->user<->role linkage. This is the
# table any future tenant-isolation/authorization dependency resolves
# access from; it does not itself enforce anything (that's a later
# milestone -- see the module docstring).
# ---------------------------------------------------------------------------


def create_membership(
    postgres_dsn: str, org_id: str, user_id: str, role: MembershipRole
) -> MembershipOut:
    """Grants a user a role within an organization.

    Raises psycopg2.errors.UniqueViolation if this user already has a
    membership in this org (one membership per org/user pair -- role
    changes are an update to the existing row, not a new one; no update
    function exists yet since nothing in this milestone needs it).
    Raises psycopg2.errors.ForeignKeyViolation if org_id or user_id
    doesn't reference a real row.
    """
    membership_id = _generate_membership_id()
    with get_postgres_connection(postgres_dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO organization_memberships (id, org_id, user_id, role)
                VALUES (%s, %s, %s, %s)
                RETURNING id, org_id, user_id, role, status, created_at
                """,
                (membership_id, org_id, user_id, role),
            )
            row = cursor.fetchone()
    return MembershipOut(**dict(row))


def get_membership(postgres_dsn: str, org_id: str, user_id: str) -> Optional[MembershipOut]:
    """Resolves whether/how a specific user relates to a specific org.

    Returns None if the user has no membership in that org -- this is
    the correct "no access" signal a future tenant-isolation/
    authorization dependency checks, not an error.
    """
    with get_postgres_connection(postgres_dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, org_id, user_id, role, status, created_at
                FROM organization_memberships
                WHERE org_id = %s AND user_id = %s
                """,
                (org_id, user_id),
            )
            row = cursor.fetchone()
    return MembershipOut(**dict(row)) if row else None


def list_memberships_for_user(postgres_dsn: str, user_id: str) -> list[MembershipOut]:
    """Lists every organization a user belongs to (and their role in each)."""
    with get_postgres_connection(postgres_dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, org_id, user_id, role, status, created_at
                FROM organization_memberships
                WHERE user_id = %s
                ORDER BY created_at ASC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
    return [MembershipOut(**dict(row)) for row in rows]


def list_memberships_for_org(postgres_dsn: str, org_id: str) -> list[MembershipOut]:
    """Lists every user who belongs to a specific organization.

    Scoped strictly by org_id -- the core query a tenant-isolation test
    exercises to confirm one org's membership list never includes a user
    whose only membership is in a different org.
    """
    with get_postgres_connection(postgres_dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, org_id, user_id, role, status, created_at
                FROM organization_memberships
                WHERE org_id = %s
                ORDER BY created_at ASC
                """,
                (org_id,),
            )
            rows = cursor.fetchall()
    return [MembershipOut(**dict(row)) for row in rows]
