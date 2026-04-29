"""
Iteration 162 — P0 Bug Fix Verification
Signup emails (welcome + admin notify) must fire non-blocking via BackgroundTasks
for both email/password and Google OAuth registrations.

Verifies:
1. POST /api/auth/register returns <2s (non-blocking)
2. Welcome email is transactional (marketing=False) → bypasses suppressions
3. Admin notification uses ADMIN_EMAIL=charbel911@gmail.com (NOT hardcoded)
4. Edge cases: duplicate email, missing consents → no email side-effects
5. Google OAuth callback code-path inspection for BackgroundTasks scheduling
6. admin_notifications.py _resolve_admin_email() env-var resolution logic
"""
import os
import re
import time
import uuid
import requests
import pytest
from pathlib import Path

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to frontend/.env
    env_file = Path("/app/frontend/.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

BACKEND_LOG = "/app/backend/routes/auth.py"  # sentinel, not read as log
SUPERVISOR_LOG = "/var/log/supervisor/backend.err.log"

# Store registered emails for log verification
_registered_emails = []


def _unique_email():
    return f"bgtask_test_{int(time.time())}_{uuid.uuid4().hex[:6]}@bidvex-test.com"


def _read_recent_log(tail_lines: int = 2000) -> str:
    try:
        from subprocess import check_output
        return check_output(["tail", "-n", str(tail_lines), SUPERVISOR_LOG], text=True, errors="ignore")
    except Exception as e:
        return f"[LOG_READ_ERROR] {e}"


# ═══════════════════════════════════════════════════════════════
# Code-path inspection tests (no HTTP)
# ═══════════════════════════════════════════════════════════════

class TestCodePathInspection:
    def test_admin_notifications_no_hardcoded_constant(self):
        src = Path("/app/backend/services/admin_notifications.py").read_text()
        # Ensure no module-level constant like: ADMIN_EMAIL = "info@bidvex.com"
        assert not re.search(r'^ADMIN_EMAIL\s*=\s*["\']', src, re.MULTILINE), \
            "admin_notifications.py should NOT have module-level hardcoded ADMIN_EMAIL"
        assert "_resolve_admin_email" in src, "Expected _resolve_admin_email() helper"
        assert "ADMIN_NOTIFICATION_EMAIL" in src
        assert "ADMIN_EMAIL" in src

    def test_resolve_admin_email_precedence(self):
        """ADMIN_NOTIFICATION_EMAIL → ADMIN_EMAIL → info@bidvex.com"""
        import sys
        sys.path.insert(0, "/app/backend")
        from services.admin_notifications import _resolve_admin_email

        orig_notif = os.environ.pop("ADMIN_NOTIFICATION_EMAIL", None)
        orig_admin = os.environ.pop("ADMIN_EMAIL", None)
        try:
            # Case 1: no env → fallback
            assert _resolve_admin_email() == "info@bidvex.com"

            # Case 2: only ADMIN_EMAIL set
            os.environ["ADMIN_EMAIL"] = "fallback@example.com"
            assert _resolve_admin_email() == "fallback@example.com"

            # Case 3: ADMIN_NOTIFICATION_EMAIL takes precedence
            os.environ["ADMIN_NOTIFICATION_EMAIL"] = "priority@example.com"
            assert _resolve_admin_email() == "priority@example.com"
        finally:
            os.environ.pop("ADMIN_EMAIL", None)
            os.environ.pop("ADMIN_NOTIFICATION_EMAIL", None)
            if orig_admin:
                os.environ["ADMIN_EMAIL"] = orig_admin
            if orig_notif:
                os.environ["ADMIN_NOTIFICATION_EMAIL"] = orig_notif

    def test_register_has_background_tasks_param(self):
        src = Path("/app/backend/routes/auth.py").read_text()
        # register signature
        assert re.search(
            r"async def register\([^)]*background_tasks:\s*BackgroundTasks", src
        ), "register() must accept background_tasks: BackgroundTasks"
        # Confirm scheduling code present
        assert "background_tasks.add_task(_send_welcome" in src
        assert "background_tasks.add_task(_notify_admin" in src
        assert "[SIGNUP_EMAILS] Scheduled welcome + admin notify" in src

    def test_google_oauth_callback_schedules_emails_for_new_users(self):
        src = Path("/app/backend/routes/auth.py").read_text()
        # Callback signature has BackgroundTasks
        assert re.search(
            r"async def google_oauth_callback\([^)]*background_tasks:\s*BackgroundTasks",
            src,
        ), "google_oauth_callback() must accept background_tasks: BackgroundTasks"
        # Extract google callback body
        gi = src.index("async def google_oauth_callback")
        body = src[gi: gi + 8000]
        # New user branch must schedule both tasks
        assert "background_tasks.add_task(_send_welcome, user)" in body
        assert "background_tasks.add_task(_notify_admin, user)" in body
        # Welcome scheduling must occur AFTER insert_one (new user branch)
        insert_idx = body.find("await db.users.insert_one(user.copy())")
        schedule_idx = body.find("background_tasks.add_task(_send_welcome, user)")
        assert insert_idx > 0 and schedule_idx > insert_idx, \
            "Welcome scheduling must happen after new-user insert"
        # Existing-user branch (after `else:`) must NOT schedule welcome
        else_idx = body.find("else:", insert_idx)
        assert else_idx > 0
        existing_branch = body[else_idx: else_idx + 4000]
        assert "add_task(_send_welcome" not in existing_branch, \
            "Existing Google user branch must NOT re-send welcome email"

    def test_send_welcome_email_is_transactional(self):
        src = Path("/app/backend/services/email_service.py").read_text()
        # Extract ONLY the send_welcome_email function body (until next 'async def' or 'def ')
        start = src.index("async def send_welcome_email")
        rest = src[start + 1:]
        # find next top-level def/async def
        m = re.search(r"\nasync def |\ndef ", rest)
        end = (start + 1 + m.start()) if m else len(src)
        block = src[start:end]
        assert "is_marketing=True" not in block, \
            "send_welcome_email must remain transactional (is_marketing defaults to False)"


# ═══════════════════════════════════════════════════════════════
# Live HTTP tests
# ═══════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def api():
    assert BASE_URL, "REACT_APP_BACKEND_URL missing"
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


class TestRegisterEmailPassword:
    def test_signup_returns_fast_and_schedules_emails(self, api):
        """Core test: signup <2s + [SIGNUP_EMAILS] Scheduled log line appears."""
        email = _unique_email()
        _registered_emails.append(email)
        payload = {
            "email": email,
            "password": "TestPass123!",
            "name": "BG Task Test",
            "terms_agreed": True,
            "ai_disclosure_consent": True,
        }
        t0 = time.time()
        r = api.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=10)
        elapsed = time.time() - t0

        assert r.status_code == 200, f"register failed: {r.status_code} {r.text[:300]}"
        assert elapsed < 2.0, f"register took {elapsed:.2f}s — should be <2s (non-blocking)"

        data = r.json()
        assert "access_token" in data or "token" in data, f"no token in response: {data}"

        # Poll logs for up to 10s for BackgroundTask execution
        found_scheduled = found_welcome = found_admin = False
        for _ in range(20):
            log = _read_recent_log(3000)
            if f"[SIGNUP_EMAILS] Scheduled welcome + admin notify for {email}" in log:
                found_scheduled = True
            if re.search(rf"\[EMAIL\] Sent:.*to={re.escape(email)}.*marketing=False", log):
                found_welcome = True
            if f"[ADMIN_EMAIL] Sent to charbel911@gmail.com" in log and f"New Signup - {email}" in log:
                found_admin = True
            if found_scheduled and found_welcome and found_admin:
                break
            time.sleep(0.5)

        assert found_scheduled, f"[SIGNUP_EMAILS] Scheduled log line NOT found for {email}"
        assert found_welcome, f"[EMAIL] Sent to={email} with marketing=False NOT found"
        assert found_admin, f"[ADMIN_EMAIL] Sent to charbel911@gmail.com for '{email}' NOT found"

    def test_second_signup_also_fires_emails(self, api):
        email = _unique_email()
        _registered_emails.append(email)
        payload = {
            "email": email,
            "password": "TestPass123!",
            "name": "BG Task Test 2",
            "terms_agreed": True,
            "ai_disclosure_consent": True,
        }
        t0 = time.time()
        r = api.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=10)
        elapsed = time.time() - t0
        assert r.status_code == 200
        assert elapsed < 2.0, f"{elapsed:.2f}s >= 2s"

        found = False
        for _ in range(20):
            log = _read_recent_log(3000)
            if f"[SIGNUP_EMAILS] Scheduled welcome + admin notify for {email}" in log:
                found = True
                break
            time.sleep(0.5)
        assert found, f"No [SIGNUP_EMAILS] log for {email}"


