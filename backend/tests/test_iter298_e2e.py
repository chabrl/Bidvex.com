"""
iter298 E2E HTTP test suite — verifies BUG1..BUG5 surfaces against the LIVE preview backend.
Per main-agent guidance, login ONCE and reuse the token everywhere (rate-limit 5/min).
"""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback from frontend env
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")
                break

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASS = "Anderosli123!@#"

MONGO_URL = None
DB_NAME = None
with open("/app/backend/.env") as f:
    for ln in f:
        if ln.startswith("MONGO_URL="):
            MONGO_URL = ln.split("=", 1)[1].strip()
        elif ln.startswith("DB_NAME="):
            DB_NAME = ln.split("=", 1)[1].strip()


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=20,
    )
    if r.status_code == 429:
        time.sleep(70)
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
            timeout=20,
        )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    tok = body.get("token") or body.get("access_token")
    assert tok, f"no token in body: {body}"
    return tok


@pytest.fixture(scope="module")
def admin_id(admin_token):
    r = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text[:200]
    return r.json().get("id") or r.json().get("user_id") or r.json().get("_id")


@pytest.fixture(scope="module")
def mongo_db():
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]
    yield db
    client.close()


# ===================== BUG1 — Ending Soon endpoints =====================
class TestBug1EndingSoon:
    def test_marketplace_ending_soon(self):
        r = requests.get(f"{BASE_URL}/api/marketplace/items?ending_soon=true", timeout=20)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        items = data if isinstance(data, list) else (data.get("items") or data.get("data") or [])
        print(f"ending_soon marketplace items count={len(items)}")
        titles = [i.get("title", "") for i in items]
        print("titles:", titles)
        # Must EXCLUDE iPad (>24h out)
        assert not any("iPad" in t for t in titles), f"iPad should be excluded: {titles}"
        # Each remaining must be within 24h
        now = datetime.now(timezone.utc)
        for it in items:
            end = it.get("auction_end_date") or it.get("end_date")
            if end:
                try:
                    end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                    delta_h = (end_dt - now).total_seconds() / 3600
                    assert -1 <= delta_h <= 24.5, f"{it.get('title')} ends in {delta_h}h"
                except ValueError:
                    pass

    def test_multi_item_listings_ending_soon(self):
        r = requests.get(f"{BASE_URL}/api/multi-item-listings?ending_soon=true", timeout=20)
        assert r.status_code == 200, r.text[:200]

    def test_vehicles_ending_soon(self):
        r = requests.get(f"{BASE_URL}/api/vehicles?ending_soon=true", timeout=20)
        assert r.status_code == 200, r.text[:200]


# ===================== BUG2 — Relist endpoint =====================
class TestBug2Relist:
    @pytest.fixture
    def ended_no_sale_listing(self, mongo_db, admin_id):
        lid = f"TEST_iter298_relist_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        doc = {
            "id": lid,
            "title": "TEST iter298 Relist Source",
            "description": "test listing for relist endpoint",
            "category": "Tools",
            "status": "ended_no_sale",
            "seller_id": admin_id,
            "starting_price": 50.0,
            "current_price": 50.0,
            "bid_count": 0,
            "images": [],
            "auction_start_date": (now - timedelta(days=2)).isoformat(),
            "auction_end_date": (now - timedelta(hours=2)).isoformat(),
            "created_at": (now - timedelta(days=3)).isoformat(),
            "iter298_test": True,
        }
        mongo_db.listings.insert_one(doc)
        yield lid
        # cleanup: this listing + any relisted copy
        relisted_id = None
        try:
            srcdoc = mongo_db.listings.find_one({"id": lid}) or {}
            relisted_id = srcdoc.get("relisted_to")
        except Exception:
            pass
        mongo_db.listings.delete_many({"id": lid})
        if relisted_id:
            mongo_db.listings.delete_many({"id": relisted_id})
        mongo_db.listings.delete_many({"iter298_test": True})

    def test_relist_now_success(self, ended_no_sale_listing, admin_token, mongo_db):
        r = requests.post(
            f"{BASE_URL}/api/listings/{ended_no_sale_listing}/relist?mode=now",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        body = r.json()
        new_id = body.get("new_listing_id") or body.get("listing_id") or body.get("id")
        assert new_id, f"no new_listing_id in: {body}"
        # Verify new listing exists, is active, bids reset
        new_doc = mongo_db.listings.find_one({"id": new_id})
        assert new_doc, f"new listing {new_id} not found"
        assert new_doc.get("status") == "active"
        assert new_doc.get("bid_count", 0) == 0
        assert float(new_doc.get("current_price", 0)) == float(new_doc.get("starting_price", 0))
        # Source must have relisted_to pointer
        src = mongo_db.listings.find_one({"id": ended_no_sale_listing})
        assert src.get("relisted_to") == new_id

        # Second relist returns 409
        r2 = requests.post(
            f"{BASE_URL}/api/listings/{ended_no_sale_listing}/relist?mode=now",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30,
        )
        assert r2.status_code == 409, f"expected 409 second relist, got {r2.status_code}: {r2.text[:200]}"

    def test_relist_non_owner_admin_override(self, mongo_db, admin_token):
        """Per relist.py L116: admin role bypasses ownership check (intentional override)."""
        lid = f"TEST_iter298_relist_nonown_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        mongo_db.listings.insert_one({
            "id": lid,
            "title": "TEST nonown relist",
            "status": "ended_no_sale",
            "seller_id": "some-other-user-id-xyz-not-admin",
            "starting_price": 10.0,
            "current_price": 10.0,
            "bid_count": 0,
            "images": [],
            "category": "Tools",
            "auction_start_date": (now - timedelta(days=2)).isoformat(),
            "auction_end_date": (now - timedelta(hours=2)).isoformat(),
            "iter298_test": True,
        })
        new_id = None
        try:
            r = requests.post(
                f"{BASE_URL}/api/listings/{lid}/relist?mode=now",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=20,
            )
            # admin override is by design — should be 200; non-admin would 403
            assert r.status_code == 200, f"admin override should succeed, got {r.status_code}: {r.text[:200]}"
            new_id = (r.json() or {}).get("new_listing_id")
        finally:
            mongo_db.listings.delete_many({"id": lid})
            if new_id:
                mongo_db.listings.delete_many({"id": new_id})

    def test_relist_with_winner_conflict(self, mongo_db, admin_token, admin_id):
        lid = f"TEST_iter298_relist_winner_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        mongo_db.listings.insert_one({
            "id": lid,
            "title": "TEST winner relist",
            "status": "ended_no_sale",
            "seller_id": admin_id,
            "winner_user_id": "some-buyer-uid",
            "starting_price": 10.0,
            "current_price": 25.0,
            "bid_count": 1,
            "images": [],
            "category": "Tools",
            "auction_start_date": (now - timedelta(days=2)).isoformat(),
            "auction_end_date": (now - timedelta(hours=2)).isoformat(),
            "iter298_test": True,
        })
        try:
            r = requests.post(
                f"{BASE_URL}/api/listings/{lid}/relist?mode=now",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=20,
            )
            assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text[:200]}"
        finally:
            mongo_db.listings.delete_many({"id": lid})


