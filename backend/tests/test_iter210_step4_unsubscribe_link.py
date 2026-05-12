"""
iter210 Step 4 — Unsubscribe Link Endpoint regression guard.

Confirms:
  * GET /api/unsubscribe/generate-test-link is admin-protected
  * Endpoint returns both url_en and url_fr in the JSON shape spec'd
  * Both URLs contain the bilingual sub-paths ("/unsubscribe" vs "/desabonnement")
    and a `lang` query param
  * {{unsubscribe_url_en}} and {{unsubscribe_url_fr}} substitutions are applied
    in services/email_marketing.py before SendGrid send (regression check via grep)
"""
import os
import sys
import re
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

API_URL = ""
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            API_URL = line.split("=", 1)[1].strip().rstrip("/")
            break


def _admin_token() -> str:
    r = httpx.post(
        f"{API_URL}/api/auth/login",
        json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("access_token") or r.json().get("token")


def test_generate_test_link_requires_admin():
    r = httpx.get(f"{API_URL}/api/unsubscribe/generate-test-link?email=x@y.com", timeout=15)
    # Either 401 (no token) or 403 (token but non-admin) — both acceptable as "admin required"
    assert r.status_code in (401, 403)


def test_generate_test_link_returns_both_urls():
    token = _admin_token()
    r = httpx.get(
        f"{API_URL}/api/unsubscribe/generate-test-link",
        params={"email": "test@bidvex.ca"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("email") == "test@bidvex.ca"
    assert body.get("expires_in_days") == 30
    assert "url_en" in body and "url_fr" in body
    assert "/unsubscribe?" in body["url_en"]
    assert "/desabonnement?" in body["url_fr"]
    assert "token=" in body["url_en"]
    assert "lang=en" in body["url_en"]
    assert "lang=fr" in body["url_fr"]


def test_generate_test_link_rejects_invalid_email():
    token = _admin_token()
    r = httpx.get(
        f"{API_URL}/api/unsubscribe/generate-test-link",
        params={"email": "not-an-email"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert r.status_code == 400


def test_unsubscribe_substitutions_are_wired():
    """Static grep — both substitution tags must be present in email_marketing.py."""
    p = Path("/app/backend/services/email_marketing.py").read_text()
    assert "{{unsubscribe_url_en}}" in p, "unsubscribe_url_en substitution NOT wired in email_marketing.py"
    assert "{{unsubscribe_url_fr}}" in p, "unsubscribe_url_fr substitution NOT wired in email_marketing.py"
    # And the resolver function should be imported lazily
    assert "build_unsubscribe_urls" in p, "build_unsubscribe_urls not used in email_marketing.py"


def test_unsubscribe_substitutions_in_email_service():
    p = Path("/app/backend/services/email_service.py").read_text()
    assert "build_unsubscribe_urls" in p
    assert "unsubscribe_url_en" in p
    assert "unsubscribe_url_fr" in p


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
