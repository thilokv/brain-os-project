"""Tests for Phase 2B.4 -- Authentication.

Covers three layers, from pure logic up to full HTTP integration:

1. app/services/auth_service.py -- password hashing and JWT issuance/
   verification. Pure cryptographic functions, no database, no
   PostgreSQL required.
2. app/api/dependencies/auth.py -- authenticate_user() (credential
   validation against a user record) and get_current_user() (JWT ->
   verified identity, 401 fail-closed). The database calls these make
   are monkeypatched for the always-run unit tests below (so this file
   works with no PostgreSQL server), plus a handful of @requires_postgres
   tests that exercise the real repository functions end-to-end.
3. app/api/dependencies/authorization.py's get_current_membership(),
   exercised together with the unmodified require_role() through a
   throwaway FastAPI app -- proving the full chain (JWT -> identity ->
   membership -> role check) works exactly as require_role() already
   expected in Phase 2B.3, with zero changes to require_role() itself.

Never touches /brain-os/*, the dashboard, or SQLite in any way.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import auth as auth_module
from app.api.dependencies import authorization as authorization_module
from app.api.dependencies.auth import authenticate_user, get_current_user
from app.api.dependencies.authorization import get_current_membership, require_role
from app.models.tenancy_schemas import MembershipOut, UserOut
from app.services.auth_service import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.utils.config import Settings

POSTGRES_TEST_DSN = os.environ.get("POSTGRES_TEST_DSN", "")

requires_postgres = pytest.mark.skipif(
    not POSTGRES_TEST_DSN,
    reason="POSTGRES_TEST_DSN not set -- no PostgreSQL test server configured for this environment.",
)


def _settings(**overrides) -> Settings:
    defaults = dict(jwt_secret_key="unit-test-secret-key-not-for-production", jwt_expiry_minutes=60)
    defaults.update(overrides)
    return Settings(**defaults)


def _user(user_id: str = "user-test", status: str = "active") -> UserOut:
    return UserOut(
        id=user_id,
        email="test@example.com",
        display_name="Test User",
        status=status,
        last_login_at=None,
        created_at=datetime.now(timezone.utc),
    )


def _membership(org_id: str, user_id: str, role: str, status: str = "active") -> MembershipOut:
    return MembershipOut(
        id="mem-test",
        org_id=org_id,
        user_id=user_id,
        role=role,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# app/services/auth_service.py -- password hashing. No database.
# ---------------------------------------------------------------------------


def test_hash_password_round_trips_with_verify_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_hash_password_produces_a_different_hash_each_time():
    """Each call uses a fresh random salt -- confirms two accounts with
    the same password never produce identical stored hashes."""
    first = hash_password("shared-password")
    second = hash_password("shared-password")
    assert first != second
    assert verify_password("shared-password", first) is True
    assert verify_password("shared-password", second) is True


def test_hash_password_rejects_passwords_over_the_bcrypt_limit():
    with pytest.raises(ValueError):
        hash_password("x" * 73)


def test_verify_password_returns_false_not_an_exception_for_a_corrupt_hash():
    """A malformed/corrupt stored hash must fail closed like a wrong
    password, never surface as an unhandled exception (a 500)."""
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False


# ---------------------------------------------------------------------------
# app/services/auth_service.py -- JWT issuance/verification. No database.
# ---------------------------------------------------------------------------


def test_create_and_decode_access_token_round_trip():
    settings = _settings()
    token = create_access_token("user-abc123", settings)
    assert decode_access_token(token, settings) == "user-abc123"


def test_decode_access_token_rejects_a_tampered_token():
    settings = _settings()
    token = create_access_token("user-abc123", settings)
    tampered = token[:-4] + ("A" if token[-4] != "A" else "B") + token[-3:]
    with pytest.raises(TokenError):
        decode_access_token(tampered, settings)


def test_decode_access_token_rejects_wrong_secret():
    token = create_access_token("user-abc123", _settings(jwt_secret_key="secret-one"))
    with pytest.raises(TokenError):
        decode_access_token(token, _settings(jwt_secret_key="secret-two"))


def test_decode_access_token_rejects_an_expired_token():
    expired_token = create_access_token("user-abc123", _settings(jwt_expiry_minutes=-1))
    with pytest.raises(TokenError):
        decode_access_token(expired_token, _settings())


def test_decode_access_token_rejects_garbage_input():
    with pytest.raises(TokenError):
        decode_access_token("not.a.jwt", _settings())


def test_create_access_token_fails_closed_when_secret_is_unset():
    with pytest.raises(TokenError):
        create_access_token("user-abc123", _settings(jwt_secret_key=""))


def test_decode_access_token_fails_closed_when_secret_is_unset():
    token = create_access_token("user-abc123", _settings())
    with pytest.raises(TokenError):
        decode_access_token(token, _settings(jwt_secret_key=""))


def test_access_token_never_carries_role_or_org_id():
    """A token proves identity only -- role/org membership is always
    re-checked fresh against PostgreSQL on every request (see
    get_current_membership), never trusted from something baked into
    the token at issuance time."""
    import jwt as pyjwt

    settings = _settings()
    token = create_access_token("user-abc123", settings)
    payload = pyjwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    assert set(payload.keys()) == {"sub", "iat", "exp"}


# ---------------------------------------------------------------------------
# app/api/dependencies/auth.py -- authenticate_user(). Database calls are
# monkeypatched onto the module so this runs with no PostgreSQL server.
# ---------------------------------------------------------------------------


def test_authenticate_user_returns_the_user_for_correct_credentials(monkeypatch):
    stored_hash = hash_password("correct-password")
    row = {
        "id": "user-1",
        "email": "alice@example.com",
        "display_name": "Alice",
        "status": "active",
        "last_login_at": None,
        "created_at": datetime.now(timezone.utc),
        "password_hash": stored_hash,
    }
    monkeypatch.setattr(auth_module, "_get_user_credentials", lambda dsn, email: row)
    login_calls = []
    monkeypatch.setattr(auth_module, "update_last_login", lambda dsn, user_id: login_calls.append(user_id))

    result = authenticate_user("unused-dsn", "alice@example.com", "correct-password")
    assert result is not None
    assert result.id == "user-1"
    assert login_calls == ["user-1"]


def test_authenticate_user_rejects_wrong_password(monkeypatch):
    row = {
        "id": "user-1",
        "email": "alice@example.com",
        "display_name": "Alice",
        "status": "active",
        "last_login_at": None,
        "created_at": datetime.now(timezone.utc),
        "password_hash": hash_password("correct-password"),
    }
    monkeypatch.setattr(auth_module, "_get_user_credentials", lambda dsn, email: row)
    monkeypatch.setattr(auth_module, "update_last_login", lambda dsn, user_id: None)

    assert authenticate_user("unused-dsn", "alice@example.com", "wrong-password") is None


def test_authenticate_user_returns_none_for_unknown_email(monkeypatch):
    monkeypatch.setattr(auth_module, "_get_user_credentials", lambda dsn, email: None)

    assert authenticate_user("unused-dsn", "nobody@example.com", "any-password") is None


def test_authenticate_user_rejects_a_disabled_account_even_with_the_correct_password(monkeypatch):
    row = {
        "id": "user-1",
        "email": "alice@example.com",
        "display_name": "Alice",
        "status": "disabled",
        "last_login_at": None,
        "created_at": datetime.now(timezone.utc),
        "password_hash": hash_password("correct-password"),
    }
    monkeypatch.setattr(auth_module, "_get_user_credentials", lambda dsn, email: row)
    login_calls = []
    monkeypatch.setattr(auth_module, "update_last_login", lambda dsn, user_id: login_calls.append(user_id))

    assert authenticate_user("unused-dsn", "alice@example.com", "correct-password") is None
    assert login_calls == [], "last_login_at must not be updated for a rejected (disabled) account"


def test_authenticate_user_never_returns_a_password_hash():
    """UserOut has no password_hash field -- structurally impossible for
    it to leak through this function's return value."""
    assert "password_hash" not in UserOut.model_fields


