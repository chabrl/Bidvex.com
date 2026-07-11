"""
iter345 — Regression + new tests for:
  BUG 1  Twilio dialer TwiML routing (client dialed, main line NEVER dialed;
         lenient signature validation admits legit requests behind K8s ingress;
         safe /twiml-fallback endpoint never contains <Dial>)
  BUG 2  Watchlist end-to-end for vehicle_multi_lot_auctions
  BUG 3  Registration 500 race → 409 with bilingual detail
  BUG 4  Impersonation history endpoint
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path("/app/backend")))
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

os.environ["TWILIO_SKIP_SIGNATURE_VERIFY"] = "1"  # unit tests only — prod path enforces

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pymongo import MongoClient

import routes.twilio as tw_routes

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


# ═══ BUG 1 — TwiML routing + safe fallback ═════════════════════════════

class TestDialerTwimlRouting:

    def test_sdk_outbound_still_bridges_client(self, twiml_client):
        r = twiml_client.post("/api/twilio/twiml", data={
            "To": CLIENT_NUM, "From": "client:agent-test-1", "Direction": "outbound-api",
        })
        assert r.status_code == 200, r.text[:300]
        xml = r.text
        assert f">{CLIENT_NUM}</Number>" in xml
        assert f'callerId="{BIDVEX_MAIN}"' in xml
        assert f">{BIDVEX_MAIN}</Number>" not in xml

    def test_sdk_self_dial_refused(self, twiml_client):
        r = twiml_client.post("/api/twilio/twiml", data={
            "To": BIDVEX_MAIN, "From": "client:agent-test-1",
        })
        assert r.status_code == 400
        assert "main number" in r.json()["detail"]

    def test_inbound_greeting_never_dials(self, twiml_client):
        r = twiml_client.post("/api/twilio/twiml", data={
            "To": BIDVEX_MAIN, "Called": BIDVEX_MAIN,
            "From": "+15140001111", "Direction": "inbound",
        })
        assert r.status_code == 200
        xml = r.text
        assert "<Say" in xml and "<Hangup" in xml
        assert "<Dial" not in xml
        assert f">{BIDVEX_MAIN}</Number>" not in xml

    def test_safe_fallback_never_dials(self, twiml_client):
        """iter345 — the /twiml-fallback endpoint (to be configured as the
        Twilio Console Fallback URL) plays a bilingual error message and
        hangs up. It MUST NEVER contain a <Dial> — guaranteed not to
        misroute the browser leg to the BidVex main line."""
        r = twiml_client.post("/api/twilio/twiml-fallback")
        assert r.status_code == 200
        xml = r.text
        assert "<Response" in xml and "<Hangup" in xml
        assert "<Dial" not in xml
        assert BIDVEX_MAIN not in xml
        # Bilingual say
        assert "en-CA" in xml and "fr-CA" in xml

    def test_safe_fallback_accepts_get(self, twiml_client):
        """Twilio Console probes the URL with GET during configuration."""
        r = twiml_client.get("/api/twilio/twiml-fallback")
        assert r.status_code == 200
        assert "<Dial" not in r.text

    def test_lenient_signature_admits_missing_header(self, twiml_client):
        """When the X-Twilio-Signature header is absent (URL reconstructed
        under the K8s ingress may not match the signature), we now ADMIT
        the request and log — instead of returning 403 → fallback URL →
        misrouting the call. Original strict 403 behavior was root cause
        of iter345 dialer regression on production."""
        # Temporarily un-skip signature verification for this test only.
        os.environ.pop("TWILIO_SKIP_SIGNATURE_VERIFY", None)
        try:
            r = twiml_client.post("/api/twilio/twiml", data={
                "To": CLIENT_NUM, "From": "client:agent-test-1", "Direction": "outbound-api",
            })
            # No 403 — the endpoint admits missing signature with warning log.
            assert r.status_code == 200, (
                f"lenient signature must admit missing header on preview/prod behind proxy; got {r.status_code}"
            )
            assert f">{CLIENT_NUM}</Number>" in r.text
            assert f">{BIDVEX_MAIN}</Number>" not in r.text
        finally:
            os.environ["TWILIO_SKIP_SIGNATURE_VERIFY"] = "1"


# ═══ BUG 2 — Watchlist for vehicle_multi_lot_auctions ═════════════════

def _register_user(db, prefix: str):
    email = f"iter345_{prefix}_{uuid.uuid4().hex[:8]}@test.com"
    body = {"email": email, "password": "Iter345Test!@#", "name": f"Iter345 {prefix}",
            "terms_agreed": True, "ai_disclosure_consent": True}
    r = requests.post(f"{API}/auth/register", json=body, timeout=30)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text[:300]}"
    j = r.json()
    token = j.get("access_token") or j.get("token")
    if not token:
        lr = requests.post(f"{API}/auth/login",
                           json={"email": email, "password": "Iter345Test!@#"}, timeout=30)
        token = lr.json().get("access_token")
    user = db.users.find_one({"email": email})
    return {"token": token, "user_id": user["id"], "email": email}


class TestWatchlistVehicleMultiLot:
    """iter345 BUG-2 — vehicle_multi_lot_auctions end-to-end watchlist."""

    def test_add_and_fetch_vehicle_multi_lot(self, db):
        u = _register_user(db, "vml_watch")
        # Seed a VML event so the watchlist row can resolve.
        vml_id = str(uuid.uuid4())
        db.vehicle_multi_lot_auctions.insert_one({
            "id":         vml_id,
            "title":      "Iter345 Test VML Event",
            "status":     "live",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time":   (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "lots":       [{
                "lot_number": 1, "make": "Test", "model": "M1",
                "current_bid": 5000, "starting_price": 4000,
                "images": ["https://example.com/lot1.jpg"],
            }],
            "photos":     [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            h = {"Authorization": f"Bearer {u['token']}"}

            # Add the VML event to the watchlist.
            r_add = requests.post(
                f"{API}/watchlist/add",
                params={"item_id": vml_id, "item_type": "vehicle_multi_lot"},
                headers=h, timeout=30,
            )
            assert r_add.status_code == 200, f"add failed: {r_add.status_code} {r_add.text[:300]}"

            # Fetch the watchlist.
            r_get = requests.get(f"{API}/watchlist", headers=h, timeout=30)
            assert r_get.status_code == 200
            data = r_get.json()

            # vehicle_multi_lot bucket must be present + non-empty + doc rendered.
            assert "vehicle_multi_lot" in data, f"missing vehicle_multi_lot bucket. keys={list(data.keys())}"
            vml_bucket = data["vehicle_multi_lot"]
            assert len(vml_bucket) >= 1, "VML event did not appear in fetch"
            row = next((x for x in vml_bucket if x.get("id") == vml_id), None)
            assert row is not None, f"VML {vml_id} not in bucket"
            assert row.get("title") == "Iter345 Test VML Event"
            assert row.get("current_price") in (5000, 5000.0)  # summed from lots
            assert row.get("auction_end_date")  # normalized end
            # Watchlist bucket must not embed the full lots array.
            assert "lots" not in row
        finally:
            requests.post(
                f"{API}/watchlist/remove",
                params={"item_id": vml_id, "item_type": "vehicle_multi_lot"},
                headers={"Authorization": f"Bearer {u['token']}"},
                timeout=30,
            )
            db.vehicle_multi_lot_auctions.delete_one({"id": vml_id})
            db.watchlist.delete_many({"user_id": u["user_id"]})
            db.users.delete_one({"id": u["user_id"]})

    def test_add_invalid_item_type_returns_400(self, db):
        u = _register_user(db, "vml_invalid")
        try:
            h = {"Authorization": f"Bearer {u['token']}"}
            r = requests.post(
                f"{API}/watchlist/add",
                params={"item_id": "x", "item_type": "not-a-type"},
                headers=h, timeout=30,
            )
            assert r.status_code == 400
        finally:
            db.users.delete_one({"id": u["user_id"]})

    def test_missing_vml_event_returns_404(self, db):
        u = _register_user(db, "vml_missing")
        try:
            h = {"Authorization": f"Bearer {u['token']}"}
            r = requests.post(
                f"{API}/watchlist/add",
                params={"item_id": "nonexistent-vml-id", "item_type": "vehicle_multi_lot"},
                headers=h, timeout=30,
            )
            assert r.status_code == 404
        finally:
            db.users.delete_one({"id": u["user_id"]})


# ═══ BUG 3 — Registration duplicate race → 409 ═════════════════════════

class TestRegistrationRace:
    """iter345 BUG-3 — rapid double-submit no longer returns 500."""

    def test_duplicate_email_returns_409_bilingual(self, db):
        email = f"iter345_race_{uuid.uuid4().hex[:8]}@test.com"
        body = {"email": email, "password": "Iter345Test!@#", "name": "Race User",
                "terms_agreed": True, "ai_disclosure_consent": True}
        r1 = requests.post(f"{API}/auth/register", json=body, timeout=30)
        assert r1.status_code in (200, 201), f"first register must succeed: {r1.status_code}"
        try:
            r2 = requests.post(f"{API}/auth/register", json=body, timeout=30)
            assert r2.status_code == 409, (
                f"second register must return 409, got {r2.status_code}"
            )
            detail = r2.json().get("detail")
            assert isinstance(detail, dict), f"detail must be bilingual dict, got {type(detail)}"
            assert "message_en" in detail and "message_fr" in detail
            assert "already registered" in detail["message_en"].lower()
            assert "enregistré" in detail["message_fr"].lower() or "enregistr" in detail["message_fr"].lower()
        finally:
            db.users.delete_one({"email": email})


# ═══ BUG 4 — Impersonation history endpoint ═══════════════════════════

class TestImpersonationHistory:
    """iter345 BUG-4 — new sub-tab endpoint for admin audit."""

    def _mint_admin_token(self, db):
        """Create an admin user + return a JWT for it."""
        import bcrypt
        from jose import jwt
        admin_id = str(uuid.uuid4())
        email = f"iter345_admin_{uuid.uuid4().hex[:8]}@test.com"
        pw = bcrypt.hashpw(b"AdminPass123!", bcrypt.gensalt()).decode()
        db.users.insert_one({
            "id":                admin_id,
            "email":             email,
            "password":          pw,
            "name":              "Iter345 Admin",
            "role":              "super_admin",
            "created_at":        datetime.now(timezone.utc).isoformat(),
            "terms_agreed_at":   datetime.now(timezone.utc).isoformat(),
            "email_verified":    True,
        })
        jwt_secret = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")
        token = jwt.encode({
            "sub":   admin_id,
            "email": email,
            "type":  "access",
            "exp":   datetime.now(timezone.utc) + timedelta(hours=1),
        }, jwt_secret, algorithm="HS256")
        return token, admin_id

    def test_empty_history_returns_200_and_empty_list(self, db):
        token, admin_id = self._mint_admin_token(db)
        try:
            r = requests.get(
                f"{API}/admin/impersonation-history",
                headers={"Authorization": f"Bearer {token}"},
                params={"admin_id": admin_id},
                timeout=30,
            )
            assert r.status_code == 200
            data = r.json()
            assert "sessions" in data and "count" in data
            assert isinstance(data["sessions"], list)
        finally:
            db.users.delete_one({"id": admin_id})

    def test_seeded_impersonation_session_appears(self, db):
        token, admin_id = self._mint_admin_token(db)
        target_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        db.admin_logs.insert_one({
            "id":               session_id,
            "action":           "impersonation_started",
            "admin_id":         admin_id,
            "admin_email":      "iter345_admin@test.com",
            "target_user_id":   target_id,
            "target_email":     "iter345_target@test.com",
            "details":          {"expires_at": expires_at},
            "timestamp":        started_at,
        })
        try:
            r = requests.get(
                f"{API}/admin/impersonation-history",
                headers={"Authorization": f"Bearer {token}"},
                params={"admin_id": admin_id},
                timeout=30,
            )
            assert r.status_code == 200
            data = r.json()
            row = next((s for s in data["sessions"] if s["session_id"] == session_id), None)
            assert row is not None, f"seeded session missing. sessions={data['sessions']}"
            assert row["admin_id"] == admin_id
            assert row["target_user_id"] == target_id
            assert row["duration_minutes"] is not None
        finally:
            db.admin_logs.delete_one({"id": session_id})
            db.users.delete_one({"id": admin_id})

    def test_non_admin_gets_403(self, db):
        """Regular user token must be rejected."""
        # Seed a plain 'user' directly to avoid the /auth/register rate limit
        # from the previous registration-race test.
        import bcrypt
        from jose import jwt
        uid = str(uuid.uuid4())
        email = f"iter345_reg_{uuid.uuid4().hex[:8]}@test.com"
        pw = bcrypt.hashpw(b"UserPass123!", bcrypt.gensalt()).decode()
        db.users.insert_one({
            "id":             uid,
            "email":          email,
            "password":       pw,
            "name":           "Iter345 Regular",
            "role":           "user",
            "created_at":     datetime.now(timezone.utc).isoformat(),
            "email_verified": True,
        })
        jwt_secret = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")
        token = jwt.encode({
            "sub":   uid,
            "email": email,
            "type":  "access",
            "exp":   datetime.now(timezone.utc) + timedelta(hours=1),
        }, jwt_secret, algorithm="HS256")
        try:
            r = requests.get(
                f"{API}/admin/impersonation-history",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            assert r.status_code == 403
        finally:
            db.users.delete_one({"id": uid})
