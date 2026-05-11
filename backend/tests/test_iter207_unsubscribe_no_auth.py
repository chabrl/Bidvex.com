"""
iter207 — Bug 3 (Unsubscribe) regression guard.

Confirms that the unsubscribe flow never requires the user to be logged in
(CASL / CAN-SPAM compliance — recipients clicking an email link must reach
the page without an authentication wall).
"""
import os
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not API_URL:
    env_path = Path(__file__).parent.parent.parent / "frontend" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                API_URL = line.split("=", 1)[1].strip().rstrip("/")
                break


def test_verify_missing_token_is_400_not_401():
    """No token → 400 token_missing (NOT 401 Not authenticated)."""
    r = httpx.get(f"{API_URL}/api/unsubscribe/verify", timeout=15)
    assert r.status_code == 400, f"expected 400 token_missing, got {r.status_code}"
    assert r.json().get("detail") == "token_missing"


def test_verify_bad_token_is_400_not_401():
    """Garbage token → 400 token_invalid (NOT 401)."""
    r = httpx.get(f"{API_URL}/api/unsubscribe/verify?token=garbage", timeout=15)
    assert r.status_code == 400, f"expected 400 token_invalid, got {r.status_code}"
    assert r.json().get("detail") == "token_invalid"


def test_verify_with_valid_token_never_requires_auth():
    """Mint a signed token via the in-process helper and call without auth headers."""
    # Load env so the secret is available
    os.environ.setdefault("PYTHONPATH", "/app/backend")
    sys.path.insert(0, "/app/backend")
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from routes.unsubscribe import generate_unsubscribe_token  # noqa: E402

    token = generate_unsubscribe_token("noauth-smoketest@bidvex.com")

    # Call verify with NO Authorization header
    r = httpx.get(
        f"{API_URL}/api/unsubscribe/verify",
        params={"token": token},
        timeout=15,
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert "email_masked" in data
    assert "already_unsubscribed" in data


def test_confirm_with_valid_token_never_requires_auth():
    """POST confirm with a signed token must also be auth-free."""
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from routes.unsubscribe import generate_unsubscribe_token  # noqa: E402

    token = generate_unsubscribe_token("noauth-confirm-smoketest@bidvex.com")
    r = httpx.post(
        f"{API_URL}/api/unsubscribe/confirm",
        json={"token": token},
        timeout=15,
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert data.get("status") in {"success", "already_done"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
