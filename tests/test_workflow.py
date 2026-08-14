"""Tests for Facility 5 (Human in the Loop) and the LangGraph pause/resume cycle."""

from __future__ import annotations


def _start(client, auth_headers, text):
    response = client.post("/brain-os/start", json={"text": text}, headers=auth_headers)
    assert response.status_code == 201
    return response.json()


def test_resume_approved_completes_workflow(client, auth_headers):
    started = _start(client, auth_headers, "Vendor: Acme Logistics\nPO Number: PO-1001\nAmount: $7500")
    workflow_id = started["workflow_id"]
    assert started["status"] == "awaiting_approval"

    response = client.post(
        "/brain-os/resume",
        json={"workflow_id": workflow_id, "decision": "approved", "user": "alice"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["briefing"]["approval_result"] == "approved"


def test_resume_rejected_completes_workflow_as_rejected(client, auth_headers):
    started = _start(client, auth_headers, "Vendor: Big Vendor\nPO Number: PO-9999\nAmount: $50000")
    workflow_id = started["workflow_id"]

    response = client.post(
        "/brain-os/resume",
        json={"workflow_id": workflow_id, "decision": "rejected", "user": "bob", "note": "over budget"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["briefing"]["approval_result"] == "rejected"


def test_resume_unknown_workflow_returns_404(client, auth_headers):
    response = client.post(
        "/brain-os/resume", json={"workflow_id": "wf-does-not-exist", "decision": "approved"}, headers=auth_headers
    )
    assert response.status_code == 404


def test_double_resume_returns_409(client, auth_headers):
    started = _start(client, auth_headers, "Vendor: Acme Logistics\nPO Number: PO-1001\nAmount: $7500")
    workflow_id = started["workflow_id"]
    client.post(
        "/brain-os/resume",
        json={"workflow_id": workflow_id, "decision": "approved", "user": "alice"},
        headers=auth_headers,
    )

    response = client.post(
        "/brain-os/resume",
        json={"workflow_id": workflow_id, "decision": "approved", "user": "alice"},
        headers=auth_headers,
    )
    assert response.status_code == 409


def test_resume_auto_approved_workflow_returns_409(client, auth_headers):
    started = _start(client, auth_headers, "Vendor: Small Co\nPO Number: PO-1\nAmount: $100")
    workflow_id = started["workflow_id"]
    assert started["status"] == "completed"

    response = client.post(
        "/brain-os/resume",
        json={"workflow_id": workflow_id, "decision": "approved", "user": "alice"},
        headers=auth_headers,
    )
    assert response.status_code == 409


def test_status_endpoint_reflects_pause_and_completion(client, auth_headers):
    started = _start(client, auth_headers, "Vendor: Acme Logistics\nPO Number: PO-1001\nAmount: $7500")
    workflow_id = started["workflow_id"]

    paused = client.get(f"/brain-os/status/{workflow_id}", headers=auth_headers).json()
    assert paused["status"] == "awaiting_approval"
    assert paused["briefing"] is None

    client.post(
        "/brain-os/resume",
        json={"workflow_id": workflow_id, "decision": "approved", "user": "alice"},
        headers=auth_headers,
    )

    completed = client.get(f"/brain-os/status/{workflow_id}", headers=auth_headers).json()
    assert completed["status"] == "completed"
    assert completed["briefing"] is not None


def test_status_unknown_workflow_returns_404(client, auth_headers):
    response = client.get("/brain-os/status/wf-does-not-exist", headers=auth_headers)
    assert response.status_code == 404
