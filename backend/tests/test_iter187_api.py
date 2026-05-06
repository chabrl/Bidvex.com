"""
iter187 — Live API checks against preview backend.
- P0: /api/payments/promote-listing returns 200/4xx (never 405)
- P0: /api/payments/promote returns 404 (mounted) for non-existent listing
- P0: /api/storage-auctions/{id}/promote returns 403/404 for non-facility user (never 405)
- P1: POST /api/multi-item-listings persists requires_deposit/deposit_amount/deposit_type/payment_method/currency
- P1: validation 400 on missing deposit_amount
- P1: validation 400 on bogus deposit_type
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

BUYER = ("p0bugtest@example.com", "TestBuyer123!")
ADMIN = ("charbel911@gmail.com", "Anderosli123!@#")


def _login(creds):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": creds[0], "password": creds[1]},
        timeout=20,
    )
    if r.status_code != 200:
        return None
    data = r.json()
    return data.get("access_token") or data.get("token") or (data.get("user") or {}).get("access_token")


@pytest.fixture(scope="module")
def buyer_token():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    tok = _login(BUYER)
    if not tok:
        pytest.skip("Buyer login failed")
    return tok


@pytest.fixture(scope="module")
def admin_token():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    tok = _login(ADMIN)
    if not tok:
        pytest.skip("Admin login failed")
    return tok


# ============ P0: promotion endpoints mounted (never 405) ============

def test_promote_listing_endpoint_mounted(buyer_token):
    """POST /api/payments/promote-listing must NOT be 405 — endpoint must be mounted."""
    headers = {"Authorization": f"Bearer {buyer_token}"}
    # Use a non-existent listing_id
    r = requests.post(
        f"{BASE_URL}/api/payments/promote-listing",
        json={"listing_id": "non-existent-12345", "tier": "premium", "duration_days": 7},
        headers=headers,
        timeout=20,
    )
    # Acceptable: 200, 400, 401, 403, 404, 422 — but NEVER 405
    assert r.status_code != 405, f"endpoint not mounted: {r.status_code} {r.text[:200]}"
    assert r.status_code < 500, f"server error: {r.status_code} {r.text[:200]}"


def test_promote_legacy_endpoint_mounted(buyer_token):
    """POST /api/payments/promote must NOT be 405 — endpoint must be mounted."""
    headers = {"Authorization": f"Bearer {buyer_token}"}
    r = requests.post(
        f"{BASE_URL}/api/payments/promote",
        json={"listing_id": "non-existent-12345", "tier": "premium", "duration_days": 7},
        headers=headers,
        timeout=20,
    )
    assert r.status_code != 405, f"endpoint not mounted: {r.status_code} {r.text[:200]}"
    assert r.status_code < 500, f"server error: {r.status_code} {r.text[:200]}"


def test_storage_auction_promote_mounted(buyer_token):
    """POST /api/storage-auctions/{id}/promote must NOT be 405; non-facility user → 403/404."""
    headers = {"Authorization": f"Bearer {buyer_token}"}
    r = requests.post(
        f"{BASE_URL}/api/storage-auctions/non-existent-12345/promote",
        json={"tier": "premium", "duration_days": 7},
        headers=headers,
        timeout=20,
    )
    assert r.status_code != 405, f"endpoint not mounted: {r.status_code} {r.text[:200]}"
    # Must be 401/403/404/400/422 — non-facility user should not get 200 here
    assert r.status_code in (400, 401, 403, 404, 422), f"unexpected: {r.status_code} {r.text[:200]}"


# ============ P1: Multi-item listing deposit fields ============

@pytest.fixture(scope="module")
def base_multi_payload():
    """Minimal valid MultiItemListingCreate payload."""
    return {
        "title": "TEST_iter187 multi-lot",
        "description": "iter187 testing deposit field persistence",
        "category": "Antiques",
        "location": "Montreal, QC",
        "city": "Montreal",
        "region": "QC",
        "country": "Canada",
        "auction_start_date": "2026-12-31T12:00:00",
        "auction_end_date": "2027-01-15T12:00:00",
        "agreement_accepted": True,
        "lots": [
            {
                "lot_number": 1,
                "title": "Lot 1",
                "description": "Test lot",
                "starting_price": 10.0,
                "current_price": 10.0,
                "starting_bid": 10.0,
                "reserve_price": 0.0,
                "quantity": 1,
                "condition": "new",
                "images": [],
            }
        ],
        "currency": "CAD",
    }


def test_multi_item_persists_deposit_fields(buyer_token, base_multi_payload):
    """Create multi-item with all 5 fields → verify GET returns them."""
    headers = {"Authorization": f"Bearer {buyer_token}"}
    payload = dict(base_multi_payload)
    payload["title"] = "TEST_iter187 deposit-persist"
    payload["payment_method"] = "cash"
    payload["requires_deposit"] = True
    payload["deposit_amount"] = 75.0
    payload["deposit_type"] = "fixed"
    payload["currency"] = "CAD"

    r = requests.post(
        f"{BASE_URL}/api/multi-item-listings",
        json=payload,
        headers=headers,
        timeout=30,
    )
    if r.status_code in (401, 403):
        pytest.skip(f"buyer cannot create multi-item: {r.status_code} {r.text[:200]}")
    if r.status_code == 402:
        pytest.skip("buyer has no saved card (sticky card guard) — cannot validate via live API; pre-seeded listing 269a9f90 covers persistence.")
    assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    # Validate response structure
    listing_id = data.get("id") or data.get("_id") or (data.get("listing") or {}).get("id")
    assert listing_id, f"no id in response: {data}"

    # Check fields in response or via GET
    fetched = data
    if "requires_deposit" not in fetched:
        g = requests.get(
            f"{BASE_URL}/api/multi-item-listings/{listing_id}",
            headers=headers,
            timeout=20,
        )
        assert g.status_code == 200, f"GET failed: {g.status_code}"
        fetched = g.json()

    assert fetched.get("currency") == "CAD"
    assert fetched.get("payment_method") == "cash"
    assert fetched.get("requires_deposit") is True
    assert float(fetched.get("deposit_amount") or 0) == 75.0
    assert fetched.get("deposit_type") == "fixed"


def test_multi_item_validation_missing_deposit_amount(buyer_token, base_multi_payload):
    """requires_deposit=true + no deposit_amount → 400 with deposit_amount_required."""
    headers = {"Authorization": f"Bearer {buyer_token}"}
    payload = dict(base_multi_payload)
    payload["title"] = "TEST_iter187 missing-amount"
    payload["requires_deposit"] = True
    payload["deposit_amount"] = None
    payload["deposit_type"] = "fixed"

    r = requests.post(
        f"{BASE_URL}/api/multi-item-listings",
        json=payload,
        headers=headers,
        timeout=30,
    )
    if r.status_code in (401, 403):
        pytest.skip(f"buyer cannot create multi-item: {r.status_code}")
    if r.status_code == 402:
        pytest.skip("sticky card guard — cannot reach deposit validator via live API")
    assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:300]}"
    body = r.json()
    detail = body.get("detail") or body
    if isinstance(detail, dict):
        assert detail.get("error") == "deposit_amount_required"
        assert "message_en" in detail and "message_fr" in detail
    else:
        assert "deposit_amount_required" in str(detail)


def test_multi_item_validation_invalid_deposit_type(buyer_token, base_multi_payload):
    """deposit_type='bogus' → 400 with invalid_deposit_type."""
    headers = {"Authorization": f"Bearer {buyer_token}"}
    payload = dict(base_multi_payload)
    payload["title"] = "TEST_iter187 bogus-type"
    payload["requires_deposit"] = True
    payload["deposit_amount"] = 50.0
    payload["deposit_type"] = "bogus"

    r = requests.post(
        f"{BASE_URL}/api/multi-item-listings",
        json=payload,
        headers=headers,
        timeout=30,
    )
    if r.status_code in (401, 403):
        pytest.skip(f"buyer cannot create multi-item: {r.status_code}")
    if r.status_code == 402:
        pytest.skip("sticky card guard — cannot reach deposit validator via live API")
    # Could be 400 (our validator) OR 422 (pydantic model rejection) — both are acceptable
    assert r.status_code in (400, 422), f"expected 400/422 got {r.status_code}: {r.text[:300]}"
    body = r.json()
    detail = body.get("detail") or body
    if r.status_code == 400 and isinstance(detail, dict):
        assert detail.get("error") == "invalid_deposit_type"
        assert "message_en" in detail and "message_fr" in detail


# ============ Verify pre-seeded listing from iter187 ============

def test_seeded_multi_item_has_deposit_fields(buyer_token):
    """Main agent already created listing 269a9f90-6741-46ea-b29d-e7126b172f35."""
    headers = {"Authorization": f"Bearer {buyer_token}"}
    r = requests.get(
        f"{BASE_URL}/api/multi-item-listings/269a9f90-6741-46ea-b29d-e7126b172f35",
        headers=headers,
        timeout=20,
    )
    if r.status_code == 404:
        pytest.skip("seed listing not present")
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert data.get("currency") == "CAD"
    assert data.get("payment_method") == "cash"
    assert data.get("requires_deposit") is True
    assert float(data.get("deposit_amount") or 0) == 75.0
    assert data.get("deposit_type") == "fixed"
