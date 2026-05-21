"""
HOTFIX v9.1 — 2 targeted backend tests.

Test 1: Admin approve → listing.status becomes "active" + is_published=True
        + ai_review_* fields wiped → appears in the active feed.

Test 2: GET /api/dashboard/seller response includes a `counts` object with
        the 5 expected keys (total, active, pending_review, draft, ended).
        Also covers GET /api/listings/my-listings.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from motor.motor_asyncio import AsyncIOMotorClient

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or "bazario_db"


@pytest.fixture
def db():
    client = AsyncIOMotorClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.mark.asyncio
async def test_admin_approve_flips_listing_to_active_and_publishes(db):
    """Hotfix v9.1 / Fix 1 — Approving a flagged listing must:
      - Set status='active'
      - Set is_published=True + published_at=now
      - Wipe ai_review_* fields
    """
    from routes.admin_ai_review import admin_approve_listing_review, ReviewActionRequest

    seller_id = f"seller-test-{uuid.uuid4().hex[:8]}"
    listing_id = f"listing-test-{uuid.uuid4().hex[:8]}"
    review_id = f"rev-test-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    # Seed a pending listing + review row
    await db.listings.insert_one({
        "id": listing_id,
        "seller_id": seller_id,
        "title": "Test Listing — Hotfix v9.1",
        "category": "Furniture",
        "status": "pending_ai_review",
        "ai_review_id": review_id,
        "ai_review_flag": "category_mismatch",
        "ai_review_status": "pending",
        "ai_review_flagged_at": now,
        "ai_suggested_category": "Furniture",
        "ai_review_reason_en": "Should be furniture not vehicles",
        "ai_review_reason_fr": "Devrait être meuble",
        "is_published": False,
        "created_at": now,
    })
    await db.listing_reviews.insert_one({
        "id": review_id,
        "listing_id": listing_id,
        "listing_type": "single",
        "collection": "listings",
        "seller_id": seller_id,
        "listing_title": "Test Listing — Hotfix v9.1",
        "seller_category": "vehicles",
        "suggested_category": "Furniture",
        "ai_confidence": 0.85,
        "ai_reason_en": "Should be furniture",
        "ai_reason_fr": "Devrait être meuble",
        "previous_status": "active",
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    })

    # Fake admin user
    class _AdminUser:
        id = "admin-test"
        email = "charbel911@gmail.com"
        role = "admin"

    # Monkey-patch get_db to return the test db
    import routes.admin_ai_review as mod
    original_get_db = mod.get_db
    mod.get_db = lambda: db

    try:
        result = await admin_approve_listing_review(
            review_id=review_id,
            payload=ReviewActionRequest(admin_note="Approved for v9.1 test"),
            current_user=_AdminUser(),
        )
    finally:
        mod.get_db = original_get_db

    # Verify route response
    assert result["success"] is True
    assert result["listing_status"] == "active"

    # Verify the listing doc was correctly flipped
    fresh = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    assert fresh is not None
    assert fresh["status"] == "active", f"Expected 'active', got {fresh['status']}"
    assert fresh["is_published"] is True
    assert fresh["published_at"] is not None
    # Every AI-review breadcrumb must be cleared
    assert fresh["ai_review_id"] is None
    assert fresh["ai_review_flag"] is None
    assert fresh["ai_review_status"] is None
    assert fresh["ai_suggested_category"] is None
    assert fresh["ai_review_reason_en"] is None
    assert fresh["ai_review_reason_fr"] is None

    # Verify review row was marked approved
    rev = await db.listing_reviews.find_one({"id": review_id}, {"_id": 0})
    assert rev["status"] == "approved"
    assert rev["admin_email"] == "charbel911@gmail.com"

    # Verify a "now live" notification was queued in the notifications collection
    notif = await db.notifications.find_one(
        {"user_id": seller_id, "type": "ai_review_approved"},
        sort=[("created_at", -1)],
    )
    assert notif is not None, "Expected an ai_review_approved notification"
    assert "now live" in notif.get("description_en", "").lower() or "now live" in notif.get("message_en", "").lower()

    # Cleanup
    await db.listings.delete_one({"id": listing_id})
    await db.listing_reviews.delete_one({"id": review_id})
    await db.notifications.delete_many({"user_id": seller_id})
    await db.email_outbox.delete_many({"to_user_id": seller_id})


@pytest.mark.asyncio
async def test_seller_dashboard_returns_counts_object(db):
    """Hotfix v9.1 / Fix 3 — GET /api/dashboard/seller response must
    include `counts` with the 5 required keys + integer values."""
    # Directly test the route function with a stub current_user
    from routes.dashboard import get_seller_dashboard, set_dashboard_db, set_dashboard_read_db, set_dashboard_auth
    from fastapi.security import HTTPAuthorizationCredentials

    seller_id = f"seller-counts-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    # Seed 5 listings spanning each status bucket
    fixtures = [
        {"status": "active",                  "title": "Active 1"},
        {"status": "active",                  "title": "Active 2"},
        {"status": "pending_ai_review",       "title": "Pending AI"},
        {"status": "pending_admin_review",    "title": "Pending Admin"},
        {"status": "draft",                   "title": "Draft 1"},
        {"status": "sold",                    "title": "Sold 1"},
        {"status": "ended",                   "title": "Ended 1"},
    ]
    listing_ids = []
    for f in fixtures:
        lid = f"lst-counts-{uuid.uuid4().hex[:8]}"
        listing_ids.append(lid)
        await db.listings.insert_one({
            "id": lid,
            "seller_id": seller_id,
            "title": f["title"],
            "status": f["status"],
            "category": "Furniture",
            "current_price": 100,
            "views": 0,
            "bid_count": 0,
            "created_at": now,
        })

    # Wire up the route with our test db + a stub auth resolver
    class _User:
        id = seller_id
        email = "counts@test.com"
        role = "user"

    async def _stub_get_user(req=None, credentials=None):  # noqa: ARG001
        return _User()

    set_dashboard_db(db)
    set_dashboard_read_db(db)
    set_dashboard_auth(_stub_get_user)

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="dummy-token")
    result = await get_seller_dashboard(credentials=creds)

    # Verify counts object structure
    counts = result.get("counts")
    assert counts is not None, "counts key missing from /dashboard/seller response"
    for key in ("total", "active", "pending_review", "draft", "ended"):
        assert key in counts, f"counts missing key: {key}"
        assert isinstance(counts[key], int), f"counts[{key!r}] must be int"

    # Verify the actual buckets
    assert counts["total"] == 7
    assert counts["active"] == 2
    # pending_ai_review + pending_admin_review = 2
    assert counts["pending_review"] == 2
    assert counts["draft"] == 1
    # sold + ended = 2 (both fall under _ENDED_STATUSES)
    assert counts["ended"] == 2

    # Cleanup
    await db.listings.delete_many({"id": {"$in": listing_ids}})


@pytest.mark.asyncio
async def test_my_listings_endpoint_returns_counts(db):
    """Hotfix v9.1 / Fix 3 — GET /api/listings/my-listings returns
    {listings: [...], counts: {...}}."""
    from routes.listings import get_my_listings

    seller_id = f"seller-mylist-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    lid = f"lst-mylist-{uuid.uuid4().hex[:8]}"
    await db.listings.insert_one({
        "id": lid,
        "seller_id": seller_id,
        "title": "My Listings Test",
        "status": "pending_ai_review",
        "category": "Furniture",
        "current_price": 100,
        "views": 0,
        "bid_count": 0,
        "created_at": now,
    })

    class _User:
        id = seller_id
        email = "mylist@test.com"
        role = "user"

    # Patch get_db inside listings route
    import routes.listings as listings_mod
    original_get_db = listings_mod.get_db
    listings_mod.get_db = lambda: db

    try:
        result = await get_my_listings(current_user=_User())
    finally:
        listings_mod.get_db = original_get_db

    assert "listings" in result
    assert "counts" in result
    assert isinstance(result["listings"], list)
    assert len(result["listings"]) == 1
    assert result["counts"]["total"] == 1
    assert result["counts"]["pending_review"] == 1
    assert result["counts"]["active"] == 0

    # Cleanup
    await db.listings.delete_one({"id": lid})
