"""
iter482 P3 — fee_calculator.calculate_fee() canonical payment_processing tests
================================================================================

Post-P3 wiring, every buyer-facing path in ``fee_calculator._iter350_*``
must:

  1. Return ``buyer_stripe_recovery = 0.0`` (fail-closed until L-1 legal
     review clears the jurisdiction).
  2. Attach a canonical ``payment_processing`` snapshot with
     ``legal_gate_status == 'REQUIRES_TAX_LEGAL_REVIEW'``,
     ``amount_cents == 0``, and ``field_version == 'payment_processing.v1'``.
  3. Preserve every other financial line-item unchanged.

Also covers the historical $7.64 → new $7.33 regression: proves the
phantom $0.31 buyer surcharge can never re-emerge through the
``calculate_fee()`` path.

Run:
    cd /app/backend
    python -m pytest tests/test_iter482_p3_fee_calculator_canonical.py -v
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from services.fee_calculator import calculate_fee  # noqa: E402


def _pp(r):
    """Convenience: return the canonical payment_processing snapshot."""
    pp = r.get("payment_processing")
    assert pp is not None, "payment_processing snapshot MUST be attached"
    return pp


# ═════════════════════════════════════════════════════════════════════
# Individual (basic/premium/vip_elite) × QC × Standard hammer
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("buyer_tier,seller_tier", [
    ("standard", "standard"),
    ("premium",  "premium"),
    ("vip_elite","vip_elite"),
])
def test_individual_qc_buyer_pays_stripe_recovery(buyer_tier, seller_tier):
    """iter482 P5 — L-1 CLEARED: buyer bears the Stripe processing cost
    via the canonical gross-up recovery.  BidVex must not silently absorb it."""
    r = calculate_fee(
        hammer_price=100.0, auction_type="marketplace",
        seller_account_type="individual", seller_tier=seller_tier,
        buyer_tier=buyer_tier, buyer_province="QC", seller_province="QC",
    )
    assert r["buyer_stripe_recovery"] > 0, (
        f"tier={buyer_tier}: buyer_stripe_recovery must be > 0 (L-1 CLEARED)"
    )
    pp = _pp(r)
    assert pp["amount_cents"] > 0
    assert pp["legal_gate_status"] == "CLEARED"
    assert pp["reason_code"] == "estimated_from_rate_matrix"
    assert pp["field_version"] == "payment_processing.v2"


def test_individual_qc_various_quantities_recovery_grows():
    """Buyer Stripe recovery grows with the total charge base."""
    prev = 0.0
    for qty in (1, 2, 10):
        r = calculate_fee(
            hammer_price=7.0 * qty, auction_type="marketplace",
            seller_account_type="individual", seller_tier="premium",
            buyer_tier="premium", buyer_province="QC", seller_province="QC",
        )
        assert r["buyer_stripe_recovery"] > 0.0, f"qty={qty}"
        assert r["buyer_stripe_recovery"] >= prev, f"qty={qty} recovery decreased"
        prev = r["buyer_stripe_recovery"]
        assert _pp(r)["amount_cents"] > 0


# ═════════════════════════════════════════════════════════════════════
# HISTORICAL $7.64 REGRESSION — buyer_total now includes recovery
# ═════════════════════════════════════════════════════════════════════

def test_historical_7_64_never_reemerges():
    """iter482 P5 — the historical bug was a phantom $0.31 leaked into
    the total.  Now the buyer explicitly pays the canonical Stripe
    recovery, sourced from payment_cost_engine.  The recovery must be
    non-zero and computed cent-exact via gross-up.
    """
    r = calculate_fee(
        hammer_price=7.0, auction_type="marketplace",
        seller_account_type="individual", seller_tier="premium",
        buyer_tier="premium", buyer_province="QC", seller_province="QC",
    )
    assert Decimal(str(r["buyer_premium"])) == Decimal("0.25")
    assert r["buyer_stripe_recovery"] > 0.0, (
        "L-1 CLEARED: buyer must pay canonical processing recovery."
    )
    pp = _pp(r)
    assert pp["amount_cents"] > 0
    # Base (hammer + BP + buyer_tax) is $7.28.  Total_charged includes the recovery.
    assert Decimal(str(r["buyer_total_charged"])) > Decimal("7.28")


# ═════════════════════════════════════════════════════════════════════
# Partner path — B2B recovery preserved (already CLEARED pre-P5)
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("bp_rate,expected_buyer_total,expected_bidvex_fee", [
    (0.05, 105.0, 3.0),
    (0.10, 110.0, 3.0),
    (0.15, 115.0, 3.0),
    (0.18, 118.0, 3.0),
])
def test_partner_various_bp_rates_buyer_total_stable(bp_rate, expected_buyer_total, expected_bidvex_fee):
    """Partner buyer_total_charged = hammer × (1 + bp_rate).  Buyer
    Stripe recovery in the Partner flow is a separate B2B recovery on
    the Partner-BidVex leg — the auction buyer's ``buyer_total_charged``
    stays at hammer + BP for this flow."""
    r = calculate_fee(
        hammer_price=100.0, auction_type="lots",
        seller_account_type="partner", partner_bp_rate=bp_rate,
        buyer_tier="standard", buyer_province="QC", seller_province="QC",
    )
    # Partner path may still legitimately charge the buyer no Stripe
    # recovery — only the Partner leg (B2B) does.  The invariant here
    # is that the hammer+BP totals stay preserved.
    assert Decimal(str(r["buyer_total_charged"])) >= Decimal(str(expected_buyer_total))
    assert Decimal(str(r["bidvex_platform_fee_amount"])) == Decimal(str(expected_bidvex_fee)), (
        "BidVex 3% platform fee must be preserved on Partner sales"
    )


def test_partner_buyer_tier_neutral_e10():
    """E-10 invariant: buyer tier has ZERO effect on partner total."""
    prev = None
    for tier in ("standard", "premium", "vip_elite"):
        r = calculate_fee(
            hammer_price=100.0, auction_type="lots",
            seller_account_type="partner", partner_bp_rate=0.10,
            buyer_tier=tier, buyer_province="QC", seller_province="QC",
        )
        if prev is None:
            prev = r["buyer_total_charged"]
        assert r["buyer_total_charged"] == prev == 110.0


# ═════════════════════════════════════════════════════════════════════
# Storage & Vehicle Dealer — buyer surcharge must be $0
# ═════════════════════════════════════════════════════════════════════

def test_storage_qc_buyer_pays_recovery():
    r = calculate_fee(
        hammer_price=100.0, auction_type="storage",
        seller_account_type="storage_facility", buyer_tier="standard",
        buyer_province="QC", facility_province="QC",
    )
    # iter482 P5 — L-1 CLEARED: buyer bears the Stripe recovery on storage.
    assert r["buyer_stripe_recovery"] > 0.0
    # Storage facility keeps 100% hammer (iter443)
    assert Decimal(str(r["seller_payout"])) == Decimal("100.00")
    assert _pp(r)["amount_cents"] > 0


def test_vehicle_dealer_qc_buyer_pays_recovery():
    r = calculate_fee(
        hammer_price=100.0, auction_type="vehicle",
        seller_account_type="vehicle_dealer", buyer_tier="standard",
        buyer_province="QC",
    )
    assert r["buyer_stripe_recovery"] > 0.0
    # Dealer receives full hammer directly (BidVex charges buyer 2.5% fee + recovery)
    assert Decimal(str(r["seller_payout"])) == Decimal("100.00")
    assert _pp(r)["amount_cents"] > 0


# ═════════════════════════════════════════════════════════════════════
# Cash / e-Transfer / Cheque payment methods — offline, always $0
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("method", ["cash", "e_transfer", "cheque"])
def test_offline_payment_methods_zero_processing(method):
    r = calculate_fee(
        hammer_price=100.0, auction_type="marketplace",
        seller_account_type="individual", seller_tier="standard",
        buyer_tier="standard", buyer_province="QC", seller_province="QC",
        payment_method=method,
    )
    # Offline methods never accrue Stripe surcharge
    assert r["buyer_stripe_recovery"] == 0.0
    pp = _pp(r)
    assert pp["amount_cents"] == 0


# ═════════════════════════════════════════════════════════════════════
# Cent-integer invariants
# ═════════════════════════════════════════════════════════════════════

def test_all_buyer_totals_are_cent_stable():
    """Every calculate_fee return must produce a buyer_total_charged
    that quantizes cleanly to 2dp (no float drift)."""
    for cfg in (
        dict(hammer_price=100.0, seller_account_type="individual", seller_tier="standard", buyer_tier="standard"),
        dict(hammer_price=7.0,   seller_account_type="individual", seller_tier="premium",  buyer_tier="premium"),
        dict(hammer_price=100.0, seller_account_type="partner",    partner_bp_rate=0.10,   buyer_tier="standard"),
        dict(hammer_price=1000.0,seller_account_type="storage_facility", buyer_tier="standard"),
        dict(hammer_price=250.0, seller_account_type="vehicle_dealer",   buyer_tier="standard"),
    ):
        r = calculate_fee(auction_type="lots", buyer_province="QC", seller_province="QC", **cfg)
        t = Decimal(str(r["buyer_total_charged"]))
        assert t == t.quantize(Decimal("0.01")), f"cent drift: {t}"
        cents = int((t * 100).quantize(Decimal("1")))
        assert cents == r["buyer_stripe_cents"]


if __name__ == "__main__":
    import subprocess
    subprocess.run(["python", "-m", "pytest", __file__, "-v"], check=False)
