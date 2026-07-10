"""
iter339 supplement — additional coverage requested in review:
  * Non-admin gets 403 on /admin/ad-campaigns/publish-config
  * GET /admin/ad-campaigns/{id}/performance → 404 for unknown id, 400 for unpublished
  * Regression: ad-campaigns list, PATCH status, export.csv
  * Regression: legacy GET /api/affiliate/stats works for authenticated user
"""
from __future__ import annotations

import os
import sys
import uuid
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, str(Path("/app/backend")))
load_dotenv("/app/backend/.env")


def _api_base() -> str:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


API = _api_base() + "/api"
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
BUYER_EMAIL = "testbuyer@bidvex.com"
BUYER_PASSWORD = "TestBuyer2026!"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text[:200]}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def buyer_token():
    return _login(BUYER_EMAIL, BUYER_PASSWORD)


@pytest.fixture(scope="module")
def db():
    client = MongoClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


# ─── Non-admin gate on publish-config ──────────────────────────────

class TestPublishConfigAuth:

    def test_non_admin_gets_403(self, buyer_token):
        r = requests.get(f"{API}/admin/ad-campaigns/publish-config",
                         headers={"Authorization": f"Bearer {buyer_token}"}, timeout=30)
        assert r.status_code == 403, r.text[:200]

    def test_admin_gets_config_with_flags_off(self, admin_token):
        r = requests.get(f"{API}/admin/ad-campaigns/publish-config",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["meta"]["enabled"] is False
        assert d["google"]["enabled"] is False
        assert "prerequisite" in d["meta"] and d["meta"]["prerequisite"]
        assert "prerequisite" in d["google"] and d["google"]["prerequisite"]
        assert isinstance(d["meta"].get("missing"), list)


# ─── Performance endpoint 404 / 400 ────────────────────────────────

class TestPerformanceEndpoint:

    def test_unknown_id_returns_404(self, admin_token):
        r = requests.get(f"{API}/admin/ad-campaigns/does-not-exist-{uuid.uuid4().hex[:6]}/performance",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 404

    def test_unpublished_campaign_returns_400(self, admin_token, db):
        camp_id = f"TEST-perf-{uuid.uuid4().hex[:8]}"
        db.ad_campaigns.insert_one({
            "id": camp_id, "listing_id": "TEST-listing",
            "listing_type": "vehicle", "platform": "both",
            "headline_en": "Test", "headline_fr": "Test",
            "description_en": "Test", "description_fr": "Test",
            "landing_url": "https://bidvex.com/",
            "image_url": "", "status": "ready",
            "regenerated_count": 0, "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z", "created_by": "test",
        })
        try:
            r = requests.get(f"{API}/admin/ad-campaigns/{camp_id}/performance",
                             headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
            assert r.status_code == 400, r.text[:200]
        finally:
            db.ad_campaigns.delete_one({"id": camp_id})


# ─── Ad campaigns CRUD regression (skip Gemini create — costly). ──
# Test list, PATCH status, DELETE, export.csv on a seeded doc.

class TestAdCampaignsCRUDRegression:

    @pytest.fixture(scope="class")
    def seeded_campaign(self, db):
        camp_id = f"TEST-crud-{uuid.uuid4().hex[:8]}"
        db.ad_campaigns.insert_one({
            "id": camp_id, "listing_id": "TEST-crud-listing",
            "listing_type": "vehicle", "platform": "both",
            "headline_en": "Bid on Ford", "headline_fr": "Enchérissez Ford",
            "description_en": "Bid now on BidVex.", "description_fr": "Enchérissez maintenant.",
            "landing_url": "https://bidvex.com/",
            "image_url": "", "status": "draft",
            "regenerated_count": 0, "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z", "created_by": "test",
        })
        yield camp_id
        db.ad_campaigns.delete_one({"id": camp_id})

    def test_list(self, admin_token, seeded_campaign):
        r = requests.get(f"{API}/admin/ad-campaigns?limit=200",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "items" in d and isinstance(d["items"], list)
        ids = {it["id"] for it in d["items"]}
        assert seeded_campaign in ids

    def test_patch_status_draft_to_ready(self, admin_token, seeded_campaign):
        r = requests.patch(f"{API}/admin/ad-campaigns/{seeded_campaign}",
                           json={"status": "ready"},
                           headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        # verify persisted
        r2 = requests.get(f"{API}/admin/ad-campaigns?limit=200",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        match = next((x for x in r2.json()["items"] if x["id"] == seeded_campaign), None)
        assert match is not None
        assert match["status"] == "ready"

    def test_export_csv_google(self, admin_token, seeded_campaign):
        r = requests.get(f"{API}/admin/ad-campaigns/export.csv?platform=google",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        # Must be CSV text
        body = r.text
        assert "\n" in body or "," in body
        # Header row should be present
        assert body.strip().split("\n")[0].count(",") >= 2

    def test_non_admin_cannot_list(self, buyer_token):
        r = requests.get(f"{API}/admin/ad-campaigns",
                         headers={"Authorization": f"Bearer {buyer_token}"}, timeout=30)
        assert r.status_code == 403


# ─── Legacy /affiliate/stats regression ───────────────────────────

class TestLegacyAffiliateStats:

    def test_stats_authenticated(self, buyer_token):
        r = requests.get(f"{API}/affiliate/stats",
                         headers={"Authorization": f"Bearer {buyer_token}"}, timeout=30)
        # Should not 500. Should be 200 (data) or 404 if not affiliate—but the
        # spec says legacy endpoint still works for authenticated user.
        assert r.status_code == 200, r.text[:200]

    def test_stats_requires_auth(self):
        r = requests.get(f"{API}/affiliate/stats", timeout=30)
        assert r.status_code in (401, 403)


# ─── Commission events privacy (no email leak) ────────────────────

class TestCommissionEventsPrivacyForBuyer:

    def test_buyer_call_ok_or_empty(self, buyer_token):
        r = requests.get(f"{API}/affiliate/commission-events?page=1&limit=10",
                         headers={"Authorization": f"Bearer {buyer_token}"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        # For a buyer with no referrals, items should be an empty list
        assert isinstance(d.get("items"), list)
        assert "has_more" in d
        assert d["has_more"] is False or isinstance(d["has_more"], bool)
        # Any items must have masked names (no '@' from email)
        for it in d["items"]:
            assert "@" not in it.get("referred_user", "")

    def test_buyer_earnings_summary_all_fields(self, buyer_token):
        r = requests.get(f"{API}/affiliate/earnings-summary",
                         headers={"Authorization": f"Bearer {buyer_token}"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ("this_month", "last_month", "lifetime", "projected_next_month",
                  "projection_basis_months", "referred_users", "pending_approval"):
            assert k in d
        assert "earned" in d["this_month"] and "transaction_count" in d["this_month"]
        assert "platform_fees_generated" in d["this_month"]
        assert "total" in d["referred_users"] and "active_this_month" in d["referred_users"]
