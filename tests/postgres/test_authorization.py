"""Tests for Phase 2B.3 -- role/permission enforcement.

None of these tests need a real PostgreSQL server: require_role() is
pure authorization logic operating on an already-resolved MembershipOut
object, not a database query. Identity resolution
(get_current_membership) is substituted via FastAPI's
app.dependency_overrides, exactly as a real caller of this module is
expected to test it -- see the module docstring in
app/api/dependencies/authorization.py for why get_current_membership
itself is a NotImplementedError placeholder until the authentication
milestone.

A tiny throwaway FastAPI app is built inside this file to exercise
require_role() through real HTTP request/response handling (status
codes, dependency resolution order) -- it is not app.main.app, is never
mounted anywhere, and does not touch /brain-os/*, the dashboard, or
SQLite in any way.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.authorization import get_current_membership, require_role
from app.models.tenancy_schemas import MembershipOut

ALL_ROLES = ("owner", "admin", "finance", "ops_manager", "analyst", "viewer")


def _membership(role: str, status: str = "active") -> MembershipOut:
    return MembershipOut(
        id="mem-test",
        org_id="org-test",
        user_id="user-test",
        role=role,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def _build_test_app() -> FastAPI:
    """A minimal, throwaway app -- not app.main.app -- with one route
    gated by require_role(), for exercising real FastAPI dependency
    resolution and status codes."""
    app = FastAPI()

    @app.get("/admin-only", dependencies=[Depends(require_role("owner", "admin"))])
    def admin_only() -> dict:
        return {"ok": True}

    @app.get("/finance-only", dependencies=[Depends(require_role("finance"))])
    def finance_only() -> dict:
        return {"ok": True}

    return app


@pytest.fixture
def client():
    app = _build_test_app()
    with TestClient(app) as test_client:
        yield app, test_client


# ---------------------------------------------------------------------------
# require_role() called directly -- pure logic, no HTTP involved.
# ---------------------------------------------------------------------------


def test_require_role_rejects_calling_with_zero_allowed_roles():
    with pytest.raises(ValueError):
        require_role()


def test_require_role_returns_a_callable_dependency():
    dep = require_role("owner")
    assert callable(dep)


# ---------------------------------------------------------------------------
# require_role() exercised through real HTTP requests, with identity
# substituted via app.dependency_overrides (never via a real
# get_current_membership implementation, which doesn't exist yet).
# ---------------------------------------------------------------------------


def test_allowed_role_reaches_the_handler(client):
    app, test_client = client
    app.dependency_overrides[get_current_membership] = lambda: _membership("admin")

    response = test_client.get("/admin-only")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_disallowed_role_is_rejected_with_403(client):
    app, test_client = client
    app.dependency_overrides[get_current_membership] = lambda: _membership("viewer")

    response = test_client.get("/admin-only")
    assert response.status_code == 403


def test_no_membership_at_all_is_rejected_with_403(client):
    """The caller is "authenticated" (in the future sense) but has zero
    access to this org -- a real, expected outcome, not an error."""
    app, test_client = client
    app.dependency_overrides[get_current_membership] = lambda: None

    response = test_client.get("/admin-only")
    assert response.status_code == 403


def test_invited_but_not_active_membership_is_rejected_even_with_correct_role(client):
    """An allowed role does not bypass the membership's own status --
    an invited-but-not-yet-accepted membership grants no access."""
    app, test_client = client
    app.dependency_overrides[get_current_membership] = lambda: _membership("admin", status="invited")

    response = test_client.get("/admin-only")
    assert response.status_code == 403


def test_disabled_membership_is_rejected_even_with_correct_role(client):
    app, test_client = client
    app.dependency_overrides[get_current_membership] = lambda: _membership("owner", status="disabled")

    response = test_client.get("/admin-only")
    assert response.status_code == 403


def test_403_is_used_never_402(client):
    """Locked distinction (PHASE2_COMMERCIAL_ARCHITECTURE.md §14): role/
    permission failures are 403; plan/usage entitlement failures are a
    separate, later (Phase 2C) concern and use 402. Nothing here ever
    produces a 402."""
    app, test_client = client
    app.dependency_overrides[get_current_membership] = lambda: _membership("viewer")

    response = test_client.get("/admin-only")
    assert response.status_code == 403
    assert response.status_code != 402


def test_error_response_does_not_distinguish_failure_reason():
    """No-membership, wrong-role, and inactive-membership all produce
    the identical detail message, so a caller cannot use response
    content to enumerate valid org/role combinations."""
    app = _build_test_app()
    with TestClient(app) as test_client:
        cases = [None, _membership("viewer"), _membership("admin", status="disabled")]
        details = set()
        for case in cases:
            app.dependency_overrides[get_current_membership] = (lambda c=case: c)
            response = test_client.get("/admin-only")
            assert response.status_code == 403
            details.add(response.json()["detail"])
        assert len(details) == 1, f"expected one uniform 403 message, got: {details}"


@pytest.mark.parametrize("role", ALL_ROLES)
def test_each_of_the_six_locked_roles_is_individually_addressable(role, client):
    """require_role() can gate on any single role from the locked
    six-role enum, not just a hardcoded subset."""
    app, test_client = client

    # /finance-only only allows "finance" -- every other role is denied,
    # "finance" itself is allowed. Exercises the full locked role set.
    app.dependency_overrides[get_current_membership] = lambda: _membership(role)
    response = test_client.get("/finance-only")
    if role == "finance":
        assert response.status_code == 200
    else:
        assert response.status_code == 403


def test_multiple_allowed_roles_all_pass(client):
    """/admin-only allows both "owner" and "admin" -- confirms
    require_role() accepts more than one role, not just exactly one."""
    app, test_client = client

    for role in ("owner", "admin"):
        app.dependency_overrides[get_current_membership] = lambda r=role: _membership(r)
        response = test_client.get("/admin-only")
        assert response.status_code == 200, f"role {role!r} should have been allowed"


def test_get_current_membership_requires_org_id_and_a_verified_user():
    """Phase 2B.4 replaced the placeholder with a real resolver that
    needs org_id (a request parameter) and a verified user (from
    get_current_user, itself derived from a signed JWT) -- calling it
    with neither fails immediately with a TypeError, not a silent
    fallback to trusting some other, spoofable source of identity. Full
    real-resolution behavior (correct org, cross-tenant, inactive
    membership, etc.) is covered in tests/postgres/test_authentication.py."""
    with pytest.raises(TypeError):
        get_current_membership()
