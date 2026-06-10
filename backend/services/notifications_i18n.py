"""
services/notifications_i18n.py — iter296 P0 BUG 4

Single source of truth for all platform (bell-icon) notifications.
Every notification is created with BOTH English and French copy in
one atomic insert so the frontend never has to fall back to an empty
string regardless of the user's `lang` preference.

Why a dedicated module?
=======================
Before iter296 the codebase had 80+ ad-hoc `db.notifications.insert_one`
calls scattered across routes, each with only English `title`/`message`
fields. The bell-icon dropdown could not render anything for FR users
because no `*_fr` fields existed. This module:

  1. Centralises EVERY notification type (auction_won, auction_ended,
     outbid, ending_soon, deposit_required, broker_request_received,
     broker_request_approved, new_bid, …) with bilingual templates.
  2. Returns the `notification` dict so callers can persist it via
     their own DB handle (sync or async, motor or pymongo).
  3. Exposes `create_notification()` for atomic insert + return.

USAGE
=====
    from services.notifications_i18n import create_notification

    await create_notification(
        db,
        user_id=winner_id,
        kind="auction_won",
        params={"title": "Vintage Lamp", "amount": 250.0,
                "listing_id": "abc-123"},
    )
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _fmt_money(amount: Any) -> str:
    try:
        return f"${float(amount):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


# ─── Bilingual template registry ──────────────────────────────────────
# Each kind owns (title_en, message_en, title_fr, message_fr) lambdas
# so the templates can interpolate the runtime params dict.
_TEMPLATES = {
    "auction_won": (
        lambda p: "You Won!",
        lambda p: f"Congratulations! You won '{p.get('title','this item')}' for {_fmt_money(p.get('amount'))}.",
        lambda p: "Vous avez gagné !",
        lambda p: f"Félicitations ! Vous avez remporté « {p.get('title','cet article')} » pour {_fmt_money(p.get('amount'))}.",
    ),
    "auction_ended": (
        lambda p: "Auction Ended",
        lambda p: f"'{p.get('title','Your item')}' sold for {_fmt_money(p.get('amount'))}.",
        lambda p: "Enchère terminée",
        lambda p: f"« {p.get('title','Votre article')} » a été vendu pour {_fmt_money(p.get('amount'))}.",
    ),
    "auction_ended_no_winner": (
        lambda p: "Auction Ended — No Bids",
        lambda p: f"Your auction '{p.get('title','your item')}' ended without bids. You can relist for free.",
        lambda p: "Enchère terminée — sans mise",
        lambda p: f"Votre enchère « {p.get('title','votre article')} » s'est terminée sans mise. Vous pouvez la republier gratuitement.",
    ),
    "outbid": (
        lambda p: "You've been outbid",
        lambda p: f"Someone bid {_fmt_money(p.get('new_bid'))} on '{p.get('title','this item')}'. Place a higher bid to stay in the lead.",
        lambda p: "Vous avez été surenchéri",
        lambda p: f"Quelqu'un a misé {_fmt_money(p.get('new_bid'))} sur « {p.get('title','cet article')} ». Placez une mise plus élevée pour reprendre la tête.",
    ),
    "ending_soon": (
        lambda p: "Auction Ending Soon",
        lambda p: f"'{p.get('title','An auction')}' ends in 15 minutes. Place your final bid now.",
        lambda p: "Enchère se termine bientôt",
        lambda p: f"« {p.get('title','Une enchère')} » se termine dans 15 minutes. Placez votre mise finale maintenant.",
    ),
    "deposit_required": (
        lambda p: "Deposit Required to Bid",
        lambda p: f"A refundable deposit of {_fmt_money(p.get('amount'))} is required to bid on '{p.get('title','this item')}'.",
        lambda p: "Dépôt requis pour miser",
        lambda p: f"Un dépôt remboursable de {_fmt_money(p.get('amount'))} est requis pour miser sur « {p.get('title','cet article')} ».",
    ),
    "broker_request_received": (
        lambda p: "New Broker Request",
        lambda p: f"{p.get('buyer_name','A buyer')} has requested you as their broker.",
        lambda p: "Nouvelle demande de courtier",
        lambda p: f"{p.get('buyer_name','Un acheteur')} vous a demandé comme courtier.",
    ),
    "broker_request_approved": (
        lambda p: "Broker Request Approved",
        lambda p: f"{p.get('broker_name','Your broker')} has approved your request. You can now bid on restricted vehicles.",
        lambda p: "Demande de courtier approuvée",
        lambda p: f"{p.get('broker_name','Votre courtier')} a approuvé votre demande. Vous pouvez maintenant miser sur les véhicules restreints.",
    ),
    "broker_request_rejected": (
        lambda p: "Broker Request Declined",
        lambda p: f"{p.get('broker_name','The broker')} has declined your request.",
        lambda p: "Demande de courtier refusée",
        lambda p: f"{p.get('broker_name','Le courtier')} a refusé votre demande.",
    ),
    "new_bid": (
        lambda p: "New Bid on Your Listing",
        lambda p: f"{p.get('bidder_alias','Someone')} bid {_fmt_money(p.get('amount'))} on '{p.get('title','your listing')}'.",
        lambda p: "Nouvelle mise sur votre annonce",
        lambda p: (
            f"{p.get('bidder_alias') or 'Quelqu’un'} a misé "
            f"{_fmt_money(p.get('amount'))} sur "
            f"« {p.get('title','votre annonce')} »."
        ),
    ),
    "winner_payment_due": (
        lambda p: "Payment Due",
        lambda p: f"Settle {_fmt_money(p.get('amount'))} for '{p.get('title','this item')}' within {p.get('days', 14)} days to avoid late penalties.",
        lambda p: "Paiement dû",
        lambda p: f"Réglez {_fmt_money(p.get('amount'))} pour « {p.get('title','cet article')} » dans les {p.get('days', 14)} jours pour éviter les pénalités.",
    ),
}


def build_notification(
    *,
    user_id: str,
    kind: str,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build (but don't persist) a bilingual notification doc.

    Args
    ----
    user_id : recipient
    kind    : registry key (auction_won, outbid, ending_soon, …).
              Unknown kinds fall back to a generic system message
              so a bug never inserts an empty notification.
    params  : interpolation values for the template lambdas.
    data    : free-form payload attached for the frontend
              (listing_id, lot_id, amount, action_url, …).
    """
    params = params or {}
    data = data or {}

    tmpl = _TEMPLATES.get(kind)
    if tmpl is None:
        logger.warning(f"[notif_i18n] unknown kind '{kind}' — using fallback")
        title_en = "Update"
        msg_en   = "You have a new update on BidVex."
        title_fr = "Mise à jour"
        msg_fr   = "Vous avez une nouvelle mise à jour sur BidVex."
    else:
        t_en_fn, m_en_fn, t_fr_fn, m_fr_fn = tmpl
        try:
            title_en = t_en_fn(params)
            msg_en   = m_en_fn(params)
            title_fr = t_fr_fn(params)
            msg_fr   = m_fr_fn(params)
        except Exception as e:  # noqa: BLE001
            logger.error(f"[notif_i18n] template render failed for {kind}: {e}")
            title_en = title_fr = "Update"
            msg_en   = msg_fr   = "You have a new update on BidVex."

    return {
        "id":         str(uuid.uuid4()),
        "user_id":    user_id,
        "type":       kind,
        # English (legacy field names — kept so old frontend code keeps working).
        "title":      title_en,
        "message":    msg_en,
        # iter296 P0 BUG 4 — French companions.
        "title_en":   title_en,
        "message_en": msg_en,
        "title_fr":   title_fr,
        "message_fr": msg_fr,
        "data":       data,
        "read":       False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


async def create_notification(
    db,
    *,
    user_id: str,
    kind: str,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build + insert in one atomic call. Returns the persisted doc."""
    doc = build_notification(user_id=user_id, kind=kind, params=params, data=data)
    try:
        await db.notifications.insert_one(doc)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[notif_i18n] insert failed: {e}")
    return doc


__all__ = ["build_notification", "create_notification"]
