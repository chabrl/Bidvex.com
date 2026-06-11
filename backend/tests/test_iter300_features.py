"""
test_iter300_features.py — iter300 feature suite
=================================================

Covers (live API on localhost:8001 + direct service calls):
  P1 Top Seller badge      — recalc job, user flag, public surfacing
  P1 Dispute resolution    — eligibility, filing, admin queue/note/escalate/resolve
  P1 Overdue auto-capture  — failure path, 3-strike bidding suspension, 403 bid
                             guard, admin lift endpoint
  P2 Analytics date range  — ?from/?to params drive range + series buckets
  P2 Follow Seller         — follow/unfollow/status/my-followed
"""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE = os.environ.get("BIDVEX_TEST_BASE", "http://localhost:8001")
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ADMIN_ID = "8940074d-da97-43ca-9a0b-c59d39411ed6"


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.text[:200]}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_token(test_admin_email, test_admin_password):
    return _login(test_admin_email, test_admin_password)


@pytest.fixture(scope="module")
def buyer():
    """Dedicated throwaway buyer (gets suspended during the overdue tests)."""
    email = f"iter300.buyer+{int(time.time())}@example.com"
    password = "Iter300Buyer!x"
    r = requests.post(f"{BASE}/api/auth/register", json={
        "email": email, "password": password, "name": "Iter300 Buyer",
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
    import asyncio  # noqa: F401
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BACKEND_DIR, ".env"))
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]


def _run(coro):
    import asyncio
    return asyncio.new_event_loop().run_until_complete(coro)


