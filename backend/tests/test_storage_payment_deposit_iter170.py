"""
Iteration 170 — Storage Auctions Payment Method + Deposit System
================================================================
Validates:
  • Pricing math for all 3 payment methods (PROOFS 1, 2, 3 from spec)
  • Pydantic model validation of payment_method + deposit_required/amount
  • Public spec proofs at module load time

Run:  python -m pytest backend/tests/test_storage_payment_deposit_iter170.py -q
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from decimal import Decimal

from services.storage_pricing import calculate_storage_pricing
from models.storage_auction import StorageAuctionCreate


# ─────────────────────────────────────────────────────────────
# PROOF 1 — Stripe Payment, $800 hammer, QC, $100 deposit
# ─────────────────────────────────────────────────────────────
def test_proof1_stripe_qc_800_with_deposit():
    p = calculate_storage_pricing(800, "QC", "stripe", deposit_amount=100)
    assert p["payment_method"] == "stripe"
    assert p["buyer_invoice"]["hammer_price"] == 800.00
    assert p["buyer_invoice"]["platform_fee"] == 40.00
    assert p["buyer_invoice"]["stripe_recovery"] == 24.66
    assert p["buyer_invoice"]["tax"] == 9.68
    assert p["buyer_invoice"]["total"] == 874.34
    assert p["buyer_invoice"]["remaining_after_deposit"] == 774.34
    assert p["buyer_invoice"]["deposit_paid"] == 100.00
    assert p["buyer_invoice"]["fee_payer"] == "buyer"
    assert p["facility_invoice"]["facility_receives"] == 800.00
    assert p["facility_invoice"]["bidvex_fee"] == 0.0


# ─────────────────────────────────────────────────────────────
# PROOF 2 — Cash, $800 hammer, QC, $100 deposit
# ─────────────────────────────────────────────────────────────
def test_proof2_cash_qc_800_with_deposit():
    p = calculate_storage_pricing(800, "QC", "cash", deposit_amount=100)
    assert p["payment_method"] == "cash"
    assert p["buyer_invoice"]["total"] == 800.00
    assert p["buyer_invoice"]["remaining_after_deposit"] == 700.00
    assert p["buyer_invoice"]["fee_payer"] == "facility"
    assert p["facility_invoice"]["bidvex_platform_fee"] == 40.00
    assert p["facility_invoice"]["stripe_recovery"] == 1.46
    assert p["facility_invoice"]["tax"] == 6.21
    assert p["facility_invoice"]["facility_owes_bidvex"] == 47.67
    assert p["facility_invoice"]["facility_net"] == 752.33


# ─────────────────────────────────────────────────────────────
# PROOF 3 — E-Transfer, $1,500 hammer, ON, no deposit
# ─────────────────────────────────────────────────────────────
def test_proof3_etransfer_on_1500_no_deposit():
    p = calculate_storage_pricing(1500, "ON", "etransfer", deposit_amount=None)
    assert p["payment_method"] == "etransfer"
    assert p["tax_label"] == "HST (13%)"
    assert p["buyer_invoice"]["total"] == 1500.00
    assert p["buyer_invoice"]["fee_payer"] == "facility"
    assert p["facility_invoice"]["bidvex_platform_fee"] == 75.00
    assert p["facility_invoice"]["stripe_recovery"] == 2.48
    assert p["facility_invoice"]["tax"] == 10.07
    assert p["facility_invoice"]["facility_owes_bidvex"] == 87.55
    assert p["facility_invoice"]["facility_net"] == 1412.45


# ─────────────────────────────────────────────────────────────
# Edge cases & alternative provinces
# ─────────────────────────────────────────────────────────────
def test_alberta_5pct_gst():
    p = calculate_storage_pricing(1000, "AB", "stripe", deposit_amount=0)
    assert p["tax_label"] == "GST (5%)"
    # 5% of (50 + stripe_recovery) tax
    assert p["buyer_invoice"]["platform_fee"] == 50.00
    # stripe_recovery = (1000+50)*0.029 + 0.30 = 30.45 + 0.30 = 30.75
    assert p["buyer_invoice"]["stripe_recovery"] == 30.75
    # tax = (50 + 30.75) * 0.05 = 4.0375 → 4.04 HALF_UP
    assert p["buyer_invoice"]["tax"] == 4.04


def test_unknown_province_no_tax():
    p = calculate_storage_pricing(500, "ZZ", "stripe", deposit_amount=0)
    assert p["tax_label"] == "No tax"
    assert p["buyer_invoice"]["tax"] == 0.0


# ─────────────────────────────────────────────────────────────
# Pydantic model validation
# ─────────────────────────────────────────────────────────────
def _good_payload(**kw):
    base = {
        "unit_number": "A-1",
        "unit_size": "10x10",
        "unit_type": "indoor",
        "description_en": "A reasonably long description of the unit.",
        "starting_price": 1,
        "start_time": "2026-04-01T00:00:00Z",
        "end_time": "2026-04-08T00:00:00Z",
        "payment_method": "stripe",
        "deposit_required": False,
    }
    base.update(kw)
    return base


def test_model_payment_method_valid():
    for m in ("stripe", "cash", "etransfer"):
        StorageAuctionCreate(**_good_payload(payment_method=m))


def test_model_payment_method_invalid():
    with pytest.raises(Exception):
        StorageAuctionCreate(**_good_payload(payment_method="bitcoin"))


def test_model_deposit_required_without_amount_fails():
    with pytest.raises(Exception):
        StorageAuctionCreate(**_good_payload(deposit_required=True, deposit_amount=None))


def test_model_deposit_required_zero_amount_fails():
    with pytest.raises(Exception):
        StorageAuctionCreate(**_good_payload(deposit_required=True, deposit_amount=0))


def test_model_deposit_required_with_amount_passes():
    m = StorageAuctionCreate(**_good_payload(deposit_required=True, deposit_amount=100))
    assert m.deposit_required is True
    assert m.deposit_amount == 100
