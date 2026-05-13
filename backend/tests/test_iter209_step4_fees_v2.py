"""
iter209 Step 4 — `/api/fees/v2/preview` parity with `calculate_fee()`.

Confirms the public preview endpoint returns the same numbers as the in-process
function for each of the 5 spec scenarios.
"""
import os
import sys
import httpx
import pytest

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

API_URL = ""
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            API_URL = line.split("=", 1)[1].strip().rstrip("/")
            break


def _hit(**params):
    r = httpx.get(f"{API_URL}/api/fees/v2/preview", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


# Spec test 1 — individual standard seller / premium buyer at $100
def test_v2_preview_case_1():
    r = _hit(
        hammer_price=100,
        auction_type="lots",
        seller_account_type="individual",
        seller_tier="standard",
        buyer_tier="premium",
        payment_method="stripe",
        card_type="domestic",
    )
    assert r["buyer_premium"] == 3.50
    assert r["buyer_gst"] == 0.18
    assert r["buyer_qst"] == 0.35
    assert r["buyer_subtotal"] == 104.03
    assert r["seller_commission"] == 4.00
    assert r["seller_payout"] == 95.40
    assert r["charge_buyer_via_stripe"] is True


# Spec test 2 — partner stripe @ $100 with 15% BP
def test_v2_preview_case_2_partner_stripe():
    r = _hit(
        hammer_price=100,
        auction_type="lots",
        seller_account_type="partner",
        partner_bp_rate=0.15,
        buyer_tier="standard",
        payment_method="stripe",
    )
    assert r["buyer_premium"] == 15.00
    assert r["seller_commission"] == 3.00
    assert r["seller_payout"] == 111.55


# Spec test 3 — partner cash → buyer pays 0 via Stripe
def test_v2_preview_case_3_partner_cash():
    r = _hit(
        hammer_price=100,
        auction_type="lots",
        seller_account_type="partner",
        partner_bp_rate=0.15,
        payment_method="cash",
    )
    assert r["charge_buyer_via_stripe"] is False
    assert r["buyer_total_charged"] == 0
    assert r["charge_seller_card_separately"] is True
    assert r["seller_commission_total"] == 3.45


# Spec test 4 — vehicle dealer @ $10k
def test_v2_preview_case_4_vehicle_dealer():
    r = _hit(
        hammer_price=10000,
        auction_type="vehicle",
        seller_account_type="vehicle_dealer",
        buyer_tier="premium",
        payment_method="stripe",
    )
    assert r["buyer_premium"] == 250.00
    assert r["seller_payout"] == 10000.00


# Spec test 5a — storage facility CASH @ $100 (corrected iter211)
def test_v2_preview_case_5a_storage_facility_cash():
    r = _hit(
        hammer_price=100,
        auction_type="storage",
        seller_account_type="storage_facility",
        buyer_tier="vip_elite",
        payment_method="cash",
    )
    assert r["buyer_total_charged"] == 0
    assert r["seller_commission_total"] == 5.75
    assert r["charge_buyer_via_stripe"] is False
    assert r["charge_seller_card_separately"] is True


# Spec test 5b — storage facility STRIPE @ $100 (iter211 P0 fix)
def test_v2_preview_case_5b_storage_facility_stripe():
    r = _hit(
        hammer_price=100,
        auction_type="storage",
        seller_account_type="storage_facility",
        buyer_tier="vip_elite",
        payment_method="stripe",
    )
    # Buyer pays hammer only via Stripe
    assert r["buyer_total_charged"] == 100.0
    assert r["buyer_premium"] == 0.0
    assert r["charge_buyer_via_stripe"] is True
    # Facility absorbs 5% + GST + QST
    assert r["seller_commission_total"] == 5.75
    assert r["seller_payout"] == 94.25
    assert r["charge_seller_card_separately"] is False


# Legacy alias — preserved so any external reference still works
test_v2_preview_case_5_storage_facility = test_v2_preview_case_5a_storage_facility_cash


# Bad params → 422
def test_v2_preview_rejects_negative_hammer():
    r = httpx.get(f"{API_URL}/api/fees/v2/preview",
                  params={"hammer_price": -100, "auction_type": "lots", "seller_account_type": "individual"},
                  timeout=15)
    assert r.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
