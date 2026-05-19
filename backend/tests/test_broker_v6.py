"""
iter217 Phase 5 Hotfix v6 — Broker Ecosystem v6 features.

Tests:
  • Invoice generation + idempotency
  • Mark paid + release vehicle state transitions
  • PDF generation returns application/pdf bytes
  • Active deals endpoint groups bids by column
  • Buyer invitation endpoint
  • Admin deposits / conflicts / revenue endpoints
  • Settings update (fee structure live edit)
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import httpx
import jwt as _jwt
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from motor.motor_asyncio import AsyncIOMotorClient

API_URL = "http://localhost:8001"


def _token_for(user_id: str, role: str = "user", email: str = "u@example.com"):
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    return _jwt.encode(
        {"sub": user_id, "email": email, "role": role, "type": "access",
         "exp": _dt.now(_tz.utc) + _td(minutes=60)},
        os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production"),
        algorithm="HS256",
    )


@pytest.fixture
def db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture
def cleanup_ids():
    ids = {"users": [], "brokers": [], "rels": [], "invoices": [], "bids": []}
    yield ids
    from pymongo import MongoClient
    s = MongoClient(os.environ["MONGO_URL"])
    sdb = s[os.environ["DB_NAME"]]
    if ids["users"]:    sdb.users.delete_many({"id": {"$in": ids["users"]}})
    if ids["brokers"]:  sdb.brokers.delete_many({"id": {"$in": ids["brokers"]}})
    if ids["rels"]:     sdb.broker_buyer_relationships.delete_many({"id": {"$in": ids["rels"]}})
    if ids["invoices"]: sdb.broker_invoices.delete_many({"id": {"$in": ids["invoices"]}})
    if ids["bids"]:     sdb.broker_bids.delete_many({"id": {"$in": ids["bids"]}})
    sdb.broker_invitations.delete_many({"broker_id": {"$in": ids["brokers"]}})
    s.close()


async def _seed_broker(db, user_id, cleanup_ids):
    bid = str(uuid.uuid4())
    await db.brokers.insert_one({
        "id": bid, "user_id": user_id,
        "legal_business_name": "V6 Test Broker", "operating_province": "ON",
        "broker_license_number": "OMVIC-V6-001", "corporate_registration_number": "X",
        "regulatory_body": "OMVIC", "permit_type": "broker",
        "fee_structure": {"type": "fixed", "fixed_amount_cad": 500},
        "default_deposit_amount_cad": 500,
        "verification_status": "approved",
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        "total_buyers_managed": 0, "total_deals_completed": 0, "total_revenue_cad": 0,
        "additional_documents": [],
    })
    cleanup_ids["brokers"].append(bid)
    return bid


async def _seed_user(db, cleanup_ids, role="user"):
    uid = str(uuid.uuid4())
    email = f"v6-{uuid.uuid4().hex[:6]}@example.com"
    await db.users.insert_one({
        "id": uid, "email": email, "name": "V6", "full_name": "V6",
        "username": email.split("@")[0],
        "role": role, "is_admin": role == "admin",
        "account_type": "broker" if role == "broker" else "personal",
        "email_verified": True, "is_active": True, "is_demo_account": False,
    })
    cleanup_ids["users"].append(uid)
    return uid, email


# ── Invoices ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_generate_invoice(db, cleanup_ids):
    uid, email = await _seed_user(db, cleanup_ids, role="broker")
    broker_id  = await _seed_broker(db, uid, cleanup_ids)
    t = _token_for(uid, "broker", email)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{API_URL}/api/broker-invoices/generate",
                         headers={"Authorization": f"Bearer {t}"},
                         json={"vehicle_listing_id": "v-1", "buyer_user_id": "buyer-1",
                               "dealer_user_id": "dealer-1", "hammer_price_cad": 10000})
    assert r.status_code == 200, r.text
    inv = r.json()
    assert inv["hammer_price_cad"] == 10000
    assert inv["broker_fee_cad"] == 500
    assert inv["bidvex_platform_fee_cad"] == 250
    assert inv["pickup_code"]
    cleanup_ids["invoices"].append(inv["id"])


@pytest.mark.asyncio
async def test_generate_invoice_idempotent(db, cleanup_ids):
    uid, email = await _seed_user(db, cleanup_ids, role="broker")
    await _seed_broker(db, uid, cleanup_ids)
    t = _token_for(uid, "broker", email)
    async with httpx.AsyncClient(timeout=20) as c:
        r1 = await c.post(f"{API_URL}/api/broker-invoices/generate",
                          headers={"Authorization": f"Bearer {t}"},
                          json={"vehicle_listing_id": "v-2", "buyer_user_id": "b-2", "dealer_user_id": "d-2", "hammer_price_cad": 5000})
        r2 = await c.post(f"{API_URL}/api/broker-invoices/generate",
                          headers={"Authorization": f"Bearer {t}"},
                          json={"vehicle_listing_id": "v-2", "buyer_user_id": "b-2", "dealer_user_id": "d-2", "hammer_price_cad": 5000})
    assert r1.json()["id"] == r2.json()["id"]
    cleanup_ids["invoices"].append(r1.json()["id"])


@pytest.mark.asyncio
async def test_mark_paid_then_release(db, cleanup_ids):
    uid, email = await _seed_user(db, cleanup_ids, role="broker")
    await _seed_broker(db, uid, cleanup_ids)
    t = _token_for(uid, "broker", email)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{API_URL}/api/broker-invoices/generate",
                        headers={"Authorization": f"Bearer {t}"},
                        json={"vehicle_listing_id": "v-3", "buyer_user_id": "b-3", "dealer_user_id": "d-3", "hammer_price_cad": 7000})
        inv_id = r.json()["id"]
        cleanup_ids["invoices"].append(inv_id)
        r2 = await c.patch(f"{API_URL}/api/broker-invoices/{inv_id}/mark-paid",
                           headers={"Authorization": f"Bearer {t}"})
        r3 = await c.post(f"{API_URL}/api/broker-invoices/{inv_id}/release-vehicle",
                          headers={"Authorization": f"Bearer {t}"})
    assert r2.status_code == 200 and r3.status_code == 200
    inv = await db.broker_invoices.find_one({"id": inv_id}, {"_id": 0})
    assert inv["buyer_payment_status"] == "paid"
    assert inv["vehicle_release_status"] == "released"


@pytest.mark.asyncio
async def test_pdf_invoice_returns_pdf_bytes(db, cleanup_ids):
    uid, email = await _seed_user(db, cleanup_ids, role="broker")
    await _seed_broker(db, uid, cleanup_ids)
    t = _token_for(uid, "broker", email)
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{API_URL}/api/broker-invoices/generate",
                        headers={"Authorization": f"Bearer {t}"},
                        json={"vehicle_listing_id": "v-4", "buyer_user_id": "b-4", "dealer_user_id": "d-4", "hammer_price_cad": 12000})
        inv_id = r.json()["id"]
        cleanup_ids["invoices"].append(inv_id)
        r2 = await c.get(f"{API_URL}/api/broker-invoices/{inv_id}/pdf",
                         headers={"Authorization": f"Bearer {t}"})
    assert r2.status_code == 200
    assert r2.headers["content-type"].startswith("application/pdf")
    assert r2.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_pdf_unauthorized_returns_403(db, cleanup_ids):
    """A non-owner non-buyer non-admin cannot fetch the PDF."""
    uid, email = await _seed_user(db, cleanup_ids, role="broker")
    await _seed_broker(db, uid, cleanup_ids)
    t = _token_for(uid, "broker", email)
    other_uid, other_email = await _seed_user(db, cleanup_ids)
    other_t = _token_for(other_uid, "user", other_email)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{API_URL}/api/broker-invoices/generate",
                        headers={"Authorization": f"Bearer {t}"},
                        json={"vehicle_listing_id": "v-5", "buyer_user_id": "b-5", "dealer_user_id": "d-5", "hammer_price_cad": 6000})
        inv_id = r.json()["id"]
        cleanup_ids["invoices"].append(inv_id)
        r2 = await c.get(f"{API_URL}/api/broker-invoices/{inv_id}/pdf",
                         headers={"Authorization": f"Bearer {other_t}"})
    assert r2.status_code == 403


# ── Active deals ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_active_deals_endpoint(db, cleanup_ids):
    uid, email = await _seed_user(db, cleanup_ids, role="broker")
    broker_id  = await _seed_broker(db, uid, cleanup_ids)
    # Seed a real-ish vehicle_listing so the endpoint joins back to it.
    vehicle_id = f"v-active-{uuid.uuid4().hex[:6]}"
    await db.vehicle_listings.insert_one({
        "id": vehicle_id, "make": "Honda", "model": "Civic", "year": 2018,
        "current_bid": 5500, "highest_bidder_id": "b-active-1",
        "auction_end_date": datetime.now(timezone.utc), "status": "active",
        "photos": [], "title": "2018 Honda Civic",
    })
    # Insert a fake bid
    bid_id = str(uuid.uuid4())
    await db.broker_bids.insert_one({
        "id": bid_id, "broker_id": broker_id, "buyer_user_id": "b-active-1",
        "vehicle_listing_id": vehicle_id, "bid_amount_cad": 5000,
        "submitted_by_user_id": "b-active-1",
        "broker_license_number": "L", "broker_legal_business_name": "B",
        "status": "placed", "placed_at": datetime.now(timezone.utc),
        "outbid_at": None, "ip_address": None, "user_agent": None,
        "session_id": None, "auction_state_snapshot": {},
    })
    cleanup_ids["bids"].append(bid_id)
    t = _token_for(uid, "broker", email)
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{API_URL}/api/broker-relationships/active-deals",
                            headers={"Authorization": f"Bearer {t}"})
        assert r.status_code == 200
        assert any(d["bid_id"] == bid_id for d in r.json()["data"])
    finally:
        await db.vehicle_listings.delete_one({"id": vehicle_id})


# ── Invitations ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_invite_buyer(db, cleanup_ids):
    uid, email = await _seed_user(db, cleanup_ids, role="broker")
    await _seed_broker(db, uid, cleanup_ids)
    t = _token_for(uid, "broker", email)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{API_URL}/api/broker-relationships/invite",
                         headers={"Authorization": f"Bearer {t}"},
                         json={"email": "guest@example.com"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"]
    assert "join_url" in body
    # Verify in DB
    inv = await db.broker_invitations.find_one({"id": body["invite_id"]}, {"_id": 0})
    assert inv["buyer_email"] == "guest@example.com"


# ── Admin endpoints ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_admin_deposits_list(db, cleanup_ids):
    admin_uid, admin_email = await _seed_user(db, cleanup_ids, role="admin")
    t = _token_for(admin_uid, "admin", admin_email)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{API_URL}/api/admin/broker-deposits",
                        headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200
    assert "data" in r.json()


@pytest.mark.asyncio
async def test_admin_conflicts_endpoint(db, cleanup_ids):
    admin_uid, admin_email = await _seed_user(db, cleanup_ids, role="admin")
    t = _token_for(admin_uid, "admin", admin_email)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{API_URL}/api/admin/broker-conflicts",
                        headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_admin_revenue_endpoint(db, cleanup_ids):
    admin_uid, admin_email = await _seed_user(db, cleanup_ids, role="admin")
    t = _token_for(admin_uid, "admin", admin_email)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{API_URL}/api/admin/broker-revenue",
                        headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200
    body = r.json()
    for k in ("deal_count", "total_platform_fee_cad", "total_broker_fees_cad", "total_hammer_cad"):
        assert k in body


# ── Settings update ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_broker_can_update_fee_structure(db, cleanup_ids):
    uid, email = await _seed_user(db, cleanup_ids, role="broker")
    bid = await _seed_broker(db, uid, cleanup_ids)
    t = _token_for(uid, "broker", email)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.patch(f"{API_URL}/api/brokers/settings",
                          headers={"Authorization": f"Bearer {t}"},
                          json={"fee_structure": {"type": "percentage", "percentage_rate": 0.05}})
    assert r.status_code == 200
    doc = await db.brokers.find_one({"id": bid}, {"_id": 0})
    assert doc["fee_structure"]["type"] == "percentage"
    assert doc["fee_structure"]["percentage_rate"] == 0.05


@pytest.mark.asyncio
async def test_deposit_below_min_rejected(db, cleanup_ids):
    uid, email = await _seed_user(db, cleanup_ids, role="broker")
    await _seed_broker(db, uid, cleanup_ids)
    t = _token_for(uid, "broker", email)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.patch(f"{API_URL}/api/brokers/settings",
                          headers={"Authorization": f"Bearer {t}"},
                          json={"default_deposit_amount_cad": 50})
    assert r.status_code == 422


# ── Route registration sanity ────────────────────────────────────────
class TestV6RouteRegistration:
    def test_v6_routes_registered(self):
        from server import app
        paths = [r.path for r in app.routes]
        assert "/api/broker-invoices/generate"            in paths
        assert "/api/broker-invoices/{invoice_id}/pdf"    in paths
        assert "/api/broker-invoices/{invoice_id}/mark-paid" in paths
        assert "/api/broker-invoices/{invoice_id}/release-vehicle" in paths
        assert "/api/broker-relationships/active-deals"   in paths
        assert "/api/broker-relationships/invite"         in paths
        assert "/api/admin/broker-deposits"               in paths
        assert "/api/admin/broker-conflicts"              in paths
        assert "/api/admin/broker-revenue"                in paths
