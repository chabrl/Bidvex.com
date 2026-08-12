"""
iter482 P5 — Payer-Bears-Stripe-Processing-Cost End-to-End Tests
================================================================

Covers:
  1. Payment cost engine gross-up math (CA + INT rates, $7 / $100 / $1000)
  2. L-1 CLEARED across all provinces for BUYER and SELLER payers
  3. calculate_general_checkout returns non-zero processing_fee and
     application_fee includes the buyer-borne recovery
  4. Path A ↔ Path B cross-calculator reconciliation cent-exact
  5. GET  /api/seller/commission-invoice/{id}  end-to-end
  6. POST /api/seller/commission-invoice/{id}/pay-now  offline branch
     persists an invoice row
  7. Offline payment method → $0 stripe recovery + reason_code=offline_method
"""

from __future__ import annotations
import os
import asyncio
import pytest
import uuid
import httpx
from decimal import Decimal
from datetime import datetime, timezone
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from services.payment_cost_engine import estimate, PayerRole, LegalGate

load_dotenv("/app/backend/.env")

BASE_URL = "http://localhost:8001"
HTTP_TIMEOUT = 30.0


def _mongo():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


# ─── 1. Gross-up math ────────────────────────────────────────────────
@pytest.mark.parametrize("amount_cents,card_class,expected_additive,expected_recovery", [
    # (amount, class, additive=amount*.029+30 or *.039+30, gross-up=ceil((*+30)/(1-r)))
    (10000, "domestic",       320, 330),   # $100 CAD → $3.20 add / $3.30 gross
    (10000, "international",  420, 438),   # $100 INT → $4.20 / $4.38
    (700,   "domestic",        50,  52),   # $7 CAD   → $0.50 / $0.52
    (700,   "international",   57,  60),   # $7 INT
    (100000, "domestic",     2930, 3018),  # $1000 CAD
    (100000, "international",3930, 4090),  # $1000 INT
])
def test_gross_up_math(amount_cents, card_class, expected_additive, expected_recovery):
    e = estimate(
        payment_method="stripe_card",
        amount_cents=amount_cents,
        currency="CAD",
        payer_role=PayerRole.BUYER,
        jurisdiction="QC",
        card_class=card_class,
        mode="gross_up",
    )
    assert e.legal_gate_status is LegalGate.CLEARED
    assert e.estimated_cents == expected_additive, f"additive mismatch: {e.estimated_cents}"
    assert e.recovery_cents == expected_recovery, f"gross-up mismatch: {e.recovery_cents}"


# ─── 2. L-1 CLEARED across provinces for BUYER + SELLER ──────────────
@pytest.mark.parametrize("payer", [PayerRole.BUYER, PayerRole.SELLER])
@pytest.mark.parametrize("prov", ["QC", "ON", "AB", "BC", "NS", "MB"])
def test_l1_open_for_buyer_and_seller(payer, prov):
    e = estimate(
        payment_method="stripe_card",
        amount_cents=10000,
        currency="CAD",
        payer_role=payer,
        jurisdiction=prov,
    )
    assert e.legal_gate_status is LegalGate.CLEARED
    assert e.estimated_cents > 0
    assert e.recovery_cents >= e.estimated_cents


# ─── 3. Offline methods stay at $0 with reason ────────────────────────
@pytest.mark.parametrize("method", ["cash", "e_transfer", "cheque"])
def test_offline_methods_zero_with_reason(method):
    e = estimate(
        payment_method=method,
        amount_cents=10000,
        currency="CAD",
        payer_role=PayerRole.BUYER,
        jurisdiction="QC",
    )
    assert e.estimated_cents == 0
    assert e.recovery_cents == 0
    assert e.reason_code == "offline_method"


# ─── 4. Path A ↔ Path B reconciliation cent-exact ────────────────────
@pytest.mark.parametrize("hammer,buyer_tier,seller_tier", [
    (7.00, "premium", "premium"),
    (100.00, "standard", "standard"),
    (100.00, "premium", "premium"),
    (100.00, "vip_elite", "vip_elite"),
    (250.50, "standard", "standard"),
    (1000.00, "standard", "standard"),
])
def test_path_a_path_b_reconcile_with_recovery(hammer, buyer_tier, seller_tier):
    from services.fee_calculator import calculate_fee
    from services.stripe_connect_service import calculate_general_checkout
    r_a = calculate_fee(
        hammer_price=hammer, auction_type="marketplace",
        seller_account_type="individual", seller_tier=seller_tier,
        buyer_tier=buyer_tier, buyer_province="QC", seller_province="QC",
    )
    b_b = calculate_general_checkout(
        hammer, buyer_tier, seller_tier, False, True, None, buyer_province="QC"
    )
    assert Decimal(str(r_a["buyer_total_charged"])) == Decimal(str(b_b.buyer_total))
    assert Decimal(str(r_a["buyer_stripe_recovery"])) == Decimal(str(b_b.processing_fee))
    assert r_a["buyer_stripe_recovery"] > 0
    assert Decimal(str(b_b.processing_fee)) > Decimal("0")


# ─── 5. BidVex retains the recovery via application_fee ──────────────
def test_application_fee_includes_recovery():
    """Charge = app_fee + transfer_to_seller.  Recovery MUST be in
    app_fee so BidVex does not silently absorb the Stripe cost."""
    from services.stripe_connect_service import calculate_general_checkout
    b = calculate_general_checkout(100.0, "standard", "standard", False, True, None, buyer_province="QC")
    assert b.stripe_charge_amount_cents == (
        b.stripe_application_fee_cents + b.stripe_transfer_amount_cents
    ), "destination-charge invariant violated"
    # The recovery must be inside the application_fee, not the transfer
    expected_app_fee = int(
        (
            Decimal(str(b.buyer_premium))
            + Decimal(str(b.seller_commission))
            + Decimal(str(b.fees_tax_total))
            + Decimal(str(b.processing_fee))
        ) * 100
    )
    assert b.stripe_application_fee_cents == expected_app_fee


