"""Shared state definition for the LangGraph invoice approval workflow."""

from __future__ import annotations

from typing import Optional, TypedDict


class InvoiceWorkflowState(TypedDict, total=False):
    workflow_id: str
    raw_text: str

    # Populated by the extract node (Facility 2: Document Intelligence).
    vendor: Optional[str]
    po_number: Optional[str]
    amount: Optional[float]

    # Populated by the risk node (Facility 4: Risk Engine).
    risk_score: float
    auto_approved: bool
    anomalies: list[dict]
    threshold: float

    # Populated by the approval gate node (Facility 5: Human in the Loop).
    status: str
    approval_decision: Optional[str]
    approved_by: Optional[str]
    approval_note: Optional[str]

    # Populated by the briefing node (Facility 6: Executive Briefing).
    summary: str
    generated_by: str
