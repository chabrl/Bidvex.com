"""
iter217 Phase 5 Hotfix v7 — Legal Compliance / Category Gate / Ratings tests.

Covers:
  • category_rules.category_requires_broker
  • category_rules.assert_seller_can_list
  • Individual sellers can't post vehicles (403)
  • Individual seller listing auto-approve after 3 listings
  • Payout preview math (8% commission + GST/QST)
  • Broker rating only after a completed transaction
  • Broker trust-score endpoint shape
  • Dispute window enforcement
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import httpx
import jwt as _jwt
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient


API_URL    = "http://localhost:8001"
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")


def _mint(user_id, email, role="user"):
    return _jwt.encode({
        "sub": user_id, "email": email, "role": role, "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
    }, JWT_SECRET, algorithm="HS256")


@pytest.fixture
def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]


@pytest.fixture
def make_user(db):
    created = []

    async def _make(account_type="personal", phone_verified=True, role="user"):
        email   = f"v7-{uuid.uuid4().hex[:6]}@example.com"
        user_id = str(uuid.uuid4())
        pw      = bcrypt.hashpw(b"TestPass123!", bcrypt.gensalt()).decode()
        await db.users.insert_one({
            "id": user_id, "email": email, "name": "V7 Test", "full_name": "V7 Test",
            "username": email.split("@")[0],
            "hashed_password": pw, "password_hash": pw,
            "role": role, "is_admin": role == "admin",
            "account_type": account_type,
            "phone_verified": phone_verified,
            "email_verified": True, "is_active": True, "is_demo_account": False,
        })
        # Pretend they have a payment method so bid gatekeeping passes
        await db.payment_methods.insert_one({
            "id": str(uuid.uuid4()), "user_id": user_id,
            "stripe_payment_method_id": "pm_test", "brand": "visa",
        })
        created.append(user_id)
        return {"id": user_id, "email": email,
                "token": _mint(user_id, email, role)}
    yield _make

    sync = MongoClient(os.environ["MONGO_URL"])
    sdb  = sync[os.environ["DB_NAME"]]
    for uid in created:
        sdb.users.delete_one({"id": uid})
        sdb.payment_methods.delete_many({"user_id": uid})
        sdb.listings.delete_many({"seller_id": uid})
        sdb.broker_buyer_relationships.delete_many({"buyer_user_id": uid})
    sync.close()


# ─────────────────────────────────────────────────────────────────────
# Task 4 — Category rules (pure unit tests)
# ─────────────────────────────────────────────────────────────────────
class TestCategoryRules:
    def test_vehicles_require_broker(self):
        from services.category_rules import category_requires_broker
        assert category_requires_broker("Vehicles") is True
        assert category_requires_broker("vehicles_cars") is True
        assert category_requires_broker("Trucks & SUVs") is True
        assert category_requires_broker("Motorcycle") is True
        assert category_requires_broker("Véhicules") is True

    def test_non_vehicle_categories_dont_require_broker(self):
        from services.category_rules import category_requires_broker
        for c in ("Restaurant Equipment", "Bankrupt Inventory",
                  "General Lots", "Industrial Equipment", "Storage Auctions"):
            assert category_requires_broker(c) is False

    def test_individual_cannot_list_vehicles(self):
        from services.category_rules import assert_seller_can_list
        ok, err = assert_seller_can_list("Vehicles", "personal")
        assert ok is False
        assert err["error"] == "individual_cannot_list_vehicles"

    def test_dealer_can_list_vehicles(self):
        from services.category_rules import assert_seller_can_list
        for role in ("broker", "dealer", "admin"):
            ok, _ = assert_seller_can_list("Vehicles", role)
            assert ok is True

    def test_individual_can_list_non_vehicle(self):
        from services.category_rules import assert_seller_can_list
        ok, _ = assert_seller_can_list("Restaurant Equipment", "personal")
        assert ok is True

    def test_commission_rates(self):
        from services.category_rules import commission_rate_for_category
        assert commission_rate_for_category("Vehicles") == 0.025
        assert commission_rate_for_category("Restaurant Equipment") == 0.05
        assert commission_rate_for_category("Bankrupt Inventory") == 0.04
        assert commission_rate_for_category("Industrial Equipment") == 0.045

    def test_broker_eligible_individual_no_relationship(self):
        from services.category_rules import assert_broker_eligible
        ok, err = assert_broker_eligible("Vehicles", "individual", False)
        assert ok is False
        assert err["error"] == "broker_required"
        assert err["action_url"] == "/brokers"

    def test_broker_eligible_dealer_ok(self):
        from services.category_rules import assert_broker_eligible
        ok, _ = assert_broker_eligible("Vehicles", "dealer", False)
        assert ok is True

    def test_broker_eligible_non_vehicle_anyone(self):
        from services.category_rules import assert_broker_eligible
        ok, _ = assert_broker_eligible("Restaurant Equipment", "individual", False)
        assert ok is True


# ─────────────────────────────────────────────────────────────────────
# Task 5 — Individual seller listings + payout preview
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_individual_cannot_list_vehicle_via_endpoint(make_user):
    user = await make_user()
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{API_URL}/api/listings/individual", json={
            "title": "Sneaky vehicle listing",
            "description": "trying to bypass",
            "category": "Vehicles",
            "starting_price": 5000,
        }, headers={"Authorization": f"Bearer {user['token']}"})
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "individual_cannot_list_vehicles"


@pytest.mark.asyncio
async def test_individual_first_listing_pending_review(make_user):
    user = await make_user()
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{API_URL}/api/listings/individual", json={
            "title": "Used Espresso Machine",
            "description": "Restaurant grade espresso machine in good condition. Selling because of move.",
            "category": "Restaurant Equipment",
            "starting_price": 1000,
        }, headers={"Authorization": f"Bearer {user['token']}"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "pending_review"
    assert d["auto_approved"] is False
    assert d["commission_rate"] == 0.08


@pytest.mark.asyncio
async def test_individual_auto_approve_after_three(make_user, db):
    user = await make_user()
    # Seed 3 prior approved listings
    for _ in range(3):
        await db.listings.insert_one({
            "id": str(uuid.uuid4()),
            "seller_id": user["id"],
            "seller_account_type": "individual",
            "status": "active",
            "category": "Restaurant Equipment",
            "title": "prior", "description": "prior", "starting_price": 100,
        })
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{API_URL}/api/listings/individual", json={
            "title": "Bulk fryer auction",
            "description": "Bulk fryer in excellent condition with 6 months warranty.",
            "category": "Restaurant Equipment",
            "starting_price": 800,
        }, headers={"Authorization": f"Bearer {user['token']}"})
    d = r.json()
    assert r.status_code == 200
    assert d["auto_approved"] is True
    assert d["status"] == "active"


@pytest.mark.asyncio
async def test_payout_preview_math_qc(make_user):
    user = await make_user()
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_URL}/api/individual-seller/payout-preview"
                        "?hammer_price=1000&buyer_province=QC",
                        headers={"Authorization": f"Bearer {user['token']}"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["commission_cad"] == 80.0           # 8% of 1000
    assert d["gst_cad"]        == 4.0            # 5% on commission
    assert round(d["qst_cad"], 2) == 7.98        # 9.975% on commission
    assert d["seller_net_cad"] == round(1000 - 80 - 4 - 7.98, 2)


# ─────────────────────────────────────────────────────────────────────
# Task 4 — Direct vehicle bid is blocked at /api/bids
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_individual_cannot_bid_directly_on_vehicle(make_user, db):
    user = await make_user(account_type="personal")
    # Seed a vehicle listing by a dealer
    seller_id = str(uuid.uuid4())
    listing_id = str(uuid.uuid4())
    await db.users.insert_one({"id": seller_id, "email": "d@example.com", "name": "D",
                               "username": "d", "hashed_password": "x", "password_hash": "x",
                               "role": "user", "account_type": "vehicle_dealer",
                               "is_demo_account": False, "is_active": True, "email_verified": True})
    await db.listings.insert_one({
        "id": listing_id, "seller_id": seller_id,
        "title": "2018 Honda Civic", "description": "Clean title",
        "category": "Vehicles", "starting_price": 5000, "current_price": 5000,
        "status": "active", "is_demo": False,
    })
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{API_URL}/api/bids", json={
                "listing_id": listing_id, "amount": 6000,
            }, headers={"Authorization": f"Bearer {user['token']}"})
        # Must be 403 broker_required (NOT a successful bid)
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["error"] in ("broker_required", "broker_required_use_proxy")
    finally:
        await db.listings.delete_one({"id": listing_id})
        await db.users.delete_one({"id": seller_id})


# ─────────────────────────────────────────────────────────────────────
# Task 7 — Broker ratings & trust score
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_cannot_rate_without_completed_tx(make_user, db):
    buyer  = await make_user()
    broker_uid = str(uuid.uuid4())
    broker_id  = str(uuid.uuid4())
    await db.users.insert_one({"id": broker_uid, "email": "b@example.com", "name": "B",
                               "username": "b", "hashed_password": "x", "password_hash": "x",
                               "role": "user", "account_type": "broker",
                               "is_demo_account": False, "is_active": True, "email_verified": True})
    await db.brokers.insert_one({"id": broker_id, "user_id": broker_uid,
                                  "legal_business_name": "Test B", "verification_status": "approved"})
    rel_id = str(uuid.uuid4())
    await db.broker_buyer_relationships.insert_one({
        "id": rel_id, "broker_id": broker_id, "buyer_user_id": buyer["id"],
        "status": "active", "created_at": datetime.now(timezone.utc),
        "approved_at": datetime.now(timezone.utc),
    })
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{API_URL}/api/broker-relationships/{rel_id}/rate",
                             json={"stars": 5, "review": "great"},
                             headers={"Authorization": f"Bearer {buyer['token']}"})
        assert r.status_code == 400
        assert r.json()["detail"]["error"] == "no_completed_tx"
    finally:
        await db.broker_buyer_relationships.delete_one({"id": rel_id})
        await db.brokers.delete_one({"id": broker_id})
        await db.users.delete_one({"id": broker_uid})


@pytest.mark.asyncio
async def test_can_rate_after_completed_tx(make_user, db):
    buyer  = await make_user()
    broker_uid = str(uuid.uuid4())
    broker_id  = str(uuid.uuid4())
    rel_id     = str(uuid.uuid4())
    inv_id     = str(uuid.uuid4())
    now        = datetime.now(timezone.utc)
    await db.users.insert_one({"id": broker_uid, "email": "b@example.com", "name": "B",
                               "username": "b", "hashed_password": "x", "password_hash": "x",
                               "role": "user", "account_type": "broker",
                               "is_demo_account": False, "is_active": True, "email_verified": True})
    await db.brokers.insert_one({"id": broker_id, "user_id": broker_uid,
                                  "legal_business_name": "Test B",
                                  "verification_status": "approved",
                                  "created_at": now - timedelta(days=30)})
    await db.broker_buyer_relationships.insert_one({
        "id": rel_id, "broker_id": broker_id, "buyer_user_id": buyer["id"],
        "status": "active", "created_at": now - timedelta(days=10),
        "approved_at": now - timedelta(days=9),
    })
    await db.broker_invoices.insert_one({
        "id": inv_id, "broker_id": broker_id, "buyer_user_id": buyer["id"],
        "vehicle_listing_id": "v1", "released_at": now - timedelta(days=1),
    })
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{API_URL}/api/broker-relationships/{rel_id}/rate",
                             json={"stars": 4, "review": "fast and professional"},
                             headers={"Authorization": f"Bearer {buyer['token']}"})
            assert r.status_code == 200, r.text
            assert r.json()["count"] == 1

            # Trust score reflects the rating + completed transaction
            t = await c.get(f"{API_URL}/api/brokers/{broker_id}/trust-score")
            ts = t.json()
            assert ts["verified"] is True
            assert ts["completed_transactions"] == 1
            assert ts["rating_avg"] == 4.0
            assert ts["rating_count"] == 1

            # Double-rate rejected
            r2 = await c.post(f"{API_URL}/api/broker-relationships/{rel_id}/rate",
                              json={"stars": 5},
                              headers={"Authorization": f"Bearer {buyer['token']}"})
            assert r2.status_code == 400
            assert r2.json()["detail"]["error"] == "already_rated"
    finally:
        await db.broker_invoices.delete_one({"id": inv_id})
        await db.broker_buyer_relationships.delete_one({"id": rel_id})
        await db.brokers.delete_one({"id": broker_id})
        await db.users.delete_one({"id": broker_uid})
        await db.broker_ratings.delete_many({"relationship_id": rel_id})


# ─────────────────────────────────────────────────────────────────────
# Task 6 — Dispute window enforcement
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_dispute_rejected_before_release(make_user, db):
    buyer = await make_user()
    inv_id = str(uuid.uuid4())
    await db.broker_invoices.insert_one({
        "id": inv_id, "broker_id": "b1", "buyer_user_id": buyer["id"],
        "vehicle_listing_id": "v1", "released_at": None,
    })
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{API_URL}/api/broker-invoices/{inv_id}/dispute",
                             json={"side": "buyer", "reason": "vehicle not as described, multiple problems found"},
                             headers={"Authorization": f"Bearer {buyer['token']}"})
        assert r.status_code == 400
        assert r.json()["detail"]["error"] == "release_not_yet"
    finally:
        await db.broker_invoices.delete_one({"id": inv_id})


@pytest.mark.asyncio
async def test_dispute_rejected_after_7_days(make_user, db):
    buyer = await make_user()
    inv_id = str(uuid.uuid4())
    old = datetime.now(timezone.utc) - timedelta(days=10)
    await db.broker_invoices.insert_one({
        "id": inv_id, "broker_id": "b1", "buyer_user_id": buyer["id"],
        "vehicle_listing_id": "v1", "released_at": old,
    })
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{API_URL}/api/broker-invoices/{inv_id}/dispute",
                             json={"side": "buyer", "reason": "way after release, should be rejected"},
                             headers={"Authorization": f"Bearer {buyer['token']}"})
        assert r.status_code == 400
        assert r.json()["detail"]["error"] == "dispute_window_closed"
    finally:
        await db.broker_invoices.delete_one({"id": inv_id})
