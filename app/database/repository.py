"""Data-access functions backing Facility 3 (Knowledge Memory) and auditability.

Every function opens its own short-lived connection (see
`app.database.connection.get_connection`) and commits before returning,
so callers never have to manage transactions directly.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from app.database.connection import get_connection
from app.models.schemas import Anomaly, AuditEvent, ExtractedInvoiceData, RiskAssessment


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_invoice(database_path: str, workflow_id: str, extracted: ExtractedInvoiceData) -> None:
    with get_connection(database_path) as conn:
        conn.execute(
            """
            INSERT INTO invoices (workflow_id, vendor, po_number, amount, raw_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (workflow_id) DO UPDATE SET
                vendor = excluded.vendor,
                po_number = excluded.po_number,
                amount = excluded.amount,
                raw_text = excluded.raw_text
            """,
            (workflow_id, extracted.vendor, extracted.po_number, extracted.amount, extracted.raw_text, _now()),
        )


def save_risk_assessment(database_path: str, workflow_id: str, risk: RiskAssessment) -> None:
    with get_connection(database_path) as conn:
        conn.execute(
            """
            INSERT INTO risk_assessments (workflow_id, risk_score, auto_approved, anomalies_json, threshold, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (workflow_id) DO UPDATE SET
                risk_score = excluded.risk_score,
                auto_approved = excluded.auto_approved,
                anomalies_json = excluded.anomalies_json,
                threshold = excluded.threshold
            """,
            (
                workflow_id,
                risk.risk_score,
                int(risk.auto_approved),
                json.dumps([a.model_dump() for a in risk.anomalies]),
                risk.threshold,
                _now(),
            ),
        )


def save_approval(
    database_path: str, workflow_id: str, decision: str, approved_by: str, note: Optional[str]
) -> None:
    with get_connection(database_path) as conn:
        conn.execute(
            """
            INSERT INTO approvals (workflow_id, decision, approved_by, note, decided_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (workflow_id) DO UPDATE SET
                decision = excluded.decision,
                approved_by = excluded.approved_by,
                note = excluded.note,
                decided_at = excluded.decided_at
            """,
            (workflow_id, decision, approved_by, note, _now()),
        )


def save_briefing(database_path: str, workflow_id: str, summary: str, generated_by: str) -> None:
    with get_connection(database_path) as conn:
        conn.execute(
            """
            INSERT INTO briefings (workflow_id, summary, generated_by, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (workflow_id) DO UPDATE SET
                summary = excluded.summary,
                generated_by = excluded.generated_by
            """,
            (workflow_id, summary, generated_by, _now()),
        )


def save_workflow_state(database_path: str, workflow_id: str, status: str) -> None:
    with get_connection(database_path) as conn:
        conn.execute(
            """
            INSERT INTO workflow_state (workflow_id, status, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT (workflow_id) DO UPDATE SET
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (workflow_id, status, _now()),
        )


def record_audit_event(database_path: str, workflow_id: str, action: str, status: str, detail: Optional[str] = None) -> None:
    """Append-only audit log entry. Facility: Auditability."""
    with get_connection(database_path) as conn:
        conn.execute(
            "INSERT INTO audit_trail (workflow_id, timestamp, action, status, detail) VALUES (?, ?, ?, ?, ?)",
            (workflow_id, _now(), action, status, detail),
        )


def get_audit_trail(database_path: str, workflow_id: str) -> list[AuditEvent]:
    with get_connection(database_path) as conn:
        rows = conn.execute(
            "SELECT id, workflow_id, timestamp, action, status, detail FROM audit_trail WHERE workflow_id = ? ORDER BY id ASC",
            (workflow_id,),
        ).fetchall()
    return [AuditEvent(**dict(row)) for row in rows]


def get_workflow_status(database_path: str, workflow_id: str) -> Optional[str]:
    with get_connection(database_path) as conn:
        row = conn.execute(
            "SELECT status FROM workflow_state WHERE workflow_id = ?", (workflow_id,)
        ).fetchone()
    return row["status"] if row else None


def get_invoice(database_path: str, workflow_id: str) -> Optional[ExtractedInvoiceData]:
    with get_connection(database_path) as conn:
        row = conn.execute(
            "SELECT vendor, po_number, amount, raw_text FROM invoices WHERE workflow_id = ?",
            (workflow_id,),
        ).fetchone()
    return ExtractedInvoiceData(**dict(row)) if row else None


def get_risk_assessment(database_path: str, workflow_id: str) -> Optional[RiskAssessment]:
    with get_connection(database_path) as conn:
        row = conn.execute(
            "SELECT risk_score, auto_approved, anomalies_json, threshold FROM risk_assessments WHERE workflow_id = ?",
            (workflow_id,),
        ).fetchone()
    if not row:
        return None
    anomalies = [Anomaly(**a) for a in json.loads(row["anomalies_json"])]
    return RiskAssessment(
        risk_score=row["risk_score"],
        auto_approved=bool(row["auto_approved"]),
        anomalies=anomalies,
        threshold=row["threshold"],
    )


def get_briefing(database_path: str, workflow_id: str) -> Optional[dict]:
    with get_connection(database_path) as conn:
        row = conn.execute(
            "SELECT summary, generated_by FROM briefings WHERE workflow_id = ?", (workflow_id,)
        ).fetchone()
    return dict(row) if row else None


def get_approval(database_path: str, workflow_id: str) -> Optional[dict]:
    with get_connection(database_path) as conn:
        row = conn.execute(
            "SELECT decision, approved_by, note FROM approvals WHERE workflow_id = ?", (workflow_id,)
        ).fetchone()
    return dict(row) if row else None


def list_known_invoices(database_path: str, exclude_workflow_id: str) -> list[dict]:
    """Used by the risk engine's duplicate-detection anomaly check."""
    with get_connection(database_path) as conn:
        rows = conn.execute(
            "SELECT workflow_id, vendor, po_number, amount FROM invoices WHERE workflow_id != ?",
            (exclude_workflow_id,),
        ).fetchall()
    return [dict(row) for row in rows]
