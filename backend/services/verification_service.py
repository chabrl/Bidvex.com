"""
iter208 — Verification Service

Central dispatcher for partner + dealer-license verification decisions.

Every Approval / Rejection produces THREE side-effects:
  1. Bilingual SendGrid email to the applicant (EN/FR — picks based on
     user.preferred_language, defaults to EN)
  2. `admin_notifications` row — visible on Admin Home
  3. `seller_notifications` row — visible on Seller Dashboard

The functions are best-effort (failures are logged, never raised) so the
admin decision endpoint never gets blocked on a transient SendGrid hiccup.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from services.email_notifications import (
    send_dealer_license_approved_email,
    send_dealer_license_rejected_email,
    send_email,
)

logger = logging.getLogger(__name__)


# ─── HTML chrome (matches iter195 dealer-license style) ────────────────────
def _bilingual_panel(title_en: str, title_fr: str, body_en: str, body_fr: str,
                     cta_url: str, cta_en: str, cta_fr: str) -> str:
    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:560px;margin:0 auto;color:#1e293b;">
      <div style="background:#2563eb;padding:24px 28px;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;margin:0;font-size:20px;">{title_en}</h1>
        <p style="color:#bfdbfe;margin:6px 0 0;font-size:13px;">{title_fr}</p>
      </div>
      <div style="padding:28px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;">
        <div style="font-size:14px;line-height:1.7;color:#334155;">{body_en}</div>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:18px 0;" />
        <div style="font-size:14px;line-height:1.7;color:#334155;">{body_fr}</div>
        <div style="margin:24px 0 8px;text-align:center;">
          <a href="{cta_url}" style="display:inline-block;background:#16a34a;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">{cta_en} · {cta_fr}</a>
        </div>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;" />
        <p style="color:#94a3b8;font-size:12px;">This is an automated message from BidVex Inc. · Message automatique de BidVex Inc.</p>
      </div>
    </div>
    """


# ─── Partner emails (NEW — iter208 bilingual rewrite) ──────────────────────
async def _send_partner_approved_email(user: dict, checkout_url: str | None = None) -> bool:
    if not user or not user.get("email"):
        return False
    company = (user.get("partner_company_name") or user.get("name") or "Partner").strip()
    payment_en = ""
    payment_fr = ""
    if checkout_url:
        payment_en = (
            f"<p style='margin-top:12px;'>To activate your account, complete the annual platform fee "
            f"of <strong>$100 CAD/year + applicable taxes</strong>:</p>"
            f"<p style='margin:8px 0;'><a href='{checkout_url}' style='color:#16a34a;font-weight:600;'>Pay $100 CAD/year → Activate Now</a></p>"
        )
        payment_fr = (
            f"<p style='margin-top:12px;'>Pour activer votre compte, complétez le paiement annuel "
            f"de <strong>100 $ CAD/an + taxes applicables</strong> :</p>"
            f"<p style='margin:8px 0;'><a href='{checkout_url}' style='color:#16a34a;font-weight:600;'>Payer 100 $ CAD/an → Activer maintenant</a></p>"
        )

    body_en = (
        f"Hi {company},<br/><br/>"
        f"Your partner/dealer status has been <strong style='color:#059669;'>verified</strong>. "
        f"You can now start listing vehicles."
        f"{payment_en}"
    )
    body_fr = (
        f"Bonjour {company},<br/><br/>"
        f"Votre statut de marchand/partenaire a été <strong style='color:#059669;'>vérifié</strong>. "
        f"Vous pouvez maintenant commencer à lister des véhicules."
        f"{payment_fr}"
    )

    return await send_email(
        to_email=user["email"],
        subject="✅ Partner Status Verified · Statut de partenaire vérifié",
        html_content=_bilingual_panel(
            title_en="Application Approved",
            title_fr="Demande approuvée",
            body_en=body_en,
            body_fr=body_fr,
            cta_url="https://bidvex.com/partner/dashboard",
            cta_en="Open Partner Dashboard",
            cta_fr="Ouvrir le tableau de bord",
        ),
    )