# ===================== BUG3 — Receipts HTTP surface =====================
class TestBug3Receipts:
    def test_receipts_mine_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/receipts/mine", timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_receipts_mine_authed(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/receipts/mine",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        body = r.json()
        assert "receipts" in body or isinstance(body, list), f"unexpected shape: {body}"


# ===================== BUG5 — Buyer/Seller dashboards =====================
class TestBug5Dashboards:
    def test_buyer_dashboard_keys(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/dashboard/buyer",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        body = r.json()
        for k in ("winning_bids", "lost_bids", "won_items_detail", "deposits"):
            assert k in body, f"missing buyer key {k} in {list(body.keys())}"

    def test_seller_dashboard_keys(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/dashboard/seller",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        body = r.json()
        # Required keys per BUG5
        counts = body.get("counts") or body
        for k in ("ended_no_sale", "payment_collected", "payment_failed", "completed"):
            assert k in counts or k in body, f"missing seller key {k} in {list(body.keys())} / counts={list((counts or {}).keys())}"
        # net payout / collected sales
        assert ("net_payout_total" in body) or ("net_payout_total" in counts), f"missing net_payout_total"
        assert ("collected_sales" in body) or ("collected_sales" in counts), f"missing collected_sales"


# ===================== Regression — listings endpoints =====================
class TestRegression:
    def test_marketplace_listings_loads(self):
        r = requests.get(f"{BASE_URL}/api/marketplace/items", timeout=20)
        assert r.status_code == 200, r.text[:200]

    def test_storage_endpoint(self):
        # storage may be under a few different paths; tolerate
        for path in ("/api/multi-item-listings", "/api/storage/listings", "/api/storage-auctions"):
            r = requests.get(f"{BASE_URL}{path}", timeout=15)
            if r.status_code == 200:
                return
        pytest.fail("no storage endpoint returned 200")

    def test_vehicles_endpoint(self):
        r = requests.get(f"{BASE_URL}/api/vehicles", timeout=15)
        assert r.status_code == 200, r.text[:200]


# ===================== Registration regression (BUG: phone null index) =====================
class TestRegistrationNoPhone:
    def test_register_without_phone_twice(self, mongo_db):
        created = []
        try:
            for _ in range(2):
                email = f"TEST_iter298_reg_{uuid.uuid4().hex[:10]}@bidvex-test.com"
                payload = {
                    "email": email,
                    "password": "TestPass123!@#",
                    "name": "Iter298 Test",
                    "account_type": "personal",
                    "terms_agreed": True,
                    "ai_disclosure_consent": True,
                }
                r = requests.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=25)
                assert r.status_code == 200, f"register failed: {r.status_code} {r.text[:300]}"
                created.append(email)
                time.sleep(1.5)
        finally:
            # cleanup created test users
            for em in created:
                try:
                    mongo_db.users.delete_many({"email": em})
                except Exception:
                    pass
