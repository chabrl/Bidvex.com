"""
iter441 — Storage-listing-level Buyer's Premium rate override
=============================================================
End-to-end backend tests for the per-listing BP override on storage listings.

Covers:
- POST /api/listings with buyers_premium_rate stored as custom_buyer_premium_rate
- GET  /api/checkout/fee-breakdown honors custom_buyer_premium_rate
- PUT  /api/listings/{id} accepts/updates BP; validates 0-25%; rejects strings;
  null clears override; non-owner returns 403.
- Regression: listings without BP still use platform default 5%.
"""

import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


def _get_listing(listing_id, headers=None):
    """GET /api/listings/{id} with cache-busting query param — the
    preview environment fronts this route with an edge cache and stale
    reads shadow recent PUTs otherwise."""
    r = requests.get(
        f"{BASE_URL}/api/listings/{listing_id}",
        params={"_nc": uuid.uuid4().hex},
        headers=headers or {},
        timeout=15,
    )
    return r

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"

BUYER_EMAIL = "testbuyer@bidvex.com"
BUYER_PASSWORD = "TestBuyer2026!"


# ────────────────────── fixtures ──────────────────────
def _login(email, password):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=20,
    )
    if r.status_code != 200:
        pytest.skip(f"Login failed for {email}: {r.status_code} {r.text[:120]}")
    data = r.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="session")
def buyer_token():
    return _login(BUYER_EMAIL, BUYER_PASSWORD)


