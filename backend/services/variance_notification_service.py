"""
iter482 P6 — Variance Notification Service
==========================================

Single canonical service that dispatches ONE idempotent SendGrid email
per genuine Stripe processing-fee SHORTFALL.

Design goals:
  * Reuses the existing canonical dispatcher
    (``services/emails/_email_core.send_email``) — no second SMTP path,
    no second SendGrid client.
  * Recipients resolved via the existing admin/office pattern
    (``compliance_notifier._admin_recipients``) — no hardcoded personal
    email.
  * Idempotent — flips ``variance_notification_status`` on the
    reconciliation doc from ``PENDING → SENT`` under an atomic
    ``$set`` guarded by the current value. A webhook retry that
    re-invokes ``reconcile_payment_intent`` re-enters this service but
    finds ``SENT`` and exits before touching SendGrid.
  * EN + FR bilingual body using the finalized iter482 P6 wording
    (« Frais de traitement du paiement »).
  * Never sends for RECONCILED / PENDING / ERROR — only SHORTFALL.
"""

from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# Bilingual copy — the FR strings are the finalized P6 vocabulary.
# Every user-visible label below is the same string used by the
# admin reconciliation dashboard so EN/FR are byte-identical across
# email and UI.
# ─────────────────────────────────────────────────────────────────
COPY = {
    "en": {
        "subject":       "BidVex — Stripe Processing Fee Variance Detected",
        "heading":       "Payment Processing Fee Variance Detected",
        "intro":         (
            "A genuine Stripe processing-fee shortfall has been detected on "
            "the payment below. BidVex is currently out of pocket for the "
            "variance amount. Please review in the Admin Payment "
            "Reconciliation dashboard."
        ),
        "payment_intent":    "Payment Intent",
        "reference":         "Reference",
        "listing":           "Listing / Invoice",
        "payer_role":        "Payer Role",
        "card_jurisdiction": "Card Jurisdiction",
        "jurisdiction_ca":   "Canada",
        "jurisdiction_int":  "International",
        "estimated":         "Estimated Payment Processing Fee",
        "recovery":          "Payment Processing Fee Recovery",
        "actual":            "Actual Stripe Processing Fee",
        "variance":          "Processing Fee Variance",
        "shortfall":         "Processing Fee Shortfall",
        "status":            "Reconciliation Status",
        "detected_at":       "Detected At (UTC)",
        "action":            "Recommended Action",
        "action_body":       (
            "Review the payment in Admin → Payment Reconciliation. "
            "Do NOT re-charge the customer — record the shortfall for "
            "internal accounting and update the payer-bears-fee policy if "
            "the jurisdiction mix has shifted."
        ),
        "footer":            (
            "This is an automated notification from the BidVex iter482 "
            "billing reconciliation service."
        ),
    },
    "fr": {
        "subject":       "BidVex — Écart des frais de traitement Stripe détecté",
        "heading":       "Écart détecté sur les frais de traitement du paiement",
        "intro":         (
            "Un manque à récupérer réel sur les frais de traitement Stripe a "
            "été détecté sur le paiement ci-dessous. BidVex est actuellement "
            "à découvert pour le montant de l'écart. Veuillez consulter le "
            "tableau de bord « Rapprochement des paiements » de "
            "l'administration."
        ),
        "payment_intent":    "Intention de paiement",
        "reference":         "Référence",
        "listing":           "Annonce / Facture",
        "payer_role":        "Rôle du payeur",
        "card_jurisdiction": "Juridiction de la carte",
        "jurisdiction_ca":   "Canada",
        "jurisdiction_int":  "International",
        "estimated":         "Frais de traitement du paiement estimés",
        "recovery":          "Récupération des frais de traitement du paiement",
        "actual":            "Frais de traitement Stripe réels",
        "variance":          "Écart des frais de traitement",
        "shortfall":         "Manque à récupérer sur les frais de traitement",
        "status":            "Statut de rapprochement",
        "detected_at":       "Détecté le (UTC)",
        "action":            "Action recommandée",
        "action_body":       (
            "Consultez le paiement dans Administration → Rapprochement des "
            "paiements. NE PAS re-facturer le client — enregistrez le "
            "manque à récupérer pour la comptabilité interne et ajustez "
            "la politique « payer bears fee » si la répartition par "
            "juridiction a changé."
        ),
        "footer":            (
            "Ceci est une notification automatique du service de "
            "rapprochement de facturation BidVex iter482."
        ),
    },
}


