"""
iter283-vehicle-bp-zero — Vehicles never carry a buyer premium.

Bug:
  The vehicle detail page's `<PricingCalculator />` was rendering a
  tier-based buyer premium (Standard 5% / Premium 3.5% / VIP Elite 3%)
  per `subscriptionTier`. Vehicles operate on the **Unlock Fee** model:
  the buyer pays a flat 2.5% **PLATFORM FEE** to BidVex, taxes apply
  ONLY to that platform fee, and the hammer price is paid directly to
  the seller out-of-band. There is no buyer premium.

  This pin guards against three regression vectors:

  1. The local breakdown calculator (`calculateLocalBreakdown`) no
     longer reads `subscriptionTier` for the BP rate — always 0%.
  2. The tax base is the **platform fee** (NOT the hammer-inclusive
     subtotal). Quebec compliance: tax on the FEE only.
  3. The "Buyer Premium by Tier" matrix, the "Subscription Savings"
     upsell, and the "Your Rate (5%/3.5%/3%)" badge are removed.
     Surfacing them implied vehicle pricing depended on subscription
     tier — it does not.

  Backend `services/fee_calculator.py` already returns the correct
  shape via the `vehicle_dealer` route (2.5% platform fee with
  `buyer_premium_rate=0.025`), labeled "Platform Fee" — not "Buyer
  Premium" — on the CostBreakdown rendering surface. This file pins
  the frontend behaviour so future refactors can't re-introduce the
  tier-based premium.
"""
from __future__ import annotations

import os
import re


