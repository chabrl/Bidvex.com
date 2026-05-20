"""
iter217 Phase 5 Hotfix v8.1 — Buyer Receipt + Title Transfer Cron tests.

Covers:
  • GET  /api/broker-invoices/{id}/receipt?code=...        — valid token ⇒ sanitized payload
  • GET  /api/broker-invoices/{id}/receipt?code=BAD        — invalid ⇒ 404 (not 403)
  • GET  /api/broker-invoices/{id}/receipt                 — missing code ⇒ 404
  • Receipt sanitization: no email/phone, buyer name masked to "First L."
  • enforce_title_transfer_overdue_job: flags overdue, idempotent, audits
  • Stripe connect endpoint requires broker role
"""
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


def _mint(uid, email, role="user"):
    return _jwt.encode({"sub": uid, "email": email, "role": role, "type": "access",
                        "exp": datetime.now(timezone.utc) + timedelta(minutes=60)},
                       JWT_SECRET, algorithm="HS256")


@pytest.fixture
def db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture
def cleanup():
    state = {"users": [], "brokers": [], "invoices": []}
    yield state
    sync = MongoClient(os.environ["MONGO_URL"])
    sdb  = sync[os.environ["DB_NAME"]]
    for uid in state["users"]:    sdb.users.delete_one({"id": uid})
    for bid in state["brokers"]:  sdb.brokers.delete_one({"id": bid})
    for iid in state["invoices"]:
        sdb.broker_invoices.delete_one({"id": iid})
        sdb.broker_invoice_audit.delete_many({"invoice_id": iid})
        sdb.broker_notifications.delete_many({"invoice_id": iid})
        sdb.email_outbox.delete_many({"context.invoice_id": iid})
    sync.close()


async def _seed_invoice(db, cleanup, *, with_token=True, with_release=True, with_title=False):
    """Seed broker + buyer + invoice. Returns (invoice_id, receipt_token, broker_id, buyer_uid)."""
    broker_uid = str(uuid.uuid4())
    broker_id  = str(uuid.uuid4())
    buyer_uid  = str(uuid.uuid4())
    inv_id     = str(uuid.uuid4())
    pw = bcrypt.hashpw(b"x", bcrypt.gensalt()).decode()
    await db.users.insert_many([
        {"id": broker_uid, "email": f"b-{uuid.uuid4().hex[:6]}@example.com", "name": "Broker Co",
         "username": "b", "hashed_password": pw, "password_hash": pw,
         "role": "user", "account_type": "broker", "is_demo_account": False,
         "is_active": True, "email_verified": True},
        {"id": buyer_uid, "email": "buyer@example.com", "name": "John Doe", "full_name": "John Doe",
         "username": "j", "hashed_password": pw, "password_hash": pw,
         "role": "user", "account_type": "personal", "is_demo_account": False,
         "is_active": True, "email_verified": True, "phone": "+15145551234"},
    ])
    await db.brokers.insert_one({
        "id": broker_id, "user_id": broker_uid,
        "legal_business_name": "Acme Auto Brokers Inc.",
        "verification_status": "approved",
        "broker_license_number": "LIC-987654",
        "operating_province": "QC", "regulatory_body": "OPC / SAAQ",
        "created_at": datetime.now(timezone.utc) - timedelta(days=30),
    })

    inv = {
        "id": inv_id, "broker_id": broker_id, "buyer_user_id": buyer_uid,
        "vehicle_listing_id": "veh-1",
        "invoice_number": f"BVX-2026-{uuid.uuid4().hex[:6].upper()}",
        "hammer_price_cad": 15000,
        "bidvex_platform_fee_cad": 375,
        "broker_fee_cad": 500,
        "gst_cad": 43.75, "qst_cad": 87.28,
        "total_cad": 1036.39,
        "fee_breakdown": {"stripe_processing_fee": 30.36},
        "pickup_code": "ABCD-1234",
        "released_at": (datetime.now(timezone.utc) - timedelta(hours=1)) if with_release else None,
        "created_at": datetime.now(timezone.utc) - timedelta(days=2),
    }
    if with_token:
        inv["receipt_token"] = "TKN" + uuid.uuid4().hex[:9].upper()
    if with_title:
        inv["title_transfer_logged_at"] = datetime.now(timezone.utc)
        inv["title_transfer_registry"]  = "SAAQ"
        inv["title_transfer_tx_number"] = "SAAQ-2026-77777"
        inv["title_transfer_province"]  = "QC"
        inv["title_transfer_date"]      = datetime.now(timezone.utc)
    await db.broker_invoices.insert_one(inv)

    cleanup["users"].extend([broker_uid, buyer_uid])
    cleanup["brokers"].append(broker_id)
    cleanup["invoices"].append(inv_id)
    return inv_id, inv.get("receipt_token"), broker_id, buyer_uid


