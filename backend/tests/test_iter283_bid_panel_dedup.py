"""
iter283-bid-panel-dedup — Vehicle bid panel must render ONE breakdown.

Bug (CRITICAL):
  The vehicle detail page was rendering THREE stacked cost breakdowns
  in the bid panel:
    1. <VehicleAcquisitionCost />  (correct — unlock-fee model)
    2. <PricingEstimate />          (duplicate — server-side estimate)
    3. <CostBreakdown />            (WRONG MATH — compounds tax on the
                                     full hammer price; not the
                                     unlock-fee model)

  This broke payment transparency: a buyer would see "$771.29 unlock
  fee total" right above "Total Charged: $28,076.22" — two completely
  different mathematical models for the same bid.

Fix:
  Removed `<PricingEstimate>` + `<CostBreakdown>` from the bid panel.
  `<VehicleAcquisitionCost>` remains as the SINGLE source of truth
  during bidding. The full invoice (`CostBreakdown`) still ships on
  the post-win Checkout / Invoice surfaces where the hammer-price-
  inclusive total is legally accurate.

This file pins:
  • Only `<VehicleAcquisitionCost />` renders in the bid panel.
  • `<CostBreakdown />` / `<PricingEstimate />` are NOT rendered while
    bidding.
  • The `calculateAcquisitionCost` math matches the CEO spec for the
    canonical $26,500 QC scenario:
       base_fee   = $662.50  (2.5% of bid)
       tax_on_fee = $99.21   (14.975% of base_fee)
       total ≈ $784.77       (gross-up for $0.30 + 2.9% Stripe fee)
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


# ── Bid panel renders ONE breakdown ──────────────────────────────────


def _strip_comments(src: str) -> str:
    """Strip JS // and /* */ comments so we only test live code."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def test_bid_panel_renders_vehicle_acquisition_cost():
    """The canonical unlock-fee breakdown MUST still render in the bid panel."""
    src = _read_fe("pages/vehicles/VehicleDetailPage.js")
    assert "<VehicleAcquisitionCost" in src


def test_bid_panel_does_not_render_cost_breakdown():
    """The invoice-shape `<CostBreakdown>` MUST NOT render in the bid
    panel — its math conflicts with `VehicleAcquisitionCost` and
    rendering both breaks payment transparency. The full invoice
    still ships on the post-win Checkout / Invoice page."""
    src = _read_fe("pages/vehicles/VehicleDetailPage.js")
    code = _strip_comments(src)
    assert "<CostBreakdown" not in code, (
        "regression: <CostBreakdown /> JSX rendered in the bid panel — "
        "this stacks a hammer-price-inclusive invoice ON TOP of the "
        "unlock-fee breakdown, producing two conflicting totals."
    )


def test_bid_panel_does_not_render_pricing_estimate():
    """`<PricingEstimate>` was the third stacked breakdown — also
    out of the bid panel per dedup spec."""
    src = _read_fe("pages/vehicles/VehicleDetailPage.js")
    code = _strip_comments(src)
    assert "<PricingEstimate" not in code, (
        "regression: <PricingEstimate /> JSX rendered in the bid panel"
    )


def test_cost_breakdown_still_exists_for_checkout():
    """`CostBreakdown` itself must NOT be deleted — it's still used on
    post-win Checkout / Invoice surfaces. The dedup is scoped to the
    bid panel only."""
    base = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src")
    )
    expected = os.path.join(base, "components", "CostBreakdown.jsx")
    assert os.path.exists(expected), (
        "CostBreakdown.jsx was deleted — that breaks the post-win "
        "Checkout invoice. Dedup must be scoped to the bid panel only."
    )


# ── calculateAcquisitionCost math (canonical $26,500 QC scenario) ───


def test_acquisition_cost_math_base_fee_25pct():
    """`base_fee = bid * 0.025`. For a $26,500 bid → $662.50."""
    src = _read_fe("components/vehicles/VehicleDetailPieces.js")
    assert "b * 0.025" in src, (
        "platform fee no longer 2.5% — buyer pricing contract broken"
    )


def test_acquisition_cost_math_qc_rate():
    """QC combined tax rate on fee MUST be 0.14975 (GST 5% + QST 9.975%)."""
    src = _read_fe("components/vehicles/VehicleDetailPieces.js")
    assert "QC: 0.14975" in src, (
        "QC tax rate on platform fee changed — Quebec compliance broken"
    )


def test_acquisition_cost_math_stripe_grossup():
    """The gross-up formula MUST be `(subtotal + 0.30) / (1 - 0.029)`
    so the BUYER sees exactly what Stripe will charge them after the
    2.9% + $0.30 processing skim."""
    src = _read_fe("components/vehicles/VehicleDetailPieces.js")
    assert "(subtotal + 0.30) / (1 - 0.029)" in src