async def _send_partner_rejected_email(user: dict, reason: str = "") -> bool:
    if not user or not user.get("email"):
        return False
    company = (user.get("partner_company_name") or user.get("name") or "Applicant").strip()
    safe_reason = (reason or "").strip()
    reason_en = safe_reason or "Application does not meet requirements at this time."
    reason_fr = safe_reason or "La demande ne répond pas aux exigences pour le moment."

    body_en = (
        f"Hi {company},<br/><br/>"
        f"Your submission was <strong style='color:#dc2626;'>not approved</strong>.<br/>"
        f"<strong>Reason:</strong> <em>{reason_en}</em><br/><br/>"
        f"Please re-upload your documents addressing the reason above. Our team is happy to help if you have questions."
    )
    body_fr = (
        f"Bonjour {company},<br/><br/>"
        f"Votre soumission <strong style='color:#dc2626;'>n'a pas été approuvée</strong>.<br/>"
        f"<strong>Raison :</strong> <em>{reason_fr}</em><br/><br/>"
        f"Veuillez télécharger à nouveau vos documents en tenant compte de la raison ci-dessus. Notre équipe est disponible si vous avez des questions."
    )

    return await send_email(
        to_email=user["email"],
        subject="Partner Application — Action Required · Action requise",
        html_content=_bilingual_panel(
            title_en="Action Required",
            title_fr="Action requise",
            body_en=body_en,
            body_fr=body_fr,
            cta_url="https://bidvex.com/become-partner",
            cta_en="Re-upload Documents",
            cta_fr="Téléverser à nouveau",
        ),
    )


