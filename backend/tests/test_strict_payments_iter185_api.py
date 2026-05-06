"""
iter185 API-level smoke tests against the live preview BASE_URL.
Covers admin charge-log endpoints + bidder-deposits endpoints.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
BUYER_EMAIL = "p0bugtest@example.com"
BUYER_PASSWORD = "TestBuyer123!"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    body = r.json()
    return body.get("token") or body.get("access_token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def buyer_token():
    return _login(BUYER_EMAIL, BUYER_PASSWORD)


# ---------- Admin charges dashboard ----------
class TestAdminCharges:
    def test_payment_charges_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/payment-charges", timeout=20)
        assert r.status_code in (401, 403), f"expected auth block, got {r.status_code}"

    def test_payment_charges_forbids_non_admin(self, buyer_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/payment-charges",
            headers={"Authorization": f"Bearer {buyer_token}"},
            timeout=20,
        )
        assert r.status_code == 403

    def test_payment_charges_admin_ok(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/payment-charges",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30,
        )
        assert r.status_code == 200
        body = r.json()
        # Spec requires rows + summary
        assert "rows" in body or "charges" in body, f"missing rows: {list(body.keys())}"
        assert "summary" in body, f"missing summary: {list(body.keys())}"
        summary = body["summary"]
        assert isinstance(summary, dict)

    def test_payment_events_admin_ok(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/payment-charges/events",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30,
        )
        assert r.status_code == 200
        body = r.json()
        assert "events" in body or isinstance(body, list)

    def test_refund_queue_admin_ok(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/payment-charges/refund-queue",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30,
        )
        assert r.status_code == 200
        body = r.json()
        # Should contain stats + failed jobs
        assert isinstance(body, dict)
        keys = set(body.keys())
        # Spec: queue stats + failed jobs
        assert "by_status" in keys or "stats" in keys, f"missing stats: {keys}"
        assert "failed_jobs" in keys or "failed" in keys, f"missing failed list: {keys}"


# ---------- Bidder deposits ----------
class TestBidderDeposits:
    def test_check_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/bidder-deposits/check/nonexistent-auction", timeout=20)
        assert r.status_code in (401, 403)

    def test_check_unknown_auction_404_or_ok_with_required_false(self, buyer_token):
        r = requests.get(
            f"{BASE_URL}/api/bidder-deposits/check/nonexistent-auction-TEST_abc",
            headers={"Authorization": f"Bearer {buyer_token}"},
            timeout=20,
        )
        # Either 404 (listing not found) or 200 with required=false is acceptable
        assert r.status_code in (200, 404), f"unexpected {r.status_code}: {r.text}"
        if r.status_code == 200:
            body = r.json()
            assert "required" in body

    def test_charge_rejects_listing_without_deposit(self, buyer_token):
        # Pick any active listing that does NOT require deposit
        listings = requests.get(f"{BASE_URL}/api/listings?limit=20", timeout=20)
        assert listings.status_code == 200
        items = listings.json()
        if isinstance(items, dict):
            items = items.get("listings") or items.get("items") or []
        target = None
        for l in items:
            if not l.get("requires_deposit"):
                target = l
                break
        if not target:
            pytest.skip("No non-deposit listing available to test rejection")
        r = requests.post(
            f"{BASE_URL}/api/bidder-deposits/charge",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={"auction_id": target["id"]},
            timeout=30,
        )
        # Spec: returns 400 if listing.requires_deposit is false
        assert r.status_code == 400, f"expected 400 (no deposit required), got {r.status_code}: {r.text}"


# ---------- Listing creation — deposit validation ----------
class TestListingDepositValidation:
    def _base_payload(self):
        return {
            "title": "TEST_iter185_deposit",
            "description": "strict payment test",
            "category": "other",
            "condition": "new",
            "starting_price": 10.0,
            "location": "Montreal",
            "city": "Montreal",
            "region": "QC",
            "auction_end_date": "2030-01-01T00:00:00+00:00",
        }

    def test_requires_deposit_true_without_amount_rejected(self, admin_token):
        payload = self._base_payload()
        payload["requires_deposit"] = True
        # Missing deposit_amount and deposit_type
        r = requests.post(
            f"{BASE_URL}/api/listings",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=payload,
            timeout=30,
        )
        assert r.status_code in (400, 422), f"expected 400/422, got {r.status_code}: {r.text}"

    def test_invalid_deposit_type_rejected(self, admin_token):
        payload = self._base_payload()
        payload["requires_deposit"] = True
        payload["deposit_amount"] = 25.0
        payload["deposit_type"] = "bogus_type"
        r = requests.post(
            f"{BASE_URL}/api/listings",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=payload,
            timeout=30,
        )
        assert r.status_code in (400, 422)
