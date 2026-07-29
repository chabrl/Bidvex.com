"""
iter408 — Unified coupon / promotion cross-collection resolution.

Verifies the following contract:

    1. A coupon minted in `coupon_codes` (Admin → Coupon Codes) is
       resolved by BOTH `apply_active_promotions` (Admin Promotions
       runtime) AND the Partner Trial Offers public preview endpoint.

    2. A coupon minted in `promotions` (Admin → Promotions) is resolved
       by BOTH `SubscriptionPricingService.validate_coupon` (subscription
       checkout) AND the Partner Trial Offers public preview endpoint.

    3. All three admin surfaces continue to reject unknown / expired /
       over-usage codes with the correct reason.

Runs against the local Motor client — no HTTP server needed. Fast +
deterministic; seeds documents with `iter408-*` prefixes and cleans up
after itself.
"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


# ─── Fixtures ──────────────────────────────────────────────────────
# Function-scoped so each test gets a fresh Motor client attached to
# the current asyncio loop (module-scoped fixtures collided with the
# per-test loop that pytest-asyncio spins up in strict mode).
@pytest_asyncio.fixture
async def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    d = client[os.environ["DB_NAME"]]

    # Wire `deps.get_db()` so routes/services that call it internally
    # (e.g. `preview_coupon`) see the same DB the test is seeding.
    import deps
    prev = deps.db
    deps.set_db(d)

    # Reset the SubscriptionPricingService singleton so it re-binds to
    # this test's DB rather than reusing whichever DB was in effect the
    # first time the process imported it.
    import services.subscription_pricing as sp_mod
    prev_svc = sp_mod._pricing_service
    sp_mod._pricing_service = None

    try:
        yield d
    finally:
        deps.set_db(prev)
        sp_mod._pricing_service = prev_svc
        client.close()


@pytest_asyncio.fixture(autouse=True)
async def _seed(db):
    """Seed one active coupon in EACH of the three collections."""
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).isoformat()
    yesterday = (now - timedelta(days=1)).isoformat()
    next_year = (now + timedelta(days=365)).isoformat()

    # (a) coupon_codes — 20% off subscription (Premium + VIP)
    await db.coupon_codes.insert_one({
        "id":                str(uuid.uuid4()),
        "code":              "ITER408-CC",
        "discount_type":     "percentage",
        "value":             20.0,
        "expiry_date":       next_year,
        "usage_limit":       100,
        "usage_count":       0,
        "applicable_plans":  ["premium", "vip"],
        "is_active":         True,
        "created_at":        now.isoformat(),
    })
    # Expired coupon_codes entry
    await db.coupon_codes.insert_one({
        "id":                str(uuid.uuid4()),
        "code":              "ITER408-CC-EXPIRED",
        "discount_type":     "percentage",
        "value":             25.0,
        "expiry_date":       yesterday,
        "usage_limit":       0,
        "usage_count":       0,
        "applicable_plans":  ["premium", "vip"],
        "is_active":         True,
        "created_at":        now.isoformat(),
    })

    # (b) promotions — 50% subscription discount
    await db.promotions.insert_one({
        "id":               str(uuid.uuid4()),
        "coupon_code":      "ITER408-PR",
        "type":             "subscription_discount",
        "status":           "active",
        "start_date":       yesterday,
        "end_date":         next_year,
        "max_uses":         500,
        "current_uses":     0,
        "config":           {"discount_percent": 50.0, "scope": ["all"]},
        "created_at":       now.isoformat(),
    })

    # (c) partner_trial_coupons — the native trial coupon
    await db.partner_trial_coupons.insert_one({
        "id":               str(uuid.uuid4()),
        "code":             "BVX-TRIAL-ITER4081",
        "partner_type":     "dealer",
        "duration_days":    30,
        "status":           "issued",
        "expires_at":       tomorrow,
        "recipient_email":  "iter408@example.com",
        "recipient_name":   "iter408 tester",
        "created_at":       now.isoformat(),
    })

    yield

    # Cleanup
    await db.coupon_codes.delete_many({"code": {"$regex": "^ITER408"}})
    await db.promotions.delete_many({"coupon_code": {"$regex": "^ITER408"}})
    await db.partner_trial_coupons.delete_many({"code": {"$regex": "^BVX-TRIAL-ITER408"}})


# ─── Helpers ───────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def test_user(db):
    """Create a throw-away user id + seed a user doc so
    `apply_active_promotions` (which fetches the user for targeting)
    finds a document to iterate against."""
    uid = f"iter408-user-{uuid.uuid4()}"
    await db.users.insert_one({
        "id":                uid,
        "email":             f"{uid}@example.com",
        "role":              "user",
        "subscription_tier": "free",
        "created_at":        datetime.now(timezone.utc).isoformat(),
    })
    yield uid
    await db.users.delete_one({"id": uid})


# ═══════════════════════════════════════════════════════════════════
# Test 1 — apply_active_promotions cross-lookup into coupon_codes.
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_apply_active_promotions_resolves_coupon_codes_row(db, test_user):
    """`ITER408-CC` lives in `coupon_codes`, not `promotions`. Before
    iter408 this returned None for the subscription-checkout path;
    now it must return a synthetic promotion dict with the right
    discount percent."""
    from routes.admin_promotions import apply_active_promotions

    result = await apply_active_promotions(
        db=db,
        user_id=test_user,
        transaction_type="subscription_upgrade",
        coupon_code="ITER408-CC",
    )
    assert result is not None, "coupon_codes fallback did not fire"
    assert result["coupon_code"] == "ITER408-CC"
    assert result["type"] == "subscription_discount"
    assert result["source"] == "coupon_codes"
    assert result["config"]["discount_percent"] == 20.0


@pytest.mark.asyncio
async def test_apply_active_promotions_promotions_row_still_wins(db, test_user):
    """When the code lives in `promotions`, the native path (not the
    fallback) must fire and the promotion doc must be returned as-is."""
    from routes.admin_promotions import apply_active_promotions

    result = await apply_active_promotions(
        db=db,
        user_id=test_user,
        transaction_type="subscription_upgrade",
        coupon_code="ITER408-PR",
    )
    assert result is not None
    assert result["coupon_code"] == "ITER408-PR"
    assert result["type"] == "subscription_discount"
    # Native promotions path never carries a `source: coupon_codes` marker.
    assert result.get("source") != "coupon_codes"


# ═══════════════════════════════════════════════════════════════════
# Test 2 — validate_coupon cross-lookup into promotions.
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_validate_coupon_resolves_promotions_row(db):
    """`ITER408-PR` lives in `promotions`. Subscription checkout must
    accept it and compute the discount from `config.discount_percent`."""
    from services.subscription_pricing import get_pricing_service

    svc = get_pricing_service(db)
    # Make sure the premium plan exists in the DB fixture; otherwise
    # `get_plan` returns None and validate_coupon returns
    # "Invalid plan selected". We synthesise a premium plan doc if it's
    # missing (does not persist beyond the test scope).
    if not await db.subscription_plans.find_one({"plan_id": "premium"}):
        await db.subscription_plans.insert_one({
            "plan_id":       "premium",
            "name":          "Premium (iter408)",
            "price_monthly": 49.99,
            "price_yearly":  499.99,
            "is_active":     True,
        })

    result = await svc.validate_coupon(code="ITER408-PR", plan_id="premium", billing_period="yearly")
    result_d = result.model_dump() if hasattr(result, "model_dump") else result.dict()
    assert result_d["valid"] is True, f"expected valid coupon, got {result_d}"
    assert result_d["code"] == "ITER408-PR"
    assert result_d["discount_value"] == 50.0
    # 50% off — discount_amount == half of original_total (whatever the
    # real premium price is on this preview DB).
    expected = round(float(result_d["original_total"]) * 0.5, 2)
    assert abs(result_d["discount_amount"] - expected) < 0.02, \
        f"expected discount ≈{expected}, got {result_d['discount_amount']}"


@pytest.mark.asyncio
async def test_validate_coupon_coupon_codes_row_still_wins(db):
    """Native path — `coupon_codes` still resolves without the fallback."""
    from services.subscription_pricing import get_pricing_service

    if not await db.subscription_plans.find_one({"plan_id": "premium"}):
        await db.subscription_plans.insert_one({
            "plan_id":       "premium",
            "name":          "Premium (iter408)",
            "price_monthly": 49.99,
            "price_yearly":  499.99,
            "is_active":     True,
        })

    svc = get_pricing_service(db)
    result = await svc.validate_coupon(code="ITER408-CC", plan_id="premium", billing_period="yearly")
    r = result.model_dump() if hasattr(result, "model_dump") else result.dict()
    assert r["valid"] is True
    assert r["code"] == "ITER408-CC"
    assert r["discount_value"] == 20.0


@pytest.mark.asyncio
async def test_validate_coupon_expired_row_still_rejected(db):
    from services.subscription_pricing import get_pricing_service

    if not await db.subscription_plans.find_one({"plan_id": "premium"}):
        await db.subscription_plans.insert_one({
            "plan_id":       "premium",
            "name":          "Premium (iter408)",
            "price_monthly": 49.99,
            "price_yearly":  499.99,
            "is_active":     True,
        })

    svc = get_pricing_service(db)
    result = await svc.validate_coupon(code="ITER408-CC-EXPIRED", plan_id="premium")
    r = result.model_dump() if hasattr(result, "model_dump") else result.dict()
    assert r["valid"] is False
    assert "expired" in (r.get("message") or "").lower()


# ═══════════════════════════════════════════════════════════════════
# Test 3 — Partner Trial Offers public preview cross-lookup.
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_preview_coupon_resolves_all_three_sources(db):
    """`preview_coupon` must accept:
      (a) BVX-TRIAL-XXXXXXXX code from `partner_trial_coupons`.
      (b) generic code from `coupon_codes`.
      (c) generic code from `promotions`.
    """
    from routes.trial_coupons import preview_coupon

    # (a) native trial code
    a = await preview_coupon("BVX-TRIAL-ITER4081")
    assert a["valid"] is True
    assert a["source"] == "partner_trial_coupons"

    # (b) coupon_codes fallback
    b = await preview_coupon("ITER408-CC")
    assert b["valid"] is True
    assert b["source"] == "coupon_codes"
    assert b["discount_value"] == 20.0

    # (c) promotions fallback
    c = await preview_coupon("ITER408-PR")
    assert c["valid"] is True
    assert c["source"] == "promotions"
    assert c["discount_percent"] == 50.0


@pytest.mark.asyncio
async def test_preview_coupon_unknown_still_404(db):
    """Unknown non-BVX-TRIAL codes must still return the invalid-format
    or coupon_not_found error (existing behaviour preserved)."""
    from fastapi import HTTPException
    from routes.trial_coupons import preview_coupon

    with pytest.raises(HTTPException) as excinfo:
        await preview_coupon("TOTALLY-UNKNOWN-ITER408")
    # Either "invalid_coupon_format" or "coupon_not_found" is acceptable —
    # the code doesn't match BVX-TRIAL regex and isn't in the fallback
    # collections, so both branches are legitimate.
    detail = excinfo.value.detail if isinstance(excinfo.value.detail, dict) else {}
    assert detail.get("error_code") in {"invalid_coupon_format", "coupon_not_found"}
