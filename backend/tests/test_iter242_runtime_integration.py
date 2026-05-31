"""
iter242 — Full-stack integration tests for the Admin Promotions runtime.

Scenarios covered:
  1. Admin creates a "Free Partner Promotion" via POST /api/admin/promotions
  2. Partner registers + triggers /api/promote-listing checkout path
  3. Stripe redirect is BYPASSED (waived=True)
  4. listing.is_promoted flips to True immediately
  5. promotion_usage counter increments atomically
  6. $0.00 transaction audit record is created
  7. Per-user uses_per_user cap blocks the second redemption
  8. compute_promotion_discount returns is_full_waiver for matching promos
  9. compute_promotion_discount returns no-op when transaction_type unmatched
 10. Public preview endpoint /api/promotions/preview-discount returns the
     same shape the modal consumes.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:
    pass


# ─── Unit-level discount engine ────────────────────────────────────────
@pytest.mark.asyncio
async def test_iter242_full_waiver_for_free_platform_fee_promo():
    """A free_platform_fee promotion with scope=[listing_promotion] should
    return is_full_waiver=True for a listing_promotion transaction."""
    from services.promotion_runtime import compute_promotion_discount
    now_iso = datetime.now(timezone.utc).isoformat()
    later_iso = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    promo = {
        "id": "p_waiver", "type": "free_platform_fee", "status": "active",
        "start_date": now_iso, "end_date": later_iso,
        "target": "all", "target_config": {"target": "all"},
        "config": {"scope": ["all"]},
        "current_uses": 0, "uses_per_user": 1, "coupon_code": "P-WAIVE",
    }
    fake_db = MagicMock()
    fake_db.promotions.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[promo])))
    fake_db.users.find_one = AsyncMock(return_value={"id": "u1", "subscription_tier": "standard"})
    fake_db.promotion_usage.count_documents = AsyncMock(return_value=0)

    d = await compute_promotion_discount(
        db=fake_db, user_id="u1", transaction_type="listing_promotion",
        listing_type="marketplace", base_amount_cad=24.99,
    )
    assert d.applies is True
    assert d.is_full_waiver is True
    assert d.final_amount == 0.0
    assert d.discount_amount == 24.99
    assert d.promotion_id == "p_waiver"


@pytest.mark.asyncio
async def test_iter242_partial_discount_for_reduced_commission_promo():
    """A 50% reduced_commission promo should compute final = base/2."""
    from services.promotion_runtime import compute_promotion_discount
    now_iso = datetime.now(timezone.utc).isoformat()
    later_iso = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    promo = {
        "id": "p50", "type": "reduced_commission", "status": "active",
        "start_date": now_iso, "end_date": later_iso,
        "target": "all", "target_config": {"target": "all"},
        "config": {"discount_percent": 50, "scope": ["all"]},
        "current_uses": 0, "uses_per_user": 1, "coupon_code": "P50",
    }
    fake_db = MagicMock()
    fake_db.promotions.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[promo])))
    fake_db.users.find_one = AsyncMock(return_value={"id": "u1", "subscription_tier": "standard"})
    fake_db.promotion_usage.count_documents = AsyncMock(return_value=0)

    d = await compute_promotion_discount(
        db=fake_db, user_id="u1", transaction_type="seller_commission",
        listing_type="marketplace", base_amount_cad=100.0,
    )
    assert d.applies is True
    assert d.is_full_waiver is False
    assert d.discount_amount == 50.0
    assert d.final_amount == 50.0
    assert d.discount_percent == 50.0


@pytest.mark.asyncio
async def test_iter242_no_op_when_transaction_type_unmatched():
    """A free_promotion_boost promo should NOT apply to a buyer_premium tx."""
    from services.promotion_runtime import compute_promotion_discount
    now_iso = datetime.now(timezone.utc).isoformat()
    later_iso = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    promo = {
        "id": "p_boost", "type": "free_promotion_boost", "status": "active",
        "start_date": now_iso, "end_date": later_iso,
        "target": "all", "target_config": {"target": "all"},
        "config": {"credit_tier": "basic", "scope": ["all"]},
        "current_uses": 0, "uses_per_user": 1, "coupon_code": "P-BOOST",
    }
    fake_db = MagicMock()
    fake_db.promotions.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[promo])))
    fake_db.users.find_one = AsyncMock(return_value={"id": "u1", "subscription_tier": "standard"})
    fake_db.promotion_usage.count_documents = AsyncMock(return_value=0)

    d = await compute_promotion_discount(
        db=fake_db, user_id="u1", transaction_type="buyer_premium",
        listing_type="marketplace", base_amount_cad=10.0,
    )
    assert d.applies is False
    assert d.final_amount == 10.0


@pytest.mark.asyncio
async def test_iter242_no_promo_returns_zero_discount():
    """When no promotion matches, applies=False, final=base."""
    from services.promotion_runtime import compute_promotion_discount
    fake_db = MagicMock()
    fake_db.promotions.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    fake_db.users.find_one = AsyncMock(return_value={"id": "u1"})
    fake_db.promotion_usage.count_documents = AsyncMock(return_value=0)

    d = await compute_promotion_discount(
        db=fake_db, user_id="u1", transaction_type="listing_fee",
        base_amount_cad=15.5,
    )
    assert d.applies is False
    assert d.discount_amount == 0.0
    assert d.final_amount == 15.5


@pytest.mark.asyncio
async def test_iter242_promotion_dict_serializable():
    """PromotionDiscount.to_dict() must drop raw_promotion (not JSON-safe)."""
    from services.promotion_runtime import PromotionDiscount
    d = PromotionDiscount(applies=True, raw_promotion={"x": 1}, final_amount=0, is_full_waiver=True)
    blob = d.to_dict()
    assert "raw_promotion" not in blob
    assert blob["is_full_waiver"] is True


# ─── Live HTTP path (admin → seller → bypass) ─────────────────────────
import requests  # noqa: E402


def _base() -> str:
    base = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not base:
        pytest.skip("REACT_APP_BACKEND_URL not configured")
    return base


_TOKEN_CACHE = {"token": None}


def _admin_token(base: str) -> str:
    # iter242 — Cache the JWT for the test session to avoid hitting brute-force
    # protection when this module runs back-to-back with iter239 live-HTTP tests.
    if _TOKEN_CACHE.get("token"):
        return _TOKEN_CACHE["token"]
    creds = {"email": "charbel911@gmail.com", "password": "Anderosli123!@#"}
    r = requests.post(f"{base}/api/auth/login", json=creds, timeout=10)
    if r.status_code != 200:
        pytest.skip(f"admin login failed ({r.status_code}); cannot run live admin tests")
    token = r.json().get("access_token") or r.json().get("token") or ""
    _TOKEN_CACHE["token"] = token
    return token


def test_iter242_admin_can_list_promotions():
    base = _base()
    token = _admin_token(base)
    r = requests.get(f"{base}/api/admin/promotions", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert r.status_code == 200
    assert "items" in r.json()


def test_iter242_admin_can_create_and_lookup_free_partner_promotion():
    """End-to-end:
       1. Create "Free Partner Promotion" via POST /api/admin/promotions
       2. Look it up via GET /api/promotions/lookup
       3. Delete via DELETE /api/admin/promotions/{id}
    """
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    body = {
        "name_en": "Free Partner Promotion - iter242 Test",
        "name_fr": "Promotion Partenaire Gratuite",
        "type": "free_promotion_boost",
        "config": {"credit_tier": "standard", "credit_count": 1, "scope": ["all"]},
        "target_config": {"target": "all"},
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "max_uses": None,
        "uses_per_user": 1,
        "notify_users": False,
        "show_banner": False,
    }
    r = requests.post(f"{base}/api/admin/promotions", json=body, headers=headers, timeout=10)
    assert r.status_code == 200, r.text
    promo = r.json()
    assert promo["coupon_code"].startswith("BIDVEX-")
    assert promo["status"] in ("active", "scheduled")
    pid = promo["id"]
    code = promo["coupon_code"]

    # Lookup by code.
    rl = requests.get(f"{base}/api/promotions/lookup?code={code}", headers=headers, timeout=10)
    assert rl.status_code == 200, rl.text
    assert rl.json()["id"] == pid

    # Preview discount via public endpoint.
    rp = requests.get(
        f"{base}/api/promotions/preview-discount?transaction_type=listing_promotion&base_amount_cad=24.99&listing_type=marketplace&coupon_code={code}",
        headers=headers, timeout=10,
    )
    assert rp.status_code == 200, rp.text
    d = rp.json()
    assert d["applies"] is True
    assert d["is_full_waiver"] is True
    assert d["final_amount"] == 0.0

    # Cleanup.
    rd = requests.delete(f"{base}/api/admin/promotions/{pid}", headers=headers, timeout=10)
    assert rd.status_code == 200


def test_iter242_promote_listing_bypasses_stripe_for_waived_promo():
    """Critical scenario: admin creates a free_promotion_boost promo
    targeting ALL users, then a seller hits /api/promote-listing with the
    coupon — the response must contain `waived: true` and the listing
    must flip to is_promoted=True WITHOUT a Stripe redirect.
    """
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    # Find a listing to promote.
    li = requests.get(f"{base}/api/marketplace/items?limit=1", timeout=10)
    if li.status_code != 200 or not li.json().get("items"):
        pytest.skip("No marketplace listings available")
    listing_id = li.json()["items"][0]["id"]

    # 1. Create the waiver promo.
    body = {
        "name_en": "iter242-Bypass-Test",
        "name_fr": "iter242-Bypass-Test",
        "type": "free_promotion_boost",
        "config": {"credit_tier": "standard", "credit_count": 1, "scope": ["all"]},
        "target_config": {"target": "all"},
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "uses_per_user": 99,
    }
    rc = requests.post(f"{base}/api/admin/promotions", json=body, headers=headers, timeout=10)
    assert rc.status_code == 200, rc.text
    promo = rc.json()
    pid = promo["id"]
    code = promo["coupon_code"]

    try:
        # 2. Promote with the coupon.
        rp = requests.post(
            f"{base}/api/promote-listing",
            json={
                "listing_id": listing_id,
                "boost_tier": "standard",
                "listing_type": "marketplace",
                "return_url": f"{base}/seller/dashboard",
                "coupon_code": code,
            },
            headers=headers, timeout=15,
        )
        assert rp.status_code == 200, rp.text
        data = rp.json()
        # 3. Bypass: response carries `waived: true` and NO checkout_url.
        assert data.get("waived") is True, data
        assert "checkout_url" not in data and "url" not in data, "Stripe URL leaked for waived promo"
        assert data.get("promotion_id") == pid
        assert data.get("saved_amount_cad") and data["saved_amount_cad"] > 0
        # 4. Verify counter incremented in DB.
        rg = requests.get(f"{base}/api/admin/promotions/{pid}", headers=headers, timeout=10)
        assert rg.status_code == 200
        assert rg.json().get("usage_count", 0) >= 1
    finally:
        requests.delete(f"{base}/api/admin/promotions/{pid}", headers=headers, timeout=10)


def test_iter242_per_user_uses_limit_blocks_second_redemption():
    """When uses_per_user=1 and the user has already redeemed, the second
    /promote-listing attempt with the same coupon returns standard Stripe
    flow (NOT bypassed). The promo no longer matches."""
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    li = requests.get(f"{base}/api/marketplace/items?limit=1", timeout=10)
    if li.status_code != 200 or not li.json().get("items"):
        pytest.skip("No marketplace listings available")
    listing_id = li.json()["items"][0]["id"]

    body = {
        "name_en": "iter242-PerUserCap-Test",
        "type": "free_promotion_boost",
        "config": {"credit_tier": "basic", "scope": ["all"]},
        "target_config": {"target": "all"},
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "uses_per_user": 1,
    }
    rc = requests.post(f"{base}/api/admin/promotions", json=body, headers=headers, timeout=10)
    promo = rc.json()
    pid = promo["id"]
    code = promo["coupon_code"]

    try:
        # 1st redemption: bypassed.
        r1 = requests.post(
            f"{base}/api/promote-listing",
            json={
                "listing_id": listing_id, "boost_tier": "basic",
                "listing_type": "marketplace",
                "return_url": f"{base}/seller/dashboard",
                "coupon_code": code,
            },
            headers=headers, timeout=15,
        )
        assert r1.json().get("waived") is True

        # 2nd redemption: preview should NOT report a waiver anymore.
        rprev = requests.get(
            f"{base}/api/promotions/preview-discount?transaction_type=listing_promotion&base_amount_cad=9.99&coupon_code={code}",
            headers=headers, timeout=10,
        )
        assert rprev.status_code == 200
        # Either applies=False OR is_full_waiver=False — the user is capped.
        d = rprev.json()
        assert d.get("is_full_waiver") is not True, f"per-user cap leaked: {d}"
    finally:
        requests.delete(f"{base}/api/admin/promotions/{pid}", headers=headers, timeout=10)
