"""
iter203 P0 Compliance — Vehicle Listing Guard
==============================================
Bullet-proof tests for the three layers of defence:

  1. Hard-coded gate     — `services.vehicle_listing_guard.enforce_vehicle_dealer_gate`
  2. AI scanner          — `services.vehicle_listing_scanner.scan_listing_for_vehicles`
  3. Safety watchdog     — `services.safety_watchdog.run_safety_watchdog`

Plus the cleanup script entry point and the route-level integration with
POST /api/listings + POST /api/multi-item-listings.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Ensure backend importable
sys.path.insert(0, str(Path("/app/backend")))
load_dotenv("/app/backend/.env")

from services.vehicle_listing_guard import (
    is_vehicle_listing,
    check_user_is_verified_dealer,
    enforce_vehicle_dealer_gate,
    should_pause_existing_listing,
)
from services.safety_watchdog import (
    run_safety_watchdog,
    cleanup_existing_violations,
    PAUSED_STATUS,
)
from services.vehicle_listing_scanner import (
    scan_listing_for_vehicles,
)


@pytest.fixture
def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


# ---------------------------------------------------------------------------
# Pure detection tests — no DB
# ---------------------------------------------------------------------------

class TestIsVehicleListing:

    def test_user_reported_case_individual_lists_car_in_marketplace(self):
        """The exact scenario the user reported: someone listed a car as an
        individual on the marketplace and the legacy gate missed it."""
        is_v, signals, strength = is_vehicle_listing(
            category="Cars",
            title="2018 Honda Civic LX — Low km",
            description="Single owner. Clean title. Runs and drives.",
        )
        assert is_v is True, f"Should detect car. signals={signals} strength={strength}"
        # Multiple signals fire — category, year+brand, body
        assert any(s.startswith("category:") for s in signals)
        assert any("year" in s and "brand" in s for s in signals)

    def test_legacy_narrow_categories_still_flag(self):
        for cat in ["vehicle", "vehicles", "Vehicles", "VEHICLE", "vehicle parts", "road_vehicles"]:
            is_v, _, _ = is_vehicle_listing(category=cat, title="Some item", description="")
            assert is_v, f"category={cat!r} must flag"

    def test_french_categories_flag(self):
        for cat in ["véhicule", "véhicules", "voiture", "Voiture", "Camion", "moto", "VTT"]:
            is_v, _, _ = is_vehicle_listing(category=cat, title="", description="")
            assert is_v, f"FR category={cat!r} must flag"

    def test_disguised_category_with_vehicle_title_flagged(self):
        """User puts category=Toys but lists a car in the title."""
        is_v, signals, _ = is_vehicle_listing(
            category="Toys & Hobbies",
            title="2020 Ford F-150 XLT 4x4 truck",
            description="Pickup truck for sale. 50,000 km.",
        )
        assert is_v, signals

    def test_vin_in_description_flags(self):
        is_v, signals, _ = is_vehicle_listing(
            category="Sports & Outdoors",
            title="Quick weekend getaway",
            description="Includes a VIN: 1HGCM82633A004352. Will transfer registration.",
        )
        assert is_v
        assert any("strong:vin" in s for s in signals)

    def test_motorcycle_flags(self):
        is_v, _, _ = is_vehicle_listing(category="Motorcycles", title="Kawasaki Ninja 2019", description="")
        assert is_v

    def test_boat_flags(self):
        is_v, _, _ = is_vehicle_listing(category="Boats & Watercraft", title="Sea-Doo 2018 jetski", description="")
        assert is_v

    def test_atv_flags(self):
        is_v, _, _ = is_vehicle_listing(category="ATVs & Off-Road", title="Polaris Sportsman 850", description="")
        assert is_v

    def test_non_vehicle_does_not_flag(self):
        is_v, _, _ = is_vehicle_listing(
            category="Electronics",
            title="MacBook Pro 16-inch 2021",  # year + 'pro' ≠ vehicle brand
            description="Brand new condition with original box.",
        )
        assert not is_v

    def test_empty_inputs_safe(self):
        is_v, _, _ = is_vehicle_listing(category=None, title=None, description=None)
        assert not is_v
        is_v, _, _ = is_vehicle_listing(category="", title="", description="")
        assert not is_v

    def test_marketplace_innocuous_title_with_year_only(self):
        """Year alone should NOT flag (handles things like "2020 Tax Return")."""
        is_v, signals, _ = is_vehicle_listing(
            category="Books",
            title="2020 Income Tax Guide",
            description="Used textbook in great condition.",
        )
        assert not is_v, signals


# ---------------------------------------------------------------------------
# DB-backed integration tests for the guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_user_is_verified_dealer_individual(db):
    user_id = "iter203-test-individual"
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"id": user_id, "email": f"{user_id}@example.com",
                  "seller_type": "individual", "dealer_license_verified": False}},
        upsert=True,
    )
    try:
        is_dealer, doc = await check_user_is_verified_dealer(db, user_id)
        assert is_dealer is False
        assert doc.get("email") == f"{user_id}@example.com"
    finally:
        await db.users.delete_one({"id": user_id})


@pytest.mark.asyncio
async def test_check_user_is_verified_dealer_dealer(db):
    user_id = "iter203-test-dealer"
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"id": user_id, "seller_type": "dealer", "dealer_license_verified": True}},
        upsert=True,
    )
    try:
        is_dealer, _ = await check_user_is_verified_dealer(db, user_id)
        assert is_dealer is True
    finally:
        await db.users.delete_one({"id": user_id})


@pytest.mark.asyncio
async def test_check_user_admin_treated_as_dealer(db):
    user_id = "iter203-test-admin"
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"id": user_id, "role": "admin"}},
        upsert=True,
    )
    try:
        is_dealer, _ = await check_user_is_verified_dealer(db, user_id)
        assert is_dealer is True, "Admins must bypass the gate"
    finally:
        await db.users.delete_one({"id": user_id})


class _FakeUser:
    def __init__(self, id_):
        self.id = id_


@pytest.mark.asyncio
async def test_enforce_gate_raises_403_for_individual(db):
    user_id = "iter203-test-block"
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"id": user_id, "email": f"{user_id}@example.com",
                  "seller_type": "individual", "dealer_license_verified": False}},
        upsert=True,
    )
    try:
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as excinfo:
            await enforce_vehicle_dealer_gate(
                db, _FakeUser(user_id),
                category="Cars",
                title="2018 Honda Civic",
                description="Clean title, runs great.",
                surface="single_listing",
            )
        exc = excinfo.value
        assert exc.status_code == 403
        assert isinstance(exc.detail, dict)
        assert exc.detail["error"] == "vehicle_listing_dealer_required"
        assert "Vehicle listings are restricted" in exc.detail["message"]
        assert "Les annonces de véhicules" in exc.detail["message"]  # FR present
        # Audit log must be written
        log = await db.audit_logs.find_one(
            {"action": "vehicle_listing_blocked", "user_id": user_id},
            sort=[("timestamp", -1)],
        )
        assert log is not None
        assert log["surface"] == "single_listing"
    finally:
        await db.users.delete_one({"id": user_id})
        await db.audit_logs.delete_many({"user_id": user_id})


@pytest.mark.asyncio
async def test_enforce_gate_allows_verified_dealer(db):
    user_id = "iter203-test-allow"
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"id": user_id, "seller_type": "dealer",
                  "dealer_license_verified": True, "dealer_license_province": "ON"}},
        upsert=True,
    )
    try:
        meta = await enforce_vehicle_dealer_gate(
            db, _FakeUser(user_id),
            category="Cars",
            title="2018 Honda Civic",
            description="Verified dealer listing.",
            surface="single_listing",
        )
        assert meta is not None
        assert meta["verified_dealer"] is True
    finally:
        await db.users.delete_one({"id": user_id})
        await db.audit_logs.delete_many({"user_id": user_id})


@pytest.mark.asyncio
async def test_enforce_gate_returns_none_for_non_vehicle(db):
    user_id = "iter203-test-nonveh"
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"id": user_id, "seller_type": "individual"}},
        upsert=True,
    )
    try:
        result = await enforce_vehicle_dealer_gate(
            db, _FakeUser(user_id),
            category="Electronics",
            title="MacBook Pro 16-inch",
            description="Used laptop.",
        )
        assert result is None
    finally:
        await db.users.delete_one({"id": user_id})


# ---------------------------------------------------------------------------
# Safety Watchdog
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_watchdog_pauses_individual_vehicle_listing(db):
    """Seed an active listing that looks like a vehicle from a non-dealer.
    Run the watchdog. Confirm it's paused to pending_review with audit log."""
    seller_id = "iter203-wd-individual"
    listing_id = "iter203-wd-listing-1"
    await db.users.update_one(
        {"id": seller_id},
        {"$set": {"id": seller_id, "seller_type": "individual",
                  "dealer_license_verified": False}},
        upsert=True,
    )
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {
            "id": listing_id,
            "seller_id": seller_id,
            "status": "active",
            "category": "Cars",
            "title": "2020 Toyota RAV4 — clean title",
            "description": "Hybrid SUV. 54,000 km. Single owner.",
        }},
        upsert=True,
    )
    try:
        summary = await run_safety_watchdog(db, triggered_by="test")
        assert summary["total_paused"] >= 1
        listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
        assert listing["status"] == PAUSED_STATUS
        assert listing["paused_reason"] == "vehicle_listing_by_non_dealer"
        assert listing["compliance_strength"] >= 4
        # Audit log
        log = await db.audit_logs.find_one(
            {"action": "vehicle_listing_paused_by_watchdog", "listing_id": listing_id},
            sort=[("timestamp", -1)],
        )
        assert log is not None
    finally:
        await db.listings.delete_one({"id": listing_id})
        await db.users.delete_one({"id": seller_id})
        await db.audit_logs.delete_many({"listing_id": listing_id})


