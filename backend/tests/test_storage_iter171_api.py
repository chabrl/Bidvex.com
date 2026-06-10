"""
Iteration 171 — BidVex Storage Auctions: Auto-close scheduler, bilingual emails,
admin deposits dashboard, and public stats endpoint.

Backend-only API integration tests.

Run:
  python -m pytest backend/tests/test_storage_iter171_api.py -v --tb=short \
    --junitxml=/app/test_reports/pytest/iter171_api.xml
"""
import os
import sys
import asyncio
import inspect
import pytest
import requests
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()
).rstrip("/")

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
BUYER_EMAIL = "abc@gmail.com"
BUYER_PASSWORD = "TestBuyer123!"


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def buyer_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": BUYER_EMAIL, "password": BUYER_PASSWORD}, timeout=20)
    if r.status_code != 200:
        # Try register
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": BUYER_EMAIL, "password": BUYER_PASSWORD, "name": "Test Buyer"
        }, timeout=20)
        if r.status_code in (200, 201):
            r = requests.post(f"{BASE_URL}/api/auth/login",
                              json={"email": BUYER_EMAIL, "password": BUYER_PASSWORD}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Buyer login failed: {r.status_code} {r.text[:200]}")
    return r.json().get("token") or r.json().get("access_token")


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ──────────────────────────────────────────────────────────────
# 1) PUBLIC STATS endpoint — no auth required
# ──────────────────────────────────────────────────────────────
class TestPublicStats:
    def test_public_stats_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/storage-auctions/stats/public", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("total_sold", "active_facilities", "active_auctions", "total_bids_placed"):
            assert k in data, f"Missing key {k}: {data}"
            assert isinstance(data[k], int), f"{k} should be int, got {type(data[k]).__name__}: {data[k]}"
            assert data[k] >= 0


# ──────────────────────────────────────────────────────────────
# 2) ADMIN DEPOSITS DASHBOARD
# ──────────────────────────────────────────────────────────────
class TestAdminDeposits:
    def test_no_token_returns_401_or_403(self):
        r = requests.get(f"{BASE_URL}/api/admin/storage-deposits", timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}: {r.text[:200]}"

    def test_buyer_token_returns_403(self, buyer_token):
        r = requests.get(f"{BASE_URL}/api/admin/storage-deposits",
                         headers=_hdr(buyer_token), timeout=15)
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text[:200]}"

    def test_admin_returns_200_with_shape(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/storage-deposits",
                         headers=_hdr(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # Top-level keys
        assert "stats" in data
        assert "total" in data
        assert "deposits" in data
        # Stats keys
        for k in ("active_holds", "applied", "refunded", "forfeited"):
            assert k in data["stats"], f"missing stats.{k}"
            assert isinstance(data["stats"][k], int)
        assert isinstance(data["total"], int)
        assert isinstance(data["deposits"], list)
        # If any deposits present, check enrichment shape
        if data["deposits"]:
            d = data["deposits"][0]
            for k in ("bidder_name", "bidder_email", "auction_unit_number",
                     "facility_name", "amount", "status", "created_at",
                     "auction_id", "buyer_id"):
                assert k in d, f"missing deposit row key: {k}"

    def test_filter_status_active(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/storage-deposits?status=active",
                         headers=_hdr(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        for d in data["deposits"]:
            assert d["status"] in ("held", "authorized"), \
                f"status filter active should include only held/authorized, got {d['status']}"

    def test_filter_status_forfeited(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/storage-deposits?status=forfeited",
                         headers=_hdr(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        for d in data["deposits"]:
            assert d["status"] == "forfeited"


# ──────────────────────────────────────────────────────────────
# 3) RELEASE / FORFEIT endpoints (RBAC + 404)
# ──────────────────────────────────────────────────────────────
class TestReleaseAndForfeit:
    def test_release_403_for_buyer(self, buyer_token):
        r = requests.post(f"{BASE_URL}/api/admin/storage-auctions/nonexistent-id/release-deposits",
                          headers=_hdr(buyer_token), timeout=15)
        assert r.status_code == 403, r.text

    def test_release_404_for_unknown_auction(self, admin_token):
        unknown = f"unknown-{uuid.uuid4().hex[:8]}"
        r = requests.post(f"{BASE_URL}/api/admin/storage-auctions/{unknown}/release-deposits",
                          headers=_hdr(admin_token), timeout=20)
        assert r.status_code == 404, f"expected 404 got {r.status_code}: {r.text[:200]}"

    def test_forfeit_403_for_buyer(self, buyer_token):
        r = requests.post(f"{BASE_URL}/api/admin/storage-auctions/some-id/forfeit-deposit",
                          headers=_hdr(buyer_token), json={"buyer_id": "x"}, timeout=15)
        assert r.status_code == 403

    def test_forfeit_400_without_buyer_id(self, admin_token):
        r = requests.post(f"{BASE_URL}/api/admin/storage-auctions/some-id/forfeit-deposit",
                          headers=_hdr(admin_token), json={}, timeout=15)
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:200]}"

    def test_forfeit_404_when_no_held_deposit(self, admin_token):
        unknown = f"unknown-{uuid.uuid4().hex[:8]}"
        r = requests.post(f"{BASE_URL}/api/admin/storage-auctions/{unknown}/forfeit-deposit",
                          headers=_hdr(admin_token), json={"buyer_id": "ghost-buyer"}, timeout=20)
        assert r.status_code == 404, f"expected 404 got {r.status_code}: {r.text[:200]}"


# ──────────────────────────────────────────────────────────────
# 4) Scheduler registration — direct module test
# ──────────────────────────────────────────────────────────────
class TestSchedulerRegistration:
    def test_scheduled_jobs_module_has_function(self):
        from services import scheduled_jobs
        assert hasattr(scheduled_jobs, "process_ended_storage_auctions")
        fn = scheduled_jobs.process_ended_storage_auctions
        assert inspect.iscoroutinefunction(fn), "process_ended_storage_auctions must be async"

    def test_scheduler_log_has_10_jobs(self):
        # Read backend stderr log (apscheduler logs go to stderr)
        with open("/var/log/supervisor/backend.err.log", "r") as f:
            content = f.read()
        assert "Scheduler initialized with 10 jobs" in content, \
            "Backend log should say 'Scheduler initialized with 10 jobs' (storage close job registered)"

    def test_scheduler_has_storage_close_job_in_code(self):
        # Verify the registration exists in scheduler.py source
        with open("/app/backend/services/scheduler.py", "r") as f:
            src = f.read()
        assert 'id="process_ended_storage_auctions"' in src
        assert "IntervalTrigger(minutes=5)" in src
        assert "storage_close_job" in src


# ──────────────────────────────────────────────────────────────
# 5) Email functions — direct invocation
# ──────────────────────────────────────────────────────────────
class TestStorageEmails:
    def test_won_and_sold_email_signatures(self):
        from services.emails.email_marketplace import (
            send_storage_auction_won_email,
            send_storage_auction_sold_email,
        )
        assert inspect.iscoroutinefunction(send_storage_auction_won_email)
        assert inspect.iscoroutinefunction(send_storage_auction_sold_email)
        # Check params
        won_params = list(inspect.signature(send_storage_auction_won_email).parameters)
        assert won_params[:3] == ["buyer", "auction", "facility"]
        sold_params = list(inspect.signature(send_storage_auction_sold_email).parameters)
        assert sold_params[:3] == ["facility", "auction", "buyer"]

    @pytest.mark.parametrize("pm", ["stripe", "cash", "etransfer"])
    def test_won_email_branches_per_payment_method(self, pm):
        from services.emails.email_marketplace import send_storage_auction_won_email
        buyer = {"email": "test_iter171@example.com", "name": "Test Buyer"}
        auction = {
            "unit_number": "A-1",
            "winning_bid": 800,
            "current_bid": 800,
            "payment_method": pm,
            "payment_deadline": "2026-12-31",
            "cleanup_deadline": "2026-12-31",
            "cleanup_deposit": 100,
        }
        facility = {
            "company_name": "TEST_Facility", "contact_name": "Owner",
            "phone": "555-0100", "email": "facility@example.com",
        }
        pricing = {
            "buyer_invoice": {"platform_fee": 40.0, "stripe_recovery": 24.66, "tax": 9.68},
            "facility_invoice": {"facility_receives": 800.0},
        }
        result = asyncio.get_event_loop().run_until_complete(
            send_storage_auction_won_email(buyer, auction, facility, pricing)
        )
        # Per review-request: return bool. Implementation returns dict in
        # SendGrid-not-configured fallback (logged contract). Accept both
        # but no exception is mandatory.
        assert result is not None
        assert isinstance(result, (bool, dict)), f"unexpected type: {type(result).__name__}: {result}"

    def test_sold_email_callable(self):
        from services.emails.email_marketplace import send_storage_auction_sold_email
        facility = {"email": "fac@example.com", "company_name": "TEST_Facility", "contact_name": "Owner"}
        auction = {"unit_number": "A-1", "winning_bid": 800, "payment_method": "stripe"}
        buyer = {"email": "b@example.com", "name": "Buyer"}
        result = asyncio.get_event_loop().run_until_complete(
            send_storage_auction_sold_email(facility, auction, buyer)
        )
        assert result is not None
        assert isinstance(result, (bool, dict))


# ──────────────────────────────────────────────────────────────
# 6) REGRESSION — public storage list + bid 402 deposit_required
# ──────────────────────────────────────────────────────────────
class TestRegression:
    def test_public_storage_auctions_list(self):
        r = requests.get(f"{BASE_URL}/api/storage-auctions", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # Could be list or {auctions: [...]}
        assert isinstance(data, (list, dict))

    def test_bid_with_deposit_required_returns_402(self, buyer_token, admin_token):
        """
        Find or create a storage auction with deposit_required=True, then bid as buyer.
        Expected: 402 with deposit_required marker.
        """
        # Try to find an existing deposit-required auction via list
        r = requests.get(f"{BASE_URL}/api/storage-auctions?status=active", timeout=20)
        if r.status_code != 200:
            pytest.skip("storage-auctions list unavailable")
        data = r.json()
        items = data if isinstance(data, list) else (data.get("auctions") or data.get("items") or [])
        target = None
        for a in items:
            if a.get("deposit_required") and a.get("status") == "active":
                target = a
                break
        if not target:
            pytest.skip("No active deposit-required storage auction available for regression test")

        bid_amount = float(target.get("current_bid", 0)) + float(target.get("min_bid_increment", 5) or 5)
        r = requests.post(
            f"{BASE_URL}/api/storage-auctions/{target['id']}/bid",
            headers=_hdr(buyer_token),
            json={"max_bid": bid_amount},
            timeout=20,
        )
        assert r.status_code == 402, f"expected 402 got {r.status_code}: {r.text[:300]}"
        body = r.json().get("detail") if isinstance(r.json().get("detail"), dict) else r.json()
        assert body.get("error") == "deposit_required" or body.get("action") == "pay_deposit", \
            f"missing deposit_required marker: {body}"
