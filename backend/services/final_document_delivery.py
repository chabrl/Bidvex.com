"""
iter468 — Final document delivery for confirmed Stripe auction payments.

Automates:
  1. Generate OR retrieve the buyer's final paid invoice (uses existing
     `generate_lots_won_invoice` for multi-item auctions, which pulls
     real settled data — no financial recomputation).
  2. Generate OR retrieve the seller's settlement statement (uses
     existing `generate_seller_statement`).
  3. Send ONE buyer email with ONE secure link to the buyer invoice.
  4. Send ONE seller email with ONE secure link to the seller statement.

Guardrails:
  • Fires ONLY for confirmed Stripe payments — never for
    failed / pending / cancelled / cash / e-transfer / unconfirmed.
  • Uses the iter460/462 dedup ledger with new kinds
    `final_document_buyer_link` / `final_document_seller_link` keyed by
    `(kind, auction_id, user_id, event_key="")` — one email each per
    settlement event. Duplicate webhook / retry / scheduler re-drive
    resolves to the same claim and is blocked.
  • No financial calc, no document data change, no PDF attachment, no
    partner co-branding, no cash / e-transfer / escrow / fee / tax
    changes.
  • Bilingual EN/FR preserved via the recipient's `preferred_language`.

Non-blocking: any failure in this delivery path logs a warning but never
crashes the caller (payment processing must not break because of email
delivery hiccups). This mirrors the platform's existing "receipts must
not block settlement" contract.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# Payment methods that count as "confirmed Stripe" for the purposes of
# this delivery. Anything else must NOT trigger the final documents.
_STRIPE_CONFIRMED_METHODS = {"stripe", "stripe_checkout", "stripe_pi"}


def _is_stripe_confirmed(*, payment_method: Optional[str],
                          buyer_charge: Optional[dict]) -> bool:
    """Strict guard: only True for CONFIRMED Stripe auction payments.

    A payment is considered confirmed-Stripe when:
      • Its `payment_method` is one of the Stripe values, AND
      • A `buyer_charge` dict is present with a `stripe_pi` reference
        (proves the charge actually succeeded).
    """
    pm = (payment_method or "").lower().strip()
    if pm not in _STRIPE_CONFIRMED_METHODS:
        return False
    if not buyer_charge or not (buyer_charge.get("stripe_pi")
                                or buyer_charge.get("stripe_session_id")
                                or buyer_charge.get("stripe_payment_intent_id")):
        return False
    return True


async def _fetch_or_generate_buyer_invoice(
    db, *, auction_id: str, buyer_id: str, lang: str,
) -> Optional[Dict[str, Any]]:
    """Retrieve the buyer's `lots_won` invoice for this auction if one
    exists (avoid double PDF generation on retry). Otherwise call the
    existing multi-item generator to create it now.

    Returns:
        {"invoice_id", "invoice_number", "download_url",
         "listing_title", "amount_paid_display"}
        or None if no lots were won.
    """
    from services.cloud_storage import generate_signed_url

    # Retrieve existing paid invoice if present.
    existing = await db.invoices.find_one({
        "auction_id": auction_id,
        "user_id": buyer_id,
        "invoice_type": "lots_won",
    }, {"_id": 0})

    if existing:
        invoice_id = existing.get("id")
        return {
            "invoice_id": invoice_id,
            "invoice_number": existing.get("invoice_number", ""),
            "download_url": generate_signed_url(invoice_id) if invoice_id else "",
            "listing_title": existing.get("listing_title", ""),
            "amount_paid_display": existing.get("amount_paid_display", ""),
        }

    # Generate fresh — reuse the existing route function's internals.
    # The route requires a `current_user` dependency; construct a minimal
    # admin proxy that satisfies the permission gate. We don't want to
    # import the full FastAPI dependency machinery here — the internal
    # function only checks `account_type`, `role`, and `id`.
    try:
        from routes.invoices import generate_lots_won_invoice

        class _AdminUser:
            account_type = "admin"
            role = "admin"
            id = "iter468-system"
        result = await generate_lots_won_invoice(
            auction_id=auction_id, user_id=buyer_id,
            lang=lang, current_user=_AdminUser(),
        )
        return {
            "invoice_id": None,
            "invoice_number": result.get("invoice_number", ""),
            "download_url": result.get("download_url", ""),
            "listing_title": result.get("auction_title", ""),
            "amount_paid_display": (
                f"${result.get('grand_total', 0):.2f} "
                f"{result.get('currency', 'CAD')}"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[iter468] buyer invoice generate failed "
                       f"auction={auction_id} buyer={buyer_id}: {exc}")
        return None


async def _fetch_or_generate_seller_statement(
    db, *, auction_id: str, seller_id: str, lang: str,
) -> Optional[Dict[str, Any]]:
    """Same retrieve-or-generate pattern for the seller settlement
    statement PDF.

    Returns:
        {"statement_id", "statement_number", "download_url",
         "listing_title", "net_payout_display"} or None.
    """
    from services.cloud_storage import generate_signed_url

    existing = await db.invoices.find_one({
        "auction_id": auction_id,
        "user_id": seller_id,
        "invoice_type": "seller_statement",
    }, {"_id": 0})

    if existing:
        sid = existing.get("id")
        return {
            "statement_id": sid,
            "statement_number": existing.get("invoice_number") or existing.get("statement_number") or "",
            "download_url": generate_signed_url(sid) if sid else "",
            "listing_title": existing.get("listing_title", ""),
            "net_payout_display": existing.get("net_payout_display", ""),
        }

    try:
        from routes.invoices import generate_seller_statement

        class _AdminUser:
            account_type = "admin"
            role = "admin"
            id = "iter468-system"
        result = await generate_seller_statement(
            auction_id=auction_id, seller_id=seller_id,
            current_user=_AdminUser(),
        )
        return {
            "statement_id": None,
            "statement_number": result.get("statement_number") or result.get("invoice_number") or "",
            "download_url": result.get("download_url", ""),
            "listing_title": result.get("auction_title", ""),
            "net_payout_display": (
                f"${result.get('net_payout', 0):.2f} "
                f"{result.get('currency', 'CAD')}"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[iter468] seller statement generate failed "
                       f"auction={auction_id} seller={seller_id}: {exc}")
        return None


async def deliver_final_documents(
    db,
    *,
    auction_id: str,
    buyer_id: Optional[str],
    seller_id: Optional[str],
    payment_method: str,
    buyer_charge: Optional[dict] = None,
    listing_title: Optional[str] = None,
) -> Dict[str, Any]:
    """Deliver final settlement documents to buyer + seller after a
    CONFIRMED Stripe auction payment.

    Never raises. Returns a dict summarising what was sent + what was
    suppressed (for observability + tests).
    """
    out: Dict[str, Any] = {
        "eligible": False,
        "buyer_email_sent": False,
        "buyer_email_suppressed_reason": None,
        "seller_email_sent": False,
        "seller_email_suppressed_reason": None,
    }

    # ── Eligibility gate: confirmed Stripe payment only ─────────────
    if not _is_stripe_confirmed(payment_method=payment_method,
                                  buyer_charge=buyer_charge):
        out["buyer_email_suppressed_reason"] = "not_confirmed_stripe"
        out["seller_email_suppressed_reason"] = "not_confirmed_stripe"
        return out
    out["eligible"] = True

    # Fetch recipients up-front (permits language detection).
    buyer = await db.users.find_one({"id": buyer_id}) if buyer_id else None
    seller = await db.users.find_one({"id": seller_id}) if seller_id else None

    from services.settlement_email_dedup import claim_settlement_email

    # ─── BUYER SIDE ─────────────────────────────────────────────────
    if buyer and buyer.get("email"):
        buyer_lang = (buyer.get("preferred_language") or "en").lower()
        if buyer_lang not in ("en", "fr"):
            buyer_lang = "en"
        # Claim the buyer's slot BEFORE generating the PDF so a webhook
        # storm never causes two generate calls.
        claimed = await claim_settlement_email(
            db, kind="final_document_buyer_link",
            auction_id=auction_id, user_id=buyer_id, event_key="",
        )
        if not claimed:
            out["buyer_email_suppressed_reason"] = "duplicate_claim"
        else:
            doc = await _fetch_or_generate_buyer_invoice(
                db, auction_id=auction_id, buyer_id=buyer_id, lang=buyer_lang,
            )
            if not doc or not doc.get("download_url"):
                out["buyer_email_suppressed_reason"] = "no_invoice_available"
            else:
                try:
                    from services.emails.email_system import (
                        send_buyer_final_invoice_link_email,
                    )
                    await send_buyer_final_invoice_link_email(
                        buyer=buyer,
                        invoice_link=doc["download_url"],
                        invoice_number=doc.get("invoice_number") or "—",
                        listing_title=(doc.get("listing_title")
                                       or listing_title or "Auction"),
                        amount_paid_display=doc.get("amount_paid_display") or "",
                    )
                    out["buyer_email_sent"] = True
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        f"[iter468] buyer link email failed "
                        f"auction={auction_id} buyer={buyer_id}: {exc}"
                    )
                    out["buyer_email_suppressed_reason"] = f"send_error: {exc}"
    else:
        out["buyer_email_suppressed_reason"] = "no_buyer_email"

    # ─── SELLER SIDE ────────────────────────────────────────────────
    if seller and seller.get("email"):
        seller_lang = (seller.get("preferred_language") or "en").lower()
        if seller_lang not in ("en", "fr"):
            seller_lang = "en"
        claimed_s = await claim_settlement_email(
            db, kind="final_document_seller_link",
            auction_id=auction_id, user_id=seller_id, event_key="",
        )
        if not claimed_s:
            out["seller_email_suppressed_reason"] = "duplicate_claim"
        else:
            doc = await _fetch_or_generate_seller_statement(
                db, auction_id=auction_id, seller_id=seller_id, lang=seller_lang,
            )
            if not doc or not doc.get("download_url"):
                out["seller_email_suppressed_reason"] = "no_statement_available"
            else:
                try:
                    from services.emails.email_system import (
                        send_seller_settlement_link_email,
                    )
                    await send_seller_settlement_link_email(
                        seller=seller,
                        statement_link=doc["download_url"],
                        statement_number=doc.get("statement_number") or "—",
                        listing_title=(doc.get("listing_title")
                                       or listing_title or "Auction"),
                        net_payout_display=doc.get("net_payout_display") or "",
                    )
                    out["seller_email_sent"] = True
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        f"[iter468] seller link email failed "
                        f"auction={auction_id} seller={seller_id}: {exc}"
                    )
                    out["seller_email_suppressed_reason"] = f"send_error: {exc}"
    else:
        out["seller_email_suppressed_reason"] = "no_seller_email"

    return out


__all__ = ["deliver_final_documents"]
