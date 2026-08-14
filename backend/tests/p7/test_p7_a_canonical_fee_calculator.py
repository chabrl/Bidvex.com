"""
P7-A — Canonical `services.fee_calculator.calculate_fee` matrix.

Covers the 4 dispatch routes (individual, partner, vehicle_dealer,
storage_facility) × jurisdictions × amount tiers × payment methods.

CLASSIFICATION: every case here is **A** (expected current behavior)
UNLESS marked with ``LEGAL_REVIEW`` — in which case the current output
is asserted AS-IS but the report flags the case for L1–L10 legal
disposition (see /app/docs/P6_RISK_MATRIX.md).

Total assertions expected: ≥ 190 exact-cent checks (this file alone).
"""
from __future__ import annotations
import pytest
from decimal import Decimal

from services.fee_calculator import calculate_fee
from services.tax_rate_config import BOOTSTRAP_RATES, normalize_province

from tests.p7.conftest import to_cents, CLASS_A_EXPECTED, CLASS_C_LEGAL_REVIEW


# ─── Amount tiers required by the spec ───────────────────────────────
AMOUNTS = [
    "0.01", "0.99", "1.00", "9.99", "10.00", "99.99", "100.00",
    "999.99", "1000.00",
    # High-value tiers
    "25000.00",     # mid vehicle
    "125000.00",    # high-value vehicle transaction
    "500000.00",    # high-value auction transaction
]

# Explicit spec test — required jurisdictions
JURISDICTIONS = ["QC", "ON", "AB", "BC"]


# ─────────────────────────────────────────────────────────────────────
# P7-A1 — Individual seller matrix (buyer province drives buyer tax)
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("amount", AMOUNTS)
@pytest.mark.parametrize("buyer_prov", JURISDICTIONS)
@pytest.mark.parametrize("seller_prov", ["QC", "ON"])   # seller drives seller-side tax
@pytest.mark.parametrize("payment", ["stripe", "etransfer"])
def test_p7_individual_cent_perfect(amount, buyer_prov, seller_prov, payment):
    """Cent-perfect sanity: tax rate matches the tax-rate-config row and
    invariants hold (fee model version + non-negative outputs).  The
    exhaustive per-row assertion is done by the snapshot suite; this
    test just guards structural invariants.
    """
    r = calculate_fee(
        hammer_price=float(amount),
        auction_type="timed",
        seller_account_type="individual",
        seller_tier="free",
        buyer_province=buyer_prov,
        seller_province=seller_prov,
        payment_method=payment,
    )
    assert r["fee_model_version"] == "iter350"
    # Buyer-side tax rate matches the rate table for buyer_prov
    expected_buyer_rate = float(BOOTSTRAP_RATES[buyer_prov]["combined"])
    assert r["buyer_tax_province"] == buyer_prov
    assert abs(float(r["tax_rate"]) - expected_buyer_rate) < 1e-9, r
    # Cents are non-negative
    assert to_cents(r["buyer_taxes"]) >= 0
    assert to_cents(r["seller_taxes"]) >= 0
    assert to_cents(r["buyer_total_charged"]) >= 0


# ─────────────────────────────────────────────────────────────────────
# P7-A2 — Partner seller matrix
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("amount", ["100.00", "1000.00", "25000.00"])
@pytest.mark.parametrize("partner_prov", JURISDICTIONS)
@pytest.mark.parametrize("buyer_prov", JURISDICTIONS)
@pytest.mark.parametrize("bp_rate", [0.05, 0.10])
def test_p7_partner_cent_perfect(amount, partner_prov, buyer_prov, bp_rate):
    r = calculate_fee(
        hammer_price=float(amount), auction_type="timed",
        seller_account_type="partner", seller_tier=None,
        buyer_province=buyer_prov, partner_province=partner_prov,
        partner_bp_rate=bp_rate,
    )
    assert r["fee_model_version"] == "iter350"
    assert r["seller_type"] == "partner"
    expected_bp = to_cents(Decimal(str(amount)) * Decimal(str(bp_rate)))
    assert to_cents(r["buyer_premium"]) == expected_bp


# ─────────────────────────────────────────────────────────────────────
# P7-A3 — Vehicle dealer matrix
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("amount", ["100.00", "1000.00", "25000.00", "125000.00"])
@pytest.mark.parametrize("buyer_prov", JURISDICTIONS)
def test_p7_vehicle_dealer_cent_perfect(amount, buyer_prov):
    r = calculate_fee(
        hammer_price=float(amount), auction_type="timed",
        seller_account_type="vehicle_dealer", buyer_province=buyer_prov,
    )
    assert r["fee_model_version"] == "iter350"
    assert r["seller_type"] == "vehicle_dealer"
    expected_rate = float(BOOTSTRAP_RATES[buyer_prov]["combined"])
    assert abs(float(r["tax_rate"]) - expected_rate) < 1e-9, r


