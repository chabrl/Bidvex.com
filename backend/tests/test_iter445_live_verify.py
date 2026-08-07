"""iter445 live verification against the preview URL — verifies BP=5% enforced end-to-end."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PW = "Anderosli123!@#"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# ---- BE — fee calculator returns 5% for storage across all payment methods ----
@pytest.mark.parametrize("pm", ["stripe", "cash", "e_transfer"])
@pytest.mark.parametrize("btier", ["standard", "premium", "vip_elite"])
def test_fee_calc_storage_5pct(admin_session, pm, btier):
    params = {
        "hammer_price": 100.0,
        "auction_type": "storage",
        "seller_account_type": "storage_facility",
        "payment_method": pm,
        "buyer_tier": btier,
        "buyer_province": "QC",
        "seller_province": "QC",
    }
    r = admin_session.get(f"{BASE_URL}/api/fees/v2/preview", params=params, timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    data = r.json()
    # Search for rate / amount at any depth
    def find(d, key):
        if isinstance(d, dict):
            if key in d:
                return d[key]
            for v in d.values():
                got = find(v, key)
                if got is not None:
                    return got
        return None
    bp_rate = find(data, "buyer_premium_rate")
    bp_amt = find(data, "buyer_premium") or find(data, "buyer_premium_amount")
    sc = find(data, "seller_commission")
    sp = find(data, "seller_payout")
    print(f"[{pm}/{btier}] rate={bp_rate} amt={bp_amt} sc={sc} sp={sp}")
    assert float(bp_rate) in (0.05, 5.0, 5), f"expected 5%, got {bp_rate}"
    assert round(float(bp_amt), 2) == 5.00, f"expected $5, got {bp_amt}"
    if sc is not None:
        assert round(float(sc), 2) == 0.0
    if sp is not None:
        assert round(float(sp), 2) == 100.0


# ---- BE — POST /api/listings storage_locker with BP override → dropped ----
def test_create_storage_listing_drops_bp_override(admin_session):
    payload = {
        "title": "TEST_iter445_storage_bp_lock",
        "description": "iter445 live verify",
        "category": "storage_locker",
        "listing_type": "storage_locker",
        "starting_price": 50.0,
        "reserve_price": 50.0,
        "condition": "used",
        "location": "Montreal",
        "city": "Montreal",
        "region": "QC",
        "province": "QC",
        "postal_code": "H2X 1Y4",
        "country": "CA",
        "buyers_premium_rate": 0.15,
        "auction_end_time": "2027-01-01T00:00:00Z",
        "auction_end": "2027-01-01T00:00:00Z",
        "auction_end_date": "2027-01-01T00:00:00Z",
        "auction_duration_days": 7,
    }
    r = admin_session.post(f"{BASE_URL}/api/listings", json=payload, timeout=30)
    assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text[:300]}"
    listing = r.json()
    lid = listing.get("id") or listing.get("_id") or listing.get("listing_id")
    assert lid, f"no id in response: {listing}"
    # GET back
    g = admin_session.get(f"{BASE_URL}/api/listings/{lid}", timeout=30)
    assert g.status_code == 200
    body = g.json()
    listing_obj = body.get("listing", body)
    cbpr = listing_obj.get("custom_buyer_premium_rate")
    print(f"custom_buyer_premium_rate on created storage listing = {cbpr!r}")
    assert cbpr in (None, 0, 0.0), f"expected null override, got {cbpr}"

    # UPDATE — try again
    u = admin_session.put(f"{BASE_URL}/api/listings/{lid}", json={"buyers_premium_rate": 0.20}, timeout=30)
    assert u.status_code in (200, 201, 204), f"update failed: {u.status_code} {u.text[:300]}"
    g2 = admin_session.get(f"{BASE_URL}/api/listings/{lid}", timeout=30)
    lo2 = g2.json().get("listing", g2.json())
    assert lo2.get("custom_buyer_premium_rate") in (None, 0, 0.0)

    # fee-breakdown must be 5%
    fb = admin_session.get(f"{BASE_URL}/api/checkout/fee-breakdown?listing_id={lid}", timeout=30)
    if fb.status_code == 200:
        fbd = fb.json()
        bp_rate = fbd.get("buyer_premium_rate") or (fbd.get("fees") or {}).get("buyer_premium_rate")
        print(f"fee-breakdown BP rate={bp_rate}")
        assert float(bp_rate) in (0.05, 5.0)
    else:
        print(f"fee-breakdown returned {fb.status_code}: {fb.text[:200]}")

    # cleanup — best-effort
    admin_session.delete(f"{BASE_URL}/api/listings/{lid}", timeout=15)
