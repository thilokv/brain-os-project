"""Tests for Facility 1 (Document Intake) and Facility 2 (Document Intelligence)."""

from __future__ import annotations


def test_start_auto_approves_small_invoice(client, auth_headers):
    response = client.post(
        "/brain-os/start", json={"text": "Vendor: Small Co\nPO Number: PO-1\nAmount: $100"}, headers=auth_headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["extracted"]["vendor"] == "Small Co"
    assert body["extracted"]["po_number"] == "PO-1"
    assert body["extracted"]["amount"] == 100.0
    assert body["risk"]["auto_approved"] is True
    assert body["briefing"] is not None
    assert body["briefing"]["approval_result"] == "approved"


def test_start_rejects_blank_text(client, auth_headers):
    response = client.post("/brain-os/start", json={"text": "   "}, headers=auth_headers)
    assert response.status_code == 422


def test_start_pauses_large_invoice_for_approval(client, auth_headers):
    response = client.post(
        "/brain-os/start",
        json={"text": "Vendor: Acme Logistics\nPO Number: PO-1001\nAmount: $7500"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "awaiting_approval"
    assert body["risk"]["auto_approved"] is False
    assert body["briefing"] is None


def test_extraction_handles_missing_fields_as_anomalies(client, auth_headers):
    response = client.post(
        "/brain-os/start", json={"text": "Some unrelated text with no recognizable fields."}, headers=auth_headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["extracted"]["vendor"] is None
    assert body["extracted"]["amount"] is None
    codes = {a["code"] for a in body["risk"]["anomalies"]}
    assert "missing_vendor" in codes
    assert "missing_amount" in codes
    # High-severity anomalies force human review even though the (missing) amount can't clear the threshold.
    assert body["status"] == "awaiting_approval"
