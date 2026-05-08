"""
iter201 — Phase 3 / 3E — Verification Checklist Runner.

Automated re-check of every box from the CEO's verification checklist.

Run:
    cd /app/backend && python -m pytest tests/test_iter201_phase3_checklist.py -v
or:
    cd /app/backend && python scripts/verify_phase3_checklist.py

Idempotent — safe to re-run. Uses no destructive writes (only reads + ephemeral
state checks). Logs PASS/FAIL with explanations.
"""
import asyncio
import os
import re
from pathlib import Path

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


# ────────── CHECK: data-model integrity ──────────

@pytest.mark.asyncio
async def test_checklist_all_13_provinces_present():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    total = await db.province_regulations.count_documents({})
    assert total == 13, f"Expected 13 provinces/territories, got {total}"
    cli.close()


@pytest.mark.asyncio
async def test_checklist_open_provinces_no_gate():
    """BC/AB/SK/MB → individual buyers allowed, no gate."""
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    for code in ("BC", "AB", "SK", "MB"):
        d = await db.province_regulations.find_one({"province_code": code}, {"_id": 0, "individual_buyers_allowed": 1})
        assert d and d["individual_buyers_allowed"] is True, f"{code} should allow individual buyers"
    cli.close()


@pytest.mark.asyncio
async def test_checklist_restricted_provinces_block():
    """ON/NB/NS/PE/NL → individuals blocked unless dealer-verified."""
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    for code in ("ON", "NB", "NS", "PE", "NL"):
        d = await db.province_regulations.find_one({"province_code": code}, {"_id": 0, "individual_buyers_allowed": 1})
        assert d and d["individual_buyers_allowed"] is False, f"{code} should restrict individual buyers"
    cli.close()


@pytest.mark.asyncio
async def test_checklist_qc_disclosure_ack_required():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    qc = await db.province_regulations.find_one({"province_code": "QC"}, {"_id": 0})
    assert qc["individual_buyers_allowed"] is True
    assert qc.get("individual_buyers_require_disclosure_ack") is True
    cli.close()


# ────────── CHECK: zero "OPC" user-facing strings ──────────

@pytest.mark.asyncio
async def test_checklist_no_user_facing_opc_strings():
    """Re-runs the same scrub assertion as Phase 1 to guarantee Phase 3 didn't
    re-introduce any user-facing OPC mentions."""
    forbidden_paths = [
        Path("/app/backend/routes/listings.py"),
        Path("/app/backend/services/ai_assistant_v2.py"),
        Path("/app/backend/services/scheduler.py"),
        Path("/app/backend/sendgrid_templates/generate_templates.py"),
        Path("/app/frontend/src/pages/HowItWorks.js"),
        Path("/app/frontend/src/pages/HowItWorksPage.js"),
        Path("/app/frontend/src/pages/TermsOfServicePage.js"),
        Path("/app/frontend/src/pages/seller/VehicleSettlements.js"),
        Path("/app/frontend/src/pages/admin/VehicleAdminManager.js"),
        Path("/app/frontend/src/pages/vehicles/VehicleDetailPage.js"),
        Path("/app/frontend/src/components/vehicles/VehicleCategoryGrid.js"),
        Path("/app/frontend/src/components/vehicles/VehicleBuyerGateModal.js"),
        Path("/app/frontend/src/components/vehicles/VehicleLegalFooter.js"),
        Path("/app/frontend/src/components/vehicles/ProvinceSellerNotice.js"),
        Path("/app/frontend/src/pages/admin/AdminBuyerVerifications.js"),
        Path("/app/frontend/src/pages/admin/AdminComplianceAlerts.js"),
    ]
    pattern = re.compile(r"\bOPC\b")
    legacy = re.compile(r"LEGACY:|legacy opc_permit|read-only since iter201|Renamed from \"OPC|iter201")
    offenses = []
    for p in forbidden_paths:
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line) and not legacy.search(line):
                offenses.append(f"{p.name}:{i}: {line.strip()[:120]}")
    assert not offenses, "User-facing OPC mentions found:\n" + "\n".join(offenses)


# ────────── CHECK: endpoint rename + legacy alias ──────────

@pytest.mark.asyncio
async def test_checklist_dealer_license_verify_endpoint_responds():
    api = _api_url()
    async with httpx.AsyncClient(base_url=api, timeout=15.0) as c:
        # Unauth → 401/403
        r = await c.put("/api/admin/users/anyone/dealer-license-verify", json={"opc_permit_verified": True})
        assert r.status_code in (401, 403, 422), f"unexpected status {r.status_code}"


@pytest.mark.asyncio
async def test_checklist_legacy_opc_verify_alias_responds():
    api = _api_url()
    async with httpx.AsyncClient(base_url=api, timeout=15.0) as c:
        r = await c.put("/api/admin/users/anyone/opc-verify", json={"opc_permit_verified": True})
        assert r.status_code in (401, 403, 422), f"legacy alias should accept calls; got {r.status_code}"


# ────────── CHECK: scheduler job registered ──────────

@pytest.mark.asyncio
async def test_checklist_expired_dealer_license_job_registered():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    from services.scheduler import init_scheduler
    sched = init_scheduler(db)
    assert sched.get_job("check_expired_dealer_licences") is not None
    cli.close()


# ────────── CHECK: parts_accessories exempt from gate ──────────

@pytest.mark.asyncio
async def test_checklist_parts_accessories_open_to_individuals():
    from services.vehicle_categories import (
        category_requires_dealer_license,
        get_category,
    )
    assert category_requires_dealer_license("parts_accessories") is False
    parts = get_category("parts_accessories")
    assert parts is not None
    assert parts["requires_dealer_license"] is False


# ────────── CHECK: admin compliance alerts endpoint exists ──────────

@pytest.mark.asyncio
async def test_checklist_compliance_alerts_count_endpoint_exists():
    api = _api_url()
    async with httpx.AsyncClient(base_url=api, timeout=15.0) as c:
        # Unauth → 401/403 (route exists, just gated)
        r = await c.get("/api/admin/compliance-alerts/count")
        assert r.status_code in (401, 403), f"got {r.status_code}"


if __name__ == "__main__":
    import subprocess
    print("Running iter201 Phase 3 verification checklist…\n")
    rc = subprocess.call(["python", "-m", "pytest", __file__, "-v"])
    raise SystemExit(rc)
