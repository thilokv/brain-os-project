"""Unit tests for Facility 2 (Document Intelligence) and Facility 4 (Risk Engine)."""

from __future__ import annotations

from app.database.vector_store import VectorMemory
from app.services.document_intelligence import DocumentIntelligenceService
from app.services.risk_engine import RiskEngine


def test_extracts_vendor_po_and_amount():
    extracted = DocumentIntelligenceService().extract("Vendor: Acme Logistics\nPO Number: PO-1001\nAmount: $7500")
    assert extracted.vendor == "Acme Logistics"
    assert extracted.po_number == "PO-1001"
    assert extracted.amount == 7500.0


def test_extracts_amount_with_commas_and_decimals():
    extracted = DocumentIntelligenceService().extract("Vendor: X\nPO Number: PO-2\nAmount: $12,345.67")
    assert extracted.amount == 12345.67


def test_amount_at_or_below_threshold_auto_approves(tmp_path):
    vm = VectorMemory(str(tmp_path / "chroma"), "invoices")
    engine = RiskEngine(auto_approve_threshold=5000.0, duplicate_similarity_threshold=0.92)
    extracted = DocumentIntelligenceService().extract("Vendor: X\nPO Number: PO-1\nAmount: $5000")
    risk = engine.assess(extracted, vm)
    assert risk.auto_approved is True
    assert risk.anomalies == []


def test_amount_above_threshold_requires_approval(tmp_path):
    vm = VectorMemory(str(tmp_path / "chroma"), "invoices")
    engine = RiskEngine(auto_approve_threshold=5000.0, duplicate_similarity_threshold=0.92)
    extracted = DocumentIntelligenceService().extract("Vendor: X\nPO Number: PO-1\nAmount: $5000.01")
    risk = engine.assess(extracted, vm)
    assert risk.auto_approved is False


def test_duplicate_invoice_is_flagged_as_high_severity_anomaly(tmp_path):
    vm = VectorMemory(str(tmp_path / "chroma"), "invoices")
    engine = RiskEngine(auto_approve_threshold=5000.0, duplicate_similarity_threshold=0.92)
    extracted = DocumentIntelligenceService().extract("Vendor: Acme\nPO Number: PO-1\nAmount: $100")

    engine.assess(extracted, vm)
    vm.remember("wf-1", extracted.vendor, extracted.po_number, extracted.amount)

    second = engine.assess(extracted, vm)
    codes = {a.code for a in second.anomalies}
    assert "possible_duplicate_invoice" in codes
    # A high-severity anomaly overrides what would otherwise be an auto-approve amount.
    assert second.auto_approved is False


def test_missing_amount_is_flagged_and_blocks_auto_approval(tmp_path):
    vm = VectorMemory(str(tmp_path / "chroma"), "invoices")
    engine = RiskEngine(auto_approve_threshold=5000.0, duplicate_similarity_threshold=0.92)
    extracted = DocumentIntelligenceService().extract("Vendor: X\nPO Number: PO-1\nno amount here")
    risk = engine.assess(extracted, vm)
    assert any(a.code == "missing_amount" for a in risk.anomalies)
    assert risk.auto_approved is False
