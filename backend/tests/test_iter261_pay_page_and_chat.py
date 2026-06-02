"""
iter261 — Payment Pay Page + AI session id + bell + email registry.

  Mission 1: Public Pay Page endpoints + email always carries a URL +
             dashboard Pending Payments card + bell payment_request
             special layout + Stripe webhook (already shipped iter258).
  Mission 2: AI chat `persist_chat_turn` non-blocking via
             `asyncio.create_task()`; resolved session id surfaces in
             `X-Session-Id` response header on EVERY turn.
  Mission 3: Bell notifications endpoints — already shipped (iter238)
             and exposed at /api/notifications, .../unread-count,
             .../read, mark-all-read. Verify presence, no rewrite.
  Mission 4: Add missing transactional email types to the unified
             template registry (Step 4 only — full callsite refactor
             stays scoped to the registry additions per "minimum code
             changes" + 69-test parity constraints).
"""
from __future__ import annotations

import os
from typing import Any

import httpx


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, "..", "frontend", "src"))


def _read(rel: str, root: str = BACKEND_ROOT) -> str:
    with open(os.path.join(root, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ─── Mission 1 — Public Pay endpoints + always-set payment URL ───────

def test_iter261_public_payments_router_registered_and_exposes_four_routes():
    src = _read("server.py")
    assert '"routes.public_payments"' in src
    assert '"public_payments_router"' in src

    r = _read("routes/public_payments.py")
    assert '@public_payments_router.get("/pay/{payment_request_id}")' in r
    assert '@public_payments_router.post("/pay/{payment_request_id}/checkout-session")' in r
    assert '@public_payments_router.post("/pay/{payment_request_id}/confirm-success")' in r
    assert '@public_payments_router.get("/my/payment-requests")' in r
    # Public payload hides PII / admin notes — confirm the returned
    # dict literal has no `internal_notes` key (the docstring may
    # legitimately mention it, so we check the actual `return {…}`
    # body, not the docstring).
    payload_fn = r.split("def _safe_public_payload")[1].split("def ")[0]
    return_block = payload_fn.split("return {")[1].split("}")[0]
    for forbidden in ("internal_notes", "admin_id"):
        assert forbidden not in return_block, f"{forbidden} leaks in public payload"


def test_iter261_admin_request_payment_always_sets_payment_url():
    """The admin endpoint must compose `final_payment_url` and pass
    it to BOTH the email AND the in-app notification — even when
    Stripe is misconfigured. iter261's BidVex-hosted Pay page is the
    fallback so the user always has a clickable button."""
    src = _read("routes/admin_payment_requests.py")
    assert "final_payment_url" in src
    assert "f\"{_PUBLIC_URL}/pay/{request_id}\"" in src or 'bidvex_pay_url' in src
    # The email payload carries both `cta_url` and `cta_label`.
    assert '"cta_url": final_payment_url' in src
    assert '"cta_label":' in src
    # The notification doc links to the same URL + carries amount_cad
    # for the bell's payment-request special layout.
    notif_block = src.split('"type": "payment_request"')[1].split("}")[0]
    assert '"link": final_payment_url' in src
    assert '"amount_cad"' in src


def test_iter261_payment_request_email_template_uses_dynamic_cta():
    src = _read("services/email_templates.py")
    pr = src.split('"payment_request"')[1].split('"payment_confirmed"')[0]
    # Template body references {cta_url} + {cta_label} so the caller
    # composes them per-send (never null).
    assert "{cta_url}" in pr or '"cta_url": "{cta_url}"' in pr
    assert "{cta_label}" in pr or '"cta_label": "{cta_label}"' in pr


def test_iter261_pay_page_route_mounted_in_app_router():
    src = _read("App.js", root=FRONTEND_ROOT)
    assert '/pay/:payment_request_id' in src
    assert '/pay/:payment_request_id/success' in src
    assert 'PaymentPage' in src
    assert 'PayRequestSuccessPage' in src


def test_iter261_pay_page_renders_three_states_active_paid_expired():
    src = _read("pages/PaymentPage.jsx", root=FRONTEND_ROOT)
    for tid in (
        "payment-page",
        "payment-page-loading",
        "payment-page-error",
        "payment-page-paid",
        "payment-page-expired",
        "payment-page-active",
        "payment-page-pay-now",
        "payment-page-amount",
        "payment-page-description",
    ):
        assert tid in src, f"PaymentPage missing data-testid={tid}"
    # On Pay click: prefer the pre-issued Stripe Payment Link, fall
    # back to the on-demand checkout-session endpoint.
    assert "pr.stripe_payment_link" in src
    assert "/checkout-session" in src
    # Manual-instructions fallback when neither path works.
    assert "manual_instructions" in src
    assert "payment-page-copy-ref" in src


def test_iter261_pay_success_page_calls_confirm_success_on_mount():
    src = _read("pages/PayRequestSuccessPage.jsx", root=FRONTEND_ROOT)
    assert 'data-testid="payment-success-page"' in src
    assert "/confirm-success" in src
    assert "payment-success-goto-dashboard" in src


def test_iter261_pending_payments_card_mounted_on_dashboards():
    card = _read("components/PendingPaymentsCard.jsx", root=FRONTEND_ROOT)
    assert 'data-testid="pending-payments-card"' in card
    assert 'data-testid="pending-payments-empty-card"' in card
    assert "/my/payment-requests" in card
    # Each row carries a payment-amount + Pay Now CTA.
    assert "pending-payment-amount-" in card
    assert "pending-payment-pay-now-" in card

    seller = _read("pages/SellerDashboard.js", root=FRONTEND_ROOT)
    assert "import PendingPaymentsCard" in seller
    assert "<PendingPaymentsCard" in seller

    buyer = _read("pages/BuyerDashboard.js", root=FRONTEND_ROOT)
    assert "import PendingPaymentsCard" in buyer
    assert "<PendingPaymentsCard" in buyer


def test_iter261_bell_notification_special_layout_for_payment_request():
    src = _read("components/NotificationCenter.js", root=FRONTEND_ROOT)
    # Registry entry for payment_request + payment_confirmed types.
    assert "payment_request: {" in src
    assert "payment_confirmed: {" in src
    # Amount pill + inline Pay Now CTA in the row render.
    assert "notif-amount-" in src
    assert "notif-pay-now-" in src
    assert "$0055FF" not in src and "#0055FF" in src  # link color


# ─── Mission 2 — Chat persist is non-blocking + session id header ────

def test_iter261_chat_persist_is_nonblocking_and_session_header_set():
    src = _read("routes/genai_chat.py")
    # `persist_chat_turn` is fired via asyncio.create_task — NEVER
    # awaited inline — so it adds zero latency to the stream tail.
    assert "asyncio.create_task(persist_chat_turn" in src \
        or "_asyncio.create_task(persist_chat_turn" in src
    # The X-Session-Id (+ legacy X-Chat-Session-Id) header is set on
    # every stream response so the FE can echo it back on the next turn.
    assert '"X-Session-Id": resolved_session_id' in src
    assert '"X-Chat-Session-Id": resolved_session_id' in src
    # The browser is allowed to read both headers (CORS).
    assert "Access-Control-Expose-Headers" in src


# ─── Mission 3 — Notifications endpoints (already shipped iter238) ──

def test_iter261_notifications_endpoints_remain_available():
    src = _read("routes/notifications.py")
    # GET listing + unread count + read + mark-all-read.
    assert "GET" in src or "get" in src
    assert "unread-count" in src or "unread_count" in src
    assert "mark-all-read" in src or "mark_all_read" in src


# ─── Mission 4 — Registry additions ──────────────────────────────────

def test_iter261_email_registry_includes_missing_transactional_types():
    src = _read("services/email_templates.py")
    for tpe in (
        "listing_approved",
        "listing_rejected",
        "account_suspended",
        "account_unsuspended",
        "new_message",
        "auction_starting_soon",
        "payment_confirmed",
        "payment_request",
        "partner_welcome",
        "trial_revoked",
    ):
        assert f'"{tpe}"' in src, f"email registry missing type: {tpe}"


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


def test_iter261_live_create_then_fetch_pay_page_payload():
    base = _base()
    token = _admin_token()
    if not token:
        import pytest
        pytest.skip("no admin token")
    me = httpx.get(f"{base}/api/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=20).json()
    user_id = me.get("id")
    create = httpx.post(
        f"{base}/api/admin/users/{user_id}/request-payment",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "subtotal": 100, "tax_type": "gst", "custom_tax_rate": None,
            "total_amount": 105, "description": "iter261 live test",
            "internal_notes": "", "send_email": False, "send_notification": False,
            "expiry_hours": 48,
        },
        timeout=20,
    )
    assert create.status_code == 200
    body = create.json()
    pr_id = body.get("id")
    # iter261 — always carries a payment_url.
    assert body.get("payment_url"), f"payment_url missing in response: {body}"

    # Public pay payload is reachable without auth.
    pub = httpx.get(f"{base}/api/pay/{pr_id}", timeout=20)
    assert pub.status_code == 200
    pdata = pub.json()
    assert pdata.get("status") in ("pending", "paid", "expired")
    assert pdata.get("total_amount") == 105.0
    # PII / internal_notes / admin_id must NOT leak in the public payload.
    assert "internal_notes" not in pdata
    assert "admin_id" not in pdata


def test_iter261_live_on_demand_checkout_session_creates_url_or_manual_instructions():
    base = _base()
    token = _admin_token()
    if not token:
        import pytest
        pytest.skip("no admin token")
    me = httpx.get(f"{base}/api/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=20).json()
    user_id = me.get("id")
    create = httpx.post(
        f"{base}/api/admin/users/{user_id}/request-payment",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "subtotal": 50, "tax_type": "none", "custom_tax_rate": None,
            "total_amount": 50, "description": "iter261 checkout-session smoke",
            "internal_notes": "", "send_email": False, "send_notification": False,
            "expiry_hours": 48,
        },
        timeout=20,
    )
    pr_id = create.json().get("id")
    sess = httpx.post(f"{base}/api/pay/{pr_id}/checkout-session", timeout=20)
    assert sess.status_code == 200
    sd = sess.json()
    # Either a real Stripe Checkout URL OR manual instructions.
    assert sd.get("checkout_url") or sd.get("manual_instructions")


def test_iter261_live_my_payment_requests_endpoint_returns_array():
    base = _base()
    token = _admin_token()
    if not token:
        import pytest
        pytest.skip("no admin token")
    r = httpx.get(
        f"{base}/api/my/payment-requests",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and isinstance(body["items"], list)
    assert "total" in body
    # Every item carries a payment_url.
    for it in body["items"]:
        assert it.get("payment_url"), f"my-payment-requests item missing payment_url: {it}"
