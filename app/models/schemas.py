"""Pydantic models shared across the API, services, and workflow layers."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

ApprovalDecision = Literal["approved", "rejected"]
WorkflowStatus = Literal[
    "pending",
    "auto_approved",
    "awaiting_approval",
    "approved",
    "rejected",
    "completed",
]


class InvoiceIntakeRequest(BaseModel):
    """Payload for POST /brain-os/start."""

    text: str = Field(..., min_length=1, description="Raw invoice text to ingest.")

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class ExtractedInvoiceData(BaseModel):
    """Fields pulled out of raw invoice text by the document intelligence service."""

    vendor: Optional[str] = None
    po_number: Optional[str] = None
    amount: Optional[float] = None
    raw_text: str

    @field_validator("amount")
    @classmethod
    def amount_non_negative(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and value < 0:
            raise ValueError("amount must not be negative")
        return value


class Anomaly(BaseModel):
    """A single anomaly flagged by the risk engine."""

    code: str
    detail: str
    severity: Literal["low", "medium", "high"]


class RiskAssessment(BaseModel):
    """Result of running the risk engine against extracted invoice data."""

    risk_score: float = Field(..., ge=0.0, le=100.0)
    auto_approved: bool
    anomalies: list[Anomaly] = Field(default_factory=list)
    threshold: float


class ResumeRequest(BaseModel):
    """Payload for POST /brain-os/resume."""

    workflow_id: str = Field(..., min_length=1)
    decision: ApprovalDecision
    user: str = Field(default="unknown_approver")
    note: Optional[str] = None


class ExecutiveBriefing(BaseModel):
    """Final human-readable summary of a completed workflow."""

    vendor: Optional[str]
    amount: Optional[float]
    po_number: Optional[str]
    risk_score: float
    approval_result: str
    workflow_outcome: WorkflowStatus
    summary: str
    generated_by: Literal["anthropic", "deterministic_fallback"]


class AuditEvent(BaseModel):
    """A single row in the audit trail."""

    id: int
    workflow_id: str
    timestamp: datetime
    action: str
    status: str
    detail: Optional[str] = None


class WorkflowStartResponse(BaseModel):
    workflow_id: str
    status: WorkflowStatus
    extracted: ExtractedInvoiceData
    risk: RiskAssessment
    briefing: Optional[ExecutiveBriefing] = None


class WorkflowResumeResponse(BaseModel):
    workflow_id: str
    status: WorkflowStatus
    briefing: ExecutiveBriefing


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    status: WorkflowStatus
    extracted: Optional[ExtractedInvoiceData] = None
    risk: Optional[RiskAssessment] = None
    briefing: Optional[ExecutiveBriefing] = None


class AuditTrailResponse(BaseModel):
    workflow_id: str
    events: list[AuditEvent]
