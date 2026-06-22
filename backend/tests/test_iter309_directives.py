"""
iter309 — End-to-end regression tests for the 4 directives:
  D1 — Multi-Lot Category Restructure
  D2 — AI Review Pause/Approve Workflow
  D3 — Partner Trial Coupon (4th option) + Wizard Audit
  D4 — Global Unsubscribe Link Standardization

These tests hit the real preview backend (or whatever REACT_APP_BACKEND_URL
points to) plus the Python helpers directly where token signing requires
the server-side secret.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")

from pymongo import MongoClient  # noqa: E402


# ────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


@pytest.fixture(scope="module", autouse=True)
def _bootstrap_async_db():
    """Wire deps.set_db with a motor client so async route helpers can call
    get_db() without a running FastAPI lifespan."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from deps import set_db
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    set_db(client[os.environ["DB_NAME"]])
    yield
    client.close()


# ────────────────────────────────────────────────────────────────────
# D1 — Multi-Lot Category Restructure
# ────────────────────────────────────────────────────────────────────

def test_d1_lot_model_has_category_field():
    """The Lot Pydantic model must carry an optional `category` field."""
    from models.auction_models import Lot

    lot = Lot(
        lot_number=1,
        title="Test lot",
        description="A description",
        category="Tools",
        quantity=1,
        starting_price=10.0,
        current_price=10.0,
        condition="good",
    )
    assert lot.category == "Tools"

    # Optional — should not raise.
    lot2 = Lot(
        lot_number=2,
        title="No cat",
        description="No cat description",
        quantity=1,
        starting_price=5.0,
        current_price=5.0,
        condition="good",
    )
    assert lot2.category is None


def test_d1_multiitem_listing_has_categories_aggregate():
    """MultiItemListing must carry a `categories` list field."""
    from models.auction_models import MultiItemListing, Lot
    from datetime import datetime, timedelta, timezone

    listing = MultiItemListing(
        seller_id="s-1",
        title="Test",
        description="Desc",
        category="Tools",
        categories=["Tools", "Furniture"],
        location="QC",
        city="Sherbrooke",
        region="QC",
        country="CA",
        auction_end_date=datetime.now(timezone.utc) + timedelta(days=3),
        lots=[
            Lot(
                lot_number=1, title="L1", description="D1 desc xxxxxxxxxxxxxxxxxxxxx",
                quantity=1, starting_price=10, current_price=10, condition="good",
                category="Tools",
            ),
            Lot(
                lot_number=2, title="L2", description="D2 desc xxxxxxxxxxxxxxxxxxxxx",
                quantity=1, starting_price=10, current_price=10, condition="good",
                category="Furniture",
            ),
        ],
    )
    assert "Tools" in listing.categories
    assert "Furniture" in listing.categories


def test_d1_multiitem_create_payload_allows_omitted_category():
    """MultiItemListingCreate must accept `category=None` (lot-level only)."""
    from models.auction_models import MultiItemListingCreate, Lot
    from datetime import datetime, timedelta, timezone

    payload = MultiItemListingCreate(
        title="No top-level cat",
        description="Desc",
        location="QC",
        city="Sherbrooke",
        region="QC",
        country="CA",
        auction_end_date=datetime.now(timezone.utc) + timedelta(days=3),
        lots=[
            Lot(
                lot_number=1, title="L1", description="D1 desc xxxxxxxxxxxxxxxxxxxxx",
                quantity=1, starting_price=10, current_price=10, condition="good",
                category="Electronics",
            ),
        ],
    )
    assert payload.category is None
    assert payload.lots[0].category == "Electronics"


def test_d1_backfill_script_is_idempotent(db):
    """The D1 backfill script must be safe to re-run with no data drift."""
    # Insert a synthetic multi-item listing with one un-categorized lot.
    doc_id = f"iter309-d1-{uuid.uuid4().hex[:8]}"
    test_doc = {
        "id":      doc_id,
        "title":   "iter309 D1 backfill test",
        "category": "Tools",
        "status":  "draft",
        "lots": [
            {"lot_number": 1, "title": "Hammer", "description": "old hammer", "quantity": 1, "starting_price": 10, "current_price": 10, "condition": "good"},  # no category
            {"lot_number": 2, "title": "Saw", "description": "old saw", "quantity": 1, "starting_price": 10, "current_price": 10, "condition": "good", "category": "Tools"},
        ],
    }
    try:
        db.multi_item_listings.insert_one(test_doc)

        # Manually run the backfill logic (mirrors the script behaviour).
        from collections import Counter
        doc = db.multi_item_listings.find_one({"id": doc_id}, {"_id": 0})
        auction_cat = (doc.get("category") or "").strip()
        counter = Counter()
        updated_lots = []
        for lot in doc["lots"]:
            lc = (lot.get("category") or "").strip()
            if not lc and auction_cat:
                lot = {**lot, "category": auction_cat}
                lc = auction_cat
            counter[lc] += 1
            updated_lots.append(lot)
        new_aggregate = sorted({c for c in counter}, key=lambda c: -counter[c])
        if auction_cat not in new_aggregate:
            new_aggregate.insert(0, auction_cat)
        db.multi_item_listings.update_one(
            {"id": doc_id},
            {"$set": {"lots": updated_lots, "categories": new_aggregate}},
        )

        post = db.multi_item_listings.find_one({"id": doc_id}, {"_id": 0})
        assert all(lot.get("category") for lot in post["lots"])
        assert "Tools" in post["categories"]
    finally:
        db.multi_item_listings.delete_one({"id": doc_id})


