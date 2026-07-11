"""
iter340 — Tests for:
  P0  Dialer TwiML routing fix (client number dialed, callerId = BidVex main,
      never self-dial, coach stream intact, inbound greeting)
  P1  Share card generation (600×315 PNG, QR, rate limit 429 on 11th)
  P2  Canada-Day promo (registration flags within window, graceful expiry,
      fee-engine guards)
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

os.environ["TWILIO_SKIP_SIGNATURE_VERIFY"] = "1"  # unit tests only — prod enforces

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.twilio as tw_routes
from services.twilio_service import build_outbound_twiml, TWILIO_PHONE_NUMBER
from services.fee_calculator import (
    promo_first_listing_waiver_applies, promo_first_month_waiver_applies,
    canada_day_promo_active,
)
from services.share_card import build_share_card_png, CARD_W, CARD_H

BIDVEX_MAIN = "+14506343099"
CLIENT_NUM = "+15145551234"


def _api_base() -> str:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


API = _api_base() + "/api"


@pytest.fixture(scope="module")
def db():
    client = MongoClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


@pytest.fixture(scope="module")
def twiml_client():
    app = FastAPI()
    app.include_router(tw_routes.router, prefix="/api")
    return TestClient(app)


def _register_user(db, prefix: str, promo_code: str = None):
    email = f"iter340_{prefix}_{uuid.uuid4().hex[:8]}@test.com"
    body = {"email": email, "password": "Iter340Test!@#", "name": f"Iter340 {prefix.title()} User",
            "terms_agreed": True, "ai_disclosure_consent": True}
    if promo_code:
        body["promo_code"] = promo_code
    r = requests.post(f"{API}/auth/register", json=body, timeout=30)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text[:300]}"
    j = r.json()
    token = j.get("access_token") or j.get("token")
    if not token:
        lr = requests.post(f"{API}/auth/login",
                           json={"email": email, "password": "Iter340Test!@#"}, timeout=30)
        token = lr.json().get("access_token")
    user = db.users.find_one({"email": email})
    return {"token": token, "user_id": user["id"], "email": email}


# ═══ P0 — Dialer TwiML routing ══════════════════════════════════════════

class TestDialerTwimlRouting:
    """QA: To=+15145551234 → <Number>+15145551234</Number>,
    callerId always +14506343099, NEVER the main line as destination."""

    def test_build_twiml_dials_client_with_bidvex_caller_id(self):
        xml = build_outbound_twiml(CLIENT_NUM, "https://x/cb", "https://x/rec")
        assert f"<Number" in xml and f">{CLIENT_NUM}</Number>" in xml
        assert f'callerId="{BIDVEX_MAIN}"' in xml
        assert f">{BIDVEX_MAIN}</Number>" not in xml, "main line must NEVER be the dialed destination"

    def test_build_twiml_refuses_self_dial(self):
        with pytest.raises(ValueError, match="self-dial"):
            build_outbound_twiml(BIDVEX_MAIN, "https://x/cb", "https://x/rec")

    def test_coach_stream_still_wires_and_dial_intact(self):
        xml = build_outbound_twiml(CLIENT_NUM, "https://x/cb", "https://x/rec",
                                   coach_stream_url="wss://x/api/twilio/coach-stream",
                                   coach_nonce="nonce-abc")
        assert "<Start>" in xml and "coach-stream" in xml
        assert 'name="nonce"' in xml
        assert f">{CLIENT_NUM}</Number>" in xml, "iter335 stream must not drop the <Dial>"
        assert xml.index("<Start>") < xml.index("<Dial"), "stream must be non-terminal, before Dial"

    def test_twiml_endpoint_sdk_outbound_bridges_client(self, twiml_client):
        r = twiml_client.post("/api/twilio/twiml", data={
            "To": CLIENT_NUM, "From": "client:agent-test-1", "Direction": "outbound-api",
        })
        assert r.status_code == 200, r.text[:200]
        xml = r.text
        assert f">{CLIENT_NUM}</Number>" in xml
        assert f'callerId="{BIDVEX_MAIN}"' in xml
        assert f">{BIDVEX_MAIN}</Number>" not in xml

    def test_twiml_endpoint_rejects_self_dial_from_sdk(self, twiml_client):
        r = twiml_client.post("/api/twilio/twiml", data={
            "To": BIDVEX_MAIN, "From": "client:agent-test-1", "Direction": "outbound-api",
        })
        assert r.status_code == 400
        assert "main number" in r.json()["detail"]

    def test_twiml_endpoint_inbound_greets_never_self_dials(self, twiml_client):
        r = twiml_client.post("/api/twilio/twiml", data={
            "To": BIDVEX_MAIN, "Called": BIDVEX_MAIN,
            "From": "+15140001111", "Direction": "inbound",
        })
        assert r.status_code == 200
        xml = r.text
        assert "<Say" in xml and "<Hangup" in xml
        assert "<Dial" not in xml, "inbound legs must never Dial anything"
        assert f">{BIDVEX_MAIN}</Number>" not in xml

    def test_twiml_endpoint_rejects_invalid_to(self, twiml_client):
        r = twiml_client.post("/api/twilio/twiml", data={
            "To": "not-a-number", "From": "client:agent-test-1",
        })
        assert r.status_code == 400


# ═══ P1 — Share card ════════════════════════════════════════════════════

class TestShareCard:

    def test_card_renders_600x315_png(self):
        png = build_share_card_png(42.50, "https://bidvex.com/r/MARC23", "en")
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(png))
        assert img.size == (CARD_W, CARD_H) == (600, 315)

    def test_card_french_variant_renders(self):
        png = build_share_card_png(0, "https://bidvex.com/r/ABC123", "fr")
        assert png[:8] == b"\x89PNG\r\n\x1a\n"

    def test_endpoint_returns_png_and_rate_limits_11th(self, db):
        u = _register_user(db, "sharecard")
        try:
            h = {"Authorization": f"Bearer {u['token']}"}
            for i in range(10):
                r = requests.get(f"{API}/affiliate/share-card?lang=en", headers=h, timeout=60)
                assert r.status_code == 200, f"gen {i+1}: {r.status_code} {r.text[:200]}"
                assert r.headers["content-type"].startswith("image/png")
                assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
            r11 = requests.get(f"{API}/affiliate/share-card?lang=en", headers=h, timeout=60)
            assert r11.status_code == 429, f"11th should be 429, got {r11.status_code}"
        finally:
            db.users.delete_one({"id": u["user_id"]})
            db.share_card_generations.delete_many({"user_id": u["user_id"]})

    def test_requires_auth(self):
        r = requests.get(f"{API}/affiliate/share-card", timeout=30)
        assert r.status_code in (401, 403)


# ═══ P2 — Canada-Day promo ══════════════════════════════════════════════

class TestCanadaDayPromo:

    def test_registration_within_window_applies_flags(self, db):
        u = _register_user(db, "canadaday", promo_code="canada-day")
        try:
            doc = db.users.find_one({"id": u["user_id"]})
            assert doc.get("first_listing_free") is True
            assert doc.get("first_month_free") is True
            assert doc.get("promo_code_used") == "canada-day"
            assert doc.get("promo_applied_at")
        finally:
            db.users.delete_one({"id": u["user_id"]})

    def test_registration_without_promo_has_no_flags(self, db):
        u = _register_user(db, "nopromo")
        try:
            doc = db.users.find_one({"id": u["user_id"]})
            assert not doc.get("first_listing_free")
            assert not doc.get("first_month_free")
            assert not doc.get("promo_code_used")
        finally:
            db.users.delete_one({"id": u["user_id"]})

    def test_expiry_gate_graceful_after_july_31(self):
        active_now = datetime(2026, 6, 15, tzinfo=timezone.utc)
        last_day = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)
        expired = datetime(2026, 8, 1, 0, 0, 1, tzinfo=timezone.utc)
        assert canada_day_promo_active(active_now) is True
        assert canada_day_promo_active(last_day) is True
        assert canada_day_promo_active(expired) is False

    def test_fee_engine_first_listing_guard(self):
        assert promo_first_listing_waiver_applies({"first_listing_free": True}) is True
        assert promo_first_listing_waiver_applies(
            {"first_listing_free": True, "first_listing_free_used": True}) is False
        assert promo_first_listing_waiver_applies({}) is False
        assert promo_first_listing_waiver_applies(None) is False

    def test_fee_engine_first_month_guard(self):
        assert promo_first_month_waiver_applies({"first_month_free": True}) is True
        assert promo_first_month_waiver_applies(
            {"first_month_free": True, "trial_redeemed_at": "2026-06-01T00:00:00+00:00"}) is False
        assert promo_first_month_waiver_applies({}) is False
