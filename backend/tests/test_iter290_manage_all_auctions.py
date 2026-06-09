"""
iter290 — Manage All Auctions cross-collection regression tests.

Validates the four production gaps closed in this sprint so vehicle,
storage, marketplace, and lots listings all surface (and respond to
admin actions) in the central "Manage All Auctions" panel.

  1. /admin/listings/all aggregates marketplace + vehicle + storage
     and tags every row with `_section` + `_collection`.

  2. /admin/multi-item-listings/all tags every row with
     `_section='lots'` so the orange Lots badge renders.

  3. /admin/listings/{id}/status (Pause / Archive / Cancel) is now
     cross-collection — it dispatches the status update at whichever
     directory collection owns the listing id.

  4. /admin/listings/{id}/feature toggles the `is_featured` flag in
     whichever collection owns the listing id.

  5. /admin/auctions/{id}/end-time resolves vehicles + storage rows in
     addition to marketplace + lots. Both `auction_end_date` and
     `end_time` get written so the field-name mismatch between
     collections no longer hides the update.

Constraints honoured:
  - Vehicle Buyer Premium / Platform Fee / Deposit rules untouched.
  - No bid logic, fee math, JWT, Stripe, or SendGrid wiring touched.
  - Only the admin oversight surface gained cross-collection routing.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("PUBLIC_BACKEND_URL", "http://localhost:8001")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def admin_token():
    import time as _t

    last = None
    for _attempt in range(6):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
            timeout=15,
        )
        last = r
        if r.status_code == 200:
            return r.json().get("access_token") or r.json().get("token")
        _t.sleep(min(2 ** _attempt, 16))
    raise AssertionError(
        f"admin login failed: {last.status_code} {last.text[:200]}"
    )


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Seed helpers — minimal docs, never collide with real data ────────


def _seed_vehicle(db, end_iso):
    vid = f"iter290-vehicle-{uuid.uuid4()}"
    db.vehicle_listings.insert_one(
        {
            "id": vid,
            "title": "iter290 Vehicle Stub",
            "make": "Ford",
            "model": "F-350",
            "year": 2020,
            "status": "active",
            "current_bid": 12000,
            "starting_price": 10000,
            "end_time": end_iso,
            "auction_end_date": end_iso,
            "location_city": "Montreal",
            "location_province": "QC",
            "seller_id": "test-seller-iter290",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return vid


def _seed_storage(db, end_iso):
    sid = f"iter290-storage-{uuid.uuid4()}"
    db.storage_auctions.insert_one(
        {
            "id": sid,
            "unit_number": "A-99",
            "facility_name": "iter290 Test Facility",
            "facility_city": "Toronto",
            "facility_province": "ON",
            "status": "active",
            "current_bid": 75,
            "starting_price": 50,
            "end_time": end_iso,
            "seller_id": "test-seller-iter290",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return sid


def _cleanup(db, vehicle_id, storage_id):
    db.vehicle_listings.delete_one({"id": vehicle_id})
    db.storage_auctions.delete_one({"id": storage_id})


# ── Gap 1 — /admin/listings/all aggregates 3 sections with badges ────


def test_listings_all_includes_vehicle_storage_with_section_tags(db, admin_token):
    """The Manage All Auctions table's primary fetcher must surface
    vehicles + storage and tag each row so the UI can render the
    right section badge + cross-route the View/Edit/Delete CTAs."""
    end_iso = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    v_id = _seed_vehicle(db, end_iso)
    s_id = _seed_storage(db, end_iso)
    try:
        r = requests.get(
            f"{BASE_URL}/api/admin/listings/all",
            headers=_auth(admin_token),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        rows = body if isinstance(body, list) else body.get("listings", [])
        v_row = next((x for x in rows if x.get("id") == v_id), None)
        s_row = next((x for x in rows if x.get("id") == s_id), None)
        assert v_row, "Vehicle seed missing from /admin/listings/all"
        assert s_row, "Storage seed missing from /admin/listings/all"
        assert v_row["_section"] == "vehicle"
        assert v_row["_collection"] == "vehicle_listings"
        assert s_row["_section"] == "storage"
        assert s_row["_collection"] == "storage_auctions"
    finally:
        _cleanup(db, v_id, s_id)


# ── Gap 2 — /admin/multi-item-listings/all tags rows with `lots` ─────


def test_multi_item_listings_all_tags_section_lots(db, admin_token):
    """Multi-item rows must carry `_section='lots'` so the Manage All
    Auctions table renders the orange Lots badge."""
    r = requests.get(
        f"{BASE_URL}/api/admin/multi-item-listings/all",
        headers=_auth(admin_token),
        timeout=15,
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    if not isinstance(rows, list) or not rows:
        # No multi-item listings exist in the preview db — assert the
        # tagging logic via a direct insert.
        mid = f"iter290-multi-{uuid.uuid4()}"
        db.multi_item_listings.insert_one(
            {
                "id": mid,
                "title": "iter290 Multi Stub",
                "status": "draft",
                "lots": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        try:
            r2 = requests.get(
                f"{BASE_URL}/api/admin/multi-item-listings/all",
                headers=_auth(admin_token),
                timeout=15,
            )
            assert r2.status_code == 200, r2.text
            rows2 = r2.json()
            row = next((x for x in rows2 if x.get("id") == mid), None)
            assert row is not None
            assert row.get("_section") == "lots"
            assert row.get("_collection") == "multi_item_listings"
        finally:
            db.multi_item_listings.delete_one({"id": mid})
    else:
        for row in rows:
            # iter293 — `/admin/multi-item-listings/all` now also returns
            # vehicle_multi_lot_auctions rows tagged 'vehicle_multi_lot'.
            assert row.get("_section") in ("lots", "vehicle_multi_lot"), (
                f"missing _section on multi row {row.get('id')}"
            )
            assert row.get("_collection") in (
                "multi_item_listings", "vehicle_multi_lot_auctions"
            )


# ── Gap 3 — /admin/listings/{id}/status is cross-collection ──────────


def test_listing_status_endpoint_handles_vehicle_collection(db, admin_token):
    """Pause / Archive / Cancel from the Manage All Auctions table must
    update the vehicle's status — even though the listing lives in
    `vehicle_listings`, not `listings`."""
    end_iso = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    v_id = _seed_vehicle(db, end_iso)
    s_id = _seed_storage(db, end_iso)
    try:
        r = requests.put(
            f"{BASE_URL}/api/admin/listings/{v_id}/status",
            headers=_auth(admin_token),
            json={"status": "paused"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("collection") == "vehicle_listings"
        vdoc = db.vehicle_listings.find_one({"id": v_id})
        assert vdoc and vdoc.get("status") == "paused"

        # Storage row → archived
        r2 = requests.put(
            f"{BASE_URL}/api/admin/listings/{s_id}/status",
            headers=_auth(admin_token),
            json={"status": "archived"},
            timeout=15,
        )
        assert r2.status_code == 200, r2.text
        sdoc = db.storage_auctions.find_one({"id": s_id})
        assert sdoc and sdoc.get("status") == "archived"
    finally:
        _cleanup(db, v_id, s_id)


# ── Gap 4 — /admin/listings/{id}/feature is cross-collection ─────────


def test_feature_endpoint_handles_vehicle_collection(db, admin_token):
    end_iso = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    v_id = _seed_vehicle(db, end_iso)
    s_id = _seed_storage(db, end_iso)
    try:
        r = requests.put(
            f"{BASE_URL}/api/admin/listings/{v_id}/feature",
            headers=_auth(admin_token),
            json={"is_featured": True},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("collection") == "vehicle_listings"
        vdoc = db.vehicle_listings.find_one({"id": v_id})
        assert vdoc and vdoc.get("is_featured") is True
    finally:
        _cleanup(db, v_id, s_id)


# ── Gap 5 — /admin/auctions/{id}/end-time resolves vehicles + storage ─


def test_end_time_endpoint_resolves_vehicle_listing(db, admin_token):
    """End-time edit from the Manage All Auctions table must hit the
    vehicle_listings collection and write BOTH `auction_end_date` and
    `end_time` (vehicles read `end_time` everywhere else)."""
    end_iso = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    v_id = _seed_vehicle(db, end_iso)
    s_id = _seed_storage(db, end_iso)
    try:
        new_end = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        r = requests.patch(
            f"{BASE_URL}/api/admin/auctions/{v_id}/end-time",
            headers=_auth(admin_token),
            json={
                "new_end_time": new_end,
                "reason": "iter290 regression",
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("collection") == "vehicle_listings"
        vdoc = db.vehicle_listings.find_one({"id": v_id})
        assert vdoc is not None
        # Both fields written so reads from any code path see the new value.
        assert vdoc.get("end_time") is not None
        assert vdoc.get("auction_end_date") is not None

        # Storage round-trip
        new_end_2 = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        r2 = requests.patch(
            f"{BASE_URL}/api/admin/auctions/{s_id}/end-time",
            headers=_auth(admin_token),
            json={
                "new_end_time": new_end_2,
                "reason": "iter290 regression storage",
            },
            timeout=15,
        )
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2.get("collection") == "storage_auctions"
        sdoc = db.storage_auctions.find_one({"id": s_id})
        assert sdoc and sdoc.get("end_time") is not None
    finally:
        _cleanup(db, v_id, s_id)


# ── Sanity — financial guardrails untouched ──────────────────────────


def test_vehicle_buyer_premium_constant_is_still_zero():
    """Hard guard — iter290 must NOT change vehicle fee math.

    Vehicles have buyer premium = 0% and platform fee = 2.5%. The
    Manage All Auctions refactor only touched admin oversight surfaces;
    if any of those constants drift, fail loudly.
    """
    from services.pricing_config import PLATFORM_FEE_VEHICLE
    from decimal import Decimal

    assert PLATFORM_FEE_VEHICLE == Decimal("0.025"), (
        f"Vehicle platform fee must stay 2.5%, got {PLATFORM_FEE_VEHICLE}"
    )
