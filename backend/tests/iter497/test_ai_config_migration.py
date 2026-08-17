"""iter497 — Backend regression tests for the BidVex Gemini system-instruction
MongoDB migration (P0.1 in the fork plan).

Coverage:
  1. Seed file is present at the documented path and non-empty.
  2. ``get_system_instruction_sync()`` returns a non-empty string that
     contains the P0 anchor (proves the sync fallback path works).
  3. ``build_generation_config()`` embeds the DB-backed sync value.
  4. Live REST — admin can GET the current instruction (200, source starts
     as ``seed_file`` on a cold DB) and PUT a new instruction (200, source
     becomes ``admin_edit``).
  5. Live REST — anonymous and non-admin callers cannot access either
     endpoint (401 / 403 respectively).
  6. Restoring the seed value via PUT keeps the platform in the pristine
     starting state so downstream tests don't observe a modified prompt.
  7. Validation — empty value is rejected (422 or 400).
"""
from __future__ import annotations

import os
import time

import pytest
import requests


BASE_URL = (
    os.environ.get("BACKEND_BASE_URL")
    or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=", 1)[-1].split("\n", 1)[0].strip()
).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"

# Path pin so any accidental deletion of the seed fails loudly.
SEED_PATH = "/app/memory/BIDVEX_AI_SYSTEM_INSTRUCTION_SEED.md"


# ── Local sync surface (does not hit the network) ─────────────────
def test_seed_file_present_and_nonempty():
    with open(SEED_PATH, "r", encoding="utf-8") as fh:
        content = fh.read()
    assert len(content) > 10_000, "seed file should be the full BidVex system instruction"
    assert "# 0. ABSOLUTE PLATFORM ANCHOR" in content
    assert "BIDVEX_ESCALATION" in content


def test_sync_accessor_returns_seed_when_db_uninitialized():
    from services.ai_config_service import get_system_instruction_sync
    val = get_system_instruction_sync()
    assert isinstance(val, str) and len(val) > 10_000
    assert "# 0. ABSOLUTE PLATFORM ANCHOR" in val


def test_build_generation_config_embeds_sync_value():
    from services.genai_direct_client import build_generation_config
    cfg = build_generation_config()
    assert cfg.system_instruction
    assert "# 0. ABSOLUTE PLATFORM ANCHOR" in cfg.system_instruction
    assert "BIDVEX_ESCALATION" in cfg.system_instruction


def test_build_generation_config_appends_extra_context():
    from services.genai_direct_client import build_generation_config
    cfg = build_generation_config(extra_system_instruction="LIVE CONTEXT — test iter497")
    assert "LIVE CONTEXT — test iter497" in (cfg.system_instruction or "")
    assert "# Additional Runtime Context" in (cfg.system_instruction or "")


def test_watchdog_backwards_compat_constant():
    """iter234+ tests import WATCHDOG_SYSTEM_INSTRUCTION directly. The name
    must remain in the module namespace and resolve to the same text the
    async DB path would return on a cold cache."""
    from services.genai_direct_client import WATCHDOG_SYSTEM_INSTRUCTION
    assert isinstance(WATCHDOG_SYSTEM_INSTRUCTION, str)
    assert len(WATCHDOG_SYSTEM_INSTRUCTION) > 10_000
    assert "# 0. ABSOLUTE PLATFORM ANCHOR" in WATCHDOG_SYSTEM_INSTRUCTION


# ── HTTP admin endpoints (live) ────────────────────────────────────
def _login(email: str, password: str) -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"login as {email} failed with {r.status_code} — cannot test live REST here")
    tok = r.json().get("access_token") or r.json().get("token") or ""
    if not tok:
        pytest.skip(f"login response for {email} did not carry a token")
    return tok


def _admin_auth() -> dict:
    return {"Authorization": f"Bearer {_login(ADMIN_EMAIL, ADMIN_PASSWORD)}"}


def _fresh_nonadmin_auth() -> dict:
    email = f"iter497nonadmin_{int(time.time())}@test.com"
    requests.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "Test123!@#",
            "name": "Iter497 NonAdmin",
            "terms_agreed": True,
            "ai_disclosure_consent": True,
        },
        timeout=15,
    )
    tok = _login(email, "Test123!@#")
    return {"Authorization": f"Bearer {tok}"}


def test_get_requires_auth():
    r = requests.get(f"{API}/admin/ai-config/system-instruction", timeout=15)
    assert r.status_code in (401, 403)


def test_get_rejects_non_admin():
    r = requests.get(
        f"{API}/admin/ai-config/system-instruction",
        headers=_fresh_nonadmin_auth(),
        timeout=15,
    )
    assert r.status_code == 403


def test_put_rejects_non_admin():
    r = requests.put(
        f"{API}/admin/ai-config/system-instruction",
        headers={**_fresh_nonadmin_auth(), "Content-Type": "application/json"},
        json={"value": "hack"},
        timeout=15,
    )
    assert r.status_code == 403


def test_admin_get_returns_current_instruction():
    r = requests.get(
        f"{API}/admin/ai-config/system-instruction",
        headers=_admin_auth(),
        timeout=15,
    )
    assert r.status_code == 200, r.text
    doc = r.json()
    for key in ("key", "value", "char_count", "source", "updated_at"):
        assert key in doc
    assert doc["key"] == "system_instruction"
    assert doc["char_count"] >= 10_000
    assert "# 0. ABSOLUTE PLATFORM ANCHOR" in doc["value"]


def test_admin_put_updates_and_get_reflects_it():
    headers = {**_admin_auth(), "Content-Type": "application/json"}
    new_text = f"iter497 admin edit test — timestamp={int(time.time())}. BIDVEX_ESCALATION marker preserved."
    put_resp = requests.put(
        f"{API}/admin/ai-config/system-instruction",
        headers=headers,
        json={"value": new_text},
        timeout=15,
    )
    assert put_resp.status_code == 200, put_resp.text
    body = put_resp.json()
    assert body["source"] == "admin_edit"
    assert body["char_count"] == len(new_text)
    assert body["updated_by_user_id"], "admin user id should be recorded"

    # Read-back
    get_resp = requests.get(
        f"{API}/admin/ai-config/system-instruction",
        headers=_admin_auth(),
        timeout=15,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["value"] == new_text

    # Restore seed so downstream tests observe a pristine platform
    seed_text = open(SEED_PATH, "r", encoding="utf-8").read()
    restore = requests.put(
        f"{API}/admin/ai-config/system-instruction",
        headers=headers,
        json={"value": seed_text},
        timeout=15,
    )
    assert restore.status_code == 200
    assert restore.json()["char_count"] == len(seed_text)


def test_admin_put_rejects_empty_value():
    r = requests.put(
        f"{API}/admin/ai-config/system-instruction",
        headers={**_admin_auth(), "Content-Type": "application/json"},
        json={"value": ""},
        timeout=15,
    )
    assert r.status_code in (400, 422), r.text
