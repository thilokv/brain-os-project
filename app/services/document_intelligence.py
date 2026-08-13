"""Facility 2: Document Intelligence.

Parses raw invoice text (the `Vendor: ... / PO Number: ... / Amount: ...`
line format described in the intake spec) into structured fields. The
parser is deliberately deterministic rather than LLM-based: field
extraction from a fixed key/value layout does not need a model call, and
a deterministic parser is fully testable and has zero latency/cost.
"""

import re
from typing import Optional

from app.models.schemas import ExtractedInvoiceData

_VENDOR_PATTERN = re.compile(r"(?im)^\s*vendor\s*:\s*(.+?)\s*$")
_PO_PATTERN = re.compile(r"(?im)^\s*(?:po\s*number|po\s*#|purchase\s*order(?:\s*number)?|po)\s*:\s*(\S+)")
_AMOUNT_PATTERN = re.compile(r"(?im)^\s*amount\s*:\s*\$?\s*([\d,]+(?:\.\d{1,2})?)")


class DocumentIntelligenceService:
    """Extracts vendor, PO number, and amount from raw invoice text."""

    def extract(self, raw_text: str) -> ExtractedInvoiceData:
        vendor = self._match(_VENDOR_PATTERN, raw_text)
        po_number = self._match(_PO_PATTERN, raw_text)
        amount_text = self._match(_AMOUNT_PATTERN, raw_text)
        amount = float(amount_text.replace(",", "")) if amount_text else None
        return ExtractedInvoiceData(vendor=vendor, po_number=po_number, amount=amount, raw_text=raw_text)

    @staticmethod
    def _match(pattern: re.Pattern, text: str) -> Optional[str]:
        found = pattern.search(text)
        return found.group(1).strip() if found else None
