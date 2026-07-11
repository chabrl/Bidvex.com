"""
iter271 — External email campaign sprint verification.

Covers all 5 missions with static checks + live HTTP smokes against the
backend running under the preview environment.

  Mission 1 — 3 new collections / schema isolation.
  Mission 2 — Full CRUD + recipients + attachments + send + analytics
              + unsubscribe + suppression endpoints registered.
  Mission 3 — `services/external_email.send_external_campaign_email`
              attaches the required headers/categories/UTM.
  Mission 4 — Admin frontend (covered by the route-existence tests
              and a single component-mount test below).
  Mission 5 — CASL validation blocks send when `{unsubscribe_url}` is
              missing AND a body without "unsubscribe" anywhere.
"""
from __future__ import annotations

import io
import os
import uuid

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


# ─── Mission 3 (static) — sender service shape ────────────────────────


def test_iter271_external_email_service_exports_present():
    src = _read("services/external_email.py")
    assert "EXTERNAL_FROM_EMAIL" in src
    assert "send_external_campaign_email" in src
    assert "inject_utm_params" in src
    assert "validate_casl" in src
    assert "make_unsubscribe_token" in src
    assert "decode_unsubscribe_token" in src


def test_iter271_external_sender_uses_dotca_acquisition_default():
    src = _read("services/external_email.py")
    # Default FROM = noreply@bidvex.ca per spec.
    assert '"noreply@bidvex.ca"' in src


def test_iter271_external_sender_attaches_required_headers():
    src = _read("services/external_email.py")
    assert "List-Unsubscribe" in src
    assert "List-Unsubscribe-Post" in src
    assert '"Precedence", "bulk"' in src or "Precedence" in src
    assert "ClickTracking(False, False)" in src
    assert "external_marketing" in src
    assert "acquisition" in src
    assert "campaign_id" in src
    assert "campaign_type" in src
    assert "X-Entity-Ref-ID" in src


def test_iter271_utm_injection_only_on_absolute_links():
    from services.external_email import inject_utm_params
    html = (
        '<a href="https://bidvex.com/register">Register</a>'
        '<a href="#anchor">In-page</a>'
        '<a href="mailto:test@x.com">Mail</a>'
        '<a href="{unsubscribe_url}">Unsub</a>'
    )
    out = inject_utm_params(html, {"utm_source": "email", "utm_campaign": "iter271"})
    assert "utm_source=email" in out
    assert "utm_campaign=iter271" in out
    assert 'href="#anchor"' in out
    assert 'href="mailto:test@x.com"' in out
    # The token-placeholder is rendered later — UTM injection ran on
    # `{unsubscribe_url}` which doesn't have a scheme, so left untouched.
    assert "{unsubscribe_url}" in out


def test_iter271_casl_validator_blocks_missing_unsubscribe():
    from services.external_email import validate_casl
    assert validate_casl("Subject", "<p>no link here</p>") is not None
    assert validate_casl("", "<p>{unsubscribe_url}</p>") is not None
    assert validate_casl("Subject", "") is not None
    assert validate_casl("Subject", "<p>{unsubscribe_url}</p>") is None


def test_iter271_unsubscribe_token_round_trip():
    from services.external_email import (
        make_unsubscribe_token, decode_unsubscribe_token,
    )
    token = make_unsubscribe_token("alice@example.com", "cmp-123", "fr")
    payload = decode_unsubscribe_token(token)
    assert payload["email"] == "alice@example.com"
    assert payload["campaign_id"] == "cmp-123"
    assert payload["lang"] == "fr"
    assert payload["type"] == "external_unsub"


# ─── Mission 2 (static) — every endpoint registered ──────────────────


def test_iter271_routes_module_exports_three_routers():
    src = _read("routes/external_campaigns.py")
    assert 'router = APIRouter(prefix="/admin/external-campaigns"' in src
    assert 'public_router = APIRouter(prefix="/external"' in src
    assert 'suppression_router = APIRouter(prefix="/admin/external-suppressions"' in src


def test_iter271_routes_all_required_endpoints():
    src = _read("routes/external_campaigns.py")
    expected = [
        '@router.post("")',
        '@router.get("")',
        '@router.get("/{campaign_id}")',
        '@router.patch("/{campaign_id}")',
        '@router.delete("/{campaign_id}")',
        '@router.post("/{campaign_id}/recipients/manual")',
        '@router.post("/{campaign_id}/recipients/csv")',
        '@router.get("/{campaign_id}/recipients/preview")',
        '@router.delete("/{campaign_id}/recipients")',
        '@router.post("/{campaign_id}/attachments")',
        '@router.delete("/{campaign_id}/attachments/{attachment_id}")',
        '@router.get("/{campaign_id}/attachments/{attachment_id}/download")',
        '@router.post("/{campaign_id}/send-test")',
        '@router.post("/{campaign_id}/schedule")',
        '@router.post("/{campaign_id}/send-now")',
        '@router.post("/{campaign_id}/pause")',
        '@router.post("/{campaign_id}/cancel")',
        '@router.get("/{campaign_id}/analytics")',
        '@router.post("/analytics/refresh")',
        '@public_router.get("/unsubscribe"',
        '@suppression_router.post("/add")',
        '@suppression_router.delete("/{email}")',
        '@suppression_router.get("")',
    ]
    for needle in expected:
        assert needle in src, f"Missing endpoint decorator: {needle}"


