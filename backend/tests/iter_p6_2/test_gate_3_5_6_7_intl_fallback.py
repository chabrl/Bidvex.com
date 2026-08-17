"""P6.2 Gates 3 / 5 / 6 / 7 — US/INTL/missing province fail-closed regression tests."""
from __future__ import annotations

import sys
from decimal import Decimal

import pytest

sys.path.insert(0, "/app/backend")

from services.invoice_service import calculate_province_tax  # noqa: E402
from services.vehicle_pricing import calculate_taxes as vp_calculate_taxes  # noqa: E402
from services.fee_calculator import calculate_partner_taxes  # noqa: E402
from routes.tax_dashboard import compute_tax_for_transaction  # noqa: E402


UNKNOWN_INPUTS = ["", None, "US", "USA", "INTERNATIONAL", "OUTSIDE CANADA",
                  "ZZ", "XX", "unknown"]


# ── Gate 3: invoice_service ─────────────────────────────────────────
@pytest.mark.parametrize("bad_prov", UNKNOWN_INPUTS)
def test_invoice_service_unknown_fails_to_intl_zero(bad_prov):
    """Missing / US / INTL / unknown must NOT silently over-collect QC."""
    if bad_prov is None:
        r = calculate_province_tax(100.0)
    else:
        r = calculate_province_tax(100.0, buyer_province=bad_prov)
    assert r.province == "INTL", r
    assert r.tax_type == "zero_rated", r
    assert r.total_tax == 0.0, r
    assert r.line_items == [], r


def test_invoice_service_canadian_still_works():
    r = calculate_province_tax(100.0, buyer_province="ON")
    assert r.province == "ON"
    assert Decimal(str(r.total_tax)) == Decimal("13.00")


# ── Gate 5: vehicle_pricing ─────────────────────────────────────────
@pytest.mark.parametrize("bad_prov", UNKNOWN_INPUTS)
def test_vehicle_pricing_unknown_fails_to_intl_zero(bad_prov):
    """Vehicle pricing must zero-rate US/INTL/unknown (was Alberta 5% fallback)."""
    r = vp_calculate_taxes(Decimal("100"), bad_prov or "")
    assert r.tax_type == "Exported Service", r
    assert r.total_tax == Decimal("0"), r


def test_vehicle_pricing_ns_is_14_percent():
    r = vp_calculate_taxes(Decimal("100"), "NS")
    assert r.tax_type == "HST"
    assert r.hst_amount == Decimal("14.00")
    assert r.total_tax == Decimal("14.00")


# ── Gate 6: fee_calculator.calculate_partner_taxes ──────────────────
@pytest.mark.parametrize("bad_prov", ["", "US", "USA", "ZZ", "INTL"])
def test_calculate_partner_taxes_unknown_returns_zero(bad_prov):
    r = calculate_partner_taxes(Decimal("100"), bad_prov)
    assert r["province"] == "INTL"
    assert r["total"] == Decimal("0.00")
    assert r["combined_rate"] == Decimal("0")


def test_calculate_partner_taxes_ns_is_14_percent():
    r = calculate_partner_taxes(Decimal("100"), "NS")
    assert r["province"] == "NS"
    assert r["hst"] == Decimal("14.00")
    assert r["total"] == Decimal("14.00")


# ── Gate 7: tax_dashboard.compute_tax_for_transaction ───────────────
@pytest.mark.parametrize("bad_region", ["", None, "US", "USA", "INTL", "INTERNATIONAL"])
def test_tax_dashboard_unknown_returns_zero(bad_region):
    tx = {"platform_fee": 100.0, "buyer_premium": 0.0}
    if bad_region is not None:
        tx["seller_region"] = bad_region
    r = compute_tax_for_transaction(tx)
    assert r["region"] == "INTL"
    assert r["total_tax"] == 0.0


def test_tax_dashboard_ns_is_14_percent():
    tx = {"platform_fee": 100.0, "buyer_premium": 0.0, "seller_region": "NS"}
    r = compute_tax_for_transaction(tx)
    assert r["region"] == "NS"
    assert r["hst"] == 14.0
    assert r["total_tax"] == 14.0


def test_tax_dashboard_bc_is_gst_only():
    tx = {"platform_fee": 100.0, "buyer_premium": 0.0, "seller_region": "BC"}
    r = compute_tax_for_transaction(tx)
    assert r["region"] == "BC"
    assert r["gst"] == 5.0
    assert r["qst"] == 0.0
    assert r["hst"] == 0.0
    assert r["total_tax"] == 5.0
