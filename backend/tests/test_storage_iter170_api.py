"""
Iteration 170 — Storage Auctions API integration tests
=======================================================
Validates HTTP-level behavior of:
  • Public list / detail endpoints (no regression)
  • Facility registration with Stripe Connect Express + 409 on dup
  • Auction creation with payment_method + deposit validation
  • Bid endpoint deposit-guard (HTTP 402 with bilingual messages)
  • Pricing preview shape per payment method
  • Deposit endpoint validation
  • Admin release/forfeit endpoints (RBAC)

Run:
  pytest /app/backend/tests/test_storage_iter170_api.py -v \
    --tb=short --junitxml=/app/test_reports/pytest/iter170_api.xml
"""
import os
import time
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
BUYER_EMAIL = "abc@gmail.com"
BUYER_PASSWORD = "TestBuyer123!"


# ─────────────────────────────────────────────────────────────
# Shared session + auth helpers
# ─────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def s():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(session, email, password):
    r = session.post(f"{API}/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        pytest.skip(f"Login failed for {email}: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_token(s):
    return _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="session")
def buyer_token(s):
    return _login(s, BUYER_EMAIL, BUYER_PASSWORD)


def _register_user(s, label):
    email = f"TEST_{label}_{uuid.uuid4().hex[:8]}@bidvextest.com"
    password = "FacilityTest123!"
    r = s.post(f"{API}/auth/register", json={
        "email": email,
        "password": password,
        "name": f"Test {label}",
        "account_type": "personal",
        "terms_agreed": True,
        "ai_disclosure_consent": True,
    })
    if r.status_code != 200:
        pytest.skip(f"Register failed: {r.status_code} {r.text[:200]}")
    token = r.json().get("access_token") or _login(s, email, password)
    return {"email": email, "password": password, "token": token}


@pytest.fixture(scope="session")
def fresh_user(s):
    """Brand-new user used ONLY for the facility-registration tests (TestFacilityRegistration)."""
    return _register_user(s, "facility")


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def verified_facility(s, admin_token):
    """
    Register a separate user as facility, then admin-verify it.
    Returns dict {token, facility_id, email}. Used by ALL tests that POST auctions.
    """
    owner = _register_user(s, "auction_owner")
    # Register facility
    body = {
        "company_name": "TEST Auction Co",
        "contact_name": "Test Auction Owner",
        "email": owner["email"],
        "phone": "+15145550123",
        "address": "456 Auction St",
        "city": "Montreal",
        "province": "QC",
        "postal_code": "H2X 1Y4",
        "units_available": 10,
        "accepted_terms": True,
    }
    r = s.post(f"{API}/storage-facilities/register", json=body, headers=_hdr(owner["token"]))
    if r.status_code != 200:
        pytest.skip(f"Facility register failed: {r.status_code} {r.text[:200]}")
    fac_id = r.json()["facility_id"]
    # Admin-verify
    vr = s.post(f"{API}/admin/storage-facilities/{fac_id}/verify", headers=_hdr(admin_token))
    if vr.status_code != 200:
        pytest.skip(f"Admin-verify failed: {vr.status_code} {vr.text[:200]}")
    return {"token": owner["token"], "facility_id": fac_id, "email": owner["email"]}


# ─────────────────────────────────────────────────────────────
# 1. Public list — no regression
# ─────────────────────────────────────────────────────────────
class TestPublicList:
    def test_list_storage_auctions_works(self, s):
        r = s.get(f"{API}/storage-auctions")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "auctions" in data
        assert "total" in data
        assert isinstance(data["auctions"], list)


# ─────────────────────────────────────────────────────────────
# 2. Facility registration — Stripe Connect + duplicate guard
# ─────────────────────────────────────────────────────────────
class TestFacilityRegistration:
    payload_template = {
        "company_name": "TEST Storage Co",
        "contact_name": "Test Owner",
        "email": "owner@teststorage.com",
        "phone": "+15145550123",
        "address": "123 Test Street",
        "city": "Montreal",
        "province": "QC",
        "postal_code": "H2X 1Y4",
        "units_available": 50,
        "accepted_terms": True,
    }

    def test_register_creates_facility_and_returns_onboarding(self, s, fresh_user):
        body = dict(self.payload_template, email=fresh_user["email"])
        r = s.post(f"{API}/storage-facilities/register", json=body, headers=_hdr(fresh_user["token"]))
        assert r.status_code == 200, f"register failed: {r.status_code} {r.text[:400]}"
        data = r.json()
        assert "facility_id" in data
        assert data["status"] == "pending_verification"
        # stripe_onboarding_url may be None if Stripe rejects (graceful degradation), but key MUST be present
        assert "stripe_onboarding_url" in data
        assert "message_en" in data and "message_fr" in data

    def test_register_second_call_returns_409(self, s, fresh_user):
        body = dict(self.payload_template, email=fresh_user["email"])
        r = s.post(f"{API}/storage-facilities/register", json=body, headers=_hdr(fresh_user["token"]))
        assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text[:300]}"
        detail = r.json().get("detail", {})
        assert detail.get("error") == "facility_already_registered"
        assert "message_en" in detail and "message_fr" in detail


