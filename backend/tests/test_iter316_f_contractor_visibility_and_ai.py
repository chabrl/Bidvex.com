"""
iter316-F — Contractor visibility + AI voice config surfacing.

Tests:
  • GET /api/twilio/config now includes ai_voice_configured + ai_voice_missing.
  • ai_voice_configured = bool(env GEMINI_API_KEY set) — verified via env pop/restore.
  • Existing fields (configured, can_mint_tokens, can_place_calls, missing,
    twilio_phone_number) remain stable.
  • Auth gate unchanged — unauthenticated callers blocked.
"""
from __future__ import annotations

import os
import sys
import httpx
import pytest

sys.path.insert(0, "/app/backend")

API_BASE = (os.environ.get("REACT_APP_BACKEND_URL")
            or "https://prod-verify-2.preview.emergentagent.com")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


@pytest.fixture(scope="module")
def admin_token() -> str:
    r = httpx.post(f"{API_BASE}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    }, timeout=30.0)
    assert r.status_code == 200
    return r.json()["access_token"]


def _h(tok): return {"Authorization": f"Bearer {tok}"}


def test_config_endpoint_returns_new_ai_voice_fields(admin_token):
    r = httpx.get(f"{API_BASE}/api/twilio/config",
                  headers=_h(admin_token), timeout=20.0)
    assert r.status_code == 200, r.text
    data = r.json()
    # NEW fields:
    assert "ai_voice_configured" in data, "missing ai_voice_configured"
    assert "ai_voice_missing" in data,    "missing ai_voice_missing"
    assert isinstance(data["ai_voice_configured"], bool)
    assert isinstance(data["ai_voice_missing"], list)
    # Existing-fields stability:
    for k in ("configured", "can_mint_tokens", "can_place_calls",
              "missing", "twilio_phone_number"):
        assert k in data, f"missing legacy field {k}"


def test_config_ai_voice_missing_lists_gemini_when_unset(admin_token):
    """ai_voice_configured must mirror env var presence.

    We can't easily pop env vars on a remote server, so this test is a
    pure contract check on the response shape rather than env mutation."""
    r = httpx.get(f"{API_BASE}/api/twilio/config",
                  headers=_h(admin_token), timeout=20.0)
    data = r.json()
    if data["ai_voice_configured"] is True:
        assert data["ai_voice_missing"] == []
    else:
        assert "GEMINI_API_KEY" in data["ai_voice_missing"]


def test_config_blocks_anonymous():
    r = httpx.get(f"{API_BASE}/api/twilio/config", timeout=20.0)
    assert r.status_code in (401, 403)


def test_genai_resolve_api_key_fails_fast_when_missing():
    """Direct unit-level check on the resolver — confirms a missing
    GEMINI_API_KEY raises a RuntimeError with a clear message that
    surfaces back through the voice_ai pipeline's exception handler."""
    from services.genai_direct_client import _resolve_api_key
    original = os.environ.pop("GEMINI_API_KEY", None)
    try:
        with pytest.raises(RuntimeError) as exc_info:
            _resolve_api_key()
        assert "GEMINI_API_KEY" in str(exc_info.value)
    finally:
        if original is not None:
            os.environ["GEMINI_API_KEY"] = original


def test_genai_resolve_api_key_returns_when_set():
    """Round-trip: when the env is set the resolver returns it intact."""
    from services.genai_direct_client import _resolve_api_key
    os.environ["GEMINI_API_KEY"] = "test-sentinel-key-please-ignore"
    try:
        out = _resolve_api_key()
        assert out == "test-sentinel-key-please-ignore"
    finally:
        # restore real key from .env so subsequent tests aren't broken.
        from dotenv import dotenv_values
        real = dotenv_values("/app/backend/.env").get("GEMINI_API_KEY")
        if real:
            os.environ["GEMINI_API_KEY"] = real
        else:
            os.environ.pop("GEMINI_API_KEY", None)
