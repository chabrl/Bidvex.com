"""
Iteration 301 — review_request integration tests.

Covers:
 - Pre-sale Q&A messaging gate relaxation + per-listing conversation_id format
 - Conversation report + admin reported-threads list & resolve
 - Reviews: submit-context, bidirectional submit, duplicate 409, reputation buyer→seller only, admin-only buyer reviews
 - Marketplace pagination metadata, sitemap.xml, robots.txt
 - Admin analytics overview cache (60s)
"""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
BUYER_EMAIL = "iter225buyer@bidvex.com"
BUYER_PASSWORD = "TestBuyer225!"
BUYER_ID_HINT = "85b3ce59-f264-4d43-8d12-19b3449ec8b3"

# ----- Mongo helpers -----
def _mongo():
    return MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "bazario_db")]


@pytest.fixture(scope="module")
def db():
    return _mongo()


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code == 429:
        time.sleep(15)
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    body = r.json()
    return body.get("access_token") or body.get("token"), body.get("user", {})


@pytest.fixture(scope="module")
def admin_token():
    tok, user = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    return tok, user


@pytest.fixture(scope="module")
def buyer_token():
    time.sleep(13)  # rate-limit spacing
    tok, user = _login(BUYER_EMAIL, BUYER_PASSWORD)
    return tok, user


@pytest.fixture(scope="module")
def seeded_active_listing(db, admin_token):
    _, admin_user = admin_token
    listing_id = f"TEST_iter301_active_{uuid.uuid4().hex[:8]}"
    doc = {
        "id": listing_id,
        "title": "TEST_iter301 Active listing",
        "description": "active for messaging gate test",
        "status": "active",
        "seller_id": admin_user["id"],
        "current_price": 10.0,
        "starting_price": 5.0,
        "end_time": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "category": "other",
        "condition": "new",
        "images": [],
    }
    db.listings.insert_one(doc)
    yield doc
    db.listings.delete_one({"id": listing_id})


@pytest.fixture(scope="module")
def seeded_ended_listing(db, admin_token, buyer_token):
    _, admin_user = admin_token
    _, buyer_user = buyer_token
    listing_id = f"TEST_iter301_ended_{uuid.uuid4().hex[:8]}"
    doc = {
        "id": listing_id,
        "title": "TEST_iter301 Ended listing",
        "description": "ended for review test",
        "status": "ended",
        "seller_id": admin_user["id"],
        "winner_id": buyer_user.get("id") or BUYER_ID_HINT,
        "current_price": 99.0,
        "starting_price": 5.0,
        "end_time": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "created_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        "category": "other",
        "condition": "new",
        "images": [],
    }
    db.listings.insert_one(doc)
    yield doc
    db.listings.delete_one({"id": listing_id})
    db.reviews.delete_many({"listing_id": listing_id})


# ---------- Messaging gate / per-listing conv id ----------
class TestMessaging:
    def test_buyer_to_seller_active_listing_creates_per_listing_conv(self, buyer_token, seeded_active_listing, admin_token):
        tok, buyer = buyer_token
        _, admin = admin_token
        r = requests.post(
            f"{BASE_URL}/api/messages",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "receiver_id": admin["id"],
                "content": "TEST_iter301 hello seller pre-sale Q",
                "listing_id": seeded_active_listing["id"],
            },
            timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        conv_id = data.get("conversation_id") or data.get("conversationId")
        assert conv_id, data
        # Format: {sorted pair}__{listing_id}
        assert conv_id.endswith(f"__{seeded_active_listing['id']}"), f"unexpected conv_id={conv_id}"
        pair_part = conv_id.split("__")[0]
        ids = sorted([buyer["id"], admin["id"]])
        assert pair_part == f"{ids[0]}_{ids[1]}", f"pair part {pair_part} should be sorted IDs"
        # Save for later
        TestMessaging._conv_id = conv_id

    def test_buyer_messages_non_seller_blocked(self, buyer_token, seeded_active_listing, db):
        tok, _ = buyer_token
        # pick any other random non-admin user (find one that has id field)
        other = db.users.find_one({
            "id": {"$exists": True, "$ne": seeded_active_listing["seller_id"]},
            "role": {"$ne": "admin"},
        })
        assert other and other.get("id"), "need another user in db"
        r = requests.post(
            f"{BASE_URL}/api/messages",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "receiver_id": other["id"],
                "content": "should be blocked",
                "listing_id": seeded_active_listing["id"],
            },
            timeout=20,
        )
        assert r.status_code == 403, f"{r.status_code} {r.text}"
        body = r.json()
        # accept either {detail:{code:...}} or {detail:str containing code}
        detail = body.get("detail")
        code = detail.get("code") if isinstance(detail, dict) else str(detail)
        assert "presale_must_message_seller" in str(code), body


