"""
iter217 Phase 5 Hotfix v6.5 — Broker Subscription Management tests.

Covers:
- Default global settings ($200 base, 50% launch discount → $100 final)
- Admin can update global settings (idempotent upsert)
- Admin per-broker override: discount, free access (requires note), suspend,
  extend, expiry, status transitions
- Subscription list endpoint with filters + search
- Revenue summary endpoint (ARR / MRR / discounted vs full / lost)
- Audit log endpoint
- Broker apply accepts document URLs
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

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


# ── Helpers ───────────────────────────────────────────────────────────
def _mint(user_id: str, email: str, role: str = "user") -> str:
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
    created_ids = []

    async def _make(is_admin=False, account_type="personal"):
        email   = f"sub-test-{uuid.uuid4().hex[:6]}@example.com"
        user_id = str(uuid.uuid4())
        pw      = bcrypt.hashpw(b"TestPass123!", bcrypt.gensalt()).decode()
        await db.users.insert_one({
            "id": user_id, "email": email, "name": "Sub Test", "full_name": "Sub Test",
            "username": email.split("@")[0],
            "hashed_password": pw, "password_hash": pw,
            "role": "admin" if is_admin else "user",
            "is_admin": is_admin,
            "account_type": account_type,
            "email_verified": True, "is_active": True, "is_demo_account": False,
        })
        created_ids.append(user_id)
        token = _mint(user_id, email, "admin" if is_admin else "user")
        return {"id": user_id, "email": email, "token": token}

    yield _make

    sync = MongoClient(os.environ["MONGO_URL"])
    sdb  = sync[os.environ["DB_NAME"]]
    for uid in created_ids:
        sdb.users.delete_one({"id": uid})
        sdb.brokers.delete_many({"user_id": uid})
    sync.close()


async def _make_broker(token: str, license_no: str | None = None) -> str:
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{API_URL}/api/brokers/apply", json={
            "legal_business_name":           f"Subs Co {uuid.uuid4().hex[:6]}",
            "operating_province":            "ON",
            "corporate_registration_number": "REG-" + uuid.uuid4().hex[:8],
            "broker_license_number":         license_no or ("LIC-" + uuid.uuid4().hex[:8]),
            "regulatory_body":               "OMVIC",
            "permit_type":                   "broker",
            "fee_structure": {
                "type":             "fixed",
                "fixed_amount_cad": 500.0,
                "percentage_rate":  0.0,
            },
            "default_deposit_amount_cad": 500.0,
        }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    return r.json()["broker_id"]


# ── 1. Global Settings ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_global_settings_defaults(make_user):
    admin = await make_user(is_admin=True)
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_URL}/api/admin/subscriptions/settings",
                        headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["plan_name"] == "BidVex Broker Annual Plan"
    assert d["base_cad"] == 200.0
    assert d["currency"] == "CAD"
    assert d["discount_active"] is True
    assert d["discount_type"] == "percentage"
    assert d["discount_value"] == 50.0
    assert d["period_days"] == 365
    assert d["auto_renew"] is True


@pytest.mark.asyncio
async def test_global_settings_non_admin_forbidden(make_user):
    user = await make_user(is_admin=False)
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_URL}/api/admin/subscriptions/settings",
                        headers={"Authorization": f"Bearer {user['token']}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_global_settings_update_persists(make_user):
    admin = await make_user(is_admin=True)
    async with httpx.AsyncClient() as c:
        r = await c.patch(f"{API_URL}/api/admin/subscriptions/settings", json={
            "base_cad": 250.0, "discount_value": 25.0, "discount_label": "Q2 Promo"
        }, headers={"Authorization": f"Bearer {admin['token']}"})
        assert r.status_code == 200, r.text
        assert r.json()["base_cad"] == 250.0
        # Verify persisted
        r2 = await c.get(f"{API_URL}/api/admin/subscriptions/settings",
                         headers={"Authorization": f"Bearer {admin['token']}"})
        assert r2.json()["base_cad"] == 250.0
        # Restore defaults
        await c.patch(f"{API_URL}/api/admin/subscriptions/settings", json={
            "base_cad": 200.0, "discount_value": 50.0, "discount_label": "Launch Offer — 50% OFF"
        }, headers={"Authorization": f"Bearer {admin['token']}"})


@pytest.mark.asyncio
async def test_global_settings_reject_negative_base(make_user):
    admin = await make_user(is_admin=True)
    async with httpx.AsyncClient() as c:
        r = await c.patch(f"{API_URL}/api/admin/subscriptions/settings",
                          json={"base_cad": -10},
                          headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_global_settings_reject_pct_over_100(make_user):
    admin = await make_user(is_admin=True)
    async with httpx.AsyncClient() as c:
        r = await c.patch(f"{API_URL}/api/admin/subscriptions/settings",
                          json={"discount_type": "percentage", "discount_value": 150},
                          headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 422


# ── 2. Per-Broker Overrides ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_broker_default_pricing_50pct_off(make_user):
    user = await make_user()
    await _make_broker(user["token"])
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_URL}/api/brokers/me/subscription",
                        headers={"Authorization": f"Bearer {user['token']}"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["base_cad"] == 200.0
    assert d["discount_pct"] == 50.0
    assert d["final_cad"] == 100.0
    assert d["plan_name"] == "BidVex Broker Annual Plan"


@pytest.mark.asyncio
async def test_admin_apply_100pct_discount(make_user):
    admin = await make_user(is_admin=True)
    user  = await make_user()
    bid   = await _make_broker(user["token"])
    async with httpx.AsyncClient() as c:
        r = await c.patch(f"{API_URL}/api/admin/brokers/{bid}/subscription",
                          json={"discount_pct": 100.0},
                          headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    assert r.json()["pricing"]["final_cad"] == 0.0


@pytest.mark.asyncio
async def test_free_access_requires_note(make_user):
    admin = await make_user(is_admin=True)
    user  = await make_user()
    bid   = await _make_broker(user["token"])
    async with httpx.AsyncClient() as c:
        # Without note → 422
        r = await c.patch(f"{API_URL}/api/admin/brokers/{bid}/subscription",
                          json={"free_access": True},
                          headers={"Authorization": f"Bearer {admin['token']}"})
        assert r.status_code == 422
        # With note → 200 + status=free + 100% off
        r = await c.patch(f"{API_URL}/api/admin/brokers/{bid}/subscription",
                          json={"free_access": True, "note": "VIP partner — comp granted."},
                          headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    d = r.json()["pricing"]
    assert d["status"] == "free"
    assert d["discount_pct"] == 100.0
    assert d["final_cad"] == 0.0


@pytest.mark.asyncio
async def test_extend_days_pushes_expires_at(make_user):
    admin = await make_user(is_admin=True)
    user  = await make_user()
    bid   = await _make_broker(user["token"])
    async with httpx.AsyncClient() as c:
        r = await c.patch(f"{API_URL}/api/admin/brokers/{bid}/subscription",
                          json={"status": "active", "extend_days": 30},
                          headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    assert r.json()["pricing"]["expires_at"] is not None


@pytest.mark.asyncio
async def test_suspend_then_reactivate(make_user):
    admin = await make_user(is_admin=True)
    user  = await make_user()
    bid   = await _make_broker(user["token"])
    async with httpx.AsyncClient() as c:
        r = await c.patch(f"{API_URL}/api/admin/brokers/{bid}/subscription",
                          json={"status": "suspended"},
                          headers={"Authorization": f"Bearer {admin['token']}"})
        assert r.json()["pricing"]["status"] == "suspended"
        r = await c.patch(f"{API_URL}/api/admin/brokers/{bid}/subscription",
                          json={"status": "active"},
                          headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.json()["pricing"]["status"] == "active"


# ── 3. List + Search ──────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_subscription_list_returns_data(make_user):
    admin = await make_user(is_admin=True)
    user  = await make_user()
    needle = f"NeedleCo{uuid.uuid4().hex[:6]}"
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{API_URL}/api/brokers/apply", json={
            "legal_business_name":           needle,
            "operating_province":            "ON",
            "corporate_registration_number": "REG-X",
            "broker_license_number":         "LIC-X-" + uuid.uuid4().hex[:6],
            "regulatory_body":               "OMVIC",
            "permit_type":                   "broker",
            "fee_structure":                 {"type": "fixed", "fixed_amount_cad": 100.0, "percentage_rate": 0.0},
            "default_deposit_amount_cad":    500.0,
        }, headers={"Authorization": f"Bearer {user['token']}"})
        assert r.status_code == 200, r.text

        r = await c.get(f"{API_URL}/api/admin/subscriptions/list?search={needle}",
                        headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200
    rows = r.json()["data"]
    assert any(row["legal_business_name"] == needle for row in rows)


# ── 4. Revenue Summary ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_revenue_summary_keys(make_user):
    admin = await make_user(is_admin=True)
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_URL}/api/admin/subscriptions/revenue",
                        headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("total_brokers", "active", "free", "comp", "suspended",
              "unpaid", "arr_cad", "mrr_cad", "revenue_lost_cad"):
        assert k in d, f"missing key {k}"


# ── 5. Audit Log ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_audit_records_override(make_user):
    admin = await make_user(is_admin=True)
    user  = await make_user()
    bid   = await _make_broker(user["token"])
    async with httpx.AsyncClient() as c:
        await c.patch(f"{API_URL}/api/admin/brokers/{bid}/subscription",
                      json={"discount_pct": 25.0, "note": "discount via test"},
                      headers={"Authorization": f"Bearer {admin['token']}"})
        r = await c.get(f"{API_URL}/api/admin/subscriptions/audit/{bid}",
                        headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    assert r.json()["count"] >= 1


# ── 6. Broker apply accepts document URLs ─────────────────────────────
@pytest.mark.asyncio
async def test_broker_apply_with_document_urls(make_user):
    user = await make_user()
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{API_URL}/api/brokers/apply", json={
            "legal_business_name":           "Docs Inc " + uuid.uuid4().hex[:6],
            "operating_province":            "ON",
            "corporate_registration_number": "REG-D",
            "broker_license_number":         "LIC-D-" + uuid.uuid4().hex[:6],
            "regulatory_body":               "OMVIC",
            "permit_type":                   "broker",
            "license_document_url":          "https://example.com/license.pdf",
            "registration_document_url":     "https://example.com/registration.pdf",
            "additional_documents":          ["https://example.com/id.jpg"],
            "fee_structure":                 {"type": "fixed", "fixed_amount_cad": 500.0, "percentage_rate": 0.0},
            "default_deposit_amount_cad":    500.0,
        }, headers={"Authorization": f"Bearer {user['token']}"})
        assert r.status_code == 200, r.text
        r2 = await c.get(f"{API_URL}/api/brokers/me",
                         headers={"Authorization": f"Bearer {user['token']}"})
    d  = r2.json()
    assert d["license_document_url"] == "https://example.com/license.pdf"
    assert d["registration_document_url"] == "https://example.com/registration.pdf"
    assert d["additional_documents"] == ["https://example.com/id.jpg"]