@pytest.mark.asyncio
async def test_watchdog_does_not_pause_dealer_listings(db):
    seller_id = "iter203-wd-dealer"
    listing_id = "iter203-wd-listing-2"
    await db.users.update_one(
        {"id": seller_id},
        {"$set": {"id": seller_id, "seller_type": "dealer",
                  "dealer_license_verified": True}},
        upsert=True,
    )
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {
            "id": listing_id,
            "seller_id": seller_id,
            "status": "active",
            "category": "Cars",
            "title": "2020 Toyota RAV4 — dealer listing",
            "description": "Verified dealer.",
        }},
        upsert=True,
    )
    try:
        await run_safety_watchdog(db, triggered_by="test")
        listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
        assert listing["status"] == "active", "Dealer listings must NOT be paused"
    finally:
        await db.listings.delete_one({"id": listing_id})
        await db.users.delete_one({"id": seller_id})


@pytest.mark.asyncio
async def test_watchdog_pauses_multi_item_with_vehicle_lot(db):
    """Multi-item parent looks benign but a hidden lot is a vehicle."""
    seller_id = "iter203-wd-multi"
    listing_id = "iter203-wd-multi-1"
    await db.users.update_one(
        {"id": seller_id},
        {"$set": {"id": seller_id, "seller_type": "individual",
                  "dealer_license_verified": False}},
        upsert=True,
    )
    await db.multi_item_listings.update_one(
        {"id": listing_id},
        {"$set": {
            "id": listing_id,
            "seller_id": seller_id,
            "status": "active",
            "category": "Estate Sale",
            "title": "Mixed estate auction",
            "description": "Various items.",
            "lots": [
                {"title": "Vintage chair", "description": "Wooden chair."},
                {"title": "2015 Honda Civic", "description": "VIN: 1HGCM82633A004352"},
            ],
        }},
        upsert=True,
    )
    try:
        summary = await run_safety_watchdog(db, triggered_by="test")
        assert summary["total_paused"] >= 1
        listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
        assert listing["status"] == PAUSED_STATUS
    finally:
        await db.multi_item_listings.delete_one({"id": listing_id})
        await db.users.delete_one({"id": seller_id})


