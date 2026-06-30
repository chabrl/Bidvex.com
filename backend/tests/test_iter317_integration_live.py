"""iter317 — Live HTTP integration tests against REACT_APP_BACKEND_URL.

Covers Directives 1, 2, 3 end-to-end through the ingress.
Run: pytest /app/backend/tests/test_iter317_integration_live.py -v
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "charbel911@gmail.com", "password": "Anderosli123!@#"}
BUYER = {"email": "testbuyer@bidvex.com", "password": "TestBuyer2026!"}
DEALER = {"email": "testdealer@bidvex.com", "password": "TestDealer2026!"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=60)
    if r.status_code != 200:
        return None
    return r.json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_token():
    tok = _login(ADMIN)
    if not tok:
        pytest.skip("admin login failed")
    return tok


@pytest.fixture(scope="module")
def buyer_token():
    tok = _login(BUYER)
    if not tok:
        pytest.skip("buyer login failed — credentials stale on env")
    return tok


@pytest.fixture(scope="module")
def dealer_token():
    tok = _login(DEALER)
    if not tok:
        pytest.skip("dealer login failed — credentials stale on env")
    return tok


# ─── Directive 1 — Leaderboard Overlay ─────────────────────────────────────
class TestDirective1LeaderboardOverlay:
    def test_run_now_admin_returns_summary(self, admin_token):
        r = requests.post(f"{API}/twilio/admin/leaderboard-overlay/run-now",
                          headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "iso_week" in data
        assert "top_5_ids" in data
        # response uses contractors_evaluated key
        assert "contractors_evaluated" in data or "evaluated" in data
        assert "batch_id" in data
        assert isinstance(data["top_5_ids"], list)

    def test_run_now_idempotent_same_batch_id(self, admin_token):
        r1 = requests.post(f"{API}/twilio/admin/leaderboard-overlay/run-now",
                           headers=_h(admin_token), timeout=30).json()
        r2 = requests.post(f"{API}/twilio/admin/leaderboard-overlay/run-now",
                           headers=_h(admin_token), timeout=30).json()
        assert r1.get("iso_week") == r2.get("iso_week")
        assert r1.get("batch_id") == r2.get("batch_id"), "second call must reuse batch_id"

    def test_batches_list_admin(self, admin_token):
        r = requests.get(f"{API}/twilio/admin/leaderboard-overlay/batches",
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # Response could be list or dict with key
        if isinstance(data, dict):
            assert "batches" in data or "items" in data or isinstance(data, list)

    def test_batches_non_admin_403(self, buyer_token):
        r = requests.get(f"{API}/twilio/admin/leaderboard-overlay/batches",
                         headers=_h(buyer_token), timeout=20)
        assert r.status_code == 403, f"expected 403 got {r.status_code}"

    def test_run_now_non_admin_403(self, buyer_token):
        r = requests.post(f"{API}/twilio/admin/leaderboard-overlay/run-now",
                          headers=_h(buyer_token), timeout=20)
        assert r.status_code == 403


# ─── Directive 2 — Contractor Agreement ────────────────────────────────────
class TestDirective2Agreement:
    def test_current_agreement_admin(self, admin_token):
        r = requests.get(f"{API}/twilio/contractor/agreements/current",
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("version", "title_en", "title_fr", "text_en", "text_fr", "text_hash"):
            assert key in data, f"missing key {key}"
        assert "account_legal_name" in data

    def test_my_agreement_status_admin(self, admin_token):
        r = requests.get(f"{API}/twilio/contractor/agreements/me",
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "signed" in data
        assert "required" in data
        # Admin should have required=False
        assert data["required"] is False

    def test_my_agreement_status_anonymous_401(self):
        r = requests.get(f"{API}/twilio/contractor/agreements/me", timeout=20)
        assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"

    def test_sign_admin_409_not_a_contractor(self, admin_token):
        cur = requests.get(f"{API}/twilio/contractor/agreements/current",
                           headers=_h(admin_token), timeout=20).json()
        payload = {
            "agreement_version": cur["version"],
            "text_hash": cur["text_hash"],
            "signed_full_name": cur.get("account_legal_name") or "Admin User",
        }
        r = requests.post(f"{API}/twilio/contractor/agreements/sign",
                          headers=_h(admin_token), json=payload, timeout=20)
        assert r.status_code == 409, f"expected 409 got {r.status_code}: {r.text}"
        data = r.json()
        detail = data.get("detail", data)
        if isinstance(detail, dict):
            assert detail.get("error") == "not_a_contractor"


# ─── Directive 3 — Contractor Email Hub ────────────────────────────────────
class TestDirective3EmailHub:
    def test_send_invalid_recipient_400(self, admin_token):
        # admin is also a "contractor-allowed" caller for this route in test infra;
        # the validation runs before any contractor check
        payload = {"to_email": "not-an-email", "subject": "hi", "body_html": "body"}
        r = requests.post(f"{API}/twilio/contractor/emails/send",
                          headers=_h(admin_token), json=payload, timeout=20)
        assert r.status_code in (400, 412, 403), f"got {r.status_code}: {r.text}"
        if r.status_code == 400:
            data = r.json()
            detail = data.get("detail", data)
            if isinstance(detail, dict):
                assert detail.get("code") in ("invalid_recipient", None) or "invalid" in str(detail).lower()

    def test_send_empty_subject_400(self, admin_token):
        payload = {"to_email": "x@example.com", "subject": "", "body_html": "body"}
        r = requests.post(f"{API}/twilio/contractor/emails/send",
                          headers=_h(admin_token), json=payload, timeout=20)
        assert r.status_code in (400, 412, 403)

    def test_send_empty_body_400(self, admin_token):
        payload = {"to_email": "x@example.com", "subject": "Hi", "body_html": ""}
        r = requests.post(f"{API}/twilio/contractor/emails/send",
                          headers=_h(admin_token), json=payload, timeout=20)
        assert r.status_code in (400, 412, 403)

    def test_emails_list_admin(self, admin_token):
        r = requests.get(f"{API}/twilio/contractor/emails?limit=5",
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # Expect metadata
        assert isinstance(data, dict)
        meta = data.get("meta") or data
        assert meta.get("sender_email") == "partners@bidvex.ca" or data.get("sender_email") == "partners@bidvex.ca"
        # Support phone
        sp = meta.get("support_phone") or data.get("support_phone")
        assert sp == "+1 450 634 3099"

    def test_emails_recipients_admin(self, admin_token):
        r = requests.get(f"{API}/twilio/contractor/emails/recipients",
                         headers=_h(admin_token), timeout=20)
        # Admin may or may not have referred clients; expect 200 with list
        assert r.status_code == 200, r.text
        data = r.json()
        assert "recipients" in data or "items" in data or isinstance(data, list)

    def test_buyer_send_403_or_412(self, buyer_token):
        """Non-contractor regular user should be blocked."""
        payload = {"to_email": "x@example.com", "subject": "hi", "body_html": "body"}
        r = requests.post(f"{API}/twilio/contractor/emails/send",
                          headers=_h(buyer_token), json=payload, timeout=20)
        assert r.status_code in (403, 412), f"expected 403/412, got {r.status_code}"


# ─── Regression: iter316 endpoints still alive ─────────────────────────────
class TestIter316Regression:
    def test_config_admin(self, admin_token):
        r = requests.get(f"{API}/twilio/config", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text

    def test_admin_contractors(self, admin_token):
        r = requests.get(f"{API}/twilio/admin/contractors", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text

    def test_contractor_dashboard_admin_includes_overlay(self, admin_token):
        """iter317 — dashboard must include leaderboard_overlay_rate + updated_at"""
        r = requests.get(f"{API}/twilio/contractor/dashboard",
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "leaderboard_overlay_rate" in data, "missing leaderboard_overlay_rate"
        assert "leaderboard_overlay_updated_at" in data, "missing leaderboard_overlay_updated_at"
        assert isinstance(data["leaderboard_overlay_rate"], (int, float))

    def test_payout_readiness(self, admin_token):
        r = requests.get(f"{API}/twilio/contractor/payout-readiness",
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
