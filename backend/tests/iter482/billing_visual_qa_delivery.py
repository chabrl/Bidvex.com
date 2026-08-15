"""iter482 — Billing Document Visual QA Delivery
=====================================================

PREVIEW ONLY.  STRIPE TEST DATA ONLY.  NO PRODUCTION MUTATIONS.

Delivers realistic TEST copies of EVERY billing-related document /
template through the app's canonical email + PDF generators to a
single audit recipient (charbel911@gmail.com) for personal visual
review.

Safeguards baked in:
  * Every subject line is prefixed with  [TEST/PREVIEW]
  * Every HTML body has a top TEST/PREVIEW banner inserted via
    ``send_email`` wrapper
  * Only ONE recipient is ever addressed (charbel911@gmail.com);
    dispatchers that would normally resolve multiple recipients
    are patched here so the visual QA CANNOT leak to real users
  * All Stripe amounts are synthetic (integer cents), no real
    charges are triggered, no BalanceTransaction retrieves are
    attempted
  * No database rows are mutated (variance dispatcher path uses
    a stub `db` object)

Run with:
    cd /app/backend && python -m tests.iter482.billing_visual_qa_delivery
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

# Ensure backend is on PYTHONPATH
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# Load backend .env BEFORE importing services (so SendGrid picks up its key).
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_BACKEND, ".env"), override=False)
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("iter482.qa_delivery")

RECIPIENT = "charbel911@gmail.com"
TAG = "[TEST/PREVIEW]"
TEST_BANNER_HTML = (
    '<div style="background:#fef3c7;border:2px dashed #d97706;padding:14px 18px;'
    'border-radius:8px;margin:0 0 18px 0;font-family:Arial,sans-serif;">'
    '<p style="margin:0;color:#78350f;font-weight:800;font-size:14px;letter-spacing:0.06em;">'
    '⚠️ TEST / PREVIEW — VISUAL QA COPY ONLY</p>'
    '<p style="margin:6px 0 0 0;color:#92400e;font-size:12px;line-height:1.45;">'
    'This document is a synthetic test copy generated from the BidVex billing '
    'templates for visual QA. No real charge was made, no customer was notified, '
    'and no financial records were mutated. Amounts, IDs and metadata are '
    'illustrative Stripe TEST data.'
    '</p></div>'
)

# --- SUBJECT + HTML DECORATION -------------------------------------------

def decorate_subject(subject: str, label: str = "") -> str:
    """Prefix TEST tag + optional descriptive label to the subject."""
    tag = f"{TAG}"
    if label:
        tag = f"{tag} {label} —"
    return f"{tag} {subject}"


def inject_test_banner(html: str) -> str:
    """Insert the TEST/PREVIEW banner right after the first <body> tag,
    or at the top if body tag is absent.  Idempotent.
    """
    if not html or "TEST / PREVIEW" in html:
        return html
    lower = html.lower()
    idx = lower.find("<body")
    if idx == -1:
        return TEST_BANNER_HTML + html
    end = lower.find(">", idx)
    if end == -1:
        return TEST_BANNER_HTML + html
    return html[: end + 1] + TEST_BANNER_HTML + html[end + 1 :]


# ─── Enforce single-recipient safety by wrapping the canonical dispatcher ─────
_DELIVERY_LOG: List[Dict[str, Any]] = []


def install_safety_wrapper():
    """Wrap `services.emails._email_core.send_email` so it can ONLY send
    to RECIPIENT, always injects the TEST/PREVIEW banner, and every
    subject is prefixed with `[TEST/PREVIEW]` if it isn't already.

    Also records every dispatch attempt in `_DELIVERY_LOG` for the
    final report.
    """
    from services.emails import _email_core as core

    real_send_email = core.send_email

    async def guarded_send_email(
        to_email: str,
        subject: str,
        html_content: str,
        attachments=None,
        from_email=None,
        from_name=None,
        reply_to=None,
        reply_to_name=None,
        is_marketing: bool = False,
        categories=None,
        custom_args=None,
    ):
        original_to = to_email
        to_email = RECIPIENT  # force override
        if TAG not in subject:
            subject = decorate_subject(subject)
        html_content = inject_test_banner(html_content or "")
        cats = list(categories or [])
        for c in ("iter482", "visual-qa", "TEST-PREVIEW"):
            if c not in cats:
                cats.append(c)
        args = dict(custom_args or {})
        args["qa_original_to"] = original_to
        args["qa_run_at"] = datetime.now(timezone.utc).isoformat()
        try:
            res = await real_send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                attachments=attachments,
                from_email=from_email,
                from_name=from_name,
                reply_to=reply_to,
                reply_to_name=reply_to_name,
                is_marketing=False,
                categories=cats,
                custom_args=args,
            )
        except Exception as e:  # pragma: no cover
            logger.error(f"[qa] send_email FAILED subject={subject!r} err={e}")
            res = {"status": "error", "message": str(e)}
        _DELIVERY_LOG.append({
            "subject": subject,
            "to": to_email,
            "original_to": original_to,
            "attachments": len(attachments or []),
            "result": (res or {}).get("status", "unknown"),
            "status_code": (res or {}).get("status_code"),
        })
        return res

    core.send_email = guarded_send_email
    # Also patch cross-module imports that already grabbed the reference.
    for mod_name in (
        "services.emails.email_system",
        "services.emails.email_marketplace",
        "services.emails.email_vehicles",
        "services.emails.email_engagement",
        "services.emails._email_core",
        "services.variance_notification_service",
    ):
        try:
            import importlib
            m = importlib.import_module(mod_name)
            if hasattr(m, "send_email"):
                setattr(m, "send_email", guarded_send_email)
        except Exception:
            pass


# ─── Fake DB stub for the variance dispatcher ────────────────────────────────

class _StubMongoCollection:
    def __init__(self, name):
        self.name = name

    async def find_one(self, *args, **kwargs):
        return None

    async def find_one_and_update(self, *args, **kwargs):
        # Always claim the send in the test
        return {"payment_intent_id": args[0].get("payment_intent_id") if args else None}

    async def update_one(self, *args, **kwargs):
        return SimpleNamespace(matched_count=1, modified_count=1)

    def find(self, *args, **kwargs):
        async def _empty():
            if False:  # pragma: no cover
                yield {}
        cursor = _empty()
        # emulate `.limit()`
        cursor.limit = lambda *_a, **_k: cursor  # type: ignore[attr-defined]
        return cursor


class _StubDB:
    def __getattr__(self, name):
        return _StubMongoCollection(name)


# ─── HTML → PDF helper for `invoice_templates.py` templates ─────────────────

def html_to_pdf_bytes(html: str, filename_hint: str = "invoice") -> Optional[bytes]:
    """Render HTML → PDF bytes. Uses WeasyPrint if available, else
    falls back to reportlab-plain text.
    Returns None if neither library is available.
    """
    try:
        from weasyprint import HTML  # type: ignore
        return HTML(string=html).write_pdf()
    except Exception as e:
        logger.warning(f"[qa] weasyprint unavailable ({e}); falling back to reportlab text PDF")
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from io import BytesIO
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        c.setFont("Helvetica", 10)
        c.drawString(50, 750, f"[TEST/PREVIEW] {filename_hint}")
        c.drawString(50, 735, "HTML template preview — see the accompanying email HTML for full layout.")
        c.showPage()
        c.save()
        return buf.getvalue()
    except Exception as e:  # pragma: no cover
        logger.error(f"[qa] PDF fallback failed: {e}")
        return None


# ─── Fixture builders — realistic Stripe TEST amounts ────────────────────────

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


BUYER_EN = {
    "id": "usr_test_buyer_en",
    "email": RECIPIENT,
    "name": "Alexandra Riley",
    "full_name": "Alexandra Riley",
    "preferred_language": "en",
    "province": "ON",
    "address": "42 Maple Way, Toronto, ON, M5V 3A8",
}
BUYER_FR = {
    "id": "usr_test_buyer_fr",
    "email": RECIPIENT,
    "name": "Sophie Tremblay",
    "full_name": "Sophie Tremblay",
    "preferred_language": "fr",
    "province": "QC",
    "address": "125 rue Notre-Dame, Montréal, QC, H2Y 1C6",
}
SELLER_EN = {
    "id": "usr_test_seller_en",
    "email": RECIPIENT,
    "name": "Prairie Auto Group",
    "business_name": "Prairie Auto Group Ltd.",
    "partner_company_name": "Prairie Auto Group Ltd.",
    "preferred_language": "en",
    "province": "AB",
    "address": "1200 6th Ave SW, Calgary, AB, T2P 3P4",
    "gst_number": "813622145RT0001",
    "qst_number": "",
}
SELLER_FR = {
    "id": "usr_test_seller_fr",
    "email": RECIPIENT,
    "name": "Encans Charbonneau",
    "business_name": "Encans Charbonneau Inc.",
    "partner_company_name": "Encans Charbonneau Inc.",
    "preferred_language": "fr",
    "province": "QC",
    "address": "88 rue Sherbrooke, Sherbrooke, QC, J1H 1V6",
    "gst_number": "706766367RT0001",
    "qst_number": "1233530880TQ0001",
}


def _invoice_common_en() -> Dict[str, Any]:
    return {
        "id": "inv_test_" + uuid.uuid4().hex[:12],
        "invoice_number": "BV-20260215-000042",
        "vehicle_title": "2019 Ford F-150 Lariat 4x4",
        "vehicle_vin": "1FTEW1EG3KFA12345",
        "auction_id": "auc_test_" + uuid.uuid4().hex[:12],
        "buyer_email": RECIPIENT,
        "buyer_name": BUYER_EN["name"],
        "buyer_province": "ON",
        "seller_email": RECIPIENT,
        "seller_name": SELLER_EN["name"],
        "hammer_price": 32500.00,
        "buyer_premium": 812.50,
        "subtotal_before_tax": 33312.50,
        "tax_type": "HST (13%)",
        "tax_total": 4330.63,
        "total_amount": 37643.13,
        "paid_amount": 37643.13,
        "penalty_amount": 0.00,
        "deposit_credited": 500.00,
        "subscription_discount": 0.00,
        "subscription_tier": "premium",
        "payment_status": "pending",
        "payment_method": "card",
        "created_at": _now_iso(),
        "due_at": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "payment_deadline": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "line_items": [
            {"description": "2019 Ford F-150 Lariat 4x4 — Hammer Price", "rate": 0, "amount": 32500.00},
            {"description": "Buyer Premium (2.5%)", "rate": 0.025, "amount": 812.50},
            {"description": "HST on subtotal (13%)", "rate": 0.13, "amount": 4330.63},
            {"description": "Deposit credit", "rate": 0, "amount": -500.00},
        ],
    }


def _invoice_common_fr() -> Dict[str, Any]:
    inv = _invoice_common_en()
    inv.update({
        "id": "inv_test_" + uuid.uuid4().hex[:12],
        "invoice_number": "BV-20260215-000043",
        "vehicle_title": "Camion Ford F-150 Lariat 4x4 2019",
        "buyer_email": RECIPIENT,
        "buyer_name": BUYER_FR["name"],
        "buyer_province": "QC",
        "preferred_language": "fr",
        "tax_type": "TPS+TVQ",
        "line_items": [
            {"description": "Camion Ford F-150 Lariat 4x4 2019 — Prix marteau", "rate": 0, "amount": 32500.00},
            {"description": "Prime acheteur (2,5 %)", "rate": 0.025, "amount": 812.50},
            {"description": "TPS (5%)", "rate": 0.05, "amount": 1665.63},
            {"description": "TVQ (9,975%)", "rate": 0.09975, "amount": 3323.71},
            {"description": "Crédit de dépôt", "rate": 0, "amount": -500.00},
        ],
        "tax_total": 1665.63 + 3323.71,
        "total_amount": 33312.50 + 1665.63 + 3323.71 - 500.00,
    })
    return inv


def _receipt_common(lang: str = "en", section: str = "marketplace") -> Dict[str, Any]:
    buyer = BUYER_FR if lang == "fr" else BUYER_EN
    seller = SELLER_FR if lang == "fr" else SELLER_EN
    return {
        "id": "rec_test_" + uuid.uuid4().hex[:12],
        "type": "buyer_receipt",
        "section": section,
        "listing_id": "lst_test_" + uuid.uuid4().hex[:12],
        "listing_title": (
            "Lot #42 — Palette d'outils électriques Milwaukee (12 pièces)"
            if lang == "fr" else
            "Lot #42 — Milwaukee Power Tool Pallet (12 pcs)"
        ),
        "seller_name": seller["name"],
        "order_number": "BVX-179B62B9",
        "hammer_price": 1875.00,
        "platform_fee": 46.88,
        "taxes": 250.83,
        "processing_fee": 62.14,
        "total_charged": 2234.85,
        "net_payout": 1828.13,
        "currency": "CAD",
        "payment_method_last4": "4242",
        "transaction_id": "pi_test_" + uuid.uuid4().hex[:20],
        "pickup_code": "BVX-9K4L2M8Q",
        "created_at": _now_iso(),
        # buyer preferences propagate via passed buyer dict
    }


def _statement_common(lang: str = "en") -> Dict[str, Any]:
    r = _receipt_common(lang=lang, section="lots")
    r["type"] = "seller_statement"
    r["buyer_first_name"] = "Alexandra" if lang == "en" else "Sophie"
    return r


# ─── Variance / shortfall doc fixture ────────────────────────────────────────

def _variance_doc(intl: bool = True) -> Dict[str, Any]:
    est_c = 200      # CA$2.00 estimated
    rec_c = 200      # CA$2.00 recovery (BidVex charged)
    act_c = 380 if intl else 200  # CA$3.80 actual vs $2.00 recovery → –$1.80 shortfall
    var_c = rec_c - act_c
    return {
        "payment_intent_id": "pi_TEST_intl_shortfall_" + uuid.uuid4().hex[:8],
        "charge_id": "ch_TEST_" + uuid.uuid4().hex[:12],
        "listing_id": "lst_test_" + uuid.uuid4().hex[:8],
        "invoice_id": "inv_test_" + uuid.uuid4().hex[:8],
        "currency": "CAD",
        "resolved_jurisdiction": "international" if intl else "domestic",
        "payer_role": "buyer",
        "estimated_cents": est_c,
        "recovery_cents":  rec_c,
        "actual_cents":    act_c,
        "variance_cents":  var_c,
        "reconciliation_status": "SHORTFALL",
        "transaction_type": "auction_purchase",
        "updated_at": _now_iso(),
    }


# ─── DISPATCH DRIVERS ────────────────────────────────────────────────────────

async def send_all():
    """Fire every billing document once for the visual QA."""
    from services.emails.email_system import (
        send_invoice_created_email,
        send_payment_confirmation_email,
        send_invoice_overdue_email,
        send_payment_reminder_email,
        send_payment_overdue_email,
        send_manual_subscription_active_email,
        send_subscription_reminder_email,
        send_subscription_expired_email,
        send_subscription_upgraded_email,
        send_promotion_confirmation_email,
        send_deposit_refunded_email,
        send_charge_confirmation_email,
        send_payout_confirmation_email,
        send_buyer_receipt_email,
        send_seller_statement_email,
        send_payment_link_email,
        send_payment_failed_email,
        send_buyer_final_invoice_link_email,
        send_seller_settlement_link_email,
    )
    from services.emails.email_marketplace import (
        send_auction_won_email,
        send_storage_seller_commission_invoice,
        send_storage_auction_won_email,
        send_auction_sold_email,
    )
    from services.emails.email_vehicles import (
        send_vehicle_deposit_captured_email,
    )
    from services.variance_notification_service import dispatch_variance_notification

    # ==================================================================
    # 1) Buyer auction purchase invoice — EN + FR
    # ==================================================================
    await send_invoice_created_email(_invoice_common_en())
    await send_invoice_created_email(_invoice_common_fr())

    # ==================================================================
    # 2) Buyer payment receipt (invoice paid) — EN + FR
    # ==================================================================
    en_paid = _invoice_common_en(); en_paid["payment_status"] = "paid"; en_paid["paid_at"] = _now_iso()
    fr_paid = _invoice_common_fr(); fr_paid["payment_status"] = "paid"; fr_paid["paid_at"] = _now_iso()
    await send_payment_confirmation_email(en_paid)
    await send_payment_confirmation_email(fr_paid)

    # ==================================================================
    # 3) Buyer receipt (final settlement) — EN + FR (marketplace + lots)
    # ==================================================================
    await send_buyer_receipt_email(BUYER_EN, _receipt_common("en", "marketplace"))
    await send_buyer_receipt_email(BUYER_FR, _receipt_common("fr", "marketplace"))
    await send_buyer_receipt_email(BUYER_EN, _receipt_common("en", "lots"))

    # ==================================================================
    # 4) Seller statement (settlement) — EN + FR
    # ==================================================================
    await send_seller_statement_email(SELLER_EN, _statement_common("en"))
    await send_seller_statement_email(SELLER_FR, _statement_common("fr"))

    # ==================================================================
    # 5) Buyer final invoice link (paid) — EN + FR
    # ==================================================================
    await send_buyer_final_invoice_link_email(
        buyer=BUYER_EN,
        invoice_link=f"https://www.bidvex.com/invoice/inv_{uuid.uuid4().hex[:10]}?sig=preview",
        invoice_number="BV-20260215-000042",
        listing_title="Lot #42 — Milwaukee Power Tool Pallet (12 pcs)",
        amount_paid_display="$2,234.85 CAD",
    )
    await send_buyer_final_invoice_link_email(
        buyer=BUYER_FR,
        invoice_link=f"https://www.bidvex.com/invoice/inv_{uuid.uuid4().hex[:10]}?sig=preview",
        invoice_number="BV-20260215-000043",
        listing_title="Lot #42 — Palette d'outils électriques Milwaukee (12 pièces)",
        amount_paid_display="2 234,85 $ CAD",
    )

    # ==================================================================
    # 6) Seller settlement link — EN + FR
    # ==================================================================
    await send_seller_settlement_link_email(
        seller=SELLER_EN,
        statement_link=f"https://www.bidvex.com/statement/stm_{uuid.uuid4().hex[:10]}?sig=preview",
        statement_number="STM-20260215-000042",
        listing_title="Lot #42 — Milwaukee Power Tool Pallet (12 pcs)",
        net_payout_display="$1,828.13 CAD",
    )
    await send_seller_settlement_link_email(
        seller=SELLER_FR,
        statement_link=f"https://www.bidvex.com/statement/stm_{uuid.uuid4().hex[:10]}?sig=preview",
        statement_number="STM-20260215-000043",
        listing_title="Lot #42 — Palette d'outils électriques Milwaukee (12 pièces)",
        net_payout_display="1 828,13 $ CAD",
    )

    # ==================================================================
    # 7) Invoice overdue / payment reminder / payment overdue  [iter482 P2-FIX]
    # ==================================================================
    # EN version
    ov_en = _invoice_common_en(); ov_en["penalty_amount"] = 100.00; ov_en["payment_status"] = "overdue"
    await send_invoice_overdue_email(ov_en, days_overdue=5)
    # FR version (invoice carries preferred_language="fr" + buyer_province="QC")
    ov_fr = _invoice_common_fr(); ov_fr["penalty_amount"] = 100.00; ov_fr["payment_status"] = "overdue"
    ov_fr["preferred_language"] = "fr"; ov_fr["buyer_province"] = "QC"
    await send_invoice_overdue_email(ov_fr, days_overdue=5)

    # Payment reminder — EN + FR
    await send_payment_reminder_email(
        winner_email=RECIPIENT, winner_name="Alexandra Riley",
        item_title="2019 Ford F-150 Lariat 4x4",
        final_price=32500.00, listing_id="lst_test_reminder",
        days_remaining=4, payment_deadline=ov_en["due_at"],
    )
    await send_payment_reminder_email(
        winner_email=RECIPIENT, winner_name="Sophie Tremblay",
        item_title="Camion Ford F-150 Lariat 4x4 2019",
        final_price=32500.00, listing_id="lst_test_reminder_fr",
        days_remaining=4, payment_deadline=ov_fr["due_at"],
        lang="fr",
    )

    # Payment overdue — EN + FR
    await send_payment_overdue_email(
        winner_email=RECIPIENT, winner_name="Alexandra Riley",
        item_title="2019 Ford F-150 Lariat 4x4",
        final_price=32500.00, listing_id="lst_test_overdue",
        penalty_amount=650.00, total_with_penalty=33150.00,
    )
    await send_payment_overdue_email(
        winner_email=RECIPIENT, winner_name="Sophie Tremblay",
        item_title="Camion Ford F-150 Lariat 4x4 2019",
        final_price=32500.00, listing_id="lst_test_overdue_fr",
        penalty_amount=650.00, total_with_penalty=33150.00,
        lang="fr",
    )

    # ==================================================================
    # 8) Payment link (no card on file) + payment failed
    # ==================================================================
    await send_payment_link_email(
        buyer=BUYER_EN, listing_title="Lot #42 — Milwaukee Power Tool Pallet",
        listing_id="lst_test_paylink", total_due=2234.85,
        payment_link_url="https://buy.stripe.com/test_visualqa_link",
        deadline_iso=(datetime.now(timezone.utc) + timedelta(hours=72)).isoformat(),
    )
    await send_payment_link_email(
        buyer=BUYER_FR, listing_title="Lot #42 — Palette d'outils Milwaukee",
        listing_id="lst_test_paylink", total_due=2234.85,
        payment_link_url="https://buy.stripe.com/test_visualqa_link",
        deadline_iso=(datetime.now(timezone.utc) + timedelta(hours=72)).isoformat(),
    )
    await send_payment_failed_email(BUYER_EN, "2019 Ford F-150 Lariat 4x4", "lst_test_failed", 940.63)
    await send_payment_failed_email(BUYER_FR, "Camion Ford F-150 Lariat 4x4 2019", "lst_test_failed", 940.63)

    # ==================================================================
    # 9) Auction won emails — Marketplace (EN + FR)
    # ==================================================================
    await send_auction_won_email(
        to_email=RECIPIENT, to_name="Alexandra Riley",
        auction_id="lst_test_marketplace_win",
        item_name="Lot #42 — Milwaukee Power Tool Pallet (12 pcs)",
        hammer_price=1875.00, platform_fee=46.88,
        is_vehicle=False, is_cross_border=False, buyer_province="ON",
        payment_deadline=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
    )
    await send_auction_won_email(
        to_email=RECIPIENT, to_name="Sophie Tremblay",
        auction_id="lst_test_marketplace_win_fr",
        item_name="Lot #42 — Palette d'outils électriques Milwaukee (12 pièces)",
        hammer_price=1875.00, platform_fee=46.88,
        is_vehicle=False, is_cross_border=False, buyer_province="QC",
        payment_deadline=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
    )
    # Vehicle Won (with vehicle notice + cross-border)
    await send_auction_won_email(
        to_email=RECIPIENT, to_name="Alexandra Riley",
        auction_id="lst_test_vehicle_win",
        item_name="2019 Ford F-150 Lariat 4x4",
        hammer_price=32500.00, platform_fee=812.50,
        seller_name="Prairie Auto Group Ltd.", seller_contact="1-403-555-0199",
        is_vehicle=True, is_cross_border=True, buyer_province="ON",
        payment_deadline=(datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
    )

    # ==================================================================
    # 10) Storage seller commission invoice + Storage auction won
    # ==================================================================
    storage_facility = {
        "email": RECIPIENT,
        "company_name": "SecureLock Storage Sherbrooke",
        "contact_name": "Marc Lévesque",
        "phone": "1-819-555-0142",
        "city": "Sherbrooke", "province": "QC", "units_available": 24,
    }
    storage_auction = {
        "id": "sa_test_" + uuid.uuid4().hex[:12],
        "unit_number": "17B",
        "winning_bid": 425.00, "current_bid": 425.00,
        "payment_method": "cash",
        "cleanup_deadline": (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d"),
        "payment_deadline": (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d"),
        "cleanup_deposit": 100.00,
        "pickup_code": "BVX-STR-4X8N2",
    }
    storage_pricing = {
        "seller_invoice": {
            "commission":       21.25,
            "stripe_recovery":  1.02,
            "tax_label":        "GST+QST (14.975%)",
            "tax":              3.34,
            "total":            25.61,
        },
        "buyer_invoice": {
            "platform_fee": 0.0, "stripe_recovery": 0.0, "tax": 0.0,
        },
    }
    await send_storage_seller_commission_invoice(storage_facility, storage_auction, storage_pricing)
    await send_storage_auction_won_email(BUYER_EN, storage_auction, storage_facility, storage_pricing)

    # ==================================================================
    # 11) Deposit refunded + Vehicle deposit captured
    # ==================================================================
    class _MiniDB:
        """Only implements find_one for `users` + `listings` (used by these
        two helpers).  Read-only, no writes."""
        def __init__(self, kind: str):
            self.kind = kind
        def __getattr__(self, name):
            return self  # any collection returns self
        async def find_one(self, q, proj=None):
            if self.kind == "user":
                return {"email": RECIPIENT, "name": "Alexandra Riley"}
            if self.kind == "listing":
                return {"title": "Lot #42 — Milwaukee Power Tool Pallet"}
            return None
    await send_deposit_refunded_email(_MiniDB("user"), user_id="usr_test",
                                      auction_id="lst_test_refund",
                                      amount=200.00, currency="CAD")
    await send_vehicle_deposit_captured_email(
        BUYER_EN,
        invoice={"invoice_number": "BV-20260215-000042",
                 "vehicle_title": "2019 Ford F-150 Lariat 4x4",
                 "total_amount": 812.50, "platform_fee": 812.50},
        deposit={"amount": 500.00},
        captured_amount=500.00,
    )

    # ==================================================================
    # 12) Charge confirmation (buyer_commission / buy_now / seller_commission)
    # ==================================================================
    class _ChargeDB:
        def __getattr__(self, name):
            return self
        async def find_one(self, q, proj=None):
            return {"email": RECIPIENT, "name": "Alexandra Riley",
                    "title": "Lot #42 — Milwaukee Power Tool Pallet"}
    cdb = _ChargeDB()
    await send_charge_confirmation_email(cdb, user_id="usr_test",
                                         auction_id="lst_test_bc",
                                         amount=46.88, currency="CAD",
                                         charge_type="buyer_commission")
    await send_charge_confirmation_email(cdb, user_id="usr_test",
                                         auction_id="lst_test_bn",
                                         amount=299.00, currency="CAD",
                                         charge_type="buy_now_payment")
    await send_charge_confirmation_email(cdb, user_id="usr_test",
                                         auction_id="lst_test_sc",
                                         amount=118.75, currency="CAD",
                                         charge_type="seller_commission")
    await send_payout_confirmation_email(cdb, seller_id="usr_test_seller",
                                         auction_id="lst_test_payout",
                                         amount=1828.13, currency="CAD")

    # ==================================================================
    # 13) Subscription documents  [iter482 P2-FIX — now EN + FR]
    # ==================================================================
    # EN — regular subscription active + reminder + expired + upgraded
    await send_manual_subscription_active_email(
        user={"email": RECIPIENT, "name": "Prairie Auto Group Ltd."},
        account_kind="vehicle_dealer",
        amount_cad=399.00, method="e_transfer",
        renewal_until=(datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
        reference="ETR-2026-042",
    )
    # Reminder — EN
    await send_subscription_reminder_email(
        user_email=RECIPIENT, user_name="Prairie Auto Group Ltd.",
        plan="premium", days_remaining=3,
        end_date=(datetime.now(timezone.utc) + timedelta(days=3)).strftime("%B %d, %Y"),
    )
    # Reminder — FR
    await send_subscription_reminder_email(
        user_email=RECIPIENT, user_name="Encans Charbonneau Inc.",
        plan="premium", days_remaining=3,
        end_date="18 février 2026",
        lang="fr",
    )
    # Expired — EN
    await send_subscription_expired_email(
        user_email=RECIPIENT, user_name="Prairie Auto Group Ltd.",
        previous_plan="vip",
    )
    # Expired — FR
    await send_subscription_expired_email(
        user_email=RECIPIENT, user_name="Encans Charbonneau Inc.",
        previous_plan="vip", lang="fr",
    )
    # Upgraded — EN
    await send_subscription_upgraded_email(
        user_email=RECIPIENT, user_name="Prairie Auto Group Ltd.",
        new_plan="vip",
        end_date=(datetime.now(timezone.utc) + timedelta(days=365)).strftime("%B %d, %Y"),
    )
    # Upgraded — FR
    await send_subscription_upgraded_email(
        user_email=RECIPIENT, user_name="Encans Charbonneau Inc.",
        new_plan="vip",
        end_date="15 février 2027",
        lang="fr",
    )

    # ==================================================================
    # 14) Promotion confirmation (Stripe receipt for boost)
    # ==================================================================
    await send_promotion_confirmation_email(
        seller_email=RECIPIENT, seller_name="Prairie Auto Group Ltd.",
        listing_title="2019 Ford F-150 Lariat 4x4",
        listing_id="lst_test_promo",
        listing_type="vehicle", tier="premium", boost_days=7,
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        base_price=79.99, gst=4.00, qst=7.98, stripe_fee=2.89,
        grand_total=94.86,
        features=["Featured banner", "Homepage carousel", "Priority search"],
    )

    # ==================================================================
    # 15) Vehicle-sold seller notice (for reference)
    # ==================================================================
    await send_auction_sold_email(
        seller_email=RECIPIENT, seller_name="Prairie Auto Group Ltd.",
        vehicle_title="2019 Ford F-150 Lariat 4x4",
        final_price=32500.00, commission=812.50, net_payout=31687.50,
    )

    # ==================================================================
    # 16) Variance / shortfall notification (admin) — INTL + DOMESTIC
    # ==================================================================
    # Override recipient resolver so this delivers to charbel911 only.
    import services.variance_notification_service as vns
    original_resolve = vns._resolve_recipients
    async def _one_recipient(_db):
        return [RECIPIENT]
    vns._resolve_recipients = _one_recipient  # type: ignore[assignment]
    try:
        await dispatch_variance_notification(_StubDB(), _variance_doc(intl=True))
        # domestic reconciled (no shortfall) — build a synthetic COVERED doc
        # but keep status SHORTFALL to force the email fire, then annotate
        # so the reader can compare intl vs domestic wording.
        dom_doc = _variance_doc(intl=False)
        dom_doc["reconciliation_status"] = "SHORTFALL"  # forces send
        dom_doc["variance_cents"] = 0
        await dispatch_variance_notification(_StubDB(), dom_doc)
    finally:
        vns._resolve_recipients = original_resolve  # type: ignore[assignment]

    # ==================================================================
    # 17) PDF templates — attach real generated PDFs from the app
    #     (buyer vehicle invoice + settlement statement)
    # ==================================================================
    await deliver_pdf_variants()


# ─── PDF DELIVERIES ─────────────────────────────────────────────────────────

async def deliver_pdf_variants():
    """Generate the actual production PDFs the app renders and attach them
    to a small email so the visual QA can view/download."""
    from services.emails._email_core import send_email
    from services.invoice_service import generate_invoice_pdf as gen_bilingual_pdf
    from services.invoice_generator import (
        generate_vehicle_invoice_pdf,
        generate_general_invoice_pdf,
    )
    from services.tax_engine import (
        calculate_vehicle_payment, calculate_general_payment,
        SellerInfo,
    )
    try:
        from invoice_templates import (
            lots_won_template,
            seller_statement_template,
            seller_receipt_template,
            commission_invoice_template,
            payment_letter_template,
        )
        HAS_LEGACY_TPL = True
    except Exception as _e:
        HAS_LEGACY_TPL = False
        logger.warning(f"[qa] legacy invoice_templates unavailable: {_e}")

    # --- (A) Bilingual auction PDF (EN + FR) via services.invoice_service ---
    inv_data_en = {
        "id": "inv_test_" + uuid.uuid4().hex[:12],
        "invoice_number": "BV-20260215-000042",
        "currency": "CAD",
        "created_at": _now_iso(),
        "transaction_id": "pi_test_" + uuid.uuid4().hex[:20],
        "subtotal": 32500.00,
        "buyer_premium": 812.50,
        "items": [
            {"title": "2019 Ford F-150 Lariat 4x4", "description": "VIN 1FTEW1EG3KFA12345 · Hammer",
             "quantity": 1, "unit_price": 32500.00, "amount": 32500.00},
        ],
        "vehicle": {"vin": "1FTEW1EG3KFA12345", "make": "Ford", "model": "F-150 Lariat 4x4", "year": 2019},
    }
    inv_data_fr = dict(inv_data_en)
    inv_data_fr["invoice_number"] = "BV-20260215-000043"
    pdf_en = gen_bilingual_pdf(inv_data_en, BUYER_EN, SELLER_EN, lang="en", buyer_province="ON")
    pdf_fr = gen_bilingual_pdf(inv_data_fr, BUYER_FR, SELLER_FR, lang="fr", buyer_province="QC")

    await send_email(
        to_email=RECIPIENT,
        subject=decorate_subject("BidVex Bilingual Auction Invoice PDF (services/invoice_service.py)",
                                 label="Buyer Invoice PDF"),
        html_content=(
            "<p>Attached: two auction-invoice PDFs (EN — Ontario HST, FR — Québec GST/TPS + QST/TVQ) "
            "rendered directly by <code>services/invoice_service.generate_invoice_pdf()</code> — "
            "the module used by the standard invoice download flow.</p>"
        ),
        attachments=[
            {"content": base64.b64encode(pdf_en).decode("ascii"),
             "filename": "TEST_PREVIEW_bilingual_invoice_EN_ON.pdf", "type": "application/pdf"},
            {"content": base64.b64encode(pdf_fr).decode("ascii"),
             "filename": "TEST_PREVIEW_bilingual_invoice_FR_QC.pdf", "type": "application/pdf"},
        ],
    )

    # --- (B) Vehicle-specific PDF (bank draft flow) via services.invoice_generator ---
    veh_result = calculate_vehicle_payment(
        hammer_price=32500.00,
        buyer_tier="premium",
    )
    veh_pdf = generate_vehicle_invoice_pdf(
        payment_result=veh_result,
        buyer_info=BUYER_EN, seller_info=SELLER_EN,
        auction_info={"title": "2019 Ford F-150 Lariat 4x4",
                      "vin": "1FTEW1EG3KFA12345", "lot_number": "V-1042"},
        invoice_number="BV-VEH-20260215-000001",
    )
    await send_email(
        to_email=RECIPIENT,
        subject=decorate_subject("BidVex Vehicle Platform-Fee Invoice PDF", label="Vehicle Fee PDF"),
        html_content=(
            "<p>Attached: vehicle platform-fee invoice PDF rendered by "
            "<code>services/invoice_generator.generate_vehicle_invoice_pdf()</code>.  "
            "Shows the split between BidVex 2.5% platform fee (charged now) and "
            "hammer-price bank-draft balance (paid directly to seller).</p>"
        ),
        attachments=[{"content": base64.b64encode(veh_pdf).decode("ascii"),
                      "filename": "TEST_PREVIEW_vehicle_platform_fee_invoice.pdf",
                      "type": "application/pdf"}],
    )

    # --- (C) General auction PDF (business seller — GST/QST on premium) ---
    seller_business = SellerInfo(
        seller_id="usr_test_seller_biz",
        seller_name="Encans Charbonneau Inc.",
        is_business=True,
        business_name="Encans Charbonneau Inc.",
        address="88 rue Sherbrooke, Sherbrooke, QC",
        gst_number="706766367RT0001",
        qst_number="1233530880TQ0001",
    )
    gen_result = calculate_general_payment(
        hammer_price=1875.00,
        buyer_tier="basic",
        seller_tier="basic",
        seller_is_business=True,
        seller_info=seller_business,
    )
    gen_pdf = generate_general_invoice_pdf(
        payment_result=gen_result,
        buyer_info=BUYER_FR, seller_info={"name": SELLER_FR["name"], "email": RECIPIENT,
                                          "business_name": "Encans Charbonneau Inc.",
                                          "gst_number": "706766367RT0001",
                                          "qst_number": "1233530880TQ0001"},
        auction_info={"title": "Lot #42 — Palette d'outils électriques Milwaukee"},
        invoice_number="BV-GEN-20260215-000001",
    )
    await send_email(
        to_email=RECIPIENT,
        subject=decorate_subject("BidVex General Auction Invoice PDF (business seller, Québec)",
                                 label="General Invoice PDF"),
        html_content=(
            "<p>Attached: general auction invoice PDF with a BUSINESS seller (GST/QST applied on hammer). "
            "Rendered by <code>services/invoice_generator.generate_general_invoice_pdf()</code>.</p>"
        ),
        attachments=[{"content": base64.b64encode(gen_pdf).decode("ascii"),
                      "filename": "TEST_PREVIEW_general_invoice_business_seller_QC.pdf",
                      "type": "application/pdf"}],
    )

    # --- (D) invoice_templates.py HTML templates → attached as PDFs ---
    #   • lots_won_template (buyer lots-won summary)
    #   • seller_statement_template
    #   • seller_receipt_template
    #   • commission_invoice_template
    #   • payment_letter_template
    if not HAS_LEGACY_TPL:
        logger.info("[qa] skipping legacy invoice_templates.py delivery — module unavailable")
        return

    now_dt = datetime.now(timezone.utc)
    now_str = now_dt.strftime("%Y-%m-%d")
    buyer_ctx = {
        "name": BUYER_EN["name"], "company_name": "Riley Contracting Ltd.",
        "billing_address": BUYER_EN["address"], "address": BUYER_EN["address"],
        "phone": "1-416-555-0142", "email": RECIPIENT,
    }
    seller_ctx = {
        "name": SELLER_EN["name"], "company_name": SELLER_EN["business_name"],
        "address": SELLER_EN["address"], "email": RECIPIENT,
        "phone": "1-403-555-0199",
    }
    auction_ctx = {
        "title": "Renaissance Multi-Item Estate Sale — Feb 15, 2026",
        "city": "Sherbrooke", "region": "QC",
        "location": "103-761 Chalifoux Street, Sherbrooke, QC",
        "auction_end_date": now_dt,
    }
    lots_ctx = [
        {"lot_number": "42", "title": "Milwaukee M18 12-piece Kit",
         "description": "Cordless drill, impact driver, batteries, charger, hard case — brand new",
         "unit_price": 1875.00, "hammer_price": 1875.00, "quantity": 1, "status": "sold"},
        {"lot_number": "43", "title": "DeWalt 20V MAX Combo",
         "description": "Circular saw, reciprocating saw, work light, 2x 5.0Ah batteries",
         "unit_price": 549.00, "hammer_price": 1098.00, "quantity": 2, "status": "sold"},
    ]

    lots_data = {
        "invoice_number": "BV-LOTS-20260215-000042",
        "paddle_number": "P-4242",
        "buyer": buyer_ctx,
        "auction": auction_ctx,
        "lots": lots_ctx,
        "premium_percentage": 15.0,
        "tax_rate_gst": 5.0,
        "tax_rate_qst": 0.0,
        "payment_deadline": (now_dt + timedelta(days=14)).strftime("%B %d, %Y"),
    }
    seller_data = {
        "invoice_number": "STM-20260215-000042",
        "seller": seller_ctx,
        "auction": auction_ctx,
        "lots": lots_ctx,
        "total_hammer": 2973.00,
        "lots_sold": 2, "total_lots": 2,
        "commission_rate": 5.0,
        "tax_rate_gst": 5.0,
        "tax_rate_qst": 9.975,
    }
    rec_data = {
        "receipt_number": "REC-20260215-000042",
        "seller": seller_ctx,
        "auction": auction_ctx,
        "lots": lots_ctx,
        "total_hammer": 2973.00,
        "lots_sold": 2, "total_lots": 2,
        "commission_amount": 148.65,
        "commission_rate": 5.0,
        "net_payout": 2824.35,
        "tax_rate_gst": 5.0,
        "tax_rate_qst": 9.975,
    }
    com_data = {
        "invoice_number": "COM-20260215-000042",
        "seller": seller_ctx,
        "auction": auction_ctx,
        "lots": lots_ctx,
        "total_hammer": 2973.00,
        "net_payout": 2824.35,
        "lots_sold": 2, "total_lots": 2,
        "commission_amount": 148.65,
        "commission_rate": 5.0,
        "tax_rate_gst": 5.0,
        "tax_rate_qst": 9.975,
    }
    pay_data = {
        "invoice_number": "LTR-20260215-000042",
        "paddle_number": "P-4242",
        "buyer": buyer_ctx,
        "auction": auction_ctx,
        "lots": lots_ctx,
        "lots_count": 2,
        "hammer_total": 2973.00,
        "premium_amount": 445.95,
        "total_tax": 512.09,
        "grand_total": 3931.04,
        "premium_percentage": 15.0,
        "payment_deadline": (now_dt + timedelta(days=14)).strftime("%B %d, %Y"),
    }

    def _try(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.warning(f"[qa] template {fn.__name__} failed: {e}")
            return None

    # iter482 P2-followup — pass buyer.province="ON" so `payment_letter_template`
    # + `lots_won_template` both correctly zero-out QST and render matching
    # grand totals ($3,589.90).  Prior fixtures let a stale QC total leak
    # into the Payment Letter for an Ontario buyer.
    buyer_ctx["province"] = "ON"
    lots_data["buyer"] = buyer_ctx
    pay_data["buyer"] = buyer_ctx
    # Payment Letter now derives everything from `lots` + `premium_percentage`
    # + buyer.province.  The three passthrough fields remain only for the
    # legacy passthrough branch (kept for backwards compat).
    pay_data["hammer_total"] = 2973.00
    pay_data["premium_amount"] = 445.95
    pay_data["total_tax"] = 170.95
    pay_data["grand_total"] = 3589.90

    # iter482 P2-followup — the Commission Invoice + Statement + Receipt now
    # share `compute_seller_payout` so they cannot disagree.  Remove the
    # stale/wrong net_payout hardcodes from the fixtures so the QA batch
    # exercises the internal derivation path.
    for _d in (rec_data, com_data):
        _d.pop("net_payout", None)

    lots_html_en = _try(lots_won_template, lots_data, "en")
    lots_html_fr = _try(lots_won_template, lots_data, "fr")
    seller_html_en = _try(seller_statement_template, seller_data)
    rec_html_en = _try(seller_receipt_template, rec_data)
    com_html_en = _try(commission_invoice_template, com_data)
    pay_html_en = _try(payment_letter_template, pay_data)

    pdf_lots_en = html_to_pdf_bytes(lots_html_en, "buyer_lots_won_EN") if lots_html_en else None
    pdf_lots_fr = html_to_pdf_bytes(lots_html_fr, "buyer_lots_won_FR") if lots_html_fr else None
    pdf_seller = html_to_pdf_bytes(seller_html_en, "seller_statement_EN") if seller_html_en else None
    pdf_rec = html_to_pdf_bytes(rec_html_en, "seller_receipt_EN") if rec_html_en else None
    pdf_com = html_to_pdf_bytes(com_html_en, "commission_invoice_EN") if com_html_en else None
    pdf_pay = html_to_pdf_bytes(pay_html_en, "payment_letter_EN") if pay_html_en else None

    attachments = []
    for label, blob in (
        ("lots_won_EN.pdf", pdf_lots_en),
        ("lots_won_FR.pdf", pdf_lots_fr),
        ("seller_statement.pdf", pdf_seller),
        ("seller_receipt.pdf", pdf_rec),
        ("commission_invoice.pdf", pdf_com),
        ("payment_letter.pdf", pdf_pay),
    ):
        if blob:
            attachments.append({
                "content": base64.b64encode(blob).decode("ascii"),
                "filename": f"TEST_PREVIEW_{label}",
                "type": "application/pdf",
            })

    combined_html = (
        "<p>Attached: PDFs rendered from every HTML template in "
        "<code>backend/invoice_templates.py</code>:</p>"
        "<ol>"
        "<li><code>lots_won_template</code> (EN + FR) — Buyer lots-won summary</li>"
        "<li><code>seller_statement_template</code> — Seller commission statement</li>"
        "<li><code>seller_receipt_template</code> — Seller payment receipt</li>"
        "<li><code>commission_invoice_template</code> — Storage / Partner commission invoice</li>"
        "<li><code>payment_letter_template</code> — Payment demand letter</li>"
        "</ol>"
        "<p style='margin-top:14px;'>PDF rendering: uses <code>weasyprint</code> if installed, else a "
        "reportlab placeholder page (open the corresponding HTML template file in the repo "
        "to review the full HTML markup).</p>"
    )
    preview_html = (lots_html_en or "")[:800] if lots_html_en else ""
    if preview_html:
        combined_html += f"<hr/><pre style='font-family:monospace;font-size:11px;'>{preview_html}...</pre>"
    await send_email(
        to_email=RECIPIENT,
        subject=decorate_subject("invoice_templates.py — all 5 templates rendered",
                                 label="Legacy HTML Invoice Templates"),
        html_content=combined_html,
        attachments=attachments,
    )


# ─── ENTRYPOINT ──────────────────────────────────────────────────────────────

async def main():
    logger.info("[qa] installing safety wrapper — all sends will target %s only", RECIPIENT)
    install_safety_wrapper()
    logger.info("[qa] beginning dispatch")
    await send_all()
    logger.info("[qa] dispatch complete — %d messages recorded", len(_DELIVERY_LOG))
    # Print a compact report
    print("\n================= DELIVERY LOG =================")
    for i, row in enumerate(_DELIVERY_LOG, 1):
        print(f"{i:>2}. {row['result']:<10} {row['subject'][:110]}"
              f"{'  (+ '+str(row['attachments'])+' attachment)' if row['attachments'] else ''}")
    print(f"================= TOTAL: {len(_DELIVERY_LOG)} =================\n")


if __name__ == "__main__":
    asyncio.run(main())
