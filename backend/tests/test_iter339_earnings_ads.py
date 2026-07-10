"""
iter339 — Tests for:
  1. GET /api/affiliate/earnings-summary — required fields + correct lifetime total
  2. Projection calculation (3-month avg + fewer-months basis)
  3. Commission-events feed — privacy-masked names
  4. Meta publish payload builders (pure, mocked — no API call) + feature flag 503
  5. Google RSA headline generation stays under 30 chars
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, str(Path("/app/backend")))
load_dotenv("/app/backend/.env")

from routes.affiliate import mask_referred_name, compute_projection, _shift_month
from routes.ad_campaigns import _gclip, _fallback_google_variants, GOOGLE_HEADLINE_MAX, GOOGLE_DESCRIPTION_MAX
from services.ads_publisher import (
    build_meta_creative_payload, build_meta_adset_targeting, meta_flag, google_flag,
)


def _api_base() -> str:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


API = _api_base() + "/api"
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


@pytest.fixture(scope="module")
def db():
    client = MongoClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def affiliate_user(db):
    """Fresh registered user with seeded platform_credits across 3 months."""
    email = f"iter339_aff_{uuid.uuid4().hex[:8]}@test.com"
    password = "Iter339Test!@#"
    r = requests.post(f"{API}/auth/register",
                      json={"email": email, "password": password, "name": "Iter339 Affiliate",
                            "terms_agreed": True, "ai_disclosure_consent": True},
                      timeout=30)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text[:300]}"
    body = r.json()
    token = body.get("access_token") or body.get("token") or _login(email, password)
    user = db.users.find_one({"email": email})
    assert user, "registered user not found in Mongo"
    uid = user["id"]

    now = datetime.now(timezone.utc)
    m1 = now - timedelta(days=32)   # last month
    m2 = now - timedelta(days=62)   # two months ago
    payer_id = f"iter339-payer-{uuid.uuid4().hex[:6]}"
    seeds = [
        # two months ago — $10 (3% of $333.33), paid
        {"amount": 10.00, "commission_base": 333.33, "created_at": m2.isoformat(),
         "status": "paid", "revenue_source": "auction_seller_fee",
         "referred_user_name": "Sarah Tremblay", "referred_user_id": "payer-old-1"},
        # last month — $20, paid
        {"amount": 20.00, "commission_base": 666.67, "created_at": m1.isoformat(),
         "status": "paid", "revenue_source": "auction_buyer_fee",
         "referred_user_name": "Marc Dubois", "referred_user_id": "payer-old-2"},
        # this month — $5 pending (referred user active this month)
        {"amount": 5.00, "commission_base": 166.67, "created_at": now.isoformat(),
         "status": "pending", "revenue_source": "auction_buyer_fee",
         "referred_user_name": "Alex Boulanger", "referred_user_id": payer_id},
    ]
    ids = []
    for s in seeds:
        doc = {
            "id": f"REF-TEST-{uuid.uuid4().hex[:8]}",
            "user_id": uid,
            "currency": "CAD",
            "source": "referral",
            "commission_rate": 0.03,
            "reference_id": f"iter339-{uuid.uuid4().hex[:6]}",
            "description": "iter339 test seed",
            **s,
        }
        db.platform_credits.insert_one(doc)
        ids.append(doc["id"])

    yield {"token": token, "user_id": uid, "email": email}
    db.platform_credits.delete_many({"id": {"$in": ids}})
    db.users.delete_one({"id": uid})


# ─── 1. Earnings summary ────────────────────────────────────────────────

class TestEarningsSummary:

    def test_all_required_fields_and_lifetime_total(self, affiliate_user):
        r = requests.get(f"{API}/affiliate/earnings-summary",
                         headers={"Authorization": f"Bearer {affiliate_user['token']}"},
                         timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for key in ("this_month", "last_month", "lifetime", "projected_next_month",
                    "projection_basis_months", "referred_users", "pending_approval"):
            assert key in d, f"missing field {key}"
        assert d["lifetime"]["earned"] == pytest.approx(35.00)
        assert d["lifetime"]["transaction_count"] == 3
        assert d["this_month"]["earned"] == pytest.approx(5.00)
        assert d["this_month"]["transaction_count"] == 1
        assert d["this_month"]["platform_fees_generated"] == pytest.approx(166.67)
        assert d["last_month"]["earned"] == pytest.approx(20.00)
        assert d["pending_approval"] == pytest.approx(5.00)
        assert d["referred_users"]["active_this_month"] == 1
        assert isinstance(d["referred_users"]["total"], int)
        assert d["projection_basis_months"] >= 1

    def test_requires_auth(self):
        r = requests.get(f"{API}/affiliate/earnings-summary", timeout=30)
        assert r.status_code in (401, 403)


# ─── 2. Projection calculation ──────────────────────────────────────────

class TestProjection:

    def test_three_full_months_average(self):
        now = datetime(2026, 6, 15, tzinfo=timezone.utc)
        prev1 = _shift_month(2026, 6, -1)
        prev2 = _shift_month(2026, 6, -2)
        prev3 = _shift_month(2026, 6, -3)
        monthly = {prev1: 30.0, prev2: 20.0, prev3: 10.0}
        projection, basis = compute_projection(monthly, now)
        assert basis == 3
        assert projection == pytest.approx(20.0)

    def test_fewer_months_uses_available_and_notes_basis(self):
        now = datetime(2026, 6, 15, tzinfo=timezone.utc)
        prev1 = _shift_month(2026, 6, -1)
        monthly = {prev1: 12.0}
        projection, basis = compute_projection(monthly, now)
        assert basis == 1
        assert projection == pytest.approx(12.0)

    def test_only_current_month_data(self):
        now = datetime(2026, 6, 15, tzinfo=timezone.utc)
        monthly = {(2026, 6): 9.0}
        projection, basis = compute_projection(monthly, now)
        assert basis == 1
        assert projection == pytest.approx(9.0)

    def test_no_data(self):
        projection, basis = compute_projection({}, datetime.now(timezone.utc))
        assert projection == 0.0 and basis == 0

    def test_year_boundary_month_shift(self):
        assert _shift_month(2026, 1, -1) == (2025, 12)
        assert _shift_month(2026, 2, -3) == (2025, 11)


# ─── 3. Commission-events feed — masked names ───────────────────────────

class TestCommissionEvents:

    def test_mask_helper(self):
        assert mask_referred_name("Alex Boulanger") == "Alex B."
        assert mask_referred_name("Sarah Tremblay") == "Sarah T."
        assert mask_referred_name("Madonna") == "Madonna"
        assert mask_referred_name("") == "User"
        assert mask_referred_name("jean marc dupont") == "jean M."

    def test_feed_masks_names_and_shows_amounts(self, affiliate_user):
        r = requests.get(f"{API}/affiliate/commission-events?page=1&limit=10",
                         headers={"Authorization": f"Bearer {affiliate_user['token']}"},
                         timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["total"] == 3
        assert len(d["items"]) == 3
        names = {it["referred_user"] for it in d["items"]}
        assert names == {"Alex B.", "Marc D.", "Sarah T."}
        for it in d["items"]:
            assert "Boulanger" not in it["referred_user"]
            assert "@" not in it["referred_user"]
            assert it["status"] in ("pending", "paid", "approved")
            assert it["commission"] > 0
        newest = d["items"][0]
        assert newest["referred_user"] == "Alex B."
        assert newest["platform_fee"] == pytest.approx(166.67)
        assert newest["commission"] == pytest.approx(5.00)

    def test_pagination_has_more_flag(self, affiliate_user):
        r = requests.get(f"{API}/affiliate/commission-events?page=1&limit=2",
                         headers={"Authorization": f"Bearer {affiliate_user['token']}"},
                         timeout=30)
        d = r.json()
        assert len(d["items"]) == 2 and d["has_more"] is True
        r2 = requests.get(f"{API}/affiliate/commission-events?page=2&limit=2",
                          headers={"Authorization": f"Bearer {affiliate_user['token']}"},
                          timeout=30)
        d2 = r2.json()
        assert len(d2["items"]) == 1 and d2["has_more"] is False


# ─── 4. Meta publish payloads (mocked/pure) + feature flag gating ───────

class TestMetaPublish:

    CAMPAIGN = {
        "id": "test-camp", "listing_id": "lst-123",
        "headline_en": "Bid now: 2021 Ford F-150", "headline_fr": "Enchérissez : Ford F-150 2021",
        "description_en": "Live on BidVex — bid on this truck today.",
        "description_fr": "En direct sur BidVex — enchérissez dès aujourd'hui.",
        "landing_url": "https://bidvex.com/vehicle-auctions/lst-123",
        "image_url": "https://example.com/img.jpg",
    }

    def test_creative_payload_structure_en(self):
        p = build_meta_creative_payload(self.CAMPAIGN, "en", page_id="PAGE123")
        spec = p["object_story_spec"]
        assert spec["page_id"] == "PAGE123"
        ld = spec["link_data"]
        assert ld["name"] == "Bid now: 2021 Ford F-150"
        assert ld["message"].startswith("Live on BidVex")
        assert ld["link"] == "https://bidvex.com/vehicle-auctions/lst-123"
        assert ld["call_to_action"]["type"] == "LEARN_MORE"
        assert ld["call_to_action"]["value"]["link"] == ld["link"]

    def test_creative_payload_uses_french_copy(self):
        p = build_meta_creative_payload(self.CAMPAIGN, "fr", page_id="PAGE123")
        ld = p["object_story_spec"]["link_data"]
        assert ld["name"].startswith("Enchérissez")
        assert "En direct" in ld["message"]

    def test_adset_targeting_canada_25_55_interests(self):
        t = build_meta_adset_targeting(["111", "222"])
        assert t["geo_locations"]["countries"] == ["CA"]
        assert t["age_min"] == 25 and t["age_max"] == 55
        interests = t["flexible_spec"][0]["interests"]
        assert {i["id"] for i in interests} == {"111", "222"}

    def test_feature_flags_disabled_without_env(self):
        assert meta_flag()["enabled"] is False
        assert "META_ACCESS_TOKEN" in meta_flag()["missing"]
        assert google_flag()["enabled"] is False
        assert "GOOGLE_ADS_DEVELOPER_TOKEN" in google_flag()["missing"]

    def test_publish_endpoints_return_503_when_flag_off(self, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.post(f"{API}/admin/ad-campaigns/nonexistent/publish/meta",
                          json={"language": "en"}, headers=h, timeout=30)
        assert r.status_code == 503, r.text[:200]
        r2 = requests.post(f"{API}/admin/ad-campaigns/nonexistent/publish/google",
                           json={"google_campaign_id": "1", "google_ad_group_id": "2"},
                           headers=h, timeout=30)
        assert r2.status_code == 503, r2.text[:200]

    def test_publish_config_endpoint(self, admin_token):
        r = requests.get(f"{API}/admin/ad-campaigns/publish-config",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert d["meta"]["enabled"] is False and d["google"]["enabled"] is False
        assert d["meta"]["prerequisite"] and d["google"]["prerequisite"]


# ─── 5. Google RSA headline generation ≤ 30 chars ───────────────────────

class TestGoogleRsaVariants:

    def test_fallback_variants_respect_caps_en(self):
        heads, descs = _fallback_google_variants(
            "Bid now: 2021 Ford F-150 XLT SuperCrew 4x4",  # 42 chars — over cap
            "Live on BidVex — bid on this fully-loaded truck today with no reserve and free pickup available.",
            "en")
        assert len(heads) == 3 and len(descs) == 2
        for h in heads:
            assert len(h) <= GOOGLE_HEADLINE_MAX, f"headline over 30: {h!r} ({len(h)})"
            assert "…" not in h
        for d in descs:
            assert len(d) <= GOOGLE_DESCRIPTION_MAX, f"description over 90: {d!r}"
            assert "…" not in d

    def test_fallback_variants_respect_caps_fr(self):
        heads, descs = _fallback_google_variants(
            "Enchérissez : Ford F-150 2021 XLT SuperCrew",
            "En direct sur BidVex — enchérissez sur ce camion entièrement équipé dès aujourd'hui sans réserve.",
            "fr")
        assert len(heads) == 3 and len(descs) == 2
        assert all(len(h) <= 30 for h in heads)
        assert all(len(d) <= 90 for d in descs)

    def test_gclip_word_boundary_no_ellipsis(self):
        assert _gclip("Short", 30) == "Short"
        clipped = _gclip("This is a very long headline that exceeds the cap", 30)
        assert len(clipped) <= 30
        assert "…" not in clipped
        assert not clipped.endswith(" ")

    def test_headlines_deduped_and_padded(self):
        heads, descs = _fallback_google_variants("Bid Live on BidVex", "Bid now on BidVex — Canada's online auction marketplace.", "en")
        assert len(heads) == 3
        assert len(set(heads)) == 3, f"duplicate headlines: {heads}"
        assert len(descs) == 2 and len(set(descs)) == 2
