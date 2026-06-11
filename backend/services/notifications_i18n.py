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
        lambda p: f"Your listing '{p.get('title','your item')}' ended with no bids. Relist it to reach more buyers.",
        lambda p: "Enchère terminée — sans mise",
        lambda p: f"Votre annonce « {p.get('title','votre article')} » s'est terminée sans mise. Republiez-la pour atteindre plus d'acheteurs.",
    ),
    # iter298 BUG 3/4 — payment lifecycle notifications.
    "payment_collected": (
        lambda p: "Payment Confirmed",
        lambda p: f"Your payment of {_fmt_money(p.get('amount'))} for '{p.get('title','your item')}' was processed. Your receipt is in your dashboard.",
        lambda p: "Paiement confirmé",
        lambda p: f"Votre paiement de {_fmt_money(p.get('amount'))} pour « {p.get('title','votre article')} » a été traité. Votre reçu est dans votre tableau de bord.",
    ),
    "payment_collected_seller": (
        lambda p: "Sale Payment Collected",
        lambda p: f"Payment for '{p.get('title','your item')}' was collected. Net payout: {_fmt_money(p.get('amount'))}. Your statement is in your dashboard.",
        lambda p: "Paiement de la vente encaissé",
        lambda p: f"Le paiement pour « {p.get('title','votre article')} » a été encaissé. Versement net : {_fmt_money(p.get('amount'))}. Votre relevé est dans votre tableau de bord.",
    ),
    "payment_link_sent": (
        lambda p: "Payment Required — 48 Hours",
        lambda p: f"You won '{p.get('title','this item')}'. Pay {_fmt_money(p.get('amount'))} within 48 hours via the link sent to your email.",
        lambda p: "Paiement requis — 48 heures",
        lambda p: f"Vous avez remporté « {p.get('title','cet article')} ». Payez {_fmt_money(p.get('amount'))} sous 48 heures via le lien envoyé par courriel.",
    ),
    "payment_failed": (
        lambda p: "Payment Failed",
        lambda p: f"Your payment of {_fmt_money(p.get('amount'))} for '{p.get('title','this item')}' failed. Please update your payment method.",
        lambda p: "Échec du paiement",
        lambda p: f"Votre paiement de {_fmt_money(p.get('amount'))} pour « {p.get('title','cet article')} » a échoué. Veuillez mettre à jour votre méthode de paiement.",
    ),
    # iter299 P1 — "Last Chance" 1-hour nudge for watchers + trailing bidders.
    "last_chance": (
        lambda p: "⏰ Last Chance",
        lambda p: f"Last chance to bid on '{p.get('title','this item')}' — auction closes soon.",
        lambda p: "⏰ Dernière chance",
        lambda p: f"Dernière chance de miser sur « {p.get('title','cet article')} » — l'enchère se termine bientôt.",
    ),
    # iter299 P1 — Marketplace moderation decisions.
    "listing_approved": (
        lambda p: "Listing Approved",
        lambda p: f"Your listing '{p.get('title','your item')}' was approved and is now live.",
        lambda p: "Annonce approuvée",
        lambda p: f"Votre annonce « {p.get('title','votre article')} » a été approuvée et est maintenant en ligne.",
    ),
    "listing_rejected": (
        lambda p: "Listing Rejected",
        lambda p: f"Your listing '{p.get('title','your item')}' was rejected. Reason: {p.get('reason','—')}",
        lambda p: "Annonce refusée",
        lambda p: f"Votre annonce « {p.get('title','votre article')} » a été refusée. Raison : {p.get('reason','—')}",
    ),
    # iter302 — manual + automated payment reminders / payouts.
    "payment_reminder": (
        lambda p: "Payment Reminder",
        lambda p: f"Friendly reminder: payment of ${p.get('amount','0')} CAD is due for \"{p.get('title','your item')}\".",
        lambda p: "Rappel de paiement",
        lambda p: f"Rappel amical : un paiement de {p.get('amount','0')} $ CAD est dû pour « {p.get('title','votre article')} ».",
    ),
    "payout_sent": (
        lambda p: "Payout Sent",
        lambda p: f"Your payout of ${p.get('amount','0')} CAD for \"{p.get('title','your item')}\" is on its way to your bank account.",
        lambda p: "Versement envoyé",
        lambda p: f"Votre versement de {p.get('amount','0')} $ CAD pour « {p.get('title','votre article')} » est en route vers votre compte bancaire.",
    ),
    "payout_pending_admin": (
        lambda p: "Manual Payout Required",
        lambda p: f"Seller has no Stripe Connect account — manual payout of ${p.get('amount','0')} CAD needed for \"{p.get('title','item')}\".",
        lambda p: "Versement manuel requis",
        lambda p: f"Le vendeur n'a pas de compte Stripe Connect — versement manuel de {p.get('amount','0')} $ CAD requis pour « {p.get('title','article')} ».",
    ),
    # iter301 — Buyer ↔ Seller messaging bell notification.
    "new_message": (
        lambda p: "New Message",
        lambda p: f"{p.get('sender_name','Someone')} sent you a message: \"{(p.get('preview') or '')[:80]}\"",
        lambda p: "Nouveau message",
        lambda p: f"{p.get('sender_name') or 'Quelqu’un'} vous a envoyé un message : « {(p.get('preview') or '')[:80]} »",
    ),
    # iter301 — Review received (either direction).
    "new_review": (
        lambda p: "New Review Received",
        lambda p: f"{p.get('reviewer_name','Someone')} left you a {p.get('rating','5')}-star review.",
        lambda p: "Nouvel avis reçu",
        lambda p: f"{p.get('reviewer_name') or 'Quelqu’un'} vous a laissé un avis de {p.get('rating','5')} étoile(s).",
    ),
    # iter301 — Abusive message thread reported (admin-facing, EN ok but bilingual for consistency).
    "message_thread_reported": (
        lambda p: "Message Thread Reported",
        lambda p: f"A conversation was reported by {p.get('reporter_name','a user')}. Reason: {p.get('reason','—')}",
        lambda p: "Fil de discussion signalé",
        lambda p: f"Une conversation a été signalée par {p.get('reporter_name','un utilisateur')}. Raison : {p.get('reason','—')}",
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
    # iter300 — Top Seller merit badge.
    "top_seller_earned": (
        lambda p: "⭐ You're a Top Seller!",
        lambda p: "Congratulations — you are now one of BidVex's top 5 sellers by total sales volume. The Top Seller badge now appears on your storefront and listings.",
        lambda p: "⭐ Vous êtes un Meilleur Vendeur !",
        lambda p: "Félicitations — vous faites maintenant partie des 5 meilleurs vendeurs BidVex par volume de ventes. L'insigne Meilleur Vendeur apparaît désormais sur votre vitrine et vos annonces.",
    ),
    # iter300 — Follow Seller fan-out.
    "followed_seller_new_listing": (
        lambda p: "New listing from a seller you follow",
        lambda p: f"{p.get('seller_name','A seller you follow')} just listed '{p.get('title','an item')}' — bid now!",
        lambda p: "Nouvelle annonce d'un vendeur que vous suivez",
        lambda p: f"{p.get('seller_name','Un vendeur que vous suivez')} vient de publier « {p.get('title','un article')} » — misez maintenant !",
    ),
    # iter300 — Dispute lifecycle.
    "dispute_received": (
        lambda p: "Dispute Under Review",
        lambda p: f"A dispute on '{p.get('title','a transaction')}' has been received and is under review. Our team will contact you with the outcome.",
        lambda p: "Litige en cours d'examen",
        lambda p: f"Un litige concernant « {p.get('title','une transaction')} » a été reçu et est en cours d'examen. Notre équipe vous contactera avec le résultat.",
    ),
    "dispute_filed_admin": (
        lambda p: "🚨 New Dispute Filed",
        lambda p: f"{p.get('filer','A user')} filed a dispute on '{p.get('title','a listing')}'. Review it in the Disputed Settlements tab.",
        lambda p: "🚨 Nouveau litige déposé",
        lambda p: f"{p.get('filer','Un utilisateur')} a déposé un litige concernant « {p.get('title','une annonce')} ». Examinez-le dans l'onglet Litiges.",
    ),
    "dispute_resolved": (
        lambda p: "Dispute Resolved",
        lambda p: (f"The dispute on '{p.get('title','your transaction')}' has been resolved — "
                   + ("funds released to the seller." if p.get('outcome') == 'release_to_seller'
                      else "the buyer has been refunded." if p.get('outcome') == 'refund_buyer'
                      else "see your email for details.")),
        lambda p: "Litige résolu",
        lambda p: (f"Le litige concernant « {p.get('title','votre transaction')} » a été résolu — "
                   + ("fonds libérés au vendeur." if p.get('outcome') == 'release_to_seller'
                      else "l'acheteur a été remboursé." if p.get('outcome') == 'refund_buyer'
                      else "consultez votre courriel pour les détails.")),
    ),
    # iter300 — Overdue auto-capture escalation.
    "payment_final_warning": (
        lambda p: "⚠️ Final Warning — Payment Overdue",
        lambda p: f"Your payment of {_fmt_money(p.get('amount'))} for '{p.get('title','this item')}' is overdue. Your account may be suspended if not resolved within 24 hours.",
        lambda p: "⚠️ Dernier avertissement — Paiement en retard",
        lambda p: f"Votre paiement de {_fmt_money(p.get('amount'))} pour « {p.get('title','cet article')} » est en retard. Votre compte pourrait être suspendu si la situation n'est pas résolue dans les 24 heures.",
    ),
    "bidding_suspended": (
        lambda p: "Bidding Privileges Suspended",
        lambda p: f"After 3 failed payment attempts for '{p.get('title','an item')}', your bidding privileges have been suspended. Contact support@bidvex.com to resolve.",
        lambda p: "Privilèges d'enchères suspendus",
        lambda p: f"Après 3 tentatives de paiement échouées pour « {p.get('title','un article')} », vos privilèges d'enchères ont été suspendus. Contactez support@bidvex.com pour résoudre.",
    ),
    "bidding_suspension_lifted": (
        lambda p: "Bidding Privileges Restored",
        lambda p: "Your bidding privileges have been restored by our team. You can bid again on BidVex.",
        lambda p: "Privilèges d'enchères rétablis",
        lambda p: "Vos privilèges d'enchères ont été rétablis par notre équipe. Vous pouvez de nouveau miser sur BidVex.",
    ),
    "overdue_capture_failed_admin": (
        lambda p: "Overdue Auto-Capture Failed",
        lambda p: f"Automatic charge of {_fmt_money(p.get('amount'))} for '{p.get('title','a listing')}' failed. Review in the admin panel.",
        lambda p: "Échec du prélèvement automatique",
        lambda p: f"Le prélèvement automatique de {_fmt_money(p.get('amount'))} pour « {p.get('title','une annonce')} » a échoué. Vérifiez dans le panneau admin.",
    ),
    "bidding_suspended_admin": (
        lambda p: "Buyer Bidding Suspended",
        lambda p: f"A buyer was suspended after 3 failed payment attempts on '{p.get('title','a listing')}' ({_fmt_money(p.get('amount'))}). You can lift the suspension in User Management.",
        lambda p: "Acheteur suspendu",
        lambda p: f"Un acheteur a été suspendu après 3 tentatives de paiement échouées sur « {p.get('title','une annonce')} » ({_fmt_money(p.get('amount'))}). Vous pouvez lever la suspension dans Gestion des utilisateurs.",
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
