"""Pydantic schemas for the multi-tenancy foundation -- Phase 2B.

Deliberately a separate module from app/models/schemas.py, which keeps
backing /brain-os/* unmodified. "Organization" here is the same entity
the architecture calls "Client" in business/domain language -- see
PHASE2_COMMERCIAL_ARCHITECTURE.md §1.1.

Phase 2B.1 added Organization schemas. Phase 2B.2 adds User and
OrganizationMembership schemas -- a user is a global identity (one
account, one row); org_id + role live on the membership, not the user,
so one person can belong to more than one organization. See the schema
note in PHASE2_COMMERCIAL_ARCHITECTURE.md §2 for why.

Role/authorization *enforcement* (require_role(), §9.3/§14) is a later
milestone -- MembershipRole here only validates the value is one of the
six locked roles, it doesn't yet gate anything.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

IndustryType = Literal["ecommerce", "manufacturing", "retail_distribution"]
OrganizationStatus = Literal["trial", "active", "suspended", "cancelled"]
UserStatus = Literal["active", "disabled"]
MembershipRole = Literal["owner", "admin", "finance", "ops_manager", "analyst", "viewer"]
MembershipStatus = Literal["invited", "active", "disabled"]


class OrganizationCreateRequest(BaseModel):
    """Input for creating a new organization (tenant/client)."""

    name: str = Field(..., min_length=1, max_length=200)
    industry_type: IndustryType
    financial_visibility_restricted: bool = True


class OrganizationOut(BaseModel):
    """An organization as persisted and returned by the repository."""

    id: str
    name: str
    industry_type: IndustryType
    status: OrganizationStatus
    financial_visibility_restricted: bool
    created_at: datetime


class UserCreateRequest(BaseModel):
    """Input for creating a new user (global identity, not org-scoped).

    email is plain str, not Pydantic's EmailStr: the latter requires the
    email-validator package, an extra dependency not otherwise needed by
    this project (same "minimal unnecessary dependency" reasoning already
    applied to psycopg2-over-asyncpg and Alembic-without-ORM). Format
    validation can be added later without disruption if a real signup
    flow needs it; uniqueness is enforced at the database level (users.email
    UNIQUE) regardless.
    """

    email: str = Field(..., min_length=1, max_length=320)
    display_name: str = Field(..., min_length=1, max_length=200)


class UserOut(BaseModel):
    """A user as persisted and returned by the repository."""

    id: str
    email: str
    display_name: str
    status: UserStatus
    last_login_at: Optional[datetime] = None
    created_at: datetime


class MembershipCreateRequest(BaseModel):
    """Input for granting a user a role within an organization."""

    org_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    role: MembershipRole


class MembershipOut(BaseModel):
    """An organization membership as persisted and returned by the repository."""

    id: str
    org_id: str
    user_id: str
    role: MembershipRole
    status: MembershipStatus
    created_at: datetime
