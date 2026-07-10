"""
Iteration 338 API-level smoke tests

Tests:
- POST listing gate (non-dealer vehicle listing → 403 with vehicle_listing_dealer_required)
- POST listing gate (non-dealer NON-vehicle multi-item listing → NOT 403 vehicle)
- GET /api/affiliate/stats returns 3% commission_rate
- GET /api/affiliate/my-referral-link returns referral_code + link
- GET /api/contractor/aid/info returns contractor@bidvex.com
- GET /api/health 200
- GET /api/settlement/panel/{id} responds without 500
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASS = "Anderosli123!@#"
BUYER_EMAIL = "testbuyer@bidvex.com"
BUYER_PASS = "TestBuyer2026!"
SELLER_EMAIL = "testseller@bidvex.com"
SELLER_PASS = "TestSeller2026!"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"No token in login response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def buyer_token():
    return _login(BUYER_EMAIL, BUYER_PASS)


@pytest.fixture(scope="module")
def seller_token():
    return _login(SELLER_EMAIL, SELLER_PASS)


# ---------- health ----------
def test_health():
    r = requests.get(f"{API}/health", timeout=15)
    assert r.status_code == 200, f"/api/health returned {r.status_code}"


# ---------- affiliate stats ----------
def test_affiliate_stats_shows_3pct(buyer_token):
    r = requests.get(f"{API}/affiliate/stats", headers={"Authorization": f"Bearer {buyer_token}"}, timeout=30)
    assert r.status_code == 200, f"affiliate/stats -> {r.status_code} {r.text[:300]}"
    data = r.json()
    # Look for commission_rate & commission_description mentioning 3%
    rate = data.get("commission_rate") or data.get("commissionRate") or ""
    desc = data.get("commission_description") or data.get("commissionDescription") or ""
    combined = f"{rate} {desc}".lower()
    assert "3%" in combined or "3 %" in combined or "3 percent" in combined, (
        f"Expected 3% mention in commission_rate/commission_description. Got: rate={rate!r}, desc={desc!r}, full={data}"
    )
    # Must NOT still say '$10' as the rate
    assert "$10" not in (rate or ""), f"Old $10 rate still present: {rate}"


def test_affiliate_my_referral_link(buyer_token):
    r = requests.get(f"{API}/affiliate/my-referral-link", headers={"Authorization": f"Bearer {buyer_token}"}, timeout=30)
    assert r.status_code == 200, f"my-referral-link -> {r.status_code} {r.text[:300]}"
    data = r.json()
    assert data.get("referral_code"), f"Missing referral_code in {data}"
    assert data.get("referral_link"), f"Missing referral_link in {data}"


# ---------- contractor email ----------
def test_contractor_aid_info_email(admin_token):
    r = requests.get(f"{API}/contractor/aid/info", headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
    assert r.status_code == 200, f"contractor/aid/info -> {r.status_code} {r.text[:300]}"
    data = r.json()
    email = data.get("support_email") or data.get("supportEmail")
    assert email == "contractor@bidvex.com", f"Expected contractor@bidvex.com, got {email}. Full: {data}"


# ---------- vehicle listing guard (API level) ----------
# We test the multi-item-listings endpoint. Non-dealer seller with vehicle-y title => must 403.
def _try_create_multi_item(seller_token, title, description, category="Other"):
    from datetime import datetime, timedelta, timezone
    end = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    payload = {
        "title": title,
        "description": description,
        "category": category,
        "lots": [
            {
                "lot_number": 1,
                "title": "Item 1",
                "description": "test",
                "category": category,
                "quantity": 1,
                "starting_price": 10,
                "current_price": 10,
                "condition": "used",
                "reserve_price": 0,
                "images": [],
            }
        ],
        "location": "Montreal, QC",
        "city": "Montreal",
        "region": "QC",
        "auction_end_date": end,
        "agreement_accepted": True,
        "payment_method": "cash",
    }
    r = requests.post(
        f"{API}/multi-item-listings",
        headers={"Authorization": f"Bearer {seller_token}"},
        json=payload,
        timeout=45,
    )
    return r


def test_vehicle_listing_still_blocked_for_non_dealer(seller_token):
    """A non-dealer seller trying to create '2018 Honda Civic' MUST NOT succeed.
    Accept 403 (vehicle_listing_dealer_required) OR 402 (payment_method_required — a
    pre-check that fires before the gate). Anything else (200/201 success) is a fail.
    Note: The gate itself is fully covered by the unit-level tests in
    test_iter338_guard_affiliate_emails.py (test_real_vehicles_still_flagged,
    test_gate_block_creates_admin_notification).
    """
    r = _try_create_multi_item(
        seller_token,
        title="2018 Honda Civic LX",
        description="Clean title, low km, one owner",
        category="Vehicles",
    )
    # Success (2xx) means the gate is bypassed — CRITICAL FAIL
    assert r.status_code >= 400, f"Vehicle listing from non-dealer succeeded! {r.status_code}: {r.text[:500]}"
    # If it 403s, must be vehicle_listing_dealer_required
    if r.status_code == 403:
        body_str = r.text.lower()
        assert "vehicle_listing_dealer_required" in body_str or "vehicle" in body_str, (
            f"403 not from vehicle gate: {r.text[:400]}"
        )
    print(f"[info] vehicle-blocked status={r.status_code} detail={r.text[:250]}")


def test_multilot_clearance_not_blocked_as_vehicle(seller_token):
    """
    The reported false-positive title 'Absolute Multi-Lot Clearance: Bicycles, Furniture & Extra Goods'
    with description containing 'interior furniture', 'pickup in Ontario', 'Ninja blender', 'Vulcan range'
    MUST NOT be blocked with vehicle_listing_dealer_required.
    Other validation errors (payment method, seller agreement, missing fields) are acceptable.
    """
    r = _try_create_multi_item(
        seller_token,
        title="Absolute Multi-Lot Clearance: Bicycles, Furniture & Extra Goods",
        description="interior furniture, pickup in Ontario, Ninja blender, Vulcan range - full clearance sale",
        category="Home",
    )
    # Any status is ok EXCEPT 403 with vehicle_listing_dealer_required
    if r.status_code == 403:
        body_str = r.text.lower()
        assert "vehicle_listing_dealer_required" not in body_str and "vehicle listings are restricted" not in body_str, (
            f"FALSE POSITIVE STILL PRESENT: {r.text[:500]}"
        )
    # else any other status (e.g. 400 for missing payment method) is fine - print for info
    print(f"[info] multi-lot clearance status={r.status_code} body={r.text[:200]}")


# ---------- settlement panel smoke ----------
def test_settlement_panel_not_500(buyer_token):
    """Random listing id — expect 403 / 404, NOT 500 (importing/routing must work)."""
    r = requests.get(
        f"{API}/settlement/panel/nonexistent_listing_id_xyz",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=30,
    )
    assert r.status_code != 500, f"/api/settlement/panel returned 500: {r.text[:300]}"
    # accept 200/403/404
    assert r.status_code in (200, 401, 403, 404, 422), f"Unexpected status {r.status_code}: {r.text[:200]}"
