"""P6.2 Gate 2 — BC/SK/MB PST/RST reconciliation regression tests.

Per P6.1.1 confirmed policy: BidVex does NOT collect BC PST (7%),
SK PST (6%), or MB RST (7%) on platform B2B service supplies. The
provincial obligation lies with the seller. `invoice_service.py`
must therefore emit GST-only for BC/SK/MB (not "dual" with PST/RST).
"""
from __future__ import annotations

import sys
from decimal import Decimal

import pytest

sys.path.insert(0, "/app/backend")

from services.invoice_service import (  # noqa: E402
    calculate_province_tax,
    PROVINCE_TAX_CONFIG,
)

# (amount, expected_total_tax) — 5% GST only on BidVex platform fees
GST_ONLY_GRID = [
    (Decimal("0.01"), Decimal("0.00")),
    (Decimal("1"),    Decimal("0.05")),
    (Decimal("100"),  Decimal("5.00")),
    (Decimal("1000"), Decimal("50.00")),
    (Decimal("500000"), Decimal("25000.00")),
]


@pytest.mark.parametrize("prov", ["BC", "SK", "MB"])
def test_province_config_is_gst_only(prov):
    cfg = PROVINCE_TAX_CONFIG[prov]
    assert cfg["type"] == "gst_only", (prov, cfg)
    assert Decimal(str(cfg["gst_rate"])) == Decimal("0.05")
    # Legacy dual keys must not linger
    assert "pst_rate" not in cfg
    assert "pst_label_en" not in cfg


@pytest.mark.parametrize("prov", ["BC", "SK", "MB"])
@pytest.mark.parametrize("amount,expected", GST_ONLY_GRID)
def test_calculate_province_tax_gst_only_for_bc_sk_mb(prov, amount, expected):
    r = calculate_province_tax(float(amount), buyer_province=prov)
    assert r.tax_type == "gst_only"
    assert Decimal(str(r.tax_gst)) == expected
    assert Decimal(str(r.tax_pst_qst)) == Decimal("0.00")
    assert Decimal(str(r.tax_hst)) == Decimal("0.00")
    assert Decimal(str(r.total_tax)) == expected


def test_qc_still_collects_gst_qst():
    """QC remains dual (5% GST + 9.975% QST) — BidVex is QC-registered."""
    r = calculate_province_tax(100.0, buyer_province="QC")
    assert r.tax_type == "dual"
    assert Decimal(str(r.tax_gst)) == Decimal("5.00")
    assert Decimal(str(r.tax_pst_qst)) == Decimal("9.98")
    assert Decimal(str(r.total_tax)) == Decimal("14.98")


def test_ns_uses_14_percent_hst():
    """NS = 14% HST per CRA Notice 342 (also covered by Gate 1)."""
    r = calculate_province_tax(100.0, buyer_province="NS")
    assert r.tax_type == "hst"
    assert Decimal(str(r.tax_hst)) == Decimal("14.00")
    assert Decimal(str(r.total_tax)) == Decimal("14.00")


def test_line_items_bc_no_pst_row():
    """Line items must NOT contain a PST/RST row for BC/SK/MB — the
    over-collection was in the total (dual added PST), and would leak
    to the invoice PDF's totals section otherwise."""
    r = calculate_province_tax(100.0, buyer_province="BC")
    labels = [li["label"] for li in r.line_items]
    assert any("GST" in lbl for lbl in labels), r.line_items
    assert not any("PST" in lbl or "RST" in lbl for lbl in labels), r.line_items
