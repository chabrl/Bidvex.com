"""
iter347 — Tests for:
  ISSUE 1  Feed image validation relaxation (S3/CDN URLs pass) +
           presigned-URL rejection + /api/feeds/refresh admin endpoint.
  ISSUE 2  Single-step bilingual IVR at /api/twilio/ivr/main-menu +
           /api/twilio/handle-menu dispatcher.
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

os.environ["TWILIO_SKIP_SIGNATURE_VERIFY"] = "1"

from pymongo import MongoClient

# Feed mapper unit-level tests import the module directly.
from services.meta_feed_mapper import _is_valid_image_url, _first_valid_image
from services.google_feed_mapper import _sanitize_google_image_url


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


def _mint_admin_token(db, prefix: str = "iter347_admin"):
    import bcrypt
    from jose import jwt
    uid = str(uuid.uuid4())
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"
    pw = bcrypt.hashpw(b"AdminPass123!", bcrypt.gensalt()).decode()
    db.users.insert_one({
        "id":             uid,
        "email":          email,
        "password":       pw,
        "name":           "Iter347 Admin",
        "role":           "super_admin",
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
    return token, uid, email


# ═══ ISSUE 1 — Feed image validation ═══════════════════════════════════

class TestFeedImageValidation:
    """iter347 — Relax _is_valid_image_url to admit modern CDN URLs +
    reject presigned URLs."""

    def test_s3_public_url_with_jpg_extension_passes(self):
        u = "https://bidvex-marketplace-images.s3.us-east-2.amazonaws.com/listings/abc123/00-a1b2c3d4.jpg"
        assert _is_valid_image_url(u), f"S3 public URL must pass, got False: {u}"
        assert _sanitize_google_image_url(u) == u

    def test_cloudfront_url_no_extension_passes(self):
        """Modern CDN URLs without extensions — Content-Type resolves at
        crawler fetch time. Was silently rejected pre-iter347."""
        u = "https://d1234abc.cloudfront.net/listing/abc/photo01"
        assert _is_valid_image_url(u), f"CloudFront extensionless URL must pass now, got False"
        assert _sanitize_google_image_url(u) == u

    def test_imgix_transform_url_passes(self):
        u = "https://images.bidvex.com/listing/abc/main.jpg?w=1200&auto=format"
        assert _is_valid_image_url(u)
        # Google mapper strips the query string.
        assert _sanitize_google_image_url(u) == "https://images.bidvex.com/listing/abc/main.jpg"

    def test_webp_extension_rejected(self):
        u = "https://d1234abc.cloudfront.net/listing/abc/photo.webp"
        assert not _is_valid_image_url(u)
        assert _sanitize_google_image_url(u) == ""

    def test_svg_extension_rejected(self):
        u = "https://d1234abc.cloudfront.net/listing/abc/photo.svg"
        assert not _is_valid_image_url(u)
        assert _sanitize_google_image_url(u) == ""

    def test_heic_rejected(self):
        assert not _is_valid_image_url("https://cdn.bidvex.com/x.heic")

    def test_presigned_s3_url_rejected(self):
        """iter347 — presigned URLs expire; crawler would 403 →
        product removed from catalog. Never emit these."""
        u = (
            "https://bidvex-marketplace-images.s3.us-east-2.amazonaws.com/"
            "listings/abc/00-x.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256"
            "&X-Amz-Signature=abcdef123456&X-Amz-Expires=3600"
        )
        assert not _is_valid_image_url(u), "presigned URL must be rejected"
        assert _sanitize_google_image_url(u) == ""

    def test_gcs_presigned_url_rejected(self):
        u = "https://storage.googleapis.com/bidvex/x.jpg?X-Goog-Signature=abc&X-Goog-Credential=xyz"
        assert not _is_valid_image_url(u)
        assert _sanitize_google_image_url(u) == ""

    def test_http_not_https_rejected(self):
        assert not _is_valid_image_url("http://cdn.bidvex.com/x.jpg")

    def test_facebook_click_redirect_rejected(self):
        assert not _is_valid_image_url("https://l.facebook.com/l.php?u=https%3A%2F%2Fcdn.example.com%2Fx.jpg")

    def test_first_valid_image_picks_first_passing_url(self):
        """When the array has a mix of URL types, the FIRST valid one
        wins (was silently falling into placeholder before iter347)."""
        # Real production shape — mix of extensionless + jpg + webp.
        images = [
            "https://d123.cloudfront.net/uuid/photo",       # extensionless → PASS
            "https://d123.cloudfront.net/uuid/photo.jpg",   # PASS
            "https://d123.cloudfront.net/uuid/photo.webp",  # REJECT (banned ext)
        ]
        primary, extras = _first_valid_image(images, None)
        assert primary == images[0], f"expected {images[0]}, got {primary}"
        # extras must not include the webp
        assert all(".webp" not in x for x in extras)

    def test_first_valid_image_falls_back_to_none_when_all_reject(self):
        images = [
            "https://d123.cloudfront.net/uuid/photo.webp",
            "https://d123.cloudfront.net/uuid/photo.svg",
            "http://insecure.example.com/x.jpg",  # http rejected
        ]
        primary, _ = _first_valid_image(images, None)
        assert primary is None, "all-invalid array must return None so placeholder kicks in"


# ═══ ISSUE 1 — /api/feeds/refresh endpoint ═════════════════════════════

class TestFeedRefreshEndpoint:

    def test_refresh_endpoint_requires_admin(self, db):
        r = requests.post(f"{API}/feeds/refresh", timeout=30)
        assert r.status_code in (401, 403), f"unauthenticated should be blocked, got {r.status_code}"

    def test_refresh_endpoint_returns_feed_urls_for_admin(self, db):
        token, uid, _ = _mint_admin_token(db, "iter347_refresh")
        try:
            r = requests.post(
                f"{API}/feeds/refresh",
                headers={"Authorization": f"Bearer {token}"},
                params={"warm": "false"},
                timeout=30,
            )
            assert r.status_code == 200, f"expected 200, got {r.status_code} — {r.text[:300]}"
            data = r.json()
            assert "invalidated_keys" in data
            assert data["warmed"] is False
            urls = data["feed_urls"]
            assert urls["meta_csv"].endswith("/api/feeds/facebook-local")
            assert urls["meta_json"].endswith("format=json")
            assert urls["google_xml"].endswith("/api/feeds/google")
            # generated_at is a valid ISO string
            datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))
        finally:
            db.users.delete_one({"id": uid})


# ═══ ISSUE 2 — Single-step IVR ═════════════════════════════════════════

class TestSingleStepIVR:

    def test_main_menu_get_returns_gather(self):
        """Twilio Console probes with GET during config."""
        r = requests.get(f"{API}/twilio/ivr/main-menu", timeout=30)
        assert r.status_code == 200
        body = r.text
        assert "<Gather" in body
        assert "<Say voice=\"alice\" language=\"en-US\"" in body
        assert "<Say voice=\"alice\" language=\"fr-CA\"" in body
        # Support prompt in EN
        assert "press 1" in body.lower() or "press the 1" in body.lower()
        # Contractor extension prompt
        assert "extension" in body.lower()

    def test_main_menu_post_persists_call_row(self, db):
        call_sid = f"iter347-CA-{uuid.uuid4().hex[:12]}"
        try:
            r = requests.post(
                f"{API}/twilio/ivr/main-menu",
                data={
                    "CallSid": call_sid,
                    "From":    "+15145559999",
                    "To":      "+14506343099",
                },
                timeout=30,
            )
            assert r.status_code == 200
            row = db.inbound_extension_calls.find_one({"call_sid": call_sid})
            assert row is not None
            assert row.get("menu_variant") == "iter349_time_aware"
            assert row.get("status") == "in_progress"
        finally:
            db.inbound_extension_calls.delete_many({"call_sid": call_sid})

    def test_handle_menu_press_1_dials_support(self):
        r = requests.post(
            f"{API}/twilio/handle-menu",
            data={
                "CallSid": f"iter347-CA-{uuid.uuid4().hex[:12]}",
                "Digits":  "1",
                "From":    "+15145559999",
            },
            timeout=30,
        )
        assert r.status_code == 200
        # iter347 — application/xml responses without charset in
        # Content-Type trigger requests' chardet fallback which
        # mis-detects ASCII-only content as CJK. Decode raw bytes.
        body = r.content.decode("utf-8")
        # Must dial the BidVex general support line.
        assert "+15149490038" in body, f"support number not in TwiML: {body[:300]}"
        assert "<Dial" in body
        assert "<Number>+15149490038</Number>" in body

    def test_handle_menu_valid_extension_dials_contractor(self, db):
        """Seed a `dialer_contractor` user with a known extension +
        personal_phone_number, then verify handle-menu dials that
        number. `lookup_contractor_by_extension` queries `db.users`
        (not `db.contractor_extensions`) and requires role=='dialer_contractor'."""
        ext = 4321
        contractor_id = str(uuid.uuid4())
        # Clean any existing.
        db.users.delete_many({"extension_number": ext, "role": "dialer_contractor"})
        db.users.insert_one({
            "id":                    contractor_id,
            "email":                 f"iter347_c_{contractor_id[:8]}@test.com",
            "name":                  "Iter347 Contractor",
            "role":                  "dialer_contractor",
            "extension_number":      ext,
            "personal_phone_number": "+15145558877",
            "is_active":             True,
            "created_at":            datetime.now(timezone.utc).isoformat(),
        })
        try:
            r = requests.post(
                f"{API}/twilio/handle-menu",
                data={
                    "CallSid": f"iter347-CA-{uuid.uuid4().hex[:12]}",
                    "Digits":  str(ext),
                    "From":    "+15145559999",
                },
                timeout=30,
            )
            assert r.status_code == 200
            body = r.content.decode("utf-8")
            assert "+15145558877" in body, f"contractor personal_phone not in TwiML: {body[:400]}"
            # callerId must be the BidVex main line for privacy.
            assert 'callerId="+14506343099"' in body
        finally:
            db.users.delete_one({"id": contractor_id})

    def test_handle_menu_unknown_extension_replays_menu(self):
        """Never drop — bounce back to /ivr/main-menu?attempt=2."""
        r = requests.post(
            f"{API}/twilio/handle-menu",
            data={
                "CallSid": f"iter347-CA-{uuid.uuid4().hex[:12]}",
                "Digits":  "9999",  # unlikely to exist
                "From":    "+15145559999",
            },
            timeout=30,
        )
        assert r.status_code == 200
        body = r.text
        assert "<Redirect" in body
        assert "ivr/main-menu" in body
        assert "attempt=2" in body

    def test_handle_menu_no_input_replays_menu(self):
        r = requests.post(
            f"{API}/twilio/handle-menu",
            data={
                "CallSid": f"iter347-CA-{uuid.uuid4().hex[:12]}",
                "Digits":  "",
                "From":    "+15145559999",
            },
            timeout=30,
        )
        assert r.status_code == 200
        assert "<Redirect" in r.text
        assert "ivr/main-menu" in r.text

    def test_main_menu_third_attempt_routes_to_support(self):
        """After 3 failed attempts, gracefully route to support so the
        call is NEVER dropped."""
        r = requests.post(
            f"{API}/twilio/ivr/main-menu?attempt=4",
            data={
                "CallSid": f"iter347-CA-{uuid.uuid4().hex[:12]}",
                "From":    "+15145559999",
            },
            timeout=30,
        )
        assert r.status_code == 200
        body = r.text
        assert "<Dial" in body
        assert "+15149490038" in body, "should have dialed support after max attempts"

    def test_main_menu_retry_has_bilingual_nudge(self):
        r = requests.get(f"{API}/twilio/ivr/main-menu?attempt=2", timeout=30)
        assert r.status_code == 200
        body = r.text
        assert "didn't catch" in body.lower() or "did not catch" in body.lower()
        # French nudge
        assert "capt" in body.lower()  # "capté"
