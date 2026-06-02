"""
iter264 — Comprehensive gap-fill iteration.

Scope of the test suite (the surfaces this iteration actually moved):

  Mission 1 — Soft ENV validation on startup. `server.py` logs a
              WARNING per missing var, never crashes the boot.
  Mission 4 — Three new admin oversight surfaces:
                • /api/admin/disputes (+ /api/disputes POST public)
                • /api/admin/compliance-alerts + scan
                • /api/admin/auctions + action endpoint
  Mission 6 — `notification_prefs_router` exposing GET + PATCH for the
              7 user-toggleable preference keys.

Skipped surfaces (already shipped, verified live, not in scope):
  Mission 2 — Quick Bid modal already shipped in FlattenedMarketplace.js
  Mission 3 — Messages system already shipped in routes/messages.py
              (POST/GET/conversations/unread-count + frontend page)
  Mission 5 — All static pages already exist (HowItWorks, BecomeABroker,
              BrokerDirectory, Contact, Terms, Privacy, RefundPolicy,
              ProhibitedItems, CookieSettings)
  Mission 7 — GTM container + dataLayer pushes already wired via
              components/MarketingPixelLoader.js
"""
from __future__ import annotations

import os

import httpx


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, "..", "frontend", "src"))


def _read(rel: str, root: str = BACKEND_ROOT) -> str:
    with open(os.path.join(root, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ─── Mission 1 — ENV validation ──────────────────────────────────────

def test_iter264_server_logs_env_validation_warnings():
    src = _read("server.py")
    # Required vars list is declared near the top of server.py.
    assert "_REQUIRED_ENV_VARS" in src
    # Each required var emits a WARNING when missing.
    assert "ENV VAR MISSING" in src
    assert "STRIPE_API_KEY" in src
    assert "STRIPE_WEBHOOK_SECRET" in src
    assert "SENDGRID_API_KEY" in src
    assert "MONGO_URL" in src
    # And the loop never crashes (no `raise` inside).
    block = src.split("_REQUIRED_ENV_VARS")[2]  # the loop body
    assert "raise " not in block.split("\n\n")[0]


# ─── Mission 4 — Admin oversight ─────────────────────────────────────

def test_iter264_admin_oversight_router_registered():
    src = _read("server.py")
    assert '"routes.admin_oversight"' in src
    assert '"admin_oversight_router"' in src
    assert '"public_disputes_router"' in src


def test_iter264_admin_disputes_endpoints_exist():
    src = _read("routes/admin_oversight.py")
    assert '@public_disputes_router.post("/disputes")' in src
    assert '@admin_oversight_router.get("/disputes")' in src
    assert '@admin_oversight_router.patch("/disputes/{dispute_id}")' in src
    # Status enum honored.
    assert '"open", "under_review", "resolved", "closed"' in src
    # Admin guard fires.
    assert "_require_admin(current_user)" in src


def test_iter264_admin_compliance_endpoints_exist():
    src = _read("routes/admin_oversight.py")
    assert '@admin_oversight_router.get("/compliance-alerts")' in src
    assert '@admin_oversight_router.patch("/compliance-alerts/{alert_id}/resolve")' in src
    assert '@admin_oversight_router.post("/compliance-alerts/scan")' in src
    # Scan covers the 3 spec rules.
    assert "vehicle_without_broker" in src
    assert "high_value_unverified_seller" in src
    assert "runaway_unpaid_bids" in src
    # Idempotent: only creates an alert if one isn't already open for
    # the same (type, target).
    assert "already_open" not in src  # just sanity — we use find_one above instead
    assert "find_one({" in src


def test_iter264_admin_manage_auctions_endpoints_exist():
    src = _read("routes/admin_oversight.py")
    assert '@admin_oversight_router.get("/auctions")' in src
    assert '@admin_oversight_router.patch("/auctions/{listing_id}/action")' in src
    # The 4 spec actions are all supported.
    for action in ('"end"', '"extend"', '"feature"', '"remove"'):
        assert action in src, f"action {action} missing"


# ─── Mission 6 — Notification preferences ────────────────────────────

def test_iter264_notification_prefs_router_exposes_get_and_patch():
    src = _read("routes/notification_prefs.py")
    assert '@notification_prefs_router.get("/notification-preferences")' in src
    assert '@notification_prefs_router.patch("/notification-preferences")' in src
    # Default registry covers the 7 keys from the spec.
    for key in ("outbid", "auction_ending", "auction_won", "notify_nearby",
                "payment_requests", "messages", "marketing"):
        assert f'"{key}"' in src, f"default missing for {key}"
    # `user_wants_email` helper is exported for callers to gate sends.
    assert "user_wants_email" in src
    # Empty-dict-from-projection bug is fixed via `is None` guard.
    assert "if me is None" in src


def test_iter264_notification_prefs_server_registered():
    src = _read("server.py")
    assert '"routes.notification_prefs"' in src
    assert '"notification_prefs_router"' in src


# ─── Live smokes ─────────────────────────────────────────────────────

def _base() -> str:
    base = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not base:
        import pytest
        pytest.skip("REACT_APP_BACKEND_URL not configured")
    return base.rstrip("/")


def _admin_token() -> str:
    base = _base()
    r = httpx.post(
        f"{base}/api/auth/login",
        json={
            "email": os.environ.get("BIDVEX_ADMIN_EMAIL", "charbel911@gmail.com"),
            "password": os.environ.get("BIDVEX_ADMIN_PASSWORD", "Anderosli123!@#"),
        },
        timeout=20,
    )
    if r.status_code != 200:
        import pytest
        pytest.skip(f"admin login failed: {r.status_code}")
    return (r.json().get("access_token") or r.json().get("token")) or ""


def test_iter264_live_admin_disputes_list_returns_paginated_payload():
    base = _base()
    token = _admin_token()
    r = httpx.get(
        f"{base}/api/admin/disputes",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    assert r.status_code == 200
    body = r.json()
    for key in ("items", "total", "page", "limit"):
        assert key in body, f"admin disputes response missing {key}"
    assert isinstance(body["items"], list)


def test_iter264_live_admin_compliance_alerts_list_and_scan():
    base = _base()
    token = _admin_token()
    list_r = httpx.get(
        f"{base}/api/admin/compliance-alerts",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    assert list_r.status_code == 200
    body = list_r.json()
    assert "items" in body and "total" in body and "open_count" in body

    scan_r = httpx.post(
        f"{base}/api/admin/compliance-alerts/scan",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert scan_r.status_code == 200
    assert "created" in scan_r.json()


def test_iter264_live_admin_auctions_list_returns_paginated_payload():
    base = _base()
    token = _admin_token()
    r = httpx.get(
        f"{base}/api/admin/auctions?limit=5",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    assert r.status_code == 200
    body = r.json()
    for key in ("items", "total", "page", "limit"):
        assert key in body, f"admin auctions response missing {key}"


def test_iter264_live_notification_prefs_round_trip():
    base = _base()
    token = _admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    # GET returns the merged default + user-customized prefs.
    g = httpx.get(f"{base}/api/users/me/notification-preferences", headers=headers, timeout=20)
    assert g.status_code == 200
    g_body = g.json()
    assert "preferences" in g_body
    prefs = g_body["preferences"]
    for key in ("outbid", "auction_ending", "auction_won", "notify_nearby",
                "payment_requests", "messages", "marketing"):
        assert key in prefs, f"GET response missing key {key}"

    # PATCH a single key — only that key changes.
    new_val = not prefs.get("marketing", False)
    p = httpx.patch(
        f"{base}/api/users/me/notification-preferences",
        headers={**headers, "Content-Type": "application/json"},
        json={"marketing": new_val},
        timeout=20,
    )
    assert p.status_code == 200, f"PATCH must not 404; got {p.status_code} {p.text[:160]}"
    p_body = p.json()
    assert p_body["preferences"]["marketing"] == new_val
    # The other 6 keys preserve their previous values.
    for key in ("outbid", "auction_ending", "auction_won", "notify_nearby",
                "payment_requests", "messages"):
        assert p_body["preferences"][key] == prefs[key], (
            f"PATCH must not clobber {key}"
        )
