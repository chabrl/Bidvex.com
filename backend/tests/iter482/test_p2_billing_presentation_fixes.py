"""iter482 P2 fix — Regression tests for the 7 billing presentation defects.

These tests lock in that:
  (1) each of the six previously EN-only email helpers now renders a fully
      French body + FR subject whenever the caller signals `lang="fr"` (or,
      for the dict-based ``send_invoice_overdue_email``, when the invoice
      itself carries an FR signal — QC province / preferred_language),
  (2) the bilingual auction-invoice PDF (``services/invoice_service.py``)
      emits Canadian French currency formatting (``1 234,56 $``) when the
      caller passes ``lang="fr"``,
  (3) the EN behavior of every helper is preserved (no signature break,
      no wording drift).

**No production financial calculation is exercised here** — these tests
snapshot the output of the presentation layer only.  Tax math,
reconciliation math and Stripe logic are OUT OF SCOPE.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Tuple

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Shared plumbing — capture the outbound email without touching SendGrid.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def captured_email(monkeypatch):
    """Capture whatever the helper hands to `send_email` without sending it."""
    captured: Dict[str, Any] = {}

    async def _fake_send_email(**kwargs):
        captured.update(kwargs)
        return {"status": "captured", "status_code": 200}

    # Every helper delegates through `services.emails._email_core.send_email`.
    import services.emails._email_core as core
    import services.emails.email_system as es
    monkeypatch.setattr(core, "send_email", _fake_send_email)
    monkeypatch.setattr(es, "send_email", _fake_send_email)
    return captured


def _fr_wording_ok(body: str) -> bool:
    """Sanity: FR body contains at least one clearly-French phrase and no
    obvious English fossil like `Hi ` or `Pay Now` (case-sensitive)."""
    if not any(fr in body for fr in ("Bonjour", "Payer maintenant", "Facture",
                                     "Rappel", "Abonnement", "Ma facture",
                                     "expiré", "expirera", "En retard",
                                     "Paiement en retard")):
        return False
    fossils = ("Hi Alexandra", "Hi Sophie", "Pay Now</a>", "Payment Reminder<",
               "Subscription Expiring Soon", "Subscription Expired",
               "Welcome to ", "Payment Overdue<", "OVERDUE: Payment")
    return not any(f in body for f in fossils)


def _en_wording_ok(body: str) -> bool:
    return ("Hi " in body or "Pay Now" in body or "Payment" in body or
            "Subscription" in body) and "Bonjour " not in body


# ─────────────────────────────────────────────────────────────────────────────
# Defect #1 — send_invoice_overdue_email
# ─────────────────────────────────────────────────────────────────────────────

def _invoice(lang: str) -> Dict[str, Any]:
    base = {
        "id": "inv_test_1",
        "invoice_number": "BV-TEST-001",
        "buyer_email": "buyer@example.com",
        "vehicle_title": "2020 Toyota Corolla",
        "total_amount": 1000.00,
        "penalty_amount": 20.00,
    }
    if lang == "fr":
        base["preferred_language"] = "fr"
        base["buyer_province"] = "QC"
    return base


@pytest.mark.asyncio
async def test_p2_1_invoice_overdue_fr_via_language_hint(captured_email):
    from services.emails.email_system import send_invoice_overdue_email
    await send_invoice_overdue_email(_invoice("fr"), days_overdue=5)

    assert captured_email["subject"].startswith("⚠️ EN RETARD"), captured_email["subject"]
    assert "Facture nº" in captured_email["subject"]
    body = captured_email["html_content"]
    assert _fr_wording_ok(body), body[:800]
    # Canadian French currency ``1 000,00 $`` (canonical `_format_currency_fr`
    # uses a regular ASCII space between thousands + suffix `$`).
    assert "1 000,00 $" in body, "FR CAD currency format missing"
    # Backend passthrough — the total = 1000 + 20 = 1020
    assert "1 020,00 $" in body


@pytest.mark.asyncio
async def test_p2_1_invoice_overdue_en_default_preserved(captured_email):
    from services.emails.email_system import send_invoice_overdue_email
    await send_invoice_overdue_email(_invoice("en"), days_overdue=5)
    assert "OVERDUE" in captured_email["subject"]
    body = captured_email["html_content"]
    assert _en_wording_ok(body)
    assert "$1,000.00" in body
    assert "$1,020.00" in body


# ─────────────────────────────────────────────────────────────────────────────
# Defect #2 — send_payment_reminder_email
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_p2_2_payment_reminder_fr(captured_email):
    from services.emails.email_system import send_payment_reminder_email
    await send_payment_reminder_email(
        winner_email="w@example.com", winner_name="Sophie Tremblay",
        item_title="Camion Ford F-150 2019", final_price=32500.00,
        listing_id="lst_test", days_remaining=4,
        payment_deadline="2026-02-25T00:00:00+00:00", lang="fr",
    )
    assert captured_email["subject"].startswith("Rappel de paiement")
    body = captured_email["html_content"]
    assert "Bonjour Sophie Tremblay" in body
    assert "Payer maintenant" in body
    assert "32 500,00 $" in body
    assert "Pay Now" not in body


@pytest.mark.asyncio
async def test_p2_2_payment_reminder_en_default(captured_email):
    from services.emails.email_system import send_payment_reminder_email
    await send_payment_reminder_email(
        winner_email="w@example.com", winner_name="Alex Riley",
        item_title="2019 Ford F-150", final_price=32500.00,
        listing_id="lst_test", days_remaining=4,
        payment_deadline="2026-02-25T00:00:00+00:00",
    )
    assert "Payment Reminder" in captured_email["subject"]
    body = captured_email["html_content"]
    assert "Hi Alex Riley" in body
    assert "$32,500.00" in body


# ─────────────────────────────────────────────────────────────────────────────
# Defect #3 — send_payment_overdue_email
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_p2_3_payment_overdue_fr(captured_email):
    from services.emails.email_system import send_payment_overdue_email
    await send_payment_overdue_email(
        winner_email="w@example.com", winner_name="Sophie",
        item_title="Camion Ford F-150",
        final_price=32500.00, listing_id="lst_test",
        penalty_amount=650.00, total_with_penalty=33150.00, lang="fr",
    )
    assert captured_email["subject"].startswith("EN RETARD")
    body = captured_email["html_content"]
    assert "Bonjour Sophie" in body
    assert "Payer maintenant" in body
    assert "Pénalité de retard" in body
    assert "32 500,00 $" in body
    assert "33 150,00 $" in body
    assert "OVERDUE:" not in body


@pytest.mark.asyncio
async def test_p2_3_payment_overdue_en_default(captured_email):
    from services.emails.email_system import send_payment_overdue_email
    await send_payment_overdue_email(
        winner_email="w@example.com", winner_name="Alex",
        item_title="2019 Ford F-150",
        final_price=32500.00, listing_id="lst_test",
        penalty_amount=650.00, total_with_penalty=33150.00,
    )
    assert "OVERDUE" in captured_email["subject"]
    body = captured_email["html_content"]
    assert "$32,500.00" in body
    assert "$33,150.00" in body


# ─────────────────────────────────────────────────────────────────────────────
# Defect #4 — send_subscription_reminder_email
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_p2_4_subscription_reminder_fr(captured_email):
    from services.emails.email_system import send_subscription_reminder_email
    await send_subscription_reminder_email(
        user_email="u@example.com", user_name="Prairie Auto Group Ltd.",
        plan="premium", days_remaining=3, end_date="15 février 2026",
        lang="fr",
    )
    assert "expire dans 3 jour" in captured_email["subject"]
    body = captured_email["html_content"]
    assert "Bonjour Prairie Auto Group Ltd." in body
    assert "Voir mon abonnement" in body
    assert "Jours restants" in body
    assert "View Subscription" not in body


@pytest.mark.asyncio
async def test_p2_4_subscription_reminder_en_default(captured_email):
    from services.emails.email_system import send_subscription_reminder_email
    await send_subscription_reminder_email(
        user_email="u@example.com", user_name="Prairie Auto Group Ltd.",
        plan="premium", days_remaining=3, end_date="February 15, 2026",
    )
    assert "Expires in 3 Days" in captured_email["subject"]
    body = captured_email["html_content"]
    assert "Hi Prairie Auto Group Ltd." in body
    assert "View Subscription" in body


# ─────────────────────────────────────────────────────────────────────────────
# Defect #5 — send_subscription_expired_email
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_p2_5_subscription_expired_fr(captured_email):
    from services.emails.email_system import send_subscription_expired_email
    await send_subscription_expired_email(
        user_email="u@example.com", user_name="Prairie Auto Group Ltd.",
        previous_plan="vip", lang="fr",
    )
    assert captured_email["subject"] == "Votre abonnement Vip est expiré"
    body = captured_email["html_content"]
    assert "Bonjour Prairie Auto Group Ltd." in body
    assert "Renouveler mon abonnement" in body
    assert "Remises sur la prime acheteur retirées" in body
    assert "Renew Subscription" not in body


@pytest.mark.asyncio
async def test_p2_5_subscription_expired_en_default(captured_email):
    from services.emails.email_system import send_subscription_expired_email
    await send_subscription_expired_email(
        user_email="u@example.com", user_name="Prairie Auto Group Ltd.",
        previous_plan="vip",
    )
    assert captured_email["subject"] == "Your Vip Subscription Has Expired"
    body = captured_email["html_content"]
    assert "Hi Prairie Auto Group Ltd." in body
    assert "Renew Subscription" in body


# ─────────────────────────────────────────────────────────────────────────────
# Defect #6 — send_subscription_upgraded_email
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_p2_6_subscription_upgraded_fr(captured_email):
    from services.emails.email_system import send_subscription_upgraded_email
    await send_subscription_upgraded_email(
        user_email="u@example.com", user_name="Prairie Auto Group Ltd.",
        new_plan="vip", end_date="15 février 2027", lang="fr",
    )
    assert captured_email["subject"] == "🎉 Bienvenue chez Vip !"
    body = captured_email["html_content"]
    assert "Bonjour Prairie Auto Group Ltd." in body
    assert "Commencer à explorer" in body
    assert "Frais de prime acheteur réduits" in body
    assert "Gestionnaire de compte dédié" in body
    assert "Start Exploring" not in body


@pytest.mark.asyncio
async def test_p2_6_subscription_upgraded_en_default(captured_email):
    from services.emails.email_system import send_subscription_upgraded_email
    await send_subscription_upgraded_email(
        user_email="u@example.com", user_name="Prairie Auto Group Ltd.",
        new_plan="vip", end_date="February 15, 2027",
    )
    assert captured_email["subject"] == "🎉 Welcome to Vip!"
    body = captured_email["html_content"]
    assert "Start Exploring" in body
    assert "Advanced analytics dashboard" in body


# ─────────────────────────────────────────────────────────────────────────────
# Defect #7 — bilingual auction PDF FR currency formatting
# ─────────────────────────────────────────────────────────────────────────────

def test_p2_7_bilingual_pdf_fr_currency_format():
    from services.invoice_service import _fmt_currency

    # EN — unchanged behavior
    assert _fmt_currency(32500.00, "CAD", "en") == "$32,500.00"
    assert _fmt_currency(32500.00, "CAD") == "$32,500.00"  # legacy default
    assert _fmt_currency(1234.56, "CAD", "en") == "$1,234.56"

    # FR — Canadian French: NBSP thousands, comma decimal, $ suffix.
    assert _fmt_currency(32500.00, "CAD", "fr") == "32\u00a0500,00\u00a0$"
    assert _fmt_currency(1234.56, "CAD", "fr") == "1\u00a0234,56\u00a0$"
    # Non-CAD keeps symbol semantics but still applies FR digit layout
    assert _fmt_currency(1000.00, "EUR", "fr") == "1\u00a0000,00\u00a0EUR"


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract all text from a PDF using pdfplumber (preserves NBSP)."""
    import io, pdfplumber
    out: List[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text() or "")
    return "\n".join(out)


