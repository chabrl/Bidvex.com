"""
iter321: Verify TWILIO_VERIFY_SID dead-env cleanup did not regress Twilio functionality.

Scope:
  1. /app/backend/.env contains TWILIO_VERIFY_SERVICE_SID but NOT TWILIO_VERIFY_SID
  2. No Python source references to TWILIO_VERIFY_SID
  3. GET /api/twilio/config (admin) returns fully-configured response
  4. POST /api/twilio/token mints a JWT
  5. get_verify_service_sid() fail-fast behavior on missing env var
"""
import os
import re
import subprocess
import importlib
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


# ---- 1. .env file content check ----
def test_env_file_has_verify_service_sid_only():
    with open("/app/backend/.env", "r") as f:
        content = f.read()
    assert "TWILIO_VERIFY_SERVICE_SID" in content, "TWILIO_VERIFY_SERVICE_SID must remain in .env"
    # ensure no standalone TWILIO_VERIFY_SID= line
    matches = re.findall(r"^TWILIO_VERIFY_SID\s*=", content, re.MULTILINE)
    assert len(matches) == 0, f"Found dead TWILIO_VERIFY_SID line(s) in .env: {matches}"


# ---- 2. Source grep for dead reference ----
def test_no_source_references_to_dead_env_var():
    result = subprocess.run(
        ["grep", "-rn", "TWILIO_VERIFY_SID", "/app/backend/", "--include=*.py",
         "--exclude=test_iter321_twilio_cleanup.py"],
        capture_output=True, text=True,
    )
    # Filter out the (valid) TWILIO_VERIFY_SERVICE_SID matches
    bad_lines = [
        line for line in result.stdout.splitlines()
        if "TWILIO_VERIFY_SID" in line and "TWILIO_VERIFY_SERVICE_SID" not in line
    ]
    assert bad_lines == [], f"Dead TWILIO_VERIFY_SID references found:\n" + "\n".join(bad_lines)


# ---- 3 & 4. Live API checks (require backend reachable) ----
@pytest.fixture(scope="module")
def admin_token():
    try:
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=20,
        )
    except Exception as e:
        pytest.skip(f"Backend unreachable: {e}")
    if r.status_code == 429:
        pytest.skip("Rate-limited (429) on admin login - acceptable per request")
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token returned: {data}"
    return token


def test_twilio_config_endpoint_healthy(admin_token):
    r = requests.get(
        f"{BASE_URL}/api/twilio/config",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=20,
    )
    assert r.status_code == 200, f"twilio/config failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    assert data.get("configured") is True, f"configured!=true: {data}"
    assert data.get("can_mint_tokens") is True, f"can_mint_tokens!=true: {data}"
    assert data.get("can_place_calls") is True, f"can_place_calls!=true: {data}"
    missing = data.get("missing", [])
    assert missing == [] or missing is None, f"missing list should be empty: {missing}"


def test_twilio_token_mint(admin_token):
    r = requests.post(
        f"{BASE_URL}/api/twilio/token",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=20,
    )
    assert r.status_code == 200, f"twilio/token failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    token = data.get("token") or data.get("access_token") or data.get("jwt")
    assert token and isinstance(token, str) and len(token) > 50, f"Bad JWT: {data}"
    # Twilio JWTs are JWS - 3 dot-separated parts
    assert token.count(".") == 2, f"Token does not look like a JWT: {token[:60]}..."


# ---- 5. Fail-fast behavior of get_verify_service_sid() ----
def test_get_verify_service_sid_returns_when_set():
    import sys
    sys.path.insert(0, "/app/backend")
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env", override=False)
    from routes import sms_verification
    importlib.reload(sms_verification)
    sid = sms_verification.get_verify_service_sid()
    assert sid, "Should return non-empty SID when env var set"
    assert sid.startswith("VA"), f"Expected SID to start with VA, got: {sid}"


def test_get_verify_service_sid_raises_when_missing():
    import sys
    sys.path.insert(0, "/app/backend")
    from routes import sms_verification

    original = os.environ.pop("TWILIO_VERIFY_SERVICE_SID", None)
    try:
        with pytest.raises(RuntimeError) as exc_info:
            sms_verification.get_verify_service_sid()
        msg = str(exc_info.value)
        assert "TWILIO_VERIFY_SERVICE_SID" in msg, f"Error msg should mention env var name: {msg}"
    finally:
        if original is not None:
            os.environ["TWILIO_VERIFY_SERVICE_SID"] = original
