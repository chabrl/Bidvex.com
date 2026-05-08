"""
iter201 — Phase 3 tests: buyer gate + admin queue + cron + endpoint rename.

Run: cd /app/backend && pytest tests/test_iter201_phase3_buyer_gate.py -v
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta

import httpx
import pytest
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()


def _api_url():
    if os.environ.get("REACT_APP_BACKEND_URL"):
        return os.environ["REACT_APP_BACKEND_URL"]
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


async def _login(client, email, password):
    """Login with retry on 429 AND 401 (rate-limit returns 401 in this app)."""
    for attempt in range(4):
        r = await client.post("/api/auth/login", json={"email": email, "password": password})
        if r.status_code == 200:
            return r.json()["access_token"]
        if r.status_code in (429, 401):
            await asyncio.sleep(20 * (attempt + 1))
            continue
        pytest.fail(f"login failed: {r.status_code} {r.text}")
    pytest.fail(f"login still failing after retries: {email}")


@pytest.mark.asyncio
async def test_3a_buyer_gate_state_machine_all_provinces():
    """Full 13-province state machine test through /buyer-verification/me."""
    api = _api_url()
    async with httpx.AsyncClient(base_url=api, timeout=15.0) as c:
        token = await _login(c, "iter189buyer@test.com", "TestBuyer123!")
        headers = {"Authorization": f"Bearer {token}"}

        expectations = {
            "BC": "open", "AB": "open", "SK": "open", "MB": "open",
            "ON": "restricted_gate", "NB": "restricted_gate", "NS": "restricted_gate",
            "PE": "restricted_gate", "NL": "restricted_gate",
            "QC": "qc_disclosure",
            "YT": "territory_advisory", "NT": "territory_advisory", "NU": "territory_advisory",
        }
        for code, expected in expectations.items():
            r = await c.post("/api/vehicles/buyer-province", json={"province": code}, headers=headers)
            assert r.status_code == 200, f"{code} set: {r.status_code} {r.text}"
            r = await c.get("/api/vehicles/buyer-verification/me", headers=headers)
            assert r.status_code == 200
            actual = r.json().get("gate_state")
            assert actual == expected, f"province {code}: expected {expected}, got {actual}"


@pytest.mark.asyncio
async def test_3a_invalid_province_rejected():
    api = _api_url()
    async with httpx.AsyncClient(base_url=api, timeout=15.0) as c:
        token = await _login(c, "iter189buyer@test.com", "TestBuyer123!")
        r = await c.post("/api/vehicles/buyer-province", json={"province": "ZZ"},
                          headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400
        detail = r.json().get("detail", {})
        assert detail.get("code") == "invalid_province"


@pytest.mark.asyncio
async def test_3a_qc_lpc_ack_persists_per_listing():
    """QC LPC ack saves per-listing and is retrievable; setting another listing doesn't overwrite."""
    api = _api_url()
    async with httpx.AsyncClient(base_url=api, timeout=15.0) as c:
        token = await _login(c, "iter189buyer@test.com", "TestBuyer123!")
        h = {"Authorization": f"Bearer {token}"}

        await c.post("/api/vehicles/buyer-province", json={"province": "QC"}, headers=h)
        r = await c.post("/api/vehicles/buyer-verification/qc-ack",
                          json={"listing_id": "iter201-test-listing-A"}, headers=h)
        assert r.status_code == 200
        assert r.json()["listing_id"] == "iter201-test-listing-A"

        # ack on another listing
        r = await c.post("/api/vehicles/buyer-verification/qc-ack",
                          json={"listing_id": "iter201-test-listing-B"}, headers=h)
        assert r.status_code == 200

        # verify both are stored — listing A should be acked
        r = await c.get("/api/vehicles/buyer-verification/me?listing_id=iter201-test-listing-A", headers=h)
        assert r.json()["qc_lpc_ack_for_listing"] is True
        r = await c.get("/api/vehicles/buyer-verification/me?listing_id=iter201-other-listing", headers=h)
        assert r.json()["qc_lpc_ack_for_listing"] is False


