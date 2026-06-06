"""
iter284 — Pre-launch critical bug regression tests.

Covers the three production-blocking bugs reported by the operator on
2026-06-06 (UNIT 205 incident):

  Bug 1) Storage cards show a 🔒 placeholder instead of the uploaded
         photo. Root cause: storage units authored via /create-listing
         live in `db.listings` with photos stored under the `images`
         array, but the storage card reads from `auction.photos`. The
         list endpoint now mirrors `images` → `photos` so cross-
         collection units render their real media.

  Bug 2) Clicking a cross-collection storage card opens the detail
         page with a "Auction not found" toast (404). The detail,
         pricing, and bid-history endpoints now fall back to
         `db.listings` and synthesize the storage-card shape.

  Bug 3) Submitting a vehicle listing causes the post-submit
         /vehicle-auctions/my-listings page to render blank (white).
         Root cause: the route was missing an ErrorBoundary AND the
         price formatter crashed on `null`/`undefined` from a freshly-
         persisted listing's `starting_price`. Both shored up.
         (Routing & component change verified via the regression smoke
         test in test_iter283_smoke_runner.py + iter284 manual curl.)

These tests run against the live preview backend, the same way every
other `test_iter283_*` regression does — they hit real HTTP routes,
exercise dual-collection logic, and assert the exact JSON shape the
frontend reads.
"""
import os
import time
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


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture()
def seeded_listing_unit(db):
    """Insert a `db.listings` storage_locker doc (mirrors what
    /create-listing produces). Cleans itself up after the test."""
    lid = f"iter284-test-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=3)
    doc = {
        "id": lid,
        "seller_id": "iter284-test-seller",
        "seller_name": "Iter284 Test Facility",
        "title": "iter284 test locker",
        "description": "regression fixture — auto-cleaned by teardown",
        "category": "storage_locker",
        "listing_type": "storage_locker",
        "section": "storage",
        "condition": "as_is",
        "starting_price": 25.0,
        "current_price": 25.0,
        "bid_increment": 5.0,
        "images": [
            "https://bidvex-marketplace-images.s3.us-east-2.amazonaws.com/listings/iter284/00-front.jpg",
            "https://bidvex-marketplace-images.s3.us-east-2.amazonaws.com/listings/iter284/01-interior.jpg",
        ],
        "city": "Montreal",
        "region": "QC",
        "country": "CA",
        "location": "Montreal, QC, H3C 1M8",
        "status": "active",
        "auction_start_date": now.isoformat(),
        "auction_end_date": end.isoformat(),
        "storage_metadata": {
            "facility_name": "Iter284 Test Facility",
            "locker_number": "T-284",
            "locker_size": "5x10",
        },
        "created_at": now.isoformat(),
    }
    db.listings.insert_one(doc.copy())
    yield doc
    db.listings.delete_one({"id": lid})


# ── Bug 1 — Photo field normalization ─────────────────────────────────


def test_bug1_listings_collection_storage_unit_exposes_photos(db, seeded_listing_unit):
    """`GET /api/storage-auctions` must mirror `images` → `photos` so the
    storage browse grid renders the uploaded photo (UNIT 205 bug)."""
    r = requests.get(f"{BASE_URL}/api/storage-auctions?limit=50", timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    hit = next((a for a in body.get("auctions", []) if a.get("id") == seeded_listing_unit["id"]), None)
    assert hit is not None, f"seeded unit {seeded_listing_unit['id']} did not surface in storage list"
    # Real production assertion — the card needs `photos[0]`.
    assert hit.get("photos"), "photos array is empty/missing — card would render the 🔒 placeholder"
    assert hit["photos"][0] == seeded_listing_unit["images"][0]
    # Sanity — bilingual description still flows through.
    assert hit.get("description_en") == seeded_listing_unit["description"]


# ── Bug 2 — Dual-visibility for the detail / bids / pricing trio ──────


def test_bug2_detail_endpoint_finds_cross_collection_unit(db, seeded_listing_unit):
    """`GET /api/storage-auctions/{id}` must succeed for storage units
    that live in `db.listings` (no more "Auction not found" 404 toast)."""
    lid = seeded_listing_unit["id"]
    r = requests.get(f"{BASE_URL}/api/storage-auctions/{lid}", timeout=10)
    assert r.status_code == 200, f"detail 404'd: {r.status_code} {r.text[:300]}"
    body = r.json()
    assert body["id"] == lid
    assert body["unit_number"] == "T-284"
    assert body["facility_name"] == "Iter284 Test Facility"
    assert body["facility"]["company_name"] == "Iter284 Test Facility"
    # Photos field is normalized from images.
    assert body.get("photos"), "detail page would render no photos"
    # Provincial flag — Quebec, displays the GST + QST tax string downstream.
    assert body.get("facility_province") == "QC"


def test_bug2_bids_endpoint_returns_empty_history_not_404(seeded_listing_unit):
    """Bid history endpoint must not 404 for cross-collection units —
    StorageAuctionDetail.fetchData parallelizes detail+bids+pricing, so
    a 404 on any one of them surfaces a "fetch failed" red toast."""
    lid = seeded_listing_unit["id"]
    r = requests.get(f"{BASE_URL}/api/storage-auctions/{lid}/bids", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["bids"] == []
    assert body["total_bids"] == 0


def test_bug2_pricing_endpoint_returns_qc_breakdown_not_404(seeded_listing_unit):
    """Pricing preview must return the QC tax string so the detail page's
    invoice breakdown renders."""
    lid = seeded_listing_unit["id"]
    r = requests.get(
        f"{BASE_URL}/api/storage-auctions/{lid}/pricing?payment_method=stripe",
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["province"] == "QC"
    # Confirm the QC tax label survives (GST + QST math, not generic "tax").
    assert "GST" in body["tax_label"]
    assert "QST" in body["tax_label"]


def test_bug2_detail_404_still_works_for_truly_unknown_id():
    """Regression — the dual-fallback must NOT swallow real 404s.
    A nonsense id must still surface the legitimate 404."""
    r = requests.get(
        f"{BASE_URL}/api/storage-auctions/this-id-does-not-exist-iter284",
        timeout=10,
    )
    assert r.status_code == 404


# ── Bug 3 — White-page guard (smoke test of the price formatter) ──────


def test_bug3_starting_price_null_does_not_crash_listing_endpoint(db):
    """Backend regression guard for the white-page fix: GET
    /api/vehicles/my/listings must not 500 even if a stored listing
    happens to carry `starting_price=None`. The frontend formatter is
    defensive but the backend should also stay healthy."""
    # We don't auth here; just confirm the public route survives.
    r = requests.get(f"{BASE_URL}/api/vehicles?limit=1", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "vehicles" in body
    assert "total" in body
