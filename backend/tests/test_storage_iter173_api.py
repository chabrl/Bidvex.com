"""
Iteration 173 — Final polish sprint backend tests.

Covers:
  1. GET /api/storage-auctions/{id}/pickup-qr — PNG for authorized / 404 / 403
  2. GET /api/storage-promotion-tiers (public)
  3. POST /api/storage-auctions/{id}/promote — requires verified facility
  4. POST /api/admin/storage-auctions?facility_id=X — admin-only create
  5. GET  /api/admin/storage-auctions — admin list
  6. POST /api/deposits/confirm — 401/404/400 guardrails
  7. Pydantic V2 migration — ValidationError on invalid payment_method and
     on deposit_required=True with deposit_amount<=0
  8. Regression — GET /api/storage-auctions/stats/public still returns shape

Uses REACT_APP_BACKEND_URL from frontend/.env via env loader.
"""
import os
import sys
import pytest
import requests
from pathlib import Path
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load REACT_APP_BACKEND_URL from frontend/.env
_FE_ENV = Path(__file__).resolve().parents[2] / "frontend" / ".env"
if _FE_ENV.exists():
    for line in _FE_ENV.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            os.environ["REACT_APP_BACKEND_URL"] = line.split("=", 1)[1].strip()

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASS = "Anderosli123!@#"
BUYER_EMAIL = "abc@gmail.com"
BUYER_PASS = "TestBuyer123!"


# ───── Fixtures ─────
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def buyer_token():
    r = requests.post(f"{API}/auth/login", json={"email": BUYER_EMAIL, "password": BUYER_PASS}, timeout=20)
    assert r.status_code == 200, f"buyer login failed: {r.status_code} {r.text[:200]}"
    return r.json().get("token") or r.json().get("access_token")


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


