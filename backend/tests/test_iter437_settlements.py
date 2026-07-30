"""iter437 — Settlements module backend tests.

Verifies:
- GET /api/vehicles/dealer/pending-settlements auth-gate
- Response shape and 4 seeded settlements sum to $90,500
- Status buckets: pending=$57,500, paid=$33,000
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

DEALER_EMAIL = "testdealer@bidvex.com"
DEALER_PASSWORD = "TestDealer2026!"


@pytest.fixture(scope="module")
def dealer_token():
    r = requests.post(f"{API}/auth/login", json={"email": DEALER_EMAIL, "password": DEALER_PASSWORD}, timeout=60)
    assert r.status_code == 200, f"Dealer login failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in login response: {data}"
    return token


def test_unauthenticated_returns_401_or_403():
    r = requests.get(f"{API}/vehicles/dealer/pending-settlements", timeout=60)
    assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"


def test_pending_settlements_shape_and_sum(dealer_token):
    r = requests.get(
        f"{API}/vehicles/dealer/pending-settlements",
        headers={"Authorization": f"Bearer {dealer_token}"},
        timeout=60,
    )
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:400]}"
    body = r.json()
    assert "total" in body and "settlements" in body
    settlements = body["settlements"]
    assert isinstance(settlements, list)
    assert len(settlements) >= 4, f"Expected >=4 seeded settlements, got {len(settlements)}"

    # Shape check on first row
    keys = {"auction_id", "buyer_id", "seller_id", "hammer_price", "net_commission_amount",
            "settlement_status", "vehicle", "buyer"}
    first = settlements[0]
    missing = keys - set(first.keys())
    assert not missing, f"Missing keys on settlement: {missing}. Got: {list(first.keys())}"
    assert "year" in first["vehicle"] and "make" in first["vehicle"] and "model" in first["vehicle"]

    # Sum check
    total_hammer = sum(float(s.get("hammer_price") or 0) for s in settlements)
    # The 4 seeded settlements sum to 90,500
    assert total_hammer >= 90500, f"Hammer total {total_hammer} < 90500"


def test_seeded_status_breakdown(dealer_token):
    r = requests.get(
        f"{API}/vehicles/dealer/pending-settlements",
        headers={"Authorization": f"Bearer {dealer_token}"},
        timeout=60,
    )
    assert r.status_code == 200
    settlements = r.json()["settlements"]

    PENDING = {"FEE_PROCESSING", "FEE_PAID", "AWAITING_DEALER_CONFIRMATION"}
    PROCESSING = {"DEALER_CONFIRMED"}
    PAID = {"FULLY_SETTLED", "ADMIN_RESOLVED"}

    pending_sum = 0.0
    paid_sum = 0.0
    for s in settlements:
        status = s.get("settlement_status")
        price = float(s.get("hammer_price") or 0)
        if status in PAID:
            paid_sum += price
        elif status in PENDING or status in PROCESSING:
            pending_sum += price

    # Expected: pending=57500, paid=33000
    assert pending_sum == pytest.approx(57500, abs=1), f"Pending sum={pending_sum}"
    assert paid_sum == pytest.approx(33000, abs=1), f"Paid sum={paid_sum}"


def test_regression_my_listings_redirects():
    """iter432 stub — /vehicle-auctions/my-listings redirects to /vehicle-dashboard on the SPA.
    Backend route (if any) shouldn't 500."""
    r = requests.get(f"{API}/vehicles/my-listings", timeout=60, allow_redirects=False)
    # Endpoint may not exist (404) or return auth (401/403) — just should not 500
    assert r.status_code < 500, f"Backend errored on my-listings: {r.status_code}"
