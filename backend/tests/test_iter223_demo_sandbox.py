"""
iter223 — Admin Demo Section: sandbox listing isolation + mock metrics.

Covers:
  Task 1.1: Demo account types include "auctioneer".
  Task 1.2: `is_demo_account=true` users can create listings (no 403 block).
  Task 2.1: Listings created by demo accounts get `is_demo_sandbox=true`.
  Task 2.2: Public marketplace EXCLUDES `is_demo_sandbox` listings.
  Task 2.3: Demo creator sees their OWN sandbox listings via owner-self-include.
  Task 3:   `/api/analytics/seller/{id}` injects mock metrics for demo users
            with empty data.
"""
import os
import uuid
import pytest
import requests


def _api_base() -> str:
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.strip().split("=", 1)[1].rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL missing")


BASE_URL = _api_base()


# ── 1. Demo account type catalog ────────────────────────────────────


def test_demo_account_types_include_auctioneer():
    from services.demo_account_service import DEMO_ACCOUNT_TYPES
    assert "auctioneer" in DEMO_ACCOUNT_TYPES
    assert "vehicle_dealer" in DEMO_ACCOUNT_TYPES
    assert "storage_facility" in DEMO_ACCOUNT_TYPES
    assert "partner" in DEMO_ACCOUNT_TYPES


# ── 2. Demo creator + sandbox flow ──────────────────────────────────


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code}")
    body = r.json()
    return body.get("access_token") or body.get("token")


