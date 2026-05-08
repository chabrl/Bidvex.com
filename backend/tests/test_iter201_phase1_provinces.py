"""
iter201 — Phase 1 tests for province_regulations + dealer_license_* migration.

Run: cd /app/backend && pytest tests/test_iter201_phase1_provinces.py -v
"""
import asyncio
import os
import uuid

import pytest
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()


@pytest.mark.asyncio
async def test_seed_idempotency_and_completeness():
    """Re-running the seeder must not produce duplicates or modifications."""
    from migrations.seed_province_regulations import seed_provinces, PROVINCES
    res = await seed_provinces(verbose=False)
    assert res["total"] == 13, f"expected 13 jurisdictions, got {res['total']}"
    assert len(res["modified"]) == 0, f"unexpected diffs on re-run: {res['modified']}"
    assert len(res["upserted"]) == 0, f"unexpected upserts on re-run: {res['upserted']}"
    assert len(PROVINCES) == 13


@pytest.mark.asyncio
async def test_quebec_has_disclosure_ack_flag():
    """CEO Q1=(c) — QC must allow individual buyers BUT require LPC disclosure acknowledgement."""
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    qc = await db.province_regulations.find_one({"province_code": "QC"}, {"_id": 0})
    assert qc is not None
    assert qc.get("individual_buyers_allowed") is True
    assert qc.get("individual_buyers_require_disclosure_ack") is True
    assert qc.get("requires_bilingual_listings") is True
    assert qc.get("primary_listing_language") == "fr"
    assert qc.get("tax_rates", {}).get("PST_QST") == pytest.approx(0.09975)
    cli.close()


@pytest.mark.asyncio
async def test_restricted_provinces_block_individuals():
    """Restricted provinces (ON / NB / NS / PE / NL) hard-block individual buyers."""
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    for code in ("ON", "NB", "NS", "PE", "NL"):
        doc = await db.province_regulations.find_one({"province_code": code}, {"_id": 0})
        assert doc is not None, code
        assert doc.get("individual_buyers_allowed") is False, f"{code} must restrict individuals"
    cli.close()


@pytest.mark.asyncio
async def test_open_provinces_allow_individuals():
    """Open provinces (BC / AB / SK / MB) allow individual buyers without a gate."""
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    for code in ("BC", "AB", "SK", "MB"):
        doc = await db.province_regulations.find_one({"province_code": code}, {"_id": 0})
        assert doc is not None, code
        assert doc.get("individual_buyers_allowed") is True, f"{code} must allow individuals"
    cli.close()


@pytest.mark.asyncio
async def test_territories_flagged_for_admin_review():
    """Territories (YT/NT/NU) must require admin review."""
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    for code in ("YT", "NT", "NU"):
        doc = await db.province_regulations.find_one({"province_code": code}, {"_id": 0})
        assert doc is not None, code
        assert doc.get("requires_admin_review") is True
    cli.close()


@pytest.mark.asyncio
async def test_legacy_opc_field_silent_migration():
    """A user with only legacy `opc_permit_*` must end up with the new `dealer_license_*`
    fields backfilled after migration runs."""
    from migrations.migrate_dealer_license_fields import migrate

    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    test_id = f"iter201-test-{uuid.uuid4().hex[:8]}"

    # Seed a legacy-only user
    await db.users.insert_one({
        "id": test_id,
        "email": f"{test_id}@test.com",
        "opc_permit_number": "LEGACY-ABC-123",
        "opc_permit_verified": True,
    })

    try:
        await migrate(verbose=False)
        u = await db.users.find_one({"id": test_id}, {"_id": 0})
        # Legacy fields preserved
        assert u.get("opc_permit_number") == "LEGACY-ABC-123"
        assert u.get("opc_permit_verified") is True
        # New fields backfilled
        assert u.get("dealer_license_number") == "LEGACY-ABC-123"
        assert u.get("dealer_license_verified") is True
        # New fields present (initialized)
        assert "dealer_license_province" in u
        assert "dealer_license_type" in u
        assert "neq" in u
        assert "vehicle_buyer_verification" in u
    finally:
        await db.users.delete_one({"id": test_id})
        cli.close()


@pytest.mark.asyncio
async def test_no_user_facing_opc_strings_in_vehicle_scope():
    """Phase 1 scrub — the literal token 'OPC' must not appear in user-facing strings
    in the vehicle scope (excluding LEGACY comments and out-of-scope storage/pricing)."""
    import re
    import pathlib
    root = pathlib.Path("/app")
    forbidden_paths = (
        root / "backend/routes/listings.py",
        root / "backend/services/ai_assistant_v2.py",
        root / "backend/services/scheduler.py",
        root / "backend/sendgrid_templates/generate_templates.py",
        root / "frontend/src/pages/HowItWorks.js",
        root / "frontend/src/pages/HowItWorksPage.js",
        root / "frontend/src/pages/TermsOfServicePage.js",
        root / "frontend/src/pages/seller/VehicleSettlements.js",
        root / "frontend/src/pages/admin/VehicleAdminManager.js",
        root / "frontend/src/pages/vehicles/VehicleDetailPage.js",
    )
    pattern = re.compile(r"\bOPC\b")
    legacy_marker = re.compile(r"LEGACY:|legacy opc_permit|read-only since iter201|Renamed from \"OPC|iter201")
    offenses = []
    for p in forbidden_paths:
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line) and not legacy_marker.search(line):
                offenses.append(f"{p.name}:{i}: {line.strip()[:120]}")
    assert not offenses, "User-facing OPC mentions found:\n" + "\n".join(offenses)
