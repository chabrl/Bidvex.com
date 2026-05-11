"""
iter209 — Step 1 verification: the 5 spec test cases for `calculate_fee()`.

These MUST pass with exact amounts before any frontend or other backend file
is touched. Spec source: PART 3 — VERIFICATION CHECKLIST → CONCRETE TEST CASES.

Notes on numeric tolerance:
  * BP / commission / taxes / payouts are asserted to the cent.
  * Stripe gross-up totals are asserted to ±$0.05 because the spec's "~" hints
    are loose ranges; the formula itself is exact and is asserted exactly via
    the formula's recomputed value.
"""
import sys
import math
import pytest

sys.path.insert(0, "/app/backend")
from services.fee_calculator import calculate_fee


def _approx(actual: float, expected: float, tol: float = 0.005) -> bool:
    return math.isclose(actual, expected, abs_tol=tol)


# ─── Test 1: Individual A1 (standard) sells, B2 (premium) buys at $100 ────
def test_spec_case_1_individual_standard_seller_premium_buyer_100():
    fee = calculate_fee(
        hammer_price=100.0,
        auction_type="lots",
        seller_account_type="individual",
        seller_tier="standard",
        buyer_account_type="individual",
        buyer_tier="premium",
        payment_method="stripe",
        card_type="domestic",
    )

    # Buyer side
    assert _approx(fee["buyer_premium"], 3.50), f"BP expected $3.50, got ${fee['buyer_premium']}"
    assert _approx(fee["buyer_premium_rate"], 0.035)
    assert _approx(fee["buyer_gst"], 0.18), f"GST expected $0.18, got ${fee['buyer_gst']}"
    assert _approx(fee["buyer_qst"], 0.35), f"QST expected $0.35, got ${fee['buyer_qst']}"
    assert _approx(fee["buyer_subtotal"], 104.03), f"Subtotal expected $104.03, got ${fee['buyer_subtotal']}"

    # Seller side
    assert _approx(fee["seller_commission"], 4.00)
    assert _approx(fee["seller_commission_rate"], 0.04)
    assert _approx(fee["seller_gst"], 0.20)
    assert _approx(fee["seller_qst"], 0.40)
    assert _approx(fee["seller_payout"], 95.40), f"Payout expected $95.40, got ${fee['seller_payout']}"

    # Routing
    assert fee["charge_buyer_via_stripe"] is True
    assert fee["charge_seller_card_separately"] is False

    # Total should be subtotal + Stripe gross-up at 2.9% + $0.30
    expected_total = (104.03 + 0.30) / (1 - 0.029)
    assert _approx(fee["buyer_total_charged"], expected_total, tol=0.02), \
        f"Total expected ${expected_total:.2f}, got ${fee['buyer_total_charged']:.2f}"


# ─── Test 2: Partner P1 (15% BP) sells, A1 buys at $100 via Stripe ───────
def test_spec_case_2_partner_15pct_bp_stripe_100():
    fee = calculate_fee(
        hammer_price=100.0,
        auction_type="lots",
        seller_account_type="partner",
        seller_tier=None,                 # partner ignores tier
        buyer_account_type="individual",
        buyer_tier="standard",            # MUST be ignored — partner BP used instead
        partner_bp_rate=0.15,
        payment_method="stripe",
        card_type="domestic",
    )

    # Buyer pays partner-set BP, NOT 5% standard rate
    assert _approx(fee["buyer_premium"], 15.00), f"BP expected $15.00, got ${fee['buyer_premium']}"
    assert _approx(fee["buyer_premium_rate"], 0.15)
    assert _approx(fee["buyer_gst"], 0.75)
    assert _approx(fee["buyer_qst"], 1.50)
    assert _approx(fee["buyer_subtotal"], 117.25)

    # Seller pays only 3% to BidVex
    assert _approx(fee["seller_commission"], 3.00)
    assert _approx(fee["seller_commission_rate"], 0.03)
    assert _approx(fee["seller_gst"], 0.15)
    assert _approx(fee["seller_qst"], 0.30)
    # Partner payout = hammer + their BP - 3% - taxes = 115 - 3.45 = 111.55
    assert _approx(fee["seller_payout"], 111.55), f"Partner payout expected $111.55, got ${fee['seller_payout']}"

    assert fee["charge_buyer_via_stripe"] is True
    assert fee["charge_seller_card_separately"] is False

    expected_total = (117.25 + 0.30) / (1 - 0.029)
    assert _approx(fee["buyer_total_charged"], expected_total, tol=0.02)


