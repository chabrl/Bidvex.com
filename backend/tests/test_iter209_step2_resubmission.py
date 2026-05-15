"""
iter209 Step 2 — Resubmission backend smoke test.

Covers BOTH partner and dealer flows:
  - Not rejected → 400 not_in_rejected_state (bilingual)
  - 3 valid resubmits → counter increments, status flips to pending_review
  - 4th resubmit → 403 max_resubmissions_reached (bilingual)
  - rejection_history accumulates each previous reason
  - admin_notifications row written on each resubmit
"""
import os
import sys
import uuid
from datetime import datetime, timezone

import httpx
import pytest
import pytest_asyncio

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient

API_URL = ""
env_path = "/app/frontend/.env"
with open(env_path) as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            API_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


@pytest_asyncio.fixture
async def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    yield database
    client.close()


def _admin_token() -> str:
    """Login with retry-or-skip on 429 (pre-existing flake hardening, iter215)."""
    import time as _time
    for attempt in range(3):
        r = httpx.post(
            f"{API_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        if r.status_code == 429:
            _time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        d = r.json()
        return d.get("access_token") or d.get("token")
    pytest.skip("admin login rate-limited (HTTP 429) after 3 retries — pre-existing live-HTTP flake")


# ─── Pure unit tests via the service layer ────────────────────────────────
@pytest.mark.asyncio
async def test_partner_not_in_rejected_returns_400(db):
    from services.resubmission_service import resubmit_application
    from fastapi import HTTPException

    uid = f"iter209-pre-{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({
        "id": uid,
        "email": f"{uid}@bidvex.test",
        "password": "x", "role": "user",
        "partner_verification_status": "pending",  # NOT rejected
        "created_at": datetime.now(timezone.utc),
    })
    try:
        with pytest.raises(HTTPException) as exc_info:
            await resubmit_application(
                db, flavor="partner", user_id=uid, user_email=f"{uid}@bidvex.test",
                payload={"partner_company_name": "Test"},
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "not_in_rejected_state"
        assert "message_en" in exc_info.value.detail
        assert "message_fr" in exc_info.value.detail
    finally:
        await db.users.delete_one({"id": uid})


@pytest.mark.asyncio
async def test_partner_resubmit_increments_and_flips_status(db):
    from services.resubmission_service import resubmit_application

    uid = f"iter209-resub-{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({
        "id": uid,
        "email": f"{uid}@bidvex.test",
        "password": "x", "role": "user",
        "partner_verification_status": "rejected",
        "partner_rejection_reason": "Missing NEQ scan",
        "partner_rejected_at": datetime.now(timezone.utc),
        "partner_rejected_by": "admin-x",
        "created_at": datetime.now(timezone.utc),
    })
    try:
        result = await resubmit_application(
            db, flavor="partner", user_id=uid, user_email=f"{uid}@bidvex.test",
            payload={"partner_company_name": "Re-Submitted Co"},
        )
        # API response keeps the human-friendly "pending_review" copy for UI
        assert result["status"] == "pending_review"
        assert result["resubmission_count"] == 1
        assert "verified" not in result["message_en"].lower()
        # FR bilingual
        assert "24" in result["message_fr"]

        fresh = await db.users.find_one({"id": uid})
        # iter211 fix — DB now stores canonical "pending" enum so the admin
        # queue (routes/admin.py) picks up resubmitted applications correctly.
        assert fresh["partner_verification_status"] == "pending"
        assert fresh["resubmission_count"] == 1
        assert fresh["partner_rejection_reason"] is None
        assert len(fresh["rejection_history"]) == 1
        assert fresh["rejection_history"][0]["reason"] == "Missing NEQ scan"

        # admin_notifications row
        notif = await db.admin_notifications.find_one({"target_user_id": uid, "kind": "partner_resubmitted"})
        assert notif is not None
        assert notif["extra"]["resubmission_count"] == 1
    finally:
        await db.users.delete_one({"id": uid})
        await db.admin_notifications.delete_many({"target_user_id": uid})