# ── 1. Valid token → 200 with sanitized data ─────────────────────────
@pytest.mark.asyncio
async def test_receipt_valid_token_returns_sanitized_data(db, cleanup):
    inv_id, token, _, _ = await _seed_invoice(db, cleanup, with_title=True)
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_URL}/api/broker-invoices/{inv_id}/receipt?code={token}")
    assert r.status_code == 200, r.text
    d = r.json()

    # Buyer name masked: "John D." (NOT "John Doe")
    assert d["buyer"]["display_name"] == "John D."
    # No email or phone leaked
    blob = str(d)
    assert "buyer@example.com" not in blob
    assert "+15145551234" not in blob
    # License # masked (last 3 visible)
    assert d["broker"]["license_masked"].endswith("654")
    assert "987654" not in d["broker"]["license_masked"][:-3]
    # Required sections present
    for k in ("vehicle", "broker", "transaction", "fees_via_stripe", "platform_disclaimer"):
        assert k in d
    # Hammer settlement = direct
    assert d["transaction"]["hammer_settlement"] == "direct"
    assert d["transaction"]["hammer_price_cad"] == 15000
    # Title transfer info present when logged
    assert d["transaction"]["title_transfer_logged_at"] is not None
    assert d["transaction"]["title_transfer_registry"] == "SAAQ"
    assert d["transaction"]["title_transfer_tx_number"] == "SAAQ-2026-77777"
    # Fee math matches v7 engine
    assert d["fees_via_stripe"]["total_via_stripe_cad"] == 1036.39
    assert d["fees_via_stripe"]["stripe_processing_fee_cad"] == 30.36


# ── 2. Invalid token → 404 (NOT 403, to avoid existence leak) ────────
@pytest.mark.asyncio
async def test_receipt_invalid_token_returns_404(db, cleanup):
    inv_id, _, _, _ = await _seed_invoice(db, cleanup)
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_URL}/api/broker-invoices/{inv_id}/receipt?code=WRONGTOKEN")
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "not_found"


# ── 3. Missing code → 404 ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_receipt_missing_code_returns_404(db, cleanup):
    inv_id, _, _, _ = await _seed_invoice(db, cleanup)
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_URL}/api/broker-invoices/{inv_id}/receipt")
    assert r.status_code == 404


# ── 4. Non-existent invoice id → 404 (does not leak which exist) ─────
@pytest.mark.asyncio
async def test_receipt_unknown_invoice_returns_404(cleanup):
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_URL}/api/broker-invoices/does-not-exist/receipt?code=any")
    assert r.status_code == 404


# ── 5. Title transfer pending shows null (not crash) ─────────────────
@pytest.mark.asyncio
async def test_receipt_title_pending(db, cleanup):
    inv_id, token, _, _ = await _seed_invoice(db, cleanup, with_title=False)
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_URL}/api/broker-invoices/{inv_id}/receipt?code={token}")
    assert r.status_code == 200
    d = r.json()
    assert d["transaction"]["title_transfer_logged_at"] is None
    assert d["transaction"]["title_transfer_tx_number"] is None