# ─── Audit/notification writers ────────────────────────────────────────────
async def _write_admin_notification(db, *, kind: str, target_user_id: str,
                                    title: str, body: str, admin_id: str | None,
                                    extra: dict | None = None) -> None:
    try:
        await db.admin_notifications.insert_one({
            "id": str(uuid.uuid4()),
            "kind": kind,
            "title": title,
            "body": body,
            "target_user_id": target_user_id,
            "admin_id": admin_id,
            "extra": extra or {},
            "resolved": False,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as exc:
        logger.warning(f"[iter208] admin_notifications insert failed: {exc}")


async def _write_seller_notification(db, *, kind: str, user_id: str,
                                     title_en: str, title_fr: str,
                                     body_en: str, body_fr: str,
                                     extra: dict | None = None) -> None:
    try:
        await db.seller_notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "kind": kind,
            "title_en": title_en,
            "title_fr": title_fr,
            "body_en": body_en,
            "body_fr": body_fr,
            "extra": extra or {},
            "read": False,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as exc:
        logger.warning(f"[iter208] seller_notifications insert failed: {exc}")


# ─── PUBLIC API ────────────────────────────────────────────────────────────
async def notify_partner_decision(db, *, user: dict, decision: str,
                                  admin_id: str | None,
                                  rejection_reason: str = "",
                                  checkout_url: str | None = None) -> dict:
    """
    Run all post-decision side effects for a PARTNER verify/reject.

    Returns:
        {"email_sent": bool, "admin_notif": bool, "seller_notif": bool}
    """
    result = {"email_sent": False, "admin_notif": False, "seller_notif": False}
    if decision not in ("approve", "reject"):
        return result
    if not user or not user.get("id"):
        return result

    # 1) Email
    try:
        if decision == "approve":
            result["email_sent"] = await _send_partner_approved_email(user, checkout_url=checkout_url)
        else:
            result["email_sent"] = await _send_partner_rejected_email(user, rejection_reason)
    except Exception as exc:
        logger.warning(f"[iter208] partner email dispatch failed: {exc}")

    # 2) admin_notifications
    decision_kind = "approved" if decision == "approve" else "rejected"
    title = (
        f"Partner {user.get('email', user['id'])} {decision_kind}"
    )
    body = (
        f"Company: {user.get('partner_company_name') or '-'} · Business Reg.: {user.get('partner_neq') or '-'}"
    )
    await _write_admin_notification(
        db,
        kind=f"partner_{decision_kind}",
        target_user_id=user["id"],
        title=title,
        body=body,
        admin_id=admin_id,
        extra={"reason": rejection_reason} if decision == "reject" else {},
    )
    result["admin_notif"] = True

    # 3) seller_notifications (visible to the partner on their dashboard)
    if decision == "approve":
        await _write_seller_notification(
            db,
            kind="partner_approved",
            user_id=user["id"],
            title_en="Partner status verified",
            title_fr="Statut de partenaire vérifié",
            body_en="Your dealer/partner status has been verified. You can now start listing vehicles.",
            body_fr="Votre statut de marchand/partenaire a été vérifié. Vous pouvez maintenant commencer à lister des véhicules.",
            extra={"checkout_url": checkout_url} if checkout_url else {},
        )
    else:
        body_en = f"Your submission was not approved. Reason: {rejection_reason or 'Please contact support.'} Please re-upload your documents."
        body_fr = f"Votre soumission n'a pas été approuvée. Raison : {rejection_reason or 'Veuillez contacter le support.'} Veuillez télécharger à nouveau vos documents."
        await _write_seller_notification(
            db,
            kind="partner_rejected",
            user_id=user["id"],
            title_en="Action Required — Partner Application",
            title_fr="Action requise — Demande de partenaire",
            body_en=body_en,
            body_fr=body_fr,
            extra={"reason": rejection_reason},
        )
    result["seller_notif"] = True
    return result


async def notify_dealer_license_decision(db, *, user: dict, license_doc: dict,
                                         decision: str, admin_id: str | None,
                                         rejection_reason: str = "") -> dict:
    """
    Run all post-decision side effects for a DEALER LICENSE verify/reject.

    Mirrors partner flow — bilingual email + admin_notifications + seller_notifications.
    """
    result = {"email_sent": False, "admin_notif": False, "seller_notif": False}
    if decision not in ("approve", "reject"):
        return result
    if not user or not user.get("id"):
        return result

    # 1) Email — reuse iter195 helpers
    try:
        if decision == "approve":
            result["email_sent"] = await send_dealer_license_approved_email(user, license_doc)
        else:
            result["email_sent"] = await send_dealer_license_rejected_email(user, license_doc, rejection_reason)
    except Exception as exc:
        logger.warning(f"[iter208] dealer-license email dispatch failed: {exc}")

    # 2) admin_notifications
    decision_kind = "approved" if decision == "approve" else "rejected"
    title = (
        f"Dealer licence {license_doc.get('license_number', '')[:24]} {decision_kind}"
    )
    body = (
        f"User: {user.get('email')} · Jurisdiction: {license_doc.get('jurisdiction', '-')}"
    )
    await _write_admin_notification(
        db,
        kind=f"dealer_license_{decision_kind}",
        target_user_id=user["id"],
        title=title,
        body=body,
        admin_id=admin_id,
        extra={"license_id": license_doc.get("id"), "reason": rejection_reason} if decision == "reject" else {"license_id": license_doc.get("id")},
    )
    result["admin_notif"] = True

    # 3) seller_notifications
    if decision == "approve":
        await _write_seller_notification(
            db,
            kind="dealer_license_approved",
            user_id=user["id"],
            title_en="Dealer licence verified",
            title_fr="Permis de concessionnaire vérifié",
            body_en="Your dealer/partner status has been verified. You can now start listing vehicles.",
            body_fr="Votre statut de marchand/partenaire a été vérifié. Vous pouvez maintenant commencer à lister des véhicules.",
            extra={"license_id": license_doc.get("id")},
        )
    else:
        body_en = f"Your submission was not approved. Reason: {rejection_reason or 'Please contact support.'} Please re-upload your documents."
        body_fr = f"Votre soumission n'a pas été approuvée. Raison : {rejection_reason or 'Veuillez contacter le support.'} Veuillez télécharger à nouveau vos documents."
        await _write_seller_notification(
            db,
            kind="dealer_license_rejected",
            user_id=user["id"],
            title_en="Action Required — Dealer Licence",
            title_fr="Action requise — Permis de concessionnaire",
            body_en=body_en,
            body_fr=body_fr,
            extra={"license_id": license_doc.get("id"), "reason": rejection_reason},
        )
    result["seller_notif"] = True
    return result
