"""
iter287 — Vehicle Auto-Bid Engine + Admin Delete Privileges.

Two launch-critical features for feature-parity with storage / marketplace
sections:

  1. Vehicle Auto-Bid (Proxy Bidding) Engine
     • POST   /api/vehicles/{id}/auto-bid?max_bid=<float>   set/update
     • DELETE /api/vehicles/{id}/auto-bid                   deactivate
     • GET    /api/vehicles/auto-bid/mine                   list mine
     The proxy bot runs inside `place_vehicle_bid` after every manual
     bid commits, mirrors the marketplace `_process_auto_bids` flow,
     and targets `db.vehicle_listings` + `db.vehicle_bids` +
     `db.vehicle_auto_bids`.

  2. Admin: Full Vehicle Listing Management
     • DELETE /api/admin/vehicles/{id}            hard delete (cascade)
     • DELETE /api/admin/vehicles/{id}?soft=true  soft delete (cancel)
     Hard delete tears down vehicle_listings, listings (cross-mirror),
     vehicle_bids, vehicle_auto_bids, watchlists, and writes a row to
     admin_audit_log. Non-admin callers get 403 admin_required.

Business constraints honoured:
  • Vehicle Buyer Premium remains 0% (fee_calculator untouched)
  • Platform Fee remains 2.5%
  • Vehicle security deposit unchanged (max($200, 10%))
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

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


@pytest.fixture(scope="module")
def admin_token():
    """Log in the seeded admin (with retry — auth endpoint can rate-limit
    on hot regression sweeps).

    iter287 — Use a longer back-off because the iter283_final_prelaunch
    + iter286 suites pummel /auth/login before iter287 runs. Five-step
    exponential backoff caps at ~30s total which clears the typical
    minute-window brute-force gate.
    """
    import time as _t
    last = None
    for _attempt in range(8):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
            timeout=15,
        )
        last = r
        if r.status_code == 200:
            return r.json().get("access_token") or r.json().get("token")
        # 429 → respect the brute-force window; 5xx → transient
        _t.sleep(min(2 ** _attempt, 16))
    raise AssertionError(f"admin login failed: {last.status_code} {last.text[:200]}")


@pytest.fixture(scope="module")
def buyer_token():
    """Stable iter286 test buyer (non-admin, non-broker)."""
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "iter286-buyer-1780788613@test.bidvex.com", "password": "TestPassw0rd!"},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip("iter286 stable test buyer unavailable — skip iter287 auth flows.")
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture()
def seeded_active_vehicle(db):
    """Active vehicle in `db.vehicle_listings` with a fresh end_time so
    auto-bid endpoints don't bounce on `auction not active`."""
    vid = f"iter287-v-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    doc = {
        "id":                vid,
        "seller_id":         "iter287-seller",
        "title":             "iter287 test vehicle",
        "make":              "Toyota",
        "model":             "Camry",
        "year":              2020,
        "vin":               "1HGBH41JXMN109186",
        "starting_price":    1000.0,
        "current_bid":       1000.0,
        "bid_increment":     100.0,
        "status":            "active",          # VehicleListingStatus.ACTIVE
        "auction_access":    "public_individual",
        "visibility":        "public",
        "end_time":          now + timedelta(days=3),
        "start_time":        now,
        "category_id":       "passenger_cars",
        "location_province": "ON",
        "requires_deposit":  False,
        "deposit_amount":    0,
        "reserve_price":     None,
        "highest_bidder_id": None,
        "media": [{"id": "m1", "type": "photo", "url": "https://example.com/iter287.jpg", "category": "front"}],
        "created_at":        now.isoformat(),
    }
    db.vehicle_listings.insert_one(doc.copy())
    yield doc
    # Cleanup — leave nothing behind even if a test fails.
    db.vehicle_listings.delete_one({"id": vid})
    db.vehicle_bids.delete_many({"vehicle_id": vid})
    db.vehicle_auto_bids.delete_many({"vehicle_id": vid})
    db.watchlists.delete_many({"listing_id": vid})
    db.listings.delete_one({"id": vid})


# ── TASK 1 — Vehicle Auto-Bid Engine ──────────────────────────────────


