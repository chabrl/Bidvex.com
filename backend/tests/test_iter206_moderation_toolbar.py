"""
iter206 — Approve / Reject Toolbar + Seller Notifications
==========================================================
Backend integration tests for:
  • GET  /api/admin/compliance-alerts                  — pending_review queue
  • POST /api/admin/listings/{id}/approve              — admin override
  • POST /api/admin/listings/{id}/reject               — admin reject
  • POST /api/admin/compliance/run-cleanup             — manual watchdog trigger
  • GET  /api/dashboard/seller/notifications           — seller-facing pause notice

End-to-end story:
  1. Seller (non-dealer) lists a "ford f150"
  2. Watchdog pauses it → admin notification + seller notification both written
  3. Admin sees it in the moderation queue
  4. Admin approves with note → listing back to active, seller gets approval email,
     audit log + admin_notifications resolved row both written
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
import httpx
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(Path("/app/backend")))
load_dotenv("/app/backend/.env")

BACKEND_URL = "http://localhost:8001/api"


@pytest.fixture
def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


async def _admin_token() -> str:
    """Cached admin login — avoids hitting the auth/login rate limit."""
    if "_cached" in _admin_token.__dict__:
        return _admin_token._cached  # type: ignore[attr-defined]
    async with httpx.AsyncClient(timeout=10) as h:
        r = await h.post(
            f"{BACKEND_URL}/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        )
    r.raise_for_status()
    _admin_token._cached = r.json()["access_token"]  # type: ignore[attr-defined]
    return _admin_token._cached  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Pending-review moderation queue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compliance_alerts_includes_pending_review_queue(db):
    """Seed a paused listing → admin compliance-alerts must surface it."""
    seller_id = "iter206-q-seller"
    listing_id = "iter206-q-listing"
    await db.users.update_one(
        {"id": seller_id},
        {"$set": {"id": seller_id, "email": "qseller@iter206.example.com",
                  "seller_type": "individual", "dealer_license_verified": False}},
        upsert=True,
    )
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {
            "id": listing_id, "seller_id": seller_id,
            "status": "pending_review",
            "category": "Heavy Equipment", "title": "ford f150 — test",
            "description": "", "previous_status": "active",
            "compliance_signals": ["model:f150", "brand-in-title:ford"],
            "compliance_strength": 8,
            "paused_by": "iter206_test", "paused_reason": "vehicle_listing_by_non_dealer",
            "paused_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    try:
        token = await _admin_token()
        async with httpx.AsyncClient(timeout=10) as h:
            r = await h.get(
                f"{BACKEND_URL}/admin/compliance-alerts",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200
        body = r.json()
        queue = body.get("pending_review_queue") or []
        # Our seeded listing must be in the queue
        match = next((e for e in queue if e["listing_id"] == listing_id), None)
        assert match is not None, "Pending listing missing from queue"
        assert match["seller_email"] == "qseller@iter206.example.com"
        assert match["seller_dealer_verified"] is False
        assert "model:f150" in match["compliance_signals"]
        assert match["paused_reason"] == "vehicle_listing_by_non_dealer"
    finally:
        await db.listings.delete_one({"id": listing_id})
        await db.users.delete_one({"id": seller_id})


@pytest.mark.asyncio
async def test_compliance_alerts_count_includes_queue(db):
    """The /count endpoint must include pending_review queue items."""
    listing_id = "iter206-count-listing"
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {
            "id": listing_id, "seller_id": "iter206-count-seller",
            "status": "pending_review", "category": "Other",
            "title": "honda civic test",
            "compliance_signals": ["model:civic"],
            "paused_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    try:
        token = await _admin_token()
        async with httpx.AsyncClient(timeout=10) as h:
            r = await h.get(
                f"{BACKEND_URL}/admin/compliance-alerts/count",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200
        assert r.json()["total"] >= 1
    finally:
        await db.listings.delete_one({"id": listing_id})


# ---------------------------------------------------------------------------
# Approve action
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_approve_restores_listing_and_audits(db):
    """Approve action moves listing back to its previous status, writes audit,
    resolves admin_notifications, and (best-effort) emails the seller."""
    seller_id = "iter206-app-seller"
    listing_id = "iter206-app-listing"
    await db.users.update_one(
        {"id": seller_id},
        {"$set": {"id": seller_id, "email": "appseller@iter206.example.com",
                  "seller_type": "individual"}},
        upsert=True,
    )
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {
            "id": listing_id, "seller_id": seller_id,
            "status": "pending_review",
            "category": "Other", "title": "false-positive test",
            "previous_status": "active",
            "compliance_signals": ["model:civic"], "compliance_strength": 5,
            "paused_by": "iter206_test",
            "paused_at": datetime.now(timezone.utc).isoformat(),
            "paused_reason": "vehicle_listing_by_non_dealer",
        }},
        upsert=True,
    )
    # Pre-seed an admin notification so we can verify it gets resolved
    await db.admin_notifications.insert_one({
        "kind": "vehicle_compliance_violation",
        "subkind": "paused_by_watchdog",
        "listing_id": listing_id,
        "severity": "high",
        "read": False,
        "resolved": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        token = await _admin_token()
        async with httpx.AsyncClient(timeout=10) as h:
            r = await h.post(
                f"{BACKEND_URL}/admin/compliance/listings/{listing_id}/approve",
                json={"note": "Verified — owner is a dealer (manual override)"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["decision"] == "approved"
        assert body["restored_status"] == "active"
        # Listing flipped back
        listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
        assert listing["status"] == "active"
        assert listing.get("compliance_overridden") is True
        assert listing.get("approval_note", "").startswith("Verified")
        assert "paused_at" not in listing or listing.get("paused_at") is None
        # Audit log
        log = await db.audit_logs.find_one(
            {"action": "compliance_signals_overridden", "listing_id": listing_id}
        )
        assert log is not None
        assert log["decision"] == "approved"
        # Admin notification resolved
        notif = await db.admin_notifications.find_one({"listing_id": listing_id})
        assert notif["resolved"] is True
        assert notif["resolution"] == "approved"
        # Seller notification of resolution
        seller_notif = await db.seller_notifications.find_one(
            {"listing_id": listing_id, "kind": "vehicle_listing_approved"}
        )
        assert seller_notif is not None
    finally:
        await db.listings.delete_one({"id": listing_id})
        await db.users.delete_one({"id": seller_id})
        await db.audit_logs.delete_many({"listing_id": listing_id})
        await db.admin_notifications.delete_many({"listing_id": listing_id})
        await db.seller_notifications.delete_many({"listing_id": listing_id})


# ---------------------------------------------------------------------------
# Reject action
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_reject_moves_to_terminal_state(db):
    seller_id = "iter206-rej-seller"
    listing_id = "iter206-rej-listing"
    await db.users.update_one(
        {"id": seller_id},
        {"$set": {"id": seller_id, "email": "rejseller@iter206.example.com"}},
        upsert=True,
    )
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {
            "id": listing_id, "seller_id": seller_id,
            "status": "pending_review", "title": "ford f150 reject test",
            "compliance_signals": ["model:f150"], "compliance_strength": 8,
            "paused_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    try:
        token = await _admin_token()
        async with httpx.AsyncClient(timeout=10) as h:
            r = await h.post(
                f"{BACKEND_URL}/admin/compliance/listings/{listing_id}/reject",
                json={"note": "Confirmed vehicle, no dealer licence on file"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["decision"] == "rejected"
        listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
        assert listing["status"] == "rejected"
        assert listing.get("rejection_note", "").startswith("Confirmed")
        log = await db.audit_logs.find_one(
            {"action": "compliance_listing_rejected", "listing_id": listing_id}
        )
        assert log is not None
        seller_notif = await db.seller_notifications.find_one(
            {"listing_id": listing_id, "kind": "vehicle_listing_rejected"}
        )
        assert seller_notif is not None
    finally:
        await db.listings.delete_one({"id": listing_id})
        await db.users.delete_one({"id": seller_id})
        await db.audit_logs.delete_many({"listing_id": listing_id})
        await db.seller_notifications.delete_many({"listing_id": listing_id})


@pytest.mark.asyncio
async def test_admin_approve_404_when_listing_missing():
    token = await _admin_token()
    async with httpx.AsyncClient(timeout=10) as h:
        r = await h.post(
            f"{BACKEND_URL}/admin/compliance/listings/__missing__iter206/approve",
            json={"note": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_approve_400_when_not_pending_review(db):
    """An already-active listing cannot be 're-approved' — 400."""
    listing_id = "iter206-not-pending"
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {"id": listing_id, "status": "active", "title": "x"}},
        upsert=True,
    )
    try:
        token = await _admin_token()
        async with httpx.AsyncClient(timeout=10) as h:
            r = await h.post(
                f"{BACKEND_URL}/admin/compliance/listings/{listing_id}/approve",
                json={"note": "x"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 400
    finally:
        await db.listings.delete_one({"id": listing_id})


# ---------------------------------------------------------------------------
# Manual cleanup runner
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_run_cleanup_returns_summary(db):
    token = await _admin_token()
    async with httpx.AsyncClient(timeout=10) as h:
        r = await h.post(
            f"{BACKEND_URL}/admin/compliance/run-cleanup",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["triggered_by"] == "cleanup_script"
    assert "total_examined" in body
    assert "total_paused" in body


@pytest.mark.asyncio
async def test_admin_run_cleanup_requires_admin():
    async with httpx.AsyncClient(timeout=10) as h:
        r = await h.post(f"{BACKEND_URL}/admin/compliance/run-cleanup")
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Seller notifications
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seller_pause_notification_dispatched_on_watchdog_pause(db):
    """End-to-end: when the watchdog pauses a listing, a seller_notifications
    row must be written (best-effort SendGrid email is not asserted)."""
    seller_id = "iter206-snoti-seller"
    listing_id = "iter206-snoti-listing"
    await db.users.update_one(
        {"id": seller_id},
        {"$set": {"id": seller_id, "email": "snoti@iter206.example.com",
                  "seller_type": "individual"}},
        upsert=True,
    )
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {
            "id": listing_id, "seller_id": seller_id,
            "status": "active", "category": "Heavy Equipment",
            "title": "ford f150 — seller notify test", "description": "",
        }},
        upsert=True,
    )
    try:
        from services.safety_watchdog import run_safety_watchdog
        summary = await run_safety_watchdog(db, triggered_by="iter206_seller_test")
        assert summary["total_paused"] >= 1
        # Allow async fire-and-forget seller dispatch a tick to land
        import asyncio
        await asyncio.sleep(0.5)
        notif = await db.seller_notifications.find_one(
            {"listing_id": listing_id, "kind": "vehicle_listing_paused"},
        )
        assert notif is not None
        assert notif["severity"] == "high"
        assert "model:f150" in notif["detection_signals"]
    finally:
        await db.listings.delete_one({"id": listing_id})
        await db.users.delete_one({"id": seller_id})
        await db.audit_logs.delete_many({"listing_id": listing_id})
        await db.admin_notifications.delete_many({"listing_id": listing_id})
        await db.seller_notifications.delete_many({"listing_id": listing_id})


@pytest.mark.asyncio
async def test_seller_dashboard_notifications_endpoint(db):
    """GET /api/dashboard/seller/notifications must return the seller's rows."""
    # Use the existing test buyer (seeded in iter205)
    async with httpx.AsyncClient(timeout=10) as h:
        login = await h.post(
            f"{BACKEND_URL}/auth/login",
            json={"email": "iter189buyer@test.com", "password": "TestBuyer123!"},
        )
    if login.status_code != 200:
        pytest.skip("test buyer credentials missing")
    token = login.json()["access_token"]
    user = login.json().get("user") or {}
    user_id = user.get("id")
    # Seed a notification for this user
    notif_id = "iter206-buyer-notif"
    await db.seller_notifications.insert_one({
        "_test_id": notif_id,
        "kind": "vehicle_listing_paused",
        "severity": "high",
        "seller_id": user_id,
        "listing_id": "iter206-x",
        "title": "x",
        "detection_signals": ["model:f150"],
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        async with httpx.AsyncClient(timeout=10) as h:
            r = await h.get(
                f"{BACKEND_URL}/dashboard/seller/notifications",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200
        body = r.json()
        assert "notifications" in body
        assert "unread" in body
        assert body["unread"] >= 1
    finally:
        await db.seller_notifications.delete_many({"_test_id": notif_id})