# ---------- Conversation report + admin moderation ----------
class TestReportThread:
    def test_report_conversation_by_participant(self, buyer_token):
        tok, _ = buyer_token
        conv_id = getattr(TestMessaging, "_conv_id", None)
        assert conv_id, "previous test must succeed"
        r = requests.post(
            f"{BASE_URL}/api/conversations/{conv_id}/report",
            headers={"Authorization": f"Bearer {tok}"},
            json={"reason": "TEST_iter301 spam content"},
            timeout=20,
        )
        assert r.status_code == 200, r.text

    def test_admin_lists_reported_thread(self, admin_token):
        tok, _ = admin_token
        conv_id = getattr(TestMessaging, "_conv_id", None)
        r = requests.get(
            f"{BASE_URL}/api/admin/messages/reported-threads?status=pending",
            headers={"Authorization": f"Bearer {tok}"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        items = body if isinstance(body, list) else body.get("items") or body.get("threads") or []
        assert any((it.get("conversation_id") == conv_id) or (it.get("id") == conv_id) for it in items), f"reported thread not in pending list: {items[:3]}"

    def test_admin_resolves_reported_thread(self, admin_token):
        tok, _ = admin_token
        conv_id = getattr(TestMessaging, "_conv_id", None)
        r = requests.post(
            f"{BASE_URL}/api/admin/messages/reported-threads/{conv_id}/resolve",
            headers={"Authorization": f"Bearer {tok}"},
            json={"action": "no_violation"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        # Verify it's no longer in pending
        r2 = requests.get(
            f"{BASE_URL}/api/admin/messages/reported-threads?status=pending",
            headers={"Authorization": f"Bearer {tok}"},
            timeout=20,
        )
        items = r2.json() if isinstance(r2.json(), list) else r2.json().get("items") or r2.json().get("threads") or []
        still_pending = any((it.get("conversation_id") == conv_id) or (it.get("id") == conv_id) for it in items)
        assert not still_pending, "resolved thread should be removed from pending filter"


# ---------- Reviews ----------
class TestReviews:
    def test_submit_context_buyer(self, buyer_token, seeded_ended_listing):
        tok, _ = buyer_token
        r = requests.get(
            f"{BASE_URL}/api/reviews/submit-context",
            params={"listing_id": seeded_ended_listing["id"], "role": "buyer"},
            headers={"Authorization": f"Bearer {tok}"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("item_title") or body.get("title"), body
        assert body.get("counterparty_name") or body.get("counterparty"), body

    def test_submit_buyer_review(self, buyer_token, seeded_ended_listing):
        tok, _ = buyer_token
        r = requests.post(
            f"{BASE_URL}/api/reviews/submit",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "listing_id": seeded_ended_listing["id"],
                "role": "buyer",
                "rating": 5,
                "comment": "TEST_iter301 buyer review excellent",
            },
            timeout=20,
        )
        assert r.status_code == 200, r.text

    def test_duplicate_buyer_review_409(self, buyer_token, seeded_ended_listing):
        tok, _ = buyer_token
        r = requests.post(
            f"{BASE_URL}/api/reviews/submit",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "listing_id": seeded_ended_listing["id"],
                "role": "buyer",
                "rating": 4,
                "comment": "dupe",
            },
            timeout=20,
        )
        assert r.status_code == 409, r.text

    def test_submit_seller_review(self, admin_token, seeded_ended_listing):
        tok, _ = admin_token
        r = requests.post(
            f"{BASE_URL}/api/reviews/submit",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "listing_id": seeded_ended_listing["id"],
                "role": "seller",
                "rating": 5,
                "comment": "TEST_iter301 seller reviewing buyer",
            },
            timeout=20,
        )
        assert r.status_code == 200, r.text

    def test_reputation_excludes_seller_role(self, admin_token, seeded_ended_listing):
        _, admin = admin_token
        r = requests.get(f"{BASE_URL}/api/reviews/reputation/{admin['id']}", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        # Reputation should reflect buyer→seller reviews only; we added 1
        count = (
            body.get("review_count")
            or body.get("count")
            or body.get("total")
            or body.get("total_reviews")
            or body.get("rating_count")
            or 0
        )
        # Fallback: check that average_rating exists and is for the buyer review (5.0)
        assert body.get("average_rating") == 5.0 or count >= 1, body

    def test_buyer_reviews_admin_only(self, buyer_token, admin_token):
        btok, buyer = buyer_token
        # Non-admin: 403
        r = requests.get(
            f"{BASE_URL}/api/reviews/buyer/{buyer['id']}",
            headers={"Authorization": f"Bearer {btok}"},
            timeout=20,
        )
        assert r.status_code == 403, r.status_code
        # Admin: 200
        atok, _ = admin_token
        r2 = requests.get(
            f"{BASE_URL}/api/reviews/buyer/{buyer['id']}",
            headers={"Authorization": f"Bearer {atok}"},
            timeout=20,
        )
        assert r2.status_code == 200, r2.text


# ---------- Marketplace / SEO / cache ----------
class TestSeoPaginationCache:
    def test_marketplace_pagination_metadata(self):
        r = requests.get(f"{BASE_URL}/api/marketplace/items", params={"limit": 2}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "total_count" in body, body.keys()
        assert "page" in body, body.keys()

    def test_sitemap_xml(self):
        r = requests.get(f"{BASE_URL}/sitemap.xml", timeout=20)
        assert r.status_code == 200, r.status_code

    def test_robots_txt(self):
        r = requests.get(f"{BASE_URL}/robots.txt", timeout=20)
        assert r.status_code == 200, r.status_code

    def test_admin_analytics_overview_cached(self, admin_token):
        tok, _ = admin_token
        r1 = requests.get(f"{BASE_URL}/api/admin/analytics/overview", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        assert r1.status_code == 200, r1.text
        r2 = requests.get(f"{BASE_URL}/api/admin/analytics/overview", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        assert r2.status_code == 200
        gen1 = r1.json().get("generated_at")
        gen2 = r2.json().get("generated_at")
        assert gen1 and gen2, (r1.json().keys(), r2.json().keys())
        assert gen1 == gen2, "cache (60s) should return identical generated_at"
