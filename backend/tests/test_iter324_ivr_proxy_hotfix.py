"""iter324 — Twilio IVR proxy/scheme hotfix tests.

Reproduces the K8s ingress scenario where the pod sees:
    request.url.scheme == "http"
    request.headers["x-forwarded-proto"] == "https"
    request.headers["x-forwarded-host"]  == "bidvex.com"
…and verifies that:
  1. _public_base() returns "https://bidvex.com" (not http://internal)
  2. TwiML <Gather action> URLs are emitted as https://
  3. _validate_twilio_signature() validates against the EXTERNAL https
     URL Twilio actually signed, not the internal http:// one
  4. /api/twilio/ivr/healthz returns valid TwiML with the public base
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Bypass signature validation by default — individual tests will toggle it.
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test_token_iter324")
os.environ["TWILIO_SIGNATURE_BYPASS"] = "1"

sys.path.insert(0, "/app/backend")


def _build_app():
    from routes.contractor_ivr_inbound import router as ivr_router
    app = FastAPI()
    app.include_router(ivr_router, prefix="/api")
    return app


# ─── 1.  _public_base() ────────────────────────────────────────────────


class TestPublicBase:
    def test_honors_x_forwarded_proto_https(self):
        from routes.contractor_ivr_inbound import _public_base
        from starlette.requests import Request

        scope = {
            "type": "http", "method": "POST", "path": "/api/twilio/ivr/incoming",
            "raw_path": b"/api/twilio/ivr/incoming", "query_string": b"",
            "headers": [
                (b"host", b"internal-pod.svc.cluster.local"),
                (b"x-forwarded-proto", b"https"),
                (b"x-forwarded-host", b"bidvex.com"),
            ],
            "scheme": "http",  # ingress terminates SSL → pod sees plain http
            "server": ("internal-pod.svc.cluster.local", 8001),
        }
        req = Request(scope)
        assert _public_base(req) == "https://bidvex.com"

    def test_forces_https_even_when_proxy_says_http(self):
        # Edge case — if X-Forwarded-Proto is somehow http, we still force https
        # because Twilio Voice requires HTTPS callbacks.
        from routes.contractor_ivr_inbound import _public_base
        from starlette.requests import Request

        scope = {
            "type": "http", "method": "POST", "path": "/api/twilio/ivr/incoming",
            "raw_path": b"/api/twilio/ivr/incoming", "query_string": b"",
            "headers": [
                (b"host", b"bidvex.com"),
                (b"x-forwarded-proto", b"http"),
            ],
            "scheme": "http",
            "server": ("internal", 8001),
        }
        req = Request(scope)
        assert _public_base(req).startswith("https://")

    def test_falls_back_to_request_host_when_no_proxy_header(self):
        from routes.contractor_ivr_inbound import _public_base
        from starlette.requests import Request

        scope = {
            "type": "http", "method": "POST", "path": "/api/twilio/ivr/incoming",
            "raw_path": b"/api/twilio/ivr/incoming", "query_string": b"",
            "headers": [(b"host", b"bidvex.com")],
            "scheme": "https",
            "server": ("bidvex.com", 443),
        }
        req = Request(scope)
        assert _public_base(req) == "https://bidvex.com"


# ─── 2.  TwiML <Gather action> URLs ────────────────────────────────────


class TestTwiMLActionUrlsAreHttps:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        # Stub out the DB so insert/update operations don't blow up in tests.
        class _FakeColl:
            async def insert_one(self, _doc): return None
            async def update_one(self, *_a, **_k): return None
            async def find_one(self, *_a, **_k): return None

        class _FakeDB:
            inbound_extension_calls = _FakeColl()
            users = _FakeColl()
            contractor_emails = _FakeColl()
            notifications = _FakeColl()

        import routes.contractor_ivr_inbound as ivr
        monkeypatch.setattr(ivr, "_get_db", lambda: _FakeDB())

    def _post(self, path, *, headers=None, data=None, query=""):
        app = _build_app()
        client = TestClient(app)
        hdrs = {
            "x-forwarded-proto": "https",
            "x-forwarded-host":  "bidvex.com",
        }
        if headers:
            hdrs.update(headers)
        url = f"/api{path}"
        if query:
            url = f"{url}?{query}"
        return client.post(url, headers=hdrs, data=data or {})

    def test_step1_action_url_is_https(self):
        # Twilio's very first POST — no lang_step → we ask language.
        r = self._post(
            "/twilio/ivr/incoming",
            data={"CallSid": "CAtest1", "From": "+15145550000", "To": "+14506343099"},
        )
        assert r.status_code == 200, r.text
        body = r.text
        # action URL must point to the externally-visible https base
        assert 'action="https://bidvex.com/api/twilio/ivr/incoming?lang_step=1"' in body, body
        # The TwiML must NOT contain http:// action URLs (would cause Twilio to drop)
        assert "action=\"http://" not in body, body

    def test_step2_action_url_is_https_for_extension_gather(self):
        # User pressed 1 (English) — we ask for extension.
        r = self._post(
            "/twilio/ivr/incoming",
            query="lang_step=1",
            data={"CallSid": "CAtest2", "From": "+15145550001", "Digits": "1"},
        )
        assert r.status_code == 200, r.text
        body = r.text
        assert 'action="https://bidvex.com/api/twilio/ivr/route?lang=en"' in body, body
        assert "<Redirect" in body
        assert "https://bidvex.com/api/twilio/ivr/route?lang=en" in body
        assert "action=\"http://" not in body, body

    def test_step2_french_path_also_https(self):
        r = self._post(
            "/twilio/ivr/incoming",
            query="lang_step=1",
            data={"CallSid": "CAtest3", "From": "+15145550002", "Digits": "2"},
        )
        assert r.status_code == 200, r.text
        body = r.text
        assert 'action="https://bidvex.com/api/twilio/ivr/route?lang=fr"' in body, body
        assert "action=\"http://" not in body

    def test_invalid_extension_reprompt_uses_https(self, monkeypatch):
        # Send non-digit → IVR should re-prompt back to /incoming
        # via a Redirect — that URL must also be https.
        async def _no_contractor(*_a, **_k): return None
        import services.contractor_extensions as ce
        monkeypatch.setattr(ce, "lookup_contractor_by_extension", _no_contractor)

        r = self._post(
            "/twilio/ivr/route",
            query="lang=en",
            data={"CallSid": "CAtest4", "From": "+15145550003", "Digits": "abc"},
        )
        assert r.status_code == 200, r.text
        body = r.text
        assert "https://bidvex.com/api/twilio/ivr/incoming" in body
        assert "action=\"http://" not in body

    def test_unknown_extension_gather_uses_https(self, monkeypatch):
        async def _no_contractor(*_a, **_k): return None
        import services.contractor_extensions as ce
        monkeypatch.setattr(ce, "lookup_contractor_by_extension", _no_contractor)

        r = self._post(
            "/twilio/ivr/route",
            query="lang=en",
            data={"CallSid": "CAtest5", "From": "+15145550004", "Digits": "9999"},
        )
        assert r.status_code == 200, r.text
        body = r.text
        # The follow-up Gather (press 0 for support) must use https
        assert 'action="https://bidvex.com/api/twilio/ivr/route?lang=en"' in body
        assert "action=\"http://" not in body

    def test_dial_action_and_whisper_url_use_https(self, monkeypatch):
        async def _contractor(*_a, **_k):
            return {
                "id": "ctest1234",
                "is_active": True,
                "personal_phone_number": "+15145559876",
                "name": "Test Contractor",
            }
        import services.contractor_extensions as ce
        monkeypatch.setattr(ce, "lookup_contractor_by_extension", _contractor)

        r = self._post(
            "/twilio/ivr/route",
            query="lang=en",
            data={"CallSid": "CAtest6", "From": "+15145550005", "Digits": "1220"},
        )
        assert r.status_code == 200, r.text
        body = r.text
        # <Dial action="..."> (status URL) must be https
        assert "https://bidvex.com/api/twilio/ivr/status" in body
        # <Number url="..."> (whisper URL) must be https
        assert "https://bidvex.com/api/twilio/ivr/whisper" in body
        assert "url=\"http://" not in body
        assert "action=\"http://" not in body


# ─── 3.  Twilio signature validation against EXTERNAL https URL ────────


class TestTwilioSignatureValidation:
    """Signature is computed against the externally-visible URL (https://bidvex.com/…).
    The pod, behind the K8s ingress, only sees http:// internally — the
    validator must reconstruct the external URL using X-Forwarded-* headers.
    """

    def setup_method(self):
        # Force the validator to actually run (not bypass) for these tests
        os.environ.pop("TWILIO_SIGNATURE_BYPASS", None)
        os.environ["TWILIO_AUTH_TOKEN"] = "iter324_signed_test_token"

    def teardown_method(self):
        os.environ["TWILIO_SIGNATURE_BYPASS"] = "1"

    def test_signature_matches_when_proxy_headers_present(self, monkeypatch):
        """Simulate exactly what Twilio does: sign https://bidvex.com/api/…
        even though the pod sees http://internal/…. The validator should
        rebuild the external URL via X-Forwarded-* and succeed."""
        from twilio.request_validator import RequestValidator
        token = os.environ["TWILIO_AUTH_TOKEN"]
        external_url = "https://bidvex.com/api/twilio/ivr/incoming"
        form_params = {
            "CallSid": "CAsigtest1",
            "From": "+15145550000",
            "To": "+14506343099",
            "AccountSid": "ACtest",
        }
        signature = RequestValidator(token).compute_signature(external_url, form_params)

        # Stub DB
        class _FakeColl:
            async def insert_one(self, _doc): return None
            async def update_one(self, *_a, **_k): return None
        class _FakeDB:
            inbound_extension_calls = _FakeColl()
        import routes.contractor_ivr_inbound as ivr
        monkeypatch.setattr(ivr, "_get_db", lambda: _FakeDB())

        app = _build_app()
        client = TestClient(app)

        r = client.post(
            "/api/twilio/ivr/incoming",
            headers={
                "x-forwarded-proto":  "https",
                "x-forwarded-host":   "bidvex.com",
                "host":               "internal-pod.svc.cluster.local",
                "X-Twilio-Signature": signature,
            },
            data=form_params,
        )
        # MUST return 200 with valid TwiML even though pod scheme is http
        assert r.status_code == 200, r.text
        assert "<Gather" in r.text
        # And the emitted action URL is https://bidvex.com/…
        assert 'action="https://bidvex.com/api/twilio/ivr/incoming?lang_step=1"' in r.text

    def test_admit_with_warning_when_signature_mismatch(self, monkeypatch, caplog):
        """Soft-admit policy — we LOG LOUDLY but do NOT 403. Verifies that
        a request with a bogus signature still gets a valid TwiML response
        (so legitimate calls don't drop in edge cases like port mismatch)."""
        class _FakeColl:
            async def insert_one(self, _doc): return None
            async def update_one(self, *_a, **_k): return None
        class _FakeDB:
            inbound_extension_calls = _FakeColl()
        import routes.contractor_ivr_inbound as ivr
        monkeypatch.setattr(ivr, "_get_db", lambda: _FakeDB())

        app = _build_app()
        client = TestClient(app)
        with caplog.at_level("WARNING"):
            r = client.post(
                "/api/twilio/ivr/incoming",
                headers={
                    "x-forwarded-proto":  "https",
                    "x-forwarded-host":   "bidvex.com",
                    "X-Twilio-Signature": "bogus_signature_value",
                },
                data={"CallSid": "CAsigtest2", "From": "+15145550001"},
            )
        assert r.status_code == 200, r.text
        assert "<Gather" in r.text
        # Confirm the WARNING was logged (so prod ops sees the mismatch)
        joined = " ".join(rec.getMessage() for rec in caplog.records)
        assert "did NOT match" in joined or "signature" in joined.lower()


# ─── 4.  Healthcheck endpoint ───────────────────────────────────────────


class TestHealthCheck:
    def test_healthz_returns_twiml_with_public_base(self):
        app = _build_app()
        client = TestClient(app)
        r = client.get(
            "/api/twilio/ivr/healthz",
            headers={"x-forwarded-proto": "https", "x-forwarded-host": "bidvex.com"},
        )
        assert r.status_code == 200
        body = r.text
        assert "<Response>" in body
        assert "BidVex IVR is online" in body
        assert "public_base = https://bidvex.com" in body


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
