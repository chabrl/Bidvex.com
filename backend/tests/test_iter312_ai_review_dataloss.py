"""
iter312 — Data-loss bug regression tests.

The bug: when a seller's listing was blocked by the AI vehicle-compliance
gate and they clicked "Request Manual Review", the backend's
`request_manual_vehicle_review` endpoint created a stub listing with
HARDCODED empty strings for location/city/region/country and missing
postal_code/province. Admin approve was a pure status flip — so the
listing went public with empty geographic data.

These tests assert the full flag → pending_admin_review → approve cycle
preserves every field the seller's wizard supplied.
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

ADMIN = ("charbel911@gmail.com", "Anderosli123!@#")
SELLER = ("testseller@bidvex.com", "TestSeller2026!")


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


@pytest.fixture(scope="module")
def seller_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": SELLER[0], "password": SELLER[1]}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"seller login failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


# ────────────────────────────────────────────────────────────────────
# Test 1 — Vehicle-block stub listing preserves all seller-supplied fields
# ────────────────────────────────────────────────────────────────────

def test_manual_vehicle_review_preserves_all_fields(seller_token, db):
    payload = {
        "title":           "iter312 — 2018 Honda Civic LX",
        "title_fr":        "iter312 — Honda Civic LX 2018",
        "description":     "Excellent condition, single owner, full service history.",
        "description_fr":  "Excellent état, propriétaire unique, historique d'entretien complet.",
        "category":        "Vehicles",
        "detected_signals": ["title:vehicle", "description:year_make_model"],
        "starting_price":  12500,
        "buy_now_price":   18000,
        "location":        "iter312-test-address-Montréal",
        "city":            "Montréal",
        "region":          "QC",
        "country":         "CA",
        "postal_code":     "H2T 2X5",
        "province":        "QC",
        "condition":       "good",
        "currency":        "CAD",
    }
    r = requests.post(
        f"{BASE_URL}/api/listings/request-manual-vehicle-review",
        json=payload,
        headers=_hdr(seller_token),
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    listing_review_id = body["listing_review_id"]
    listing_id = f"locked-{listing_review_id}"

    try:
        listing = db.listings.find_one({"id": listing_id}, {"_id": 0})
        assert listing is not None, f"locked-* listing was not created: {listing_id}"

        # The core regression: every field the seller supplied must be on the doc.
        assert listing["location"]    == payload["location"],    f"location lost: {listing.get('location')!r}"
        assert listing["city"]        == payload["city"],        f"city lost: {listing.get('city')!r}"
        assert listing["region"]      == payload["region"],      f"region lost: {listing.get('region')!r}"
        assert listing["country"]     == payload["country"],     f"country lost: {listing.get('country')!r}"
        assert listing["postal_code"] == payload["postal_code"], f"postal_code lost: {listing.get('postal_code')!r}"
        assert listing["province"]    == payload["province"],    f"province lost: {listing.get('province')!r}"
        assert listing["category"]    == payload["category"],    f"category lost: {listing.get('category')!r}"
        assert listing["title"]       == payload["title"],       f"title lost: {listing.get('title')!r}"
        assert listing["title_fr"]    == payload["title_fr"],    f"title_fr lost"
        assert listing["description_fr"] == payload["description_fr"], f"description_fr lost"
        assert listing["condition"]   == payload["condition"]
        assert listing["currency"]    == payload["currency"]
        assert listing["buy_now_price"] == payload["buy_now_price"]
        assert listing["status"]      == "pending_admin_review"
        # iter312 D2 — Seller-editability flag.
        assert listing.get("is_seller_editable_pending") is True
    finally:
        db.listings.delete_many({"id": listing_id})
        db.listing_reviews.delete_many({"id": listing_review_id})
        db.manual_review_requests.delete_many({"id": listing_review_id})


# ────────────────────────────────────────────────────────────────────
# Test 2 — Admin approve preserves seller fields end-to-end
# ────────────────────────────────────────────────────────────────────

def test_admin_approve_preserves_seller_fields_end_to_end(seller_token, admin_token, db):
    payload = {
        "title":           "iter312-approve-roundtrip Honda",
        "description":     "fixture roundtrip listing",
        "category":        "Vehicles",
        "detected_signals": ["title:vehicle"],
        "starting_price":  9999,
        "location":        "ROUNDTRIP-LOCATION-VALUE",
        "city":            "ROUNDTRIP-CITY",
        "region":          "QC",
        "country":         "CA",
        "postal_code":     "G1V 1G4",
        "province":        "QC",
        "condition":       "good",
        "currency":        "CAD",
    }
    r = requests.post(
        f"{BASE_URL}/api/listings/request-manual-vehicle-review",
        json=payload,
        headers=_hdr(seller_token),
        timeout=15,
    )
    assert r.status_code == 200, r.text
    listing_review_id = r.json()["listing_review_id"]
    listing_id = f"locked-{listing_review_id}"

    try:
        # Snapshot the pre-approval doc.
        pre = db.listings.find_one({"id": listing_id}, {"_id": 0})
        assert pre is not None
        assert pre["status"] == "pending_admin_review"

        # Admin approves.
        ra = requests.post(
            f"{BASE_URL}/api/admin/listing-reviews/{listing_review_id}/approve",
            json={"admin_note": "iter312 regression — preserve fields"},
            headers=_hdr(admin_token),
            timeout=15,
        )
        assert ra.status_code == 200, ra.text

        # Verify post-approval doc still has every field.
        post = db.listings.find_one({"id": listing_id}, {"_id": 0})
        assert post["status"] == "active"
        for k in ("title", "description", "category", "location", "city", "region",
                  "country", "postal_code", "province", "starting_price",
                  "condition", "currency"):
            assert post.get(k) == pre.get(k), (
                f"field {k!r} mutated during approve: pre={pre.get(k)!r} post={post.get(k)!r}"
            )
        # Approve flags must be set.
        assert post.get("admin_approved_override") is True
        assert post.get("ai_scan_bypass") is True
    finally:
        db.listings.delete_many({"id": listing_id})
        db.listing_reviews.delete_many({"id": listing_review_id})
        db.manual_review_requests.delete_many({"id": listing_review_id})


# ────────────────────────────────────────────────────────────────────
# Test 3 — Seller can edit a pending_admin_review listing via PUT
# ────────────────────────────────────────────────────────────────────

def test_seller_can_edit_pending_listing(seller_token, db):
    payload = {
        "title":           "iter312-D2-edit-fixture",
        "description":     "pre-edit description",
        "category":        "Vehicles",
        "detected_signals": ["title:vehicle"],
        "starting_price":  5000,
        "location":        "PRE-EDIT-LOC",
        "city":            "PRE-EDIT-CITY",
        "region":          "ON",
        "country":         "CA",
        "postal_code":     "M5V 2T6",
    }
    r = requests.post(
        f"{BASE_URL}/api/listings/request-manual-vehicle-review",
        json=payload,
        headers=_hdr(seller_token),
        timeout=15,
    )
    assert r.status_code == 200, r.text
    listing_review_id = r.json()["listing_review_id"]
    listing_id = f"locked-{listing_review_id}"

    try:
        # Seller edits via PUT — should NOT 403 just because status is pending.
        ru = requests.put(
            f"{BASE_URL}/api/listings/{listing_id}",
            json={
                "title":    "iter312-D2-edited-title",
                "category": "Tools",   # seller realises they picked wrong category
                "location": "POST-EDIT-LOC",
                "city":     "POST-EDIT-CITY",
            },
            headers=_hdr(seller_token),
            timeout=15,
        )
        assert ru.status_code == 200, f"edit blocked: {ru.status_code} {ru.text}"
        edited = ru.json()
        assert edited["title"]    == "iter312-D2-edited-title"
        assert edited["category"] == "Tools"
        assert edited["location"] == "POST-EDIT-LOC"
        assert edited["city"]     == "POST-EDIT-CITY"
    finally:
        db.listings.delete_many({"id": listing_id})
        db.listing_reviews.delete_many({"id": listing_review_id})
        db.manual_review_requests.delete_many({"id": listing_review_id})


# ────────────────────────────────────────────────────────────────────
# Test 4 — Resubmit endpoint exists and triggers a rescan
# ────────────────────────────────────────────────────────────────────

def test_resubmit_endpoint_exists_and_responds(seller_token, db):
    """The /api/listings/{id}/resubmit-for-review endpoint must exist and
    respond with a status indicating either 'active' (rescan passed) or
    'pending_admin_review' (rescan still flagged)."""
    payload = {
        "title":           "iter312-resubmit-fixture",
        "description":     "small wooden chair",
        "category":        "Furniture",
        "detected_signals": ["category:false_positive"],
        "starting_price":  50,
        "location":        "iter312-resubmit-loc",
        "city":            "Toronto",
        "region":          "ON",
        "country":         "CA",
    }
    r = requests.post(
        f"{BASE_URL}/api/listings/request-manual-vehicle-review",
        json=payload,
        headers=_hdr(seller_token),
        timeout=15,
    )
    assert r.status_code == 200, r.text
    listing_review_id = r.json()["listing_review_id"]
    listing_id = f"locked-{listing_review_id}"

    try:
        rr = requests.post(
            f"{BASE_URL}/api/listings/{listing_id}/resubmit-for-review",
            headers=_hdr(seller_token),
            timeout=20,
        )
        assert rr.status_code == 200, rr.text
        body = rr.json()
        assert body["success"] is True
        assert body["status"] in ("active", "pending_admin_review")
        assert body["rescan"] in ("passed", "still_flagged")
    finally:
        db.listings.delete_many({"id": listing_id})
        db.listing_reviews.delete_many({"id": listing_review_id})
        db.manual_review_requests.delete_many({"id": listing_review_id})


# ────────────────────────────────────────────────────────────────────
# Test 5 — Code-level invariant: approve endpoint is a pure $set
# ────────────────────────────────────────────────────────────────────

def test_admin_approve_uses_pure_set_semantics():
    """The approve handler must use $set on an allow-list — NOT
    insert/replace/reconstruction (the previous-iteration claim about
    this remains true and we want a regression guard)."""
    import inspect
    from routes import admin_ai_review
    src = inspect.getsource(admin_ai_review.admin_approve_listing_review)
    assert "$set" in src
    assert "replace_one" not in src
    assert "insert_one" not in src
    # The approve endpoint must NOT touch `location`/`city`/`region`/`country`
    # (those are seller fields, not admin-controllable from the review row).
    assert "'location'" not in src
    assert "'city'" not in src
    assert "'region'" not in src
    assert "'country'" not in src


# ────────────────────────────────────────────────────────────────────
# Test 6 — Code-level invariant: stub doc creator no longer hardcodes empty strings
# ────────────────────────────────────────────────────────────────────

def test_request_manual_vehicle_review_no_longer_hardcodes_empties():
    """The locked-* stub creator must NOT pin location/city/region/country
    to empty strings irrespective of seller input (that was the iter312
    root cause)."""
    import inspect
    from routes import admin_ai_review
    src = inspect.getsource(admin_ai_review.request_manual_vehicle_review)
    # The bug pattern was four consecutive lines:
    #   "location":           "",
    #   "city":               "",
    #   "region":             "",
    #   "country":            "",
    # Confirm none of those four hardcoded empty assignments survive.
    assert '"location":           ""' not in src, "location hardcoded empty"
    assert '"city":               ""' not in src, "city hardcoded empty"
    assert '"region":             ""' not in src, "region hardcoded empty"
    assert '"country":            ""' not in src, "country hardcoded empty"
    # New pattern must reference payload.location etc.
    assert "payload.location" in src
    assert "payload.city" in src
    assert "payload.region" in src
    assert "payload.country" in src


def test_get_listing_endpoint_serves_locked_stub_200(seller_token, db):
    """Regression guard (per testing agent feedback): GET /api/listings/{id}
    MUST return 200 with the full seller form snapshot for a locked-*
    pending_admin_review stub. The previous iter309 contract had
    current_price + auction_end_date required on the response model — the
    stub creator must keep those populated so the Edit-mode hydration
    on /edit-listing/:id never breaks."""
    payload = {
        "title":           "iter312-http-roundtrip",
        "description":     "fixture",
        "category":        "Vehicles",
        "detected_signals": ["title:vehicle"],
        "starting_price":  77,
        "location":        "HTTP-ROUNDTRIP-LOC",
        "city":            "HTTP-CITY",
        "region":          "QC",
        "country":         "CA",
    }
    r = requests.post(
        f"{BASE_URL}/api/listings/request-manual-vehicle-review",
        json=payload,
        headers=_hdr(seller_token),
        timeout=15,
    )
    assert r.status_code == 200, r.text
    listing_id = f"locked-{r.json()['listing_review_id']}"

    try:
        # Anonymous GET (used by frontend edit hydration before token attaches).
        rg = requests.get(f"{BASE_URL}/api/listings/{listing_id}", timeout=15)
        assert rg.status_code == 200, f"GET broke contract: {rg.status_code} {rg.text[:300]}"
        body = rg.json()
        assert body["title"]          == payload["title"]
        assert body["location"]       == payload["location"]
        assert body["city"]           == payload["city"]
        assert body["region"]         == payload["region"]
        assert body["country"]        == payload["country"]
        assert body["current_price"]  == 77.0
        # auction_end_date is required by the Listing response model.
        assert body["auction_end_date"] is not None
    finally:
        db.listings.delete_many({"id": listing_id})
        db.listing_reviews.delete_many({"id": listing_id.removeprefix("locked-")})
        db.manual_review_requests.delete_many({"id": listing_id.removeprefix("locked-")})