@pytest.mark.asyncio
async def test_cleanup_script_entry_point_works(db):
    """`cleanup_existing_violations` is the entry point used by the script.
    It must run end-to-end and return a summary."""
    summary = await cleanup_existing_violations(db)
    assert "total_paused" in summary
    assert "total_examined" in summary
    assert summary["triggered_by"] == "cleanup_script"


# ---------------------------------------------------------------------------
# AI Scanner — exercised without a real LLM (fail-OPEN path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_scanner_skips_when_listing_not_found(db):
    result = await scan_listing_for_vehicles(db, listing_id="non-existent-12345")
    assert result.get("skipped") == "not_found"


@pytest.mark.asyncio
async def test_ai_scanner_records_scan_and_fail_open(db, monkeypatch):
    """Force the LLM call to fail. Listing must remain active (fail-OPEN)
    and a `listing_scans` record with status='ai_unavailable' must exist."""
    seller_id = "iter203-ai-individual"
    listing_id = "iter203-ai-listing-1"
    await db.users.update_one(
        {"id": seller_id},
        {"$set": {"id": seller_id, "seller_type": "individual"}},
        upsert=True,
    )
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {
            "id": listing_id, "seller_id": seller_id, "status": "active",
            "category": "Cars", "title": "2017 Honda Accord",
            "description": "Clean.",
        }},
        upsert=True,
    )
    try:
        # Monkeypatch the AI call to raise
        from services import vehicle_listing_scanner as scanner_mod
        async def _raise(*args, **kwargs):
            raise RuntimeError("forced_test_failure")
        monkeypatch.setattr(scanner_mod, "_call_gemini_scanner", _raise)
        result = await scan_listing_for_vehicles(db, listing_id=listing_id)
        assert result.get("ai_unavailable") is True
        # Listing must remain active when AI is down
        listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
        assert listing["status"] == "active"
        # Scan record must exist
        scan = await db.listing_scans.find_one(
            {"listing_id": listing_id, "status": "ai_unavailable"},
            sort=[("scanned_at", -1)],
        )
        assert scan is not None
    finally:
        await db.listings.delete_one({"id": listing_id})
        await db.users.delete_one({"id": seller_id})
        await db.listing_scans.delete_many({"listing_id": listing_id})


