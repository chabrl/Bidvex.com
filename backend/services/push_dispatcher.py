"""
iter306 — Centralized Web Push Dispatcher

Single source of truth for the 6 launch-blocking push notification triggers.
Bilingual (EN default; FR via `lang` param). Every kind maps to a concise
title + body + click-through URL. Safe-by-default: any error inside is
swallowed (warns to log) so this never breaks the primary write path.

Trigger kinds:
  • outbid           — Someone outbid you.
  • auction_won      — You won an auction.
  • ending_soon_1h   — One of your watchlisted auctions ends in ~1 hour.
  • payment_due      — Winner has 14 days to pay; payment is now overdue.
  • dispute_resolved — Your dispute has been resolved by an admin.
  • new_message      — Someone replied in your thread.

Usage:
    from services.push_dispatcher import dispatch_push
    await dispatch_push(db, user_id, kind="auction_won",
                        title_item="2020 Toyota Camry", amount=8500,
                        listing_id=lid, lang="fr")
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _fmt_amount(v) -> str:
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return str(v)


def _payload_for(kind: str, lang: str, **kw) -> Optional[dict]:
    """Build the payload for a given kind. Returns None if kind unknown."""
    fr = (lang or "").lower().startswith("fr")
    title_item = kw.get("title_item") or kw.get("listing_title") or "Item"
    amount = _fmt_amount(kw.get("amount", 0))
    listing_id = kw.get("listing_id")
    is_vehicle = bool(kw.get("is_vehicle"))
    url = kw.get("url")
    if not url and listing_id:
        url = f"/vehicle-auctions/{listing_id}" if is_vehicle else f"/listing/{listing_id}"
    url = url or "/"

    if kind == "outbid":
        return {
            "title": "Vous avez été surenchéri !" if fr else "You've been outbid!",
            "body": (f"Une nouvelle enchère de {amount} sur '{title_item}'." if fr
                     else f"Someone bid {amount} on '{title_item}'. Tap to counter-bid."),
            "type": "outbid", "url": url, "listing_id": listing_id,
        }

    if kind == "auction_won":
        return {
            "title": "Félicitations — vous avez gagné !" if fr else "Congratulations — you won!",
            "body": (f"Vous avez gagné '{title_item}' pour {amount}." if fr
                     else f"You won '{title_item}' for {amount}. Tap to complete payment."),
            "type": "auction_won", "url": url, "listing_id": listing_id,
        }

    if kind == "ending_soon_1h":
        return {
            "title": "L'enchère se termine bientôt" if fr else "Auction ending soon",
            "body": (f"'{title_item}' se termine dans environ 1 heure." if fr
                     else f"'{title_item}' ends in about 1 hour. Place your final bid!"),
            "type": "ending_soon_1h", "url": url, "listing_id": listing_id,
        }

    if kind == "payment_due":
        return {
            "title": "Paiement requis" if fr else "Payment due",
            "body": (f"Vous devez compléter le paiement de '{title_item}'." if fr
                     else f"You have 14 days to pay for '{title_item}'. Tap to checkout."),
            "type": "payment_due", "url": url, "listing_id": listing_id,
        }

    if kind == "dispute_resolved":
        outcome = kw.get("outcome", "")
        return {
            "title": "Litige résolu" if fr else "Dispute resolved",
            "body": (f"Le litige sur '{title_item}' a été résolu ({outcome})." if fr
                     else f"The dispute on '{title_item}' has been resolved ({outcome})."),
            "type": "dispute_resolved", "url": url or "/disputes", "listing_id": listing_id,
        }

    if kind == "new_message":
        sender = kw.get("sender_name") or ("Quelqu'un" if fr else "Someone")
        preview = (kw.get("preview") or "")[:80]
        return {
            "title": f"{sender} vous a envoyé un message" if fr else f"New message from {sender}",
            "body": preview or ("Touchez pour répondre." if fr else "Tap to reply."),
            "type": "new_message", "url": url or "/messages",
        }

    return None


async def dispatch_push(db, user_id: str, kind: str, **kw) -> int:
    """Dispatch a push notification to all of `user_id`'s subscribed devices.

    Returns the number of subscriptions notified (0 on any error, missing
    VAPID config, or unknown kind). Never raises — failures log warnings.
    """
    if not user_id:
        return 0
    try:
        # Resolve user's preferred language if not explicitly provided.
        lang = kw.pop("lang", None)
        if not lang:
            try:
                u = await db.users.find_one({"id": user_id}, {"_id": 0, "preferred_language": 1})
                lang = (u or {}).get("preferred_language") or "en"
            except Exception:
                lang = "en"
        payload = _payload_for(kind, lang, **kw)
        if not payload:
            logger.warning(f"[push_dispatcher] Unknown kind: {kind}")
            return 0
        # Defensive import — module is small, but avoid circular at boot.
        from routes.push_notifications import send_push_to_user
        return await send_push_to_user(db, user_id, payload)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[push_dispatcher] dispatch failed (kind={kind}, user={user_id}): {e}")
        return 0
