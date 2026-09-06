"""Authentication primitives for the commercial API surface -- Phase 2B.4.

Two independent concerns live here because both are pure cryptographic
operations with no database access:
- password hashing (bcrypt) -- verifying a user knows their password
- access tokens (JWT, HS256) -- proving, on every subsequent request,
  that a specific user_id was already authenticated, without needing
  to re-check a password on every call

This module never touches the database and an access token never
carries an org_id or role -- a token proves *identity* only ("this is
user X"). *Authorization* (does user X have a role in a specific org
right now) is resolved fresh from PostgreSQL on every request by
app/api/dependencies/authorization.py's get_current_membership(), not
baked into the token -- so a role change or membership removal takes
effect immediately, without waiting for a token to expire.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.utils.config import Settings

_JWT_ALGORITHM = "HS256"
# bcrypt's own hard limit on input length; longer passwords are rejected
# outright rather than silently truncated (a well-known bcrypt gotcha).
_BCRYPT_MAX_PASSWORD_BYTES = 72


class TokenError(Exception):
    """Raised for any invalid access token -- missing, malformed, expired,
    wrong signature, or wrong algorithm. Deliberately a single exception
    type: callers (see app/api/dependencies/auth.py) must respond
    identically to every failure mode with a generic 401, never a message
    that would help an attacker distinguish "expired" from "forged" from
    "malformed"."""


def hash_password(password: str) -> str:
    """Hashes a plaintext password with bcrypt (a fresh random salt per
    call). Never store, log, or return the plaintext password itself --
    only the return value of this function."""
    if len(password.encode("utf-8")) > _BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(f"password must be at most {_BCRYPT_MAX_PASSWORD_BYTES} bytes")
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Checks a plaintext password against a stored bcrypt hash
    (bcrypt.checkpw itself runs in constant time). Returns False, never
    raises, for a malformed/corrupt stored hash -- a broken hash must
    fail closed like a wrong password, not surface as a 500."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, settings: Settings) -> str:
    """Issues a signed JWT proving `user_id` was authenticated just now.
    Encodes only user_id (`sub`) plus standard timing claims -- never a
    role or org_id, which can change after issuance (see module
    docstring).

    Fails closed: refuses to issue a token if jwt_secret_key is unset,
    the same "empty means reject, never means disabled" discipline
    app/api/security.py already applies to brain_os_api_token.
    """
    if not settings.jwt_secret_key:
        raise TokenError("jwt_secret_key is not configured -- cannot issue access tokens.")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiry_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> str:
    """Verifies a JWT's signature and expiry and returns the user_id it
    was issued for. Raises TokenError -- never a bare jwt.* exception --
    for every failure mode (expired, tampered, wrong secret, malformed,
    wrong algorithm, missing `sub` claim), so callers have exactly one
    exception type to handle and never see library-specific details."""
    if not settings.jwt_secret_key:
        raise TokenError("jwt_secret_key is not configured -- cannot verify access tokens.")
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError("invalid access token") from exc
    user_id = payload.get("sub")
    if not user_id:
        raise TokenError("invalid access token")
    return user_id