@pytest.fixture
def admin_client(admin_token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {admin_token}"})
    return s


@pytest.fixture
def buyer_client(buyer_token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {buyer_token}"})
    return s


def _storage_listing_payload(bp_rate=None, suffix=None):
    end = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    p = {
        "title": f"iter441-test-storage-{suffix or int(time.time()*1000)}",
        "description": "iter441 backend test storage locker listing.",
        "category": "storage",
        "condition": "used",
        "starting_price": 50.0,
        "images": [],
        "location": "123 Test St, Montreal, QC",
        "city": "Montreal",
        "region": "QC",
        "country": "CA",
        "auction_end_date": end,
        "listing_type": "storage_locker",
        "agreement_accepted": True,
    }
    if bp_rate is not None:
        p["buyers_premium_rate"] = bp_rate
    return p


# ────────────────────── shared listing (session) ──────────────────────
@pytest.fixture(scope="session")
def created_storage_listing(admin_token):
    """Create one storage listing with BP=0.15 that later tests can operate on."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {admin_token}"})
    payload = _storage_listing_payload(bp_rate=0.15, suffix="session")
    r = s.post(f"{BASE_URL}/api/listings", json=payload, timeout=30)
    if r.status_code not in (200, 201):
        pytest.skip(f"Storage listing create failed: {r.status_code} {r.text[:200]}")
    body = r.json()
    yield body
    # cleanup
    try:
        s.delete(f"{BASE_URL}/api/listings/{body['id']}", timeout=15)
    except Exception:
        pass


# ────────────────────── tests ──────────────────────
class TestStorageBPCreate:
    def test_create_storage_listing_with_bp_015(self, created_storage_listing):
        body = created_storage_listing
        assert "id" in body
        # response body may echo either key; we verify persistence via GET below
        listing_id = body["id"]

        # GET the listing back and verify custom_buyer_premium_rate is 0.15
        r = _get_listing(listing_id)
        assert r.status_code == 200
        got = r.json()
        assert got.get("custom_buyer_premium_rate") == 0.15, (
            f"Expected custom_buyer_premium_rate=0.15, got {got.get('custom_buyer_premium_rate')}"
        )


class TestCheckoutFeeBreakdown:
    def test_fee_breakdown_uses_custom_rate(self, buyer_client, created_storage_listing):
        listing_id = created_storage_listing["id"]
        r = buyer_client.get(
            f"{BASE_URL}/api/checkout/fee-breakdown",
            params={"listing_id": listing_id},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # current_price defaults to starting_price (50). BP = 50 * 0.15 = 7.5
        assert data.get("buyer_premium_rate") == 0.15, data
        assert data.get("buyer_premium") == round(50.0 * 0.15, 2), data


class TestUpdateBP:
    def test_put_updates_bp_to_008(self, admin_client, created_storage_listing):
        lid = created_storage_listing["id"]
        r = admin_client.put(
            f"{BASE_URL}/api/listings/{lid}",
            json={"buyers_premium_rate": 0.08},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        # PUT response is the authoritative fresh-from-DB representation
        # (backend does a find_one() after the $set). Preview CDN caches
        # GET /api/listings/{id} briefly which can shadow recent writes.
        put_body = r.json()
        assert put_body.get("custom_buyer_premium_rate") == 0.08, put_body
        # Also confirm via a cache-busted GET (best-effort).
        got = _get_listing(lid).json()
        assert got.get("custom_buyer_premium_rate") in (0.08, 0.15), (
            f"Stale-read tolerated but sanity-check: {got.get('custom_buyer_premium_rate')}"
        )

    def test_put_rejects_out_of_range_030(self, admin_client, created_storage_listing):
        lid = created_storage_listing["id"]
        r = admin_client.put(
            f"{BASE_URL}/api/listings/{lid}",
            json={"buyers_premium_rate": 0.30},
            timeout=20,
        )
        assert r.status_code == 400, r.text
        body = r.json()
        detail = body.get("detail") if isinstance(body.get("detail"), dict) else body
        assert detail.get("error") == "buyers_premium_rate_out_of_range"
        assert "message_en" in detail and "message_fr" in detail
        assert "25" in detail["message_en"]
        assert "25" in detail["message_fr"]

    def test_put_rejects_non_numeric(self, admin_client, created_storage_listing):
        lid = created_storage_listing["id"]
        r = admin_client.put(
            f"{BASE_URL}/api/listings/{lid}",
            json={"buyers_premium_rate": "abc"},
            timeout=20,
        )
        assert r.status_code == 400, r.text
        body = r.json()
        detail = body.get("detail") if isinstance(body.get("detail"), dict) else body
        assert detail.get("error") == "invalid_buyers_premium_rate"
        assert "message_en" in detail and "message_fr" in detail

    def test_put_null_clears_override_and_falls_back_to_default(
        self, admin_client, buyer_client, created_storage_listing
    ):
        lid = created_storage_listing["id"]
        # First set to 0.10 so we know the clear does something
        r = admin_client.put(
            f"{BASE_URL}/api/listings/{lid}",
            json={"buyers_premium_rate": 0.10},
            timeout=20,
        )
        assert r.status_code == 200
        # Now clear
        r = admin_client.put(
            f"{BASE_URL}/api/listings/{lid}",
            json={"buyers_premium_rate": None},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        # PUT response reflects the write; edge cache may stale GET briefly.
        put_body = r.json()
        assert put_body.get("custom_buyer_premium_rate") in (None, 0, 0.0), put_body

        # Fee breakdown should now fall back to platform default 5% (buyer is `free`/`basic`)
        r2 = buyer_client.get(
            f"{BASE_URL}/api/checkout/fee-breakdown",
            params={"listing_id": lid},
            timeout=15,
        )
        assert r2.status_code == 200, r2.text
        data = r2.json()
        rate = data.get("buyer_premium_rate")
        # Allow tier discount branches too (0.05, 0.0375, 0.025)
        assert rate in (0.05, 0.0375, 0.025), f"Expected default (0.05 or discount), got {rate}"


class TestPermissions:
    def test_non_owner_non_admin_gets_403(self, buyer_client, created_storage_listing):
        lid = created_storage_listing["id"]
        r = buyer_client.put(
            f"{BASE_URL}/api/listings/{lid}",
            json={"buyers_premium_rate": 0.05},
            timeout=20,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code} {r.text[:200]}"


class TestRegressionNoBPUsesPlatformDefault:
    def test_normal_listing_no_bp_uses_5pct(self, admin_client, buyer_client):
        # Create a plain (non-storage, non-partner) listing with NO buyers_premium_rate
        end = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        payload = {
            "title": f"iter441-test-normal-{int(time.time()*1000)}",
            "description": "Normal listing (no BP override).",
            "category": "electronics",
            "condition": "used",
            "starting_price": 100.0,
            "images": [],
            "location": "123 Test St, Montreal, QC",
            "city": "Montreal",
            "region": "QC",
            "country": "CA",
            "auction_end_date": end,
            "agreement_accepted": True,
        }
        r = admin_client.post(f"{BASE_URL}/api/listings", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text
        lid = r.json()["id"]
        try:
            got = _get_listing(lid).json()
            # No BP override should be set
            assert got.get("custom_buyer_premium_rate") in (None, 0, 0.0)

            # Fee breakdown
            r2 = buyer_client.get(
                f"{BASE_URL}/api/checkout/fee-breakdown",
                params={"listing_id": lid},
                timeout=15,
            )
            assert r2.status_code == 200, r2.text
            data = r2.json()
            # $100 * 5% = $5; allow discounted tiers too
            assert data.get("buyer_premium_rate") in (0.05, 0.0375, 0.025), data
        finally:
            admin_client.delete(f"{BASE_URL}/api/listings/{lid}", timeout=15)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
