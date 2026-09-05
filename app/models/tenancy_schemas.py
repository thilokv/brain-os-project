"""Pydantic schemas for the multi-tenancy foundation -- Phase 2B.

Deliberately a separate module from app/models/schemas.py, which keeps
backing /brain-os/* unmodified. "Organization" here is the same entity
the architecture calls "Client" in business/domain language -- see
PHASE2_COMMERCIAL_ARCHITECTURE.md §1.1.

Only Organization schemas exist in this file for Phase 2B.1. User and
OrganizationMembership schemas are a later 2B milestone, not this one.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

IndustryType = Literal["ecommerce", "manufacturing", "retail_distribution"]
OrganizationStatus = Literal["trial", "active", "suspended", "cancelled"]


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
