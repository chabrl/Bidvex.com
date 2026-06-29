"""
BidVex Careers — applicant + admin notification emails.

Goes through `send_email()` so the canonical noreply@bidvex.com FROM is
preserved (this is a transactional email, NOT an Email Hub email).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _admin_notification_email() -> str:
    return (
        os.environ.get("ADMIN_NOTIFICATION_EMAIL")
        or os.environ.get("ADMIN_EMAIL")
        or "info@bidvex.com"
    )


def _bilingual_footer() -> str:
    return """
<hr style="margin:24px 0;border:none;border-top:1px solid #e2e8f0;" />
<p style="font-size:11px;color:#64748b;line-height:1.5;">
  BidVex Inc. · 761 Rue Chalifoux, Sherbrooke (Québec) J1G 0A8, Canada<br />
  EN — You received this email because you applied to a BidVex job opening. Replies go to
  <a href="mailto:support@bidvex.com" style="color:#64748b;">support@bidvex.com</a>.<br />
  FR — Vous recevez ce courriel parce que vous avez postulé à une offre BidVex. Les réponses sont acheminées à
  <a href="mailto:support@bidvex.com" style="color:#64748b;">support@bidvex.com</a>.
</p>
""".strip()


async def send_applicant_confirmation(
    *,
    to_email: str,
    first_name: str,
    job_title: str,
    locale: str = "en",
) -> Dict[str, Any]:
    """Bilingual-aware confirmation email to the applicant.
    FROM is the canonical noreply@bidvex.com (NOT Email Hub)."""
    fr = (locale or "en").lower().startswith("fr")
    subject = (
        "Candidature reçue — Carrières BidVex"
        if fr
        else "Application Received — BidVex Careers"
    )
    name = first_name or ("candidat" if fr else "applicant")
    heading = ("Merci, " + name) if fr else ("Thank you, " + name)
    body_para = (
        "Votre candidature pour le poste de <strong>" + job_title + "</strong> a bien été reçue. "
        "Notre équipe l\u2019examinera et vous contactera dans les 5 à 7 jours ouvrables."
    ) if fr else (
        "Your application for the <strong>" + job_title + "</strong> position has been received. "
        "Our team will review it and be in touch within 5\u20137 business days."
    )
    contact_para = (
        'Questions ? Écrivez-nous à <a href="mailto:support@bidvex.com" style="color:#0b1a30;">support@bidvex.com</a>.'
    ) if fr else (
        'Questions? Reach us at <a href="mailto:support@bidvex.com" style="color:#0b1a30;">support@bidvex.com</a>.'
    )
    footer = _bilingual_footer()
    body = (
        '<div style="font-family:Arial,sans-serif;color:#0b1a30;max-width:600px;margin:0 auto;padding:24px;">'
        f'<h1 style="color:#0b1a30;font-size:22px;">{heading}!</h1>'
        f'<p style="font-size:14px;line-height:1.55;">{body_para}</p>'
        f'<p style="font-size:14px;line-height:1.55;">{contact_para}</p>'
        f'{footer}'
        '</div>'
    )
    try:
        from services.emails._email_core import send_email
        return await send_email(
            to_email=to_email,
            subject=subject,
            html_content=body,
            reply_to="support@bidvex.com",
            reply_to_name="BidVex Support",
            categories=["careers", "application_confirmation"],
        )
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[careers] applicant confirmation failed: {e}")
        return {"status": "failed", "error": str(e)[:200]}


async def send_admin_new_applicant_notification(
    *,
    applicant: Dict[str, Any],
    job_title: str,
    admin_panel_link: Optional[str] = None,
) -> Dict[str, Any]:
    """Notify admin inbox that a new application landed."""
    to_email = _admin_notification_email()
    subj = f"New Application: {job_title} — {applicant.get('first_name','?')} {applicant.get('last_name','?')}"
    link_html = (
        f'<p><a href="{admin_panel_link}" style="color:#0b1a30;font-weight:600;">'
        f"Open in admin panel →</a></p>"
        if admin_panel_link
        else ""
    )
    body = f"""
<div style="font-family:Arial,sans-serif;color:#0b1a30;max-width:640px;margin:0 auto;padding:24px;">
  <h2 style="font-size:18px;">New BidVex Careers application</h2>
  <table style="border-collapse:collapse;font-size:13px;line-height:1.5;">
    <tr><td style="padding:4px 12px 4px 0;color:#475569;">Job:</td><td><strong>{job_title}</strong></td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#475569;">Name:</td><td>{applicant.get('first_name','')} {applicant.get('last_name','')}</td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#475569;">Email:</td><td>{applicant.get('email','')}</td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#475569;">Phone:</td><td>{applicant.get('phone','')}</td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#475569;">Province:</td><td>{applicant.get('province','')}</td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#475569;">Applied at:</td><td>{applicant.get('applied_at','')}</td></tr>
  </table>
  {link_html}
</div>
""".strip()
    try:
        from services.emails._email_core import send_email
        return await send_email(
            to_email=to_email,
            subject=subj,
            html_content=body,
            categories=["careers", "admin_new_applicant"],
        )
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[careers] admin notification failed: {e}")
        return {"status": "failed", "error": str(e)[:200]}


__all__ = [
    "send_applicant_confirmation",
    "send_admin_new_applicant_notification",
]