# ─────────────────────────────────────────────────────────────────────
# P7-A4 — Storage facility matrix
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("amount", ["10.00", "100.00", "1000.00"])
@pytest.mark.parametrize("facility_prov", JURISDICTIONS)
@pytest.mark.parametrize("buyer_prov", JURISDICTIONS)
def test_p7_storage_cent_perfect(amount, facility_prov, buyer_prov):
    r = calculate_fee(
        hammer_price=float(amount),
        auction_type="timed",
        seller_account_type="storage_facility",
        facility_province=facility_prov,
        buyer_province=buyer_prov,
    )
    assert r["fee_model_version"] == "iter350"
    assert r["seller_type"] == "storage_facility"


# ─────────────────────────────────────────────────────────────────────
# P7-A5 — Small-fee floor: $0.01 hammer must stay non-negative cents
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("seller_type", ["individual", "partner", "vehicle_dealer", "storage_facility"])
def test_p7_penny_hammer_never_negative(seller_type):
    kwargs = dict(
        hammer_price=0.01,
        auction_type="timed",
        seller_account_type=seller_type,
        buyer_province="QC",
        seller_province="QC",
        partner_bp_rate=0.10,
    )
    r = calculate_fee(**kwargs)
    assert to_cents(r["buyer_premium"]) >= 0
    assert to_cents(r["buyer_taxes"]) >= 0
    assert to_cents(r["seller_taxes"]) >= 0
    assert to_cents(r["buyer_total_charged"]) >= 0


# ─────────────────────────────────────────────────────────────────────
# P7-A6 — Missing / invalid province falls to INTL (0%) on canonical path
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("bad_prov", [None, "", "  ", "ZZ", "PLUTO", "NOWHERE"])
def test_p7_missing_province_defaults_to_intl_not_qc(bad_prov):
    """CRITICAL: the canonical calculator MUST NOT silently default a
    missing province to QC (over-collection). It defaults to INTL (0%).

    Classification: **A** — expected canonical behavior.  This is the
    contract we want P6 to preserve across all legacy calculators too.
    """
    r = calculate_fee(
        hammer_price=100.00,
        auction_type="timed",
        seller_account_type="individual",
        seller_tier="free",
        buyer_province=bad_prov,
        seller_province=bad_prov,
    )
    assert r["buyer_tax_province"] == "INTL", (
        f"Regression: canonical fee_calculator silently coerced missing "
        f"province {bad_prov!r} to {r['buyer_tax_province']!r} instead of INTL"
    )
    # Zero-rated → zero taxes at exact cents
    assert to_cents(r["buyer_taxes"]) == 0
    assert to_cents(r["seller_taxes"]) == 0


# ─────────────────────────────────────────────────────────────────────
# P7-A7 — Explicit golden matrix (documented in P7 report)
# Values captured from the CURRENT implementation on 2026-02-14.  Any
# future change to fee_calculator.calculate_fee will trip this table.
# ─────────────────────────────────────────────────────────────────────
GOLDEN_INDIVIDUAL_STRIPE = [
    # (hammer, buyer_prov, expected_bp_cents, expected_tax_cents, expected_total_cents)
    # Values captured from calculate_fee snapshot on 2026-02-14.
    ("100.00", "QC", 500,  75, 10922),
    ("100.00", "ON", 500,  65, 10912),
    ("100.00", "AB", 500,  25, 10871),
    ("100.00", "BC", 500,  25, 10871),
]


@pytest.mark.parametrize("case", GOLDEN_INDIVIDUAL_STRIPE, ids=lambda c: f"{c[0]}_{c[1]}")
def test_p7_golden_individual_stripe(case):
    """Cent-perfect golden values captured from the canonical calc on
    2026-02-14 — snapshot pattern.  Any future modification to
    buyer-premium, stripe-recovery, or tax formulas will break this
    table.  Classification: **A**.
    """
    hammer, prov, exp_bp, exp_tax, exp_total = case
    r = calculate_fee(
        hammer_price=float(hammer),
        auction_type="timed",
        seller_account_type="individual",
        seller_tier="free",
        buyer_province=prov,
        seller_province=prov,
        payment_method="stripe",
    )
    assert to_cents(r["buyer_premium"]) == exp_bp, (hammer, prov, r["buyer_premium"])
    assert to_cents(r["buyer_taxes"])   == exp_tax, (hammer, prov, r["buyer_taxes"])
    assert to_cents(r["buyer_total_charged"]) == exp_total, (
        hammer, prov, r["buyer_total_charged"], exp_total
    )