def test_autobid_setup_persists_max_bid(seeded_active_vehicle, buyer_token, db):
    """POST /vehicles/{id}/auto-bid creates the proxy row."""
    vid = seeded_active_vehicle["id"]
    r = requests.post(
        f"{BASE_URL}/api/vehicles/{vid}/auto-bid?max_bid=5000",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vehicle_id"] == vid
    assert body["max_bid"] == 5000.0
    assert body["is_active"] is True
    assert body["updated"] is False
    # Persisted with the right shape.
    row = db.vehicle_auto_bids.find_one({"vehicle_id": vid, "is_active": True})
    assert row is not None
    assert row["max_bid"] == 5000.0


def test_autobid_setup_is_idempotent_and_updates_existing(seeded_active_vehicle, buyer_token, db):
    """Calling POST twice updates the existing row in place."""
    vid = seeded_active_vehicle["id"]
    r1 = requests.post(
        f"{BASE_URL}/api/vehicles/{vid}/auto-bid?max_bid=3500",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=10,
    )
    assert r1.status_code == 200, r1.text
    r2 = requests.post(
        f"{BASE_URL}/api/vehicles/{vid}/auto-bid?max_bid=7500",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=10,
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["updated"] is True
    assert body["max_bid"] == 7500.0
    # Exactly one active row — never duplicated.
    rows = list(db.vehicle_auto_bids.find({"vehicle_id": vid, "is_active": True}))
    assert len(rows) == 1
    assert rows[0]["max_bid"] == 7500.0


def test_autobid_rejects_max_bid_below_current(seeded_active_vehicle, buyer_token):
    """`max_bid` must exceed the current bid (starting_price=$1000 here)."""
    vid = seeded_active_vehicle["id"]
    r = requests.post(
        f"{BASE_URL}/api/vehicles/{vid}/auto-bid?max_bid=500",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=10,
    )
    assert r.status_code == 400, r.text
    assert "current bid" in r.json().get("detail", "").lower()


def test_autobid_rejects_unknown_vehicle(buyer_token):
    r = requests.post(
        f"{BASE_URL}/api/vehicles/iter287-unknown/auto-bid?max_bid=5000",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=10,
    )
    assert r.status_code == 404


def test_autobid_delete_deactivates_row(seeded_active_vehicle, buyer_token, db):
    vid = seeded_active_vehicle["id"]
    requests.post(
        f"{BASE_URL}/api/vehicles/{vid}/auto-bid?max_bid=5000",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=10,
    )
    r = requests.delete(
        f"{BASE_URL}/api/vehicles/{vid}/auto-bid",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    row = db.vehicle_auto_bids.find_one({"vehicle_id": vid})
    assert row is not None
    assert row["is_active"] is False


def test_autobid_get_mine_returns_active_rows(seeded_active_vehicle, buyer_token):
    vid = seeded_active_vehicle["id"]
    requests.post(
        f"{BASE_URL}/api/vehicles/{vid}/auto-bid?max_bid=6500",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=10,
    )
    r = requests.get(
        f"{BASE_URL}/api/vehicles/auto-bid/mine",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 1
    assert any(ab["vehicle_id"] == vid for ab in body["auto_bids"])


def test_autobid_processor_function_exists():
    """The proxy processor must be importable and async."""
    import inspect
    from routes.vehicles import _process_vehicle_auto_bids
    assert inspect.iscoroutinefunction(_process_vehicle_auto_bids)


# ── TASK 2 — Admin Delete Privileges ─────────────────────────────────


def test_admin_delete_vehicle_hard_cascades_all_collections(seeded_active_vehicle, admin_token, db, buyer_token):
    """Hard delete must wipe vehicle_listings + bids + auto_bids."""
    vid = seeded_active_vehicle["id"]
    # Seed an auto-bid + watchlist entry so cascade is exercised.
    requests.post(
        f"{BASE_URL}/api/vehicles/{vid}/auto-bid?max_bid=5000",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=10,
    )
    db.vehicle_bids.insert_one({"id": str(uuid.uuid4()), "vehicle_id": vid, "bidder_id": "x", "amount": 1100})
    db.watchlists.insert_one({"user_id": "x", "listing_id": vid})

    r = requests.delete(
        f"{BASE_URL}/api/admin/vehicles/{vid}",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["soft"] is False
    counts = body["deleted"]
    assert counts["vehicle_listings"] == 1
    assert counts["vehicle_bids"] >= 1
    assert counts["vehicle_auto_bids"] >= 1
    assert counts["watchlists"] >= 1
    # Verify the listing is gone.
    assert db.vehicle_listings.find_one({"id": vid}) is None
    assert db.vehicle_bids.find_one({"vehicle_id": vid}) is None
    assert db.vehicle_auto_bids.find_one({"vehicle_id": vid}) is None


def test_admin_delete_vehicle_soft_marks_cancelled(seeded_active_vehicle, admin_token, db):
    """Soft delete must flip status + is_visible without removing the doc."""
    vid = seeded_active_vehicle["id"]
    r = requests.delete(
        f"{BASE_URL}/api/admin/vehicles/{vid}?soft=true",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["soft"] is True
    doc = db.vehicle_listings.find_one({"id": vid})
    assert doc is not None  # not removed
    assert doc["status"] == "cancelled"
    assert doc["is_visible"] is False
    assert "deleted_at" in doc


def test_admin_delete_vehicle_403s_for_non_admin(seeded_active_vehicle, buyer_token):
    """Non-admins MUST receive 403 — no leakage of the destructive action."""
    vid = seeded_active_vehicle["id"]
    r = requests.delete(
        f"{BASE_URL}/api/admin/vehicles/{vid}",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=10,
    )
    assert r.status_code == 403, r.text


def test_admin_delete_vehicle_404s_for_unknown_id(admin_token):
    r = requests.delete(
        f"{BASE_URL}/api/admin/vehicles/iter287-unknown",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10,
    )
    assert r.status_code == 404


# ── Business constraints — unchanged ──────────────────────────────────


def test_vehicle_platform_fee_unchanged_by_iter287():
    """Hard guard — the iter287 auto-bid + admin-delete work must
    NOT alter the vehicle fee math. The fee calculator still reports
    the 2.5% platform fee under `buyer_premium_rate` (legacy internal
    label) and the UI continues to render it as "Platform Fee" with
    Buyer Premium hidden (per iter283 spec)."""
    from services.fee_calculator import calculate_fee
    res = calculate_fee(
        hammer_price=10000.0,
        auction_type="vehicle",
        seller_account_type="vehicle_dealer",
        buyer_account_type="individual",
    )
    # Platform fee on vehicles is 2.5% (= $250 on $10,000 hammer).
    assert float(res["buyer_premium_rate"]) == 0.025, res
    assert 240 <= float(res["buyer_premium"]) <= 260, res
    # Seller commission on vehicle dealers is $0 per transaction
    # (annual flat fee billed separately).
    assert float(res["seller_commission"]) == 0.0, res