# ─── Test 3: Partner P1 (15% BP), buyer pays via CASH ────────────────────
def test_spec_case_3_partner_15pct_bp_cash_100():
    fee = calculate_fee(
        hammer_price=100.0,
        auction_type="lots",
        seller_account_type="partner",
        partner_bp_rate=0.15,
        buyer_account_type="individual",
        buyer_tier="premium",
        payment_method="cash",
        card_type="domestic",
    )

    # Buyer is NOT charged via Stripe — pays partner directly
    assert fee["charge_buyer_via_stripe"] is False
    assert fee["buyer_subtotal"] == 0
    assert fee["buyer_total_charged"] == 0
    assert fee["buyer_stripe_fee"] == 0

    # Partner card auto-charged 3% + taxes + Stripe gross-up
    assert fee["charge_seller_card_separately"] is True
    assert _approx(fee["seller_commission"], 3.00)
    assert _approx(fee["seller_gst"], 0.15)
    assert _approx(fee["seller_qst"], 0.30)
    assert _approx(fee["seller_commission_total"], 3.45)

    expected_seller_charge = (3.45 + 0.30) / (1 - 0.029) - 3.45
    assert _approx(fee["seller_stripe_fee"], expected_seller_charge, tol=0.02), \
        f"Seller Stripe gross-up expected ${expected_seller_charge:.2f}, got ${fee['seller_stripe_fee']:.2f}"

    # Buyer pays partner directly, partner payout from BidVex side is $0
    assert fee["seller_payout"] == 0


# ─── Test 4: Dealer V1 sells car at $10,000 ──────────────────────────────
def test_spec_case_4_vehicle_dealer_10000():
    fee = calculate_fee(
        hammer_price=10_000.0,
        auction_type="vehicle",
        seller_account_type="vehicle_dealer",
        buyer_account_type="individual",
        buyer_tier="premium",            # MUST be ignored — flat 2.5% applies
        payment_method="stripe",
        card_type="domestic",
    )

    assert _approx(fee["buyer_premium"], 250.00)
    assert _approx(fee["buyer_premium_rate"], 0.025)
    assert _approx(fee["buyer_gst"], 12.50)
    assert _approx(fee["buyer_qst"], 24.94), f"QST expected $24.94, got ${fee['buyer_qst']}"
    assert _approx(fee["buyer_subtotal"], 10_287.44)

    # Dealer pays $0 per transaction
    assert _approx(fee["seller_commission"], 0.00)
    assert _approx(fee["seller_commission_rate"], 0.00)
    # Dealer receives full hammer
    assert _approx(fee["seller_payout"], 10_000.00)

    expected_total = (10_287.44 + 0.30) / (1 - 0.029)
    assert _approx(fee["buyer_total_charged"], expected_total, tol=0.05)


# ─── Test 5: Storage S1 lists, buyer wins at $100 ─────────────────────────
def test_spec_case_5_storage_facility_100():
    fee = calculate_fee(
        hammer_price=100.0,
        auction_type="storage",
        seller_account_type="storage_facility",
        buyer_account_type="individual",
        buyer_tier="vip_elite",          # MUST be ignored — buyer pays $0 to BidVex
        payment_method="stripe",
        card_type="domestic",
    )

    # Buyer is NOT charged anything by BidVex
    assert fee["charge_buyer_via_stripe"] is False
    assert _approx(fee["buyer_premium"], 0.00)
    assert _approx(fee["buyer_total_charged"], 0.00)
    assert _approx(fee["buyer_stripe_fee"], 0.00)

    # Facility card auto-charged 5% + taxes + Stripe gross-up
    assert fee["charge_seller_card_separately"] is True
    assert _approx(fee["seller_commission"], 5.00)
    assert _approx(fee["seller_commission_rate"], 0.05)
    assert _approx(fee["seller_gst"], 0.25)
    assert _approx(fee["seller_qst"], 0.50)
    assert _approx(fee["seller_commission_total"], 5.75)

    expected_seller_stripe = (5.75 + 0.30) / (1 - 0.029) - 5.75
    assert _approx(fee["seller_stripe_fee"], expected_seller_stripe, tol=0.02)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
