"""Role/permission enforcement for the future commercial API surface --
Phase 2B.3 (authorization logic) + Phase 2B.4 (real identity resolution).

This is authorization logic: given "this caller has membership M in
this org", decide whether M's role is allowed to proceed. Identity
itself -- who is actually making the request -- is resolved by
app.api.dependencies.auth.get_current_user from a signed JWT, never
from a client-supplied header; see that module for why a bearer token
is trustworthy (the signature) even though a header is not, by itself.

`get_current_membership()` takes `org_id` as a plain parameter -- this
is a REQUEST parameter (which org this request is about, e.g. from a
route path like `/orgs/{org_id}/...`), not a credential, and is never
trusted as proof the caller belongs to that org. The actual membership
is looked up fresh from PostgreSQL on every request, keyed by this
org_id and the verified user_id from get_current_user() -- a client can
put any org_id in a URL, but only ever gets a non-None membership back
for an org where a real membership row exists for their real, verified
identity. This function is still not wired to any real, reachable route
in this milestone: doing so requires that route to declare an `org_id`
path parameter for FastAPI to inject here, which is the next, later
milestone's concern -- require_role() itself needs no change either way.

Status code discipline, locked in PHASE2_COMMERCIAL_ARCHITECTURE.md §14:
role/permission failures are always 403. Plan/usage entitlement failures
(a separate, later concern -- Phase 2C) are 402. Nothing in this module
ever raises 402. Authentication failures (invalid/missing/expired
credentials -- we don't know who you are at all) are 401 and raised by
get_current_user, not here; by the time this module runs, identity is
already verified and the only remaining question is access.
"""

from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, HTTPException, status

from app.api.dependencies.auth import get_current_user
from app.database.postgres.tenancy import get_membership
from app.models.tenancy_schemas import MembershipOut, MembershipRole, UserOut
from app.utils.config import Settings, get_settings

_ACTIVE_MEMBERSHIP_STATUS = "active"


def get_current_membership(
    org_id: str,
    user: UserOut = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Optional[MembershipOut]:
    """Resolves the verified caller's membership in a specific org.

    Returns Optional, not MembershipOut, because "the caller has no
    membership in this org at all" is a real, expected outcome (an
    authenticated user with zero access to a given org) -- not an
    error condition to special-case away.

    `user` is only ever the identity get_current_user() resolved from a
    verified JWT (401 already raised there if that failed) -- never a
    client-supplied user_id. The membership itself is looked up by
    app.database.postgres.tenancy.get_membership, returning None exactly
    when that lookup returns None.

    Tests may still override this via `app.dependency_overrides` to
    substitute a controlled membership without needing a real database
    or a real JWT, exactly as Phase 2B.3's tests already do.
    """
    return get_membership(settings.postgres_dsn, org_id, user.id)


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