# ─── 6. GET /api/seller/commission-invoice/{id} ─────────────────────
async def _register_seller(client: httpx.AsyncClient):
    email = f"iter482p5-seller-{uuid.uuid4().hex[:8]}@test.com"
    r = await client.post("/api/auth/register", json={
        "name": "P5 Seller",
        "email": email,
        "password": "TestSeller!23",
        "role": "user",
        "terms_agreed": True,
        "ai_disclosure_consent": True,
        "accepted_terms": True,
        "terms_accepted": True,
        "province": "QC",
    })
    assert r.status_code in (200, 201), r.text
    token = r.json().get("access_token") or r.json().get("token")
    db = _mongo()
    u = await db.users.find_one({"email": email})
    return {"email": email, "token": token, "user_id": u["id"]}


async def _seed_listing(db, seller_id, hammer=100.0):
    lid = f"iter482p5-{uuid.uuid4().hex[:8]}"
    await db.listings.insert_one({
        "id": lid,
        "title": "iter482 P5 test",
        "seller_id": seller_id,
        "hammer_price": hammer,
        "current_price": hammer,
        "category": "general",
        "region": "QC",
        "currency": "CAD",
        "status": "ended",
        "accepted_payment_methods": ["stripe", "cash", "etransfer", "cheque"],
    })
    return lid


async def _cleanup(db, listing_id, email):
    await db.listings.delete_one({"id": listing_id})
    await db.seller_commission_invoices.delete_many({"listing_id": listing_id})
    await db.users.delete_one({"email": email})


def test_http_get_seller_commission_invoice_returns_full_breakdown():
    async def _t():
        db = _mongo()
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=HTTP_TIMEOUT) as c:
            seller = await _register_seller(c)
            lid = await _seed_listing(db, seller["user_id"], hammer=100.0)
            try:
                r = await c.get(
                    f"/api/seller/commission-invoice/{lid}",
                    headers={"Authorization": f"Bearer {seller['token']}"},
                )
                assert r.status_code == 200, r.text
                inv = r.json()
                # 4% Individual rate
                assert inv["seller_commission_rate"] == "0.04"
                assert inv["seller_commission_cents"] == 400   # $4.00
                # Taxes on $4.00: GST $0.20 + QST $0.40 = $0.60
                assert inv["taxes"]["gst_cents"] == 20
                assert inv["taxes"]["qst_cents"] == 40
                assert inv["tax_total_cents"] == 60
                # Stripe branch has non-zero recovery
                stripe_row = inv["breakdown_by_method"]["stripe"]
                assert stripe_row["stripe_recovery_cents"] > 0
                assert stripe_row["total_cents"] == 400 + 60 + stripe_row["stripe_recovery_cents"]
                # All offline branches → recovery = 0
                for m in ("cash", "etransfer", "cheque"):
                    row = inv["breakdown_by_method"][m]
                    assert row["stripe_recovery_cents"] == 0
                    assert row["reason_code"] == "offline_method"
                    assert row["total_cents"] == 460
                # Unpaid state
                assert inv["payment_status"] == "unpaid"
            finally:
                await _cleanup(db, lid, seller["email"])
    asyncio.run(_t())


# ─── 7. POST pay-now (offline branch) persists row ──────────────────
def test_http_pay_now_offline_persists_invoice():
    async def _t():
        db = _mongo()
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=HTTP_TIMEOUT) as c:
            seller = await _register_seller(c)
            lid = await _seed_listing(db, seller["user_id"], hammer=100.0)
            try:
                r = await c.post(
                    f"/api/seller/commission-invoice/{lid}/pay-now",
                    json={"payment_method": "etransfer", "return_url": ""},
                    headers={"Authorization": f"Bearer {seller['token']}"},
                )
                assert r.status_code == 200, r.text
                body = r.json()
                assert body["payment_method"] == "etransfer"
                # Offline branch total = commission + tax + $0 recovery = $4.60
                assert body["total_cents"] == 460
                # Persisted row exists
                row = await db.seller_commission_invoices.find_one({"listing_id": lid})
                assert row is not None
                assert row["payment_method"] == "etransfer"
                assert row["total_cents"] == 460
                assert row["stripe_recovery_cents"] == 0
            finally:
                await _cleanup(db, lid, seller["email"])
    asyncio.run(_t())


# ─── 8. POST pay-now non-owner is rejected ──────────────────────────
def test_http_pay_now_rejects_non_owner():
    async def _t():
        db = _mongo()
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=HTTP_TIMEOUT) as c:
            owner = await _register_seller(c)
            stranger = await _register_seller(c)
            lid = await _seed_listing(db, owner["user_id"], hammer=100.0)
            try:
                r = await c.post(
                    f"/api/seller/commission-invoice/{lid}/pay-now",
                    json={"payment_method": "cash", "return_url": ""},
                    headers={"Authorization": f"Bearer {stranger['token']}"},
                )
                assert r.status_code == 403, r.text
            finally:
                await _cleanup(db, lid, owner["email"])
                await _cleanup(db, "does-not-exist", stranger["email"])
    asyncio.run(_t())
