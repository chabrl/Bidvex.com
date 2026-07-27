"""
iter399 — Subscription trial-conversion reminder email.

Sends a bilingual (EN + FR) reminder to every user whose paid-subscription
free trial converts to paid billing in EXACTLY 3 days. Runs once per day.

Trigger rule:
  A user is eligible for one reminder iff:
    * `users.trial_redeemed_at` is set (they redeemed a 30-day trial via
      `services.trial_promo.mark_trial_redeemed`)
    * The computed `trial_end = trial_redeemed_at + TRIAL_DAYS` falls
      within the [now + 2.5d, now + 3.5d] window (24-hour tolerance so
      the daily cron never double-sends or skips).
    * `users.trial_reminder_sent_at` is not set (idempotency stamp).

Email contents (per user requirement):
  * Plan name (Premium / VIP / Partner Pro / Vehicle Dealer / …)
  * Amount that will be charged (from Stripe if a subscription exists,
    else from the plan doc `price_yearly` / `price_monthly`).
  * Charge date (the trial_end date).
  * Cancel link deep-linking `/settings?tab=subscription`.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger("trial_conversion_reminder")

TRIAL_DAYS = 30
REMINDER_LEAD_DAYS = 3
REMINDER_WINDOW_HOURS = 12  # ±12h around T-3 so the daily job never misses

FRONTEND_URL = (os.environ.get("FRONTEND_URL") or os.environ.get("REACT_APP_BACKEND_URL") or "https://www.bidvex.com").rstrip("/")

# Human-readable plan labels (EN, FR)
_PLAN_LABELS = {
    "premium":          ("Premium", "Premium"),
    "vip":              ("VIP Elite", "VIP Elite"),
    "vip_elite":        ("VIP Elite", "VIP Elite"),
    "partner":          ("Partner", "Partenaire"),
    "partner_pro":      ("Partner Pro", "Partenaire Pro"),
    "vehicle_dealer":   ("Vehicle Dealer", "Concessionnaire automobile"),
    "storage_facility": ("Storage Facility", "Entrepôt"),
}


def _plan_label(tier: str, lang: str) -> str:
    en, fr = _PLAN_LABELS.get((tier or "").lower(), (tier or "Plan", tier or "Forfait"))
    return fr if lang == "fr" else en


async def _resolve_charge_amount(db, user: dict, tier: str) -> tuple[Optional[float], str]:
    """Best-effort read of the amount + currency that will be charged
    when the trial converts. Prefers a live Stripe lookup; falls back to
    the plan doc yearly price then monthly price.

    Returns (amount, currency). amount may be None if nothing found.
    """
    # 1) Stripe subscription authoritative source
    sub_id = user.get("stripe_subscription_id") or user.get("partner_subscription_id")
    if sub_id:
        try:
            import stripe
            stripe.api_key = os.environ.get("STRIPE_API_KEY")
            sub = stripe.Subscription.retrieve(sub_id)
            items = (sub.get("items") or {}).get("data") or []
            if items:
                pr = items[0].get("price") or {}
                amt_cents = pr.get("unit_amount")
                cur = (pr.get("currency") or "cad").upper()
                if amt_cents:
                    return float(amt_cents) / 100.0, cur
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[trial_reminder] Stripe lookup failed for sub={sub_id}: {e}")

    # 2) Plan doc fallback
    try:
        plan = await db.subscription_plans.find_one(
            {"plan_id": tier}, {"_id": 0, "price_yearly": 1, "price_monthly": 1, "currency": 1},
        )
        if plan:
            py = float(plan.get("price_yearly") or 0)
            pm = float(plan.get("price_monthly") or 0)
            cur = (plan.get("currency") or "CAD").upper()
            if py > 0:
                return py, cur
            if pm > 0:
                return pm, cur
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[trial_reminder] plan lookup failed for tier={tier}: {e}")

    return None, "CAD"


def _format_amount(amount: Optional[float], currency: str, lang: str) -> str:
    if amount is None:
        return "—"
    if lang == "fr":
        # French: "200,00 $ CAD"
        return f"{amount:,.2f}".replace(",", " ").replace(".", ",") + f" $ {currency}"
    return f"${amount:,.2f} {currency}"


def _format_date(dt: datetime, lang: str) -> str:
    if lang == "fr":
        months = ["janvier", "février", "mars", "avril", "mai", "juin",
                  "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        return f"{dt.day} {months[dt.month - 1]} {dt.year}"
    return dt.strftime("%B %-d, %Y") if hasattr(dt, "strftime") else str(dt)


def _build_email(user_name: str, tier: str, amount: Optional[float], currency: str, charge_date: datetime, cancel_url: str) -> dict:
    """Return {'subject', 'html'} for a bilingual EN+FR trial reminder."""
    plan_en = _plan_label(tier, "en")
    plan_fr = _plan_label(tier, "fr")
    amt_en = _format_amount(amount, currency, "en")
    amt_fr = _format_amount(amount, currency, "fr")
    date_en = _format_date(charge_date, "en")
    date_fr = _format_date(charge_date, "fr")

    subject = f"Your BidVex {plan_en} trial ends in 3 days / Votre essai {plan_fr} se termine dans 3 jours"

    html = f"""
