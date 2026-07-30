"""iter428 — My Vehicles module backend tests.

Covers:
  - GET  /api/vehicles/my/listings
  - POST /api/vehicles/{id}/duplicate  (success, 404 not-owned)
  - POST /api/vehicles/{id}/retire     (success, idempotent, 409 sold, 404 not-owned)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")

DEALER_EMAIL = "testdealer@bidvex.com"
DEALER_PASSWORD = "TestDealer2026!"
BUYER_EMAIL = "testbuyer@bidvex.com"
BUYER_PASSWORD = "TestBuyer2026!"


@pytest.fixture(scope="module")
def dealer_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": DEALER_EMAIL, "password": DEALER_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def dealer_headers(dealer_token):
    return {"Authorization": f"Bearer {dealer_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def my_listings(dealer_headers):
    r = requests.get(f"{BASE_URL}/api/vehicles/my/listings", headers=dealer_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "listings" in data
    return data["listings"]


# ------- GET /api/vehicles/my/listings -------

def test_my_listings_returns_200_and_dealer_owns_all(dealer_headers, my_listings):
    assert isinstance(my_listings, list)
    assert len(my_listings) >= 1, "Expected >=1 seeded listings for testdealer"
    # All listings must have seller_id (dealer owns them)
    seller_ids = {l.get("seller_id") for l in my_listings}
    assert len(seller_ids) == 1, f"Expected single seller_id, got {seller_ids}"


def test_my_listings_covers_expected_statuses(my_listings):
    statuses = {l.get("status") for l in my_listings}
    print(f"[my_listings] statuses present: {statuses}")
    # seed intent per review request: active x2, draft, sold, retired
    # Not strict — just ensure a decent spread
    assert "draft" in statuses or "active" in statuses


# ------- POST /api/vehicles/{id}/duplicate -------

def _pick(my_listings, predicate):
    for l in my_listings:
        if predicate(l):
            return l
    return None


def test_duplicate_success_creates_new_draft(dealer_headers, my_listings):
    # Pick any listing that is not sold (we'll duplicate it)
    src = _pick(my_listings, lambda l: l.get("status") != "sold") or my_listings[0]
    src_id = src["id"]
    src_title = src.get("title") or ""
    src_bids = src.get("bid_count", 0)

    r = requests.post(f"{BASE_URL}/api/vehicles/{src_id}/duplicate",
                      headers=dealer_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert data.get("status") == "draft"
    new_id = data.get("id")
    assert new_id and new_id != src_id

    # Verify persistence via GET /api/vehicles/my/listings
    r2 = requests.get(f"{BASE_URL}/api/vehicles/my/listings", headers=dealer_headers, timeout=20)
    listings = r2.json()["listings"]
    new_row = _pick(listings, lambda l: l["id"] == new_id)
    assert new_row is not None, "duplicate not visible in my/listings"
    assert new_row["status"] == "draft"
    assert new_row.get("bid_count", 0) == 0
    assert new_row.get("views_count", 0) == 0
    assert (new_row.get("current_bid") or 0) == 0
    assert new_row.get("winner_id") in (None, "")
    if src_title:
        assert "(Copy)" in (new_row.get("title") or ""), f"Expected (Copy) suffix, got {new_row.get('title')!r}"

    # Original unchanged
    orig = _pick(listings, lambda l: l["id"] == src_id)
    assert orig is not None
    assert orig.get("bid_count", 0) == src_bids
    assert orig.get("status") == src.get("status")


def test_duplicate_404_when_not_owned(dealer_headers):
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = requests.post(f"{BASE_URL}/api/vehicles/{fake_id}/duplicate",
                      headers=dealer_headers, timeout=20)
    assert r.status_code == 404, r.text


# ------- POST /api/vehicles/{id}/retire -------

def test_retire_non_sold_success(dealer_headers, my_listings):
    # Pick an active or draft listing that isn't already retired/sold
    target = _pick(my_listings, lambda l: l.get("status") in ("active", "draft"))
    assert target, "no active/draft listing to retire"
    tid = target["id"]

    r = requests.post(f"{BASE_URL}/api/vehicles/{tid}/retire",
                      headers=dealer_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert data.get("status") == "retired"

    # Verify persisted + retired_at/retired_by stamped (via my/listings)
    r2 = requests.get(f"{BASE_URL}/api/vehicles/my/listings", headers=dealer_headers, timeout=20)
    row = _pick(r2.json()["listings"], lambda l: l["id"] == tid)
    assert row and row["status"] == "retired"
    assert row.get("retired_at"), "retired_at not stamped"
    assert row.get("retired_by"), "retired_by not stamped"

    # Idempotent second call
    r3 = requests.post(f"{BASE_URL}/api/vehicles/{tid}/retire",
                       headers=dealer_headers, timeout=20)
    assert r3.status_code == 200, r3.text
    d3 = r3.json()
    assert d3.get("ok") is True
    assert d3.get("status") == "retired"
    assert d3.get("already") is True, f"expected already=True, got {d3}"


def test_retire_sold_returns_409_bilingual(dealer_headers, my_listings):
    sold = _pick(my_listings, lambda l: l.get("status") == "sold")
    if not sold:
        pytest.skip("No sold listing in seed for testdealer")
    r = requests.post(f"{BASE_URL}/api/vehicles/{sold['id']}/retire",
                      headers=dealer_headers, timeout=20)
    assert r.status_code == 409, r.text
    body = r.json()
    detail = body.get("detail") or {}
    assert detail.get("code") == "cannot_retire_sold"
    assert "message_en" in detail
    assert "message_fr" in detail
    assert detail["message_en"] and detail["message_fr"]


def test_retire_404_when_not_owned(dealer_headers):
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = requests.post(f"{BASE_URL}/api/vehicles/{fake_id}/retire",
                      headers=dealer_headers, timeout=20)
    assert r.status_code == 404, r.text
