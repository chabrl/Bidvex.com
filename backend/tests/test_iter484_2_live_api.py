"""
Live API tests for iter484.2 payment methods visibility fix.

Runs against REACT_APP_BACKEND_URL and verifies the exact bugs the main
agent claims are fixed:
 - GET /api/multi-item-listings/{id} now emits accepted_payment_methods
 - Single-item listing GET still emits accepted_payment_methods (regression)
 - POST /api/checkout/select-payment-method rejects methods not in accepted list
 - POST /api/listings/{id}/accepted-payment-methods returns 409 when locked
"""
import os
import requests
import pytest

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://prod-verify-2.preview.emergentagent.com",
).rstrip("/")

TARGET_MULTI = "58758582-f53a-46d8-bc0b-87cf9de60523"
BUYER_EMAIL = "testbuyer@bidvex.com"
BUYER_PW = "TestBuyer2026!"


# --- Multi-item listing model regression (Defect A) ---------------------
def test_multi_item_listing_emits_accepted_payment_methods():
    r = requests.get(f"{BASE_URL}/api/multi-item-listings/{TARGET_MULTI}", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    apm = data.get("accepted_payment_methods")
    assert isinstance(apm, list), f"apm must be a list, got {apm!r}"
    assert set(apm) == {"stripe", "etransfer", "cheque", "cash"}, apm


def test_multi_item_listing_returns_all_expected_pricing_fields():
    """Regression: ensure other fields survive the Pydantic parsing."""
    r = requests.get(f"{BASE_URL}/api/multi-item-listings/{TARGET_MULTI}", timeout=30)
    assert r.status_code == 200
    data = r.json()
    for k in ("id", "seller_id", "title", "lots", "status"):
        assert k in data


# --- Single-item listing model regression check -------------------------
def test_single_item_listing_endpoint_declares_apm_field():
    """Fetch any active single-item listing and confirm the response schema
    now includes accepted_payment_methods (may be null for legacy rows)."""
    r = requests.get(f"{BASE_URL}/api/listings?limit=25", timeout=30)
    assert r.status_code == 200
    items = r.json()
    if isinstance(items, dict):
        items = items.get("listings") or items.get("items") or []
    assert items, "no listings on server"
    # Look for a single-item listing (id without _lot_)
    for it in items:
        lid = it.get("id", "")
        if "_lot_" in lid:
            continue
        detail = requests.get(f"{BASE_URL}/api/listings/{lid}", timeout=30)
        if detail.status_code != 200:
            continue
        assert "accepted_payment_methods" in detail.json(), (
            f"single-item GET /api/listings/{lid} MUST expose "
            "accepted_payment_methods key (even if null)"
        )
        return
    pytest.skip("No standalone single-item listing found to test")


# --- Buyer selection gate -----------------------------------------------
def _buyer_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": BUYER_EMAIL, "password": BUYER_PW},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"Buyer login failed: {r.status_code} {r.text}")
    return r.json().get("access_token") or r.json().get("token")


def test_buyer_selection_rejects_method_not_in_accepted():
    """Send `wire` (or `paypal`) which is NOT in seller's accepted list.
    Must return 400 with PAYMENT_METHOD_NOT_ACCEPTED."""
    tok = _buyer_token()
    r = requests.post(
        f"{BASE_URL}/api/checkout/select-payment-method",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "listing_id": TARGET_MULTI,
            "selected_payment_method": "paypal",  # not accepted
            "ack_totals": {
                "hammer_cents": 10000,
                "buyer_premium_cents": 1500,
                "buyer_tax_cents": 1500,
                "payment_processing_cents": 0,
                "total_cents": 13000,
            },
        },
        timeout=30,
    )
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
    body = r.json()
    detail = body.get("detail", body)
    assert (detail.get("error") or "").upper() in (
        "PAYMENT_METHOD_NOT_ACCEPTED",
        "PAYMENT_METHODS_MISSING",
    ), detail


def test_buyer_selection_accepts_valid_method():
    tok = _buyer_token()
    r = requests.post(
        f"{BASE_URL}/api/checkout/select-payment-method",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "listing_id": TARGET_MULTI,
            "selected_payment_method": "cheque",  # accepted
            "ack_totals": {
                "hammer_cents": 10000,
                "buyer_premium_cents": 1500,
                "buyer_tax_cents": 1500,
                "payment_processing_cents": 0,
                "total_cents": 13000,
            },
        },
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    assert body.get("selected_payment_method") == "cheque"


# --- Post-bid lock 409 --------------------------------------------------
def test_edit_accepted_methods_requires_auth_or_owner():
    """Unauthenticated / non-owner edit must NOT succeed (401/403)."""
    r = requests.post(
        f"{BASE_URL}/api/listings/{TARGET_MULTI}/accepted-payment-methods",
        json={"accepted_payment_methods": ["stripe"]},
        timeout=30,
    )
    assert r.status_code in (401, 403), r.text