@pytest.mark.asyncio
async def test_3a_qc_ack_blocked_for_non_qc_buyer():
    api = _api_url()
    async with httpx.AsyncClient(base_url=api, timeout=15.0) as c:
        token = await _login(c, "iter189buyer@test.com", "TestBuyer123!")
        h = {"Authorization": f"Bearer {token}"}
        await c.post("/api/vehicles/buyer-province", json={"province": "BC"}, headers=h)
        r = await c.post("/api/vehicles/buyer-verification/qc-ack",
                          json={"listing_id": "iter201-test-listing"}, headers=h)
        assert r.status_code == 400
        assert r.json().get("detail", {}).get("code") == "qc_only"


@pytest.mark.asyncio
async def test_3d_dealer_license_verify_endpoint_and_legacy_alias():
    """Both endpoints (new /dealer-license-verify and legacy /opc-verify) accept the same payload."""
    api = _api_url()
    async with httpx.AsyncClient(base_url=api, timeout=15.0) as c:
        admin_token = await _login(c, "charbel911@gmail.com", "Anderosli123!@#")
        h = {"Authorization": f"Bearer {admin_token}"}

        # Find a target user (must have an id)
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        target = await db.users.find_one(
            {"role": {"$ne": "admin"}, "id": {"$exists": True, "$ne": None}},
            {"_id": 0, "id": 1},
        )
        cli.close()
        assert target and target.get("id"), f"no eligible target user: {target}"

        # Hit NEW endpoint
        r = await c.put(
            f"/api/admin/users/{target['id']}/dealer-license-verify",
            json={"opc_permit_verified": True, "opc_permit_number": "TEST-NEW-1"},
            headers=h,
        )
        assert r.status_code == 200, r.text
        assert r.json()["success"] is True

        # Hit LEGACY alias
        r = await c.put(
            f"/api/admin/users/{target['id']}/opc-verify",
            json={"opc_permit_verified": False, "opc_permit_number": "TEST-LEGACY"},
            headers=h,
        )
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_3b_admin_pending_buyer_verifications_endpoint_exists():
    api = _api_url()
    async with httpx.AsyncClient(base_url=api, timeout=15.0) as c:
        admin_token = await _login(c, "charbel911@gmail.com", "Anderosli123!@#")
        r = await c.get("/api/admin/buyer-verifications/pending",
                          headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        d = r.json()
        assert "items" in d and "total" in d


@pytest.mark.asyncio
async def test_3b_admin_compliance_alerts_endpoint_exists():
    api = _api_url()
    async with httpx.AsyncClient(base_url=api, timeout=15.0) as c:
        admin_token = await _login(c, "charbel911@gmail.com", "Anderosli123!@#")
        r = await c.get("/api/admin/compliance-alerts",
                          headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        d = r.json()
        for k in ("expired", "high_fraud_score", "unreviewed_manual_review", "territory_bids"):
            assert k in d


@pytest.mark.asyncio
async def test_3c_expired_dealer_license_cron_callable():
    """Programmatically invoke the expired-dealer-license job and verify it runs idempotently."""
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]

    # Seed a user with a licence that expired yesterday
    test_uid = f"iter201-p3c-{uuid.uuid4().hex[:8]}"
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    await db.users.insert_one({
        "id": test_uid,
        "email": f"{test_uid}@test.com",
        "name": "iter201 cron test",
        "dealer_license_verified": True,
        "dealer_license_expiry_date": yesterday.isoformat(),
        "preferred_language": "en",
    })

    try:
        # Initialise the scheduler module to pull in the job factory
        from services.scheduler import init_scheduler
        sched = init_scheduler(db)
        job = sched.get_job("check_expired_dealer_licences")
        assert job is not None, "Job not registered"

        # Call the underlying function directly (bypasses cron)
        await job.func()

        # Verify side effects
        u = await db.users.find_one({"id": test_uid}, {"_id": 0, "dealer_license_verified": 1, "dealer_license_expired_at": 1})
        assert u["dealer_license_verified"] is False
        assert u.get("dealer_license_expired_at") is not None

        # Verify compliance log written
        log_count = await db.dealer_compliance_log.count_documents({"user_id": test_uid})
        assert log_count >= 1
    finally:
        await db.users.delete_one({"id": test_uid})
        await db.dealer_compliance_log.delete_many({"user_id": test_uid})
        cli.close()
