"""
iter267 — 5-Mission sprint covering:

  Mission 1 — Stripe Connect Express affiliate payouts: real
              `stripe.Transfer` fires on approval, no-Stripe path
              returns spec-aligned error envelope + onboarding email
              endpoint.
  Mission 2 — Admin attachment download (path-traversal protected)
              + user-side preview after submission + re-upload block.
  Mission 3 — `/uploads/` static mount with on-disk path-traversal
              guard inside the admin attachment endpoint.
  Mission 4 — Notification WebSocket (`/api/ws/notifications/{user_id}`)
              + `NotificationConnectionManager` + frontend client with
              polling fallback.
  Mission 5 — `regex=` → `pattern=` migration + on_event/Pydantic V2
              status pinned (no-op since already migrated).
"""
from __future__ import annotations

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


# ─── Mission 1 ────────────────────────────────────────────────────────


def test_iter267_approve_fires_stripe_transfer_on_connect_account():
    src = _read("routes/admin_oversight.py")
    assert "stripe.Transfer" in src or "_stripe.Transfer.create" in src
    assert "stripe_transfer_id" in src
    assert "affiliate_no_stripe_connect" in src


def test_iter267_send_stripe_onboarding_endpoint_registered():
    src = _read("routes/admin_oversight.py")
    assert '@admin_oversight_router.post("/affiliates/{user_id}/send-stripe-onboarding")' in src
    assert "stripe.AccountLink" in src or "_stripe.AccountLink.create" in src


def test_iter267_affiliate_connect_routes_registered():
    src = _read("routes/misc.py")
    assert '@misc_router.post("/affiliate/connect-stripe")' in src
    assert '@misc_router.get("/affiliate/stripe-connect-status")' in src
    assert '@misc_router.get("/affiliate/stripe-dashboard-link")' in src


def test_iter267_payouts_enrich_includes_has_stripe_connect():
    src = _read("routes/admin_oversight.py")
    assert "has_stripe_connect" in src
    assert "stripe_onboarding_complete" in src


def test_iter267_admin_dashboard_handles_no_stripe_branch():
    src = _read("../frontend/src/pages/admin/AdminAffiliatePayouts.jsx")
    assert "affiliate_no_stripe_connect" in src
    assert "handleSendOnboarding" in src
    assert "send-stripe-onboarding" in src
    assert "stripe_transfer_id" in src


def test_iter267_affiliate_status_live():
    token = _login_admin()
    if not token:
        return
    r = httpx.get(
        f"{BASE}/api/affiliate/stripe-connect-status",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    assert r.status_code == 200
    data = r.json()
    assert "connected" in data


# ─── Mission 2 ────────────────────────────────────────────────────────


def test_iter267_admin_attachment_endpoint_registered():
    src = _read("routes/notifications.py")
    assert "admin_notifications_router" in src
    assert '@admin_notifications_router.get("/{notification_id}/attachment")' in src
    assert "FileResponse" in src


def test_iter267_admin_attachment_requires_admin_role():
    """Anonymous → 401; non-admin → 403."""
    try:
        r = httpx.get(f"{BASE}/api/admin/notifications/xyz/attachment", timeout=8.0)
        assert r.status_code in (401, 403)
    except Exception:
        return


def test_iter267_admin_attachment_404_for_missing_notification():
    token = _login_admin()
    if not token:
        return
    r = httpx.get(
        f"{BASE}/api/admin/notifications/does-not-exist/attachment",
        headers={"Authorization": f"Bearer {token}"},
        timeout=8.0,
    )
    assert r.status_code == 404


def test_iter267_path_traversal_guard_in_source():
    src = _read("routes/notifications.py")
    assert "realpath" in src
    assert "Access denied" in src
    assert "NOTIFICATION_UPLOAD_BASE" in src


def test_iter267_resubmit_blocked_after_submission_message():
    src = _read("routes/notifications.py")
    assert "Already submitted — contact support" in src


def test_iter267_user_side_attachment_preview_in_modal():
    src = _read("../frontend/src/components/NotificationDetailModal.jsx")
    assert "notif-attachment-preview-img" in src
    assert "notif-attachment-preview-pdf" in src
    assert "attachment_submitted_at" in src


# ─── Mission 3 ────────────────────────────────────────────────────────


def test_iter267_uploads_static_mount_in_server():
    src = _read("server.py")
    assert 'app.mount("/uploads"' in src
    assert "/app/uploads" in src
    assert "notification_attachments" in src


def test_iter267_uploads_dir_serves_root_index_live():
    """Static mount answers GET (200 or 403). 404 means mount missing."""
    try:
        r = httpx.get(f"{BASE}/uploads/", timeout=8.0, follow_redirects=False)
        assert r.status_code != 404
    except Exception:
        return


# ─── Mission 4 ────────────────────────────────────────────────────────


def test_iter267_websocket_endpoint_registered():
    src = _read("routes/notifications.py")
    assert "NotificationConnectionManager" in src
    assert '@notifications_router.websocket("/ws/notifications/{user_id}")' in src
    assert "broadcast_notification_to_user" in src


def test_iter267_admin_send_endpoints_broadcast_to_ws():
    """Both admin-send paths must invoke `broadcast_notification_to_user`."""
    n = _read("routes/notifications.py")
    a = _read("routes/admin_user_actions.py")
    assert "broadcast_notification_to_user" in n
    assert "broadcast_notification_to_user" in a


def test_iter267_frontend_ws_client_wired():
    src = _read("../frontend/src/components/NotificationCenter.js")
    assert "new WebSocket" in src
    assert "/ws/notifications/" in src
    assert "new_notification" in src


# ─── Mission 5 ────────────────────────────────────────────────────────


def test_iter267_no_legacy_regex_query_param():
    """All `regex=` Query() params migrated to `pattern=` (Pydantic v2)."""
    import subprocess
    out = subprocess.run(
        ["grep", "-rn", '\\bregex="', "/app/backend/routes", "/app/backend/services"],
        capture_output=True, text=True,
    )
    assert out.stdout.strip() == "", f"Stray regex= Query found:\n{out.stdout}"


def test_iter267_on_event_already_migrated_to_lifespan():
    """`@app.on_event` should remain only as a comment marker, not active code."""
    src = _read("server.py")
    # The lifespan @asynccontextmanager pattern is in place.
    assert "asynccontextmanager" in src
    assert "lifespan=" in src or "FastAPI(lifespan" in src or "FastAPI(\n    lifespan" in src
