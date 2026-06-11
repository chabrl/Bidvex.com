"""
test_iter302_settlement.py — iter302 settlement + payouts regression suite
==========================================================================

Covers (live API on localhost:8001 + direct DB seeding via pymongo):
  Directive 1 — GET /api/settlement/panel/{id} seller/admin gate, winner
                contact payload, amounts math (2.5% fee), reminder
                endpoint gate + 24h cooldown
  Directive 2 — GET /api/settlement/settle-context/{id} winner-only gate,
                POST /api/settlement/settle winner-only gate + no-card 400,
                GET /api/settlement/connect/status shape,
                GET /api/dashboard/buyer surfaces pickup_code only to winner
  Directive 3 — POST /api/vehicle-multi-lot-auctions enforces the 60s
                per-lot duration floor (422 below / 200 at minimum)
  QA gates    — winner PII not exposed to non-sellers at the API level;
                pickup code gated to buyer (+admin) on
                GET /api/transactions/{id}/pickup-code
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

BASE = os.environ.get("BIDVEX_TEST_BASE", "http://localhost:8001")
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(BACKEND_DIR, ".env"))

LISTING_ID = f"iter302-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def db():
    client = MongoClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.text[:200]}"
    return r.json().get("access_token") or r.json().get("token")


def _register(prefix):
    email = f"{prefix}+{uuid.uuid4().hex[:8]}@example.com"
    password = "Iter302Test!x"
    r = requests.post(f"{BASE}/api/auth/register", json={
        "email": email, "password": password, "name": f"Iter302 {prefix}",
        "terms_agreed": True, "ai_disclosure_consent": True}, timeout=30)
    assert r.status_code in (200, 201), r.text[:200]
    token = r.json().get("access_token") or r.json().get("token")
    uid = (r.json().get("user") or {}).get("id")
    return {"email": email, "token": token, "id": uid}


@pytest.fixture(scope="module")
def admin_token(test_admin_email, test_admin_password):
    return _login(test_admin_email, test_admin_password)


@pytest.fixture(scope="module")
def admin_id(db, test_admin_email):
    return db.users.find_one({"email": test_admin_email}, {"id": 1})["id"]


@pytest.fixture(scope="module")
def winner(db):
    u = _register("iter302winner")
    yield u
    db.users.delete_one({"id": u["id"]})


@pytest.fixture(scope="module")
def outsider(db):
    u = _register("iter302outsider")
    yield u
    db.users.delete_one({"id": u["id"]})


@pytest.fixture(scope="module")
def seeded_listing(db, admin_id, winner):
    now = datetime.now(timezone.utc)
    doc = {
        "id": LISTING_ID,
        "title": "iter302 pytest settlement item",
        "description": "test", "category": "Electronics",
        "condition": "good", "location": "Montreal, QC",
        "seller_id": admin_id, "winner_id": winner["id"],
        "status": "sold", "payment_status": "pending_payment",
        "final_price": 400.0, "current_price": 400.0,
        "starting_price": 100.0, "images": [],
        "city": "Montreal", "region": "QC", "country": "CA",
        "auction_end_date": (now - timedelta(days=1)).isoformat(),
        "ended_at": (now - timedelta(days=1)).isoformat(),
        "sold_at": (now - timedelta(days=1)).isoformat(),
        "payment_deadline": (now + timedelta(days=2)).isoformat(),
        "created_at": (now - timedelta(days=5)).isoformat(),
        "views": 1, "bid_count": 1,
    }
    db.listings.delete_one({"id": LISTING_ID})
    db.listings.insert_one(doc)
    yield doc
    db.listings.delete_one({"id": LISTING_ID})
    db.bids.delete_many({"listing_id": LISTING_ID})


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


# ────────────────────────────────────────────────────────────────────
# Directive 1 — settlement panel (seller view)
# ────────────────────────────────────────────────────────────────────

def test_panel_returns_winner_and_amounts_for_seller(seeded_listing, admin_token, winner):
    r = requests.get(f"{BASE}/api/settlement/panel/{LISTING_ID}",
                     headers=_auth(admin_token), timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d["winner"]["id"] == winner["id"]
    assert d["winner"]["email"] == winner["email"]
    assert d["hammer_price"] == 400.0
    assert d["platform_fee"] == 10.0            # 2.5 %
    assert d["total_due"] == 410.0
    assert d["net_payout"] == 390.0
    assert d["payment_status"] == "pending_payment"
    assert "reminder_available" in d


def test_panel_403_for_non_seller(seeded_listing, winner, outsider):
    """QA gate — winner PII must NOT leak to anyone but seller/admin."""
    for tok in (winner["token"], outsider["token"]):
        r = requests.get(f"{BASE}/api/settlement/panel/{LISTING_ID}",
                         headers=_auth(tok), timeout=30)
        assert r.status_code == 403, f"expected 403, got {r.status_code}"


def test_panel_404_unknown_listing(admin_token):
    r = requests.get(f"{BASE}/api/settlement/panel/does-not-exist-xyz",
                     headers=_auth(admin_token), timeout=30)
    assert r.status_code == 404


def test_remind_gate_and_cooldown(db, seeded_listing, admin_token, outsider):
    # Non-seller → 403
    r = requests.post(f"{BASE}/api/settlement/panel/{LISTING_ID}/remind",
                      headers=_auth(outsider["token"]), timeout=30)
    assert r.status_code == 403
    # Pre-stamp a recent manual reminder → seller hits the 24h cooldown (429)
    db.listings.update_one(
        {"id": LISTING_ID},
        {"$set": {"manual_payment_reminder_sent_at":
                  datetime.now(timezone.utc).isoformat()}})
    r = requests.post(f"{BASE}/api/settlement/panel/{LISTING_ID}/remind",
                      headers=_auth(admin_token), timeout=30)
    assert r.status_code == 429, r.text[:200]
    detail = r.json()["detail"]
    assert detail["code"] == "reminder_cooldown"
    assert "message_fr" in detail
    db.listings.update_one({"id": LISTING_ID},
                           {"$unset": {"manual_payment_reminder_sent_at": ""}})


# ────────────────────────────────────────────────────────────────────
# Directive 2 — buyer settle flow + connect status
# ────────────────────────────────────────────────────────────────────

def test_settle_context_winner_only(seeded_listing, winner, outsider, admin_token):
    r = requests.get(f"{BASE}/api/settlement/settle-context/{LISTING_ID}",
                     headers=_auth(winner["token"]), timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d["already_paid"] is False
    assert d["total_due"] == 410.0
    # seller and outsider both blocked
    for tok in (admin_token, outsider["token"]):
        r2 = requests.get(f"{BASE}/api/settlement/settle-context/{LISTING_ID}",
                          headers=_auth(tok), timeout=30)
        assert r2.status_code == 403


def test_settle_requires_saved_card(seeded_listing, winner):
    r = requests.post(f"{BASE}/api/settlement/settle/{LISTING_ID}",
                      headers=_auth(winner["token"]), timeout=30)
    assert r.status_code == 400, r.text[:300]
    assert r.json()["detail"]["code"] == "no_payment_method"


def test_settle_403_for_non_winner(seeded_listing, outsider):
    r = requests.post(f"{BASE}/api/settlement/settle/{LISTING_ID}",
                      headers=_auth(outsider["token"]), timeout=30)
    assert r.status_code == 403


def test_connect_status_shape(winner):
    r = requests.get(f"{BASE}/api/settlement/connect/status",
                     headers=_auth(winner["token"]), timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["connected"] is False
    assert d["payouts_enabled"] is False


def test_buyer_dashboard_surfaces_pickup_code_to_winner_only(
        db, seeded_listing, winner, outsider):
    code = "BVX-TEST302X"
    db.listings.update_one({"id": LISTING_ID},
                           {"$set": {"pickup_code": code,
                                     "payment_status": "payment_collected"}})
    db.bids.insert_one({
        "id": str(uuid.uuid4()), "listing_id": LISTING_ID,
        "bidder_id": winner["id"], "amount": 400.0,
        "payment_authorization_consented": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        r = requests.get(f"{BASE}/api/dashboard/buyer",
                         headers=_auth(winner["token"]), timeout=30)
        assert r.status_code == 200
        rows = [w for w in r.json().get("won_items_detail", [])
                if w["listing_id"] == LISTING_ID]
        assert rows and rows[0]["pickup_code"] == code
        # outsider's dashboard must NOT contain this listing at all
        r2 = requests.get(f"{BASE}/api/dashboard/buyer",
                          headers=_auth(outsider["token"]), timeout=30)
        assert all(w["listing_id"] != LISTING_ID
                   for w in r2.json().get("won_items_detail", []))
    finally:
        db.listings.update_one(
            {"id": LISTING_ID},
            {"$set": {"payment_status": "pending_payment"},
             "$unset": {"pickup_code": ""}})


def test_transaction_pickup_code_gated_to_buyer(db, winner, outsider):
    """QA gate — pickup code endpoint blocks anyone but the buyer/admin."""
    txn_id = f"iter302-txn-{uuid.uuid4().hex[:8]}"
    db.transactions.insert_one({
        "id": txn_id, "buyer_id": winner["id"],
        "pickup_code": "BVX-GATE302X",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        r = requests.get(f"{BASE}/api/transactions/{txn_id}/pickup-code",
                         headers=_auth(winner["token"]), timeout=30)
        assert r.status_code == 200
        assert r.json()["pickup_code"] == "BVX-GATE302X"
        r2 = requests.get(f"{BASE}/api/transactions/{txn_id}/pickup-code",
                          headers=_auth(outsider["token"]), timeout=30)
        assert r2.status_code == 403
    finally:
        db.transactions.delete_one({"id": txn_id})


# ────────────────────────────────────────────────────────────────────
# Directive 3 — 60s per-lot duration floor (server-side)
# ────────────────────────────────────────────────────────────────────

def _ml_payload(duration):
    return {
        "title": f"iter302 duration test {uuid.uuid4().hex[:6]}",
        "timing_mode": "sequential",
        "start_time": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "lot_duration_seconds": duration,
        "stagger_offset_seconds": 60,
        "submission_intent": "draft",
        "lots": [{
            "vin": f"TESTVIN{uuid.uuid4().hex[:10].upper()}",
            "year": 2020, "make": "Ford", "model": "F-350",
            "title": "duration test lot", "mileage": 1,
            "body_type": "truck", "transmission": "automatic",
            "fuel_type": "diesel", "drivetrain": "4wd",
            "ownership_status": "owned", "title_status": "clean",
            "lien_status": "clear", "location_city": "Toronto",
            "location_province": "ON", "starting_price": 1000,
            "bid_increment": 100,
        }],
    }


def test_multilot_duration_below_60_rejected(admin_token):
    r = requests.post(f"{BASE}/api/vehicle-multi-lot-auctions",
                      json=_ml_payload(59), headers=_auth(admin_token), timeout=30)
    assert r.status_code == 422, r.text[:300]


def test_multilot_duration_60_accepted(db, admin_token):
    r = requests.post(f"{BASE}/api/vehicle-multi-lot-auctions",
                      json=_ml_payload(60), headers=_auth(admin_token), timeout=30)
    assert r.status_code == 200, r.text[:300]
    eid = r.json()["id"]
    db.vehicle_multi_lot_auctions.delete_one({"id": eid})
