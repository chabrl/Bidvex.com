"""
iter217 Phase 5 — Email outbox drainer.

Background worker that polls the `email_outbox` MongoDB collection and
delivers queued messages via SendGrid (or skips gracefully if SendGrid
is not configured — the dev preview).

Handles the kinds queued by v8 / v8.1:
  • `vehicle_released_with_receipt`  — bilingual buyer receipt link
  • `title_transfer_overdue`         — broker reminder (cron-triggered)
  • `title_transfer_filed`           — buyer confirmation when broker
                                         logs SAAQ / ServiceOntario etc.
  • `day21_broker_reminder`          — retention reminder (Task 2)

Each outbox row carries at minimum:
    { id, kind, to_user_id?, to_email?, context: {...}, queued_at }

Drained rows are stamped with `sent_at` and `delivery_status`.
Failed rows are retried up to `MAX_ATTEMPTS` times before being marked
`failed`. The job is idempotent — re-runs skip already-sent rows.

Bilingual decision: we honor `user.language` if available, else default
to English. Templates can be configured via env vars
SENDGRID_TEMPLATE_<KIND>_<EN|FR>; if a template id is missing we log
and skip rather than raising (keeps the worker green in dev).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Subject lines, hard-coded fallbacks for dev (no SendGrid templates yet) ──
_SUBJECTS = {
    "vehicle_released_with_receipt": {
        "en": "Your BidVex transaction receipt is ready",
        "fr": "Votre reçu de transaction BidVex est prêt",
    },
    "title_transfer_overdue": {
        "en": "ACTION REQUIRED — Title transfer overdue",
        "fr": "ACTION REQUISE — Transfert de propriété en retard",
    },
    "title_transfer_filed": {
        "en": "Your vehicle title transfer has been filed",
        "fr": "Le transfert de propriété de votre véhicule a été déposé",
    },
    "day21_broker_reminder": {
        "en": "Buying at auction? A licensed broker is required",
        "fr": "Acheter aux enchères ? Un courtier licencié est requis",
    },
    # FEATURE PATCH v9 — Feature 1: end-time change notifications
    "auction_end_time_changed_seller": {
        "en": "Your auction end time was updated by an administrator",
        "fr": "L'heure de fin de votre enchère a été modifiée par un administrateur",
    },
    "auction_end_time_changed_bidder": {
        "en": "Heads up — an auction you bid on has a new end time",
        "fr": "Attention — une enchère sur laquelle vous avez enchéri a une nouvelle heure de fin",
    },
    "auction_end_time_changed_watchlist": {
        "en": "An auction in your watchlist has a new end time",
        "fr": "Une enchère de votre liste de suivi a une nouvelle heure de fin",
    },
    # FEATURE PATCH v9 — Feature 3: AI review flow
    "ai_review_admin_alert": {
        "en": "[BidVex Admin] A listing requires AI category review",
        "fr": "[Admin BidVex] Une annonce nécessite un examen IA de catégorie",
    },
    "ai_review_admin_escalation": {
        "en": "[BidVex Admin] AI review still open after 60 minutes",
        "fr": "[Admin BidVex] L'examen IA est ouvert depuis plus de 60 minutes",
    },
    "ai_review_approved": {
        "en": "Your listing has been approved",
        "fr": "Votre annonce a été approuvée",
    },
    "ai_review_rejected": {
        "en": "Your listing was rejected after review",
        "fr": "Votre annonce a été rejetée après examen",
    },
}


def _public_url(path: str) -> str:
    """Return the user-facing absolute URL for a path."""
    base = (
        os.environ.get("PUBLIC_FRONTEND_URL")
        or os.environ.get("REACT_APP_BACKEND_URL")
        or "https://bidvex.com"
    ).rstrip("/")
    return base + ("/" + path.lstrip("/") if path else "")


async def _resolve_recipient(db, row: Dict[str, Any]) -> tuple[Optional[str], Optional[str], str]:
    """Returns (email, name, lang).  Empty email = skip row."""
    email = row.get("to_email")
    name  = None
    lang  = "en"
    user_id = row.get("to_user_id")
    if user_id:
        u = await db.users.find_one({"id": user_id}, {"_id": 0,
                                                       "email": 1, "name": 1, "full_name": 1, "language": 1,
                                                       "preferred_language": 1})
        if u:
            email = email or u.get("email")
            name  = u.get("full_name") or u.get("name")
            lang  = (u.get("language") or u.get("preferred_language") or "en")[:2].lower()
            if lang not in ("en", "fr"):
                lang = "en"
    return email, name, lang


def _template_id(kind: str, lang: str) -> Optional[str]:
    """Look up a SendGrid Dynamic Template id for `<kind>_<lang>`."""
    env_key = f"SENDGRID_TEMPLATE_{kind.upper()}_{lang.upper()}"
    return os.environ.get(env_key) or None


async def _send_via_sendgrid(row: Dict[str, Any], email: str, name: Optional[str],
                              lang: str, dynamic_data: Dict[str, Any]) -> tuple[bool, str]:
    """Hands off to SendGrid. Returns (ok, reason).

    Phase 5.3 — when a Dynamic Template id is missing for the given kind,
    we render an inline HTML fallback (services/templates/welcome_email.py)
    and ship it as a plain HTML email via `send_html_email`. This means
    the 7 v9 email kinds (auction_end_time_changed_*, ai_review_*,
    quantity_invoice) no longer mark `stubbed_no_template` — they go live
    immediately even without SendGrid template ids configured.
    """
    if not email:
        return False, "no_recipient_email"
    tmpl_id = _template_id(row["kind"], lang)
    if tmpl_id:
        try:
            from services.email_service import send_template_email
            sent = await send_template_email(
                to_email=email, to_name=name or "",
                template_id=tmpl_id, dynamic_data=dynamic_data,
                is_marketing=(row["kind"] == "day21_broker_reminder"),
            )
            return bool(sent), ("sent" if sent else "sendgrid_returned_false")
        except Exception as e:
            logger.error("[email_outbox] send (template) failed kind=%s err=%s", row.get("kind"), e, exc_info=True)
            return False, f"exception:{type(e).__name__}"

    # No template id → try inline HTML fallback
    try:
        from services.templates.welcome_email import render_kind_html
        html = render_kind_html(row["kind"], dynamic_data)
    except Exception as e:
        logger.warning("[email_outbox] HTML fallback import failed kind=%s err=%s", row.get("kind"), e)
        html = None

    if not html:
        # Truly no fallback available — keep legacy stub behaviour so we don't loop.
        logger.info("[email_outbox] no template AND no HTML fallback for kind=%s lang=%s — stubbing", row["kind"], lang)
        return True, "stubbed_no_template"

    subject = dynamic_data.get("subject") or _SUBJECTS.get(row["kind"], {}).get(lang) \
        or _SUBJECTS.get(row["kind"], {}).get("en") or "BidVex"
    try:
        from services.email_service import send_html_email
        sent = await send_html_email(
            to_email=email, to_name=name or "",
            subject=subject, html_content=html,
            is_marketing=(row["kind"] == "day21_broker_reminder"),
        )
        if sent:
            return True, "sent_html_fallback"
        # SendGrid not configured — gracefully degrade so the queue doesn't back up.
        return True, "stubbed_no_sendgrid"
    except Exception as e:
        logger.error("[email_outbox] HTML fallback send failed kind=%s err=%s", row.get("kind"), e, exc_info=True)
        return False, f"exception_html:{type(e).__name__}"


def _build_dynamic_data(row: Dict[str, Any], lang: str, name: Optional[str]) -> Dict[str, Any]:
    """Per-kind dynamic data assembly. Always includes `lang`, `name` and a CTA URL."""
    ctx = row.get("context") or {}
    kind = row["kind"]
    data: Dict[str, Any] = {
        "lang":           lang,
        "name":           name or "",
        "current_year":   datetime.now().year,
        "subject":        _SUBJECTS.get(kind, {}).get(lang) or _SUBJECTS.get(kind, {}).get("en") or "BidVex",
    }

    if kind == "vehicle_released_with_receipt":
        url = _public_url(ctx.get("receipt_url") or "/")
        data.update({
            "receipt_url":    url,
            "invoice_number": ctx.get("invoice_number"),
            "pickup_code":    ctx.get("pickup_code"),
            "headline":       ("Your transaction receipt is ready"
                               if lang == "en"
                               else "Votre reçu de transaction est prêt"),
            "body":           (f"Your broker has confirmed the release of your vehicle. "
                               f"Your shareable transaction receipt is available at the link below — "
                               f"you can forward it to your insurance company or provincial vehicle "
                               f"registry as proof of purchase.")
                              if lang == "en" else
                              (f"Votre courtier a confirmé la remise de votre véhicule. "
                               f"Votre reçu de transaction partageable est disponible au lien ci-dessous "
                               f"— vous pouvez le transférer à votre compagnie d'assurance ou au registre "
                               f"des véhicules provincial comme preuve d'achat."),
            "cta_label":      "View Receipt" if lang == "en" else "Voir le reçu",
            "cta_url":        url,
        })

    elif kind == "title_transfer_overdue":
        url = _public_url("/broker/dashboard")
        days_overdue = ctx.get("days_overdue")
        data.update({
            "invoice_number": ctx.get("invoice_number"),
            "broker_name":    ctx.get("broker_name"),
            "days_overdue":   days_overdue,
            "headline":       "ACTION REQUIRED — Title transfer overdue" if lang == "en" else "ACTION REQUISE — Transfert de propriété en retard",
            "body":           (f"The vehicle for invoice {ctx.get('invoice_number')} was released more than "
                               f"14 days ago and the provincial title transfer reference has not been "
                               f"logged yet. Please log it in your broker dashboard immediately to avoid "
                               f"account suspension under BidVex Terms § 21.")
                              if lang == "en" else
                              (f"Le véhicule pour la facture {ctx.get('invoice_number')} a été remis il y a "
                               f"plus de 14 jours et la référence du transfert de propriété provincial n'a "
                               f"pas encore été consignée. Veuillez la consigner immédiatement dans votre "
                               f"tableau de bord pour éviter la suspension du compte (art. 21 des CGU)."),
            "cta_label":      "Log Title Transfer" if lang == "en" else "Consigner le transfert",
            "cta_url":        url,
        })

    elif kind == "title_transfer_filed":
        url = _public_url(ctx.get("receipt_url") or "/")
        data.update({
            "invoice_number":     ctx.get("invoice_number"),
            "registry":           ctx.get("registry"),
            "registry_tx_number": ctx.get("registry_tx_number"),
            "transfer_date":      ctx.get("transfer_date"),
            "broker_name":        ctx.get("broker_name"),
            "headline":           "Your title transfer has been filed" if lang == "en" else "Votre transfert de propriété a été déposé",
            "body":               (f"Your broker has filed the provincial title transfer for your vehicle. "
                                   f"Reference: {ctx.get('registry')} {ctx.get('registry_tx_number')}. "
                                   f"Keep this for your records.")
                                  if lang == "en" else
                                  (f"Votre courtier a déposé le transfert de propriété provincial pour votre "
                                   f"véhicule. Référence : {ctx.get('registry')} {ctx.get('registry_tx_number')}. "
                                   f"Conservez ceci pour vos dossiers."),
            "cta_label":          "View Receipt" if lang == "en" else "Voir le reçu",
            "cta_url":            url,
        })

    elif kind == "day21_broker_reminder":
        url = _public_url("/brokers")
        data.update({
            "headline":  "Ready to buy at auction?" if lang == "en" else "Prêt à acheter aux enchères ?",
            "body":      ("Canadian law requires a licensed dealer / broker to bid at vehicle auctions. "
                          "It's just 7 simple steps: (1) browse vehicles, (2) find a verified broker in your "
                          "province, (3) request a partnership ($500 refundable deposit held — not charged), "
                          "(4) authorize your max bid, (5) auction closes & invoice is generated, "
                          "(6) two separate payments (Stripe service fees + hammer paid directly to broker), "
                          "(7) pick up your vehicle with the 8-character code. Start at the Broker Directory.")
                         if lang == "en" else
                         ("La loi canadienne exige qu'un concessionnaire / courtier licencié enchérisse "
                          "aux enchères de véhicules. C'est simple en 7 étapes : (1) parcourir les véhicules, "
                          "(2) trouver un courtier vérifié dans votre province, (3) demander un partenariat "
                          "(caution remboursable de 500 $, non débitée), (4) autoriser votre enchère "
                          "maximale, (5) fermeture des enchères et facture générée, (6) deux paiements "
                          "distincts (frais Stripe + prix marteau payé directement au courtier), "
                          "(7) récupérer votre véhicule avec le code de 8 caractères. "
                          "Commencez au répertoire des courtiers."),
            "cta_label": "Find a Broker" if lang == "en" else "Trouver un courtier",
            "cta_url":   url,
        })

    elif kind in ("auction_end_time_changed_seller", "auction_end_time_changed_bidder", "auction_end_time_changed_watchlist"):
        listing_id = ctx.get("listing_id") or ""
        url = _public_url(f"/listing/{listing_id}" if listing_id else "/marketplace")
        new_end = ctx.get("new_end_time") or ""
        old_end = ctx.get("old_end_time") or ""
        if lang == "fr":
            headline = "Heure de fin mise à jour"
            body = (
                f"L'heure de fin de l'enchère « {ctx.get('listing_title', '')} » a été "
                f"modifiée par un administrateur de BidVex. Nouvelle heure de fin : {new_end}."
                + (f" Heure précédente : {old_end}." if old_end else "")
            )
            cta = "Voir l'enchère"
        else:
            headline = "Auction end time updated"
            body = (
                f"The end time of '{ctx.get('listing_title', '')}' was updated by a BidVex "
                f"administrator. New end time: {new_end}."
                + (f" Previous end time: {old_end}." if old_end else "")
            )
            cta = "View auction"
        data.update({
            "headline":  headline,
            "body":      body,
            "cta_label": cta,
            "cta_url":   url,
            "listing_id":     listing_id,
            "listing_title":  ctx.get("listing_title"),
            "new_end_time":   new_end,
            "old_end_time":   old_end,
        })

    elif kind == "ai_review_admin_alert":
        url = _public_url("/admin?tab=ai-review")
        if lang == "fr":
            headline = "Une annonce nécessite votre examen"
            body = (
                f"Le système IA a signalé une possible incohérence de catégorie pour "
                f"« {ctx.get('listing_title', '')} ». Catégorie du vendeur : "
                f"{ctx.get('seller_category', '?')} · Catégorie suggérée : "
                f"{ctx.get('suggested_category', '?')}."
            )
            cta = "Ouvrir le panneau admin"
        else:
            headline = "A listing requires your review"
            body = (
                f"The AI system flagged a possible category mismatch for "
                f"'{ctx.get('listing_title', '')}'. Seller's category: "
                f"{ctx.get('seller_category', '?')} · Suggested: "
                f"{ctx.get('suggested_category', '?')}."
            )
            cta = "Open admin panel"
        data.update({"headline": headline, "body": body, "cta_label": cta, "cta_url": url, **ctx})

    elif kind == "ai_review_admin_escalation":
        url = _public_url("/admin?tab=ai-review")
        if lang == "fr":
            data["headline"] = "Examen IA en attente depuis plus de 60 minutes"
            data["body"] = (
                f"L'annonce « {ctx.get('listing_title', '')} » attend toujours un examen "
                f"par un administrateur. Veuillez la traiter dès que possible."
            )
            data["cta_label"] = "Ouvrir le panneau admin"
        else:
            data["headline"] = "AI review pending for over 60 minutes"
            data["body"] = (
                f"Listing '{ctx.get('listing_title', '')}' is still awaiting admin review. "
                f"Please action it as soon as possible."
            )
            data["cta_label"] = "Open admin panel"
        data["cta_url"] = url
        data.update(ctx)

    elif kind == "ai_review_approved":
        url = _public_url("/seller/dashboard")
        if lang == "fr":
            data["headline"] = "Votre annonce a été approuvée"
            data["body"] = (
                f"Bonne nouvelle — votre annonce « {ctx.get('listing_title', '')} » a été "
                f"approuvée par notre équipe et est maintenant visible sur la place de marché."
                + (f" Note de l'administrateur : {ctx.get('admin_note')}" if ctx.get("admin_note") else "")
            )
            data["cta_label"] = "Voir mes annonces"
        else:
            data["headline"] = "Your listing has been approved"
            data["body"] = (
                f"Good news — your listing '{ctx.get('listing_title', '')}' has been "
                f"approved by our team and is now visible on the marketplace."
                + (f" Admin note: {ctx.get('admin_note')}" if ctx.get("admin_note") else "")
            )
            data["cta_label"] = "View my listings"
        data["cta_url"] = url
        data.update(ctx)

    elif kind == "ai_review_rejected":
        url = _public_url("/seller/dashboard")
        if lang == "fr":
            data["headline"] = "Votre annonce a été rejetée"
            data["body"] = (
                f"Après examen, votre annonce « {ctx.get('listing_title', '')} » n'a pas pu être "
                f"approuvée."
                + (f" Note de l'administrateur : {ctx.get('admin_note')}" if ctx.get("admin_note") else "")
                + " Vous pouvez modifier la catégorie depuis votre tableau de bord et la soumettre à nouveau."
            )
            data["cta_label"] = "Ouvrir le tableau de bord"
        else:
            data["headline"] = "Your listing was rejected"
            data["body"] = (
                f"After review, your listing '{ctx.get('listing_title', '')}' could not be "
                f"approved."
                + (f" Admin note: {ctx.get('admin_note')}" if ctx.get("admin_note") else "")
                + " You can fix the category from your dashboard and resubmit it."
            )
            data["cta_label"] = "Open dashboard"
        data["cta_url"] = url
        data.update(ctx)

    else:
        data.update(ctx)   # passthrough for unknown kinds

    return data


async def drain_email_outbox(db, batch_size: int = 50) -> Dict[str, int]:
    """Process one batch of pending outbox rows.  Idempotent + retry-safe."""
    stats = {"processed": 0, "sent": 0, "stubbed": 0, "failed": 0, "skipped": 0, "retried": 0}

    cursor = db.email_outbox.find({
        "sent_at": {"$exists": False},
        "$or": [{"attempts": {"$exists": False}}, {"attempts": {"$lt": MAX_ATTEMPTS}}],
    }).sort("queued_at", 1).limit(batch_size)

    async for row in cursor:
        stats["processed"] += 1
        attempts = int(row.get("attempts", 0))
        try:
            # Phase 5.4 — Fast path for rows that ship pre-rendered HTML
            # (weekly_funnel_digest queues a complete HTML payload + subject
            # + to_email directly, bypassing dynamic template resolution).
            if row.get("html") and row.get("to_email") and row.get("subject"):
                now = _utcnow()
                try:
                    from services.email_service import send_html_email
                    sent = await send_html_email(
                        to_email=row["to_email"],
                        to_name=row.get("to_name", ""),
                        subject=row["subject"],
                        html_content=row["html"],
                        is_marketing=False,
                    )
                    reason = "sent_html_inline" if sent else "stubbed_no_sendgrid"
                except Exception as e:
                    logger.error("[email_outbox] inline HTML send failed: %s", e, exc_info=True)
                    sent, reason = False, f"exception_inline:{type(e).__name__}"
                # Inline HTML always "completes" (success or graceful stub) so we
                # never loop the same digest row forever — Mongo update inline.
                upd = {
                    "delivery_status": reason,
                    "sent_at":         now,
                    "sent_to":         row["to_email"],
                    "sent_lang":       row.get("lang", "en"),
                }
                if reason == "stubbed_no_sendgrid":
                    stats["stubbed"] += 1
                else:
                    stats["sent"] += 1
                await db.email_outbox.update_one({"_id": row["_id"]}, {"$set": upd})
                continue

            email, name, lang = await _resolve_recipient(db, row)
            if not email:
                # No recipient → skip permanently
                await db.email_outbox.update_one({"_id": row["_id"]},
                    {"$set": {"delivery_status": "skipped_no_recipient",
                              "sent_at": _utcnow()}})
                stats["skipped"] += 1
                continue

            dynamic_data = _build_dynamic_data(row, lang, name)
            ok, reason  = await _send_via_sendgrid(row, email, name, lang, dynamic_data)

            now = _utcnow()
            if ok:
                upd = {
                    "delivery_status": reason,
                    "sent_at":         now,
                    "sent_to":         email,
                    "sent_lang":       lang,
                }
                if reason == "stubbed_no_template":
                    stats["stubbed"] += 1
                else:
                    stats["sent"] += 1
                await db.email_outbox.update_one({"_id": row["_id"]}, {"$set": upd})
            else:
                next_attempts = attempts + 1
                stats["retried" if next_attempts < MAX_ATTEMPTS else "failed"] += 1
                upd = {
                    "attempts":      next_attempts,
                    "last_error":    reason,
                    "last_attempt_at": now,
                }
                if next_attempts >= MAX_ATTEMPTS:
                    upd["delivery_status"] = "failed"
                    upd["sent_at"]         = now    # stop polling
                await db.email_outbox.update_one({"_id": row["_id"]}, {"$set": upd})
        except Exception as e:
            stats["failed"] += 1
            logger.error("[email_outbox] unexpected error on row %s: %s", row.get("id"), e, exc_info=True)
            await db.email_outbox.update_one({"_id": row["_id"]},
                {"$set": {"attempts": attempts + 1, "last_error": f"unexpected:{type(e).__name__}"}})
    return stats
