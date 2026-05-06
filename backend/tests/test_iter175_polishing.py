"""
iter175 backend tests — RecentlySoldTicker, Email Preferences (CASL),
Admin Analytics custom date-range, and deposit auto-capture service import.
"""
import os
import sys
import asyncio
import pytest
import requests

_url = os.environ.get("REACT_APP_BACKEND_URL")
if not _url:
    # Load from frontend/.env if not in runtime env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    _url = line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass
BASE_URL = (_url or "").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PW = "Anderosli123!@#"

sys.path.insert(0, "/app/backend")


# ─────────── Fixtures ───────────
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text}")
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, f"no token in login response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ─────────── 1. Recently Sold Ticker ───────────
class TestRecentlySoldTicker:
    def test_endpoint_returns_expected_shape(self):
        r = requests.get(f"{API}/carousel/recently-sold-ticker", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("visible", "total", "threshold", "items"):
            assert key in data, f"missing key: {key}; body={data}"
        assert isinstance(data["visible"], bool)
        assert isinstance(data["total"], int)
        assert isinstance(data["threshold"], int)
        assert isinstance(data["items"], list)

    def test_visibility_threshold_logic(self):
        r = requests.get(f"{API}/carousel/recently-sold-ticker", timeout=15)
        data = r.json()
        if data["total"] >= data["threshold"]:
            assert data["visible"] is True
        else:
            assert data["visible"] is False


# ─────────── 2. Email Preferences ───────────
class TestEmailPreferences:
    def test_verify_missing_token(self):
        r = requests.get(f"{API}/email-preferences/verify", timeout=10)
        assert r.status_code == 400

    def test_verify_invalid_token(self):
        r = requests.get(f"{API}/email-preferences/verify", params={"token": "garbage.token.xxx"}, timeout=10)
        assert r.status_code == 400

    def test_generate_token_requires_auth(self):
        r = requests.get(f"{API}/email-preferences/generate-token", params={"email": "a@b.com"}, timeout=10)
        assert r.status_code in (401, 403)

    def test_generate_token_invalid_email(self, admin_headers):
        r = requests.get(f"{API}/email-preferences/generate-token", params={"email": "not-an-email"},
                         headers=admin_headers, timeout=10)
        assert r.status_code == 400

    def test_full_flow_generate_verify_update(self, admin_headers):
        # Generate
        target = "TEST_emailprefs_iter175@example.com"
        r = requests.get(f"{API}/email-preferences/generate-token", params={"email": target},
                         headers=admin_headers, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "url" in body
        # Extract token from url ?token=...
        token = body["url"].split("token=")[-1]
        assert token

        # Verify
        v = requests.get(f"{API}/email-preferences/verify", params={"token": token}, timeout=10)
        assert v.status_code == 200, v.text
        vbody = v.json()
        assert "email_masked" in vbody
        assert "***" in vbody["email_masked"]
        assert "preferences" in vbody
        assert set(vbody["preferences"].keys()) >= {"marketing", "bidding_alerts"}
        cats = vbody["categories"]
        keys = {c["key"] for c in cats}
        assert keys == {"marketing", "bidding_alerts", "transactional"}
        trans = next(c for c in cats if c["key"] == "transactional")
        assert trans["toggleable"] is False

        # Update — opt-out of marketing
        u = requests.post(f"{API}/email-preferences/update",
                         json={"token": token, "preferences": {"marketing": False, "bidding_alerts": True}},
                         timeout=10)
        assert u.status_code == 200, u.text
        ubody = u.json()
        assert ubody["preferences"]["marketing"] is False
        assert ubody["preferences"]["bidding_alerts"] is True

        # Verify again — should reflect updated prefs
        v2 = requests.get(f"{API}/email-preferences/verify", params={"token": token}, timeout=10)
        assert v2.status_code == 200
        assert v2.json()["preferences"]["marketing"] is False

        # Verify suppression written — re-opt-in to clean up
        u2 = requests.post(f"{API}/email-preferences/update",
                          json={"token": token, "preferences": {"marketing": True}}, timeout=10)
        assert u2.status_code == 200


# ─────────── 3. Admin Analytics custom date range ───────────
class TestAdminAnalyticsRevenue:
    def test_revenue_requires_auth(self):
        r = requests.get(f"{API}/admin/analytics/revenue", timeout=10)
        assert r.status_code in (401, 403)

    def test_revenue_custom_range(self, admin_headers):
        r = requests.get(f"{API}/admin/analytics/revenue",
                        params={"start_date": "2025-01-01", "end_date": "2025-01-31"},
                        headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_revenue_bad_date_format(self, admin_headers):
        r = requests.get(f"{API}/admin/analytics/revenue",
                        params={"start_date": "01/01/2025", "end_date": "01/31/2025"},
                        headers=admin_headers, timeout=10)
        assert r.status_code == 400

    def test_revenue_end_before_start(self, admin_headers):
        r = requests.get(f"{API}/admin/analytics/revenue",
                        params={"start_date": "2025-03-01", "end_date": "2025-01-01"},
                        headers=admin_headers, timeout=10)
        assert r.status_code == 400


# ─────────── 4. Deposit auto-capture service (import/shape) ───────────
class TestDepositAutoCapture:
    def test_module_imports_and_signature(self):
        from services.deposit_auto_capture import run_auto_capture_overdue_deposits
        assert callable(run_auto_capture_overdue_deposits)

    def test_run_with_none_db_returns_dict(self):
        from services.deposit_auto_capture import run_auto_capture_overdue_deposits
        result = asyncio.get_event_loop().run_until_complete(
            run_auto_capture_overdue_deposits(None)
        ) if sys.version_info < (3, 11) else asyncio.run(
            run_auto_capture_overdue_deposits(None)
        )
        assert isinstance(result, dict)
        # db=None path returns error key
        assert "error" in result or "processed" in result

    def test_email_helper_exists(self):
        from services.email_notifications import send_vehicle_deposit_captured_email
        import inspect
        assert callable(send_vehicle_deposit_captured_email)
        sig = inspect.signature(send_vehicle_deposit_captured_email)
        # Should accept buyer, invoice, deposit, captured_amount kwargs
        params = set(sig.parameters.keys())
        assert {"buyer", "invoice", "deposit", "captured_amount"}.issubset(params), f"params={params}"

    def test_scheduler_registered_12_jobs(self):
        # Check backend log contains "Scheduler initialized with N jobs" — N grows over time
        # iter175 added job 12 (auto-capture); iter178 → 13; iter183 → 14; iter185 → still 14 (deposit refund queue is registered in server.py, not scheduler.py)
        import re
        import subprocess
        res = subprocess.run(
            ["grep", "Scheduler initialized with", "/var/log/supervisor/backend.err.log"],
            capture_output=True, text=True
        )
        matches = re.findall(r"Scheduler initialized with (\d+) jobs", res.stdout)
        assert matches and int(matches[-1]) >= 12, f"expected ≥12 scheduler jobs, got: {res.stdout[-500:]}"