class TestRegisterEdgeCases:
    def test_duplicate_email_returns_400_no_email_sent(self, api):
        """Re-register first test email → 400, no new [SIGNUP_EMAILS] log."""
        if not _registered_emails:
            pytest.skip("No prior registered email")
        email = _registered_emails[0]

        log_before = _read_recent_log(500)
        count_before = log_before.count(f"[SIGNUP_EMAILS] Scheduled welcome + admin notify for {email}")

        payload = {
            "email": email,
            "password": "TestPass123!",
            "name": "Dup",
            "terms_agreed": True,
            "ai_disclosure_consent": True,
        }
        r = api.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=10)
        assert r.status_code == 400
        assert "already registered" in r.text.lower()

        time.sleep(2)
        log_after = _read_recent_log(1000)
        count_after = log_after.count(f"[SIGNUP_EMAILS] Scheduled welcome + admin notify for {email}")
        assert count_after == count_before, \
            f"Duplicate registration triggered new [SIGNUP_EMAILS] log (before={count_before}, after={count_after})"

    def test_missing_terms_agreed_returns_400(self, api):
        email = _unique_email()
        payload = {
            "email": email,
            "password": "TestPass123!",
            "name": "NoTerms",
            "terms_agreed": False,
            "ai_disclosure_consent": True,
        }
        r = api.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=10)
        assert r.status_code == 400
        assert "terms" in r.text.lower()

        time.sleep(1.5)
        log = _read_recent_log(500)
        assert f"[SIGNUP_EMAILS] Scheduled welcome + admin notify for {email}" not in log

    def test_missing_ai_disclosure_returns_400(self, api):
        email = _unique_email()
        payload = {
            "email": email,
            "password": "TestPass123!",
            "name": "NoAI",
            "terms_agreed": True,
            "ai_disclosure_consent": False,
        }
        r = api.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=10)
        assert r.status_code == 400
        # message mentions AI disclosure (EN or FR)
        assert "ai" in r.text.lower() or "ia" in r.text.lower()

        time.sleep(1.5)
        log = _read_recent_log(500)
        assert f"[SIGNUP_EMAILS] Scheduled welcome + admin notify for {email}" not in log