<!doctype html><html><body style="margin:0;padding:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#0f172a;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.06);overflow:hidden;">
        <tr><td style="padding:28px 32px;border-bottom:1px solid #e2e8f0;">
          <div style="font-size:20px;font-weight:700;color:#0055FF;">BidVex</div>
        </td></tr>

        <!-- ENGLISH -->
        <tr><td style="padding:28px 32px 8px 32px;">
          <h2 style="margin:0 0 8px;font-size:22px;color:#0f172a;">Your {plan_en} trial ends in 3 days</h2>
          <p style="margin:0 0 14px;color:#334155;line-height:1.5;">Hi {user_name},</p>
          <p style="margin:0 0 14px;color:#334155;line-height:1.5;">
            This is a friendly heads-up that your BidVex <strong>{plan_en}</strong> free trial ends on
            <strong>{date_en}</strong>. On that date your saved payment method will be charged
            <strong>{amt_en}</strong> and your subscription will continue.
          </p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 18px;border-collapse:collapse;">
            <tr><td style="padding:6px 12px;background:#f1f5f9;border-radius:8px;">
              <span style="color:#0f172a;font-weight:600;">Plan:</span> <span style="color:#334155;">{plan_en}</span> &nbsp;·&nbsp;
              <span style="color:#0f172a;font-weight:600;">Amount:</span> <span style="color:#334155;">{amt_en}</span> &nbsp;·&nbsp;
              <span style="color:#0f172a;font-weight:600;">Charge date:</span> <span style="color:#334155;">{date_en}</span>
            </td></tr>
          </table>
          <p style="margin:0 0 18px;color:#334155;line-height:1.5;">
            Not ready to continue?
            <a href="{cancel_url}" style="color:#0055FF;font-weight:600;text-decoration:underline;">Cancel your subscription</a>
            before {date_en} and you won't be charged.
          </p>
        </td></tr>

        <tr><td style="padding:0 32px;"><hr style="border:0;border-top:1px solid #e2e8f0;margin:8px 0;"></td></tr>

        <!-- FRANÇAIS -->
        <tr><td style="padding:8px 32px 28px 32px;">
          <h2 style="margin:0 0 8px;font-size:22px;color:#0f172a;">Votre essai {plan_fr} se termine dans 3 jours</h2>
          <p style="margin:0 0 14px;color:#334155;line-height:1.5;">Bonjour {user_name},</p>
          <p style="margin:0 0 14px;color:#334155;line-height:1.5;">
            Ceci est un rappel amical : votre essai gratuit BidVex <strong>{plan_fr}</strong> se termine le
            <strong>{date_fr}</strong>. À cette date, votre moyen de paiement sera débité de
            <strong>{amt_fr}</strong> et votre abonnement sera reconduit.
          </p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 18px;border-collapse:collapse;">
            <tr><td style="padding:6px 12px;background:#f1f5f9;border-radius:8px;">
              <span style="color:#0f172a;font-weight:600;">Forfait :</span> <span style="color:#334155;">{plan_fr}</span> &nbsp;·&nbsp;
              <span style="color:#0f172a;font-weight:600;">Montant :</span> <span style="color:#334155;">{amt_fr}</span> &nbsp;·&nbsp;
              <span style="color:#0f172a;font-weight:600;">Date de facturation :</span> <span style="color:#334155;">{date_fr}</span>
            </td></tr>
          </table>
          <p style="margin:0 0 8px;color:#334155;line-height:1.5;">
            Vous ne souhaitez pas continuer ?
            <a href="{cancel_url}" style="color:#0055FF;font-weight:600;text-decoration:underline;">Annulez votre abonnement</a>
            avant le {date_fr} et aucun montant ne sera prélevé.
          </p>
        </td></tr>

        <tr><td style="padding:14px 32px 24px;color:#94a3b8;font-size:12px;text-align:center;">
          © BidVex — Auction Marketplace · <a href="{FRONTEND_URL}" style="color:#94a3b8;">bidvex.com</a>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>
