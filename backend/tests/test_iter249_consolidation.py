"""
iter249 — Final consolidation sprint: self-preview wiring, B2B ROI
analytics, bilingual transactional emails, and XSS sanitization.

Test roster (15 tests):

  Mission 1 — Self-preview button (1 backend regression):
    1. Endpoint round-trip for `recipient_emails=[admin]` returns
       `is_preview=True` AND the recipient row carries `subject` +
       `pdf_filename` so the frontend toast can confirm what was sent.

  Mission 2 — B2B Partner Acquisition ROI block (3):
    2. Analytics dashboard endpoint returns a `partner_roi` block with
       the seven canonical keys.
    3. `partner_roi.partner_conversion_rate_pct` = 100 ×
       `partners_redeemed` / `total_registered_partners` (within
       rounding tolerance) when at least one partner exists.
    4. `projected_gmv_lift_cad` is non-negative.

  Mission 3 — Bilingual transactional emails (8):
    5. `_detect_language` matrix (QC, ON, AB, BC, empty, explicit pref).
    6. `send_invoice_created_email` swaps to "Facture …" for QC.
    7. `send_invoice_created_email` keeps "Invoice …" for ON.
    8. `send_payment_confirmation_email` swaps to "Paiement confirmé"
       for QC.
    9. `send_payment_confirmation_email` keeps English for ON.
   10. `send_auction_won_email` swaps to "Vous avez gagné !" for QC.
   11. `send_auction_won_email` keeps "You Won!" for ON.
   12. `send_dealer_license_approved_email` swaps to a FR-only subject
       for QC users.

  Mission 4 — XSS sanitization (3):
   13. `<script>`, `<iframe>`, `on*=` handlers, `javascript:` schemes
       are stripped.
   14. Standard formatting tags (`<p>`, `<a href="https://...">`,
       `<img src="https://...">`, `<table>`) survive intact.
   15. `sanitize_inline` strips ALL markup and trims whitespace.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

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


_TOKEN = {"v": None}


def _admin_token(base: str) -> str:
    if _TOKEN["v"]:
        return _TOKEN["v"]
    r = requests.post(
        f"{base}/api/auth/login",
        json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip("admin login failed")
    body = r.json()
    _TOKEN["v"] = body.get("access_token") or body.get("token") or ""
    return _TOKEN["v"]


# ─── Mission 1: Self-preview regression ──────────────────────────────

def test_iter249_self_preview_returns_actionable_response_for_frontend_toast():
    base = _base()
    token = _admin_token(base)
    r = requests.post(
        f"{base}/api/admin/promotions/partner-outreach/send",
        json={"recipient_emails": ["charbel911@gmail.com"], "dry_run": True},
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_preview"] is True
    # The toast surfaces the email and PDF filename; both must be present.
    assert body["recipient_count"] == 1
    row = body["recipients"][0]
    assert row["email"] == "charbel911@gmail.com"
    assert row["subject"]
    assert row["pdf_filename"].endswith(".pdf")


# ─── Mission 2: B2B ROI block ────────────────────────────────────────

def test_iter249_analytics_includes_partner_roi_block_with_canonical_keys():
    base = _base()
    token = _admin_token(base)
    r = requests.get(
        f"{base}/api/admin/promotions/analytics/dashboard?window_days=30",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "partner_roi" in body, body.keys()
    roi = body["partner_roi"]
    for k in (
        "campaign_code", "total_registered_partners", "partners_redeemed",
        "partner_conversion_rate_pct", "projected_gmv_lift_cad", "window_days",
    ):
        assert k in roi, (k, roi)
    assert roi["campaign_code"] == "BIDVEX-PARTNERS"
    assert roi["window_days"] == 90


def test_iter249_partner_conversion_rate_math_consistent():
    base = _base()
    token = _admin_token(base)
    r = requests.get(
        f"{base}/api/admin/promotions/analytics/dashboard?window_days=30",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    body = r.json()
    roi = body["partner_roi"]
    if roi["total_registered_partners"] == 0:
        # Edge: no partners → math returns 0.0 by definition.
        assert roi["partner_conversion_rate_pct"] == 0.0
        return
    expected = round(
        100.0 * roi["partners_redeemed"] / roi["total_registered_partners"], 2,
    )
    assert abs(roi["partner_conversion_rate_pct"] - expected) <= 0.05, (
        roi, expected,
    )


def test_iter249_projected_gmv_lift_is_non_negative():
    base = _base()
    token = _admin_token(base)
    r = requests.get(
        f"{base}/api/admin/promotions/analytics/dashboard?window_days=30",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    body = r.json()
    assert body["partner_roi"]["projected_gmv_lift_cad"] >= 0.0


# ─── Mission 3: Bilingual transactional emails ───────────────────────

def test_iter249_detect_language_matrix():
    from services.email_notifications import _detect_language

    assert _detect_language({"province": "QC"}) == "fr"
    assert _detect_language({"province": "qc"}) == "fr"
    assert _detect_language({"buyer_province": "QC"}) == "fr"
    assert _detect_language("QC") == "fr"
    assert _detect_language({"province": "ON"}) == "en"
    assert _detect_language({"province": "AB"}) == "en"
    assert _detect_language({"province": "BC"}) == "en"
    assert _detect_language(None) == "en"
    assert _detect_language({}) == "en"
    # Explicit pref wins.
    assert _detect_language({"preferred_language": "fr-CA", "province": "ON"}) == "fr"
    assert _detect_language({"preferred_language": "en", "province": "QC"}) == "en"


@pytest.mark.asyncio
async def test_iter249_invoice_created_email_french_subject_for_qc():
    from services import email_notifications as en

    inv = {
        "invoice_number": "INV-249-FR",
        "vehicle_title": "Honda Civic 2025",
        "hammer_price": 12000.0, "total_amount": 13200.0,
        "buyer_email": "qc@example.com", "buyer_province": "QC",
        "due_at": "2026-04-01T00:00:00+00:00",
        "id": "inv-1",
    }
    captured = {}

    async def fake_unified(to_email, subject, html_content, **kw):
        captured["subject"] = subject
        captured["html"] = html_content
        return {"status": "sent"}

    with patch.object(en, "_send_via_unified", new=fake_unified):
        await en.send_invoice_created_email(inv)

    assert "Facture nº" in captured["subject"]
    assert "Honda Civic" in captured["subject"]
    # French body markers.
    assert "Félicitations" in captured["html"]
    assert "Total à payer" in captured["html"]


@pytest.mark.asyncio
async def test_iter249_invoice_created_email_english_subject_for_ontario():
    from services import email_notifications as en

    inv = {
        "invoice_number": "INV-249-EN",
        "vehicle_title": "Honda Civic 2025",
        "hammer_price": 12000.0, "total_amount": 13200.0,
        "buyer_email": "on@example.com", "buyer_province": "ON",
        "due_at": "2026-04-01T00:00:00+00:00",
        "id": "inv-2",
    }
    captured = {}

    async def fake_unified(to_email, subject, html_content, **kw):
        captured["subject"] = subject
        return {"status": "sent"}

    with patch.object(en, "_send_via_unified", new=fake_unified):
        await en.send_invoice_created_email(inv)

    assert captured["subject"].startswith("Invoice #INV-249-EN")
    assert "Facture" not in captured["subject"]


@pytest.mark.asyncio
async def test_iter249_payment_confirmation_french_subject_for_qc():
    from services import email_notifications as en

    inv = {
        "invoice_number": "INV-249-PMT",
        "vehicle_title": "F-150",
        "total_amount": 15000.0, "paid_amount": 15000.0,
        "buyer_email": "qc@example.com", "buyer_province": "QC",
        "paid_at": "2026-04-10T00:00:00+00:00",
        "id": "inv-3",
    }
    captured = {}

    async def fake_unified(to_email, subject, html_content, **kw):
        captured["subject"] = subject
        return {"status": "sent"}

    with patch.object(en, "_send_via_unified", new=fake_unified):
        await en.send_payment_confirmation_email(inv)

    assert "Paiement confirmé" in captured["subject"]
    assert "Facture nº" in captured["subject"]


@pytest.mark.asyncio
async def test_iter249_payment_confirmation_english_subject_for_alberta():
    from services import email_notifications as en

    inv = {
        "invoice_number": "INV-249-PMT-EN",
        "vehicle_title": "F-150",
        "total_amount": 15000.0, "paid_amount": 15000.0,
        "buyer_email": "ab@example.com", "buyer_province": "AB",
        "paid_at": "2026-04-10T00:00:00+00:00",
        "id": "inv-4",
    }
    captured = {}

    async def fake_unified(to_email, subject, html_content, **kw):
        captured["subject"] = subject
        return {"status": "sent"}

    with patch.object(en, "_send_via_unified", new=fake_unified):
        await en.send_payment_confirmation_email(inv)

    assert "Payment Confirmed" in captured["subject"]
    assert "Paiement" not in captured["subject"]


@pytest.mark.asyncio
async def test_iter249_auction_won_french_subject_for_qc():
    from services import email_notifications as en

    captured = {}

    async def fake_unified(to_email, subject, html_content, **kw):
        captured["subject"] = subject
        return {"status": "sent"}

    with patch.object(en, "_send_via_unified", new=fake_unified):
        await en.send_auction_won_email(
            to_email="qc@example.com",
            item_name="Toyota Camry",
            hammer_price=8500.0,
            buyer_province="QC",
            is_vehicle=False,
        )

    assert "Vous avez gagné" in captured["subject"]


@pytest.mark.asyncio
async def test_iter249_auction_won_english_subject_for_ontario():
    from services import email_notifications as en

    captured = {}

    async def fake_unified(to_email, subject, html_content, **kw):
        captured["subject"] = subject
        return {"status": "sent"}

    with patch.object(en, "_send_via_unified", new=fake_unified):
        await en.send_auction_won_email(
            to_email="on@example.com",
            item_name="Toyota Camry",
            hammer_price=8500.0,
            buyer_province="ON",
            is_vehicle=True,
        )

    assert "You Won!" in captured["subject"]
    assert "Vous" not in captured["subject"]


@pytest.mark.asyncio
async def test_iter249_dealer_license_approved_french_subject_for_qc():
    from services import email_notifications as en

    captured = {}

    async def fake_unified(to_email, subject, html_content, **kw):
        captured["subject"] = subject
        return {"status": "sent"}

    user_qc = {"email": "qc@example.com", "province": "QC"}
    license_doc = {"license_number": "QC-12345", "jurisdiction": "QC"}
    with patch.object(en, "_send_via_unified", new=fake_unified):
        await en.send_dealer_license_approved_email(user_qc, license_doc)

    # QC user receives FR-ONLY subject (no English prefix).
    assert "Permis de concessionnaire vérifié" in captured["subject"]
    assert "Dealer License Verified" not in captured["subject"]


# ─── Mission 4: XSS sanitization ─────────────────────────────────────

def test_iter249_html_sanitizer_strips_dangerous_vectors():
    from services.html_sanitizer import sanitize_user_html

    payloads = {
        "<script>alert(1)</script><p>hi</p>": "<script",
        '<a href="javascript:alert(1)">x</a>': "javascript:",
        '<img src="x" onerror="alert(1)">': "onerror",
        '<iframe src="http://evil.com"></iframe>': "<iframe",
        '<div onload="steal()">hi</div>': "onload",
        '<object data="evil.swf"></object>': "<object",
        '<embed src="evil.swf">': "<embed",
    }
    for raw, must_be_stripped in payloads.items():
        out = sanitize_user_html(raw)
        assert must_be_stripped not in out.lower(), (raw, out)

    # `javascript:` URI inside href is removed → tag may stay, attribute gone.
    out = sanitize_user_html('<a href="javascript:alert(1)">x</a>')
    assert "javascript:" not in out.lower()


def test_iter249_html_sanitizer_preserves_safe_markup():
    from services.html_sanitizer import sanitize_user_html

    safe_html = (
        '<p>Hello <strong>world</strong></p>'
        '<a href="https://bidvex.com" target="_blank" rel="noopener">visit</a>'
        '<img src="https://bidvex.com/logo.png" alt="logo">'
        '<table><tr><td>cell</td></tr></table>'
    )
    out = sanitize_user_html(safe_html)
    assert "<p>" in out and "<strong>" in out
    assert 'href="https://bidvex.com"' in out
    assert "<img" in out
    assert 'src="https://bidvex.com/logo.png"' in out
    assert "<table>" in out and "<td>" in out


def test_iter249_html_sanitizer_inline_strips_all_markup_and_trims():
    from services.html_sanitizer import sanitize_inline

    assert sanitize_inline(None) == ""
    assert sanitize_inline("") == ""
    assert sanitize_inline("  Plain text  ") == "Plain text"
    out = sanitize_inline("Hello <script>alert(1)</script> World")
    assert "<" not in out and ">" not in out
    assert "Hello" in out and "World" in out
    out2 = sanitize_inline("<b>BOLD</b>")
    # All tags stripped, text content preserved.
    assert "BOLD" in out2
    assert "<" not in out2
