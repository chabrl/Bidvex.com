"""
iter211 — Pickup Coordination Service

After a non-vehicle, non-storage auction is paid for, both the winner and the
seller need each other's contact info to coordinate pickup or shipping. This
service is invoked from the payment_intent.succeeded webhook handler.

Emails are bilingual EN/FR auto-routed by `preferred_language`, and an
in-app `pickup_notifications` row is written for each party so they can see
the contact info inside their dashboard too.

Idempotent: a `pickup_notifications` row tagged `payment_intent_id` is the
unique key — re-firing on a duplicate webhook is a no-op.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

PICKUP_NOTIFICATION_COLLECTION = "pickup_notifications"


def _fmt_addr(user: dict) -> str:
    parts = [
        user.get("street_address"),
        user.get("city"),
        user.get("province") or user.get("state"),
        user.get("postal_code") or user.get("zip"),
    ]
    line = ", ".join([p for p in parts if p])
    return line or ""


def _send_bilingual_pickup_email(
    to_email: str,
    to_name: str,
    counterparty_name: str,
    counterparty_email: str,
    counterparty_phone: str,
    counterparty_address: str,
    listing_title: str,
    listing_id: str,
    role: str,  # "winner" or "seller"
    language: str = "en",
) -> bool:
    """Send the bilingual pickup-coordination email via SendGrid."""
    try:
        from services.email_notifications import send_email  # type: ignore
    except Exception:
        try:
            from services.email_service import send_email  # type: ignore
        except Exception as e:
            logger.warning(f"[pickup_email] No SendGrid sender available: {e}")
            return False

    frontend_url = os.environ.get("FRONTEND_URL", "https://bidvex.com")
    listing_url = f"{frontend_url}/listings/{listing_id}"

    is_fr = (language or "en").startswith("fr")

    if role == "winner":
        title_en = "Coordinate pickup with the seller"
        title_fr = "Coordonner la collecte avec le vendeur"
        intro_en = (
            f"Congrats on winning <strong>{listing_title}</strong>! "
            "Now that payment has cleared, please reach out to the seller below "
            "to arrange pickup or shipping."
        )
        intro_fr = (
            f"Félicitations pour votre adjudication de <strong>{listing_title}</strong> ! "
            "Maintenant que le paiement est confirmé, veuillez contacter le vendeur "
            "ci-dessous pour organiser la collecte ou l'expédition."
        )
        counterparty_role_en = "Seller"
        counterparty_role_fr = "Vendeur"
    else:
        title_en = "Coordinate pickup with the winner"
        title_fr = "Coordonner la collecte avec l'acheteur"
        intro_en = (
            f"Your listing <strong>{listing_title}</strong> has been paid for. "
            "The winner's contact info is below — please reach out within 48 hours "
            "to arrange pickup or shipping."
        )
        intro_fr = (
            f"Votre annonce <strong>{listing_title}</strong> a été payée. "
            "Voici les coordonnées de l'acheteur — veuillez le contacter dans "
            "les 48 heures pour organiser la collecte ou l'expédition."
        )
        counterparty_role_en = "Winner"
        counterparty_role_fr = "Acheteur"

    addr_line_en = (
        f"<p style='margin:4px 0;'><strong>Address:</strong> {counterparty_address}</p>"
        if counterparty_address else ""
    )
    addr_line_fr = (
        f"<p style='margin:4px 0;'><strong>Adresse :</strong> {counterparty_address}</p>"
        if counterparty_address else ""
    )

    voir_label = "Voir l'annonce" if is_fr else "View listing"
    bidvex_disclaimer = (
        "BidVex ne facilite pas les paiements en personne. Soyez prudent."
        if is_fr else
        "BidVex does not facilitate in-person payments \u2014 please use caution."
    )
    title = title_fr if is_fr else title_en
    phone_block_fr = (
        f"<p style='margin:4px 0;'><strong>Téléphone :</strong> {counterparty_phone}</p>"
        if counterparty_phone else ""
    )
    phone_block_en = (
        f"<p style='margin:4px 0;'><strong>Phone:</strong> {counterparty_phone}</p>"
        if counterparty_phone else ""
    )
    email_label = "Courriel" if is_fr else "Email"
    role_label = counterparty_role_fr if is_fr else counterparty_role_en
    intro = intro_fr if is_fr else intro_en
    addr_line = addr_line_fr if is_fr else addr_line_en
    phone_line = phone_block_fr if is_fr else phone_block_en

    html = f"""
<html><body style="font-family:Inter,Arial,sans-serif;max-width:600px;margin:0 auto;color:#1e293b;">
  <h2 style="color:#0f172a;">{title}</h2>
  <p style="line-height:1.6;">{intro}</p>
  <div style="background:#f1f5f9;border-radius:12px;padding:16px;margin:16px 0;">
    <p style="margin:0 0 8px 0;font-weight:600;color:#0f172a;">
      {role_label}: {counterparty_name}
    </p>
    <p style="margin:4px 0;"><strong>{email_label}:</strong>
      <a href="mailto:{counterparty_email}">{counterparty_email}</a></p>
    {phone_line}
    {addr_line}
  </div>
  <p style="line-height:1.6;">
    <a href="{listing_url}" style="background:#0f172a;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none;display:inline-block;">
      {voir_label}
    </a>
  </p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;" />
  <p style="font-size:12px;color:#64748b;">
    BidVex \u00b7 support@bidvex.com<br/>
    {bidvex_disclaimer}
  </p>
