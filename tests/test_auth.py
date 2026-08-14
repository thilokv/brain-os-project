"""Tests for bearer-token authentication on the /brain-os/* API surface.

`GET /health` intentionally has no auth tests here beyond Test 4 --
tests/test_health.py already exercises it unauthenticated on every run.
"""

from __future__ import annotations

from tests.conftest import TEST_API_TOKEN

START_PAYLOAD = {"text": "Vendor: Auth Test Co\nPO Number: PO-AUTH-1\nAmount: $100"}


# --- Test 1: protected endpoint, no Authorization header -----------------


def test_start_without_token_returns_401(client):
    response = client.post("/brain-os/start", json=START_PAYLOAD)
    assert response.status_code == 401


# --- Test 2: protected endpoint, invalid bearer token ---------------------


def test_start_with_invalid_token_returns_401(client):
    response = client.post(
        "/brain-os/start", json=START_PAYLOAD, headers={"Authorization": "Bearer wrong-token"}
    )
    assert response.status_code == 401


# --- Test 3: protected endpoint, correct token reaches application logic --


def test_start_with_valid_token_reaches_application_logic(client, auth_headers):
    response = client.post("/brain-os/start", json=START_PAYLOAD, headers=auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["extracted"]["vendor"] == "Auth Test Co"
    assert body["status"] == "completed"


# --- Test 4: GET /health requires no authentication ------------------------


def test_health_requires_no_authentication(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# --- Test 5: auth failures never expose the expected token -----------------


def test_auth_failure_does_not_expose_expected_token(client):
    no_header_response = client.post("/brain-os/start", json=START_PAYLOAD)
    wrong_token_response = client.post(
        "/brain-os/start", json=START_PAYLOAD, headers={"Authorization": "Bearer wrong-token"}
    )

    for response in (no_header_response, wrong_token_response):
        assert response.status_code == 401
        assert TEST_API_TOKEN not in response.text
        # The failure message is generic and does not vary by failure mode.
        assert response.json()["detail"] == "Missing or invalid bearer token."


# --- Test 6: /brain-os/resume is protected ----------------------------------


def test_resume_without_token_returns_401(client):
    response = client.post("/brain-os/resume", json={"workflow_id": "wf-does-not-exist", "decision": "approved"})
    assert response.status_code == 401


def test_resume_with_invalid_token_returns_401(client):
    response = client.post(
        "/brain-os/resume",
        json={"workflow_id": "wf-does-not-exist", "decision": "approved"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401


# --- Test 7: /brain-os/status/{workflow_id} is protected --------------------


def test_status_without_token_returns_401(client):
    response = client.get("/brain-os/status/wf-does-not-exist")
    assert response.status_code == 401


def test_status_with_invalid_token_returns_401(client):
    response = client.get(
        "/brain-os/status/wf-does-not-exist", headers={"Authorization": "Bearer wrong-token"}
    )
    assert response.status_code == 401


# --- Test 8: /brain-os/audit/{workflow_id} is protected ----------------------


def test_audit_without_token_returns_401(client):
    response = client.get("/brain-os/audit/wf-does-not-exist")
    assert response.status_code == 401


def test_audit_with_invalid_token_returns_401(client):
    response = client.get(
        "/brain-os/audit/wf-does-not-exist", headers={"Authorization": "Bearer wrong-token"}
    )
    assert response.status_code == 401


# --- Bonus: an unconfigured token must fail closed, not open ---------------


def test_unconfigured_token_rejects_every_request(client, monkeypatch):
    from app.utils.config import get_settings

    monkeypatch.setenv("BRAIN_OS_API_TOKEN", "")
    get_settings.cache_clear()
    try:
        response = client.post("/brain-os/start", json=START_PAYLOAD, headers={"Authorization": "Bearer anything"})
        assert response.status_code == 401
    finally:
        monkeypatch.setenv("BRAIN_OS_API_TOKEN", TEST_API_TOKEN)
        get_settings.cache_clear()


# --- Bonus: OpenAPI/Swagger correctly describes the bearer requirement -----


def test_openapi_schema_declares_bearer_auth(client):
    schema = client.get("/openapi.json").json()

    security_schemes = schema["components"]["securitySchemes"]
    assert any(s.get("scheme") == "bearer" for s in security_schemes.values())

    start_operation = schema["paths"]["/brain-os/start"]["post"]
    assert start_operation.get("security"), "/brain-os/start should declare a security requirement in OpenAPI"

    health_operation = schema["paths"]["/health"]["get"]
    assert not health_operation.get("security"), "/health must stay unauthenticated in the OpenAPI schema"
