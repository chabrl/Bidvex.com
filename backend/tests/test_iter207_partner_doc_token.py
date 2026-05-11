"""
iter207 — Bug 2 fix verification
Browser-friendly token-via-query-param fallback on
GET /api/uploads/partner_docs/{filename}.

Why this exists: the Admin Partner Manager renders document URLs as plain
`<a href target="_blank">`. Browsers cannot attach an `Authorization` header
on a plain navigation, so we needed to support `?token=<jwt>` as a fallback
on this single file-serve endpoint.
"""
import os
import sys
import uuid
import asyncio
import shutil
from pathlib import Path

import pytest
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not API_URL:
    # fall back to reading /app/frontend/.env
    env_path = Path(__file__).parent.parent.parent / "frontend" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                API_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"

_cached_admin_token: str | None = None


def _get_admin_token() -> str:
    global _cached_admin_token
    if _cached_admin_token:
        return _cached_admin_token
    r = httpx.post(
        f"{API_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"no token in login response: {data}"
    _cached_admin_token = tok
    return tok


# Pick any file that already exists in preview's uploads dir, or seed one.
UPLOADS_DIR = Path("/app/backend/uploads/partner_docs")


def _pick_or_seed_file() -> str:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    existing = list(UPLOADS_DIR.glob("*"))
    if existing:
        return existing[0].name
    # Seed a tiny placeholder
    name = f"neq_test_{uuid.uuid4().hex[:8]}.pdf"
    (UPLOADS_DIR / name).write_bytes(b"%PDF-1.4 test")
    return name


def test_no_auth_returns_401():
    """No header and no ?token= → 401 Not authenticated."""
    fname = _pick_or_seed_file()
    r = httpx.get(f"{API_URL}/api/uploads/partner_docs/{fname}", timeout=15)
    assert r.status_code == 401, f"expected 401 without auth, got {r.status_code}: {r.text[:200]}"


def test_query_token_serves_file_for_admin():
    """?token=<admin-jwt> → 200 with the file body (browser-navigation path)."""
    tok = _get_admin_token()
    fname = _pick_or_seed_file()
    r = httpx.get(
        f"{API_URL}/api/uploads/partner_docs/{fname}",
        params={"token": tok},
        timeout=15,
    )
    assert r.status_code == 200, f"expected 200 with ?token=, got {r.status_code}: {r.text[:200]}"
    assert len(r.content) > 0, "expected non-empty file body"


def test_header_token_still_works_for_admin():
    """Authorization: Bearer header still served — regression guard."""
    tok = _get_admin_token()
    fname = _pick_or_seed_file()
    r = httpx.get(
        f"{API_URL}/api/uploads/partner_docs/{fname}",
        headers={"Authorization": f"Bearer {tok}"},
        timeout=15,
    )
    assert r.status_code == 200, f"expected 200 with header, got {r.status_code}: {r.text[:200]}"


def test_invalid_query_token_returns_401():
    """A garbage ?token= falls through to 401 (no privilege escalation)."""
    fname = _pick_or_seed_file()
    r = httpx.get(
        f"{API_URL}/api/uploads/partner_docs/{fname}",
        params={"token": "not.a.valid.jwt"},
        timeout=15,
    )
    assert r.status_code == 401, f"expected 401 with bad ?token=, got {r.status_code}: {r.text[:200]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