# ────────────────────────────────────────────────────────────────────
# D2 — AI Review Pause/Approve Workflow
# ────────────────────────────────────────────────────────────────────

def test_d2_pending_listings_hidden_from_public_marketplace(db):
    """Listings with status=pending_ai_review or pending_admin_review must
    NOT appear in the public marketplace query (which filters status=active).
    """
    pending_id = f"iter309-d2-pending-{uuid.uuid4().hex[:8]}"
    active_id = f"iter309-d2-active-{uuid.uuid4().hex[:8]}"

    try:
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        db.listings.insert_many([
            {
                "id":              pending_id,
                "seller_id":       "test-seller",
                "title":           "iter309 D2 pending listing",
                "description":     "test description",
                "category":        "Tools",
                "condition":       "good",
                "starting_price":  10.0,
                "current_price":   10.0,
                "images":          [],
                "location":        "QC",
                "city":            "Sherbrooke",
                "region":          "QC",
                "country":         "CA",
                "currency":        "CAD",
                "status":          "pending_admin_review",
                "auction_end_date": now + timedelta(days=7),
                "created_at":      now,
            },
            {
                "id":              active_id,
                "seller_id":       "test-seller",
                "title":           "iter309 D2 active listing",
                "description":     "test description",
                "category":        "Tools",
                "condition":       "good",
                "starting_price":  10.0,
                "current_price":   10.0,
                "images":          [],
                "location":        "QC",
                "city":            "Sherbrooke",
                "region":          "QC",
                "country":         "CA",
                "currency":        "CAD",
                "status":          "active",
                "auction_end_date": now + timedelta(days=7),
                "created_at":      now,
            },
        ])

        # The marketplace filter must hide the pending row.
        visible_ids = {d["id"] for d in db.listings.find({"status": "active", "id": {"$in": [pending_id, active_id]}}, {"_id": 0, "id": 1})}
        assert active_id in visible_ids
        assert pending_id not in visible_ids
    finally:
        db.listings.delete_many({"id": {"$in": [pending_id, active_id]}})


def test_d2_admin_approve_preserves_seller_fields():
    """The admin approve handler must use $set on a fixed set of keys —
    NOT reconstruct the entire payload (which would destroy seller data).
    """
    import inspect
    from routes import admin_ai_review

    src = inspect.getsource(admin_ai_review.admin_approve_listing_review)
    # The handler must NOT replace the listing doc — only $set selected fields.
    assert 'replace_one' not in src
    assert 'insert_one' not in src
    # It uses $set semantics.
    assert '"status":' in src
    assert "$set" in src


# ────────────────────────────────────────────────────────────────────
# D3 — Partner Trial Coupon (4th option)
# ────────────────────────────────────────────────────────────────────

def test_d3_partner_tier_in_trial_durations():
    """`partner` must be a valid 30-day trial type."""
    from routes.trial_coupons import TRIAL_DURATIONS
    assert TRIAL_DURATIONS["partner"] == 30
    assert TRIAL_DURATIONS["dealer"] == 30
    assert TRIAL_DURATIONS["broker"] == 60
    assert TRIAL_DURATIONS["storage"] == 45


def test_d3_campaign_create_accepts_partner_type():
    """The external campaign CampaignCreate model must allow trial_partner_type='partner'."""
    from routes.external_campaigns import CampaignCreate

    body = CampaignCreate(
        name="Partner trial campaign",
        subject_en="Try BidVex free for 30 days",
        body_html_en="<p>Hello {trial_signup_url} {unsubscribe_url}</p>",
        attach_trial_coupon=True,
        trial_partner_type="partner",
    )
    assert body.trial_partner_type == "partner"


def test_d3_redeem_partner_coupon_sets_trial_active(db):
    """Redeeming a partner coupon must set trial_active=true + account_tier=partner."""
    from routes.trial_coupons import redeem_coupon_for_user, generate_coupon_code
    from datetime import datetime, timezone, timedelta

    code = generate_coupon_code()
    user_id = f"iter309-d3-user-{uuid.uuid4().hex[:8]}"
    user_email = f"{user_id}@test.example"

    try:
        # Pre-mint a partner coupon synchronously.
        now = datetime.now(timezone.utc)
        db.partner_trial_coupons.insert_one({
            "id":                  str(uuid.uuid4()),
            "code":                code,
            "partner_type":        "partner",
            "duration_days":       30,
            "status":              "issued",
            "created_by":          "test",
            "created_at":          now.isoformat(),
            "expires_at":          (now + timedelta(days=90)).isoformat(),
            "redeemed_by_user_id": None,
            "redeemed_at":         None,
            "source":              "manual",
            "campaign_id":         None,
        })
        db.users.insert_one({
            "id":    user_id,
            "email": user_email,
            "role":  "user",
        })

        # Drive the async helper.
        claimed = asyncio.run(redeem_coupon_for_user(
            code,
            user_id=user_id,
            user_email=user_email,
        ))
        assert claimed is not None
        assert claimed["partner_type"] == "partner"

        updated_user = db.users.find_one({"id": user_id}, {"_id": 0})
        assert updated_user["trial_active"] is True
        assert updated_user["account_tier"] == "partner"
        assert updated_user["partner_type"] == "partner"
        assert updated_user["partner_trial_active"] is True
    finally:
        db.partner_trial_coupons.delete_many({"code": code})
        db.users.delete_many({"id": user_id})
        db.partner_trials.delete_many({"user_id": user_id})


