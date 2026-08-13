"""LangGraph workflow wiring Facilities 2-6 together.

    extract -> risk -> approval_gate -> briefing -> END

`approval_gate` calls `interrupt()` when human approval is required,
which pauses the graph and checkpoints its state via the SQLite
checkpointer (Facility 5: Human in the Loop). POST /brain-os/resume
drives the graph forward again with `Command(resume=...)`, picking up
exactly where it left off rather than restarting the workflow.

Side effects (SQLite writes, Slack notification, Chroma indexing) are
placed only in nodes that run exactly once per workflow -- `extract`,
`risk`, and the post-interrupt tail of `approval_gate` -- because
LangGraph re-runs a node's code from the top on resume up to the point
where `interrupt()` returns; code before that call in `approval_gate` is
intentionally side-effect free.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.database import repository
from app.database.vector_store import VectorMemory
from app.models.schemas import Anomaly, ExtractedInvoiceData, RiskAssessment
from app.services.document_intelligence import DocumentIntelligenceService
from app.services.executive_briefing import ExecutiveBriefingService
from app.services.notification_service import NotificationService
from app.services.risk_engine import RiskEngine
from app.utils.logging import get_logger
from app.workflows.state import InvoiceWorkflowState

logger = get_logger(__name__)


class WorkflowEngine:
    """Builds and drives the invoice approval LangGraph."""

    def __init__(
        self,
        database_path: str,
        checkpointer: BaseCheckpointSaver,
        document_intelligence: DocumentIntelligenceService,
        risk_engine: RiskEngine,
        vector_memory: VectorMemory,
        briefing_service: ExecutiveBriefingService,
        notification_service: NotificationService,
    ) -> None:
        self._database_path = database_path
        self._document_intelligence = document_intelligence
        self._risk_engine = risk_engine
        self._vector_memory = vector_memory
        self._briefing_service = briefing_service
        self._notification_service = notification_service
        self._graph = self._build_graph().compile(checkpointer=checkpointer)

    # ---- node implementations --------------------------------------------

    def _extract_node(self, state: InvoiceWorkflowState) -> dict[str, Any]:
        extracted = self._document_intelligence.extract(state["raw_text"])
        repository.save_invoice(self._database_path, state["workflow_id"], extracted)
        repository.record_audit_event(
            self._database_path,
            state["workflow_id"],
            action="document_intelligence.extract",
            status="completed",
            detail=f"vendor={extracted.vendor!r} po_number={extracted.po_number!r} amount={extracted.amount!r}",
        )
        return {"vendor": extracted.vendor, "po_number": extracted.po_number, "amount": extracted.amount}

    def _risk_node(self, state: InvoiceWorkflowState) -> dict[str, Any]:
        extracted = ExtractedInvoiceData(
            vendor=state.get("vendor"),
            po_number=state.get("po_number"),
            amount=state.get("amount"),
            raw_text=state["raw_text"],
        )
        risk = self._risk_engine.assess(extracted, self._vector_memory)
        self._vector_memory.remember(state["workflow_id"], extracted.vendor, extracted.po_number, extracted.amount)
        repository.save_risk_assessment(self._database_path, state["workflow_id"], risk)

        status = "auto_approved" if risk.auto_approved else "awaiting_approval"
        repository.save_workflow_state(self._database_path, state["workflow_id"], status)
        repository.record_audit_event(
            self._database_path,
            state["workflow_id"],
            action="risk_engine.assess",
            status=status,
            detail=f"risk_score={risk.risk_score} anomalies={[a.code for a in risk.anomalies]}",
        )

        if status == "awaiting_approval":
            sent = self._notification_service.notify_approval_needed(
                state["workflow_id"], extracted.vendor, extracted.amount, risk.risk_score
            )
            repository.record_audit_event(
                self._database_path,
                state["workflow_id"],
                action="notification.slack",
                status="sent" if sent else "skipped",
            )

        return {
            "risk_score": risk.risk_score,
            "auto_approved": risk.auto_approved,
            "anomalies": [a.model_dump() for a in risk.anomalies],
            "threshold": risk.threshold,
            "status": status,
        }

    def _approval_gate_node(self, state: InvoiceWorkflowState) -> dict[str, Any]:
        if state.get("auto_approved"):
            return {"status": "auto_approved", "approval_decision": "approved", "approved_by": "system:auto_approval"}

        # Nothing above this line has side effects: LangGraph re-runs this
        # node's code from the top on resume, up to where interrupt() returns.
        decision_payload = interrupt(
            {
                "message": "Human approval required before this invoice can proceed.",
                "workflow_id": state["workflow_id"],
                "vendor": state.get("vendor"),
                "po_number": state.get("po_number"),
                "amount": state.get("amount"),
                "risk_score": state.get("risk_score"),
                "anomalies": state.get("anomalies", []),
            }
        )
        decision = decision_payload["decision"]
        return {
            "status": decision,
            "approval_decision": decision,
            "approved_by": decision_payload.get("user", "unknown_approver"),
            "approval_note": decision_payload.get("note"),
        }

    def _briefing_node(self, state: InvoiceWorkflowState) -> dict[str, Any]:
        workflow_id = state["workflow_id"]
        repository.save_approval(
            self._database_path,
            workflow_id,
            decision=state["approval_decision"],
            approved_by=state.get("approved_by", "system:auto_approval"),
            note=state.get("approval_note"),
        )
        repository.record_audit_event(
            self._database_path,
            workflow_id,
            action="human_in_loop.decision" if state.get("approved_by") != "system:auto_approval" else "risk_engine.auto_approve",
            status=state["approval_decision"],
            detail=state.get("approval_note"),
        )

        extracted = ExtractedInvoiceData(
            vendor=state.get("vendor"),
            po_number=state.get("po_number"),
            amount=state.get("amount"),
            raw_text=state["raw_text"],
        )
        risk = RiskAssessment(
            risk_score=state.get("risk_score", 0.0),
            auto_approved=state.get("auto_approved", False),
            anomalies=[Anomaly(**a) for a in state.get("anomalies", [])],
            threshold=state.get("threshold", 0.0),
        )
        outcome = "rejected" if state["approval_decision"] == "rejected" else "completed"
        briefing = self._briefing_service.generate(
            workflow_id, extracted, risk, outcome, approval_result=state["approval_decision"]
        )
        repository.save_briefing(self._database_path, workflow_id, briefing.summary, briefing.generated_by)
        repository.save_workflow_state(self._database_path, workflow_id, outcome)
        repository.record_audit_event(
            self._database_path,
            workflow_id,
            action="executive_briefing.generate",
            status="completed",
            detail=briefing.generated_by,
        )

        return {"status": outcome, "summary": briefing.summary, "generated_by": briefing.generated_by}

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(InvoiceWorkflowState)
        graph.add_node("extract", self._extract_node)
        graph.add_node("risk", self._risk_node)
        graph.add_node("approval_gate", self._approval_gate_node)
        graph.add_node("briefing", self._briefing_node)
        graph.add_edge(START, "extract")
        graph.add_edge("extract", "risk")
        graph.add_edge("risk", "approval_gate")
        graph.add_edge("approval_gate", "briefing")
        graph.add_edge("briefing", END)
        return graph

    # ---- public entry points ----------------------------------------------

    def start(self, raw_text: str) -> dict[str, Any]:
        workflow_id = f"wf-{uuid.uuid4().hex[:12]}"
        repository.record_audit_event(self._database_path, workflow_id, action="workflow.start", status="received")
        config = {"configurable": {"thread_id": workflow_id}}
        result = self._graph.invoke({"workflow_id": workflow_id, "raw_text": raw_text}, config=config)
        result["workflow_id"] = workflow_id
        return result

    def resume(self, workflow_id: str, decision: str, user: str, note: Optional[str]) -> dict[str, Any]:
        config = {"configurable": {"thread_id": workflow_id}}
        result = self._graph.invoke(Command(resume={"decision": decision, "user": user, "note": note}), config=config)
        result["workflow_id"] = workflow_id
        return result

    def is_awaiting_approval(self, workflow_id: str) -> bool:
        config = {"configurable": {"thread_id": workflow_id}}
        snapshot = self._graph.get_state(config)
        return bool(snapshot.next)
