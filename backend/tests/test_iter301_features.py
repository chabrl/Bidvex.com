"""
test_iter301_features.py — iter301 feature suite
=================================================

Covers (live API on localhost:8001 + direct DB seeding):
  P1 Reviews        — /reviews/submit-context + /reviews/submit (both
                      directions), idempotency, role guards, reputation
                      exclusion of seller→buyer docs, admin buyer-review
                      list + soft delete
  P1 Messaging      — pre-sale Q&A gate relaxation (active listing →
                      seller only), messaging_suspended enforcement,
                      per-listing conversation threading, bell
                      notification, thread abuse report + admin queue
  P2 SEO            — sitemap.xml + robots.txt reachable
  P2 Performance    — marketplace items pagination exposes total_count
                      + page; analytics overview 60s response cache
"""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE = os.environ.get("BIDVEX_TEST_BASE", "http://localhost:8001")
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.text[:200]}"
    return r.json().get("access_token") or r.json().get("token")


def _register(prefix):
    email = f"{prefix}+{uuid.uuid4().hex[:8]}@example.com"
    password = "Iter301Test!x"
    r = requests.post(f"{BASE}/api/auth/register", json={
        "email": email, "password": password, "name": f"Iter301 {prefix}",
        "terms_agreed": True, "ai_disclosure_consent": True}, timeout=30)
    assert r.status_code in (200, 201), r.text[:200]
    token = r.json().get("access_token") or r.json().get("token") or _login(email, password)
    uid = (r.json().get("user") or {}).get("id")
    if not uid:
        me = requests.get(f"{BASE}/api/auth/me",
                          headers={"Authorization": f"Bearer {token}"}, timeout=30)
        uid = me.json().get("id")
    return {"email": email, "token": token, "id": uid}


def _db():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BACKEND_DIR, ".env"))
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]


def _run(coro):
    import asyncio
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture(scope="module")
def admin_token(test_admin_email, test_admin_password):
    return _login(test_admin_email, test_admin_password)


@pytest.fixture(scope="module")
def seller():
    return _register("iter301.seller")


@pytest.fixture(scope="module")
def buyer():
    return _register("iter301.buyer")


@pytest.fixture(scope="module")
def outsider():
    return _register("iter301.outsider")


@pytest.fixture(scope="module")
def ended_listing(seller, buyer):
    """Completed transaction: buyer won seller's listing."""
    lid = f"iter301-ended-{uuid.uuid4().hex[:8]}"
    doc = {
        "id": lid, "title": "Iter301 Ended Lamp", "description": "test",
        "status": "ended", "seller_id": seller["id"], "winner_id": buyer["id"],
        "final_price": 120.0, "current_price": 120.0,
        "images": [], "created_at": datetime.now(timezone.utc).isoformat(),
        "end_time": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "_iter301_test": True,
    }

    async def seed():
        db = _db()
        await db.listings.insert_one(dict(doc))
    _run(seed())
    yield doc

    async def cleanup():
        db = _db()
        await db.listings.delete_one({"id": lid})
        await db.reviews.delete_many({"listing_id": lid})
        await db.seller_reputation.delete_one({"seller_id": seller["id"]})
    _run(cleanup())


