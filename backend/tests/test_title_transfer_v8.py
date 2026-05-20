"""
iter217 Phase 5 Hotfix v8 — Title Transfer Tracker tests.

Covers:
  • PATCH /api/broker-invoices/{id}/log-title-transfer
      - Requires released_at to be set
      - Rejects double-log
      - Only the owning broker can log
      - Auto-fills registry from province
      - Audit log written
      - Buyer email queued in email_outbox
  • GET  /api/admin/broker-invoices/missing-title-transfer
      - Admin-only
      - Returns invoices released > 14 days ago without a log
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
    return _jwt.encode({
        "sub": uid, "email": email, "role": role, "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
    }, JWT_SECRET, algorithm="HS256")


@pytest.fixture
def db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture
def cleanup(db):
    """Yields a list to append IDs to; deletes on teardown."""
    state = {"users": [], "brokers": [], "invoices": [], "audits": [], "outbox": []}
    yield state
    sync = MongoClient(os.environ["MONGO_URL"])
    sdb  = sync[os.environ["DB_NAME"]]
    for uid in state["users"]:    sdb.users.delete_one({"id": uid})
    for bid in state["brokers"]:  sdb.brokers.delete_one({"id": bid})
    for iid in state["invoices"]:
        sdb.broker_invoices.delete_one({"id": iid})
        sdb.broker_invoice_audit.delete_many({"invoice_id": iid})
        sdb.email_outbox.delete_many({"context.invoice_id": iid})
    sync.close()


async def _make_broker_with_invoice(db, cleanup, *, released=True, hours_ago_released=1):
    """Seed a broker user + invoice. Returns (broker_token, broker_id,
    invoice_id, buyer_user_id)."""
    broker_uid   = str(uuid.uuid4())
    broker_email = f"broker-{uuid.uuid4().hex[:6]}@example.com"
    broker_id    = str(uuid.uuid4())
    invoice_id   = str(uuid.uuid4())
    buyer_uid    = str(uuid.uuid4())
    pw_hash      = bcrypt.hashpw(b"x", bcrypt.gensalt()).decode()

    await db.users.insert_one({
        "id": broker_uid, "email": broker_email, "name": "B", "username": broker_email.split("@")[0],
        "hashed_password": pw_hash, "password_hash": pw_hash,
        "role": "user", "account_type": "broker",
        "is_demo_account": False, "is_active": True, "email_verified": True,
    })
    await db.users.insert_one({
        "id": buyer_uid, "email": f"buyer-{uuid.uuid4().hex[:6]}@example.com",
        "name": "buyer", "username": "buyer", "hashed_password": pw_hash, "password_hash": pw_hash,
        "role": "user", "account_type": "personal",
        "is_demo_account": False, "is_active": True, "email_verified": True,
    })
    await db.brokers.insert_one({
        "id": broker_id, "user_id": broker_uid,
        "legal_business_name": "Title Transfer Test Co",
        "verification_status": "approved",
        "broker_license_number": "LIC-9999",
        "created_at": datetime.now(timezone.utc) - timedelta(days=10),
    })
    inv = {
        "id": invoice_id, "broker_id": broker_id, "buyer_user_id": buyer_uid,
        "vehicle_listing_id": "veh-1",
        "invoice_number": f"BVX-2026-{uuid.uuid4().hex[:6].upper()}",
        "hammer_price_cad": 15000,
        "released_at": None,
    }
    if released:
        inv["released_at"] = datetime.now(timezone.utc) - timedelta(hours=hours_ago_released)
    await db.broker_invoices.insert_one(inv)

    cleanup["users"].extend([broker_uid, buyer_uid])
    cleanup["brokers"].append(broker_id)
    cleanup["invoices"].append(invoice_id)
    return _mint(broker_uid, broker_email), broker_id, invoice_id, buyer_uid


# ── 1. Rejected if vehicle not released yet ──────────────────────────
@pytest.mark.asyncio
async def test_log_title_transfer_requires_release(db, cleanup):
    token, _, inv_id, _ = await _make_broker_with_invoice(db, cleanup, released=False)
    async with httpx.AsyncClient() as c:
        r = await c.patch(f"{API_URL}/api/broker-invoices/{inv_id}/log-title-transfer", json={
            "registry_tx_number": "SAAQ-2026-12345",
            "province": "QC",
            "transfer_date": datetime.now(timezone.utc).isoformat(),
        }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "release_required_first"


# ── 2. Successful log + audit + buyer email queued + auto-registry ──
@pytest.mark.asyncio
async def test_log_title_transfer_success(db, cleanup):
    token, _, inv_id, buyer_uid = await _make_broker_with_invoice(db, cleanup, released=True)
    async with httpx.AsyncClient() as c:
        r = await c.patch(f"{API_URL}/api/broker-invoices/{inv_id}/log-title-transfer", json={
            "registry_tx_number": "SAAQ-2026-99999",
            "province": "QC",
            "transfer_date": datetime.now(timezone.utc).isoformat(),
        }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["success"] is True
    assert d["registry"] == "SAAQ"                  # auto-filled for QC
    assert d["registry_tx_number"] == "SAAQ-2026-99999"

    # Invoice doc was updated
    inv = await db.broker_invoices.find_one({"id": inv_id}, {"_id": 0})
    assert inv["title_transfer_logged_at"] is not None
    assert inv["title_transfer_tx_number"] == "SAAQ-2026-99999"
    assert inv["title_transfer_registry"]  == "SAAQ"
    assert inv["title_transfer_province"]  == "QC"

    # Audit row written
    audit_count = await db.broker_invoice_audit.count_documents({"invoice_id": inv_id, "action": "log_title_transfer"})
    assert audit_count == 1

    # Buyer email queued
    queued = await db.email_outbox.count_documents({"context.invoice_id": inv_id, "to_user_id": buyer_uid, "kind": "title_transfer_filed"})
    assert queued == 1


# ── 3. Double-log rejected ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_log_title_transfer_double_rejected(db, cleanup):
    token, _, inv_id, _ = await _make_broker_with_invoice(db, cleanup, released=True)
    payload = {
        "registry_tx_number": "ON-2026-AAA",
        "province": "ON",
        "transfer_date": datetime.now(timezone.utc).isoformat(),
    }
    async with httpx.AsyncClient() as c:
        r1 = await c.patch(f"{API_URL}/api/broker-invoices/{inv_id}/log-title-transfer", json=payload,
                           headers={"Authorization": f"Bearer {token}"})
        assert r1.status_code == 200
        r2 = await c.patch(f"{API_URL}/api/broker-invoices/{inv_id}/log-title-transfer", json=payload,
                           headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 400
    assert r2.json()["detail"]["error"] == "already_logged"


# ── 4. Cannot log another broker's invoice ──────────────────────────
@pytest.mark.asyncio
async def test_log_title_transfer_other_broker_forbidden(db, cleanup):
    # Broker A owns the invoice
    _, broker_id_a, inv_id, _ = await _make_broker_with_invoice(db, cleanup, released=True)

    # Broker B logs in
    broker_b_uid   = str(uuid.uuid4())
    broker_b_email = f"b2-{uuid.uuid4().hex[:6]}@example.com"
    broker_b_id    = str(uuid.uuid4())
    pw_hash = bcrypt.hashpw(b"x", bcrypt.gensalt()).decode()
    await db.users.insert_one({
        "id": broker_b_uid, "email": broker_b_email, "name": "B2", "username": "b2",
        "hashed_password": pw_hash, "password_hash": pw_hash, "role": "user",
        "account_type": "broker", "is_demo_account": False, "is_active": True, "email_verified": True,
    })
    await db.brokers.insert_one({
        "id": broker_b_id, "user_id": broker_b_uid, "verification_status": "approved",
        "legal_business_name": "Stranger",
    })
    cleanup["users"].append(broker_b_uid)
    cleanup["brokers"].append(broker_b_id)

    token_b = _mint(broker_b_uid, broker_b_email)
    async with httpx.AsyncClient() as c:
        r = await c.patch(f"{API_URL}/api/broker-invoices/{inv_id}/log-title-transfer", json={
            "registry_tx_number": "STOLEN-001",
            "province": "ON",
            "transfer_date": datetime.now(timezone.utc).isoformat(),
        }, headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 403


# ── 5. Admin missing-title-transfer list ─────────────────────────────
@pytest.mark.asyncio
async def test_admin_missing_title_transfer_list(db, cleanup):
    # Seed an invoice released > 14 days ago and not logged
    _, _, inv_id, _ = await _make_broker_with_invoice(db, cleanup, released=True, hours_ago_released=24 * 15)

    # Admin token
    admin_uid   = str(uuid.uuid4())
    admin_email = f"admin-{uuid.uuid4().hex[:6]}@example.com"
    pw_hash = bcrypt.hashpw(b"x", bcrypt.gensalt()).decode()
    await db.users.insert_one({
        "id": admin_uid, "email": admin_email, "name": "Adm", "username": "adm",
        "hashed_password": pw_hash, "password_hash": pw_hash, "role": "admin", "is_admin": True,
        "account_type": "admin", "is_demo_account": False, "is_active": True, "email_verified": True,
    })
    cleanup["users"].append(admin_uid)
    admin_token = _mint(admin_uid, admin_email, "admin")

    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_URL}/api/admin/broker-invoices/missing-title-transfer",
                        headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    ids = [row["invoice_id"] for row in r.json()["data"]]
    assert inv_id in ids
