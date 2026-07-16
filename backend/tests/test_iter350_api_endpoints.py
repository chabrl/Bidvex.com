"""
iter350 — Backend API-level regression tests
Tests the live HTTP endpoints for:
  - /api/fees/v2/preview  (per-province fee routing)
  - /api/subscriptions/price-breakdown  (per-province subscription tax)
  - /api/admin/pricing/tax-rates (CRUD + audit history)
Test target: REACT_APP_BACKEND_URL from /app/frontend/.env
"""
import os
import time
import pytest
import requests

BASE_URL = "https://prod-verify-2.preview.emergentagent.com"
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
NONADMIN_EMAIL = "iter350_nonadmin@test.com"
NONADMIN_PASSWORD = "NonAdmin2026!"


def _login(email, password):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    assert r.status_code == 200, f"Login {email} failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"No token in response: {r.text[:200]}"
    return tok


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def nonadmin_token():
    try:
        return _login(NONADMIN_EMAIL, NONADMIN_PASSWORD)
    except AssertionError:
        pytest.skip("Non-admin credentials not available")


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ==============================================================
# 1. /api/fees/v2/preview endpoint
# ==============================================================
class TestFeesV2Preview:
    """Verify per-province fee routing for iter350"""

    def test_ab_buyer_gets_gst_5pct_not_qc_rate(self):
        r = requests.get(
            f"{BASE_URL}/api/fees/v2/preview",
            params={
                "hammer_price": 5000,
                "auction_type": "vehicle",
                "seller_account_type": "vehicle_dealer",
                "buyer_province": "AB",
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("buyer_tax_label") == "GST (5%)", f"Got {data.get('buyer_tax_label')}"
        assert round(float(data.get("buyer_taxes", 0)), 2) == 6.45, data
        assert round(float(data.get("buyer_total_charged", 0)), 2) == 135.38, data
        assert data.get("fee_model_version") == "iter350"

    def test_qc_buyer_on_seller_split_province(self):
        r = requests.get(
            f"{BASE_URL}/api/fees/v2/preview",
            params={
                "hammer_price": 500,
                "auction_type": "general",
                "seller_account_type": "individual",
                "buyer_province": "QC",
                "seller_province": "ON",
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("buyer_tax_label") == "GST + QST (14.975%)", data
        assert data.get("seller_tax_label") == "HST (13%)", data
        assert data.get("fee_model_version") == "iter350"

    def test_us_buyer_zero_rated(self):
        r = requests.get(
            f"{BASE_URL}/api/fees/v2/preview",
            params={
                "hammer_price": 500,
                "auction_type": "general",
                "seller_account_type": "individual",
                "buyer_province": "US",
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert round(float(data.get("buyer_taxes", 0)), 2) == 0.0, data
        assert data.get("buyer_tax_label") == "Exported Service (0%)", data

    def test_partner_qc_qc_flow(self):
        r = requests.get(
            f"{BASE_URL}/api/fees/v2/preview",
            params={
                "hammer_price": 2000,
                "auction_type": "general",
                "seller_account_type": "partner",
                "buyer_province": "QC",
                "seller_province": "QC",
                "partner_bp_rate": 0.12,
                "payment_method": "stripe",
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # Buyer premium waived for partner => buyer_taxes = 0 (BidVex charges buyer nothing)
        assert round(float(data.get("buyer_taxes", 0)), 2) == 0.0, data
        # Seller (partner) commission = 2000 * 0.03 = 60.00
        assert round(float(data.get("seller_commission", 0)), 2) == 60.00, data
        # Stripe recovery on 60 fee = 60*0.029 + 0.30 = 2.04
        assert round(float(data.get("seller_stripe_recovery", 0)), 2) == 2.04, data
        # QC tax on (60 + 2.04) = 62.04 * 0.14975 = 9.290 -> 9.29
        assert round(float(data.get("seller_taxes", 0)), 2) == 9.29, data
        assert round(float(data.get("seller_payout", 0)), 2) == 71.33, data


# ==============================================================
# 2. /api/subscriptions/price-breakdown endpoint
# ==============================================================
class TestSubscriptionsPriceBreakdown:
    def test_premium_ab(self):
        r = requests.get(
            f"{BASE_URL}/api/subscriptions/price-breakdown",
            params={"plan_id": "premium", "province": "AB"},
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert round(float(data.get("gst", 0)), 2) == 9.00, data
        assert round(float(data.get("qst", 0)), 2) == 0.00, data
        assert round(float(data.get("hst", 0)), 2) == 0.00, data
        assert round(float(data.get("total", 0)), 2) == 194.78, data
        assert data.get("tax_label") == "GST (5%)", data
        assert data.get("fee_model_version") == "iter350"

    def test_premium_qc(self):
        r = requests.get(
            f"{BASE_URL}/api/subscriptions/price-breakdown",
            params={"plan_id": "premium", "province": "QC"},
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert round(float(data.get("gst", 0)), 2) == 9.00, data
        assert round(float(data.get("qst", 0)), 2) == 17.96, data
        assert round(float(data.get("total", 0)), 2) == 213.26, data
        assert data.get("tax_label") == "GST + QST (14.975%)"

    def test_premium_us(self):
        r = requests.get(
            f"{BASE_URL}/api/subscriptions/price-breakdown",
            params={"plan_id": "premium", "province": "US"},
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert round(float(data.get("gst", 0)), 2) == 0.0, data
        assert round(float(data.get("qst", 0)), 2) == 0.0, data
        assert round(float(data.get("hst", 0)), 2) == 0.0, data
        assert data.get("tax_label") == "Exported Service (0%)", data
        assert round(float(data.get("total", 0)), 2) == 185.52, data


# ==============================================================
# 3. Admin /api/admin/pricing/tax-rates endpoints
# ==============================================================
class TestAdminTaxRatesEndpoints:
    def test_list_returns_14_rows(self, admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/pricing/tax-rates",
            headers=admin_headers,
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        rows = data.get("tax_rates") or data.get("rates") or data
        if isinstance(rows, dict):
            rows = list(rows.values()) if "items" not in rows else rows.get("items")
        assert isinstance(rows, list), f"unexpected response shape: {type(rows)} {str(data)[:200]}"
        assert len(rows) == 14, f"expected 14 rows, got {len(rows)}"
        provinces = {row.get("province") for row in rows}
        expected = {"QC", "ON", "NB", "NS", "PE", "NL", "AB", "BC", "SK", "MB", "YT", "NT", "NU", "INTL"}
        assert expected == provinces, f"provinces mismatch: {provinces ^ expected}"
        # Field validation
        sample = rows[0]
        for f in ("gst", "qst", "hst", "combined", "label"):
            assert f in sample, f"missing field {f}: {sample}"

    def test_get_single_on(self, admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/pricing/tax-rates/ON",
            headers=admin_headers,
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert round(float(data.get("hst", 0)), 4) == 0.13, data
        assert round(float(data.get("combined", 0)), 4) == 0.13, data
        assert data.get("label") == "HST (13%)", data

    def test_put_update_snapshot_and_restore(self, admin_headers):
        # Update ON to HST 14%
        put_body = {"gst": 0, "qst": 0, "hst": 0.14, "label": "HST (14%) — TEST"}
        r = requests.put(
            f"{BASE_URL}/api/admin/pricing/tax-rates/ON",
            headers=admin_headers,
            json=put_body,
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        # Verify GET returns updated
        time.sleep(1)
        r2 = requests.get(
            f"{BASE_URL}/api/admin/pricing/tax-rates/ON",
            headers=admin_headers,
            timeout=15,
        )
        assert r2.status_code == 200
        data = r2.json()
        assert round(float(data.get("hst", 0)), 4) == 0.14, f"update not reflected: {data}"
        # Verify history exists
        r3 = requests.get(
            f"{BASE_URL}/api/admin/pricing/tax-rates-history/ON",
            headers=admin_headers,
            timeout=15,
        )
        assert r3.status_code == 200, r3.text[:300]
        hist = r3.json()
        hist_rows = hist.get("history") or hist.get("snapshots") or hist
        assert isinstance(hist_rows, list) and len(hist_rows) >= 1, f"no history: {hist}"
        h = hist_rows[0]
        # Must have snapshot fields
        assert any(k in h for k in ("effective_from", "effective_to", "superseded_by_user_id")), \
            f"snapshot missing audit fields: {h}"
        # Restore to 0.13
        restore = {"gst": 0, "qst": 0, "hst": 0.13, "label": "HST (13%)"}
        r4 = requests.put(
            f"{BASE_URL}/api/admin/pricing/tax-rates/ON",
            headers=admin_headers,
            json=restore,
            timeout=15,
        )
        assert r4.status_code == 200, r4.text[:300]
        time.sleep(1)
        r5 = requests.get(
            f"{BASE_URL}/api/admin/pricing/tax-rates/ON",
            headers=admin_headers,
            timeout=15,
        )
        assert round(float(r5.json().get("hst", 0)), 4) == 0.13, r5.json()

    def test_history_endpoint_on(self, admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/pricing/tax-rates-history/ON",
            headers=admin_headers,
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        payload = r.json()
        rows = payload.get("history") or payload.get("snapshots") or payload
        assert isinstance(rows, list), f"unexpected: {payload}"

    def test_non_admin_403_on_list(self, nonadmin_token):
        headers = {"Authorization": f"Bearer {nonadmin_token}"}
        r = requests.get(
            f"{BASE_URL}/api/admin/pricing/tax-rates",
            headers=headers,
            timeout=15,
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:200]}"

    def test_non_admin_403_on_get_single(self, nonadmin_token):
        headers = {"Authorization": f"Bearer {nonadmin_token}"}
        r = requests.get(
            f"{BASE_URL}/api/admin/pricing/tax-rates/ON",
            headers=headers,
            timeout=15,
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}"

    def test_non_admin_403_on_put(self, nonadmin_token):
        headers = {"Authorization": f"Bearer {nonadmin_token}"}
        r = requests.put(
            f"{BASE_URL}/api/admin/pricing/tax-rates/ON",
            headers=headers,
            json={"gst": 0, "qst": 0, "hst": 0.99, "label": "HACK"},
            timeout=15,
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}"

    def test_non_admin_403_on_history(self, nonadmin_token):
        headers = {"Authorization": f"Bearer {nonadmin_token}"}
        r = requests.get(
            f"{BASE_URL}/api/admin/pricing/tax-rates-history/ON",
            headers=headers,
            timeout=15,
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}"


# ==============================================================
# 4. Scheduler + startup verification (indirect via API)
# ==============================================================
class TestSchedulerAndStartup:
    def test_scheduler_jobs_registered_in_logs(self):
        # Look at backend.err.log for the two new job names
        with open("/var/log/supervisor/backend.err.log", "r") as f:
            log = f.read()
        assert "contractor_monthly_payouts" in log or "Contractor Monthly Payouts" in log, \
            "contractor_monthly_payouts scheduler job not found in logs"
        assert "Tax Rate Cache Refresh" in log or "tax_rate_cache_refresh" in log, \
            "tax_rate_cache_refresh scheduler job not found in logs"

    def test_bootstrap_seeding_logged(self):
        with open("/var/log/supervisor/backend.err.log", "r") as f:
            log = f.read()
        assert "tax_rate_config" in log and "bootstrap rates seeded" in log, \
            "bootstrap seed log line missing"