def _fmt_cents(cents: int, currency: str = "CAD") -> str:
    """Format integer cents as a signed money string.
    Example: 1234 → '$12.34 CAD', -50 → '-$0.50 CAD'.
    """
    try:
        c = int(cents or 0)
    except (TypeError, ValueError):
        c = 0
    sign = "-" if c < 0 else ""
    dollars = abs(c) // 100
    remainder = abs(c) % 100
    return f"{sign}${dollars}.{remainder:02d} {currency.upper()}"


def _row(label: str, value: str) -> str:
    """One-line responsive table row for the email body."""
    return (
        f'<tr>'
        f'<td style="padding:6px 12px;color:#666;font-size:13px;'
        f'border-bottom:1px solid #eee">{label}</td>'
        f'<td style="padding:6px 12px;color:#111;font-size:13px;'
        f'border-bottom:1px solid #eee;font-family:monospace">{value}</td>'
        f'</tr>'
    )


def _render_html(doc: Dict[str, Any], lang: str) -> str:
    """Render the EN or FR variance-notification email body.
    Uses ONLY plain HTML — inline styles — so SendGrid rewriting and
    Gmail Promotions gating don't strip layout.
    """
    c = COPY.get(lang) or COPY["en"]
    currency = (doc.get("currency") or "CAD").upper()
    jurisdiction_label = (
        c["jurisdiction_ca"]
        if (doc.get("resolved_jurisdiction") or "").lower() == "domestic"
        else c["jurisdiction_int"]
    )
    variance_cents = int(doc.get("variance_cents") or 0)
    is_shortfall = variance_cents < 0
    variance_label = c["shortfall"] if is_shortfall else c["variance"]
    variance_display = _fmt_cents(variance_cents, currency)

    reference = (
        doc.get("listing_id")
        or doc.get("invoice_id")
        or doc.get("charge_id")
        or "—"
    )
    payer_role = (doc.get("payer_role") or "buyer").capitalize()

    return (
        '<div style="font-family:-apple-system,BlinkMacSystemFont,'
        '\'Segoe UI\',Roboto,sans-serif;max-width:640px;margin:0 auto;'
        'padding:24px;background:#fff;color:#111">'
        f'<h2 style="margin:0 0 12px;color:#b91c1c;font-size:18px">'
        f'{c["heading"]}</h2>'
        f'<p style="color:#374151;font-size:14px;line-height:1.5">'
        f'{c["intro"]}</p>'
        '<table style="width:100%;border-collapse:collapse;margin-top:16px">'
        + _row(c["payment_intent"], doc.get("payment_intent_id") or "—")
        + _row(c["reference"], reference)
        + _row(c["payer_role"], payer_role)
        + _row(c["card_jurisdiction"], jurisdiction_label)
        + _row(c["estimated"], _fmt_cents(doc.get("estimated_cents"), currency))
        + _row(c["recovery"], _fmt_cents(doc.get("recovery_cents"), currency))
        + _row(c["actual"], _fmt_cents(doc.get("actual_cents"), currency))
        + _row(variance_label, variance_display)
        + _row(c["status"], doc.get("reconciliation_status") or "—")
        + _row(c["detected_at"], doc.get("updated_at") or "—")
        + '</table>'
        f'<h3 style="margin:24px 0 8px;font-size:15px;color:#111">{c["action"]}</h3>'
        f'<p style="color:#374151;font-size:13px;line-height:1.5">{c["action_body"]}</p>'
        f'<p style="margin-top:32px;color:#9ca3af;font-size:11px">{c["footer"]}</p>'
        '</div>'
    )


async def _resolve_recipients(db) -> List[str]:
    """Recipient resolution mirrors ``compliance_notifier._admin_recipients``.
    Rules:
      1. All ``role in {admin, super_admin}`` users (up to 20).
      2. Plus ``BILLING_ALERT_EMAIL`` env override if set.
      3. Plus the existing ``ADMIN_EMAIL`` env fallback (last-resort).
    Deduped, empty-safe, order-preserving.
    """
    recipients: List[str] = []
    seen: set = set()

    def _add(email: Optional[str]) -> None:
        if not email:
            return
        e = email.strip().lower()
        if e and e not in seen:
            seen.add(e)
            recipients.append(email)

    try:
        cur = db.users.find(
            {"role": {"$in": ["admin", "super_admin"]}, "email": {"$ne": None}},
            {"_id": 0, "email": 1},
        ).limit(20)
        async for u in cur:
            _add(u.get("email"))
    except Exception as e:  # pragma: no cover — DB failure
        logger.warning(f"[variance-notify] admin recipient lookup failed: {e}")

    _add(os.environ.get("BILLING_ALERT_EMAIL"))
    _add(os.environ.get("ADMIN_EMAIL"))
    return recipients


