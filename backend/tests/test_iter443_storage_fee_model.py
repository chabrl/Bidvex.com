"""
iter443 — Storage Auctions Fee Model (BUYER pays 5% BP; facility never charged)
================================================================================
Supersedes the iter170 model where the facility was invoiced 5% commission on
cash/etransfer auctions. Under iter443:

  • Stripe path → BidVex charges the BUYER hammer + 5% BP + Stripe + tax on
    the buyer's card. Facility receives the FULL hammer.
  • Cash / E-Transfer path → buyer pays the FACILITY the hammer offline. BidVex
    separately charges the BUYER's card on file for the 5% BP + Stripe recovery
    + tax on 5%+recovery. Facility receives the FULL hammer offline and is
    NEVER invoiced by BidVex.
  • fee_calculator._iter350_storage returns buyer_premium=5%, seller_commission=0,
    seller_payout=hammer regardless of payment method.

Run: python -m pytest backend/tests/test_iter443_storage_fee_model.py -q
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal

from services.storage_pricing import calculate_storage_pricing
from services.fee_calculator import calculate_fee


# ─────────────────────────────────────────────────────────────
# storage_pricing.calculate_storage_pricing (payment-method flow)
# ─────────────────────────────────────────────────────────────
def test_stripe_qc_800_deposit_100():
    """Stripe path — buyer pays hammer + 5% BP + recovery + tax."""
    p = calculate_storage_pricing(800, "QC", "stripe", deposit_amount=100)
    assert p["payment_method"] == "stripe"
    assert p["buyer_invoice"]["platform_fee"] == 40.00
    assert p["buyer_invoice"]["total"] == 874.34
    assert p["buyer_invoice"]["remaining_after_deposit"] == 774.34
    # Facility receives full hammer, NEVER invoiced.
    assert p["facility_invoice"]["facility_receives"] == 800.00
    assert p["facility_invoice"]["facility_owes_bidvex"] == 0.0


def test_cash_qc_800_deposit_100_iter443():
    """Cash path — iter443: BidVex charges BUYER 5% BP; facility owes 0."""
    p = calculate_storage_pricing(800, "QC", "cash", deposit_amount=100)
    assert p["payment_method"] == "cash"
    # Buyer's BidVex charge: 5% BP + recovery + tax = 40 + 1.46 + 6.21 = 47.67
    assert p["buyer_invoice"]["platform_fee"] == 40.00
    assert p["buyer_invoice"]["stripe_recovery"] == 1.46
    assert p["buyer_invoice"]["tax"] == 6.21
    assert p["buyer_invoice"]["total"] == 47.67
    # Deposit ($100) fully covers the buyer's BidVex charge → remaining = 0.
    assert p["buyer_invoice"]["remaining_after_deposit"] == 0.00
    assert p["buyer_invoice"]["fee_payer"] == "buyer"
    # Facility: full hammer offline, never invoiced.
    assert p["facility_invoice"]["facility_receives"] == 800.00
    assert p["facility_invoice"]["facility_owes_bidvex"] == 0.0
    assert p["facility_invoice"]["bidvex_platform_fee"] == 0.0


def test_etransfer_on_1500_no_deposit_iter443():
    """E-Transfer path — iter443: BidVex charges BUYER 5% BP; facility owes 0."""
    p = calculate_storage_pricing(1500, "ON", "etransfer", deposit_amount=None)
    assert p["payment_method"] == "etransfer"
    assert p["tax_label"] == "HST (13%)"
    # Buyer's BidVex charge: 5% BP + recovery + tax = 75 + 2.48 + 10.07 = 87.55
    assert p["buyer_invoice"]["platform_fee"] == 75.00
    assert p["buyer_invoice"]["stripe_recovery"] == 2.48
    assert p["buyer_invoice"]["tax"] == 10.07
    assert p["buyer_invoice"]["total"] == 87.55
    assert p["buyer_invoice"]["fee_payer"] == "buyer"
    # Facility: full hammer, never invoiced.
    assert p["facility_invoice"]["facility_receives"] == 1500.00
    assert p["facility_invoice"]["facility_owes_bidvex"] == 0.0


# ─────────────────────────────────────────────────────────────
# fee_calculator.calculate_fee (canonical iter350 API)
# ─────────────────────────────────────────────────────────────
def test_calc_fee_storage_stripe_qc():
    """calculate_fee(storage_facility, stripe) — BUYER pays 5% BP."""
    fee = calculate_fee(
        hammer_price=800.0,
        auction_type="storage",
        seller_account_type="storage_facility",
        payment_method="stripe",
        buyer_province="QC",
        facility_province="QC",
    )
    assert fee["seller_type"] == "storage_facility"
    assert fee["buyer_premium"] == 40.00
    assert fee["buyer_premium_rate"] == 0.05
    # Facility side is zeroed — facility keeps full hammer.
    assert fee["seller_commission"] == 0.0
    assert fee["seller_commission_rate"] == 0.0
    assert fee["seller_payout"] == 800.00
    assert fee["bidvex_revenue"] == 40.00
    # Tax is anchored on BUYER's province (iter443 semantic).
    assert fee["buyer_tax_province"] == "QC"


def test_calc_fee_storage_cash_ab():
    """calculate_fee(storage_facility, cash, AB) — BUYER pays 5% BP + 5% GST."""
    fee = calculate_fee(
        hammer_price=1000.0,
        auction_type="storage",
        seller_account_type="storage_facility",
        payment_method="cash",
        buyer_province="AB",
        facility_province="AB",
    )
    assert fee["buyer_premium"] == 50.00
    assert fee["buyer_premium_rate"] == 0.05
    assert fee["seller_commission"] == 0.0
    assert fee["seller_payout"] == 1000.00
    # Buyer's total under cash path = BP + recovery + tax (no hammer via BidVex).
    # BP = 50; recovery = 50*0.029 + 0.30 = 1.75; tax = (50+1.75)*0.05 = 2.59.
    assert fee["buyer_total_charged"] == round(50 + 1.75 + 2.59, 2)


def test_calc_fee_storage_never_charges_facility():
    """Regression — no seller/facility charge for any storage combo."""
    combos = [
        (800.0, "QC", "stripe"),
        (800.0, "QC", "cash"),
        (1500.0, "ON", "etransfer"),
        (2500.0, "BC", "stripe"),
    ]
    for hammer, prov, pm in combos:
        fee = calculate_fee(
            hammer_price=hammer,
            auction_type="storage",
            seller_account_type="storage_facility",
            payment_method=pm,
            buyer_province=prov,
            facility_province=prov,
        )
        assert fee["seller_commission"] == 0.0, f"facility charged on {pm}/{prov}"
        assert fee["seller_taxes"] == 0.0, f"facility taxed on {pm}/{prov}"
        assert fee["seller_stripe_recovery"] == 0.0, f"facility stripe rec on {pm}/{prov}"
        assert fee["seller_payout"] == hammer, f"facility payout != hammer on {pm}/{prov}"