@pytest.fixture(scope="module")
def active_listing(seller):
    """Live listing for pre-sale Q&A messaging."""
    lid = f"iter301-active-{uuid.uuid4().hex[:8]}"
    doc = {
        "id": lid, "title": "Iter301 Live Chair", "description": "test",
        "status": "active", "seller_id": seller["id"],
        "current_price": 50.0, "starting_price": 50.0,
        "images": [], "created_at": datetime.now(timezone.utc).isoformat(),
        "end_time": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        "_iter301_test": True,
    }

    async def seed():
        db = _db()
        await db.listings.insert_one(dict(doc))
    _run(seed())
    yield doc

    async def cleanup():
        db = _db()
        await db.listings.delete_one({"id": lid})
        await db.messages.delete_many({"listing_id": lid})
        convs = "_".join(sorted([]))  # noqa: F841
        await db.conversations.delete_many({"listing_id": lid})
    _run(cleanup())


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ────────────────────────────────────────────────────────────────────
# P1 — Reviews: submit-context + submit (both directions)
# ────────────────────────────────────────────────────────────────────
def test_review_context_buyer_ok(buyer, ended_listing):
    r = requests.get(f"{BASE}/api/reviews/submit-context",
                     params={"listing_id": ended_listing["id"], "role": "buyer"},
                     headers=_h(buyer["token"]), timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d["item_title"] == "Iter301 Ended Lamp"
    assert d["role"] == "buyer"
    assert d["existing_review"] is None


def test_review_context_role_guard(buyer, seller, ended_listing):
    # Buyer cannot review as seller
    r = requests.get(f"{BASE}/api/reviews/submit-context",
                     params={"listing_id": ended_listing["id"], "role": "seller"},
                     headers=_h(buyer["token"]), timeout=30)
    assert r.status_code == 403
    # Seller cannot review as buyer
    r2 = requests.get(f"{BASE}/api/reviews/submit-context",
                      params={"listing_id": ended_listing["id"], "role": "buyer"},
                      headers=_h(seller["token"]), timeout=30)
    assert r2.status_code == 403


def test_review_submit_buyer_then_idempotent(buyer, ended_listing):
    body = {"listing_id": ended_listing["id"], "role": "buyer",
            "rating": 5, "comment": "Great seller, fast pickup coordination!"}
    r = requests.post(f"{BASE}/api/reviews/submit", json=body,
                      headers=_h(buyer["token"]), timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d["review"]["role"] == "buyer"
    assert d["review"]["seller_id"] == ended_listing["seller_id"]
    # idempotent — second submit rejected
    r2 = requests.post(f"{BASE}/api/reviews/submit", json=body,
                       headers=_h(buyer["token"]), timeout=30)
    assert r2.status_code == 409


def test_review_submit_seller_direction(seller, buyer, ended_listing):
    body = {"listing_id": ended_listing["id"], "role": "seller",
            "rating": 4, "comment": "Pleasant buyer, paid on time."}
    r = requests.post(f"{BASE}/api/reviews/submit", json=body,
                      headers=_h(seller["token"]), timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d["review"]["role"] == "seller"
    assert d["review"]["reviewee_id"] == buyer["id"]
    assert d["reputation"] is None  # seller→buyer never touches reputation
    r2 = requests.post(f"{BASE}/api/reviews/submit", json=body,
                       headers=_h(seller["token"]), timeout=30)
    assert r2.status_code == 409


def test_reputation_excludes_seller_to_buyer(seller, ended_listing):
    r = requests.get(f"{BASE}/api/reviews/reputation/{seller['id']}", timeout=30)
    assert r.status_code == 200
    d = r.json()
    # Only the buyer→seller review counts (1), not the seller→buyer one
    assert d["total_reviews"] == 1, d


def test_admin_buyer_reviews_list_and_guard(admin_token, buyer, seller, ended_listing):
    # non-admin blocked
    r0 = requests.get(f"{BASE}/api/reviews/buyer/{buyer['id']}",
                      headers=_h(seller["token"]), timeout=30)
    assert r0.status_code == 403
    # admin sees the seller→buyer review
    r = requests.get(f"{BASE}/api/reviews/buyer/{buyer['id']}",
                     headers=_h(admin_token), timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d["total"] >= 1
    assert any(rv["rating"] == 4 for rv in d["reviews"])
    assert d["average_rating"] is not None


def test_admin_soft_delete_review(admin_token, buyer, ended_listing):
    r = requests.get(f"{BASE}/api/reviews/buyer/{buyer['id']}",
                     headers=_h(admin_token), timeout=30)
    review_id = r.json()["reviews"][0]["id"]
    rd = requests.delete(f"{BASE}/api/reviews/{review_id}",
                         headers=_h(admin_token), timeout=30)
    assert rd.status_code == 200
    # still in DB (audit) but status=removed, excluded from average
    r2 = requests.get(f"{BASE}/api/reviews/buyer/{buyer['id']}",
                      headers=_h(admin_token), timeout=30)
    d2 = r2.json()
    assert any(rv["status"] == "removed" for rv in d2["reviews"])
    assert d2["average_rating"] is None


def test_review_context_existing_after_submit(buyer, ended_listing):
    r = requests.get(f"{BASE}/api/reviews/submit-context",
                     params={"listing_id": ended_listing["id"], "role": "buyer"},
                     headers=_h(buyer["token"]), timeout=30)
    assert r.status_code == 200
    assert r.json()["existing_review"] is not None


# ────────────────────────────────────────────────────────────────────
# P1 — Messaging: pre-sale gate, suspension, threading, report queue
# ────────────────────────────────────────────────────────────────────
def test_presale_message_to_seller_allowed(buyer, seller, active_listing):
    r = requests.post(f"{BASE}/api/messages", json={
        "receiver_id": seller["id"],
        "listing_id": active_listing["id"],
        "content": "Is the chair still available for inspection?",
    }, headers=_h(buyer["token"]), timeout=30)
    assert r.status_code == 200, r.text[:300]
    # iter301 — per-listing conversation id
    conv_id = r.json()["conversation_id"]
    pair = "_".join(sorted([buyer["id"], seller["id"]]))
    assert conv_id == f"{pair}__{active_listing['id']}"


def test_presale_message_to_non_seller_blocked(buyer, outsider, active_listing):
    r = requests.post(f"{BASE}/api/messages", json={
        "receiver_id": outsider["id"],
        "listing_id": active_listing["id"],
        "content": "hello stranger",
    }, headers=_h(buyer["token"]), timeout=30)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "presale_must_message_seller"


def test_new_message_bell_notification(seller, active_listing):
    async def fetch():
        db = _db()
        return await db.notifications.find_one(
            {"user_id": seller["id"], "type": "new_message"}, {"_id": 0})
    notif = _run(fetch())
    assert notif is not None, "new_message bell notification missing"
    assert notif.get("title_fr") == "Nouveau message"


def test_messaging_suspended_enforced(buyer, seller, active_listing):
    async def toggle(flag):
        db = _db()
        await db.users.update_one({"id": buyer["id"]},
                                  {"$set": {"messaging_suspended": flag}})
    _run(toggle(True))
    try:
        r = requests.post(f"{BASE}/api/messages", json={
            "receiver_id": seller["id"],
            "listing_id": active_listing["id"],
            "content": "should be blocked",
        }, headers=_h(buyer["token"]), timeout=30)
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "messaging_suspended"
    finally:
        _run(toggle(False))


def test_report_thread_flow(buyer, seller, outsider, admin_token, active_listing):
    pair = "_".join(sorted([buyer["id"], seller["id"]]))
    conv_id = f"{pair}__{active_listing['id']}"

    # non-participant blocked
    r0 = requests.post(f"{BASE}/api/conversations/{conv_id}/report",
                       json={"reason": "spam"}, headers=_h(outsider["token"]), timeout=30)
    assert r0.status_code == 403

    # participant reports
    r1 = requests.post(f"{BASE}/api/conversations/{conv_id}/report",
                       json={"reason": "Suspected off-platform payment scam"},
                       headers=_h(seller["token"]), timeout=30)
    assert r1.status_code == 200, r1.text[:300]

    # admin queue contains it
    rq = requests.get(f"{BASE}/api/admin/messages/reported-threads",
                      params={"status": "pending"}, headers=_h(admin_token), timeout=30)
    assert rq.status_code == 200
    ids = [t["id"] for t in rq.json()["threads"]]
    assert conv_id in ids

    # resolve
    rr = requests.post(f"{BASE}/api/admin/messages/reported-threads/{conv_id}/resolve",
                       headers=_h(admin_token), timeout=30)
    assert rr.status_code == 200
    rq2 = requests.get(f"{BASE}/api/admin/messages/reported-threads",
                       params={"status": "pending"}, headers=_h(admin_token), timeout=30)
    assert conv_id not in [t["id"] for t in rq2.json()["threads"]]


def test_reply_with_explicit_conversation_id(buyer, seller, active_listing):
    pair = "_".join(sorted([buyer["id"], seller["id"]]))
    conv_id = f"{pair}__{active_listing['id']}"
    r = requests.post(f"{BASE}/api/messages", json={
        "receiver_id": buyer["id"],
        "content": "Yes — inspection Friday 2pm works.",
        "conversation_id": conv_id,
    }, headers=_h(seller["token"]), timeout=30)
    assert r.status_code == 200, r.text[:300]
    assert r.json()["conversation_id"] == conv_id


# ────────────────────────────────────────────────────────────────────
# P2 — SEO endpoints
# ────────────────────────────────────────────────────────────────────
def test_sitemap_and_robots():
    s = requests.get(f"{BASE}/sitemap.xml", timeout=30)
    assert s.status_code == 200 and "<urlset" in s.text
    rb = requests.get(f"{BASE}/robots.txt", timeout=30)
    assert rb.status_code == 200
    assert "Disallow: /admin" in rb.text and "Sitemap:" in rb.text


# ────────────────────────────────────────────────────────────────────
# P2 — Performance: pagination metadata + analytics cache
# ────────────────────────────────────────────────────────────────────
def test_marketplace_items_pagination_metadata():
    r = requests.get(f"{BASE}/api/marketplace/items", params={"limit": 2}, timeout=60)
    assert r.status_code == 200
    d = r.json()
    for key in ("items", "total", "total_count", "page", "limit"):
        assert key in d, f"missing {key}"
    assert d["page"] == 1


def test_analytics_overview_cached_60s(admin_token):
    r1 = requests.get(f"{BASE}/api/admin/analytics/overview",
                      headers=_h(admin_token), timeout=60)
    r2 = requests.get(f"{BASE}/api/admin/analytics/overview",
                      headers=_h(admin_token), timeout=60)
    assert r1.status_code == r2.status_code == 200
    # second response served from the 60s cache → identical generated_at
    assert r1.json()["generated_at"] == r2.json()["generated_at"]


# ────────────────────────────────────────────────────────────────────
# P0 — bilingual notification templates registered
# ────────────────────────────────────────────────────────────────────
def test_notification_i18n_new_kinds():
    import sys
    sys.path.insert(0, BACKEND_DIR)
    from services.notifications_i18n import build_notification
    n1 = build_notification(user_id="x", kind="new_message",
                            params={"sender_name": "Marie", "preview": "Bonjour"})
    assert n1["title_fr"] == "Nouveau message" and "Marie" in n1["message_fr"]
    n2 = build_notification(user_id="x", kind="new_review",
                            params={"reviewer_name": "Marc", "rating": 5})
    assert n2["title_fr"] == "Nouvel avis reçu"
    n3 = build_notification(user_id="x", kind="message_thread_reported",
                            params={"reporter_name": "Eve", "reason": "spam"})
    assert "signalé" in n3["title_fr"]


# ────────────────────────────────────────────────────────────────────
# Cleanup throwaway users
# ────────────────────────────────────────────────────────────────────
def test_zz_cleanup(buyer, seller, outsider):
    async def cleanup():
        db = _db()
        ids = [buyer["id"], seller["id"], outsider["id"]]
        await db.notifications.delete_many({"user_id": {"$in": ids}})
        await db.messages.delete_many({"sender_id": {"$in": ids}})
        await db.conversations.delete_many({"participants": {"$in": ids}})
    _run(cleanup())
    assert True
