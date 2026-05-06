"""Iter 183 — Lot numbering, Down Payments HTTP layer, Checkout-success seller_contact, scheduler cron."""
import os, requests, pytest, sys
sys.path.insert(0, "/app/backend")

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN = {"email": "charbel911@gmail.com", "password": "Anderosli123!@#"}
BUYER = {"email": "p0bugtest@example.com", "password": "TestBuyer123!"}

def _login(creds):
    r = requests.post(f"{BASE}/api/auth/login", json=creds, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Login failed for {creds['email']}: {r.status_code} {r.text[:120]}")
    return r.json().get("access_token") or r.json().get("token")

@pytest.fixture(scope="module")
def admin_token(): return _login(ADMIN)
@pytest.fixture(scope="module")
def buyer_token(): return _login(BUYER)

# ---------- Lot numbering (service-level, since multi_item_listings collection empty) ----------
def test_lot_numbering_service_overrides_input_and_caps_at_500():
    from services.listings_service import build_lots_with_end_time, MAX_LOTS_PER_AUCTION
    from datetime import datetime, timezone
    class Lot:
        def __init__(self, n=99): self.lot_number = n; self.title = "x"
        def model_dump(self): return {"lot_number": self.lot_number, "title": self.title}
    end = datetime(2030,1,1, tzinfo=timezone.utc)
    out = build_lots_with_end_time([Lot(n=999) for _ in range(5)], end)
    assert [l["lot_number"] for l in out] == [1,2,3,4,5], "lot_number must be auto-assigned 1..N"
    assert MAX_LOTS_PER_AUCTION == 500
    with pytest.raises(ValueError, match="Maximum 500 lots"):
        build_lots_with_end_time([Lot() for _ in range(501)], end)

# ---------- Down Payments HTTP layer ----------
def test_dp_me_no_auth_returns_401():
    r = requests.get(f"{BASE}/api/down-payments/me", timeout=20)
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text[:100]}"

def test_dp_me_buyer_returns_200_empty(buyer_token):
    r = requests.get(f"{BASE}/api/down-payments/me",
                     headers={"Authorization": f"Bearer {buyer_token}"}, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "items" in j and "count" in j
    assert isinstance(j["items"], list)
    assert j["count"] == len(j["items"])

def test_dp_by_auction_no_auth_returns_401():
    r = requests.get(f"{BASE}/api/down-payments/some-fake-auction-id", timeout=20)
    assert r.status_code in (401, 403)

def test_dp_by_auction_unknown_returns_404(buyer_token):
    r = requests.get(f"{BASE}/api/down-payments/nonexistent-id-xyz",
                     headers={"Authorization": f"Bearer {buyer_token}"}, timeout=20)
    assert r.status_code == 404

# ---------- Down-payment math (service-level, manual-verified per main agent) ----------
def test_dp_amount_math():
    from services.down_payment_service import _calculate_down_payment
    assert _calculate_down_payment("storage", 999) == 50.0
    assert _calculate_down_payment("storage", 1) == 50.0
    assert _calculate_down_payment("vehicle", 1000) == 100.0
    assert _calculate_down_payment("vehicle", 12345.67) == round(12345.67 * 0.10, 2)

# ---------- Scheduler cron registration ----------
def test_scheduler_has_expire_overdue_down_payments_job(admin_token):
    r = requests.get(f"{BASE}/api/admin/scheduler/status",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    body = str(j).lower()
    assert "expire_overdue_down_payments" in body or "down_payment" in body, \
        f"down-payment cron not registered: {body[:300]}"

# ---------- Checkout-success enrichment (the BUG) ----------
def test_checkout_status_does_not_500_with_invalid_session():
    """Even an invalid session must return 4xx, not 500."""
    r = requests.get(f"{BASE}/api/payments/status/cs_test_invalid_xyz", timeout=20)
    # Stripe returns 400 from the StripeError handler — NOT 500
    assert r.status_code in (400, 404), f"unexpected status {r.status_code}: {r.text[:200]}"

def test_checkout_status_db_variable_bug_in_source():
    """Read the route source — `db` must be initialised before use."""
    src = open("/app/backend/routes/payments.py").read()
    # Locate the get_checkout_status function block
    start = src.index("async def get_checkout_status(")
    end = src.index("@payments_router", start + 10)
    fn = src[start:end]
    assert "db = get_db()" in fn, (
        "BUG: get_checkout_status references `db.payment_transactions` but never "
        "calls `db = get_db()`. The NameError is silently swallowed by the bare "
        "`except Exception: pass`, so seller_contact is NEVER surfaced."
    )