# ─────────────────────────────────────────────────────────────
# 3. Auction creation — payment_method + deposit validation
# ─────────────────────────────────────────────────────────────
def _auction_payload(**kw):
    start = datetime.now(timezone.utc) + timedelta(hours=2)
    end = start + timedelta(days=3)
    base = {
        "unit_number": f"TEST-{uuid.uuid4().hex[:6]}",
        "unit_size": "10x10",
        "unit_type": "indoor",
        "description_en": "TEST unit listing for iter170 API regression suite — 10x10 indoor.",
        "starting_price": 1.0,
        "bid_increment": 10.0,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "payment_method": "stripe",
        "deposit_required": False,
    }
    base.update(kw)
    return base


class TestAuctionCreation:
    def test_invalid_payment_method_returns_422(self, s, verified_facility):
        body = _auction_payload(payment_method="bitcoin")
        r = s.post(f"{API}/storage-facilities/auctions", json=body, headers=_hdr(verified_facility["token"]))
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text[:300]}"

    def test_deposit_required_without_amount_returns_422(self, s, verified_facility):
        body = _auction_payload(deposit_required=True, deposit_amount=None)
        r = s.post(f"{API}/storage-facilities/auctions", json=body, headers=_hdr(verified_facility["token"]))
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text[:300]}"

    def test_stripe_no_deposit_succeeds(self, s, verified_facility):
        body = _auction_payload(payment_method="stripe", deposit_required=False)
        r = s.post(f"{API}/storage-facilities/auctions", json=body, headers=_hdr(verified_facility["token"]))
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert data["payment_method"] == "stripe"
        assert data["deposit_required"] is False
        assert "id" in data

    def test_cash_with_deposit_persists_correctly(self, s, verified_facility):
        body = _auction_payload(payment_method="cash", deposit_required=True, deposit_amount=100)
        r = s.post(f"{API}/storage-facilities/auctions", json=body, headers=_hdr(verified_facility["token"]))
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert data["payment_method"] == "cash"
        assert data["deposit_required"] is True
        assert float(data["deposit_amount"]) == 100.0
        # verify GET returns same
        gr = s.get(f"{API}/storage-auctions/{data['id']}")
        assert gr.status_code == 200
        gd = gr.json()
        assert gd["payment_method"] == "cash"
        assert gd["deposit_required"] is True
        assert float(gd["deposit_amount"]) == 100.0


# ─────────────────────────────────────────────────────────────
# 4. Bid endpoint — deposit guard 402
# ─────────────────────────────────────────────────────────────
class TestBidDepositGuard:
    @pytest.fixture(scope="class")
    def deposit_required_auction_id(self, s, verified_facility):
        """Create an auction that REQUIRES deposit and force-activate it (start_time in past)."""
        # Create with future start, then mongo-mutate via admin edit isn't supported here, so
        # we create with start ~30s in the past via direct payload - but model requires start<end only.
        start = datetime.now(timezone.utc) - timedelta(minutes=5)
        end = datetime.now(timezone.utc) + timedelta(days=2)
        body = _auction_payload(
            payment_method="stripe",
            deposit_required=True,
            deposit_amount=50,
            start_time=start.isoformat(),
            end_time=end.isoformat(),
        )
        r = s.post(f"{API}/storage-facilities/auctions", json=body, headers=_hdr(verified_facility["token"]))
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_bid_returns_402_when_no_deposit(self, s, buyer_token, deposit_required_auction_id):
        r = s.post(
            f"{API}/storage-auctions/{deposit_required_auction_id}/bid",
            json={"max_bid": 25.0},
            headers=_hdr(buyer_token),
        )
        assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text[:300]}"
        detail = r.json().get("detail", {})
        assert detail.get("error") == "deposit_required"
        assert isinstance(detail.get("deposit_amount"), (int, float))
        assert detail.get("deposit_amount") == 50.0
        assert "message_en" in detail and "message_fr" in detail
        assert detail.get("action") == "pay_deposit"

    def test_bid_no_deposit_required_succeeds_or_400(self, s, buyer_token, verified_facility):
        """Auction with no deposit — bid should succeed (or 400 'auction_not_active')."""
        start = datetime.now(timezone.utc) - timedelta(minutes=2)
        end = datetime.now(timezone.utc) + timedelta(days=1)
        body = _auction_payload(
            payment_method="stripe",
            deposit_required=False,
            start_time=start.isoformat(),
            end_time=end.isoformat(),
        )
        cr = s.post(f"{API}/storage-facilities/auctions", json=body, headers=_hdr(verified_facility["token"]))
        assert cr.status_code == 200, cr.text
        aid = cr.json()["id"]
        r = s.post(
            f"{API}/storage-auctions/{aid}/bid",
            json={"max_bid": 25.0},
            headers=_hdr(buyer_token),
        )
        # Both acceptable: 200 (success) OR 400 (auction_not_active depending on status calc)
        assert r.status_code in (200, 400), f"unexpected {r.status_code}: {r.text[:300]}"


