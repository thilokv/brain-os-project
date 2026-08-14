"""Tests for the two-layer request size cap:

1. MaxBodySizeMiddleware rejects an oversized body outright (413),
   before FastAPI/Pydantic ever parses it.
2. InvoiceIntakeRequest.text's max_length rejects an oversized *field*
   that's still under the raw body cap (422), same as any other
   validation error.
"""

from __future__ import annotations

# Default MAX_REQUEST_BODY_BYTES is 1 MiB (1_048_576); InvoiceIntakeRequest.text's
# max_length is 50_000 characters -- comfortably inside that body cap.


def test_oversized_body_is_rejected_before_parsing(client, auth_headers):
    huge_text = "x" * 1_100_000  # body well over the 1 MiB middleware cap
    response = client.post("/brain-os/start", json={"text": huge_text}, headers=auth_headers)
    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"]


def test_field_over_max_length_but_under_body_cap_returns_422(client, auth_headers):
    # 60,000 chars: over InvoiceIntakeRequest.text's 50_000 max_length,
    # but well under the 1 MiB body-size middleware cap -- isolates the
    # Pydantic validation path from the middleware path.
    long_text = "Vendor: X\n" + ("y" * 60_000)
    response = client.post("/brain-os/start", json={"text": long_text}, headers=auth_headers)
    assert response.status_code == 422


def test_normal_sized_invoice_is_unaffected(client, auth_headers):
    response = client.post(
        "/brain-os/start",
        json={"text": "Vendor: Small Co\nPO Number: PO-1\nAmount: $100"},
        headers=auth_headers,
    )
    assert response.status_code == 201
