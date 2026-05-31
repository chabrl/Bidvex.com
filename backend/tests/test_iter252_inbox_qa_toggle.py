"""
iter252 — Inbox QA toggle wired into the Launch Broadcast modal.

The toggle is a frontend UX safety control: when ON it appends
`recipient_emails: [admin_email]` to the POST body so the blast
endpoint routes the campaign back to the admin's inbox as a self-
preview. When OFF, the request body is unchanged from iter251 and the
endpoint resolves the real `target_config.custom_emails` audience.

These tests assert the BACKEND behaviour under both payload shapes is
correct end-to-end — frontend toggle wiring is verified via the
data-testid contracts in the linked PromotionManager.js source.

Test roster (5 tests):
  1. Toggle OFF: `POST {promotion_id}` (no recipient_emails) routes to
     the manual list defined on the promo's target_config.custom_emails.
  2. Toggle ON: `POST {promotion_id, recipient_emails=[admin]}` routes
     ONLY to the admin email — the manual list audience is bypassed.
  3. Toggle ON returns `is_preview=True` so the modal can render the
     amber/green "Test broadcast dispatched" toast and stay open.
  4. Toggle ON survives the same admin-auth gate (non-admin → 403).
  5. Toggle ON with a non-partner promo type still honors the override
     (recipient_emails takes precedence over target_config in every
     path — back-compat with iter247/iter248 self-preview semantics).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:
    pass


def _base() -> str:
    base = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not base:
        pytest.skip("REACT_APP_BACKEND_URL not configured")
    return base


_TOKEN = {"admin": None}


def _admin_token(base: str) -> str:
    if _TOKEN["admin"]:
        return _TOKEN["admin"]
    r = requests.post(
        f"{base}/api/auth/login",
        json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip("admin login failed")
    body = r.json()
    _TOKEN["admin"] = body.get("access_token") or body.get("token") or ""
    return _TOKEN["admin"]


def _make_partner_promo(base, token, custom_emails):
    body = {
        "name_en": f"iter252-toggle-{uuid.uuid4().hex[:6]}",
        "name_fr": "iter252-toggle-FR",
        "type": "partner_launch_offer",
        "config": {"scope": ["all"]},
        "target_config": {"target": "custom", "custom_emails": custom_emails},
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        "uses_per_user": 1,
        "show_banner": False, "notify_users": False,
    }
    r = requests.post(
        f"{base}/api/admin/promotions",
        json=body, headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _delete_promo(base, token, pid):
    requests.delete(
        f"{base}/api/admin/promotions/{pid}",
        headers={"Authorization": f"Bearer {token}"}, timeout=10,
    )


# ─── Toggle OFF — production audience path ───────────────────────────

def test_iter252_toggle_off_routes_to_manual_audience():
    """When `recipient_emails` is OMITTED from the body (toggle OFF),
    the endpoint resolves the promo's `target_config.custom_emails`."""
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    manual = [
        f"iter252-real-1-{uuid.uuid4().hex[:6]}@example.com",
        f"iter252-real-2-{uuid.uuid4().hex[:6]}@example.com",
    ]
    promo = _make_partner_promo(base, token, manual)
    pid = promo["id"]
    try:
        r = requests.post(
            f"{base}/api/admin/promotions/partner-outreach/send",
            json={"promotion_id": pid, "dry_run": True},  # toggle OFF
            headers=headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # is_preview must be False when no recipient_emails was supplied.
        assert body["is_preview"] is False
        # Recipient list = manual audience (de-duplicated).
        got = sorted([row["email"].lower() for row in body["recipients"]])
        assert got == sorted([e.lower() for e in manual]), got
    finally:
        _delete_promo(base, token, pid)


# ─── Toggle ON — self-preview path ───────────────────────────────────

def test_iter252_toggle_on_redirects_blast_to_admin_inbox():
    """When `recipient_emails=[admin]` is supplied (toggle ON), the
    real audience is bypassed and the blast goes only to the admin."""
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    manual = [
        f"iter252-real-A-{uuid.uuid4().hex[:6]}@example.com",
        f"iter252-real-B-{uuid.uuid4().hex[:6]}@example.com",
    ]
    promo = _make_partner_promo(base, token, manual)
    pid = promo["id"]
    admin_email = "charbel911@gmail.com"
    try:
        r = requests.post(
            f"{base}/api/admin/promotions/partner-outreach/send",
            json={
                "promotion_id": pid,
                "recipient_emails": [admin_email],
                "dry_run": True,
            },
            headers=headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # is_preview flag flips ON.
        assert body["is_preview"] is True
        # Recipient list = ONLY the admin email.
        emails = [row["email"].lower() for row in body["recipients"]]
        assert emails == [admin_email.lower()], emails
        # Manual-list addresses must NOT appear.
        for m in manual:
            assert m.lower() not in emails, (m, emails)
    finally:
        _delete_promo(base, token, pid)


def test_iter252_toggle_on_returns_is_preview_true_for_toast_routing():
    """The amber/green 'Test broadcast dispatched' toast is keyed off
    `is_preview=True` in the response. Explicit assertion."""
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    promo = _make_partner_promo(base, token, ["recipient@example.com"])
    pid = promo["id"]
    try:
        r = requests.post(
            f"{base}/api/admin/promotions/partner-outreach/send",
            json={
                "promotion_id": pid,
                "recipient_emails": ["charbel911@gmail.com"],
                "dry_run": True,
            },
            headers=headers, timeout=20,
        )
        body = r.json()
        assert body["is_preview"] is True
        # And the recipient count == 1 so the toast can render
        # accurately.
        assert body["recipient_count"] == 1
    finally:
        _delete_promo(base, token, pid)


def test_iter252_toggle_on_still_requires_admin_auth():
    """Self-preview is admin-only — anonymous calls remain rejected."""
    base = _base()
    r = requests.post(
        f"{base}/api/admin/promotions/partner-outreach/send",
        json={
            "promotion_id": "any-promo-id",
            "recipient_emails": ["attacker@example.com"],
            "dry_run": True,
        },
        timeout=10,
    )
    assert r.status_code in (401, 403)


def test_iter252_recipient_emails_override_takes_precedence_over_target_config():
    """Back-compat: when `recipient_emails` is set, it ALWAYS wins —
    even if the promo's target_config has a `target` that points at a
    fully different audience (partners, tier, province, …). This is the
    semantic contract iter247/iter248 self-preview tests already
    validated; iter252 just confirms it still holds after the iter251
    custom-emails routing was added."""
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    # Build a promo whose target_config points at the all-partners
    # segment (no custom_emails).
    body = {
        "name_en": f"iter252-precedence-{uuid.uuid4().hex[:6]}",
        "name_fr": "iter252-precedence-FR",
        "type": "partner_launch_offer",
        "config": {"scope": ["all"]},
        "target_config": {"target": "partners"},  # ← would normally hit is_partner=True users
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        "uses_per_user": 1,
        "show_banner": False, "notify_users": False,
    }
    r = requests.post(f"{base}/api/admin/promotions", json=body, headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    override_email = "charbel911@gmail.com"
    try:
        rb = requests.post(
            f"{base}/api/admin/promotions/partner-outreach/send",
            json={
                "promotion_id": pid,
                "recipient_emails": [override_email],
                "dry_run": True,
            },
            headers=headers, timeout=20,
        )
        assert rb.status_code == 200, rb.text
        body = rb.json()
        # is_preview flag flipped + ONLY the override email lands.
        assert body["is_preview"] is True
        emails = [row["email"].lower() for row in body["recipients"]]
        assert emails == [override_email.lower()]
    finally:
        _delete_promo(base, token, pid)
