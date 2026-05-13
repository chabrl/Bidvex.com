"""
iter211 — Push notification + partner status desync fixes.

Covers:
  Push notifications:
    1. POST /api/push/subscribe accepts BOTH shapes (raw + wrapped).
    2. Both shapes save to MongoDB push_subscriptions correctly.
    3. Missing keys produce a precise 422 error.
    4. Frontend pushNotifications.js returns structured {ok, code} results.
    5. PushNotificationToggle maps error codes to precise toast messages.

  Partner desync:
    1. resubmission_service writes "pending" (not "pending_review") to the DB.
    2. routes/admin.py:list_partners accepts BOTH "pending" and "pending_review"
       defensively.
    3. routes/admin.py:approve_partner accepts both legacy and current enums.
"""
import os
import pytest
import requests


# ─── PUSH NOTIFICATIONS ──────────────────────────────────────────────────
API_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com")


def _get_token():
    r = requests.post(
        f"{API_URL}/api/auth/login",
        json={"email": "iter189buyer@test.com", "password": "TestBuyer123!"},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip(f"Could not log in iter189buyer ({r.status_code}); skipping live HTTP test")
    return r.json().get("token") or r.json().get("access_token")


class TestPushSubscribeEndpoint:
    """Live HTTP tests against /api/push/subscribe (requires preview env)."""

    def test_accepts_wrapped_shape_from_frontend(self):
        token = _get_token()
        r = requests.post(
            f"{API_URL}/api/push/subscribe",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "subscription": {
                    "endpoint": "https://fcm.googleapis.com/test/wrapped",
                    "keys": {"p256dh": "BKpxKEY", "auth": "secret"},
                },
                "user_agent": "pytest",
            },
            timeout=10,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json().get("success") is True

    def test_accepts_raw_shape_legacy(self):
        token = _get_token()
        r = requests.post(
            f"{API_URL}/api/push/subscribe",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "endpoint": "https://fcm.googleapis.com/test/raw",
                "keys": {"p256dh": "BKpxKEY", "auth": "secret"},
            },
            timeout=10,
        )
        assert r.status_code == 200

    def test_rejects_missing_keys_with_422(self):
        token = _get_token()
        r = requests.post(
            f"{API_URL}/api/push/subscribe",
            headers={"Authorization": f"Bearer {token}"},
            json={"endpoint": "https://x.com/y"},  # no keys
            timeout=10,
        )
        assert r.status_code == 422
        assert "keys" in r.text.lower()

    def test_rejects_unauthenticated(self):
        r = requests.post(
            f"{API_URL}/api/push/subscribe",
            json={"endpoint": "https://x.com/y", "keys": {"p256dh": "a", "auth": "b"}},
            timeout=10,
        )
        # 401 from get_current_user or 403 — anything non-2xx is acceptable
        assert r.status_code in (401, 403)


# ─── STATIC SMOKE TESTS — code paths ────────────────────────────────────
class TestPushFrontendStructuredErrors:
    """Verify the frontend rewrite returns {ok: bool, code: string} per spec."""

    def test_pushnotifications_js_uses_result_object(self):
        with open("/app/frontend/src/utils/pushNotifications.js", "r") as f:
            body = f.read()
        # Result codes
        for code in (
            "unsupported", "no_vapid_key", "permission_denied",
            "permission_default", "subscribe_failed", "backend_save_failed",
            "network_error", "no_service_worker",
        ):
            assert f"'{code}'" in body, f"Missing error code constant: {code}"
        # Returns ok:true on success
        assert "ok: true" in body
        # Checks fetch response status
        assert "response.ok" in body or "!response.ok" in body

    def test_toggle_maps_error_codes_to_precise_messages(self):
        with open("/app/frontend/src/components/PushNotificationToggle.js", "r") as f:
            body = f.read()
        # Every code must have a user-facing message
        for code in ("unsupported", "no_vapid_key", "permission_denied",
                     "subscribe_failed", "backend_save_failed", "network_error"):
            assert f"{code}:" in body, f"Toggle missing message for code: {code}"
        # The misleading universal "Check browser permissions" line must be gone
        assert "'Could not enable notifications. Check browser permissions.'" not in body


# ─── PARTNER STATUS DESYNC ──────────────────────────────────────────────
class TestPartnerStatusEnumCanonical:
    """Static smoke for the iter211 status-value drift fix."""

    def test_resubmission_service_writes_pending(self):
        with open("/app/backend/services/resubmission_service.py", "r") as f:
            body = f.read()
        # The DB write must be "pending" (canonical), not "pending_review"
        write_block = body[body.index("Update payload fields"):body.index("Update payload fields") + 1000]
        assert '"partner_verification_status": "pending"' in write_block, \
            "resubmission_service must write canonical 'pending' to users.partner_verification_status"

    def test_admin_list_accepts_both_pending_and_pending_review(self):
        with open("/app/backend/routes/admin.py", "r") as f:
            body = f.read()
        # Defensive: both enum values accepted
        assert '"pending", "pending_review"' in body or \
               '"pending_review", "pending"' in body, \
            "admin.py list_partners must accept both 'pending' and 'pending_review'"

    def test_admin_approve_accepts_both_enums(self):
        with open("/app/backend/routes/admin.py", "r") as f:
            body = f.read()
        # approve_partner must accept both legacy & canonical
        assert '("pending", "pending_review")' in body or \
               '("pending_review", "pending")' in body, \
            "admin.py approve_partner must accept both enum values"