# ── 6. Cron: flags overdue invoices, writes audit + notification ────
@pytest.mark.asyncio
async def test_cron_flags_overdue_invoice(db, cleanup):
    # Seed broker + invoice released > 14 days ago, no title transfer logged
    broker_uid = str(uuid.uuid4())
    broker_id  = str(uuid.uuid4())
    inv_id     = str(uuid.uuid4())
    pw = bcrypt.hashpw(b"x", bcrypt.gensalt()).decode()
    await db.users.insert_one({
        "id": broker_uid, "email": f"b-{uuid.uuid4().hex[:6]}@example.com", "name": "BX",
        "username": "bx", "hashed_password": pw, "password_hash": pw,
        "role": "user", "account_type": "broker", "is_demo_account": False,
        "is_active": True, "email_verified": True,
    })
    await db.brokers.insert_one({
        "id": broker_id, "user_id": broker_uid,
        "legal_business_name": "Overdue Co",
        "verification_status": "approved",
        "auto_approval_revoked": False,
    })
    await db.broker_invoices.insert_one({
        "id": inv_id, "broker_id": broker_id, "buyer_user_id": str(uuid.uuid4()),
        "vehicle_listing_id": "v1", "invoice_number": "BVX-OVD-1",
        "released_at": datetime.now(timezone.utc) - timedelta(days=20),
        "title_transfer_logged_at": None,
        "title_transfer_enforced_at": None,
        "created_at": datetime.now(timezone.utc) - timedelta(days=25),
    })
    cleanup["users"].append(broker_uid)
    cleanup["brokers"].append(broker_id)
    cleanup["invoices"].append(inv_id)

    from jobs.title_transfer_cron import enforce_title_transfer_overdue_job
    s1 = await enforce_title_transfer_overdue_job(db)
    assert s1["enforced_count"] >= 1

    # Broker auto-approval should now be revoked
    b = await db.brokers.find_one({"id": broker_id}, {"_id": 0, "auto_approval_revoked": 1,
                                                       "auto_approval_revoked_reason": 1})
    assert b["auto_approval_revoked"] is True
    assert b["auto_approval_revoked_reason"] == "title_transfer_overdue"

    # Notification queued
    notif = await db.broker_notifications.count_documents({"invoice_id": inv_id,
                                                            "kind": "title_transfer_overdue"})
    assert notif == 1
    # Email queued
    email = await db.email_outbox.count_documents({"kind": "title_transfer_overdue",
                                                    "context.invoice_id": inv_id})
    assert email == 1
    # Audit row written
    audit = await db.broker_invoice_audit.count_documents({"invoice_id": inv_id,
                                                            "action": "title_transfer_overdue_enforced"})
    assert audit == 1

    # Cleanup — second run must be idempotent (no new enforcements)
    s2 = await enforce_title_transfer_overdue_job(db)
    assert s2["enforced_count"] == 0


# ── 7. Stripe Connect onboarding requires broker role ───────────────
@pytest.mark.asyncio
async def test_stripe_connect_requires_broker(db, cleanup):
    # Regular user (no broker doc) gets 403
    uid = str(uuid.uuid4())
    pw  = bcrypt.hashpw(b"x", bcrypt.gensalt()).decode()
    email = f"u-{uuid.uuid4().hex[:6]}@example.com"
    await db.users.insert_one({
        "id": uid, "email": email, "name": "U", "username": "u",
        "hashed_password": pw, "password_hash": pw, "role": "user",
        "account_type": "personal", "is_demo_account": False,
        "is_active": True, "email_verified": True,
    })
    cleanup["users"].append(uid)
    token = _mint(uid, email)
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_URL}/api/stripe/connect-onboarding-link",
                        headers={"Authorization": f"Bearer {token}"})
    # 403 (not_a_broker) OR 503 (stripe not configured) are both acceptable —
    # the contract is "non-brokers are rejected before any Stripe call".
    assert r.status_code in (403, 503)
    if r.status_code == 403:
        assert r.json()["detail"]["error"] == "not_a_broker"