class TestThirdSignup:
    """Third signup to confirm pattern holds (modest count — emails deliver to real inbox).
    Register rate limit is 5/minute; wait to avoid 429 from prior tests."""
    def test_third_signup(self, api):
        # Retry w/ exponential backoff to clear rate-limit window (5/min)
        email = _unique_email()
        _registered_emails.append(email)
        payload = {
            "email": email,
            "password": "TestPass123!",
            "name": "BG Task 3",
            "terms_agreed": True,
            "ai_disclosure_consent": True,
        }
        r = None
        elapsed = 0.0
        for attempt in range(7):
            t0 = time.time()
            r = api.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=10)
            elapsed = time.time() - t0
            if r.status_code != 429:
                break
            time.sleep(12)  # wait out rate-limit window
        assert r is not None and r.status_code == 200, \
            f"third signup status={r.status_code if r else 'None'} body={r.text[:200] if r else ''}"
        assert elapsed < 2.0, f"elapsed={elapsed:.2f}s"

        found_welcome = found_admin = False
        for _ in range(20):
            log = _read_recent_log(3000)
            if re.search(rf"\[EMAIL\] Sent:.*to={re.escape(email)}.*marketing=False", log):
                found_welcome = True
            if f"[ADMIN_EMAIL] Sent to charbel911@gmail.com" in log and f"New Signup - {email}" in log:
                found_admin = True
            if found_welcome and found_admin:
                break
            time.sleep(0.5)
        assert found_welcome, f"welcome marketing=False NOT sent for {email}"
        assert found_admin, f"admin notify NOT sent for {email} to charbel911@gmail.com"