# ---------------------------------------------------------------------------
# app/api/dependencies/auth.py -- get_current_user(). A throwaway app,
# never app.main.app. get_user is monkeypatched onto the module so this
# runs with no PostgreSQL server.
# ---------------------------------------------------------------------------


def _build_whoami_app(settings: Settings) -> FastAPI:
    app = FastAPI()

    @app.get("/whoami", dependencies=[])
    def whoami(user: UserOut = Depends(get_current_user)) -> dict:
        return {"user_id": user.id}

    from app.utils.config import get_settings

    app.dependency_overrides[get_settings] = lambda: settings
    return app


def test_get_current_user_rejects_a_missing_authorization_header():
    app = _build_whoami_app(_settings())
    with TestClient(app) as client:
        response = client.get("/whoami")
    assert response.status_code == 401


def test_get_current_user_rejects_a_malformed_token():
    app = _build_whoami_app(_settings())
    with TestClient(app) as client:
        response = client.get("/whoami", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_get_current_user_rejects_an_expired_token(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(auth_module, "get_user", lambda dsn, user_id: _user(user_id))
    expired_token = create_access_token("user-1", _settings(jwt_expiry_minutes=-1))

    app = _build_whoami_app(settings)
    with TestClient(app) as client:
        response = client.get("/whoami", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


def test_get_current_user_rejects_a_token_for_a_deleted_or_unknown_user(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(auth_module, "get_user", lambda dsn, user_id: None)
    token = create_access_token("user-does-not-exist", settings)

    app = _build_whoami_app(settings)
    with TestClient(app) as client:
        response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_get_current_user_rejects_a_token_for_a_disabled_account(monkeypatch):
    """The token itself is perfectly valid -- the account was disabled
    after it was issued. Re-checked fresh against the database on every
    request, not trusted from anything cached in the token."""
    settings = _settings()
    monkeypatch.setattr(auth_module, "get_user", lambda dsn, user_id: _user(user_id, status="disabled"))
    token = create_access_token("user-1", settings)

    app = _build_whoami_app(settings)
    with TestClient(app) as client:
        response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_get_current_user_accepts_a_valid_token_for_an_active_user(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(auth_module, "get_user", lambda dsn, user_id: _user(user_id))
    token = create_access_token("user-42", settings)

    app = _build_whoami_app(settings)
    with TestClient(app) as client:
        response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"user_id": "user-42"}


def test_get_current_user_error_response_does_not_distinguish_failure_reason():
    """Missing header, malformed token, and (via other tests above)
    every other failure mode all produce the identical 401 detail, so a
    caller cannot use response content to enumerate valid user_ids or
    tell "expired" apart from "forged"."""
    app = _build_whoami_app(_settings())
    with TestClient(app) as client:
        no_header = client.get("/whoami")
        bad_token = client.get("/whoami", headers={"Authorization": "Bearer garbage"})
    assert no_header.status_code == bad_token.status_code == 401
    assert no_header.json()["detail"] == bad_token.json()["detail"]


# ---------------------------------------------------------------------------
# get_current_membership() + require_role() -- full chain, unchanged
# require_role() logic. get_membership is monkeypatched onto the
# authorization module so this runs with no PostgreSQL server.
# ---------------------------------------------------------------------------


def _build_orgs_app(settings: Settings) -> FastAPI:
    app = FastAPI()

    @app.get("/orgs/{org_id}/admin-only", dependencies=[Depends(require_role("owner", "admin"))])
    def admin_only(org_id: str) -> dict:
        return {"ok": True, "org_id": org_id}

    from app.utils.config import get_settings

    app.dependency_overrides[get_settings] = lambda: settings
    return app


def test_full_chain_allows_a_correctly_authorized_request(monkeypatch):
    """JWT -> get_current_user -> get_current_membership (org_id from
    the route path, never trusted from a client header) -> require_role,
    end to end, with zero changes to require_role() itself."""
    settings = _settings()
    monkeypatch.setattr(auth_module, "get_user", lambda dsn, user_id: _user(user_id))
    monkeypatch.setattr(
        authorization_module,
        "get_membership",
        lambda dsn, org_id, user_id: _membership(org_id, user_id, "admin") if org_id == "org-a" else None,
    )
    token = create_access_token("user-1", settings)

    app = _build_orgs_app(settings)
    with TestClient(app) as client:
        response = client.get("/orgs/org-a/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "org_id": "org-a"}


def test_full_chain_rejects_a_cross_tenant_access_attempt(monkeypatch):
    """The same authenticated user, same token, requesting a DIFFERENT
    org they have no membership in -- must be rejected. org_id in the
    URL is a request parameter, not a credential; a client can put any
    org_id there, but only ever gets access where a real membership row
    exists for their real, verified identity."""
    settings = _settings()
    monkeypatch.setattr(auth_module, "get_user", lambda dsn, user_id: _user(user_id))
    monkeypatch.setattr(
        authorization_module,
        "get_membership",
        lambda dsn, org_id, user_id: _membership(org_id, user_id, "admin") if org_id == "org-a" else None,
    )
    token = create_access_token("user-1", settings)

    app = _build_orgs_app(settings)
    with TestClient(app) as client:
        response = client.get("/orgs/org-b/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_full_chain_rejects_a_disabled_user_before_ever_checking_membership(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(auth_module, "get_user", lambda dsn, user_id: _user(user_id, status="disabled"))
    membership_lookups = []
    monkeypatch.setattr(
        authorization_module,
        "get_membership",
        lambda dsn, org_id, user_id: membership_lookups.append((org_id, user_id)) or _membership(org_id, user_id, "admin"),
    )
    token = create_access_token("user-1", settings)

    app = _build_orgs_app(settings)
    with TestClient(app) as client:
        response = client.get("/orgs/org-a/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert membership_lookups == [], "a disabled account must never reach the membership lookup at all"


def test_full_chain_rejects_an_invited_but_not_yet_active_membership(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(auth_module, "get_user", lambda dsn, user_id: _user(user_id))
    monkeypatch.setattr(
        authorization_module,
        "get_membership",
        lambda dsn, org_id, user_id: _membership(org_id, user_id, "admin", status="invited"),
    )
    token = create_access_token("user-1", settings)

    app = _build_orgs_app(settings)
    with TestClient(app) as client:
        response = client.get("/orgs/org-a/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_full_chain_rejects_the_wrong_role(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(auth_module, "get_user", lambda dsn, user_id: _user(user_id))
    monkeypatch.setattr(
        authorization_module,
        "get_membership",
        lambda dsn, org_id, user_id: _membership(org_id, user_id, "viewer"),
    )
    token = create_access_token("user-1", settings)

    app = _build_orgs_app(settings)
    with TestClient(app) as client:
        response = client.get("/orgs/org-a/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_full_chain_rejects_with_no_credentials_at_all():
    app = _build_orgs_app(_settings())
    with TestClient(app) as client:
        response = client.get("/orgs/org-a/admin-only")
    assert response.status_code == 401


def test_get_current_membership_passes_org_id_and_verified_user_id_through_unchanged(monkeypatch):
    """Direct unit check (no HTTP) that get_current_membership calls
    get_membership with exactly (postgres_dsn, org_id, user.id) -- the
    verified user_id from get_current_user, never anything else."""
    settings = _settings(postgres_dsn="postgres://unit-test-dsn")
    captured = {}

    def _fake_get_membership(dsn, org_id, user_id):
        captured["args"] = (dsn, org_id, user_id)
        return _membership(org_id, user_id, "owner")

    monkeypatch.setattr(authorization_module, "get_membership", _fake_get_membership)

    result = get_current_membership(org_id="org-z", user=_user("user-99"), settings=settings)
    assert captured["args"] == ("postgres://unit-test-dsn", "org-z", "user-99")
    assert result is not None
    assert result.role == "owner"


# ---------------------------------------------------------------------------
# End-to-end tests against a real PostgreSQL server.
# ---------------------------------------------------------------------------


@requires_postgres
def test_authenticate_user_round_trip_against_real_postgres():
    from app.database.postgres.tenancy import create_user

    email = "auth.roundtrip@example.com"
    create_user(POSTGRES_TEST_DSN, email=email, display_name="Auth Roundtrip", password_hash=hash_password("s3cure-pass!"))

    authenticated = authenticate_user(POSTGRES_TEST_DSN, email, "s3cure-pass!")
    assert authenticated is not None
    assert authenticated.email == email

    assert authenticate_user(POSTGRES_TEST_DSN, email, "wrong-password") is None
    assert authenticate_user(POSTGRES_TEST_DSN, "nobody-here@example.com", "s3cure-pass!") is None


@requires_postgres
def test_authenticate_user_updates_last_login_at_on_success():
    from app.database.postgres.tenancy import create_user, get_user

    email = "last.login@example.com"
    created = create_user(POSTGRES_TEST_DSN, email=email, display_name="Last Login Test", password_hash=hash_password("s3cure-pass!"))
    assert created.last_login_at is None

    authenticate_user(POSTGRES_TEST_DSN, email, "s3cure-pass!")

    refreshed = get_user(POSTGRES_TEST_DSN, created.id)
    assert refreshed.last_login_at is not None


@requires_postgres
def test_get_current_membership_resolves_real_active_membership_and_rejects_cross_tenant():
    from app.database.postgres.tenancy import create_membership, create_organization, create_user

    org_a = create_organization(POSTGRES_TEST_DSN, name="2B4 Org A", industry_type="ecommerce")
    org_b = create_organization(POSTGRES_TEST_DSN, name="2B4 Org B", industry_type="ecommerce")
    user = create_user(
        POSTGRES_TEST_DSN,
        email="2b4.membership@example.com",
        display_name="2B4 Membership Test",
        password_hash=hash_password("s3cure-pass!"),
    )
    create_membership(POSTGRES_TEST_DSN, org_id=org_a.id, user_id=user.id, role="finance")

    settings = _settings(postgres_dsn=POSTGRES_TEST_DSN)
    resolved = get_current_membership(org_id=org_a.id, user=user, settings=settings)
    assert resolved is not None
    assert resolved.role == "finance"

    cross_tenant = get_current_membership(org_id=org_b.id, user=user, settings=settings)
    assert cross_tenant is None
