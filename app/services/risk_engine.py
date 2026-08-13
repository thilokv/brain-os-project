"""Facility 4: Risk Engine.

Core rule: invoices at or below the auto-approve threshold clear
automatically; anything above it pauses the workflow for human approval.
On top of that rule, the engine flags anomalies (missing fields,
unusually large amounts, likely duplicate submissions via the Chroma
vector memory) and rolls them into a 0-100 risk score. A high-severity
anomaly forces human review even when the raw amount would otherwise
qualify for auto-approval, since an incomplete or suspicious extraction
is exactly the case a human should look at.
"""

from __future__ import annotations

from app.database.vector_store import VectorMemory
from app.models.schemas import Anomaly, ExtractedInvoiceData, RiskAssessment

_SEVERITY_PENALTY = {"low": 5.0, "medium": 10.0, "high": 20.0}


class RiskEngine:
    def __init__(self, auto_approve_threshold: float, duplicate_similarity_threshold: float) -> None:
        self._threshold = auto_approve_threshold
        self._duplicate_threshold = duplicate_similarity_threshold

    def assess(self, extracted: ExtractedInvoiceData, vector_memory: VectorMemory) -> RiskAssessment:
        anomalies = self._detect_anomalies(extracted, vector_memory)
        risk_score = self._score(extracted.amount, anomalies)

        has_high_severity_anomaly = any(a.severity == "high" for a in anomalies)
        auto_approved = (
            extracted.amount is not None
            and extracted.amount <= self._threshold
            and not has_high_severity_anomaly
        )

        return RiskAssessment(
            risk_score=risk_score,
            auto_approved=auto_approved,
            anomalies=anomalies,
            threshold=self._threshold,
        )

    def _detect_anomalies(self, extracted: ExtractedInvoiceData, vector_memory: VectorMemory) -> list[Anomaly]:
        anomalies: list[Anomaly] = []

        if not extracted.vendor:
            anomalies.append(
                Anomaly(code="missing_vendor", detail="No vendor name could be extracted from the invoice text.", severity="high")
            )
        if not extracted.po_number:
            anomalies.append(
                Anomaly(
                    code="missing_po_number",
                    detail="No purchase order number could be extracted from the invoice text.",
                    severity="medium",
                )
            )
        if extracted.amount is None:
            anomalies.append(
                Anomaly(code="missing_amount", detail="No invoice amount could be extracted from the invoice text.", severity="high")
            )
        elif extracted.amount > self._threshold * 10:
            anomalies.append(
                Anomaly(
                    code="unusually_high_amount",
                    detail=f"Amount ${extracted.amount:,.2f} is more than 10x the auto-approval threshold of ${self._threshold:,.2f}.",
                    severity="high",
                )
            )

        if extracted.vendor or extracted.po_number:
            for match in vector_memory.find_similar(extracted.vendor, extracted.po_number, extracted.amount):
                if match["similarity"] >= self._duplicate_threshold:
                    anomalies.append(
                        Anomaly(
                            code="possible_duplicate_invoice",
                            detail=(
                                f"{match['similarity']:.0%} similar to a previously processed invoice "
                                f"(workflow {match['workflow_id']})."
                            ),
                            severity="high",
                        )
                    )

        return anomalies

    def _score(self, amount: float | None, anomalies: list[Anomaly]) -> float:
        if amount is None:
            base = 60.0
        elif self._threshold > 0:
            base = min(70.0, (amount / self._threshold) * 35.0)
        else:
            base = 70.0

        penalty = sum(_SEVERITY_PENALTY[a.severity] for a in anomalies)
        return round(min(100.0, base + penalty), 2)