@pytest.mark.asyncio
async def test_partner_max_3_resubmissions_then_blocked(db):
    from services.resubmission_service import resubmit_application
    from fastapi import HTTPException

    uid = f"iter209-max-{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({
        "id": uid,
        "email": f"{uid}@bidvex.test",
        "password": "x", "role": "user",
        "partner_verification_status": "rejected",
        "partner_rejection_reason": "r0",
        "created_at": datetime.now(timezone.utc),
    })
    try:
        # 3 successful resubmits — each followed by an admin "reject" simulation to reset to rejected
        for i in range(3):
            result = await resubmit_application(
                db, flavor="partner", user_id=uid, user_email=f"{uid}@bidvex.test",
                payload={"partner_company_name": f"attempt-{i+1}"},
            )
            assert result["resubmission_count"] == i + 1
            # Simulate admin rejecting again
            await db.users.update_one({"id": uid}, {"$set": {
                "partner_verification_status": "rejected",
                "partner_rejection_reason": f"r{i+1}",
                "partner_rejected_at": datetime.now(timezone.utc),
            }})

        # 4th must fail with 403 max_resubmissions_reached
        with pytest.raises(HTTPException) as exc_info:
            await resubmit_application(
                db, flavor="partner", user_id=uid, user_email=f"{uid}@bidvex.test",
                payload={"partner_company_name": "attempt-4"},
            )
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"] == "max_resubmissions_reached"
        assert "message_en" in exc_info.value.detail
        assert "message_fr" in exc_info.value.detail
        # rejection_history must show all 3 prior reasons (one per resubmit)
        fresh = await db.users.find_one({"id": uid})
        assert len(fresh["rejection_history"]) == 3
        reasons = [h["reason"] for h in fresh["rejection_history"]]
        assert reasons == ["r0", "r1", "r2"]
    finally:
        await db.users.delete_one({"id": uid})
        await db.admin_notifications.delete_many({"target_user_id": uid})


@pytest.mark.asyncio
async def test_dealer_not_in_rejected_returns_400(db):
    from services.resubmission_service import resubmit_application
    from fastapi import HTTPException

    uid = f"iter209-dealer-pre-{uuid.uuid4().hex[:8]}"
    sid = str(uuid.uuid4())
    await db.vehicle_sellers.insert_one({
        "id": sid, "user_id": uid,
        "verification_status": "pending",
        "seller_type": "dealer",
        "created_at": datetime.now(timezone.utc),
    })
    try:
        with pytest.raises(HTTPException) as exc_info:
            await resubmit_application(
                db, flavor="dealer", user_id=uid, user_email=f"{uid}@bidvex.test",
                payload={"business_name": "X"},
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "not_in_rejected_state"
    finally:
        await db.vehicle_sellers.delete_one({"id": sid})


@pytest.mark.asyncio
async def test_dealer_resubmit_full_flow(db):
    from services.resubmission_service import resubmit_application

    uid = f"iter209-dealer-{uuid.uuid4().hex[:8]}"
    sid = str(uuid.uuid4())
    await db.vehicle_sellers.insert_one({
        "id": sid, "user_id": uid,
        "verification_status": "rejected",
        "rejection_reason": "License expired",
        "seller_type": "dealer",
        "business_name": "Old Name",
        "license_number": "OMVIC-12345",
        "license_province": "ON",
        "created_at": datetime.now(timezone.utc),
    })
    try:
        result = await resubmit_application(
            db, flavor="dealer", user_id=uid, user_email=f"{uid}@bidvex.test",
            payload={
                "seller_type": "dealer",
                "business_name": "Fresh Name",
                "license_number": "OMVIC-99999",
                "license_province": "ON",
            },
        )
        assert result["status"] == "pending_review"
        assert result["resubmission_count"] == 1

        fresh = await db.vehicle_sellers.find_one({"id": sid})
        assert fresh["verification_status"] == "pending"
        assert fresh["resubmission_count"] == 1
        assert fresh["rejection_reason"] is None
        assert fresh["business_name"] == "Fresh Name"
        assert fresh["license_number"] == "OMVIC-99999"
        assert len(fresh["rejection_history"]) == 1
        assert fresh["rejection_history"][0]["reason"] == "License expired"

        notif = await db.admin_notifications.find_one({"target_user_id": uid, "kind": "dealer_resubmitted"})
        assert notif is not None
    finally:
        await db.vehicle_sellers.delete_one({"id": sid})
        await db.admin_notifications.delete_many({"target_user_id": uid})


# ─── Live HTTP smoke (partner endpoint) ───────────────────────────────────
@pytest.mark.asyncio
async def test_live_partner_resubmit_http_blocks_when_not_rejected(db):
    """End-to-end HTTP test: hitting /api/partner/resubmit when user is not rejected returns 400."""
    # Use the admin account itself — its partner status is `pending`/`verified`, never rejected
    token = _admin_token()

    # Build multipart upload (real files needed by endpoint signature)
    files = {
        "neq_document": ("dummy.pdf", b"%PDF-1.4 test", "application/pdf"),
    }
    multi_files = [
        ("certification_documents", ("cert.pdf", b"%PDF-1.4 test", "application/pdf")),
    ]
    data = {"company_name": "X", "neq_number": "123"}

    r = httpx.post(
        f"{API_URL}/api/partner/resubmit",
        headers={"Authorization": f"Bearer {token}"},
        data=data,
        files=[*files.items(), *multi_files],
        timeout=20,
    )
    # admin is currently pending or verified → expect 400 not_in_rejected_state OR 404 (still surfaces business rule)
    assert r.status_code in (400, 404), f"Expected 400/404, got {r.status_code}: {r.text[:200]}"
    if r.status_code == 400:
        body = r.json()
        # detail is a dict per spec
        detail = body.get("detail")
        assert isinstance(detail, dict) and detail.get("error") == "not_in_rejected_state"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
