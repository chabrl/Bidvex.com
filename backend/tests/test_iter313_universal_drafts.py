"""
iter313 — Universal Save-as-Draft round-trip regression tests.

ONE test per listing type. Each test must independently confirm:
  1. POST /api/drafts/save with partial half-typed payload returns 200 + draft_id
  2. The draft is persisted to seller_drafts collection
  3. GET /api/drafts/{id} hydrates with the EXACT payload that was saved
  4. The draft appears in GET /api/drafts (the dashboard list)
  5. POST /api/drafts/save with the same draft_id updates in place (no duplicate row)
  6. DELETE /api/drafts/{id} removes it

A pass on one type does NOT count as evidence for any other type — that
was the spec from the iter313 directive. Each of the 5 types has its
own dedicated test.
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest
import requests

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")

from pymongo import MongoClient  # noqa: E402


with open("/app/frontend/.env") as f:
    BASE_URL = next(
        (line.split("=", 1)[1].strip() for line in f if line.startswith("REACT_APP_BACKEND_URL")),
        None,
    )

SELLER = ("testseller@bidvex.com", "TestSeller2026!")


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


@pytest.fixture(scope="module")
def seller_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": SELLER[0], "password": SELLER[1]},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"seller login failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


def _roundtrip(draft_type: str, payload: dict, seller_token, db, marker: str):
    """Shared round-trip: save -> get -> list -> update -> delete."""
    # 1. Save with partial payload
    r1 = requests.post(
        f"{BASE_URL}/api/drafts/save",
        json={"type": draft_type, "payload": payload},
        headers=_hdr(seller_token),
        timeout=15,
    )
    assert r1.status_code == 200, f"[{draft_type}] save failed: {r1.status_code} {r1.text}"
    body = r1.json()
    draft_id = body["draft_id"]
    assert body["type"] == draft_type
    assert body["status"] == "draft"
    assert body["expires_in_days"] == 30

    try:
        # 2. Persisted to seller_drafts collection
        doc = db.seller_drafts.find_one({"id": draft_id}, {"_id": 0})
        assert doc is not None, f"[{draft_type}] draft not in DB"
        assert doc["type"] == draft_type
        assert doc["status"] == "draft"
        assert doc["payload"]["__marker"] == marker, f"[{draft_type}] payload corrupted"

        # 3. GET /api/drafts/{id} hydrates with exact payload
        r2 = requests.get(f"{BASE_URL}/api/drafts/{draft_id}", headers=_hdr(seller_token), timeout=10)
        assert r2.status_code == 200, f"[{draft_type}] get failed"
        got = r2.json()
        assert got["id"] == draft_id
        assert got["payload"]["__marker"] == marker
        for k, v in payload.items():
            assert got["payload"].get(k) == v, (
                f"[{draft_type}] field {k!r} drifted: expected {v!r}, got {got['payload'].get(k)!r}"
            )

        # 4. Listed in /api/drafts (with this type filter)
        r3 = requests.get(
            f"{BASE_URL}/api/drafts",
            headers=_hdr(seller_token),
            params={"type": draft_type},
            timeout=10,
        )
        assert r3.status_code == 200
        ids = [d["id"] for d in r3.json()["drafts"]]
        assert draft_id in ids, f"[{draft_type}] not in drafts list"

        # 5. Update in place (no duplicate row)
        new_payload = {**payload, "updated_field": "yes-iter313"}
        r4 = requests.post(
            f"{BASE_URL}/api/drafts/save",
            json={"type": draft_type, "draft_id": draft_id, "payload": new_payload},
            headers=_hdr(seller_token),
            timeout=10,
        )
        assert r4.status_code == 200
        assert r4.json()["draft_id"] == draft_id

        count = db.seller_drafts.count_documents({"id": draft_id})
        assert count == 1, f"[{draft_type}] in-place save created duplicate"

        # 6. Verify the new payload field landed.
        r5 = requests.get(f"{BASE_URL}/api/drafts/{draft_id}", headers=_hdr(seller_token), timeout=10)
        assert r5.json()["payload"]["updated_field"] == "yes-iter313"

    finally:
        # 7. Delete cleanup.
        requests.delete(f"{BASE_URL}/api/drafts/{draft_id}", headers=_hdr(seller_token), timeout=10)


# ────────────────────────────────────────────────────────────────────
# Per-type tests — one each, no shared state
# ────────────────────────────────────────────────────────────────────


def test_roundtrip_marketplace_save_as_draft(seller_token, db):
    marker = f"iter313-marketplace-{uuid.uuid4().hex[:8]}"
    _roundtrip(
        "marketplace",
        {
            "__marker":      marker,
            "title":         "Half-typed Marketplace listing",
            "description":   "Only got partway",
            "category":      "Tools",
            "starting_price": 50,
            "city":          "Sherbrooke",
        },
        seller_token, db, marker,
    )


def test_roundtrip_lots_save_as_draft(seller_token, db):
    marker = f"iter313-lots-{uuid.uuid4().hex[:8]}"
    _roundtrip(
        "lots",
        {
            "__marker":  marker,
            "title":     "Half-typed Multi-Item auction",
            "category":  "Furniture",
            "lots": [
                {"lot_number": 1, "title": "lot 1 half typed", "category": "Furniture", "starting_price": 10},
            ],
        },
        seller_token, db, marker,
    )


def test_roundtrip_storage_save_as_draft(seller_token, db):
    marker = f"iter313-storage-{uuid.uuid4().hex[:8]}"
    _roundtrip(
        "storage",
        {
            "__marker":     marker,
            "unit_number":  "A-12",
            "unit_size":    "10x10",
            "unit_type":    "indoor",
            "is_lien_unit": True,
            "description_en": "Half-typed storage description",
        },
        seller_token, db, marker,
    )


def test_roundtrip_vehicle_save_as_draft(seller_token, db):
    marker = f"iter313-vehicle-{uuid.uuid4().hex[:8]}"
    _roundtrip(
        "vehicle",
        {
            "__marker": marker,
            "vin":      "1HGBH41JXMN109186",
            "year":     2018,
            "make":     "Honda",
            "model":    "Civic",
            "trim":     "LX",
        },
        seller_token, db, marker,
    )


def test_roundtrip_multi_lot_vehicle_save_as_draft(seller_token, db):
    marker = f"iter313-multilotveh-{uuid.uuid4().hex[:8]}"
    _roundtrip(
        "multi_lot_vehicle",
        {
            "__marker":   marker,
            "event_title": "Spring vehicle event (half-typed)",
            "draft": {"make": "Toyota", "model": "Tacoma"},
        },
        seller_token, db, marker,
    )


# ────────────────────────────────────────────────────────────────────
# Restore flow (P1 — 60-day window)
# ────────────────────────────────────────────────────────────────────


def test_restore_expired_draft_within_60d_window(seller_token, db):
    """A draft_expired row aged ≤ 60d must restore to status='draft'."""
    from datetime import datetime, timedelta, timezone
    draft_id = str(uuid.uuid4())
    # Use the seller's actual id so ownership checks pass.
    seller = db.users.find_one({"email": SELLER[0]}, {"_id": 0, "id": 1})
    assert seller, "testseller missing from DB"

    db.seller_drafts.insert_one({
        "id":                 draft_id,
        "seller_id":          seller["id"],
        "type":               "marketplace",
        "title":              "iter313 restore-window fixture",
        "payload":            {"title": "Half typed", "iter313_restore_test": True},
        "status":             "draft_expired",
        "created_at":         datetime.now(timezone.utc) - timedelta(days=35),
        "updated_at":         datetime.now(timezone.utc) - timedelta(days=35),
        "draft_expired_at":   datetime.now(timezone.utc) - timedelta(days=5),
    })
    try:
        r = requests.post(f"{BASE_URL}/api/drafts/{draft_id}/restore", headers=_hdr(seller_token), timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "draft"

        doc = db.seller_drafts.find_one({"id": draft_id}, {"_id": 0})
        assert doc["status"] == "draft"
        assert doc["draft_expired_at"] is None
        assert doc.get("restored_at") is not None
    finally:
        db.seller_drafts.delete_one({"id": draft_id})


def test_restore_expired_draft_after_60d_window_blocked(seller_token, db):
    """A draft_expired row aged > 60d must return 410 gone."""
    from datetime import datetime, timedelta, timezone
    draft_id = str(uuid.uuid4())
    seller = db.users.find_one({"email": SELLER[0]}, {"_id": 0, "id": 1})

    db.seller_drafts.insert_one({
        "id":                 draft_id,
        "seller_id":          seller["id"],
        "type":               "marketplace",
        "title":              "iter313 too-old fixture",
        "payload":            {},
        "status":             "draft_expired",
        "created_at":         datetime.now(timezone.utc) - timedelta(days=100),
        "updated_at":         datetime.now(timezone.utc) - timedelta(days=100),
        "draft_expired_at":   datetime.now(timezone.utc) - timedelta(days=70),
    })
    try:
        r = requests.post(f"{BASE_URL}/api/drafts/{draft_id}/restore", headers=_hdr(seller_token), timeout=10)
        assert r.status_code == 410, r.text
    finally:
        db.seller_drafts.delete_one({"id": draft_id})


def test_drafts_list_includes_expired_within_window(seller_token, db):
    """GET /api/drafts?include_expired=true must return draft_expired rows ≤ 60d."""
    from datetime import datetime, timedelta, timezone
    draft_id = str(uuid.uuid4())
    seller = db.users.find_one({"email": SELLER[0]}, {"_id": 0, "id": 1})

    db.seller_drafts.insert_one({
        "id":                 draft_id,
        "seller_id":          seller["id"],
        "type":               "vehicle",
        "title":              "iter313 expired-list fixture",
        "payload":            {},
        "status":             "draft_expired",
        "created_at":         datetime.now(timezone.utc) - timedelta(days=35),
        "updated_at":         datetime.now(timezone.utc) - timedelta(days=35),
        "draft_expired_at":   datetime.now(timezone.utc) - timedelta(days=3),
    })
    try:
        r = requests.get(f"{BASE_URL}/api/drafts?include_expired=true", headers=_hdr(seller_token), timeout=10)
        assert r.status_code == 200
        rows = r.json()["drafts"]
        match = next((d for d in rows if d["id"] == draft_id), None)
        assert match is not None, "expired draft not in list"
        assert match["status"] == "draft_expired"
        assert match.get("restore_days_left") is not None and match["restore_days_left"] > 0
    finally:
        db.seller_drafts.delete_one({"id": draft_id})


def test_drafts_cross_ownership_returns_403(seller_token, db):
    """Reading or modifying another user's draft must 403."""
    foreign_id = str(uuid.uuid4())
    foreign_seller = str(uuid.uuid4())
    db.seller_drafts.insert_one({
        "id":         foreign_id,
        "seller_id":  foreign_seller,
        "type":       "marketplace",
        "payload":    {},
        "status":     "draft",
    })
    try:
        r = requests.get(f"{BASE_URL}/api/drafts/{foreign_id}", headers=_hdr(seller_token), timeout=10)
        assert r.status_code == 403
        r2 = requests.delete(f"{BASE_URL}/api/drafts/{foreign_id}", headers=_hdr(seller_token), timeout=10)
        assert r2.status_code == 403
    finally:
        db.seller_drafts.delete_one({"id": foreign_id})
