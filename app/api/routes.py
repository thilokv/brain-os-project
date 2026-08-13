"""API routes for Brain OS.

    POST /brain-os/start           Facility 1: Document Intake
    POST /brain-os/resume          Facility 5: Human in the Loop
    GET  /brain-os/status/{id}     Current workflow state
    GET  /brain-os/audit/{id}      Facility: Auditability
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.database import repository
from app.models.schemas import (
    AuditTrailResponse,
    ExecutiveBriefing,
    ExtractedInvoiceData,
    InvoiceIntakeRequest,
    ResumeRequest,
    RiskAssessment,
    WorkflowResumeResponse,
    WorkflowStartResponse,
    WorkflowStatusResponse,
)
from app.utils.logging import get_logger
from app.workflows.graph import WorkflowEngine

logger = get_logger(__name__)
router = APIRouter(prefix="/brain-os", tags=["brain-os"])


def _engine(request: Request) -> WorkflowEngine:
    return request.app.state.engine


def _database_path(request: Request) -> str:
    return request.app.state.settings.database_path


@router.post("/start", response_model=WorkflowStartResponse, status_code=201)
def start_workflow(payload: InvoiceIntakeRequest, request: Request) -> WorkflowStartResponse:
    """Ingest raw invoice text and run it through extraction, risk scoring, and (if it
    clears auto-approval) the executive briefing -- pausing for human approval otherwise."""
    logger.info("Received invoice intake request (%d chars).", len(payload.text))
    result = _engine(request).start(payload.text)

    extracted = ExtractedInvoiceData(
        vendor=result.get("vendor"),
        po_number=result.get("po_number"),
        amount=result.get("amount"),
        raw_text=payload.text,
    )
    risk = RiskAssessment(
        risk_score=result.get("risk_score", 0.0),
        auto_approved=result.get("auto_approved", False),
        anomalies=result.get("anomalies", []),
        threshold=result.get("threshold", 0.0),
    )

    briefing = None
    if "summary" in result:
        briefing = ExecutiveBriefing(
            vendor=extracted.vendor,
            amount=extracted.amount,
            po_number=extracted.po_number,
            risk_score=risk.risk_score,
            approval_result=result.get("approval_decision", "unknown"),
            workflow_outcome=result["status"],
            summary=result["summary"],
            generated_by=result["generated_by"],
        )

    return WorkflowStartResponse(
        workflow_id=result["workflow_id"], status=result["status"], extracted=extracted, risk=risk, briefing=briefing
    )


@router.post("/resume", response_model=WorkflowResumeResponse)
def resume_workflow(payload: ResumeRequest, request: Request) -> WorkflowResumeResponse:
    """Resume a workflow paused for human approval, from its LangGraph checkpoint."""
    database_path = _database_path(request)

    current_status = repository.get_workflow_status(database_path, payload.workflow_id)
    if current_status is None:
        raise HTTPException(status_code=404, detail=f"Unknown workflow_id: {payload.workflow_id}")
    if current_status != "awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Workflow {payload.workflow_id} is not awaiting approval (current status: {current_status}).",
        )

    logger.info("Resuming workflow %s with decision=%s user=%s", payload.workflow_id, payload.decision, payload.user)
    result = _engine(request).resume(payload.workflow_id, decision=payload.decision, user=payload.user, note=payload.note)

    briefing = ExecutiveBriefing(
        vendor=result.get("vendor"),
        amount=result.get("amount"),
        po_number=result.get("po_number"),
        risk_score=result.get("risk_score", 0.0),
        approval_result=result["approval_decision"],
        workflow_outcome=result["status"],
        summary=result["summary"],
        generated_by=result["generated_by"],
    )
    return WorkflowResumeResponse(workflow_id=payload.workflow_id, status=result["status"], briefing=briefing)


@router.get("/status/{workflow_id}", response_model=WorkflowStatusResponse)
def get_workflow_status_endpoint(workflow_id: str, request: Request) -> WorkflowStatusResponse:
    """Look up the current persisted state of a workflow."""
    database_path = _database_path(request)
    status = repository.get_workflow_status(database_path, workflow_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Unknown workflow_id: {workflow_id}")

    extracted = repository.get_invoice(database_path, workflow_id)
    risk = repository.get_risk_assessment(database_path, workflow_id)
    briefing_row = repository.get_briefing(database_path, workflow_id)
    approval_row = repository.get_approval(database_path, workflow_id)

    briefing = None
    if briefing_row and approval_row:
        briefing = ExecutiveBriefing(
            vendor=extracted.vendor if extracted else None,
            amount=extracted.amount if extracted else None,
            po_number=extracted.po_number if extracted else None,
            risk_score=risk.risk_score if risk else 0.0,
            approval_result=approval_row["decision"],
            workflow_outcome=status,
            summary=briefing_row["summary"],
            generated_by=briefing_row["generated_by"],
        )

    return WorkflowStatusResponse(workflow_id=workflow_id, status=status, extracted=extracted, risk=risk, briefing=briefing)


@router.get("/audit/{workflow_id}", response_model=AuditTrailResponse)
def get_audit_trail_endpoint(workflow_id: str, request: Request) -> AuditTrailResponse:
    """Return the full, timestamped audit trail for a workflow."""
    database_path = _database_path(request)
    events = repository.get_audit_trail(database_path, workflow_id)
    if not events:
        raise HTTPException(status_code=404, detail=f"No audit trail found for workflow_id: {workflow_id}")
    return AuditTrailResponse(workflow_id=workflow_id, events=events)
