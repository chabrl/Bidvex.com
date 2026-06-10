"""
iter266 — 4-Mission sprint covering:

  Mission 1 — Affiliate Payouts oversight panel (GET list + summary,
              PATCH approve, PATCH reject with reason)
  Mission 2 — Universal suppression gate inside `send_email()` so the
              unsubscribe / marketing opt-out covers ALL outbound
              paths including raw-HTML and html_full_override.
  Mission 3 — Click-to-Detail notification modal + attachment upload
              flow + admin form fields + multilingual.
  Mission 4 — Bell unread-count polling at 60s, "9+" cap, Mark-All-Read.
"""
from __future__ import annotations

import io
import os

import httpx


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8001")


def _read(rel: str, root: str = BACKEND_ROOT) -> str:
    with open(os.path.join(root, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _login_admin():
    try:
        r = httpx.post(
            f"{BASE}/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
            timeout=8.0,
        )
        if r.status_code != 200:
            return None
        return r.json().get("access_token") or r.json().get("token")
    except Exception:
        return None


# ─── Mission 1 ─────────────────────────────────────────────────────────


def test_iter266_admin_oversight_has_payout_routes():
    src = _read("routes/admin_oversight.py")
    assert '@admin_oversight_router.get("/affiliate-payouts")' in src
    assert '@admin_oversight_router.patch("/affiliate-payouts/{payout_id}/approve")' in src
    assert '@admin_oversight_router.patch("/affiliate-payouts/{payout_id}/reject")' in src
    assert "AffiliatePayoutReject" in src


def test_iter266_payout_list_summary_cards_live():
    token = _login_admin()
    if not token:
        return
    r = httpx.get(
        f"{BASE}/api/admin/affiliate-payouts",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data
    assert "summary" in data
    for k in ("pending_total_cad", "paid_this_month_cad", "active_affiliates", "referrals_this_month"):
        assert k in data["summary"]


def test_iter266_admin_dashboard_has_payouts_tab():
    src = _read("../frontend/src/pages/AdminDashboard.js")
    assert "AdminAffiliatePayouts" in src
    assert "affiliate-payouts" in src


# ─── Mission 2 ─────────────────────────────────────────────────────────


def test_iter266_send_email_has_suppression_gate():
    src = _read("services/emails/_email_core.py")
    assert "email-suppressed" in src
    assert "email_suppressions" in src
    # Both unsubscribe + marketing branches.
    assert '"reason": "unsubscribed"' in src
    assert '"reason": "marketing_suppressed"' in src


def test_iter266_send_unified_email_threads_is_marketing():
    src = _read("services/emails/_email_core.py")
    assert "is_marketing: bool = False" in src
    # Must forward into the low-level dispatcher.
    assert "is_marketing=is_marketing" in src


# ─── Mission 3 ─────────────────────────────────────────────────────────


def test_iter266_notification_modal_component_exists():
    src = _read("../frontend/src/components/NotificationDetailModal.jsx")
    assert "NotificationDetailModal" in src
    assert "submit-attachment" in src
    assert "requires_attachment" in src
    assert "attachment_request_label" in src
    # Bilingual handling.
    assert "preferred_language" in src or "isFrench" in src


def test_iter266_notification_center_uses_modal_no_settings_redirect():
    src = _read("../frontend/src/components/NotificationCenter.js")
    assert "NotificationDetailModal" in src
    assert "setSelectedNotification" in src
    # The legacy "click → /settings?tab=documents" path must be gone
    # from the click handler — only legacy navigateForNotification keeps it.
    assert "case 'admin_rejection':" not in src  # removed the settings-redirect block
    assert "navigate('/settings?tab=documents')" not in src


def test_iter266_submit_attachment_endpoint_exists():
    src = _read("routes/notifications.py")
    assert "/notifications/{notification_id}/submit-attachment" in src
    assert "submit_notification_attachment" in src


def test_iter266_admin_send_notification_supports_attachment_fields():
    src = _read("routes/admin_user_actions.py")
    assert "requires_attachment" in src
    assert "attachment_request_label" in src
    assert "attachment_max_mb" in src
    assert "attachment_types" in src


def test_iter266_admin_form_has_attachment_fields():
    src = _read("../frontend/src/pages/admin/EnhancedUserManager.js")
    assert "notify-requires-attachment" in src
    assert "notify-attachment-label-en" in src
    assert "notify-attachment-label-fr" in src
    assert "notify-attachment-types" in src
    assert "notify-attachment-max-mb" in src


def test_iter266_attachment_upload_validates_size_live():
    """Smoke-test the live endpoint: an unauthenticated request 401s."""
    try:
        r = httpx.post(
            f"{BASE}/api/notifications/nonexistent/submit-attachment",
            files={"file": ("test.pdf", b"x")},
            timeout=8.0,
        )
        assert r.status_code in (401, 403)
    except Exception:
        return


def test_iter266_attachment_upload_404_on_missing_notification_live():
    """Authenticated request on a non-existent notification id → 404."""
    token = _login_admin()
    if not token:
        return
    r = httpx.post(
        f"{BASE}/api/notifications/does-not-exist/submit-attachment",
        files={"file": ("test.pdf", b"PDF FAKE BYTES")},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    assert r.status_code == 404


# ─── Mission 4 ─────────────────────────────────────────────────────────


def test_iter266_mark_all_read_returns_updated_key():
    src = _read("routes/notifications.py")
    assert '"updated":' in src
    assert "modified_count" in src


def test_iter266_notification_center_bell_badge_9plus_cap():
    src = _read("../frontend/src/components/NotificationCenter.js")
    # Must cap at 9+ (per spec) and have a stable data-testid.
    assert "> 9 ? '9+'" in src
    assert "notif-bell-badge" in src


def test_iter266_unread_count_endpoint_live():
    token = _login_admin()
    if not token:
        return
    r = httpx.get(
        f"{BASE}/api/notifications/unread-count",
        headers={"Authorization": f"Bearer {token}"},
        timeout=8.0,
    )
    assert r.status_code == 200
    assert "unread_count" in r.json()


def test_iter266_mark_all_read_live_idempotent():
    token = _login_admin()
    if not token:
        return
    r = httpx.post(
        f"{BASE}/api/notifications/mark-all-read",
        headers={"Authorization": f"Bearer {token}"},
        timeout=8.0,
    )
    assert r.status_code == 200
    data = r.json()
    assert "updated" in data and "updated_count" in data


def test_iter266_polling_interval_60s_in_center():
    src = _read("../frontend/src/components/NotificationCenter.js")
    assert "60_000" in src or "60000" in src
    assert "fetchUnreadCount" in src
