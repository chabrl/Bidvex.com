"""
iter341 — Tests for:
  P0  Summer Grand Opening campaign (SUMMER2026 valid until Aug 31 / expired
      canada-day graceful, registration flags, promo_source_url attribution)
  P0  OG card (1200×628 PNG, served publicly without auth, crawler share page)
  P1  Prospect Finder (503 flag gate, cache hit, already_in_bidvex matching)
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, str(Path("/app/backend")))
load_dotenv("/app/backend/.env")

from services.fee_calculator import promo_code_active, get_promo_definition
from services.og_card import OG_CARD_PATH, OG_W, OG_H
from services.prospect_finder import (
    maps_flag, normalize_phone, normalize_business_name, TYPE_QUERIES,
)


def _api_base() -> str:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


BASE = _api_base()
API = BASE + "/api"


@pytest.fixture(scope="module")
def db():
    client = MongoClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


@pytest.fixture(scope="module")
def contractor_token():
    # admin has dialer access
    r = requests.post(f"{API}/auth/login",
                      json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
                      timeout=30)
    assert r.status_code == 200, r.text[:200]
    return r.json().get("access_token") or r.json().get("token")


# ═══ P0 — Summer campaign gates ═════════════════════════════════════════

class TestSummerCampaign:

    def test_summer2026_valid_before_aug_31_invalid_after(self):
        before = datetime(2026, 7, 10, tzinfo=timezone.utc)
        last_day = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
        after = datetime(2026, 9, 1, 0, 0, 1, tzinfo=timezone.utc)
        assert promo_code_active("SUMMER2026", before) is True
        assert promo_code_active("summer2026", last_day) is True
        assert promo_code_active("summer2026", after) is False

    def test_canada_day_retired(self):
        now = datetime(2026, 7, 10, tzinfo=timezone.utc)
        assert promo_code_active("canada-day", now) is False
        assert get_promo_definition("canada-day") is not None  # kept for messaging

    def test_registration_summer2026_applies_flags_and_source_url(self, db):
        email = f"iter341_summer_{uuid.uuid4().hex[:8]}@test.com"
        r = requests.post(f"{API}/auth/register", json={
            "email": email, "password": "Iter341Test!@#", "name": "Iter341 Summer",
            "terms_agreed": True, "ai_disclosure_consent": True,
            "promo_code": "SUMMER2026",
            "promo_source_url": "https://bidvex.com/promo/summer-launch",
        }, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        doc = db.users.find_one({"email": email})
        try:
            assert doc.get("first_listing_free") is True
            assert doc.get("first_month_free") is True
            assert doc.get("promo_code_used") == "summer2026"
            assert doc.get("promo_source_url") == "https://bidvex.com/promo/summer-launch"
        finally:
            db.users.delete_one({"id": doc["id"]})

    def test_registration_expired_canada_day_no_flags_but_attribution_kept(self, db):
        email = f"iter341_expired_{uuid.uuid4().hex[:8]}@test.com"
        r = requests.post(f"{API}/auth/register", json={
            "email": email, "password": "Iter341Test!@#", "name": "Iter341 Expired",
            "terms_agreed": True, "ai_disclosure_consent": True,
            "promo_code": "canada-day",
            "promo_source_url": "https://bidvex.com/promo/canada-day",
        }, timeout=30)
        assert r.status_code in (200, 201), "expired promo must NOT block registration"
        doc = db.users.find_one({"email": email})
        try:
            assert not doc.get("first_listing_free")
            assert not doc.get("first_month_free")
            assert not doc.get("promo_code_used")
            assert doc.get("promo_source_url") == "https://bidvex.com/promo/canada-day"
        finally:
            db.users.delete_one({"id": doc["id"]})


# ═══ P0 — OG card ═══════════════════════════════════════════════════════

class TestOgCard:

    def test_file_generated_1200x628(self):
        assert os.path.exists(OG_CARD_PATH), "startup generation must write the card"
        from PIL import Image
        img = Image.open(OG_CARD_PATH)
        assert img.size == (OG_W, OG_H) == (1200, 628)

    def test_served_publicly_no_auth(self):
        r = requests.get(f"{BASE}/static/og/summer-launch-promo.png", timeout=30)
        assert r.status_code == 200
        assert "image/png" in r.headers.get("content-type", "")
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"

    def test_crawler_share_page_has_og_tags(self):
        r = requests.get(f"{API}/promo/share/summer-launch", timeout=30)
        assert r.status_code == 200
        html = r.text
        assert 'og:image" content="https://bidvex.com/static/og/summer-launch-promo.png"' in html
        assert 'og:image:width" content="1200"' in html
        assert 'og:image:height" content="628"' in html
        assert 'twitter:card" content="summary_large_image"' in html
        assert "0;url=https://bidvex.com/promo/summer-launch" in html


# ═══ P1 — Prospect Finder ═══════════════════════════════════════════════

class TestProspectFinder:

    def test_flag_disabled_without_key(self):
        assert os.environ.get("GOOGLE_MAPS_API_KEY", "") == ""
        flag = maps_flag()
        assert flag["enabled"] is False
        assert "GOOGLE_MAPS_API_KEY" in flag["missing"]
        assert "Emergent environment configuration" in flag["prerequisite"]

    def test_endpoint_503_when_flag_off(self, contractor_token):
        r = requests.get(f"{API}/contractor/prospect-finder?city=Montreal&type=vehicle_dealer",
                         headers={"Authorization": f"Bearer {contractor_token}"}, timeout=30)
        assert r.status_code == 503, r.text[:200]
        assert "GOOGLE_MAPS_API_KEY" in r.json()["detail"]

    def test_config_endpoint_exposes_flag_and_billing_note(self, contractor_token):
        r = requests.get(f"{API}/contractor/prospect-finder/config",
                         headers={"Authorization": f"Bearer {contractor_token}"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["enabled"] is False
        assert "0.035" in d["billing_note"]
        assert set(d["types"]) == set(TYPE_QUERIES.keys())

    def test_requires_dialer_access(self):
        r = requests.get(f"{API}/contractor/prospect-finder?city=Montreal&type=vehicle_dealer",
                         timeout=30)
        assert r.status_code in (401, 403)

    def test_cache_hit_and_already_in_bidvex(self, db, contractor_token):
        """With the key set in-process, a seeded 24h cache entry is served
        without any Google call, and already_in_bidvex flags a seeded user."""
        os.environ["GOOGLE_MAPS_API_KEY"] = "test-key-not-used-cache-path"
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            from routes.contractor_prospects import router
            import routes.contractor_prospects as cp
            import deps

            seeded_user = {
                "id": f"iter341-biz-{uuid.uuid4().hex[:6]}",
                "email": f"iter341_biz_{uuid.uuid4().hex[:6]}@test.com",
                "name": "Montreal Auto Galerie",
                "company_name": "Montreal Auto Galerie Inc.",
                "phone": "+15145559876",
                "role": "seller",
            }
            db.users.insert_one(seeded_user)
            cache_key = "testville|vehicle_dealer|25"
            db.prospect_finder_cache.update_one({"key": cache_key}, {"$set": {
                "key": cache_key,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "results": [
                    {"name": "Montreal Auto Galerie", "address": "1 Rue Test, Testville QC",
                     "phone": "(514) 555-9876", "website": "https://mag.example.com",
                     "rating": 4.5, "review_count": 87, "place_id": "pid-1",
                     "google_maps_url": "https://maps.google.com/?cid=1"},
                    {"name": "Fresh Prospect Motors", "address": "2 Rue Test, Testville QC",
                     "phone": "(438) 555-0000", "website": "", "rating": 4.0,
                     "review_count": 12, "place_id": "pid-2",
                     "google_maps_url": "https://maps.google.com/?cid=2"},
                ],
            }}, upsert=True)

            app = FastAPI()
            app.include_router(router, prefix="/api")
            # bypass auth dep — cache/matching logic is what's under test
            from routes.twilio import require_dialer_access
            app.dependency_overrides[require_dialer_access] = lambda: type(
                "U", (), {"id": "test-user", "role": "admin"})()
            # deps.get_db global is only set during server startup — override
            from motor.motor_asyncio import AsyncIOMotorClient
            motor_db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
            app.dependency_overrides[deps.get_db] = lambda: motor_db
            client = TestClient(app)
            r = client.get("/api/contractor/prospect-finder?city=Testville&type=vehicle_dealer&radius_km=25")
            assert r.status_code == 200, r.text[:300]
            d = r.json()
            assert d["cached"] is True, "second identical query must hit the 24h cache"
            assert d["total"] == 2
            by_name = {i["name"]: i for i in d["items"]}
            assert by_name["Montreal Auto Galerie"]["already_in_bidvex"] is True
            assert by_name["Fresh Prospect Motors"]["already_in_bidvex"] is False
        finally:
            os.environ["GOOGLE_MAPS_API_KEY"] = ""
            db.users.delete_one({"id": seeded_user["id"]})
            db.prospect_finder_cache.delete_many({"key": "testville|vehicle_dealer|25"})

    def test_phone_and_name_normalizers(self):
        assert normalize_phone("(514) 555-9876") == "5145559876"
        assert normalize_phone("+1 514-555-9876") == "5145559876"
        assert normalize_business_name("Montreal Auto Galerie Inc.") == "montreal auto galerie"
        assert normalize_business_name("Dépôt Liquidation Ltée") == "d p t liquidation"
