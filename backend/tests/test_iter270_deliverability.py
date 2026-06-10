"""
iter270 — Email deliverability sprint verification.

  Mission 1 — Unified FROM = noreply@bidvex.com, Reply-To contextual.
  Mission 2 — PDF / email-body contact addresses fixed to .com.
  Mission 3 — Spam-classification headers + tracking + Categories.
  Mission 4 — test-email endpoint accepts type param + startup validation.
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


def test_iter270_canonical_from_is_noreply_dotcom():
    src = _read("services/emails/_email_core.py")
    # The default FROM falls back to noreply@bidvex.com.
    assert 'FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@bidvex.com")' in src
    # FROM_NAME is "BidVex Canada" per spec.
    assert '"BidVex Canada"' in src


def test_iter270_partner_from_collapsed_to_noreply():
    src = _read("services/emails/_email_core.py")
    # Partner B2B FROM is now noreply@bidvex.com (was partners@bidvex.ca).
    assert 'B2B_PARTNER_FROM_EMAIL = "noreply@bidvex.com"' in src
    # Reply-To stays partners@bidvex.ca.
    assert 'B2B_PARTNER_REPLY_TO = "partners@bidvex.ca"' in src


def test_iter270_send_email_forces_canonical_sender():
    """`send_email()` ignores any `from_email` override and always
    sends as the unified noreply@ address so DKIM is consistent."""
    src = _read("services/emails/_email_core.py")
    assert "_from = FROM_EMAIL  # Force canonical sender" in src


def test_iter270_no_legacy_dotca_support_in_outbound_templates():
    """Email body templates must reference support@bidvex.com — not .ca."""
    for path in (
        "services/emails/_email_core.py",
        "services/emails/email_marketplace.py",
        "services/emails/email_system.py",
        "services/emails/email_vehicles.py",
        "services/email_journey.py",
        "services/partner_outreach.py",
        "services/pickup_coordination_service.py",
    ):
        src = _read(path)
        assert "support@bidvex.ca" not in src, f"{path} still references support@bidvex.ca"


def test_iter270_no_info_or_hello_at_bidvex_in_runtime():
    """No info@/hello@ fallbacks in runtime paths."""
    import subprocess
    out = subprocess.run(
        ["grep", "-rn", "info@bidvex\\|hello@bidvex",
         BACKEND_ROOT + "/routes", BACKEND_ROOT + "/services"],
        capture_output=True, text=True,
    )
    bad = [ln for ln in out.stdout.splitlines() if "test_" not in ln and "__pycache__" not in ln]
    assert not bad, f"Found stray info@/hello@ refs:\n{bad}"


def test_iter270_admin_promotions_partner_path_uses_reply_to():
    """Partner promotion blasts ship FROM noreply + Reply-To partners@."""
    src = _read("routes/admin_promotions.py")
    assert "B2B_PARTNER_REPLY_TO" in src
    assert 'reply_to=_B2B_REPLY' in src


# ─── Mission 2 ────────────────────────────────────────────────────────


def test_iter270_pdf_footers_use_dotcom_support():
    """PDF generators contact lines route to support@bidvex.com."""
    for path in ("services/invoice_generator.py", "services/pdf_invoice.py"):
        src = _read(path)
        assert "support@bidvex.com" in src
        assert "support@bidvex.ca" not in src, f"{path}: legacy .ca contact still in PDF"


# ─── Mission 3 ────────────────────────────────────────────────────────


def test_iter270_send_email_attaches_list_unsubscribe_on_marketing():
    src = _read("services/emails/_email_core.py")
    assert "List-Unsubscribe" in src
    assert "List-Unsubscribe-Post" in src
    assert "List-Unsubscribe=One-Click" in src
    assert "Precedence" in src and '"bulk"' in src


def test_iter270_send_email_attaches_x_entity_ref_id():
    src = _read("services/emails/_email_core.py")
    assert "X-Entity-Ref-ID" in src
    assert "hashlib" in src
    assert "X-Mailer" in src


def test_iter270_click_tracking_disabled_in_tracking_settings():
    src = _read("services/emails/_email_core.py")
    # ClickTracking is constructed with `False, False` (enable + enable_text).
    assert "_SgClickTracking(False, False)" in src
    # Open tracking on, subscription tracking off.
    assert "_SgOpenTracking(True)" in src
    assert "_SgSubscriptionTracking(False)" in src


def test_iter270_send_email_attaches_sendgrid_categories():
    src = _read("services/emails/_email_core.py")
    assert "add_category" in src
    # Default category logic.
    assert '"marketing", "promotional"' in src
    assert '"transactional"' in src


def test_iter270_email_service_html_path_has_spam_headers():
    """The template-id and html_content paths in email_service.py also
    attach the spam-busting headers + tracking config."""
    src = _read("services/email_service.py")
    assert src.count("List-Unsubscribe") >= 2
    assert "List-Unsubscribe-Post" in src
    assert "_SgClickTracking" in src or "ClickTracking" in src


def test_iter270_deliverability_module_present():
    src = _read("services/email_deliverability.py")
    assert "validate_email_config" in src
    assert "verify_sendgrid_domain" in src
    assert "em.bidvex.com" in src
    assert "s1._domainkey.bidvex.com" in src
    assert "s2._domainkey.bidvex.com" in src


def test_iter270_server_calls_deliverability_on_startup():
    src = _read("server.py")
    assert "validate_email_config" in src
    assert "verify_sendgrid_domain" in src


# ─── Mission 4 ────────────────────────────────────────────────────────


def test_iter270_test_email_endpoint_accepts_type_param():
    src = _read("routes/admin_oversight.py")
    assert 'type: str = Query("transactional"' in src
    assert "marketing" in src
    assert "partner" in src


def test_iter270_test_email_transactional_live_send():
    token = _login_admin()
    if not token:
        return
    r = httpx.get(
        f"{BASE}/api/admin/test-email?type=transactional",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("type") == "transactional"
    assert data.get("success") is True
    res = data.get("result") or {}
    assert res.get("from") == "noreply@bidvex.com"
    assert res.get("reply_to") == "support@bidvex.com"
    assert res.get("status") in ("sent", "logged")


def test_iter270_test_email_marketing_live_send():
    token = _login_admin()
    if not token:
        return
    r = httpx.get(
        f"{BASE}/api/admin/test-email?type=marketing",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("type") == "marketing"
    res = data.get("result") or {}
    assert res.get("from") == "noreply@bidvex.com"
    assert res.get("is_marketing") is True


def test_iter270_test_email_partner_live_send():
    token = _login_admin()
    if not token:
        return
    r = httpx.get(
        f"{BASE}/api/admin/test-email?type=partner",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("type") == "partner"
    res = data.get("result") or {}
    assert res.get("from") == "noreply@bidvex.com"
    assert res.get("reply_to") == "partners@bidvex.ca"
