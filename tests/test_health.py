"""Tests for the /health liveness/readiness endpoint used by container orchestrators."""

from __future__ import annotations


def test_health_reports_ok_when_database_is_reachable(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["service"]
