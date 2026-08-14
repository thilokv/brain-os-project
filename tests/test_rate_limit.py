"""Tests for per-token rate limiting on the /brain-os/* API surface."""

from __future__ import annotations

from app.api.rate_limit import RateLimiter

STATUS_PATH = "/brain-os/status/wf-does-not-exist"


def test_rate_limiter_tracks_each_key_independently():
    limiter = RateLimiter(max_requests=2, window_seconds=60)

    # Token A uses up its quota...
    assert limiter.check("token-a") is None
    assert limiter.check("token-a") is None
    assert limiter.check("token-a") is not None  # 3rd call: over limit

    # ...but token B is unaffected, proving quotas are per-key, not global.
    assert limiter.check("token-b") is None
    assert limiter.check("token-b") is None
    assert limiter.check("token-b") is not None


def test_requests_within_limit_are_not_rate_limited(low_rate_limit_client, auth_headers):
    # RATE_LIMIT_MAX_REQUESTS=2 for this fixture -- both should pass auth/
    # rate-limit checks and reach the real handler (which 404s: no such workflow).
    first = low_rate_limit_client.get(STATUS_PATH, headers=auth_headers)
    second = low_rate_limit_client.get(STATUS_PATH, headers=auth_headers)
    assert first.status_code == 404
    assert second.status_code == 404


def test_exceeding_limit_returns_429_with_retry_after(low_rate_limit_client, auth_headers):
    low_rate_limit_client.get(STATUS_PATH, headers=auth_headers)
    low_rate_limit_client.get(STATUS_PATH, headers=auth_headers)

    third = low_rate_limit_client.get(STATUS_PATH, headers=auth_headers)
    assert third.status_code == 429
    assert third.json()["detail"] == "Rate limit exceeded. Try again later."
    assert "Retry-After" in third.headers
    assert int(third.headers["Retry-After"]) > 0


def test_failed_auth_does_not_consume_rate_limit_quota(low_rate_limit_client, auth_headers):
    # Many failed-auth attempts...
    for _ in range(5):
        response = low_rate_limit_client.get(STATUS_PATH, headers={"Authorization": "Bearer wrong"})
        assert response.status_code == 401

    # ...must not have touched the real token's quota.
    first = low_rate_limit_client.get(STATUS_PATH, headers=auth_headers)
    second = low_rate_limit_client.get(STATUS_PATH, headers=auth_headers)
    assert first.status_code == 404
    assert second.status_code == 404


def test_health_is_not_rate_limited(low_rate_limit_client):
    for _ in range(5):
        response = low_rate_limit_client.get("/health")
        assert response.status_code == 200
