"""
Iteration 172 — Storage Auctions admin controls + promotion + pickup + my-deposits API tests.

Validates HTTP contracts for ~20 new endpoints introduced in iter172:
  • Promotion: tiers list, facility promote (Stripe PI), admin grant/revoke
  • Facility admin: suspend/unsuspend/reject/delete
  • Auction admin: pause/resume/edit/delete/override-winner/force-close/create
  • Pickup code: facility verify/mark, admin regenerate
  • My deposits: GET /api/my-storage-deposits
  • Scheduler: 11 jobs registered, process_expired_promotions importable

Auth: charbel911@gmail.com (admin) and abc@gmail.com (buyer).
NO Stripe captures — only PI creation is exercised, and never confirmed.
"""
import os
import sys
import importlib
import pytest
import requests
from typing import Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASS = "Anderosli123!@#"
BUYER_EMAIL = "abc@gmail.com"
BUYER_PASS = "TestBuyer123!"


def _login(email: str, password: str) -> Optional[str]:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    if r.status_code != 200:
        return None
    data = r.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def admin_token():
    t = _login(ADMIN_EMAIL, ADMIN_PASS)
    if not t:
        pytest.skip("Admin login failed")
    return t


@pytest.fixture(scope="module")
def buyer_token():
    t = _login(BUYER_EMAIL, BUYER_PASS)
    if not t:
        pytest.skip("Buyer login failed")
    return t


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def buyer_headers(buyer_token):
    return {"Authorization": f"Bearer {buyer_token}", "Content-Type": "application/json"}


# ──────────────────────────────────────────────────────────────
# Promotion tiers (public)
# ──────────────────────────────────────────────────────────────
class TestPromotionTiers:
    def test_get_promotion_tiers_public(self):
        r = requests.get(f"{BASE_URL}/api/storage-promotion-tiers", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "tiers" in data
        for tier in ("basic", "featured", "premium"):
            assert tier in data["tiers"], f"Missing tier {tier}"
            t = data["tiers"][tier]
            assert "price_cad" in t and isinstance(t["price_cad"], (int, float))
            assert "duration_days" in t and isinstance(t["duration_days"], int)
            assert t["duration_days"] > 0
            assert t["price_cad"] > 0


# ──────────────────────────────────────────────────────────────
# Admin grant/revoke promotion (RBAC + 404)
# ──────────────────────────────────────────────────────────────
class TestAdminPromotion:
    def test_grant_promotion_requires_admin(self, buyer_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/nonexistent/grant-promotion",
            json={"tier": "basic"}, headers=buyer_headers, timeout=10,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text[:200]}"

    def test_grant_promotion_unknown_auction_returns_404(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/does-not-exist-xyz/grant-promotion",
            json={"tier": "basic"}, headers=admin_headers, timeout=10,
        )
        assert r.status_code == 404

    def test_grant_promotion_invalid_tier_returns_400(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/any/grant-promotion",
            json={"tier": "platinum"}, headers=admin_headers, timeout=10,
        )
        assert r.status_code == 400

    def test_revoke_promotion_requires_admin(self, buyer_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/x/revoke-promotion",
            headers=buyer_headers, timeout=10,
        )
        assert r.status_code == 403

    def test_revoke_promotion_unknown_auction_returns_404(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/does-not-exist-xyz/revoke-promotion",
            headers=admin_headers, timeout=10,
        )
        assert r.status_code == 404

    def test_grant_then_revoke_real_auction(self, admin_headers):
        # Grab an auction owned by charbel (the admin's facility) from admin list
        r = requests.get(f"{BASE_URL}/api/admin/storage-auctions", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        items = r.json() if isinstance(r.json(), list) else r.json().get("auctions", [])
        if not items:
            pytest.skip("No storage auctions present to grant/revoke")
        target = items[0]
        aid = target["id"]
        grant = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/{aid}/grant-promotion",
            json={"tier": "basic"}, headers=admin_headers, timeout=15,
        )
        assert grant.status_code == 200
        gd = grant.json()
        assert gd.get("success") is True
        assert gd.get("tier") == "basic"
        assert gd.get("promoted_until")

        rev = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/{aid}/revoke-promotion",
            headers=admin_headers, timeout=15,
        )
        assert rev.status_code == 200
        assert rev.json().get("success") is True


# ──────────────────────────────────────────────────────────────
# Facility-only: promote (Stripe PI) — non-facility 403, no capture
# ──────────────────────────────────────────────────────────────
class TestFacilityPromote:
    def test_promote_requires_facility(self, buyer_headers):
        # buyer is NOT a verified facility
        r = requests.post(
            f"{BASE_URL}/api/storage-auctions/any/promote",
            json={"tier": "basic"}, headers=buyer_headers, timeout=10,
        )
        assert r.status_code in (403, 404)