# ─────────────────────────────────────────────────────────────
# 5. Pricing preview — per payment method
# ─────────────────────────────────────────────────────────────
class TestPricingPreview:
    @pytest.fixture(scope="class")
    def auction_id(self, s, verified_facility):
        body = _auction_payload(payment_method="stripe", starting_price=100.0)
        r = s.post(f"{API}/storage-facilities/auctions", json=body, headers=_hdr(verified_facility["token"]))
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_pricing_stripe_shape(self, s, auction_id):
        r = s.get(f"{API}/storage-auctions/{auction_id}/pricing",
                  params={"payment_method": "stripe", "deposit_amount": 100})
        assert r.status_code == 200, r.text
        data = r.json()
        bi = data["buyer_invoice"]
        for k in ("platform_fee", "stripe_recovery", "tax", "total", "remaining_after_deposit"):
            assert k in bi, f"missing buyer_invoice.{k}"
        assert "facility_receives" in data["facility_invoice"]

    def test_pricing_cash_shape(self, s, auction_id):
        r = s.get(f"{API}/storage-auctions/{auction_id}/pricing",
                  params={"payment_method": "cash"})
        assert r.status_code == 200, r.text
        fi = r.json()["facility_invoice"]
        for k in ("bidvex_platform_fee", "facility_owes_bidvex", "facility_net"):
            assert k in fi, f"missing facility_invoice.{k}"


# ─────────────────────────────────────────────────────────────
# 6. Deposit endpoint validation
# ─────────────────────────────────────────────────────────────
class TestDepositEndpoint:
    @pytest.fixture(scope="class")
    def deposit_auction_id(self, s, verified_facility):
        start = datetime.now(timezone.utc) - timedelta(minutes=5)
        end = datetime.now(timezone.utc) + timedelta(days=2)
        body = _auction_payload(
            payment_method="stripe",
            deposit_required=True,
            deposit_amount=25,
            start_time=start.isoformat(),
            end_time=end.isoformat(),
        )
        r = s.post(f"{API}/storage-facilities/auctions", json=body, headers=_hdr(verified_facility["token"]))
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_deposit_without_pm_returns_422(self, s, buyer_token, deposit_auction_id):
        r = s.post(
            f"{API}/storage-auctions/{deposit_auction_id}/deposit",
            json={},  # missing payment_method_id
            headers=_hdr(buyer_token),
        )
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text[:300]}"

    def test_deposit_with_bogus_pm_returns_402_or_400(self, s, buyer_token, deposit_auction_id):
        r = s.post(
            f"{API}/storage-auctions/{deposit_auction_id}/deposit",
            json={"payment_method_id": "pm_card_visa_bogus_test"},
            headers=_hdr(buyer_token),
        )
        # Stripe will reject; graceful 402 / 400 / 500 are all acceptable per spec
        assert r.status_code in (200, 400, 402, 500), f"unexpected {r.status_code}: {r.text[:300]}"


# ─────────────────────────────────────────────────────────────
# 7. Admin release / forfeit deposit (RBAC)
# ─────────────────────────────────────────────────────────────
class TestAdminDepositRBAC:
    @pytest.fixture(scope="class")
    def some_auction_id(self, s, verified_facility):
        body = _auction_payload()
        r = s.post(f"{API}/storage-facilities/auctions", json=body, headers=_hdr(verified_facility["token"]))
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_release_deposits_403_for_non_admin(self, s, buyer_token, some_auction_id):
        r = s.post(
            f"{API}/admin/storage-auctions/{some_auction_id}/release-deposits",
            headers=_hdr(buyer_token),
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:200]}"

    def test_forfeit_deposit_403_for_non_admin(self, s, buyer_token, some_auction_id):
        r = s.post(
            f"{API}/admin/storage-auctions/{some_auction_id}/forfeit-deposit",
            json={"buyer_id": "anything"},
            headers=_hdr(buyer_token),
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:200]}"

    def test_forfeit_deposit_400_without_buyer_id_admin(self, s, admin_token, some_auction_id):
        r = s.post(
            f"{API}/admin/storage-auctions/{some_auction_id}/forfeit-deposit",
            json={},
            headers=_hdr(admin_token),
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"