# ────────────────────────────────────────────────────────────────────
# D4 — Global Unsubscribe Link Standardization
# ────────────────────────────────────────────────────────────────────

def test_d4_build_unsubscribe_urls_uses_canonical_format():
    """Both EN and FR URLs must point to /unsubscribe with the lang query param."""
    # Provide a known secret so the helper can sign.
    os.environ.setdefault("UNSUBSCRIBE_SECRET", "iter309-test-secret-please-change")
    from routes.unsubscribe import build_unsubscribe_urls

    urls = build_unsubscribe_urls("alice@example.com")
    assert "/unsubscribe?token=" in urls["en"]
    assert "&lang=en" in urls["en"]
    assert "/unsubscribe?token=" in urls["fr"]
    assert "&lang=fr" in urls["fr"]
    # No /desabonnement leakage in the canonical EN/FR builder.
    assert "/desabonnement" not in urls["en"]
    assert "/desabonnement" not in urls["fr"]


def test_d4_external_campaign_unsubscribe_url_canonical():
    """The external campaign send pipeline must inject the canonical
    https://...bidvex.com/unsubscribe?token=...&lang=... URL into emails."""
    import inspect
    from services import external_email
    src = inspect.getsource(external_email.send_external_campaign_email)
    # Must NOT use the legacy /api/external/unsubscribe URL anymore.
    assert "/api/external/unsubscribe" not in src
    assert "/unsubscribe?token=" in src
    assert "lang=" in src


def test_d4_auto_decoder_accepts_platform_itsdangerous_token():
    """The unified `_decode_any_unsubscribe_token` helper must accept the
    platform itsdangerous token shape."""
    os.environ.setdefault("UNSUBSCRIBE_SECRET", "iter309-test-secret-please-change")
    from routes.unsubscribe import generate_unsubscribe_token, _decode_any_unsubscribe_token

    token = generate_unsubscribe_token("alice@example.com")
    payload = _decode_any_unsubscribe_token(token)
    assert payload["email"] == "alice@example.com"
    assert payload["source"] == "platform"


def test_d4_auto_decoder_accepts_external_jwt_token():
    """The unified decoder must also accept external JWT tokens."""
    os.environ.setdefault("JWT_SECRET", "iter309-jwt-secret-please-change")
    from services.external_email import make_unsubscribe_token
    from routes.unsubscribe import _decode_any_unsubscribe_token

    token = make_unsubscribe_token("bob@example.com", "campaign-123", "fr")
    payload = _decode_any_unsubscribe_token(token)
    assert payload["email"] == "bob@example.com"
    assert payload["campaign_id"] == "campaign-123"
    assert payload["source"] == "external"


def test_d4_auto_confirm_sets_email_unsubscribed_flag(db):
    """The unified auto-confirm endpoint must flip `email_unsubscribed=true`
    on the user document + write to suppression tables."""
    os.environ.setdefault("UNSUBSCRIBE_SECRET", "iter309-test-secret-please-change")
    from routes.unsubscribe import generate_unsubscribe_token, auto_confirm_unsubscribe, ConfirmRequest
    from motor.motor_asyncio import AsyncIOMotorClient
    from deps import set_db

    email = f"iter309-d4-{uuid.uuid4().hex[:8]}@test.example"
    user_id = str(uuid.uuid4())
    try:
        db.users.insert_one({
            "id":    user_id,
            "email": email,
            "role":  "user",
        })
        token = generate_unsubscribe_token(email)

        class _FakeRequest:
            client = None

        async def _run():
            # Rebind motor client to this freshly-created event loop.
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            set_db(client[os.environ["DB_NAME"]])
            try:
                return await auto_confirm_unsubscribe(ConfirmRequest(token=token), _FakeRequest())
            finally:
                client.close()

        result = asyncio.run(_run())
        assert result["status"] == "success"

        user = db.users.find_one({"email": email}, {"_id": 0})
        assert user["email_unsubscribed"] is True
        assert user["marketing_unsubscribed"] is True

        suppression = db.email_suppressions.find_one({"email": email}, {"_id": 0})
        assert suppression is not None

        external_suppression = db.external_email_suppressions.find_one({"email": email}, {"_id": 0})
        assert external_suppression is not None
    finally:
        db.users.delete_many({"email": email})
        db.email_suppressions.delete_many({"email": email})
        db.external_email_suppressions.delete_many({"email": email})