async def dispatch_variance_notification(
    db,
    doc: Dict[str, Any],
) -> Dict[str, Any]:
    """Dispatch ONE variance email for the given reconciliation doc.
    Idempotency is enforced by an atomic conditional ``$set`` on
    ``variance_notification_status`` — the first caller that flips it
    from missing/PENDING to SENDING wins and sends the mail. Concurrent
    or replayed callers observe the SENDING/SENT state and no-op.

    Returns a summary envelope:
        {"status": "sent" | "skipped" | "no_recipients" | "not_shortfall",
         "recipients": [...], "sent_at": iso, "notification_id": pi_id}
    """
    pi_id = doc.get("payment_intent_id")
    if not pi_id:
        return {"status": "skipped", "reason": "missing_payment_intent_id"}

    # Guard rail — dispatch is only allowed for genuine SHORTFALL.
    if (doc.get("reconciliation_status") or "").upper() != "SHORTFALL":
        return {"status": "not_shortfall"}

    # Atomic idempotency guard. We only claim the send if the doc's
    # variance_notification_status is either missing OR "PENDING". Any
    # concurrent caller that already flipped it to SENDING / SENT is
    # ignored.
    now_iso = datetime.now(timezone.utc).isoformat()
    claim = await db.payment_processing_reconciliation.find_one_and_update(
        {
            "payment_intent_id": pi_id,
            "$or": [
                {"variance_notification_status": {"$exists": False}},
                {"variance_notification_status": "PENDING"},
            ],
        },
        {
            "$set": {
                "variance_notification_status": "SENDING",
                "variance_notification_claimed_at": now_iso,
            },
        },
        return_document=False,
    )
    if claim is None:
        # Another caller already claimed / completed this notification.
        logger.info(
            f"[variance-notify] PI={pi_id} — notification already claimed, skipping"
        )
        return {"status": "skipped", "reason": "already_dispatched"}

    recipients = await _resolve_recipients(db)
    if not recipients:
        # Roll the claim back to PENDING so a later admin bootstrap
        # can re-try.
        await db.payment_processing_reconciliation.update_one(
            {"payment_intent_id": pi_id},
            {"$set": {"variance_notification_status": "PENDING"}},
        )
        logger.warning(f"[variance-notify] PI={pi_id} — no admin recipients configured")
        return {"status": "no_recipients"}

    # Resolve dispatch surface.
    try:
        from services.emails._email_core import send_email
    except Exception as e:
        await db.payment_processing_reconciliation.update_one(
            {"payment_intent_id": pi_id},
            {"$set": {
                "variance_notification_status": "ERROR",
                "variance_notification_error": f"import_failure: {e}",
            }},
        )
        logger.warning(f"[variance-notify] canonical send_email import failed: {e}")
        return {"status": "error", "reason": "dispatcher_unavailable"}

    subject_en = COPY["en"]["subject"]
    subject_fr = COPY["fr"]["subject"]
    # The email is bilingual — EN block, then FR block, in one message.
    body_en = _render_html(doc, "en")
    body_fr = _render_html(doc, "fr")
    body = (
        body_en
        + '<hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0" />'
        + body_fr
    )
    subject = f"{subject_en} · {subject_fr}"

    sent_any = False
    delivery: List[Dict[str, Any]] = []
    for to in recipients:
        try:
            res = await send_email(
                to_email=to,
                subject=subject,
                html_content=body,
                categories=["iter482", "variance-notification"],
                custom_args={"payment_intent_id": pi_id, "kind": "variance"},
            )
            delivery.append({"to": to, "result": (res or {}).get("status", "sent")})
            if res and (res.get("status") in (None, "sent", "success", 200, "200", "ok")):
                sent_any = True
        except Exception as e:  # pragma: no cover — SendGrid outage
            logger.warning(f"[variance-notify] send failure to {to}: {e}")
            delivery.append({"to": to, "result": "error", "error": str(e)[:200]})

    final_status = "SENT" if sent_any else "ERROR"
    await db.payment_processing_reconciliation.update_one(
        {"payment_intent_id": pi_id},
        {"$set": {
            "variance_notification_status":  final_status,
            "variance_notification_sent_at": now_iso if sent_any else None,
            "variance_notification_recipients": recipients,
            "variance_notification_delivery": delivery,
        }},
    )
    logger.info(
        f"[variance-notify] PI={pi_id} status={final_status} recipients={len(recipients)}"
    )
    return {
        "status":          "sent" if sent_any else "error",
        "recipients":      recipients,
        "sent_at":         now_iso if sent_any else None,
        "notification_id": pi_id,
        "delivery":        delivery,
    }


__all__ = [
    "dispatch_variance_notification",
    "COPY",
    "_render_html",  # exposed for tests
    "_resolve_recipients",
]