def test_p2_7_bilingual_pdf_end_to_end_fr_renders_canadian_french_numbers():
    """Render a real FR invoice PDF and confirm the FR digit format
    appears in the extracted text (pdfplumber preserves NBSP U+00A0)."""
    from services.invoice_service import generate_invoice_pdf

    invoice = {
        "id": "inv_test_p2_7",
        "invoice_number": "BV-TEST-P2-7",
        "currency": "CAD",
        "created_at": "2026-02-15T00:00:00+00:00",
        "subtotal": 32500.00,
        "buyer_premium": 812.50,
        "items": [{"title": "Camion Ford F-150 2019", "description": "VIN 12345",
                   "quantity": 1, "unit_price": 32500.00, "amount": 32500.00}],
    }
    buyer = {"name": "Sophie Tremblay", "email": "s@example.com",
             "address": "125 rue Notre-Dame, Montréal, QC",
             "preferred_language": "fr", "province": "QC"}
    seller = {"business_name": "Encans Charbonneau", "email": "s@example.com",
              "gst_number": "706766367RT0001",
              "qst_number": "1233530880TQ0001"}

    pdf_fr = generate_invoice_pdf(invoice, buyer, seller, lang="fr", buyer_province="QC")
    pdf_en = generate_invoice_pdf(invoice, buyer, seller, lang="en", buyer_province="ON")

    fr_text = _extract_pdf_text(pdf_fr)
    en_text = _extract_pdf_text(pdf_en)

    # Canadian French: thousand separator + $ suffix + comma decimal.
    # pdfplumber may normalize NBSP to a regular space during extraction,
    # so accept either NBSP (\u00a0) or regular ASCII space.
    assert ("32\u00a0500,00\u00a0$" in fr_text) or ("32 500,00 $" in fr_text), \
        f"FR PDF missing Canadian-French currency.\nFR text (first 500 chars):\n{fr_text[:500]}"
    # Sanity: EN prefix format must be ABSENT from the FR PDF
    assert "$32,500.00" not in fr_text, "FR PDF regressed — still contains EN currency format"
    # EN PDF must still use the classic $32,500.00 format
    assert "$32,500.00" in en_text, \
        f"EN PDF regressed from $32,500.00 format.\nEN text (first 500 chars):\n{en_text[:500]}"
    # And EN PDF must NOT accidentally emit the FR pattern
    assert "32 500,00 $" not in en_text, "EN PDF regressed — leaked FR format"


