"""iter309 — HTTP-level end-to-end tests against the preview backend URL.

Covers the directives that explicitly call out API endpoints:
  D4 — /api/unsubscribe/auto-verify, /api/unsubscribe/auto-confirm,
       /api/unsubscribe/generate-test-link
  D3 — /api/admin/external-campaigns (list + create), /api/admin/promotions/activate-trial
  D2 — public marketplace hides pending_admin_review listings (live HTTP)
  D1 — POST /api/multi-item-listings with per-lot categories returns
       a categories[] aggregate
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
SELLER_EMAIL = "testseller@bidvex.com"
SELLER_PASSWORD = "TestSeller2026!"


# ───────── Helpers / fixtures ─────────

@pytest.fixture(scope="module")
def admin_token() -> str:
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert resp.status_code == 200, f"admin login failed: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def seller_token() -> str:
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": SELLER_EMAIL, "password": SELLER_PASSWORD},
        timeout=20,
    )
    if resp.status_code != 200:
        pytest.skip(f"seller login failed: {resp.status_code} {resp.text}")
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ───────── D4 — Unsubscribe ─────────

class TestD4Unsubscribe:
    def test_auto_verify_token_missing(self):
        r = requests.get(f"{BASE_URL}/api/unsubscribe/auto-verify", timeout=15)
        assert r.status_code == 400, f"got {r.status_code} {r.text}"
        body = r.json()
        # FastAPI default error envelope: {"detail": "..."} or {"detail": {"error": ...}}
        text = str(body).lower()
        assert "token" in text or "missing" in text

    def test_auto_verify_invalid_token(self):
        r = requests.get(
            f"{BASE_URL}/api/unsubscribe/auto-verify",
            params={"token": "garbage-not-a-real-token"},
            timeout=15,
        )
        assert r.status_code == 400, f"got {r.status_code} {r.text}"

    def test_generate_test_link_and_auto_confirm(self, admin_token):
        email = f"qatest_iter309_{uuid.uuid4().hex[:8]}@example.com"
        # 1. Mint a signed token via admin helper
        r = requests.get(
            f"{BASE_URL}/api/unsubscribe/generate-test-link",
            params={"email": email},
            headers=auth(admin_token),
            timeout=20,
        )
        assert r.status_code == 200, f"generate-test-link: {r.status_code} {r.text}"
        body = r.json()
        url_en = body.get("url_en") or body.get("en") or body.get("url")
        assert url_en, f"missing url_en in response: {body}"
        # URL pattern check
        assert "/unsubscribe?token=" in url_en
        assert "lang=en" in url_en

        # Extract token
        token = url_en.split("token=", 1)[1].split("&", 1)[0]
        assert token

        # 2. auto-verify with that token should succeed
        v = requests.get(
            f"{BASE_URL}/api/unsubscribe/auto-verify",
            params={"token": token},
            timeout=15,
        )
        assert v.status_code == 200, f"verify failed: {v.status_code} {v.text}"

        # 3. auto-confirm
        c = requests.post(
            f"{BASE_URL}/api/unsubscribe/auto-confirm",
            json={"token": token},
            timeout=20,
        )
        assert c.status_code == 200, f"confirm failed: {c.status_code} {c.text}"
        cbody = c.json()
        assert cbody.get("status") == "success", f"unexpected: {cbody}"
        # masked email present
        masked = cbody.get("email") or cbody.get("email_masked") or ""
        assert "@" in masked  # some form of email returned

        # 4. Re-confirm -> already_done
        c2 = requests.post(
            f"{BASE_URL}/api/unsubscribe/auto-confirm",
            json={"token": token},
            timeout=20,
        )
        assert c2.status_code == 200
        assert c2.json().get("status") in ("already_done", "already_unsubscribed"), c2.json()


# ───────── D3 — Partner trial coupon & external campaigns ─────────

class TestD3PartnerCoupon:
    def test_list_external_campaigns(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/external-campaigns",
            headers=auth(admin_token),
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body, (list, dict))

    def test_create_campaign_partner_type_accepted(self, admin_token):
        payload = {
            "name": f"TEST_iter309_partner_{uuid.uuid4().hex[:6]}",
            "subject_en": "Partner trial",
            "body_html_en": "<p>Hi {trial_signup_url} {unsubscribe_url}</p>",
            "attach_trial_coupon": True,
            "trial_partner_type": "partner",
        }
        r = requests.post(
            f"{BASE_URL}/api/admin/external-campaigns",
            json=payload,
            headers=auth(admin_token),
            timeout=20,
        )
        assert r.status_code == 200, f"got {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("status") == "draft" or body.get("campaign", {}).get("status") == "draft", body

    @pytest.mark.parametrize("ptype", ["dealer", "broker", "storage", "partner"])
    def test_create_campaign_all_4_partner_types_accepted(self, admin_token, ptype):
        payload = {
            "name": f"TEST_iter309_{ptype}_{uuid.uuid4().hex[:6]}",
            "subject_en": f"{ptype} trial",
            "body_html_en": "<p>Hi {trial_signup_url} {unsubscribe_url}</p>",
            "attach_trial_coupon": True,
            "trial_partner_type": ptype,
        }
        r = requests.post(
            f"{BASE_URL}/api/admin/external-campaigns",
            json=payload,
            headers=auth(admin_token),
            timeout=20,
        )
        assert r.status_code == 200, f"{ptype}: {r.status_code} {r.text}"

    def test_create_campaign_invalid_partner_type_rejected(self, admin_token):
        payload = {
            "name": f"TEST_iter309_bad_{uuid.uuid4().hex[:6]}",
            "subject_en": "x",
            "body_html_en": "<p>{unsubscribe_url}</p>",
            "attach_trial_coupon": True,
            "trial_partner_type": "nonsense",
        }
        r = requests.post(
            f"{BASE_URL}/api/admin/external-campaigns",
            json=payload,
            headers=auth(admin_token),
            timeout=20,
        )
        assert r.status_code in (400, 422), f"expected 4xx, got {r.status_code}: {r.text}"

    def test_activate_partner_trial_coupon(self, admin_token):
        r = requests.post(
            f"{BASE_URL}/api/admin/promotions/activate-trial",
            json={"partner_type": "partner"},
            headers=auth(admin_token),
            timeout=20,
        )
        assert r.status_code == 200, f"got {r.status_code} {r.text}"
        body = r.json()
        coupon = body.get("coupon") or body
        assert coupon.get("duration_days") == 30, coupon
        code = coupon.get("code") or ""
        assert code.startswith("BVX-TRIAL-"), code


# ───────── D2 — Public marketplace hides pending ─────────

class TestD2PublicMarketplaceHidesPending:
    def test_marketplace_returns_only_active(self):
        r = requests.get(f"{BASE_URL}/api/listings", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        items = body if isinstance(body, list) else body.get("listings", body.get("items", []))
        # Every returned listing must be active (no pending_*)
        bad = [it for it in items if it.get("status", "active") not in ("active", None)]
        assert not bad, f"public marketplace exposed non-active listings: {[(b.get('id'), b.get('status')) for b in bad[:5]]}"


# ───────── D1 — Multi-item listing per-lot category aggregate ─────────

class TestD1MultiItemCategories:
    def test_create_multi_item_listing_aggregates_categories(self, seller_token):
        end = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
        payload = {
            "title": f"TEST_iter309_d1_{uuid.uuid4().hex[:6]}",
            "description": "iter309 D1 multi-lot category aggregate test",
            "location": "QC",
            "city": "Sherbrooke",
            "region": "QC",
            "country": "CA",
            "auction_end_date": end,
            "lots": [
                {
                    "lot_number": 1, "title": "Hammer set", "description": "tools desc xxxxxxxxxxxxxxxxxxx",
                    "quantity": 1, "starting_price": 10, "current_price": 10, "condition": "good",
                    "category": "Tools",
                },
                {
                    "lot_number": 2, "title": "Wooden chair", "description": "furniture desc xxxxxxxxxxxxxxxx",
                    "quantity": 1, "starting_price": 20, "current_price": 20, "condition": "good",
                    "category": "Furniture",
                },
            ],
        }
        r = requests.post(
            f"{BASE_URL}/api/multi-item-listings",
            json=payload,
            headers=auth(seller_token),
            timeout=30,
        )
        if r.status_code == 402:
            pytest.skip(f"seller has no payment method on file (payment-gated): {r.text}")
        if r.status_code != 200:
            pytest.fail(f"create multi-item failed: {r.status_code} {r.text}")
        body = r.json()
        cats = body.get("categories") or body.get("listing", {}).get("categories")
        assert cats, f"missing categories aggregate in response: {body}"
        assert "Tools" in cats and "Furniture" in cats, cats
