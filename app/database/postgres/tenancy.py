"""Repository functions for the multi-tenancy foundation -- Phase 2B.1.

Mirrors the discipline of app/database/repository.py (the SQLite
repository backing /brain-os/*): one function per operation, explicit
parameterized SQL, no ORM. The only difference is the connection source
-- app/database/postgres_connection.get_postgres_connection() instead
of SQLite's get_connection().

Only organization functions exist here for Phase 2B.1. User and
membership functions are a later 2B milestone.
"""

from __future__ import annotations

import uuid
from typing import Optional

from app.database.postgres_connection import get_postgres_connection
from app.models.tenancy_schemas import IndustryType, OrganizationOut


def _generate_organization_id() -> str:
    """Server-generated identifier -- never client-supplied. Matches the
    existing workflow_id convention (f"wf-{uuid...}") in app/workflows/graph.py."""
    return f"org-{uuid.uuid4().hex[:12]}"


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
