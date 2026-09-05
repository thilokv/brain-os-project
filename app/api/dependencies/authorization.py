"""Role/permission enforcement for the future commercial API surface -- Phase 2B.3.

This is authorization logic only: given "this caller has membership M
in this org", decide whether M's role is allowed to proceed. It is
deliberately NOT wired to any real, reachable route yet, and does not
touch /brain-os/*, the dashboard, or SQLite in any way.

Why identity resolution is a placeholder here, not a real
implementation: authentication (verifying who is actually making a
request -- a session cookie, a JWT) is an explicitly separate, later
milestone. `get_current_membership()` below intentionally raises
`NotImplementedError` if ever actually invoked, rather than trusting
any client-supplied header/parameter as if it were verified identity --
that would be a real security shortcut dressed up as a stand-in, not a
safe placeholder. Tests exercise `require_role()`'s real logic by
substituting a controlled membership via FastAPI's
`app.dependency_overrides[get_current_membership] = ...` mechanism, so
the authorization logic itself is fully and honestly tested without
needing (or faking) authentication. When the authentication milestone
lands, it only needs to replace `get_current_membership` with a real
implementation that derives org_id/user_id from a verified session and
looks up the membership (via app.database.postgres.tenancy.get_membership)
-- require_role() itself does not change.

Status code discipline, locked in PHASE2_COMMERCIAL_ARCHITECTURE.md §14:
role/permission failures are always 403. Plan/usage entitlement failures
(a separate, later concern -- Phase 2C) are 402. Nothing in this module
ever raises 402.
"""

from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, HTTPException, status

from app.models.tenancy_schemas import MembershipOut, MembershipRole

_ACTIVE_MEMBERSHIP_STATUS = "active"


def get_current_membership() -> Optional[MembershipOut]:
    """Placeholder identity/membership resolver.

    Returns Optional, not MembershipOut, because "the caller has no
    membership in this org at all" is a real, expected outcome (an
    authenticated user with zero access to a given org) -- not an
    error condition to special-case away.

    Not implemented until the authentication milestone. Real routes
    must not depend on `require_role()` (and therefore not on this
    function) until that milestone replaces this with one that derives
    org_id/user_id from a verified session -- never from client-supplied,
    spoofable input -- and looks up the membership via
    app.database.postgres.tenancy.get_membership (returning None exactly
    when that lookup returns None).

    Tests override this via `app.dependency_overrides`; they never call
    it directly, and never rely on it actually resolving anything here.
    """
    raise NotImplementedError(
        "get_current_membership is not implemented until the authentication milestone. "
        "Do not depend on require_role() from any real route until then."
    )


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def require_role(*allowed_roles: MembershipRole) -> Callable[..., MembershipOut]:
    """Dependency factory: returns a FastAPI dependency that allows a
    request through only if the caller has an active membership whose
    role is one of `allowed_roles`.

    Usage (once wired to a real route, in a later milestone):
        @router.post(..., dependencies=[Depends(require_role("owner", "admin"))])

    Fails closed on every non-matching case -- no membership at all,
    membership present but not active (invited/disabled), or membership
    active but the wrong role -- with an identical 403 (never 402, see
    module docstring), so a caller cannot use the error to distinguish
    "you have no access" from "you have the wrong role" and enumerate
    valid org/role combinations.
    """
    if not allowed_roles:
        raise ValueError("require_role() needs at least one allowed role")

    def _check(membership: Optional[MembershipOut] = Depends(get_current_membership)) -> MembershipOut:
        if membership is None:
            raise _forbidden("You do not have permission to perform this action.")
        if membership.status != _ACTIVE_MEMBERSHIP_STATUS:
            raise _forbidden("You do not have permission to perform this action.")
        if membership.role not in allowed_roles:
            raise _forbidden("You do not have permission to perform this action.")
        return membership

    return _check