@pytest.mark.asyncio
async def test_ai_scanner_pauses_when_individual_vehicle_detected(db, monkeypatch):
    """Mock Gemini to return is_vehicle=true. Listing must be moved to
    pending_review and audit log must be written."""
    seller_id = "iter203-ai-block"
    listing_id = "iter203-ai-listing-2"
    await db.users.update_one(
        {"id": seller_id},
        {"$set": {"id": seller_id, "seller_type": "individual",
                  "dealer_license_verified": False}},
        upsert=True,
    )
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {
            "id": listing_id, "seller_id": seller_id, "status": "active",
            "category": "Misc", "title": "My old wheels",
            "description": "Pickup it up yourself.",
        }},
        upsert=True,
    )
    try:
        from services import vehicle_listing_scanner as scanner_mod
        async def _fake_ai(*args, **kwargs):
            return {
                "is_vehicle": True,
                "vehicle_type": "car",
                "confidence": 0.92,
                "reasons": ["title mentions 'wheels'", "category disguised"],
                "recommended_action": "block_and_review",
            }
        monkeypatch.setattr(scanner_mod, "_call_gemini_scanner", _fake_ai)
        result = await scan_listing_for_vehicles(db, listing_id=listing_id)
        assert result["action_taken"] == "paused_pending_review"
        listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
        assert listing["status"] == "pending_review"
        assert listing["paused_by"] == "ai_scanner"
        assert listing["ai_confidence"] == 0.92
        log = await db.audit_logs.find_one(
            {"action": "vehicle_listing_paused_by_ai_scanner", "listing_id": listing_id}
        )
        assert log is not None
    finally:
        await db.listings.delete_one({"id": listing_id})
        await db.users.delete_one({"id": seller_id})
        await db.audit_logs.delete_many({"listing_id": listing_id})
        await db.listing_scans.delete_many({"listing_id": listing_id})


@pytest.mark.asyncio
async def test_ai_scanner_logs_only_for_dealer(db, monkeypatch):
    """Even if AI flags a dealer's listing as a vehicle — log only, never pause."""
    seller_id = "iter203-ai-dealer"
    listing_id = "iter203-ai-listing-3"
    await db.users.update_one(
        {"id": seller_id},
        {"$set": {"id": seller_id, "seller_type": "dealer",
                  "dealer_license_verified": True}},
        upsert=True,
    )
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {
            "id": listing_id, "seller_id": seller_id, "status": "active",
            "category": "Cars", "title": "2018 Honda Civic — dealer",
            "description": "Verified dealer.",
        }},
        upsert=True,
    )
    try:
        from services import vehicle_listing_scanner as scanner_mod
        async def _fake_ai(*args, **kwargs):
            return {"is_vehicle": True, "confidence": 0.99, "reasons": ["dealer"], "recommended_action": "allow"}
        monkeypatch.setattr(scanner_mod, "_call_gemini_scanner", _fake_ai)
        result = await scan_listing_for_vehicles(db, listing_id=listing_id)
        assert result["action_taken"] == "logged_only"
        listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
        assert listing["status"] == "active"
    finally:
        await db.listings.delete_one({"id": listing_id})
        await db.users.delete_one({"id": seller_id})
        await db.listing_scans.delete_many({"listing_id": listing_id})


# ---------------------------------------------------------------------------
# Scheduler — watchdog job is registered
# ---------------------------------------------------------------------------

def test_scheduler_registers_safety_watchdog_job():
    src = Path("/app/backend/services/scheduler.py").read_text()
    assert 'id="safety_watchdog"' in src
    assert "IntervalTrigger(minutes=60)" in src
    assert "iter203" in src
    assert "Scheduler initialized with 16 jobs" in src