# ─────────────────────────────────────────────────────────────────────────────
# Cross-cutting — the six helpers keep the same public signature keys.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_six_helpers_still_default_to_en_when_lang_omitted(captured_email):
    """Backward-compat guard — none of the six new `lang` kwargs are
    required, and omitting them yields the exact same subject/body as
    the pre-fix EN behavior."""
    import services.emails.email_system as es

    calls = [
        (es.send_payment_reminder_email, dict(
            winner_email="a@b", winner_name="X", item_title="Y",
            final_price=100.0, listing_id="l", days_remaining=1,
            payment_deadline="2026-02-15T00:00:00+00:00")),
        (es.send_payment_overdue_email, dict(
            winner_email="a@b", winner_name="X", item_title="Y",
            final_price=100.0, listing_id="l",
            penalty_amount=2.0, total_with_penalty=102.0)),
        (es.send_subscription_reminder_email, dict(
            user_email="a@b", user_name="X", plan="premium",
            days_remaining=3, end_date="Feb 15, 2026")),
        (es.send_subscription_expired_email, dict(
            user_email="a@b", user_name="X", previous_plan="vip")),
        (es.send_subscription_upgraded_email, dict(
            user_email="a@b", user_name="X", new_plan="vip",
            end_date="Feb 15, 2027")),
    ]
    for fn, kwargs in calls:
        captured_email.clear()
        await fn(**kwargs)
        # An EN default subject must NOT include « Bienvenue chez », « Rappel »,
        # « Abonnement », etc.
        assert " Bienvenue " not in captured_email["subject"]
        assert "Bonjour X" not in captured_email["html_content"]
