"""
iter204 — Compliance Health KPI tests
======================================
Tests for the `/api/admin/compliance/health` endpoint that powers the
green/yellow/red traffic-light KPI on Admin Home.

Status bands tested:
  • green  — all systems nominal
  • yellow — 1+ pending_review listings
  • red    — 5+ pending_review OR watchdog overdue

Plus shape/auth contract checks.
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
# Auth / shape contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compliance_health_requires_admin():
    async with httpx.AsyncClient(timeout=10) as h:
        r = await h.get(f"{BACKEND_URL}/admin/compliance/health")
    assert r.status_code in (401, 403), r.text


@pytest.mark.asyncio
async def test_compliance_health_response_shape():
    token = await _admin_token()
    async with httpx.AsyncClient(timeout=10) as h:
        r = await h.get(
            f"{BACKEND_URL}/admin/compliance/health",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    for key in (
        "status", "status_reasons", "pending_review",
        "pending_review_breakdown", "blocked_today",
        "paused_by_ai_today", "paused_by_watchdog_today",
        "ai_unavailable_last_hour", "last_watchdog_run",
        "minutes_since_last_watchdog", "checked_at",
    ):
        assert key in body, f"missing key {key}"
    assert body["status"] in ("green", "yellow", "red")
    assert isinstance(body["status_reasons"], list)
    assert len(body["status_reasons"]) >= 1
    assert isinstance(body["pending_review_breakdown"], dict)


# ---------------------------------------------------------------------------
# Status band logic — uses real DB inserts, then cleans up
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compliance_health_yellow_with_one_pending_review(db):
    token = await _admin_token()
    listing_id = "iter204-pending-1"
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {
            "id": listing_id,
            "seller_id": "iter204-seller",
            "status": "pending_review",
            "category": "Cars",
            "title": "Test pending listing",
            "description": "test",
            "paused_at": datetime.now(timezone.utc).isoformat(),
            "paused_reason": "vehicle_listing_by_non_dealer",
        }},
        upsert=True,
    )
    # Make sure a recent watchdog run exists so we don't fall to red
    await db.audit_logs.insert_one({
        "action": "watchdog_run",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_examined": 1,
        "total_paused": 0,
        "triggered_by": "test_setup",
    })
    try:
        async with httpx.AsyncClient(timeout=10) as h:
            r = await h.get(
                f"{BACKEND_URL}/admin/compliance/health",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["pending_review"] >= 1
        assert body["status"] in ("yellow", "red")
        # Reason text mentions the count
        assert any("pending_review" in s or "review" in s for s in body["status_reasons"])
    finally:
        await db.listings.delete_one({"id": listing_id})
        await db.audit_logs.delete_many({
            "action": "watchdog_run", "triggered_by": "test_setup",
        })


@pytest.mark.asyncio
async def test_compliance_health_red_with_five_plus_pending(db):
    token = await _admin_token()
    ids = [f"iter204-red-{i}" for i in range(6)]
    for lid in ids:
        await db.listings.update_one(
            {"id": lid},
            {"$set": {
                "id": lid,
                "seller_id": "iter204-seller",
                "status": "pending_review",
                "category": "Cars",
                "title": f"red test {lid}",
                "description": "x",
            }},
            upsert=True,
        )
    await db.audit_logs.insert_one({
        "action": "watchdog_run",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_examined": 6,
        "total_paused": 0,
        "triggered_by": "test_setup",
    })
    try:
        async with httpx.AsyncClient(timeout=10) as h:
            r = await h.get(
                f"{BACKEND_URL}/admin/compliance/health",
                headers={"Authorization": f"Bearer {token}"},
            )
        body = r.json()
        assert body["pending_review"] >= 5
        assert body["status"] == "red"
    finally:
        await db.listings.delete_many({"id": {"$in": ids}})
        await db.audit_logs.delete_many({
            "action": "watchdog_run", "triggered_by": "test_setup",
        })


@pytest.mark.asyncio
async def test_compliance_health_red_when_watchdog_never_ran(db):
    """Save existing watchdog_run docs, delete them, verify red."""
    token = await _admin_token()
    backup_cursor = db.audit_logs.find(
        {"action": "watchdog_run"}, {"_id": 1}
    )
    backup_ids = [doc["_id"] async for doc in backup_cursor]
    # Move them to a temp marker; pytest will restore in finally
    if backup_ids:
        await db.audit_logs.update_many(
            {"_id": {"$in": backup_ids}},
            {"$set": {"action": "watchdog_run__test_hidden"}},
        )
    # Also hide pending_review listings we don't control
    pre_pending = await db.listings.count_documents({"status": "pending_review"})
    pre_pending += await db.multi_item_listings.count_documents({"status": "pending_review"})
    try:
        async with httpx.AsyncClient(timeout=10) as h:
            r = await h.get(
                f"{BACKEND_URL}/admin/compliance/health",
                headers={"Authorization": f"Bearer {token}"},
            )
        body = r.json()
        # When watchdog never ran the status MUST be red — even if the queue
        # is otherwise clean (pre_pending == 0)
        assert body["last_watchdog_run"] is None
        assert body["status"] == "red"
        assert any("Watchdog has never run" in s for s in body["status_reasons"])
    finally:
        if backup_ids:
            await db.audit_logs.update_many(
                {"_id": {"$in": backup_ids}},
                {"$set": {"action": "watchdog_run"}},
            )