</body></html>
"""
    try:
        send_email(to_email=to_email, subject=title, html_content=html)
        return True
    except Exception as e:
        logger.warning(f"[pickup_email] Failed sending to {to_email}: {e}")
        return False


async def send_pickup_coordination_emails(
    db,
    listing_id: str,
    buyer_id: str,
    seller_id: str,
    payment_intent_id: str,
    listing_title: Optional[str] = None,
) -> dict:
    """Dispatch the bilingual pickup-coordination emails AND write an in-app
    notification row for each party. Idempotent on payment_intent_id."""
    # Idempotency guard
    if payment_intent_id:
        exists = await db[PICKUP_NOTIFICATION_COLLECTION].find_one(
            {"payment_intent_id": payment_intent_id}, {"_id": 0, "id": 1}
        )
        if exists:
            logger.info(f"[pickup_email] Already dispatched for PI {payment_intent_id}")
            return {"status": "duplicate", "payment_intent_id": payment_intent_id}

    buyer = await db.users.find_one({"id": buyer_id}, {"_id": 0}) or {}
    seller = await db.users.find_one({"id": seller_id}, {"_id": 0}) or {}

    if not buyer.get("email") or not seller.get("email"):
        logger.warning(
            f"[pickup_email] Missing email for buyer={buyer_id} or seller={seller_id}; skipping"
        )
        return {"status": "skipped", "reason": "missing_email"}

    # Resolve listing title if not provided
    if not listing_title:
        listing = await db.listings.find_one({"id": listing_id}, {"_id": 0, "title": 1}) or {}
        listing_title = listing.get("title") or "Auction Item"

    buyer_name = buyer.get("full_name") or buyer.get("name") or buyer.get("email")
    seller_name = seller.get("full_name") or seller.get("business_name") or seller.get("name") or seller.get("email")
    buyer_addr = _fmt_addr(buyer)
    seller_addr = _fmt_addr(seller)

    # 1. Email buyer → contact info for seller
    buyer_sent = _send_bilingual_pickup_email(
        to_email=buyer["email"],
        to_name=buyer_name,
        counterparty_name=seller_name,
        counterparty_email=seller.get("email", ""),
        counterparty_phone=seller.get("phone") or "",
        counterparty_address=seller_addr,
        listing_title=listing_title,
        listing_id=listing_id,
        role="winner",
        language=buyer.get("preferred_language", "en"),
    )

    # 2. Email seller → contact info for buyer
    seller_sent = _send_bilingual_pickup_email(
        to_email=seller["email"],
        to_name=seller_name,
        counterparty_name=buyer_name,
        counterparty_email=buyer.get("email", ""),
        counterparty_phone=buyer.get("phone") or "",
        counterparty_address=buyer_addr,
        listing_title=listing_title,
        listing_id=listing_id,
        role="seller",
        language=seller.get("preferred_language", "en"),
    )

    now = datetime.now(timezone.utc).isoformat()

    # In-app notification rows
    notifications = [
        {
            "id": str(uuid.uuid4()),
            "user_id": buyer_id,
            "kind": "pickup_coordination_winner",
            "payment_intent_id": payment_intent_id,
            "listing_id": listing_id,
            "listing_title": listing_title,
            "counterparty_id": seller_id,
            "counterparty_name": seller_name,
            "counterparty_email": seller.get("email", ""),
            "counterparty_phone": seller.get("phone") or "",
            "counterparty_address": seller_addr,
            "title_en": "Coordinate pickup with the seller",
            "title_fr": "Coordonner la collecte avec le vendeur",
            "email_sent": buyer_sent,
            "read": False,
            "created_at": now,
        },
        {
            "id": str(uuid.uuid4()),
            "user_id": seller_id,
            "kind": "pickup_coordination_seller",
            "payment_intent_id": payment_intent_id,
            "listing_id": listing_id,
            "listing_title": listing_title,
            "counterparty_id": buyer_id,
            "counterparty_name": buyer_name,
            "counterparty_email": buyer.get("email", ""),
            "counterparty_phone": buyer.get("phone") or "",
            "counterparty_address": buyer_addr,
            "title_en": "Coordinate pickup with the winner",
            "title_fr": "Coordonner la collecte avec l'acheteur",
            "email_sent": seller_sent,
            "read": False,
            "created_at": now,
        },
    ]
    try:
        await db[PICKUP_NOTIFICATION_COLLECTION].insert_many(notifications)
    except Exception as e:
        logger.error(f"[pickup_email] Failed to persist notifications: {e}")

    logger.info(
        f"[pickup_email] Dispatched for PI {payment_intent_id}: buyer={buyer_sent} seller={seller_sent}"
    )
    return {
        "status": "ok",
        "payment_intent_id": payment_intent_id,
        "buyer_email_sent": buyer_sent,
        "seller_email_sent": seller_sent,
        "notifications_created": 2,
    }
