"""
iter217 Phase 5 Hotfix v5b — Broker Ecosystem regression tests.

20+ test cases covering the legal-critical and revenue-critical paths:
  • Fee engine math (fixed, percentage, min/max clamps, QST, Stripe gross-up)
  • Broker application + admin approve/reject/suspend state machine
  • Buyer ↔ broker binding (1-broker-per-buyer rule, deposit lifecycle)
  • Bid-via-broker flow (active relationship gate, bid-limit, audit trail)
  • Intra-broker conflict guard (legal blocker — broker can't bid against
    its own client)
  • Public broker directory (license masking, approved-only filter)
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import bcrypt
import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from motor.motor_asyncio import AsyncIOMotorClient

API_URL = "http://localhost:8001"


# ── Fixtures ──────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def api_base():
    return API_URL


@pytest.fixture
def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]


def _bcrypt_hash(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


@pytest.fixture
def make_user(db):
    created_ids = []

    async def _make(role="user", is_admin=False, account_type="personal", password="TestPass123!"):
        email   = f"broker-test-{uuid.uuid4().hex[:6]}@example.com"
        user_id = str(uuid.uuid4())
        pw      = _bcrypt_hash(password)
        await db.users.insert_one({
            "id": user_id, "email": email, "name": "Broker Test", "full_name": "Broker Test",
            "username": email.split("@")[0], "hashed_password": pw, "password_hash": pw,
            "role": "admin" if is_admin else role, "is_admin": is_admin,
            "account_type": account_type,
            "email_verified": True, "is_active": True, "is_demo_account": False,
        })
        created_ids.append(user_id)

        async def login():
            # iter217 Phase 5 Hotfix v5b — bypass /auth/login (rate-limited
            # at 5 req/min per IP) by minting a JWT directly using the same
            # JWT_SECRET / algorithm the backend uses.
            import jwt as _jwt
            from datetime import datetime as _dt, timedelta as _td, timezone as _tz
            secret = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")
            claims = {
                "sub":   user_id,
                "email": email,
                "role":  "admin" if is_admin else role,
                "type":  "access",
                "exp":   _dt.now(_tz.utc) + _td(minutes=60),
            }
            return _jwt.encode(claims, secret, algorithm="HS256")
        return {"id": user_id, "email": email, "password": password, "login": login}

    yield _make

    # Teardown uses a SYNCHRONOUS pymongo client so we don't need the
    # event loop. The async-on-closed-loop dance was causing every test
    # to ERROR after passing.
    from pymongo import MongoClient
    sync = MongoClient(os.environ["MONGO_URL"])
    sdb  = sync[os.environ["DB_NAME"]]
    for uid in created_ids:
        sdb.users.delete_one({"id": uid})
        sdb.brokers.delete_many({"user_id": uid})
        sdb.broker_buyer_relationships.delete_many({"buyer_user_id": uid})
        sdb.broker_bids.delete_many({"buyer_user_id": uid})
    sync.close()


# ── 1. Fee engine ─────────────────────────────────────────────────────
# iter217 Phase 5 Hotfix v7 — calculate_broker_transaction now returns a
# dict (per Senior Architect Legal Compliance directive). Tests below
# validate the v7 shape AND that hammer is excluded from the Stripe total.
class TestBrokerFeeEngine:
    def test_fixed_fee_basic(self):
        from services.broker_fee_engine import calculate_broker_transaction
        bd = calculate_broker_transaction(
            hammer_price=10000,
            broker_fee_structure={"type": "fixed", "fixed_amount_cad": 500},
            buyer_province="ON",
        )
        assert bd["hammer_price"] == 10000
        assert bd["hammer_settlement"] == "direct"
        assert bd["platform_fee"] == 250.0           # 2.5% of 10000
        assert bd["broker_fee"] == 500.0
        assert bd["broker_fee_details"] == {"type": "fixed", "rate_value": 500.0}
        assert round(bd["gst"], 2) == round((250 + 500) * 0.05, 2)  # 37.50
        assert bd["qst"] == 0                          # ON has no QST
        # CRITICAL: Stripe total must NOT include hammer
        assert bd["stripe_total_charged"] < 1500, "hammer must not flow through Stripe!"

    def test_percentage_fee_qc(self):
        from services.broker_fee_engine import calculate_broker_transaction
        bd = calculate_broker_transaction(
            hammer_price=20000,
            broker_fee_structure={"type": "percentage", "percentage_rate": 0.03},
            buyer_province="QC",
        )
        assert round(bd["broker_fee"], 2) == 600.0     # 20000 * 3%
        assert bd["broker_fee_details"] == {"type": "percentage", "rate_value": 0.03}
        assert bd["qst"] > 0                            # QST IS charged in QC
        # QST on (platform 500 + broker 600) only — NEVER on hammer
        assert round(bd["qst"], 2) == round((500 + 600) * 0.09975, 2)

    def test_min_fee_clamp(self):
        from services.broker_fee_engine import calculate_broker_transaction
        bd = calculate_broker_transaction(
            hammer_price=1000,
            broker_fee_structure={"type": "percentage", "percentage_rate": 0.03, "min_fee_cad": 200},
            buyer_province="ON",
        )
        assert bd["broker_fee"] == 200

    def test_max_fee_clamp(self):
        from services.broker_fee_engine import calculate_broker_transaction
        bd = calculate_broker_transaction(
            hammer_price=1_000_000,
            broker_fee_structure={"type": "percentage", "percentage_rate": 0.05, "max_fee_cad": 5000},
            buyer_province="ON",
        )
        assert bd["broker_fee"] == 5000

    def test_zero_hammer_price_safe(self):
        from services.broker_fee_engine import calculate_broker_transaction
        bd = calculate_broker_transaction(
            hammer_price=0, broker_fee_structure={"type": "fixed", "fixed_amount_cad": 100}, buyer_province="ON",
        )
        assert bd["hammer_price"] == 0
        assert bd["broker_fee"] == 100
        # Still must NEVER mix hammer into Stripe
        assert bd["summary"]["buyer_pays_direct"] == 0

    def test_hammer_never_in_stripe_total(self):
        """LEGAL COMPLIANCE: Stripe-charged total must never include the
        $15,000 (or any) hammer price. The hammer settles outside BidVex.
        """
        from services.broker_fee_engine import calculate_broker_transaction
        bd = calculate_broker_transaction(
            hammer_price=15000, broker_fee_structure={"type": "fixed", "fixed_amount_cad": 500},
            buyer_province="QC",
        )
        # Stripe total ≈ (375 platform + 500 broker + ~44 GST + ~87 QST + ~30 stripe) = ~1036
        # It should be FAR less than 15000.
        assert bd["stripe_total_charged"] < 1500, "FATAL: hammer included in Stripe charge!"
        assert bd["summary"]["buyer_pays_direct"] == 15000
        assert bd["summary"]["buyer_pays_stripe"] == bd["stripe_total_charged"]
        assert round(bd["summary"]["buyer_total_cost"], 2) == round(15000 + bd["stripe_total_charged"], 2)

    def test_stripe_gross_up_covers_processing_fee(self):
        """The Stripe gross-up should be large enough to cover Stripe's
        2.9% + $0.30 fee on the TOTAL amount Stripe charges (services only).
        """
        from services.broker_fee_engine import calculate_broker_transaction, STRIPE_PCT, STRIPE_FIXED_CAD
        bd = calculate_broker_transaction(
            hammer_price=10000, broker_fee_structure={"type": "fixed", "fixed_amount_cad": 500}, buyer_province="ON",
        )
        # net_target = subtotal_taxable + gst + qst (NO hammer, NO QST in ON)
        net_target = bd["subtotal_taxable"] + bd["gst"] + bd["qst"]
        stripe_take = bd["stripe_total_charged"] * STRIPE_PCT + STRIPE_FIXED_CAD
        assert abs((bd["stripe_total_charged"] - stripe_take) - net_target) < 0.05

    def test_v7_output_shape(self):
        """Every key the directive specifies must be present."""
        from services.broker_fee_engine import calculate_broker_transaction
        bd = calculate_broker_transaction(
            hammer_price=15000, broker_fee_structure={"type": "fixed", "fixed_amount_cad": 500},
            buyer_province="QC",
        )
        for k in ("hammer_price", "hammer_settlement", "hammer_settlement_note",
                  "platform_fee", "broker_fee_details", "broker_fee",
                  "subtotal_taxable", "gst", "qst",
                  "stripe_subtotal", "stripe_processing_fee", "stripe_total_charged",
                  "deposit_held", "summary"):
            assert k in bd, f"v7 key missing: {k}"
        for k in ("buyer_pays_stripe", "buyer_pays_direct", "buyer_total_cost",
                  "bidvex_earns", "broker_earns"):
            assert k in bd["summary"], f"v7 summary key missing: {k}"


# ── 2. Broker application flow ────────────────────────────────────────
@pytest.mark.asyncio
async def test_broker_application_creates_pending_record(make_user, db):
    user = await make_user()
    token = await user["login"]()
    payload = {
        "legal_business_name": "Test Brokers Inc.",
        "operating_province": "ON",
        "corporate_registration_number": "OBC-12345",
        "broker_license_number": "OMVIC-87654",
        "regulatory_body": "OMVIC",
        "permit_type": "broker",
        "fee_structure": {"type": "fixed", "fixed_amount_cad": 500},
        "default_deposit_amount_cad": 500,
    }
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{API_URL}/api/brokers/apply",
                         headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["verification_status"] == "pending_review"
    broker_id = body["broker_id"]

    # DB has the record
    doc = await db.brokers.find_one({"id": broker_id}, {"_id": 0})
    assert doc["legal_business_name"] == "Test Brokers Inc."
    assert doc["fee_structure"]["fixed_amount_cad"] == 500


@pytest.mark.asyncio
async def test_cannot_apply_twice(make_user):
    user = await make_user()
    token = await user["login"]()
    payload = {
        "legal_business_name": "Dup Brokers", "operating_province": "ON",
        "corporate_registration_number": "X", "broker_license_number": "Y",
        "regulatory_body": "OMVIC", "permit_type": "broker",
        "fee_structure": {"type": "fixed", "fixed_amount_cad": 100},
    }
    async with httpx.AsyncClient(timeout=15) as c:
        r1 = await c.post(f"{API_URL}/api/brokers/apply", headers={"Authorization": f"Bearer {token}"}, json=payload)
        assert r1.status_code == 200
        r2 = await c.post(f"{API_URL}/api/brokers/apply", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert r2.status_code == 400
    assert r2.json()["detail"]["error"] == "broker_application_exists"


@pytest.mark.asyncio
async def test_partner_account_cannot_apply(make_user):
    user = await make_user(account_type="vehicle_dealer")
    token = await user["login"]()
    payload = {
        "legal_business_name": "Partner Bro", "operating_province": "ON",
        "corporate_registration_number": "X", "broker_license_number": "Y",
        "regulatory_body": "OMVIC", "permit_type": "broker",
        "fee_structure": {"type": "fixed", "fixed_amount_cad": 100},
    }
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{API_URL}/api/brokers/apply", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "incompatible_account_type"


@pytest.mark.asyncio
async def test_admin_can_approve_broker(make_user, db):
    user = await make_user()
    admin = await make_user(is_admin=True)
    payload = {
        "legal_business_name": "Approve Test", "operating_province": "QC",
        "corporate_registration_number": "X", "broker_license_number": "L-1",
        "regulatory_body": "SAAQ", "permit_type": "broker",
        "fee_structure": {"type": "percentage", "percentage_rate": 0.03},
    }
    user_token  = await user["login"]()
    admin_token = await admin["login"]()
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{API_URL}/api/brokers/apply", headers={"Authorization": f"Bearer {user_token}"}, json=payload)
        broker_id = r.json()["broker_id"]
        r2 = await c.patch(f"{API_URL}/api/admin/brokers/{broker_id}/approve",
                           headers={"Authorization": f"Bearer {admin_token}"})
    assert r2.status_code == 200
    doc = await db.brokers.find_one({"id": broker_id}, {"_id": 0})
    assert doc["verification_status"] == "approved"
    assert doc["verified_by"] == admin["email"]


@pytest.mark.asyncio
async def test_non_admin_cannot_approve(make_user):
    user      = await make_user()
    user_alt  = await make_user()
    payload   = {"legal_business_name": "X", "operating_province": "ON",
                 "corporate_registration_number": "X", "broker_license_number": "Y",
                 "regulatory_body": "OMVIC", "permit_type": "broker",
                 "fee_structure": {"type": "fixed", "fixed_amount_cad": 100}}
    t1 = await user["login"]()
    t2 = await user_alt["login"]()
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{API_URL}/api/brokers/apply",
                         headers={"Authorization": f"Bearer {t1}"}, json=payload)
        broker_id = r.json()["broker_id"]
        r2 = await c.patch(f"{API_URL}/api/admin/brokers/{broker_id}/approve",
                           headers={"Authorization": f"Bearer {t2}"})
    assert r2.status_code in (401, 403)


# ── 3. Public directory ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_public_directory_masks_license_number(db):
    # Seed an approved broker directly
    broker_id = str(uuid.uuid4())
    await db.brokers.insert_one({
        "id": broker_id, "user_id": str(uuid.uuid4()),
        "legal_business_name": "Public Broker", "operating_province": "AB",
        "broker_license_number": "AMVIC-XYZ-12345678",
        "corporate_registration_number": "X", "regulatory_body": "AMVIC",
        "permit_type": "broker",
        "fee_structure": {"type": "fixed", "fixed_amount_cad": 250},
        "default_deposit_amount_cad": 500,
        "verification_status": "approved",
        "verified_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        "total_buyers_managed": 0, "total_deals_completed": 0, "total_revenue_cad": 0,
        "additional_documents": [],
    })
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{API_URL}/api/brokers?province=AB")
        assert r.status_code == 200
        items = [b for b in r.json()["data"] if b["id"] == broker_id]
        assert len(items) == 1
        b = items[0]
        assert "broker_license_number" not in b, "raw license must be hidden"
        assert b["broker_license_number_masked"].endswith("5678")
        assert "•" in b["broker_license_number_masked"]
    finally:
        await db.brokers.delete_one({"id": broker_id})


@pytest.mark.asyncio
async def test_pending_brokers_not_in_directory(db):
    bid = str(uuid.uuid4())
    await db.brokers.insert_one({
        "id": bid, "user_id": str(uuid.uuid4()),
        "legal_business_name": "Pending Broker", "operating_province": "BC",
        "broker_license_number": "VSA-PENDING", "corporate_registration_number": "X",
        "regulatory_body": "VSA", "permit_type": "broker",
        "fee_structure": {"type": "fixed", "fixed_amount_cad": 100},
        "default_deposit_amount_cad": 500,
        "verification_status": "pending_review",
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        "total_buyers_managed": 0, "total_deals_completed": 0, "total_revenue_cad": 0,
        "additional_documents": [],
    })
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{API_URL}/api/brokers")
        ids = [b["id"] for b in r.json()["data"]]
        assert bid not in ids
    finally:
        await db.brokers.delete_one({"id": bid})


# ── 4. Buyer ↔ broker binding ─────────────────────────────────────────
async def _seed_approved_broker(db, *, user_id=None, deposit_amount=500):
    bid = str(uuid.uuid4())
    await db.brokers.insert_one({
        "id": bid, "user_id": user_id or str(uuid.uuid4()),
        "legal_business_name": "Test Broker LLC", "operating_province": "ON",
        "broker_license_number": "OMVIC-TEST-001", "corporate_registration_number": "X",
        "regulatory_body": "OMVIC", "permit_type": "broker",
        "fee_structure": {"type": "fixed", "fixed_amount_cad": 500},
        "default_deposit_amount_cad": float(deposit_amount),
        "verification_status": "approved",
        "verified_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        "total_buyers_managed": 0, "total_deals_completed": 0, "total_revenue_cad": 0,
        "additional_documents": [],
    })
    return bid


@pytest.mark.asyncio
async def test_buyer_can_request_binding_without_stripe(make_user, db):
    """Even if Stripe fails (no test key in this env), the relationship
    must be created with deposit_status='pending'. The fee preview and
    broker workflow continue."""
    user   = await make_user()
    broker_id = await _seed_approved_broker(db)
    token  = await user["login"]()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{API_URL}/api/broker-relationships/request",
                             headers={"Authorization": f"Bearer {token}"},
                             json={"broker_id": broker_id})
        assert r.status_code == 200
        rid = r.json()["relationship_id"]
        rel = await db.broker_buyer_relationships.find_one({"id": rid}, {"_id": 0})
        assert rel["broker_id"] == broker_id
        assert rel["status"] == "pending"
        assert rel["deposit_amount_cad"] == 500
    finally:
        await db.brokers.delete_one({"id": broker_id})


@pytest.mark.asyncio
async def test_buyer_cannot_bind_to_two_brokers(make_user, db):
    user = await make_user()
    b1   = await _seed_approved_broker(db)
    b2   = await _seed_approved_broker(db)
    token = await user["login"]()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r1 = await c.post(f"{API_URL}/api/broker-relationships/request",
                              headers={"Authorization": f"Bearer {token}"},
                              json={"broker_id": b1})
            assert r1.status_code == 200
            r2 = await c.post(f"{API_URL}/api/broker-relationships/request",
                              headers={"Authorization": f"Bearer {token}"},
                              json={"broker_id": b2})
            assert r2.status_code == 400
            assert r2.json()["detail"]["error"] == "already_bound"
    finally:
        await db.brokers.delete_many({"id": {"$in": [b1, b2]}})


@pytest.mark.asyncio
async def test_broker_can_approve_relationship(make_user, db):
    buyer  = await make_user()
    broker_owner = await make_user()
    broker_id = await _seed_approved_broker(db, user_id=broker_owner["id"])
    buyer_token  = await buyer["login"]()
    broker_token = await broker_owner["login"]()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{API_URL}/api/broker-relationships/request",
                             headers={"Authorization": f"Bearer {buyer_token}"},
                             json={"broker_id": broker_id})
            rid = r.json()["relationship_id"]
            r2 = await c.post(f"{API_URL}/api/broker-relationships/{rid}/approve",
                              headers={"Authorization": f"Bearer {broker_token}"})
        assert r2.status_code == 200
        rel = await db.broker_buyer_relationships.find_one({"id": rid}, {"_id": 0})
        assert rel["status"] == "active"
        assert rel["can_bid"] is True
        u = await db.users.find_one({"id": buyer["id"]}, {"_id": 0, "bound_broker_id": 1, "can_bid_on_vehicles": 1})
        assert u["bound_broker_id"] == broker_id
        assert u["can_bid_on_vehicles"] is True
    finally:
        await db.brokers.delete_one({"id": broker_id})


@pytest.mark.asyncio
async def test_other_broker_cannot_approve_my_relationship(make_user, db):
    buyer = await make_user()
    other_broker_owner = await make_user()
    broker_id       = await _seed_approved_broker(db, user_id=str(uuid.uuid4()))
    other_broker_id = await _seed_approved_broker(db, user_id=other_broker_owner["id"])
    buyer_token = await buyer["login"]()
    other_token = await other_broker_owner["login"]()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{API_URL}/api/broker-relationships/request",
                             headers={"Authorization": f"Bearer {buyer_token}"},
                             json={"broker_id": broker_id})
            rid = r.json()["relationship_id"]
            r2 = await c.post(f"{API_URL}/api/broker-relationships/{rid}/approve",
                              headers={"Authorization": f"Bearer {other_token}"})
        assert r2.status_code == 403
    finally:
        await db.brokers.delete_many({"id": {"$in": [broker_id, other_broker_id]}})


# ── 5. Bid-via-broker (audit trail + bid-limit) ───────────────────────
async def _seed_active_relationship(db, *, buyer_id, broker_id, max_bid=None):
    rid = str(uuid.uuid4())
    doc = {
        "id": rid, "broker_id": broker_id, "buyer_user_id": buyer_id,
        "status": "active", "can_bid": True,
        "deposit_amount_cad": 500, "deposit_status": "held",
        "deposit_stripe_payment_intent_id": "pi_test_seed",
        "max_bid_amount_cad": max_bid,
        "active_bids_count": 0, "kyc_verified": False, "kyc_documents": [],
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    }
    await db.broker_buyer_relationships.insert_one(doc)
    return rid


@pytest.mark.asyncio
async def test_bid_via_broker_creates_audit_trail(make_user, db):
    buyer = await make_user()
    broker_id = await _seed_approved_broker(db)
    await _seed_active_relationship(db, buyer_id=buyer["id"], broker_id=broker_id)
    listing_id = str(uuid.uuid4())
    token = await buyer["login"]()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{API_URL}/api/vehicle-auctions/{listing_id}/bid-via-broker",
                             headers={"Authorization": f"Bearer {token}"},
                             json={"bid_amount_cad": 5000, "broker_confirmation": True})
        assert r.status_code == 200, r.text
        bid_id = r.json()["bid_id"]
        audit = await db.broker_bids.find_one({"id": bid_id}, {"_id": 0})
        assert audit["broker_license_number"] == "OMVIC-TEST-001"
        assert audit["broker_legal_business_name"] == "Test Broker LLC"
        assert audit["submitted_by_user_id"] == buyer["id"]
        assert audit["bid_amount_cad"] == 5000
        assert audit["status"] == "placed"
    finally:
        await db.brokers.delete_one({"id": broker_id})


@pytest.mark.asyncio
async def test_buyer_without_broker_cannot_bid(make_user, db):
    buyer = await make_user()
    listing_id = str(uuid.uuid4())
    token = await buyer["login"]()
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{API_URL}/api/vehicle-auctions/{listing_id}/bid-via-broker",
                         headers={"Authorization": f"Bearer {token}"},
                         json={"bid_amount_cad": 1000})
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "no_active_broker"


@pytest.mark.asyncio
async def test_bid_exceeds_broker_limit_rejected(make_user, db):
    buyer = await make_user()
    broker_id = await _seed_approved_broker(db)
    await _seed_active_relationship(db, buyer_id=buyer["id"], broker_id=broker_id, max_bid=1000)
    listing_id = str(uuid.uuid4())
    token = await buyer["login"]()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{API_URL}/api/vehicle-auctions/{listing_id}/bid-via-broker",
                             headers={"Authorization": f"Bearer {token}"},
                             json={"bid_amount_cad": 5000})
        assert r.status_code == 400
        assert r.json()["detail"]["error"] == "bid_exceeds_broker_limit"
    finally:
        await db.brokers.delete_one({"id": broker_id})


# ── 6. Intra-broker conflict guard ────────────────────────────────────
@pytest.mark.asyncio
async def test_intra_broker_conflict_blocks_second_buyer(make_user, db):
    """Two buyers under the SAME broker cannot bid against each other."""
    buyer_a = await make_user()
    buyer_b = await make_user()
    broker_id = await _seed_approved_broker(db)
    await _seed_active_relationship(db, buyer_id=buyer_a["id"], broker_id=broker_id)
    await _seed_active_relationship(db, buyer_id=buyer_b["id"], broker_id=broker_id)
    listing_id = str(uuid.uuid4())
    ta = await buyer_a["login"]()
    tb = await buyer_b["login"]()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r1 = await c.post(f"{API_URL}/api/vehicle-auctions/{listing_id}/bid-via-broker",
                              headers={"Authorization": f"Bearer {ta}"},
                              json={"bid_amount_cad": 5000})
            assert r1.status_code == 200
            r2 = await c.post(f"{API_URL}/api/vehicle-auctions/{listing_id}/bid-via-broker",
                              headers={"Authorization": f"Bearer {tb}"},
                              json={"bid_amount_cad": 6000})
        assert r2.status_code == 409
        assert r2.json()["detail"]["error"] == "intra_broker_conflict"
        assert r2.json()["detail"]["blocking_buyer_id"] == buyer_a["id"]
    finally:
        await db.brokers.delete_one({"id": broker_id})


@pytest.mark.asyncio
async def test_different_broker_buyers_can_compete(make_user, db):
    """Two buyers under DIFFERENT brokers CAN bid against each other."""
    buyer_a = await make_user()
    buyer_b = await make_user()
    broker_1 = await _seed_approved_broker(db, user_id=str(uuid.uuid4()))
    broker_2 = await _seed_approved_broker(db, user_id=str(uuid.uuid4()))
    await _seed_active_relationship(db, buyer_id=buyer_a["id"], broker_id=broker_1)
    await _seed_active_relationship(db, buyer_id=buyer_b["id"], broker_id=broker_2)
    listing_id = str(uuid.uuid4())
    ta = await buyer_a["login"]()
    tb = await buyer_b["login"]()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r1 = await c.post(f"{API_URL}/api/vehicle-auctions/{listing_id}/bid-via-broker",
                              headers={"Authorization": f"Bearer {ta}"},
                              json={"bid_amount_cad": 5000})
            assert r1.status_code == 200
            r2 = await c.post(f"{API_URL}/api/vehicle-auctions/{listing_id}/bid-via-broker",
                              headers={"Authorization": f"Bearer {tb}"},
                              json={"bid_amount_cad": 6000})
        assert r2.status_code == 200, r2.text
    finally:
        await db.brokers.delete_many({"id": {"$in": [broker_1, broker_2]}})


# ── 7. Fee preview endpoint ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_public_fee_preview_endpoint(db):
    broker_id = await _seed_approved_broker(db)
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{API_URL}/api/brokers/{broker_id}/fee-preview",
                             json={"hammer_price": 15000, "buyer_province": "QC"})
        assert r.status_code == 200
        body = r.json()
        assert body["hammer_price"] == 15000          # v7 dict key
        assert body["broker_fee"] == 500              # fixed
        assert body["qst"] > 0                         # QC charges QST
        # Legal: hammer is INFORMATIONAL only — never in Stripe total
        assert body["hammer_settlement"] == "direct"
        assert body["stripe_total_charged"] < 2000     # services only, never hammer
    finally:
        await db.brokers.delete_one({"id": broker_id})


# ── 8. Admin audit endpoint ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_admin_audit_endpoint_returns_bids(make_user, db):
    admin = await make_user(is_admin=True)
    # Seed an audit row directly
    await db.broker_bids.insert_one({
        "id": str(uuid.uuid4()),
        "vehicle_listing_id": "v1",
        "broker_id": "b1", "buyer_user_id": "u1",
        "bid_amount_cad": 1000, "submitted_by_user_id": "u1",
        "broker_license_number": "LIC", "broker_legal_business_name": "B",
        "status": "placed", "placed_at": datetime.now(timezone.utc),
        "outbid_at": None, "ip_address": "1.2.3.4",
        "user_agent": "test", "session_id": None, "auction_state_snapshot": {},
    })
    token = await admin["login"]()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{API_URL}/api/broker-bids/audit?listing_id=v1",
                            headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert any(b["vehicle_listing_id"] == "v1" for b in r.json()["data"])
    finally:
        await db.broker_bids.delete_many({"vehicle_listing_id": "v1"})


# ── 9. Module/import sanity ───────────────────────────────────────────
class TestBrokerModuleSanity:
    def test_broker_router_registered(self):
        from server import app
        paths = [r.path for r in app.routes]
        assert "/api/brokers/apply" in paths
        assert "/api/admin/brokers" in paths
        assert "/api/vehicle-auctions/{listing_id}/bid-via-broker" in paths

    def test_models_importable(self):
        from models.broker_models import (
            BrokerCreate, BrokerFeeStructure, RelationshipRequest,
            make_broker_doc, make_relationship_doc, make_broker_bid_doc,
            make_invoice_doc,
        )
        # Smoke construct
        fs = BrokerFeeStructure(type="fixed", fixed_amount_cad=100)
        bc = BrokerCreate(
            legal_business_name="X", operating_province="ON",
            corporate_registration_number="X", broker_license_number="Y",
            regulatory_body="OMVIC", permit_type="broker", fee_structure=fs,
        )
        d = make_broker_doc(user_id="u", payload=bc)
        assert d["verification_status"] == "pending_review"
        assert d["fee_structure"]["fixed_amount_cad"] == 100

    def test_fee_structure_validation_rejects_invalid_pct(self):
        from models.broker_models import BrokerFeeStructure
        with pytest.raises(Exception):
            BrokerFeeStructure(type="percentage", percentage_rate=2.0)
        with pytest.raises(Exception):
            BrokerFeeStructure(type="percentage", percentage_rate=-0.1)