""".strip()

    return {"subject": subject, "html": html}


async def send_trial_conversion_reminders(db) -> dict:
    """Query users whose free trial converts to paid in ~3 days and send
    the bilingual reminder once. Runs from APScheduler (daily).

    Returns a summary `{scanned, matched, sent, failed}` for logging.
    """
    now = datetime.now(timezone.utc)
    target_end_low  = now + timedelta(days=REMINDER_LEAD_DAYS, hours=-REMINDER_WINDOW_HOURS)
    target_end_high = now + timedelta(days=REMINDER_LEAD_DAYS, hours=+REMINDER_WINDOW_HOURS)
    # trial_redeemed_at + TRIAL_DAYS ∈ [target_end_low, target_end_high]
    # ⇒ trial_redeemed_at ∈ [target_end_low - 30d, target_end_high - 30d]
    redeemed_low  = target_end_low  - timedelta(days=TRIAL_DAYS)
    redeemed_high = target_end_high - timedelta(days=TRIAL_DAYS)

    summary = {"scanned": 0, "matched": 0, "sent": 0, "failed": 0}

    try:
        # Use string ISO comparison (trial_redeemed_at is stored as ISO string).
        query = {
            "trial_redeemed_at": {
                "$gte": redeemed_low.isoformat(),
                "$lte": redeemed_high.isoformat(),
            },
            "$or": [
                {"trial_reminder_sent_at": {"$exists": False}},
                {"trial_reminder_sent_at": None},
                {"trial_reminder_sent_at": ""},
            ],
        }

        candidates = await db.users.find(query, {"_id": 0}).to_list(500)
        summary["scanned"] = len(candidates)

        for user in candidates:
            try:
                # If subscription is already cancelled or set to cancel at
                # period end, skip — the user has already opted out.
                if (user.get("cancel_at_period_end") is True
                        or (user.get("subscription_status") or "").lower() in ("canceled", "cancelled")):
                    continue

                tier = (user.get("trial_redeemed_tier")
                        or user.get("subscription_tier")
                        or "premium").lower()
                try:
                    trial_start = datetime.fromisoformat(user["trial_redeemed_at"].replace("Z", "+00:00"))
                except Exception:  # noqa: BLE001
                    continue
                if trial_start.tzinfo is None:
                    trial_start = trial_start.replace(tzinfo=timezone.utc)
                charge_date = trial_start + timedelta(days=TRIAL_DAYS)
                summary["matched"] += 1

                amount, currency = await _resolve_charge_amount(db, user, tier)
                cancel_url = f"{FRONTEND_URL}/settings?tab=subscription&utm_source=trial_reminder"
                email_body = _build_email(
                    user_name=user.get("name") or user.get("email", "there"),
                    tier=tier,
                    amount=amount,
                    currency=currency,
                    charge_date=charge_date,
                    cancel_url=cancel_url,
                )

                to_email = user.get("email")
                if not to_email:
                    continue

                try:
                    from services.email_service import get_email_service
                    svc = get_email_service()
                    if svc and svc.is_configured():
                        await svc.send_raw_html(to_email, email_body["subject"], email_body["html"])
                        # Idempotency stamp.
                        await db.users.update_one(
                            {"id": user["id"]},
                            {"$set": {
                                "trial_reminder_sent_at":      now.isoformat(),
                                "trial_reminder_sent_for_tier": tier,
                                "trial_reminder_charge_date":  charge_date.isoformat(),
                            }},
                        )
                        summary["sent"] += 1
                        logger.info(f"[trial_reminder] sent to {to_email} (tier={tier}, charge={charge_date.date()})")
                    else:
                        logger.warning(f"[trial_reminder] email service unavailable, skipping {to_email}")
                except Exception as em:
                    summary["failed"] += 1
                    logger.error(f"[trial_reminder] send failed for {to_email}: {em}")
            except Exception as inner:  # noqa: BLE001
                summary["failed"] += 1
                logger.warning(f"[trial_reminder] per-user error: {inner}")

    except Exception as e:  # noqa: BLE001
        logger.error(f"[trial_reminder] top-level error: {e}")

    logger.info(f"[trial_reminder] daily run complete: {summary}")
    return summary


__all__ = ["send_trial_conversion_reminders", "TRIAL_DAYS", "REMINDER_LEAD_DAYS"]