@pytest.fixture(scope="module")
def demo_account(admin_token):
    """Spin up a fresh demo lead via the admin endpoint."""
    suffix = uuid.uuid4().hex[:6]
    payload = {
        "account_type":  "auctioneer",
        "company_name":  f"Pytest Demo {suffix}",
        "contact_email": f"demo-iter223-{suffix}@example.com",
        "province":      "QC",
        "duration_days": 14,
        "notes":         "Created by iter223 automated test",
    }
    r = requests.post(
        f"{BASE_URL}/api/admin/demo-accounts",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    if r.status_code not in (200, 201):
        pytest.skip(f"Demo account creation failed: {r.status_code} {r.text}")
    body = r.json()
    # Endpoint returns generated password under various keys depending on rev
    pw = body.get("password") or body.get("temp_password") or body.get("initial_password")
    uid = body.get("user_id") or body.get("id") or (body.get("user") or {}).get("id")
    return {
        "email":    payload["contact_email"],
        "password": pw,
        "user_id":  uid,
    }


def _login(email: str, password: str) -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


def _demo_listing_payload():
    safe = "".join("ghjkmnpqr"[uuid.uuid4().int % 9] for _ in range(8))
    return {
        "title": f"Demo Sandbox Bundle {safe}",
        "title_fr": f"Lot Démo Bac {safe}",
        "description": "Pure pure pure - generic empty placeholder.",
        "description_fr": "Pur pur pur - placeholder generique.",
        "category": "misc",
        "condition": "good",
        "starting_price": 25.0,
        "images": [],
        "location": "Toronto, ON",
        "city": "Toronto",
        "region": "ON",
        "country": "CA",
        "auction_end_date": "2027-12-15T20:00:00+00:00",
        "agreement_accepted": True,
    }


def test_demo_user_can_create_listing(demo_account):
    """The 403 block on demo users creating listings MUST be lifted (iter223)."""
    if not demo_account.get("password"):
        pytest.skip("demo account password not returned by admin endpoint")
    token = _login(demo_account["email"], demo_account["password"])
    payload = _demo_listing_payload()
    r = requests.post(
        f"{BASE_URL}/api/listings",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert r.status_code in (200, 201), r.text
    out = r.json()
    assert out.get("id"), out


def test_demo_user_listings_get_is_demo_sandbox_stamp(demo_account):
    """Every listing the demo user creates MUST be stamped is_demo_sandbox=true."""
    if not demo_account.get("password"):
        pytest.skip()
    token = _login(demo_account["email"], demo_account["password"])
    r = requests.post(
        f"{BASE_URL}/api/listings",
        json=_demo_listing_payload(),
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert r.status_code in (200, 201), r.text
    out = r.json()
    # Verify via the GET endpoint (may pull from cache; both shapes accepted)
    lid = out["id"]
    r2 = requests.get(
        f"{BASE_URL}/api/listings/{lid}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert r2.status_code == 200, r2.text
    listing = r2.json()
    assert listing.get("is_demo_sandbox") is True
    assert listing.get("is_demo") is True


def test_demo_listings_excluded_from_public_marketplace(demo_account):
    """Public `/api/marketplace/items` (no auth) MUST exclude sandbox listings."""
    if not demo_account.get("password"):
        pytest.skip()
    token = _login(demo_account["email"], demo_account["password"])
    create_resp = requests.post(
        f"{BASE_URL}/api/listings",
        json=_demo_listing_payload(),
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert create_resp.status_code in (200, 201)
    sandbox_id = create_resp.json()["id"]

    # Anonymous fetch — must NOT contain the sandbox listing
    r = requests.get(f"{BASE_URL}/api/marketplace/items?limit=200", timeout=20)
    assert r.status_code == 200
    ids = {it.get("id") for it in (r.json().get("items") or [])}
    assert sandbox_id not in ids, (
        f"Sandbox listing leaked to public marketplace: {sandbox_id}"
    )


def test_demo_user_sees_own_sandbox_in_marketplace(demo_account):
    """Owner-self-include: when the demo creator passes their bearer token to
    `/api/marketplace/items`, their own sandbox listings tail-merge into the
    response so they can experience the real product surface."""
    if not demo_account.get("password"):
        pytest.skip()
    token = _login(demo_account["email"], demo_account["password"])
    create_resp = requests.post(
        f"{BASE_URL}/api/listings",
        json=_demo_listing_payload(),
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert create_resp.status_code in (200, 201)
    sandbox_id = create_resp.json()["id"]

    r = requests.get(
        f"{BASE_URL}/api/marketplace/items?limit=200",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    assert r.status_code == 200
    items = r.json().get("items") or []
    ids = {it.get("id") for it in items}
    assert sandbox_id in ids, (
        f"Owner-self-include missing — demo user can't see their own sandbox "
        f"listing in marketplace feed. Got {len(items)} items."
    )
    matched = next(it for it in items if it.get("id") == sandbox_id)
    assert matched.get("is_demo_sandbox") is True


# ── 3. Demo metrics waterfall on analytics ──────────────────────────


@pytest.fixture(scope="function")
def fresh_demo_account(admin_token):
    """A FRESH demo user with zero listings/activity — used for analytics
    mock-data verification (the module-scoped `demo_account` has listings
    from earlier tests which may have generated activity counters)."""
    suffix = uuid.uuid4().hex[:6]
    payload = {
        "account_type":  "auctioneer",
        "company_name":  f"Pytest Fresh Demo {suffix}",
        "contact_email": f"fresh-iter223-{suffix}@example.com",
        "province":      "ON",
        "duration_days": 14,
        "notes":         "Fresh demo for analytics test",
    }
    r = requests.post(
        f"{BASE_URL}/api/admin/demo-accounts",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    if r.status_code not in (200, 201):
        pytest.skip(f"Fresh demo creation failed: {r.status_code}")
    b = r.json()
    return {
        "email":    b.get("email"),
        "password": b.get("temp_password") or b.get("password"),
        "user_id":  b.get("id") or b.get("user_id"),
    }


def test_analytics_seller_endpoint_injects_demo_metrics(fresh_demo_account):
    """Demo users with empty real data MUST receive a high-fidelity mock dataset."""
    if not fresh_demo_account.get("user_id"):
        pytest.skip("fresh demo account did not return user_id")
    r = requests.get(
        f"{BASE_URL}/api/analytics/seller/{fresh_demo_account['user_id']}?period=7d",
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("demo_metrics_injected") is True
    summary = body.get("summary") or {}
    assert summary.get("total_sales_volume") == 24_800.00
    assert summary.get("lots_successfully_closed") == 9
    assert summary.get("total_impressions") > 0
    assert summary.get("total_clicks") > 0
    # Charts must be non-empty
    charts = body.get("charts") or {}
    assert len(charts.get("impressions") or []) > 0
    assert len(charts.get("clicks") or []) > 0
    assert len(charts.get("bids") or []) > 0
    # Top performing listings must be 5 mock items
    top = body.get("top_listings") or []
    assert len(top) == 5


def test_analytics_normal_seller_does_not_get_demo_injection(admin_token):
    """Non-demo sellers MUST never see the demo metrics waterfall."""
    # Get the admin user's own id
    me = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    ).json()
    uid = me.get("id")
    if not uid:
        pytest.skip("admin user id not available")
    r = requests.get(f"{BASE_URL}/api/analytics/seller/{uid}?period=7d", timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert body.get("demo_metrics_injected") in (False, None)
    summary = body.get("summary") or {}
    assert summary.get("total_sales_volume") in (None, 0, 0.0)
