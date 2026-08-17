"""P6.2 Gate 9 — Golden Matrix Regression Tests.

Implements the 600-cell specification from
`/app/backend/tests/iter496_2/golden_matrix_spec.md`.

Reference expectation for each cell:
    federal = amount × REFERENCE_FEDERAL[prov]         (rounded 2dp)
    qst     = amount × 0.09975 if prov == "QC" else 0  (rounded 2dp)
    total   = federal + qst

BidVex does NOT collect BC PST / SK PST / MB RST on B2B platform
supplies per the P6.1.1 confirmed policy.

Any calculator whose result differs from the reference on a cell
must be listed in `APPROVED_DELTAS` with a written reason. All other
divergences fail the test.
"""
from __future__ import annotations

import sys
from decimal import Decimal, ROUND_HALF_UP

import pytest

sys.path.insert(0, "/app/backend")

from services.tax_engine import (  # noqa: E402
    calculate_taxes_for_recipient,
)
from services.vehicle_pricing import calculate_taxes as vp_calculate_taxes  # noqa: E402
from services.fee_calculator import (  # noqa: E402
    tax_on,
    calculate_partner_taxes,
)
from services.invoice_service import calculate_province_tax  # noqa: E402
from routes.tax_dashboard import compute_tax_for_transaction  # noqa: E402


# ── Confirmed reference (per P6.1.1 §11 + operator policy) ─────────
REFERENCE_FEDERAL: dict[str, Decimal] = {
    "AB": Decimal("0.05"), "BC": Decimal("0.05"), "MB": Decimal("0.05"),
    "NB": Decimal("0.15"), "NL": Decimal("0.15"), "NS": Decimal("0.14"),
    "NT": Decimal("0.05"), "NU": Decimal("0.05"), "ON": Decimal("0.13"),
    "PE": Decimal("0.15"), "QC": Decimal("0.05"), "SK": Decimal("0.05"),
    "YT": Decimal("0.05"), "US": Decimal("0.00"), "INTL": Decimal("0.00"),
}
QC_QST_RATE = Decimal("0.09975")

PROVINCES = ["QC", "ON", "AB", "BC", "MB", "SK", "NB", "NL", "NS", "PE",
             "YT", "NT", "NU", "US", "INTL"]
AMOUNTS = [Decimal("0.01"), Decimal("1"), Decimal("100"),
           Decimal("1000"), Decimal("500000")]


def _q(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def expected_total_bidvex_tax(prov: str, amount: Decimal) -> Decimal:
    fed = REFERENCE_FEDERAL.get(prov.upper(), Decimal("0"))
    fed_amt = _q(amount * fed)
    qst_amt = _q(amount * QC_QST_RATE) if prov.upper() == "QC" else Decimal("0")
    return fed_amt + qst_amt


# ── Calculators under test (only the province-aware ones) ──────────
# Note: `tax_engine.calculate_tax` and `calculate_gst_qst` are Gate 4
# QC-only preview helpers by design and are NOT in the golden matrix.
CALCULATORS = {
    "tax_engine.calculate_taxes_for_recipient": (
        lambda amt, prov: Decimal(str(calculate_taxes_for_recipient(float(amt), prov)["total_tax"]))
    ),
    "vehicle_pricing.calculate_taxes": (
        lambda amt, prov: Decimal(str(vp_calculate_taxes(amt, prov).total_tax))
    ),
    "fee_calculator.tax_on": (
        lambda amt, prov: Decimal(str(tax_on(amt, prov)["total"]))
    ),
    "fee_calculator.calculate_partner_taxes": (
        lambda amt, prov: Decimal(str(calculate_partner_taxes(amt, prov)["total"]))
    ),
    "invoice_service.calculate_province_tax": (
        lambda amt, prov: Decimal(str(calculate_province_tax(float(amt), prov).total_tax))
    ),
    "tax_dashboard.compute_tax_for_transaction": (
        lambda amt, prov: Decimal(str(compute_tax_for_transaction({
            "platform_fee": float(amt), "buyer_premium": 0, "seller_region": prov,
        })["total_tax"]))
    ),
}


# ── Approved deltas — cells where actual output intentionally
# differs from the pure federal+QC-QST reference. Empty as of P6.2.
APPROVED_DELTAS: dict[tuple[str, str, str], Decimal] = {
    # (calculator, province, amount) → approved delta from reference
}


@pytest.mark.parametrize("calc_name", sorted(CALCULATORS.keys()))
@pytest.mark.parametrize("prov", PROVINCES)
@pytest.mark.parametrize("amount", AMOUNTS)
def test_golden_matrix(calc_name, prov, amount):
    fn = CALCULATORS[calc_name]
    actual = fn(amount, prov)
    expected = expected_total_bidvex_tax(prov, amount)
    delta_key = (calc_name, prov, str(amount))
    if delta_key in APPROVED_DELTAS:
        # Explicit intentional delta
        expected = expected + APPROVED_DELTAS[delta_key]
    assert _q(actual) == _q(expected), (
        f"Golden-matrix mismatch on {calc_name} × {prov} × ${amount}: "
        f"actual={actual} expected={expected}"
    )