# ────────────────────────────────────────────────────────────────────
# P2 — Analytics custom date range
# ────────────────────────────────────────────────────────────────────
def test_analytics_range_params(admin_token):
    r = requests.get(f"{BASE}/api/admin/analytics/overview",
                     params={"from": "2026-06-01", "to": "2026-06-08"},
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d["range"] == {"from": "2026-06-01", "to": "2026-06-08", "days": 8}
    assert len(d["signups_per_day"]) == 8
    assert len(d["revenue_per_day"]) == 8
    assert "range" in d["gmv"] and "all_time" in d["gmv"]


def test_analytics_default_still_30_days(admin_token):
    r = requests.get(f"{BASE}/api/admin/analytics/overview",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
    d = r.json()
    assert d["range"]["days"] == 30
    assert len(d["signups_per_day"]) == 30


# ────────────────────────────────────────────────────────────────────
# P1 — Top Seller badge
# ────────────────────────────────────────────────────────────────────
def test_top_seller_recalc_and_flag(admin_token):
    r = requests.post(f"{BASE}/api/admin/analytics/top-sellers/recalculate",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert isinstance(d.get("top"), list) and len(d["top"]) >= 1
    top_ids = [t["seller_id"] for t in d["top"]]

    async def check():
        db = _db()
        flagged = [u["id"] async for u in db.users.find({"is_top_seller": True}, {"id": 1})]
        return flagged
    flagged = _run(check())
    assert set(flagged) == set(top_ids), "user flags must exactly mirror the top-5 ranking"


def test_top_seller_visible_on_storefront_and_profile(admin_token):
    top_id = ADMIN_ID  # admin owns the sold seed listings → top seller
    r = requests.get(f"{BASE}/api/storefronts/{top_id}", timeout=30)
    assert r.status_code == 200
    assert r.json()["seller"]["is_top_seller"] is True
    assert "stats" in r.json() and "followers" in r.json()["stats"]
    r2 = requests.get(f"{BASE}/api/sellers/{top_id}", timeout=30)
    assert r2.status_code == 200
    assert r2.json().get("is_top_seller") is True


def test_scheduler_jobs_registered():
    src = open(os.path.join(BACKEND_DIR, "server.py"), encoding="utf-8").read()
    assert "top_seller_recalc" in src
    assert "overdue_autocapture" in src


# ────────────────────────────────────────────────────────────────────
# P2 — Follow Seller
# ────────────────────────────────────────────────────────────────────
def test_follow_unfollow_flow(buyer):
    h = {"Authorization": f"Bearer {buyer['token']}"}
    r = requests.post(f"{BASE}/api/sellers/{ADMIN_ID}/follow", headers=h, timeout=30)
    assert r.status_code == 200 and r.json()["following"] is True

    r = requests.get(f"{BASE}/api/sellers/{ADMIN_ID}/follow-status", headers=h, timeout=30)
    assert r.json()["following"] is True and r.json()["followers_count"] >= 1

    r = requests.get(f"{BASE}/api/me/followed-sellers", headers=h, timeout=30)
    assert any(s["seller_id"] == ADMIN_ID for s in r.json()["sellers"])
    assert "is_top_seller" in r.json()["sellers"][0]

    r = requests.delete(f"{BASE}/api/sellers/{ADMIN_ID}/follow", headers=h, timeout=30)
    assert r.status_code == 200 and r.json()["following"] is False


def test_cannot_follow_self(admin_token):
    r = requests.post(f"{BASE}/api/sellers/{ADMIN_ID}/follow",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
    assert r.status_code == 400


def test_follower_gets_notified_on_new_listing(buyer):
    """Direct fan-out service test: follower receives the bilingual notification."""
    h = {"Authorization": f"Bearer {buyer['token']}"}
    requests.post(f"{BASE}/api/sellers/{ADMIN_ID}/follow", headers=h, timeout=30)

    async def fanout():
        db = _db()
        from services.follower_notify import notify_followers
        return await notify_followers(
            db, seller_id=ADMIN_ID, listing_id="iter300-test-listing",
            listing_title="Iter300 Fanout Item", section="marketplace")
    out = _run(fanout())
    assert out["notified"] >= 1, out

    r = requests.get(f"{BASE}/api/notifications", headers=h, timeout=30)
    notifs = r.json()["notifications"]
    match = [n for n in notifs if n.get("type") == "followed_seller_new_listing"]
    assert match, "follower should have the followed_seller_new_listing notification"
    assert match[0]["title_fr"] and match[0]["message_fr"]
    # cleanup
    requests.delete(f"{BASE}/api/sellers/{ADMIN_ID}/follow", headers=h, timeout=30)


# ────────────────────────────────────────────────────────────────────
# P1 — Dispute resolution (full lifecycle)
# ────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def disputed_listing(buyer):
    """Seed a payment_collected listing won by the throwaway buyer."""
    lid = f"iter300-dispute-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    async def seed():
        db = _db()
        await db.listings.insert_one({
            "id": lid, "title": "Iter300 Dispute Test Item",
            "seller_id": ADMIN_ID, "status": "sold",
            "final_price": 120.0, "current_price": 120.0,
            "winner_id": buyer["id"],
            "payment_status": "payment_collected",
            "payment_collected_at": now.isoformat(),
            "sold_at": now.isoformat(),
            "created_at": now.isoformat(),
        })
    _run(seed())
    yield lid

    async def cleanup():
        db = _db()
        await db.listings.delete_one({"id": lid})
        await db.disputes.delete_many({"listing_id": lid})
    _run(cleanup())


def test_dispute_full_lifecycle(buyer, admin_token, disputed_listing):
    bh = {"Authorization": f"Bearer {buyer['token']}"}
    ah = {"Authorization": f"Bearer {admin_token}"}

    # 1. eligibility — buyer is eligible within 7-day window
    r = requests.get(f"{BASE}/api/disputes/eligibility/{disputed_listing}", headers=bh, timeout=30)
    assert r.status_code == 200 and r.json()["eligible"] is True, r.text[:300]
    assert r.json()["role"] == "buyer"

    # 2. file
    r = requests.post(f"{BASE}/api/disputes/file", headers=bh, json={
        "listing_id": disputed_listing, "section": "marketplace",
        "reason_category": "item_not_as_described",
        "details": "Item arrived damaged."}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    dispute_id = r.json()["dispute"]["id"]
    assert "internal_notes" not in r.json()["dispute"]  # never exposed to parties

    # 3. duplicate filing blocked
    r = requests.post(f"{BASE}/api/disputes/file", headers=bh, json={
        "listing_id": disputed_listing, "section": "marketplace",
        "reason_category": "other", "details": "again"}, timeout=30)
    assert r.status_code == 409

    # 4. invalid reason rejected
    r = requests.post(f"{BASE}/api/disputes/file", headers=bh, json={
        "listing_id": "whatever", "section": "marketplace",
        "reason_category": "bogus", "details": ""}, timeout=30)
    assert r.status_code == 422

    # 5. visible in /my (without internal notes)
    r = requests.get(f"{BASE}/api/disputes/my", headers=bh, timeout=30)
    mine = [d for d in r.json()["disputes"] if d["id"] == dispute_id]
    assert mine and "internal_notes" not in mine[0]

    # 6. admin queue
    r = requests.get(f"{BASE}/api/admin/disputes/queue?status=open", headers=ah, timeout=30)
    row = [d for d in r.json()["disputes"] if d["id"] == dispute_id]
    assert row, "dispute must appear in the admin queue"
    assert row[0]["buyer_name"] and row[0]["seller_name"]
    assert row[0]["hammer_price"] == 120.0

    # 7. internal note + escalate
    r = requests.post(f"{BASE}/api/admin/disputes/{dispute_id}/note",
                      headers=ah, json={"note": "Checked photos."}, timeout=30)
    assert r.status_code == 200
    r = requests.post(f"{BASE}/api/admin/disputes/{dispute_id}/escalate",
                      headers=ah, json={"note": "Needs senior review."}, timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "escalated"

    # 8. resolve — release to seller
    r = requests.post(f"{BASE}/api/admin/disputes/{dispute_id}/resolve",
                      headers=ah, json={"action": "release_to_seller",
                                        "note": "Buyer claim unsubstantiated."}, timeout=30)
    assert r.status_code == 200 and r.json()["outcome"] == "release_to_seller"

    # 9. resolving twice → 409; invalid action → 422
    r = requests.post(f"{BASE}/api/admin/disputes/{dispute_id}/resolve",
                      headers=ah, json={"action": "refund_buyer", "note": "duplicate attempt"}, timeout=30)
    assert r.status_code == 409
    r = requests.post(f"{BASE}/api/admin/disputes/{dispute_id}/resolve",
                      headers=ah, json={"action": "nope", "note": "xxxxx"}, timeout=30)
    assert r.status_code == 422

    # 10. both parties got the resolution notification
    r = requests.get(f"{BASE}/api/notifications", headers=bh, timeout=30)
    assert any(n.get("type") == "dispute_resolved" for n in r.json()["notifications"])

    # 11. eligibility now reports the resolved dispute
    r = requests.get(f"{BASE}/api/disputes/eligibility/{disputed_listing}", headers=bh, timeout=30)
    assert r.json()["already_disputed"] is True and r.json()["dispute_status"] == "resolved"


def test_dispute_requires_party(admin_token, buyer, disputed_listing):
    """A random third user can't file on someone else's transaction."""
    email = f"iter300.outsider+{int(time.time())}@example.com"
    r = requests.post(f"{BASE}/api/auth/register", json={
        "email": email, "password": "Outsider300!x", "name": "Outsider",
        "terms_agreed": True, "ai_disclosure_consent": True}, timeout=30)
    tok = r.json().get("access_token") or r.json().get("token")
    r = requests.post(f"{BASE}/api/disputes/file",
                      headers={"Authorization": f"Bearer {tok}"},
                      json={"listing_id": disputed_listing, "section": "marketplace",
                            "reason_category": "other", "details": "not mine"}, timeout=30)
    assert r.status_code == 403


# ────────────────────────────────────────────────────────────────────
# P1 — Overdue auto-capture + bidding suspension + admin lift
# ────────────────────────────────────────────────────────────────────
def test_overdue_autocapture_three_strikes_and_suspension(buyer, admin_token):
    lid = f"iter300-overdue-{uuid.uuid4().hex[:8]}"
    old = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()

    async def seed():
        db = _db()
        await db.listings.insert_one({
            "id": lid, "title": "Iter300 Overdue Item",
            "seller_id": ADMIN_ID, "status": "sold",
            "final_price": 80.0, "current_price": 80.0,
            "winner_id": buyer["id"],
            "payment_status": "overdue",
            "overdue_at": old, "sold_at": old, "created_at": old,
        })
        # iter302 — autocapture only fires with standing payment
        # authorization consent on the winning buyer's bid.
        await db.bids.insert_one({
            "id": str(uuid.uuid4()), "listing_id": lid,
            "bidder_id": buyer["id"], "amount": 80.0,
            "payment_authorization_consented": True,
            "created_at": old,
        })
    _run(seed())

    async def tick_and_get(attempt_reset=False):
        db = _db()
        if attempt_reset:  # bypass the 55-min retry gate between attempts
            await db.listings.update_one(
                {"id": lid}, {"$set": {"payment_last_attempt_at": old}})
        from services.overdue_autocapture import process_overdue_autocapture
        out = await process_overdue_autocapture(db)
        doc = await db.listings.find_one({"id": lid}, {"_id": 0})
        usr = await db.users.find_one({"id": buyer["id"]}, {"_id": 0, "bidding_suspended": 1})
        return out, doc, usr

    # attempt 1 — no saved payment method → payment_overdue (iter302 semantics)
    out, doc, usr = _run(tick_and_get())
    assert doc["payment_status"] == "payment_overdue", doc.get("payment_status")
    assert doc["payment_retry_attempts"] == 1
    assert not (usr or {}).get("bidding_suspended")

    # attempts 2 + 3 → suspension
    _run(tick_and_get(attempt_reset=True))
    out, doc, usr = _run(tick_and_get(attempt_reset=True))
    assert doc["payment_retry_attempts"] == 3
    assert (usr or {}).get("bidding_suspended") is True

    # buyer notifications include the final warning + suspension
    bh = {"Authorization": f"Bearer {buyer['token']}"}
    r = requests.get(f"{BASE}/api/notifications?limit=25", headers=bh, timeout=30)
    types = {n.get("type") for n in r.json()["notifications"]}
    assert "payment_final_warning" in types
    assert "bidding_suspended" in types

    # ── bid guard: suspended buyer gets 403 on the marketplace bid endpoint ──
    r = requests.post(f"{BASE}/api/bids", headers=bh,
                      json={"listing_id": lid, "amount": 999}, timeout=30)
    assert r.status_code == 403, f"expected 403 for suspended bidder, got {r.status_code}: {r.text[:200]}"
    assert "bidding_suspended" in r.text

    # ── admin lifts the suspension ──
    ah = {"Authorization": f"Bearer {admin_token}"}
    r = requests.post(f"{BASE}/api/admin/users/{buyer['id']}/bidding-suspension?suspended=false",
                      headers=ah, timeout=30)
    assert r.status_code == 200 and r.json()["bidding_suspended"] is False

    async def check_lifted():
        db = _db()
        u = await db.users.find_one({"id": buyer["id"]}, {"_id": 0, "bidding_suspended": 1})
        await db.listings.delete_one({"id": lid})  # cleanup
        await db.bids.delete_many({"listing_id": lid})
        return u
    u = _run(check_lifted())
    assert u.get("bidding_suspended") is False

    r = requests.get(f"{BASE}/api/notifications?limit=10", headers=bh, timeout=30)
    assert any(n.get("type") == "bidding_suspension_lifted" for n in r.json()["notifications"])
