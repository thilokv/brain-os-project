"""Authentication -- Phase 2B.4: who is actually making this request.

Deliberately a separate module from authorization.py: this file answers
"who is this" (identity), authorization.py answers "what can they do"
(role/permission given an org). Mirrors app/api/security.py's bearer-
token pattern for /brain-os/* -- a distinct HTTPBearer instance, a
generic fail-closed error, no distinction in the response between
failure reasons -- but is otherwise fully independent: this JWT
mechanism, its settings (jwt_secret_key/jwt_expiry_minutes), and the
PostgreSQL users table it resolves against have nothing to do with
BRAIN_OS_API_TOKEN or /brain-os/*.

The identity this module resolves comes from a server-issued, signed
JWT -- never from a client-supplied user_id/org_id/role header, which
would just be trusting the client's own unverified claim about itself.
A bearer token is still transmitted via a header, but what makes it
trustworthy is the cryptographic signature (only this server could have
produced it), not the transport.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.database.postgres.tenancy import _get_user_credentials, get_user, update_last_login
from app.models.tenancy_schemas import UserOut
from app.services.auth_service import TokenError, decode_access_token, hash_password, verify_password
from app.utils.config import Settings, get_settings

_ACTIVE_USER_STATUS = "active"

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Access token issued by the commercial API's login flow (Phase 2B.4).",
)

# A fixed, precomputed bcrypt hash that no real password will ever match --
# used only to normalize authentication response timing for a nonexistent
# email, so that timing alone can't reveal whether an account exists (see
# authenticate_user() below).
_NONEXISTENT_ACCOUNT_DUMMY_HASH = hash_password("this-is-never-a-real-users-password")


def _unauthenticated() -> HTTPException:
    # One generic message for every failure mode (missing header, malformed
    # token, expired, tampered, unknown/disabled user) -- the response
    # never hints at which case applies, so it can't be used to enumerate
    # valid user_ids or distinguish "expired" from "forged."
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def authenticate_user(postgres_dsn: str, email: str, password: str) -> Optional[UserOut]:
    """Verifies email+password against the PostgreSQL users table.

    Returns the authenticated user, or None uniformly for every failure
    reason -- no such email, wrong password, or a disabled account --
    so a caller can never distinguish "no such account" from "wrong
    password" from the result alone. An unknown email still runs a full
    bcrypt comparison (against a fixed dummy hash) before returning,
    so response timing does not itself reveal whether the email exists.

    Never logs or raises with the plaintext password or the stored hash.
    """
    row = _get_user_credentials(postgres_dsn, email)
    if row is None:
        verify_password(password, _NONEXISTENT_ACCOUNT_DUMMY_HASH)
        return None

    if not verify_password(password, row["password_hash"]):
        return None

    if row["status"] != _ACTIVE_USER_STATUS:
        return None

    update_last_login(postgres_dsn, row["id"])
    row = dict(row)
    row.pop("password_hash")
    return UserOut(**row)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    """FastAPI dependency resolving the authenticated caller's identity
    from a signed JWT's `sub` claim, then re-checking that user's current
    account status against PostgreSQL (not trusting anything cached in
    the token itself).

    Fails closed with 401 for every invalid case: missing Authorization
    header, malformed/tampered/expired token, wrong signature, or a
    token whose user_id no longer resolves to an active account (deleted
    or disabled after the token was issued).
    """
    if credentials is None:
        raise _unauthenticated()

    try:
        user_id = decode_access_token(credentials.credentials, settings)
    except TokenError:
        raise _unauthenticated()

    user = get_user(settings.postgres_dsn, user_id)
    if user is None or user.status != _ACTIVE_USER_STATUS:
        raise _unauthenticated()

    return user