# ─────────────────────────────────────────────────────────────
# 1. PICKUP-QR endpoint
# ─────────────────────────────────────────────────────────────
class TestPickupQr:
    def test_pickup_qr_unauth_401(self):
        r = requests.get(f"{API}/storage-auctions/nonexistent-id/pickup-qr", timeout=10)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_pickup_qr_unknown_auction_404(self, admin_token):
        r = requests.get(f"{API}/storage-auctions/does-not-exist-xyz/pickup-qr",
                         headers=_hdr(admin_token), timeout=10)
        assert r.status_code == 404

    def test_pickup_qr_returns_png_for_admin_on_sold(self, admin_token):
        # Find a sold auction with a pickup_code
        r = requests.get(f"{API}/admin/storage-auctions", headers=_hdr(admin_token), timeout=20)
        assert r.status_code == 200
        payload = r.json()
        auctions = payload.get("auctions") if isinstance(payload, dict) else payload
        sold = [a for a in (auctions or []) if a.get("pickup_code")]
        if not sold:
            pytest.skip("No auction with pickup_code in dataset — cannot test PNG return path")
        a = sold[0]
        r2 = requests.get(f"{API}/storage-auctions/{a['id']}/pickup-qr",
                          headers=_hdr(admin_token), timeout=15)
        assert r2.status_code == 200, f"expected 200, got {r2.status_code} {r2.text[:200]}"
        assert r2.headers.get("content-type", "").startswith("image/png")
        assert r2.content[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic
        assert r2.headers.get("X-Pickup-Code") == a["pickup_code"]

    def test_pickup_qr_non_authorized_403(self, buyer_token, admin_token):
        # Any auction with pickup_code that buyer did NOT win
        r = requests.get(f"{API}/admin/storage-auctions", headers=_hdr(admin_token), timeout=20)
        payload = r.json()
        auctions = payload.get("auctions") if isinstance(payload, dict) else payload
        # Get buyer id
        me = requests.get(f"{API}/auth/me", headers=_hdr(buyer_token), timeout=10)
        if me.status_code != 200:
            pytest.skip("cannot resolve buyer id")
        buyer_id = me.json().get("id") or me.json().get("user", {}).get("id")
        candidates = [a for a in (auctions or [])
                      if a.get("pickup_code") and a.get("winning_bidder_id") != buyer_id]
        if not candidates:
            pytest.skip("No auction with pickup_code not won by buyer")
        r2 = requests.get(f"{API}/storage-auctions/{candidates[0]['id']}/pickup-qr",
                          headers=_hdr(buyer_token), timeout=10)
        assert r2.status_code == 403


# ─────────────────────────────────────────────────────────────
# 2+3. Promotion endpoints
# ─────────────────────────────────────────────────────────────
class TestPromotion:
    def test_tiers_public(self):
        r = requests.get(f"{API}/storage-promotion-tiers", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "tiers" in body
        assert isinstance(body["tiers"], dict)
        # Expect 3 tiers: basic / featured / premium (per spec)
        tiers = body["tiers"]
        assert len(tiers) >= 3

    def test_promote_unauth_401(self):
        r = requests.post(f"{API}/storage-auctions/any-id/promote",
                          json={"tier": "basic"}, timeout=10)
        assert r.status_code in (401, 403)

    def test_promote_buyer_forbidden(self, buyer_token):
        r = requests.post(f"{API}/storage-auctions/any-id/promote",
                          json={"tier": "basic"},
                          headers=_hdr(buyer_token), timeout=10)
        # Buyer is not a verified facility → 403 (or 401 depending on dependency order)
        assert r.status_code in (401, 403)


# ─────────────────────────────────────────────────────────────
# 4+5. Admin storage auction listing + create
# ─────────────────────────────────────────────────────────────
class TestAdminStorageAuctions:
    def test_admin_list(self, admin_token):
        r = requests.get(f"{API}/admin/storage-auctions", headers=_hdr(admin_token), timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, (list, dict))

    def test_admin_list_buyer_forbidden(self, buyer_token):
        r = requests.get(f"{API}/admin/storage-auctions", headers=_hdr(buyer_token), timeout=10)
        assert r.status_code in (401, 403)

    def test_admin_create_requires_facility_id(self, admin_token):
        # Missing facility_id query param → 422 (fastapi) or 400
        payload = {
            "unit_number": "TEST_ITER173_A",
            "unit_size": "10x10",
            "unit_type": "indoor",
            "description_en": "Test unit created by iter173 backend test and will be cancelled.",
            "starting_price": 1,
            "start_time": "2099-04-01T00:00:00Z",
            "end_time": "2099-04-08T00:00:00Z",
            "payment_method": "stripe",
            "deposit_required": False,
        }
        r = requests.post(f"{API}/admin/storage-auctions", json=payload,
                          headers=_hdr(admin_token), timeout=15)
        assert r.status_code in (400, 422)

    def test_admin_create_unknown_facility_404(self, admin_token):
        payload = {
            "unit_number": "TEST_ITER173_B",
            "unit_size": "10x10",
            "unit_type": "indoor",
            "description_en": "Test unit — unknown facility should 404 cleanly.",
            "starting_price": 1,
            "start_time": "2099-04-01T00:00:00Z",
            "end_time": "2099-04-08T00:00:00Z",
            "payment_method": "stripe",
            "deposit_required": False,
        }
        r = requests.post(f"{API}/admin/storage-auctions?facility_id=does-not-exist",
                          json=payload, headers=_hdr(admin_token), timeout=15)
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────
# 6. POST /deposits/confirm
# ─────────────────────────────────────────────────────────────
class TestDepositConfirm:
    def test_unauth_401(self):
        r = requests.post(f"{API}/deposits/confirm",
                          json={"deposit_id": "x", "payment_intent_id": "pi_x"},
                          timeout=10)
        assert r.status_code in (401, 403)

    def test_unknown_deposit_404(self, buyer_token):
        r = requests.post(f"{API}/deposits/confirm",
                          json={"deposit_id": "does-not-exist-xyz",
                                "payment_intent_id": "pi_whatever"},
                          headers=_hdr(buyer_token), timeout=10)
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────
# 7. Pydantic V2 — StorageAuctionCreate validators
# ─────────────────────────────────────────────────────────────
class TestPydanticV2Validators:
    def _good(self, **kw):
        base = {
            "unit_number": "A-1",
            "unit_size": "10x10",
            "unit_type": "indoor",
            "description_en": "A reasonably long description of the unit.",
            "starting_price": 1,
            "start_time": "2099-04-01T00:00:00Z",
            "end_time": "2099-04-08T00:00:00Z",
            "payment_method": "stripe",
            "deposit_required": False,
        }
        base.update(kw)
        return base

    def test_invalid_payment_method_raises(self):
        from models.storage_auction import StorageAuctionCreate
        with pytest.raises(ValidationError):
            StorageAuctionCreate(**self._good(payment_method="bitcoin"))

    def test_deposit_required_zero_amount_raises(self):
        from models.storage_auction import StorageAuctionCreate
        with pytest.raises(ValidationError):
            StorageAuctionCreate(**self._good(deposit_required=True, deposit_amount=0))

    def test_deposit_required_none_amount_raises(self):
        from models.storage_auction import StorageAuctionCreate
        with pytest.raises(ValidationError):
            StorageAuctionCreate(**self._good(deposit_required=True, deposit_amount=None))

    def test_valid_payload(self):
        from models.storage_auction import StorageAuctionCreate
        m = StorageAuctionCreate(**self._good(deposit_required=True, deposit_amount=100))
        assert m.payment_method == "stripe"
        assert m.deposit_amount == 100

    def test_no_v1_validator_decorator_used(self):
        """Assert migration to V2: @field_validator / @model_validator only."""
        import models.storage_auction as mod
        src = Path(mod.__file__).read_text()
        # Should use V2 decorators
        assert "@field_validator" in src or "@model_validator" in src
        # Should NOT use the bare V1 @validator decorator
        lines = [ln.strip() for ln in src.splitlines() if ln.strip().startswith("@validator(")]
        assert not lines, f"Found V1 @validator decorators: {lines}"


# ─────────────────────────────────────────────────────────────
# 8. Regression — stats shape
# ─────────────────────────────────────────────────────────────
class TestPublicStats:
    def test_stats_shape(self):
        r = requests.get(f"{API}/storage-auctions/stats/public", timeout=15)
        assert r.status_code == 200
        body = r.json()
        # Expected 4 stats (per previous iters)
        assert isinstance(body, dict)
        # Common keys (any 4 numeric stats acceptable)
        keys = set(body.keys())
        # Ensure at least 4 numeric fields returned
        numeric_fields = [k for k, v in body.items() if isinstance(v, (int, float))]
        assert len(numeric_fields) >= 4, f"Expected ≥4 numeric stats, got {body}"
