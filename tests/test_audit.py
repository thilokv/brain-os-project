"""Tests for the auditability requirement: every workflow action is recorded."""

from __future__ import annotations


def test_audit_trail_records_full_lifecycle_for_auto_approved_workflow(client):
    started = client.post("/brain-os/start", json={"text": "Vendor: Small Co\nPO Number: PO-1\nAmount: $100"}).json()
    workflow_id = started["workflow_id"]

    response = client.get(f"/brain-os/audit/{workflow_id}")
    assert response.status_code == 200
    events = response.json()["events"]
    actions = [event["action"] for event in events]

    assert actions == [
        "workflow.start",
        "document_intelligence.extract",
        "risk_engine.assess",
        "risk_engine.auto_approve",
        "executive_briefing.generate",
    ]
    for event in events:
        assert event["timestamp"]
        assert event["status"]


def test_audit_trail_records_human_decision_for_paused_workflow(client):
    started = client.post(
        "/brain-os/start", json={"text": "Vendor: Acme Logistics\nPO Number: PO-1001\nAmount: $7500"}
    ).json()
    workflow_id = started["workflow_id"]
    client.post(
        "/brain-os/resume",
        json={"workflow_id": workflow_id, "decision": "rejected", "user": "bob", "note": "too risky"},
    )

    events = client.get(f"/brain-os/audit/{workflow_id}").json()["events"]
    actions = [event["action"] for event in events]

    assert "notification.slack" in actions
    assert "human_in_loop.decision" in actions
    decision_event = next(e for e in events if e["action"] == "human_in_loop.decision")
    assert decision_event["status"] == "rejected"
    assert decision_event["detail"] == "too risky"


def test_audit_trail_unknown_workflow_returns_404(client):
    response = client.get("/brain-os/audit/wf-does-not-exist")
    assert response.status_code == 404
