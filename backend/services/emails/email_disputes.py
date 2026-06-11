"""
services/emails/email_disputes.py — iter300 P1 Dispute Resolution

Transactional emails for the dispute lifecycle (all bilingual,
STRICT Outlook-safe table layouts — no div/flex/grid/gradients):
  • Acknowledgement to filer + counterparty
  • Immediate admin alert
  • Resolution outcome to both parties
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

from services.emails._email_core import _base_template, send_email

logger = logging.getLogger(__name__)

FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://www.bidvex.com")

REASON_LABELS = {
    "item_not_as_described": ("Item not as described", "Article non conforme à la description"),
    "no_contact_from_seller": ("No contact from seller", "Aucun contact du vendeur"),
    "payment_issue": ("Payment issue", "Problème de paiement"),
    "other": ("Other", "Autre"),
}

OUTCOME_LABELS = {
    "release_to_seller": ("Resolved — funds released to the seller",
                          "Résolu — fonds libérés au vendeur"),
    "refund_buyer": ("Resolved — buyer refunded",
                     "Résolu — acheteur remboursé"),
}


def _bi(en_html: str, fr_html: str) -> str:
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="color:#334155;font-size:14px;line-height:1.6;">{en_html}</td></tr>
      <tr><td style="padding:12px 0;"><hr style="border:none;border-top:1px solid #e2e8f0;"/></td></tr>
      <tr><td style="color:#334155;font-size:14px;line-height:1.6;">{fr_html}</td></tr>
    </table>
    """


def _summary_box(listing_title: str, reason_en: str, reason_fr: str, details: str = "") -> str:
    details_row = (
        f"<p style='margin:4px 0;font-size:13px;color:#475569;'><strong>Details / Détails:</strong> {details[:500]}</p>"
        if details else ""
    )
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:14px 0;">
      <tr><td bgcolor="#fff7ed" style="background-color:#fff7ed;border:1px solid #fb923c;border-radius:10px;padding:14px;">
        <p style="margin:4px 0;font-size:13px;color:#7c2d12;"><strong>Listing / Annonce:</strong> {listing_title}</p>
        <p style="margin:4px 0;font-size:13px;color:#7c2d12;"><strong>Reason:</strong> {reason_en} · <strong>Raison :</strong> {reason_fr}</p>
        {details_row}
      </td></tr>
    </table>
    """


async def send_dispute_ack_email(*, to_email: str, to_name: str, listing_title: str,
                                 reason_key: str, details: str = "",
                                 is_filer: bool = True) -> Dict[str, Any]:
    r_en, r_fr = REASON_LABELS.get(reason_key, REASON_LABELS["other"])
    if is_filer:
        body = _bi(
            f"<p style='margin:0 0 8px 0;'>Hi <strong>{to_name}</strong>,</p>"
            f"<p style='margin:0;'>Your dispute has been received and is under review. "
            f"Our team will investigate and contact both parties with the outcome.</p>",
            f"<p style='margin:0 0 8px 0;'>Bonjour <strong>{to_name}</strong>,</p>"
            f"<p style='margin:0;'>Votre litige a été reçu et est en cours d'examen. "
            f"Notre équipe enquêtera et contactera les deux parties avec le résultat.</p>")
    else:
        body = _bi(
            f"<p style='margin:0 0 8px 0;'>Hi <strong>{to_name}</strong>,</p>"
            f"<p style='margin:0;'>A dispute has been filed on one of your transactions and is under review. "
            f"Our team may contact you for more information. No action is required right now.</p>",
            f"<p style='margin:0 0 8px 0;'>Bonjour <strong>{to_name}</strong>,</p>"
            f"<p style='margin:0;'>Un litige a été déposé sur l'une de vos transactions et est en cours d'examen. "
            f"Notre équipe pourrait vous contacter pour plus d'informations. Aucune action n'est requise pour le moment.</p>")
    content = body + _summary_box(listing_title, r_en, r_fr, details)
    return await send_email(
        to_email=to_email,
        subject=f"Dispute received — {listing_title} / Litige reçu",
        html_content=_base_template(content, title="Dispute Received"),
        categories=["dispute_ack"])


async def send_dispute_admin_alert_email(*, to_email: str, listing_title: str,
                                         filer_name: str, filer_role: str,
                                         reason_key: str, details: str,
                                         hammer_price: float, dispute_id: str) -> Dict[str, Any]:
    r_en, r_fr = REASON_LABELS.get(reason_key, REASON_LABELS["other"])
    url = f"{FRONTEND_URL}/admin?tab=disputed-settlements"
    content = f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td bgcolor="#fef2f2" style="background-color:#fef2f2;border:2px solid #dc2626;border-radius:10px;padding:14px;">
        <p style="margin:0;color:#991b1b;font-weight:700;">🚨 NEW DISPUTE FILED — action required</p>
        <p style="margin:6px 0 0 0;color:#7f1d1d;font-size:13px;">
          Filed by {filer_name} ({filer_role}) · Hammer CA${hammer_price:,.2f} · Dispute #{dispute_id[:8]}
        </p>
      </td></tr>
    </table>
    {_summary_box(listing_title, r_en, r_fr, details)}
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td align="center" style="padding:14px 0;">
        <a href="{url}" style="display:inline-block;padding:12px 28px;background-color:#dc2626;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;">
          Open dispute queue
        </a>
      </td></tr>
    </table>
    """
    return await send_email(
        to_email=to_email,
        subject=f"🚨 Dispute filed — {listing_title} (CA${hammer_price:,.2f})",
        html_content=_base_template(content, title="New Dispute"),
        categories=["dispute_admin_alert"])


async def send_dispute_resolved_email(*, to_email: str, to_name: str,
                                      listing_title: str, outcome: str,
                                      note: str = "") -> Dict[str, Any]:
    o_en, o_fr = OUTCOME_LABELS.get(outcome, ("Resolved", "Résolu"))
    note_block = ""
    if note:
        note_block = f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:12px 0;">
          <tr><td bgcolor="#f1f5f9" style="background-color:#f1f5f9;border-radius:8px;padding:12px;">
            <p style="margin:0;font-size:13px;color:#475569;"><strong>Resolution note / Note de résolution :</strong> {note[:600]}</p>
          </td></tr>
        </table>
        """
    content = f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td bgcolor="#ecfdf5" style="background-color:#ecfdf5;border:2px solid #16a34a;border-radius:10px;padding:14px;">
        <p style="margin:0;color:#166534;font-weight:700;">✅ {o_en}</p>
        <p style="margin:4px 0 0 0;color:#166534;font-size:13px;">{o_fr}</p>
      </td></tr>
      <tr><td style="height:14px;line-height:14px;font-size:1px;">&nbsp;</td></tr>
    </table>
    {_bi(
        f"<p style='margin:0 0 8px 0;'>Hi <strong>{to_name}</strong>,</p>"
        f"<p style='margin:0;'>The dispute on <strong>{listing_title}</strong> has been resolved by our team. "
        f"Outcome: <strong>{o_en}</strong>.</p>",
        f"<p style='margin:0 0 8px 0;'>Bonjour <strong>{to_name}</strong>,</p>"
        f"<p style='margin:0;'>Le litige concernant <strong>{listing_title}</strong> a été résolu par notre équipe. "
        f"Résultat : <strong>{o_fr}</strong>.</p>",
    )}
    {note_block}
    """
    return await send_email(
        to_email=to_email,
        subject=f"Dispute resolved — {listing_title} / Litige résolu",
        html_content=_base_template(content, title="Dispute Resolved"),
        categories=["dispute_resolved"])