# ──────────────────────────────────────────────────────────────
# Admin facility lifecycle (RBAC checks; we don't actually delete charbel's facility)
# ──────────────────────────────────────────────────────────────
class TestAdminFacilityControls:
    def test_reject_facility_requires_admin(self, buyer_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-facilities/nope/reject",
            json={"reason": "test"}, headers=buyer_headers, timeout=10,
        )
        assert r.status_code == 403

    def test_reject_facility_unknown_returns_404(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-facilities/does-not-exist-xyz/reject",
            json={"reason": "test"}, headers=admin_headers, timeout=10,
        )
        assert r.status_code == 404

    def test_suspend_unknown_facility_returns_404(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-facilities/does-not-exist-xyz/suspend",
            headers=admin_headers, timeout=10,
        )
        assert r.status_code == 404

    def test_unsuspend_unknown_facility_returns_404(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-facilities/does-not-exist-xyz/unsuspend",
            headers=admin_headers, timeout=10,
        )
        assert r.status_code == 404

    def test_delete_unknown_facility_returns_404(self, admin_headers):
        r = requests.delete(
            f"{BASE_URL}/api/admin/storage-facilities/does-not-exist-xyz",
            headers=admin_headers, timeout=10,
        )
        assert r.status_code == 404

    def test_delete_facility_requires_admin(self, buyer_headers):
        r = requests.delete(
            f"{BASE_URL}/api/admin/storage-facilities/x", headers=buyer_headers, timeout=10,
        )
        assert r.status_code == 403


# ──────────────────────────────────────────────────────────────
# Admin auction lifecycle (pause/resume/edit/delete/override/force-close/create)
# Use a real existing auction owned by charbel where possible. We do NOT
# delete it; we only validate 404 contracts and pause/resume cycle.
# ──────────────────────────────────────────────────────────────
class TestAdminAuctionControls:
    def test_pause_unknown_returns_404(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/does-not-exist-xyz/pause",
            headers=admin_headers, timeout=10,
        )
        assert r.status_code == 404

    def test_resume_unknown_returns_404(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/does-not-exist-xyz/resume",
            headers=admin_headers, timeout=10,
        )
        assert r.status_code == 404

    def test_edit_unknown_returns_404(self, admin_headers):
        r = requests.put(
            f"{BASE_URL}/api/admin/storage-auctions/does-not-exist-xyz",
            json={"description_en": "x"}, headers=admin_headers, timeout=10,
        )
        assert r.status_code == 404

    def test_edit_no_fields_returns_400(self, admin_headers):
        r = requests.put(
            f"{BASE_URL}/api/admin/storage-auctions/anything",
            json={}, headers=admin_headers, timeout=10,
        )
        # 400 (no valid fields) takes priority over 404 lookup since updates dict empty triggers first
        assert r.status_code == 400

    def test_delete_unknown_returns_404(self, admin_headers):
        r = requests.delete(
            f"{BASE_URL}/api/admin/storage-auctions/does-not-exist-xyz",
            headers=admin_headers, timeout=10,
        )
        assert r.status_code == 404

    def test_override_winner_missing_fields_400(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/anything/override-winner",
            json={}, headers=admin_headers, timeout=10,
        )
        assert r.status_code == 400

    def test_override_winner_unknown_auction_returns_404(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/does-not-exist-xyz/override-winner",
            json={"winner_id": "u1", "reason": "test"}, headers=admin_headers, timeout=10,
        )
        assert r.status_code == 404

    def test_force_close_unknown_returns_404(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/does-not-exist-xyz/force-close",
            headers=admin_headers, timeout=10,
        )
        assert r.status_code == 404

    def test_force_close_requires_admin(self, buyer_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/x/force-close",
            headers=buyer_headers, timeout=10,
        )
        assert r.status_code == 403

    def test_pause_resume_real_active_auction(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/storage-auctions", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        items = r.json() if isinstance(r.json(), list) else r.json().get("auctions", [])
        active = next((x for x in items if x.get("status") == "active"), None)
        if not active:
            pytest.skip("No active storage auction to pause/resume")
        aid = active["id"]
        p = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/{aid}/pause",
            headers=admin_headers, timeout=15,
        )
        assert p.status_code == 200, f"pause failed: {p.text[:200]}"
        assert p.json().get("status") == "paused"
        rs = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/{aid}/resume",
            headers=admin_headers, timeout=15,
        )
        assert rs.status_code == 200, f"resume failed: {rs.text[:200]}"
        assert rs.json().get("status") == "active"