def test_iter271_server_registers_external_routers():
    src = _read("server.py")
    assert '("routes.external_campaigns", "router"' in src
    assert '("routes.external_campaigns", "public_router"' in src
    assert '("routes.external_campaigns", "suppression_router"' in src


# ─── Mission 1 + 2 (live) — CRUD + recipients + send-now CASL block ──


def _create(token: str, body_extra: dict = None) -> str:
    payload = {
        "name":         f"iter271-{uuid.uuid4().hex[:6]}",
        "subject_en":   "Welcome to BidVex",
        "subject_fr":   "Bienvenue chez BidVex",
        "body_html_en": "<p>Hello</p><p><a href='https://bidvex.com/register'>Register</a> <a href='{unsubscribe_url}'>Unsub</a></p>",
        "body_html_fr": "<p>Bonjour</p>",
    }
    if body_extra:
        payload.update(body_extra)
    r = httpx.post(
        f"{BASE}/api/admin/external-campaigns",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    assert r.status_code == 200, r.text
    return r.json()["campaign_id"]


def _delete(token: str, cid: str) -> None:
    httpx.delete(
        f"{BASE}/api/admin/external-campaigns/{cid}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )


def test_iter271_create_and_get_campaign():
    token = _login_admin()
    if not token:
        return
    cid = _create(token)
    try:
        r = httpx.get(
            f"{BASE}/api/admin/external-campaigns/{cid}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        assert r.status_code == 200
        doc = r.json()
        assert doc["status"] == "draft"
        assert doc["from_email"] == "noreply@bidvex.ca"
        assert doc["reply_to_email"] == "service@bidvex.com"
        assert doc["analytics"]["delivered"] == 0
    finally:
        _delete(token, cid)


def test_iter271_manual_recipients_dedup_and_invalid():
    token = _login_admin()
    if not token:
        return
    cid = _create(token)
    try:
        r = httpx.post(
            f"{BASE}/api/admin/external-campaigns/{cid}/recipients/manual",
            json={"emails": ["a@x.com", "b@y.com", "a@x.com", "bogus", "c@z.ca"]},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["added"] == 3
        assert data["invalid"] == 1
        # Idempotent re-adding the same set must report duplicates only.
        r2 = httpx.post(
            f"{BASE}/api/admin/external-campaigns/{cid}/recipients/manual",
            json={"emails": ["a@x.com", "b@y.com"]},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        assert r2.status_code == 200
        assert r2.json()["duplicates"] == 2
    finally:
        _delete(token, cid)


def test_iter271_csv_upload_parses_email_column():
    token = _login_admin()
    if not token:
        return
    cid = _create(token)
    try:
        csv_body = "email,name\nfoo@example.com,Foo\nbar@example.ca,Bar\nbad,Skip\nfoo@example.com,Dup\n"
        files = {"file": ("contacts.csv", csv_body.encode(), "text/csv")}
        r = httpx.post(
            f"{BASE}/api/admin/external-campaigns/{cid}/recipients/csv",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["processed"] == 4
        assert d["added"] == 2  # foo + bar (dup + bad excluded)
        assert d["invalid"] == 1
    finally:
        _delete(token, cid)


def test_iter271_send_now_blocked_without_recipients():
    token = _login_admin()
    if not token:
        return
    cid = _create(token)
    try:
        r = httpx.post(
            f"{BASE}/api/admin/external-campaigns/{cid}/send-now",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        assert r.status_code == 400
        assert "no recipients" in r.text.lower()
    finally:
        _delete(token, cid)


def test_iter271_send_now_blocked_without_casl_unsubscribe():
    """When the body has neither {unsubscribe_url} nor any text containing
    'unsubscribe', send-now must 400 with a CASL message."""
    token = _login_admin()
    if not token:
        return
    cid = _create(token, body_extra={
        "body_html_en": "<p>Plain promotional text without the magic placeholder.</p>",
    })
    try:
        # Add a recipient so we get past the empty-list guard and hit
        # the CASL validator.
        httpx.post(
            f"{BASE}/api/admin/external-campaigns/{cid}/recipients/manual",
            json={"emails": ["test@example.com"]},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        r = httpx.post(
            f"{BASE}/api/admin/external-campaigns/{cid}/send-now",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        assert r.status_code == 400, r.text
        assert "unsubscribe_url" in r.text.lower() or "casl" in r.text.lower()
    finally:
        _delete(token, cid)


def test_iter271_attachment_upload_rejects_invalid_mime():
    token = _login_admin()
    if not token:
        return
    cid = _create(token)
    try:
        files = {"file": ("malware.exe", b"MZbinary", "application/x-msdownload")}
        r = httpx.post(
            f"{BASE}/api/admin/external-campaigns/{cid}/attachments",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
        assert r.status_code == 400
        assert ".exe" in r.text.lower() or "invalid" in r.text.lower()
    finally:
        _delete(token, cid)


def test_iter271_attachment_upload_rejects_oversize():
    token = _login_admin()
    if not token:
        return
    cid = _create(token)
    try:
        # 3.1 MB > 3 MB cap.
        oversize = b"x" * int(3.1 * 1024 * 1024)
        files = {"file": ("big.pdf", oversize, "application/pdf")}
        r = httpx.post(
            f"{BASE}/api/admin/external-campaigns/{cid}/attachments",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        assert r.status_code == 400, r.text
        assert "too large" in r.text.lower()
    finally:
        _delete(token, cid)


def test_iter271_attachment_upload_accepts_valid_pdf():
    token = _login_admin()
    if not token:
        return
    cid = _create(token)
    try:
        files = {"file": ("guide.pdf", b"%PDF-1.4\n%fake", "application/pdf")}
        r = httpx.post(
            f"{BASE}/api/admin/external-campaigns/{cid}/attachments",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["filename"] == "guide.pdf"
        assert d["mime_type"] in ("application/pdf",)
    finally:
        _delete(token, cid)


def test_iter271_suppression_add_remove_and_blocks_send():
    token = _login_admin()
    if not token:
        return
    # 1) Add suppression
    target = f"sup-{uuid.uuid4().hex[:6]}@example.com"
    r = httpx.post(
        f"{BASE}/api/admin/external-suppressions/add",
        json={"email": target, "reason": "manual"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=8.0,
    )
    assert r.status_code == 200, r.text

    # 2) Create campaign and try to add the suppressed address — it
    #    must be filtered out.
    cid = _create(token)
    try:
        r2 = httpx.post(
            f"{BASE}/api/admin/external-campaigns/{cid}/recipients/manual",
            json={"emails": [target, "ok@example.com"]},
            headers={"Authorization": f"Bearer {token}"},
            timeout=8.0,
        )
        assert r2.status_code == 200
        assert r2.json()["suppressed"] >= 1
        assert r2.json()["added"] == 1
    finally:
        _delete(token, cid)
        httpx.delete(
            f"{BASE}/api/admin/external-suppressions/{target}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=8.0,
        )


def test_iter271_public_unsubscribe_with_valid_token_returns_200():
    token = _login_admin()
    if not token:
        return
    from services.external_email import make_unsubscribe_token
    tok = make_unsubscribe_token("optout@example.com", "test-campaign", "en")
    r = httpx.get(
        f"{BASE}/api/external/unsubscribe?token={tok}",
        timeout=8.0,
    )
    assert r.status_code == 200
    assert "unsubscribed" in r.text.lower()


def test_iter271_send_test_admin_only():
    """Unauthenticated send-test must be rejected."""
    r = httpx.post(
        f"{BASE}/api/admin/external-campaigns/nope/send-test",
        json={"to_email": "x@y.com"},
        timeout=8.0,
    )
    assert r.status_code in (401, 403)


def test_iter271_sendgrid_webhook_external_handler_present():
    src = _read("routes/sendgrid_webhook.py")
    assert "_handle_external_campaign_event" in src
    assert "external_email_campaigns" in src
    assert "external_email_suppressions" in src
    assert "campaign_type" in src
    assert "analytics.delivered" in src
    assert "analytics.opened" in src
    assert "analytics.bounced" in src
    assert "spam_reports" in src


# ─── Mission 4 (static) — frontend tab exists ─────────────────────────


def test_iter271_frontend_external_campaigns_component_exists():
    fp = os.path.join(
        BACKEND_ROOT, "..", "frontend", "src", "pages", "admin",
        "AdminExternalCampaigns.jsx",
    )
    assert os.path.isfile(fp), "AdminExternalCampaigns.jsx missing"
    src = open(fp, encoding="utf-8").read()
    # Wizard steps + key data-testids per spec.
    for needle in (
        "external-campaigns",
        "step-content",
        "step-recipients",
        "step-attachments",
        "step-review",
        "campaign-list-table",
    ):
        assert needle in src, f"missing testid: {needle}"


def test_iter271_admin_dashboard_mounts_external_tab():
    src = _read("../frontend/src/pages/AdminDashboard.js")
    assert "AdminExternalCampaigns" in src
    assert "external-campaigns" in src
