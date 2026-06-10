"""
iter297 — Cleanup + P1 features:
  CLEANUP    - users_router actually registered (was dead before)
  P1         - Buyer Confirm Pickup + Deposit Release Flow
  P1         - Server-side Pillow placeholder image for feeds
  P2         - email_notifications.py shim emits DeprecationWarning
"""
import os
import uuid
import warnings
import importlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("PUBLIC_BACKEND_URL", "http://localhost:8001")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


# ── CLEANUP — users_router registered ─────────────────────────────────

def test_users_router_is_registered():
    """`from routes.users import users_router` was imported but never
    passed to `api_router.include_router`. Routes like
    `/api/users/{id}/profile-summary` were dead. iter297 wires the
    router into the app — this test locks that in."""
    r_login = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        timeout=15,
    )
    assert r_login.status_code == 200
    token = r_login.json().get("access_token") or r_login.json().get("token")

    # A route owned by users_router (NOT profiles): /users/{id}/profile-summary
    me_id = r_login.json().get("user", {}).get("id") or r_login.json().get("id")
    if me_id:
        r = requests.get(
            f"{BASE_URL}/api/users/{me_id}/profile-summary",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert r.status_code == 200, f"users_router /profile-summary not reachable: {r.status_code} {r.text[:200]}"


# ── P1 / Pickup confirm — service unit ────────────────────────────────

@pytest.mark.asyncio
async def test_pickup_confirm_marketplace_releases_deposit_and_closes(db):
    """Buyer confirms → status=completed, pickup stamped, deposit
    refunded, completed_auctions counter incremented, rating-request
    emails fire."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.pickup_confirmation import confirm_pickup

    mdb = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
    seller_id = f"iter297-s-{uuid.uuid4().hex[:8]}"
    winner_id = f"iter297-w-{uuid.uuid4().hex[:8]}"
    listing_id = f"iter297-l-{uuid.uuid4().hex[:8]}"

    await mdb.users.insert_one({"id": seller_id, "email": "s@t.com", "name": "Seller iter297", "completed_auctions": 0})
    await mdb.users.insert_one({"id": winner_id, "email": "w@t.com", "name": "Winner iter297"})
    await mdb.listings.insert_one({
        "id": listing_id, "title": "pickup-confirm test",
        "seller_id": seller_id, "status": "ended",
        "winner_user_id": winner_id, "final_price": 55.5,
        "ended_at": datetime.now(timezone.utc).isoformat(),
    })
    await mdb.bidder_deposits.insert_one({
        "id": str(uuid.uuid4()),
        "listing_id": listing_id, "bidder_id": winner_id,
        "amount": 25, "status": "paid",
        "payment_intent_id": "demo_pi_iter297",
    })

    try:
        # Buyer confirms.
        with patch("services.email_notifications.send_unified_email",
                   new=AsyncMock(return_value={"ok": True})):
            result = await confirm_pickup(
                mdb,
                listing_id=listing_id,
                actor_user={"id": winner_id, "role": "user"},
            )
        assert result["ok"] is True
        assert result["role"] == "buyer"
        assert result["kind"] == "marketplace"

        # Listing closed.
        doc = await mdb.listings.find_one({"id": listing_id}, {"_id": 0})
        assert doc["status"]            == "completed"
        assert doc["pickup_confirmed"]  is True
        assert doc["pickup_confirmed_by"] == "buyer"
        assert doc["pickup_confirmed_at"]

        # Deposit refunded.
        dep = await mdb.bidder_deposits.find_one({"listing_id": listing_id}, {"_id": 0})
        assert dep["status"] == "refunded"
        assert dep["refund_reason"] == "pickup_confirmed"

        # Counter incremented.
        s = await mdb.users.find_one({"id": seller_id}, {"_id": 0, "completed_auctions": 1})
        assert s["completed_auctions"] == 1

        # Idempotent: second call is a no-op success.
        result2 = await confirm_pickup(
            mdb, listing_id=listing_id,
            actor_user={"id": winner_id, "role": "user"},
        )
        assert result2["ok"] is True
        assert result2.get("idempotent") is True
    finally:
        await mdb.listings.delete_one({"id": listing_id})
        await mdb.bidder_deposits.delete_many({"listing_id": listing_id})
        await mdb.notifications.delete_many({"data.listing_id": listing_id})
        await mdb.users.delete_many({"id": {"$in": [seller_id, winner_id]}})


@pytest.mark.asyncio
async def test_pickup_confirm_vehicle_holds_deposit_for_admin(db):
    """Vehicle pickup confirmation must NOT auto-refund the deposit
    (vehicles are high-value → admin sign-off required). The flag
    `deposit_release == 'pending_admin_signoff'` makes the gating
    explicit, and an admin bell-icon ping is emitted."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.pickup_confirmation import confirm_pickup

    mdb = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
    seller = f"iter297-vs-{uuid.uuid4().hex[:8]}"
    winner = f"iter297-vw-{uuid.uuid4().hex[:8]}"
    admin  = f"iter297-va-{uuid.uuid4().hex[:8]}"
    vid    = f"iter297-veh-{uuid.uuid4().hex[:8]}"

    await mdb.users.insert_one({"id": seller, "email": "s@t.com", "name": "S"})
    await mdb.users.insert_one({"id": winner, "email": "w@t.com", "name": "W"})
    await mdb.users.insert_one({"id": admin,  "email": "a@t.com", "name": "A", "role": "admin"})
    await mdb.vehicle_listings.insert_one({
        "id": vid, "title": "test vehicle",
        "seller_user_id": seller, "status": "sold",
        "winner_user_id": winner, "final_price": 12000,
        "sold_at": datetime.now(timezone.utc).isoformat(),
    })
    await mdb.vehicle_bid_deposits.insert_one({
        "id": str(uuid.uuid4()), "listing_id": vid,
        "bidder_id": winner, "amount": 1200, "status": "paid",
    })

    try:
        with patch("services.email_notifications.send_unified_email",
                   new=AsyncMock(return_value={"ok": True})):
            result = await confirm_pickup(
                mdb, listing_id=vid,
                actor_user={"id": winner, "role": "user"},
            )
        assert result["ok"] is True
        assert result["kind"] == "vehicle"
        assert result["deposit_release"] == "pending_admin_signoff"

        # Deposit still HELD.
        dep = await mdb.vehicle_bid_deposits.find_one({"listing_id": vid}, {"_id": 0})
        assert dep["status"] == "paid", "vehicle deposit must NOT auto-refund"

        # Admin notification emitted.
        anotifs = await mdb.notifications.find(
            {"user_id": admin, "data.listing_id": vid},
            {"_id": 0},
        ).to_list(5)
        assert any(n["data"].get("action") == "deposit_release_required" for n in anotifs)
    finally:
        await mdb.vehicle_listings.delete_one({"id": vid})
        await mdb.vehicle_bid_deposits.delete_many({"listing_id": vid})
        await mdb.notifications.delete_many({"data.listing_id": vid})
        await mdb.users.delete_many({"id": {"$in": [seller, winner, admin]}})


@pytest.mark.asyncio
async def test_pickup_confirm_seller_must_wait_7_days(db):
    """Within the 7-day buyer window the seller cannot confirm yet —
    `not_authorized` with reason `seller_must_wait`."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.pickup_confirmation import confirm_pickup

    mdb = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
    seller = f"iter297-7s-{uuid.uuid4().hex[:8]}"
    winner = f"iter297-7w-{uuid.uuid4().hex[:8]}"
    lid    = f"iter297-7l-{uuid.uuid4().hex[:8]}"

    await mdb.users.insert_one({"id": seller, "email": "x@y.com", "name": "S"})
    await mdb.users.insert_one({"id": winner, "email": "z@y.com", "name": "W"})
    await mdb.listings.insert_one({
        "id": lid, "title": "still in window",
        "seller_id": seller, "status": "ended",
        "winner_user_id": winner, "final_price": 10,
        # Ended 2 days ago — within the 7-day buyer window.
        "ended_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
    })
    try:
        r = await confirm_pickup(mdb, listing_id=lid,
                                 actor_user={"id": seller, "role": "user"})
        assert r["ok"] is False
        assert r["error"] == "not_authorized"
        assert r["reason"] == "seller_must_wait"
    finally:
        await mdb.listings.delete_one({"id": lid})
        await mdb.users.delete_many({"id": {"$in": [seller, winner]}})


@pytest.mark.asyncio
async def test_stuck_transactions_flagged_after_7_days(db):
    """`flag_stuck_transactions` sweeps and stamps `pending_review_flagged`
    on ended-with-winner listings where neither party confirmed within
    the 7-day grace window. Pings admins via bell-icon."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.pickup_confirmation import flag_stuck_transactions

    mdb = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
    admin = f"iter297-st-admin-{uuid.uuid4().hex[:8]}"
    lid   = f"iter297-st-{uuid.uuid4().hex[:8]}"

    await mdb.users.insert_one({"id": admin, "email": "a@x.com", "name": "A", "role": "admin"})
    await mdb.listings.insert_one({
        "id": lid, "title": "stuck listing",
        "seller_id": "x", "status": "ended",
        "winner_user_id": "y", "final_price": 99,
        # Ended 10 days ago.
        "ended_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
    })

    try:
        out = await flag_stuck_transactions(mdb)
        assert out["flagged"] >= 1
        doc = await mdb.listings.find_one({"id": lid}, {"_id": 0})
        assert doc.get("pending_review_flagged") is True
        assert doc.get("pending_review_reason") == "no_pickup_confirmation_after_7d"

        # Admin notif emitted.
        anotifs = await mdb.notifications.find(
            {"user_id": admin, "data.listing_id": lid},
            {"_id": 0},
        ).to_list(5)
        assert any(n["data"].get("action") == "pickup_overdue" for n in anotifs)

        # Idempotent: re-run does not re-flag the same listing.
        out2 = await flag_stuck_transactions(mdb)
        # Count for THIS specific listing should not double-flag (we
        # check that no second admin notif was emitted).
        anotifs2 = await mdb.notifications.find(
            {"user_id": admin, "data.listing_id": lid},
            {"_id": 0},
        ).to_list(5)
        assert len(anotifs2) == len(anotifs), \
            "stuck-transaction flag must be idempotent (no duplicate admin pings)"
    finally:
        await mdb.listings.delete_one({"id": lid})
        await mdb.notifications.delete_many({"data.listing_id": lid})
        await mdb.users.delete_one({"id": admin})


# ── P1 / Pillow feed placeholder ──────────────────────────────────────

def test_pillow_placeholder_generates_valid_jpeg_bytes():
    """`build_placeholder_bytes` returns a non-trivial JPEG that
    starts with the SOI marker `0xFFD8` so feed crawlers can parse
    the Content-Type from magic bytes."""
    from services.feed_placeholder_image import build_placeholder_bytes
    data = build_placeholder_bytes(title="2018 Ford F-150 Lariat", category="vehicle")
    assert data[:2] == b"\xff\xd8"             # JPEG SOI
    assert b"JFIF" in data[:200] or b"Exif" in data[:200] or len(data) > 4000


@pytest.mark.asyncio
async def test_feed_placeholder_sweep_stamps_url(db):
    """`regenerate_missing_feed_placeholders` finds active listings
    without an image and stamps `placeholder_image_url`."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.feed_placeholder_image import regenerate_missing_feed_placeholders

    mdb = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
    lid_no_img = f"iter297-fp-{uuid.uuid4().hex[:8]}"
    lid_w_img  = f"iter297-fp-w-{uuid.uuid4().hex[:8]}"
    await mdb.listings.insert_one({
        "id": lid_no_img, "title": "fp-no-img",
        "seller_id": "x", "status": "active", "images": [],
    })
    await mdb.listings.insert_one({
        "id": lid_w_img, "title": "fp-with-img",
        "seller_id": "x", "status": "active",
        "images": ["https://example.com/real.jpg"],
    })

    try:
        # Mock the actual S3 upload so the test doesn't need credentials.
        async def _fake_gen(*, listing_id, title, category=""):
            return f"https://cdn.bidvex.com/placeholders/{listing_id}.jpg"

        from services import feed_placeholder_image as _fpi
        with patch.object(_fpi, "generate_and_upload_placeholder", side_effect=_fake_gen):
            out = await regenerate_missing_feed_placeholders(mdb)
        assert out["generated"] >= 1
        no_img = await mdb.listings.find_one({"id": lid_no_img}, {"_id": 0})
        with_img = await mdb.listings.find_one({"id": lid_w_img}, {"_id": 0})
        assert no_img["placeholder_image_url"].endswith(f"{lid_no_img}.jpg")
        # Listing that already has an image must NOT be touched.
        assert "placeholder_image_url" not in with_img
    finally:
        await mdb.listings.delete_one({"id": lid_no_img})
        await mdb.listings.delete_one({"id": lid_w_img})


# ── P2 / Deprecation warning ──────────────────────────────────────────

def test_email_notifications_emits_deprecation_warning():
    """Importing `services.email_notifications` (the shim) must emit a
    DeprecationWarning so the migration to bucketed modules is
    visible in CI / dev logs."""
    import sys
    # Force a fresh import so the module-level warnings.warn fires.
    for mod_name in list(sys.modules):
        if mod_name.endswith("email_notifications"):
            del sys.modules[mod_name]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.import_module("services.email_notifications")
        dep = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert dep, "expected DeprecationWarning on import of services.email_notifications"
        assert "deprecated" in str(dep[0].message).lower()
