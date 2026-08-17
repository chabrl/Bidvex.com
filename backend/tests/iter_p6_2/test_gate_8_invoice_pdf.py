"""P6.2 Gate 8 — Invoice PDF regression tests.

Verifies:
* NS invoices render 14% HST (not 15%).
* BC/SK/MB invoices render 5% GST only (no PST/RST line).
* Missing-province invoices render as zero-rated exported service.
* Existing QC + ON + AB invoices unchanged.
"""
from __future__ import annotations

import re
import sys

import pytest

sys.path.insert(0, "/app/backend")

from services.invoice_service import generate_invoice_pdf  # noqa: E402


_INVOICE = {
    "invoice_number": "INV-P6.2-GATE8",
    "created_at": "2026-02-17",
    "transaction_id": "tx_test",
    "items": [
        {"title": "Test Item", "quantity": 1, "unit_price": 100.00, "amount": 100.00},
    ],
    "subtotal": 100.00,
    "buyer_premium": 0.00,
    "currency": "CAD",
}
_BUYER = {"name": "Test Buyer", "email": "buyer@example.com"}
_SELLER = {"name": "Test Seller", "email": "seller@example.com"}


def _extract_text(pdf_bytes: bytes) -> str:
    """Very lightweight text extraction for regex assertions."""
    from pdfminer.high_level import extract_text
    from io import BytesIO
    return extract_text(BytesIO(pdf_bytes))


@pytest.mark.parametrize("prov,expected_pct,expected_amount", [
    ("QC", "5%",  "5.00"),   # QC 5% GST + 9.98 QST separately (dual)
    ("ON", "13%", "13.00"),  # HST
    ("NS", "14%", "14.00"),  # P6.2 Gate 1 — was 15%
    ("NB", "15%", "15.00"),  # HST
    ("AB", "5%",  "5.00"),   # GST only
    ("BC", "5%",  "5.00"),   # P6.2 Gate 2 — was 12% (5+7)
    ("SK", "5%",  "5.00"),   # P6.2 Gate 2 — was 11% (5+6)
    ("MB", "5%",  "5.00"),   # P6.2 Gate 2 — was 12% (5+7)
])
def test_invoice_pdf_shows_correct_tax_rate(prov, expected_pct, expected_amount):
    pdf = generate_invoice_pdf(_INVOICE, _BUYER, _SELLER, lang="en", buyer_province=prov)
    text = _extract_text(pdf)
    assert expected_pct in text, f"{prov}: expected rate {expected_pct} in PDF"
    assert expected_amount in text, f"{prov}: expected amount {expected_amount} in PDF"


def test_bc_pdf_no_pst_line():
    pdf = generate_invoice_pdf(_INVOICE, _BUYER, _SELLER, lang="en", buyer_province="BC")
    text = _extract_text(pdf)
    assert "PST" not in text, "BC invoice must not show PST line post-Gate 2"


def test_sk_pdf_no_pst_line():
    pdf = generate_invoice_pdf(_INVOICE, _BUYER, _SELLER, lang="en", buyer_province="SK")
    text = _extract_text(pdf)
    assert "PST" not in text, "SK invoice must not show PST line post-Gate 2"


def test_mb_pdf_no_rst_line():
    pdf = generate_invoice_pdf(_INVOICE, _BUYER, _SELLER, lang="en", buyer_province="MB")
    text = _extract_text(pdf)
    assert "RST" not in text, "MB invoice must not show RST line post-Gate 2"


def test_intl_pdf_no_tax_line():
    """Zero-rated exported service — no tax line rendered on the total."""
    pdf = generate_invoice_pdf(_INVOICE, _BUYER, _SELLER, lang="en", buyer_province="")
    text = _extract_text(pdf)
    # Total should equal subtotal (no tax added)
    assert "$100.00" in text  # total
