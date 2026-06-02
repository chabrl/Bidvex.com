"""
iter260 — Single bug fix: "Failed to create payment request" toast.

Root cause traced live in preview: some user rows returned by
`/api/admin/users` are marketing-list "contact-only" stubs with no
`id` field. When an admin clicked Request Payment on one, the URL
became `/api/admin/users/undefined/request-payment` → 404 → toast
fallback "Failed to create payment request".

iter260 fixes:
  • Backend: explicit 400 with actionable message when path param
    is `undefined` / `null` / empty / whitespace.
  • Backend: full traceback + structured 500 surfacing the exception
    type so future failures aren't swallowed.
  • Frontend: button disabled when `user.id` is falsy + raw error
    detail surfaced in the toast (validation arrays, 400/404 strings).
"""
from __future__ import annotations

import os
import re
from typing import Any

import httpx


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, "..", "frontend", "src"))


def _read(rel: str, root: str = BACKEND_ROOT) -> str:
    with open(os.path.join(root, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ─── Static-source assertions ─────────────────────────────────────────

def test_iter260_backend_rejects_undefined_null_or_empty_user_id():
    src = _read("routes/admin_payment_requests.py")
    # The cleaned uid check covers the three garbage values the
    # frontend can stringify a missing id into.
    assert 'clean_uid.lower() in ("undefined", "null", "none")' in src
    # And the response surfaces a useful message (not a generic 404).
    assert "This user has no account ID" in src
    assert "contact-only" in src
    # Status code is 400 (client bug), not 404 (user resource missing).
    assert "status_code=400" in src


def test_iter260_backend_wraps_handler_with_traceback_logging():
    src = _read("routes/admin_payment_requests.py")
    assert "import traceback" in src
    assert "traceback.print_exc()" in src
    # The handler body delegates to `_build_payment_request` inside a
    # try/except that re-raises HTTPExceptions verbatim and converts
    # everything else into a structured 500.
    assert "_build_payment_request(" in src
    assert "except HTTPException:" in src
    assert "type(e).__name__" in src
    # Stripe-related crash hardening from iter259 must still be in place.
    assert "stripe_payment_link_url = None" in src


def test_iter260_frontend_disables_button_on_missing_user_id():
    src = _read("pages/admin/EnhancedUserManager.js", root=FRONTEND_ROOT)
    # The button now disables when `user.id` is falsy and shows a
    # tooltip explaining why.
    m = re.search(
        r"setReqPayModal\(\{ open: true, user \}\)[\s\S]{0,400}?disabled=\{!user\.id\}",
        src,
    )
    assert m, "Request Payment button must disable when user.id is missing"
    # Submit handler also short-circuits with a clear toast.
    assert "no registered account" in src
    assert "Request Payment is unavailable." in src


def test_iter260_frontend_surfaces_real_backend_error_in_toast():
    src = _read("pages/admin/EnhancedUserManager.js", root=FRONTEND_ROOT)
    # The catch block logs `e.response.status` + `e.response.data` so
    # admins can debug from the browser console, AND it surfaces
    # 422 validation arrays / 400/404 detail strings in the toast.
    assert "console.error('[request-payment] error:'" in src
    assert "Array.isArray(detail)" in src
    assert "Validation:" in src


# ─── Live curl regression — production-shape contract ────────────────

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
    token = r.json().get("access_token") or r.json().get("token")
    if not token:
        import pytest
        pytest.skip("no token in login response")
    return token


def _admin_id(token: str) -> str:
    base = _base()
    me = httpx.get(
        f"{base}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    ).json()
    return me.get("id") or ""


def test_iter260_live_undefined_user_id_returns_400_with_actionable_message():
    base = _base()
    token = _admin_token()
    r = httpx.post(
        f"{base}/api/admin/users/undefined/request-payment",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "subtotal": 100,
            "tax_type": "gst",
            "custom_tax_rate": None,
            "total_amount": 105,
            "description": "Test",
            "internal_notes": "",
            "send_email": False,
            "send_notification": False,
            "expiry_hours": 48,
        },
        timeout=20,
    )
    assert r.status_code == 400, f"expected 400 actionable; got {r.status_code} {r.text[:200]}"
    detail = r.json().get("detail", "")
    assert "no account ID" in detail
    assert "contact-only" in detail


def test_iter260_live_valid_user_with_send_email_returns_200():
    """End-to-end: the realistic admin flow (send_email=true,
    send_notification=true) must succeed. iter258's stale
    `stripe.error.StripeError` 500 bug stays fixed."""
    base = _base()
    token = _admin_token()
    user_id = _admin_id(token)
    assert user_id, "could not resolve admin id for self-target test"

    r = httpx.post(
        f"{base}/api/admin/users/{user_id}/request-payment",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "subtotal": 100,
            "tax_type": "gst",
            "custom_tax_rate": None,
            "total_amount": 105,
            "description": "iter260 live smoke",
            "internal_notes": "",
            "send_email": True,
            "send_notification": True,
            "expiry_hours": 48,
        },
        timeout=20,
    )
    assert r.status_code == 200, f"expected 200; got {r.status_code} {r.text[:200]}"
    body = r.json()
    assert body.get("success") is True
    # Either a real payment_link OR a warning. Never both null without a warning.
    assert body.get("payment_link") or body.get("warning")


def test_iter260_live_unauthorized_returns_401_not_500():
    base = _base()
    r = httpx.post(
        f"{base}/api/admin/users/anything/request-payment",
        headers={"Content-Type": "application/json"},
        json={
            "subtotal": 100,
            "tax_type": "gst",
            "total_amount": 105,
            "description": "x",
            "internal_notes": "",
            "send_email": False,
            "send_notification": False,
            "expiry_hours": 48,
        },
        timeout=20,
    )
    assert r.status_code in (401, 403), f"expected 401/403; got {r.status_code}"