def _read_fe(rel: str) -> str:
    base = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src")
    )
    with open(os.path.join(base, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    src = re.sub(r"//[^\n]*", "", src)
    return src


# ── PricingCalculator local breakdown ────────────────────────────────


def test_vehicle_calculator_clamps_bp_to_zero():
    """`calculateLocalBreakdown` MUST set bpRate = 0 unconditionally."""
    src = _read_fe("components/vehicles/PricingCalculator.js")
    idx = src.find("calculateLocalBreakdown")
    assert idx > 0
    block = src[idx:idx + 2200]
    # bpRate is hard-coded to 0 (not reading the tier rate).
    assert "const bpRate = 0" in block
    assert "const buyerPremium = 0" in block
    # Defensive: the tier-table read for bpRate is gone from this
    # function body.
    assert "listingBpPercent !== null" not in block, (
        "regression: PricingCalculator is reading a per-listing BP "
        "override for vehicles. Vehicles must always be 0% BP."
    )


def test_vehicle_calculator_taxes_only_the_platform_fee():
    """Tax base = platform fee (NOT hammer + premium + fee). The
    hammer is paid directly to the seller out-of-band; no provincial
    sales tax applies."""
    src = _read_fe("components/vehicles/PricingCalculator.js")
    idx = src.find("calculateLocalBreakdown")
    assert idx > 0
    block = src[idx:idx + 2200]
    assert "const taxBase = platformFee;" in block
    # And every tax-line computation uses taxBase, NOT subtotal.
    for tax_line in (
        "taxes.hst = (taxBase",
        "taxes.gst = (taxBase",
        "taxes.pst = (taxBase",
        "taxes.qst = (taxBase",
    ):
        assert tax_line in block, (
            f"regression: {tax_line!r} not using taxBase — vehicle tax "
            "is being computed on the hammer-inclusive subtotal."
        )


# ── PricingCalculator UI hygiene ─────────────────────────────────────


def test_vehicle_calculator_hides_tier_matrix():
    """`<FeeTierComparison>` (Buyer Premium by Tier matrix) MUST NOT
    render in the vehicle PricingCalculator. Showing a tier matrix
    on a 0% product creates a false impression of upsell value."""
    src = _read_fe("components/vehicles/PricingCalculator.js")
    code = _strip_comments(src)
    assert "<FeeTierComparison" not in code, (
        "regression: FeeTierComparison rendered in vehicle calculator"
    )
    # The label "Buyer Premium by Tier" is also gone.
    assert "Buyer Premium by Tier" not in code


def test_vehicle_calculator_hides_subscription_savings():
    """`<SavingsDisplay>` is a no-op for vehicles (always returns null)
    because vehicles have no buyer premium to discount."""
    src = _read_fe("components/vehicles/PricingCalculator.js")
    idx = src.find("export const SavingsDisplay")
    assert idx > 0
    block = src[idx:idx + 800]
    # The active component returns null immediately.
    assert "return null;" in block
    # The legacy logic was preserved under a `_UNUSED_` prefix for
    # historical reference but MUST NOT be exported.
    assert "_UNUSED_SavingsDisplay_legacy" in src
    # It's a const declaration, not an export.
    assert "export const _UNUSED_SavingsDisplay_legacy" not in src


def test_vehicle_calculator_hides_your_rate_badge():
    """`Your Rate (Standard 5% / Premium 3.5% / VIP Elite 3%)` badge
    is removed — the rate value DOES NOT APPLY to vehicles."""
    src = _read_fe("components/vehicles/PricingCalculator.js")
    code = _strip_comments(src)
    assert "VIP Elite (3%)" not in code
    assert "Premium (3.5%)" not in code
    assert "Standard (5%)" not in code


def test_vehicle_calculator_hides_buyer_premium_row_when_zero():
    """The Buyer Premium row in the breakdown table renders only
    when amount > 0 (which is never the case for vehicles after the
    clamp). A `$0.00 Buyer Premium` row is misleading."""
    src = _read_fe("components/vehicles/PricingCalculator.js")
    assert "breakdown.buyer_premium?.amount > 0" in src


# ── CostBreakdown (shared) — keep 2.5% Platform Fee label ─────────────


def test_cost_breakdown_labels_2pct5_as_platform_fee():
    """For `vehicle_dealer` accounts, the 2.5% fee MUST render with
    the label "Platform Fee" — never "Buyer's Premium". Keeps the
    semantic distinction explicit for buyers and accountants."""
    src = _read_fe("components/CostBreakdown.jsx")
    assert "Platform Fee" in src
    assert "Frais de plateforme" in src
    assert "accountKind === 'vehicle_dealer'" in src


def test_cost_breakdown_hides_zero_buyer_premium_row():
    """Storage-facility cash route has 0 buyer premium — the row
    must NOT render at all (a "$0.00" line is misleading)."""
    src = _read_fe("components/CostBreakdown.jsx")
    assert "buyerPremium > 0 &&" in src
    # The label code path remains, but the wrapping `{cond &&}`
    # short-circuits when value is 0.


# ── Backend contract preservation (vehicle_dealer route) ─────────────


def test_backend_vehicle_dealer_route_uses_2pct5():
    """`services/fee_calculator.py::vehicle_dealer` route MUST use
    `VEHICLE_DEALER_BUYER_RATE = 0.025`. Spec-pin so future agents
    don't accidentally re-introduce a tier-based BP."""
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    with open(os.path.join(base, "services", "fee_calculator.py"), "r") as fh:
        src = fh.read()
    # The constant is defined.
    assert "VEHICLE_DEALER_BUYER_RATE" in src
    # The vehicle_dealer route assigns BOTH rate and premium from it
    # (no tier table read).
    assert 'elif seller_type == "vehicle_dealer":' in src
    idx = src.find('elif seller_type == "vehicle_dealer":')
    block = src[idx:idx + 800]
    assert "buyer_premium_rate = VEHICLE_DEALER_BUYER_RATE" in block
    assert "buyer_premium = hammer * VEHICLE_DEALER_BUYER_RATE" in block
    # No tier-table lookup inside this branch.
    assert "INDIVIDUAL_BUYER_RATES" not in block
    assert "buyer_tier_norm" not in block
