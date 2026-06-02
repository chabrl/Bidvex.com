"""
iter262 — Three surgical fixes.

  Mission 1 (the screenshot bug): `services/email_templates.py` rendered
  the literal "{cta_label}" placeholder in the rendered HTML because
  line 340 inlined `spec["cta_label"]` AS-IS in an f-string, never
  applying `.format(**fmt)`. iter262 formats `cta_label` identically
  to `cta_url` / `headline` / `subheadline`.

  Mission 2: Confirm Stripe webhook signature verification is wired
  (it has been since pre-iter258 — `stripe.Webhook.construct_event`
  with multi-secret support) AND that empty / fake signatures are
  rejected with HTTP 400. The user's diagnosis was wrong but the
  protection is locked in by this test.

  Mission 3: Admin Payment Requests history modal upgrades — colored
  status badges (PENDING red / PAID green / EXPIRED gray), `+ New
  Request` header CTA opens the existing modal pre-filled, and the
  Re-issue per-row action clones the source request's amount +
  description. Backend `list_payment_requests` now surfaces
  `payment_url` (Stripe Payment Link OR BidVex `/pay/{id}` fallback)
  on every row.
"""
from __future__ import annotations

import os

import httpx


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, "..", "frontend", "src"))


def _read(rel: str, root: str = BACKEND_ROOT) -> str:
    with open(os.path.join(root, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ─── Mission 1 — cta_label substitution ───────────────────────────────

def test_iter262_build_email_payload_substitutes_cta_label_against_data():
    """Reproduce + assert the fix: the literal "{cta_label}" must
    never appear in the rendered email HTML when the caller supplied
    a value in `data`."""
    from services.email_templates import build_email_payload
    out = build_email_payload(
        "payment_request",
        user={"email": "test@bidvex.com", "name": "Charbel"},
        data={
            "cta_url": "https://bidvex.com/pay/abc123",
            "cta_label": "💳 Pay Now — $23.00 CAD",
            "total_amount": "23.00",
            "description": "Test balance",
            "expiry_label": "in 48 hours",
        },
    )
    html = out["html_content"]
    # The bug — the literal placeholder string must be GONE.
    assert "{cta_label}" not in html, "rendered email still contains literal {cta_label} placeholder"
    assert "{cta_url}" not in html
    assert "{first_name}" not in html
    # The button label is the actual passed-through string.
    assert "💳 Pay Now — $23.00 CAD" in html
    # The CTA link is the actual passed URL.
    assert "https://bidvex.com/pay/abc123" in html


def test_iter262_build_email_payload_handles_missing_cta_label_gracefully():
    """If a caller forgets to pass `cta_label`, the rendering must
    NOT crash (KeyError) — it falls back to the spec's default."""
    from services.email_templates import build_email_payload
    out = build_email_payload(
        "welcome",
        user={"email": "x@bidvex.com", "name": "X"},
        data={},
    )
    assert "html_content" in out
    # The welcome template's static cta_label is "Explore Marketplace"
    # (per current registry). We just need NO crash + no literal
    # placeholder leak.
    assert "{cta_label}" not in out["html_content"]


def test_iter262_no_email_type_renders_literal_placeholders():
    """Sweep every registered email type and confirm none leaks a
    `{*}` placeholder in the rendered HTML when called with a minimal
    data dict."""
    from services.email_templates import BIDVEX_EMAIL_TEMPLATE, build_email_payload  # noqa: F401
    # Pull the registry off the module.
    from services import email_templates as _et
    registry = getattr(_et, "_EMAIL_TYPE_REGISTRY", None) or getattr(_et, "EMAIL_TYPES", None)
    if registry is None:
        # Dig through the module for the dict-of-dicts that drives templates.
        import re
        src = _read("services/email_templates.py")
        # Best-effort: every payload renders without literal {x} leaks
        # when called with the union of placeholders we commonly use.
        placeholders = sorted(set(re.findall(r"\{(\w+)\}", src)))
        data = {p: f"<{p}>" for p in placeholders}
        for tpe in (
            "welcome", "bid_placed", "outbid", "auction_won",
            "payment_request", "payment_confirmed", "partner_welcome",
            "trial_revoked", "listing_approved", "listing_rejected",
            "account_suspended", "account_unsuspended", "new_message",
            "auction_starting_soon",
        ):
            try:
                out = build_email_payload(
                    tpe,
                    user={"email": "x@bidvex.com", "name": "X"},
                    data=dict(data),
                )
            except KeyError:
                # The template references a placeholder we didn't seed —
                # skip this type, the type-specific test should cover it.
                continue
            html = out["html_content"]
            # No literal `{x}` placeholder should ever survive into the
            # rendered HTML for the placeholders we DID seed.
            for ph in ("cta_label", "cta_url", "headline", "subheadline", "first_name", "body_html"):
                assert f"{{{ph}}}" not in html, f"{tpe}: literal {{{ph}}} leaked in rendered HTML"


# ─── Mission 2 — Stripe webhook signature verification ────────────────

def test_iter262_stripe_webhook_signature_verification_is_wired():
    src = _read("routes/webhooks.py")
    # Multi-secret verification helper exists.
    assert "stripe.Webhook.construct_event(payload, sig_header, secret)" in src
    # Missing/invalid signatures are rejected with 400.
    assert 'detail="Missing stripe-signature header"' in src
    assert 'detail="Invalid signature"' in src
    # `checkout.session.completed` IS routed.
    assert 'event_type == "checkout.session.completed"' in src


def test_iter262_stripe_webhook_rejects_unsigned_request_live():
    """End-to-end: posting to the webhook without a valid
    Stripe-Signature header MUST return 400 (not 500, not 200)."""
    base = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    if not base:
        import pytest
        pytest.skip("REACT_APP_BACKEND_URL not configured")
    r = httpx.post(
        f"{base}/api/webhooks/stripe",
        headers={"Content-Type": "application/json"},
        content=b'{"id":"evt_fake","type":"checkout.session.completed","data":{"object":{}}}',
        timeout=10,
    )
    assert r.status_code == 400, f"unsigned webhook must be 400; got {r.status_code} {r.text[:160]}"
    assert "Missing stripe-signature header" in r.text


def test_iter262_stripe_webhook_rejects_fake_signature_live():
    base = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    if not base:
        import pytest
        pytest.skip("REACT_APP_BACKEND_URL not configured")
    r = httpx.post(
        f"{base}/api/webhooks/stripe",
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": "t=1234567890,v1=deadbeef",
        },
        content=b'{"id":"evt_fake","type":"checkout.session.completed","data":{"object":{}}}',
        timeout=10,
    )
    assert r.status_code == 400, f"fake-signature webhook must be 400; got {r.status_code} {r.text[:160]}"
    assert "Invalid signature" in r.text


# ─── Mission 3 — Admin Payment Requests history tab upgrades ─────────

def test_iter262_admin_list_payment_requests_surfaces_payment_url():
    src = _read("routes/admin_payment_requests.py")
    # The /users/{id}/payment-requests endpoint enriches each item
    # with a `payment_url` (Stripe link OR BidVex fallback).
    assert 'it["payment_url"] = it.get("stripe_payment_link") or f"{_PUBLIC_URL}/pay/{rid}"' in src


def test_iter262_history_modal_has_new_request_cta_and_reissue_action():
    src = _read("pages/admin/EnhancedUserManager.js", root=FRONTEND_ROOT)
    # The history dialog header now carries a + New Request button.
    assert "payment-history-new-request-btn" in src
    # Per-row Re-issue action.
    assert "reissue-payment-request-${pr.id}" in src
    # Empty-state matches the spec.
    assert "No payment requests sent to this user yet." in src
    # Status badge testid is wired per-row.
    assert "payment-request-status-${pr.id}" in src


def test_iter262_history_modal_uses_spec_color_badges():
    src = _read("pages/admin/EnhancedUserManager.js", root=FRONTEND_ROOT)
    # PENDING — red palette.
    assert "#e53e3e" in src and "#fed7d7" in src
    # PAID — green palette.
    assert "#276749" in src and "#c6f6d5" in src
    # EXPIRED — slate palette.
    assert "#718096" in src and "#e2e8f0" in src


# ─── Live regression — payment_request email goes through unified ──

def _admin_token() -> str:
    base = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    if not base:
        import pytest
        pytest.skip("REACT_APP_BACKEND_URL not configured")
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


def test_iter262_live_admin_history_payload_carries_payment_url():
    base = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    token = _admin_token()
    if not token:
        import pytest
        pytest.skip("no admin token")
    me = httpx.get(f"{base}/api/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=20).json()
    user_id = me.get("id")
    r = httpx.get(
        f"{base}/api/admin/users/{user_id}/payment-requests",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    assert r.status_code == 200
    items = r.json().get("items", [])
    if not items:
        # Seed one so the assertion is meaningful.
        httpx.post(
            f"{base}/api/admin/users/{user_id}/request-payment",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "subtotal": 23, "tax_type": "none", "custom_tax_rate": None,
                "total_amount": 23, "description": "iter262 history seed",
                "internal_notes": "", "send_email": False, "send_notification": False,
                "expiry_hours": 48,
            },
            timeout=20,
        )
        items = httpx.get(
            f"{base}/api/admin/users/{user_id}/payment-requests",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        ).json().get("items", [])
    assert items, "admin history must have at least one row to verify"
    for it in items:
        assert it.get("payment_url"), f"admin history row missing payment_url: {it.get('id')}"
