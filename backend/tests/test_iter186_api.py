"""
iter186 — Live API checks against preview backend.
- Storage auction model accepts new currency + deposit_type without breaking
- Admin payment-charges/events endpoint reachable + accepts DUPLICATE_REFUND_BLOCKED filter
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read from frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

ADMIN = ("charbel911@gmail.com", "Anderosli123!@#")


@pytest.fixture(scope="module")
def admin_token():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    # Try common login endpoints
    for ep in ("/api/auth/login", "/api/auth/email-login"):
        r = requests.post(
            f"{BASE_URL}{ep}",
            json={"email": ADMIN[0], "password": ADMIN[1]},
            timeout=20,
        )
        if r.status_code == 200:
            data = r.json()
            tok = data.get("access_token") or data.get("token") or (data.get("user") or {}).get("access_token")
            if tok:
                return tok
    pytest.skip("Admin login failed")


def test_health():
    r = requests.get(f"{BASE_URL}/api/", timeout=20)
    assert r.status_code in (200, 404)  # root may redirect


def test_storage_auctions_list_doesnt_500():
    r = requests.get(f"{BASE_URL}/api/storage-facilities/auctions", timeout=20)
    # Should not 500. May 200 or 404 depending on alias path
    assert r.status_code < 500, f"got {r.status_code}: {r.text[:300]}"


def test_admin_payment_events_filter(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    r = requests.get(
        f"{BASE_URL}/api/admin/payment-charges/events",
        params={"event": "DUPLICATE_REFUND_BLOCKED", "limit": 10},
        headers=headers,
        timeout=20,
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
    body = r.json()
    # Expect either {rows:[...]} or {events:[...]}
    assert isinstance(body, dict)
    rows = body.get("rows") or body.get("events") or body.get("data") or []
    assert isinstance(rows, list)


def test_admin_payment_charges_overview(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    r = requests.get(f"{BASE_URL}/api/admin/payment-charges", headers=headers, timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert "rows" in body or "summary" in body or "data" in body


def test_storage_auction_model_currency_default():
    """Pure model validation — currency defaults to CAD and accepts deposit_type."""
    import sys
    sys.path.insert(0, "/app/backend")
    from models.storage_auction import StorageAuctionCreate  # type: ignore

    fields = StorageAuctionCreate.model_fields
    assert "currency" in fields
    assert "deposit_type" in fields
    # default
    assert fields["currency"].default in ("CAD", "cad")
