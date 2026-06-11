"""
services/seller_payouts.py — iter302 DIRECTIVE 2

Automatic seller payout after a buyer payment is collected via Stripe.

Flow (called from payment_collection.finalize_auction_payment success path):
  1. Net payout = hammer_price − platform_fee (2.5 %).
  2. Seller HAS Stripe Connect (stripe_connect_account_id + payouts enabled):
       → stripe.Transfer.create to the connected account immediately.
       → record db.seller_payouts {status: "sent"}, stamp listing
         payout_status="payout_sent", email + bell notification.
  3. Seller has NO Connect account (or transfer fails):
       → flag payout_pending (existing pending_payouts queue), notify admin,
         stamp listing payout_status="payout_pending". Seller sees the
         "funds within 14 business days" banner in their dashboard.

Never raises — payouts must not block settlement.
"""
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def process_seller_payout(
    db,
    *,
    section: str,
    listing_id: str,
    listing_title: str,
    seller_id: Optional[str],
    net_amount: float,
    lot_number: Optional[Any] = None,
    source_transaction_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Attempt instant Connect transfer; fall back to the pending queue."""
    out: Dict[str, Any] = {"status": "skipped"}
    if not seller_id or net_amount <= 0:
        return out

    # Idempotency — one payout per (listing, lot)
    existing = await db.seller_payouts.find_one(
        {"listing_id": listing_id, "lot_number": lot_number}, {"_id": 0, "id": 1, "status": 1}
    )
    if existing:
        return {"status": existing.get("status", "duplicate"), "payout_id": existing.get("id")}

    seller = await db.users.find_one(
        {"id": seller_id},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "preferred_language": 1,
         "stripe_connect_account_id": 1, "stripe_connect_onboarding_complete": 1,
         "stripe_connect_payouts_enabled": 1},
    )
    acct = (seller or {}).get("stripe_connect_account_id")
    connect_ready = bool(
        acct and (
            seller.get("stripe_connect_payouts_enabled")
            or seller.get("stripe_connect_onboarding_complete")
        )
    )

    payout_id = str(uuid.uuid4())
    base_row = {
        "id": payout_id,
        "section": section,
        "listing_id": listing_id,
        "lot_number": lot_number,
        "listing_title": listing_title,
        "seller_id": seller_id,
        "amount": round(float(net_amount), 2),
        "currency": "CAD",
        "source_transaction_id": source_transaction_id,
        "created_at": _now_iso(),
    }

    transfer_id = None
    if connect_ready:
        try:
            import stripe
            stripe.api_key = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")
            transfer = stripe.Transfer.create(
                amount=int(round(net_amount * 100)),
                currency="cad",
                destination=acct,
                metadata={
                    "listing_id": listing_id,
                    "section": section,
                    "seller_id": seller_id,
                    "platform": "bidvex",
                },
                idempotency_key=f"payout-{listing_id}-{lot_number or 0}",
            )
            transfer_id = transfer.id
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[payouts] Connect transfer failed for {listing_id}: {e}")
            transfer_id = None

    if transfer_id:
        await db.seller_payouts.insert_one({
            **base_row, "status": "sent",
            "stripe_transfer_id": transfer_id,
            "sent_at": _now_iso(),
        })
        out = {"status": "sent", "payout_id": payout_id, "transfer_id": transfer_id}
        await _stamp_listing(db, section, listing_id, "payout_sent")
        await _notify_seller_payout_sent(db, seller, listing_title, net_amount, transfer_id)
    else:
        # Fallback — pending queue + admin notification
        await db.seller_payouts.insert_one({**base_row, "status": "pending"})
        try:
            from services.payment_collection import _enqueue_payout_pending
            await _enqueue_payout_pending(
                db, section=section, listing_id=listing_id, listing_title=listing_title,
                seller_id=seller_id, amount=net_amount, lot_number=lot_number,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[payouts] pending enqueue failed for {listing_id}: {e}")
        out = {"status": "pending", "payout_id": payout_id}
        await _stamp_listing(db, section, listing_id, "payout_pending")
        await _notify_admin_payout_pending(db, seller_id, listing_id, listing_title, net_amount)

    return out


_SECTION_COLLECTIONS = {
    "marketplace": "listings",
    "lots": "multi_item_listings",
    "storage": "storage_auctions",
    "vehicles": "vehicle_listings",
}


async def _stamp_listing(db, section: str, listing_id: str, payout_status: str):
    coll = _SECTION_COLLECTIONS.get(section, "listings")
    try:
        await db[coll].update_one(
            {"id": listing_id},
            {"$set": {"payout_status": payout_status, "payout_status_at": _now_iso()}},
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[payouts] stamp failed for {listing_id}: {e}")


async def _notify_seller_payout_sent(db, seller, listing_title, net_amount, transfer_id):
    if not seller:
        return
    # Bell notification (bilingual via notifications_i18n payout kind if present)
    try:
        from services.notifications_i18n import create_notification
        await create_notification(
            db, user_id=seller["id"], kind="payout_sent",
            params={"amount": f"{net_amount:,.2f}", "title": listing_title},
            data={"transfer_id": transfer_id},
        )
    except Exception:  # noqa: BLE001
        # Fallback raw notification when the kind isn't registered
        try:
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()), "user_id": seller["id"], "type": "payout_sent",
                "title_en": "Payout Sent", "title_fr": "Versement envoyé",
                "message_en": f"Your payout of ${net_amount:,.2f} CAD for \"{listing_title}\" is on its way.",
                "message_fr": f"Votre versement de {net_amount:,.2f} $ CAD pour « {listing_title} » est en route.",
                "read": False, "created_at": _now_iso(),
            })
        except Exception:  # noqa: BLE001
            pass
    # Email — bilingual
    try:
        if seller.get("email"):
            from services.emails._email_core import send_email, _base_template
            html = (
                f"<h2 style='margin:0 0 20px 0;color:#1e3a8a;'>Payout Sent / Versement envoy&eacute;</h2>"
                f"<p>Hi {seller.get('name','')},</p>"
                f"<p>Your payout for <strong>{listing_title}</strong> has been sent to your connected bank account.</p>"
                f"<p style='color:#555;'>Votre versement pour <strong>{listing_title}</strong> a &eacute;t&eacute; envoy&eacute; vers votre compte bancaire connect&eacute;.</p>"
                f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='background:#ecfdf5;border-radius:8px;margin:16px 0;'>"
                f"<tr><td style='padding:14px 18px;'>"
                f"<p style='margin:0;font-size:22px;font-weight:bold;color:#047857;'>${net_amount:,.2f} CAD</p>"
                f"<p style='margin:4px 0 0 0;font-size:12px;color:#555;'>Transaction ID: {transfer_id}</p>"
                f"<p style='margin:4px 0 0 0;font-size:12px;color:#555;'>Expected arrival / Arriv&eacute;e pr&eacute;vue : 2&ndash;3 business days / jours ouvrables</p>"
                f"</td></tr></table>"
            )
            await send_email(
                to_email=seller["email"],
                subject=f"Payout sent: ${net_amount:,.2f} CAD / Versement envoyé — {listing_title}",
                html_content=_base_template(html, "Payout Sent"),
            )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[payouts] seller payout email failed: {e}")


async def _notify_admin_payout_pending(db, seller_id, listing_id, listing_title, net_amount):
    try:
        from services.notifications_i18n import create_notification
        admins = await db.users.find({"role": {"$in": ["admin", "super_admin"]}}, {"_id": 0, "id": 1}).to_list(10)
        for a in admins:
            try:
                await create_notification(
                    db, user_id=a["id"], kind="payout_pending_admin",
                    params={"amount": f"{net_amount:,.2f}", "title": listing_title},
                    data={"listing_id": listing_id, "seller_id": seller_id},
                )
            except Exception:  # noqa: BLE001
                await db.notifications.insert_one({
                    "id": str(uuid.uuid4()), "user_id": a["id"], "type": "payout_pending_admin",
                    "title_en": "Manual Payout Required", "title_fr": "Versement manuel requis",
                    "message_en": f"Seller has no Stripe Connect — manual payout of ${net_amount:,.2f} CAD needed for \"{listing_title}\".",
                    "message_fr": f"Le vendeur n'a pas Stripe Connect — versement manuel de {net_amount:,.2f} $ CAD requis pour « {listing_title} ».",
                    "read": False, "created_at": _now_iso(),
                })
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[payouts] admin pending notification failed: {e}")