# ──────────────────────────────────────────────────────────────
# Admin create auction on behalf of facility
# ──────────────────────────────────────────────────────────────
class TestAdminCreateAuction:
    def test_admin_create_storage_auction_unknown_facility_404(self, admin_headers):
        payload = {
            "unit_number": "TEST_TST-1",
            "unit_size": "10x10",
            "unit_type": "indoor",
            "description_en": "Admin-created test unit (should fail).",
            "starting_price": 1,
            "start_time": "2099-01-01T00:00:00Z",
            "end_time": "2099-01-08T00:00:00Z",
            "payment_method": "stripe",
            "deposit_required": False,
        }
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions?facility_id=does-not-exist-xyz",
            json=payload, headers=admin_headers, timeout=10,
        )
        assert r.status_code == 404

    def test_admin_create_storage_auction_requires_admin(self, buyer_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions?facility_id=any",
            json={}, headers=buyer_headers, timeout=10,
        )
        assert r.status_code in (403, 422)


# ──────────────────────────────────────────────────────────────
# Pickup code endpoints
# ──────────────────────────────────────────────────────────────
class TestPickupCode:
    def test_verify_pickup_requires_facility(self, buyer_headers):
        r = requests.post(
            f"{BASE_URL}/api/storage-facilities/verify-pickup-code",
            json={"pickup_code": "ABC123"}, headers=buyer_headers, timeout=10,
        )
        assert r.status_code in (403, 404)

    def test_mark_picked_up_requires_facility(self, buyer_headers):
        r = requests.post(
            f"{BASE_URL}/api/storage-facilities/mark-picked-up",
            json={"pickup_code": "ABC123"}, headers=buyer_headers, timeout=10,
        )
        assert r.status_code in (403, 404)

    def test_regenerate_pickup_code_requires_admin(self, buyer_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/x/regenerate-pickup-code",
            headers=buyer_headers, timeout=10,
        )
        assert r.status_code == 403

    def test_regenerate_pickup_code_unknown_auction_returns_404(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/does-not-exist-xyz/regenerate-pickup-code",
            headers=admin_headers, timeout=10,
        )
        assert r.status_code == 404

    def test_regenerate_pickup_code_non_sold_returns_400(self, admin_headers):
        # Find any non-sold auction
        r = requests.get(f"{BASE_URL}/api/admin/storage-auctions", headers=admin_headers, timeout=15)
        items = r.json() if isinstance(r.json(), list) else r.json().get("auctions", [])
        non_sold = next((x for x in items if x.get("status") != "sold"), None)
        if not non_sold:
            pytest.skip("No non-sold auction to validate 400 contract")
        rr = requests.post(
            f"{BASE_URL}/api/admin/storage-auctions/{non_sold['id']}/regenerate-pickup-code",
            headers=admin_headers, timeout=15,
        )
        assert rr.status_code == 400


# ──────────────────────────────────────────────────────────────
# My deposits user endpoint
# ──────────────────────────────────────────────────────────────
class TestMyStorageDeposits:
    def test_my_deposits_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/my-storage-deposits", timeout=10)
        assert r.status_code in (401, 403)

    def test_my_deposits_buyer_returns_shape(self, buyer_headers):
        r = requests.get(f"{BASE_URL}/api/my-storage-deposits", headers=buyer_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "total" in data and isinstance(data["total"], int)
        assert "deposits" in data and isinstance(data["deposits"], list)
        # If any deposits, validate enrichment shape
        for d in data["deposits"][:3]:
            assert "auction_id" in d
            assert "auction_unit_number" in d
            assert "facility_name" in d


# ──────────────────────────────────────────────────────────────
# Scheduler / cron sanity (in-process import)
# ──────────────────────────────────────────────────────────────
class TestSchedulerImports:
    def test_process_expired_promotions_importable(self):
        mod = importlib.import_module("services.scheduled_jobs")
        assert hasattr(mod, "process_expired_promotions")
        assert hasattr(mod, "generate_pickup_code")

    def test_scheduler_log_shows_11_jobs(self):
        # Read backend supervisor log; tail for the latest "Scheduler initialized with" line
        path = "/var/log/supervisor/backend.err.log"
        if not os.path.exists(path):
            pytest.skip("backend.err.log not present in this environment")
        with open(path, "r") as f:
            lines = f.readlines()
        sched_lines = [ln for ln in lines if "Scheduler initialized with" in ln]
        if not sched_lines:
            pytest.skip("No scheduler init log found yet")
        last = sched_lines[-1]
        assert "11 jobs" in last, f"Expected 11 jobs, last log: {last.strip()}"

    @pytest.mark.asyncio
    async def test_process_expired_promotions_runs_against_db(self):
        # Hit the actual DB. If it errors, the function returns {"error": ...}
        from services.scheduled_jobs import process_expired_promotions
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        if not mongo_url or not db_name:
            pytest.skip("MONGO_URL/DB_NAME not set")
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        try:
            res = await process_expired_promotions(db)
            assert isinstance(res, dict)
            assert "error" not in res, f"process_expired_promotions returned error: {res}"
            assert "downgraded" in res
            assert "per_collection" in res
        finally:
            client.close()
