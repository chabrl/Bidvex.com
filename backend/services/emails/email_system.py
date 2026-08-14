"""services/emails/email_system.py — iter295 P2

Cross-cutting / system-level email senders. Function bodies
physically migrated from services/email_notifications.py."""
import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from services.emails._email_core import (
    SENDGRID_API_KEY, SENDGRID_AVAILABLE, sg, FRONTEND_URL,
    FROM_EMAIL, FROM_NAME,
    TRANSACTIONAL_FROM_EMAIL, TRANSACTIONAL_FROM_NAME,
    TRANSACTIONAL_REPLY_TO, TRANSACTIONAL_REPLY_TO_NAME,
    B2B_PARTNER_FROM_EMAIL, B2B_PARTNER_FROM_NAME,
    B2B_PARTNER_REPLY_TO, B2B_PARTNER_REPLY_TO_NAME,
    MARKETING_REPLY_TO, MARKETING_REPLY_TO_NAME,
    _format_currency, _format_date, _format_currency_fr,
    _detect_language, _section_label, _base_template, _storage_panel,
    send_email, send_unified_email, _send_via_unified,
)
import os as _os

logger = logging.getLogger(__name__)


async def send_welcome_email(user_email: str, user_name: str) -> Dict[str, Any]:
    """
    Send premium bilingual welcome email — BidVex Ecosystem.
    French (top) → English (bottom), separated by grey divider.
    High-end branded HTML with hero image, two-column advantage grid, CTA.
    """
    logger.info(f"[EMAIL_DEBUG] Triggering Welcome Email for: {user_email} | User: {user_name}")

    HERO_IMG = "https://images.unsplash.com/photo-1774867559682-e856ab83a7db?w=1200&q=80&auto=format"
    MARKETPLACE_URL = "https://bidvex.com/marketplace"
    PRIVACY_URL = "https://bidvex.com/legal"
    TERMS_URL = "https://bidvex.com/legal"

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bienvenue chez BidVex / Welcome to BidVex</title>
</head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;background-color:#f0f4f8;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f0f4f8;padding:32px 16px;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,0.08);">

  <!-- Logo Header -->
  <tr>
    <td style="background-color:#1e40af;padding:28px 32px;text-align:center;">
      <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:800;letter-spacing:-0.5px;">
        BidVex
      </h1>
      <p style="margin:6px 0 0;color:#93c5fd;font-size:12px;text-transform:uppercase;letter-spacing:2px;font-weight:600;">
        Auction Ecosystem / Écosystème d'enchères
      </p>
    </td>
  </tr>

  <!-- Hero Image -->
  <tr>
    <td>
      <img src="{HERO_IMG}" alt="BidVex All-in-One Marketplace — Heavy equipment, vehicles, and industrial assets / Marché tout-en-un BidVex — Équipement lourd, véhicules et actifs industriels" width="640" style="display:block;width:100%;height:auto;max-height:260px;object-fit:cover;" />
    </td>
  </tr>

  <!-- ═══════ FRENCH SECTION ═══════ -->
  <tr>
    <td style="padding:36px 32px 24px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="border-left:4px solid #2563eb;padding-left:16px;">
            <p style="margin:0 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:#2563eb;font-weight:700;">Français</p>
            <h2 style="margin:0;color:#0f172a;font-size:24px;font-weight:700;">Bienvenue chez BidVex, {user_name} !</h2>
          </td>
        </tr>
      </table>
      <p style="color:#475569;font-size:15px;line-height:1.7;margin:18px 0;">
        Vous venez de rejoindre la plateforme &laquo; tout-en-un &raquo; la plus avancée en Amérique du Nord. Que vous cherchiez une flotte de camions, une pièce de collection unique ou que vous souhaitiez liquider un entrepôt complet d'équipement industriel, BidVex est conçu pour tout gérer.
      </p>

      <!-- Advantage Grid FR -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 0;">
        <tr>
          <td width="50%" valign="top" style="padding:8px 12px 8px 0;">
            <table cellpadding="0" cellspacing="0" style="background:#eff6ff;border-radius:10px;padding:16px;width:100%;">
              <tr>
                <td style="padding:0 0 8px;font-size:22px;">&#128722;</td>
              </tr>
              <tr>
                <td style="font-size:13px;font-weight:700;color:#1e3a5f;">Marché tout-en-un</td>
              </tr>
              <tr>
                <td style="font-size:12px;color:#475569;line-height:1.5;padding-top:4px;">Des véhicules et de la machinerie lourde aux lots d'articles multiples.</td>
              </tr>
            </table>
          </td>
          <td width="50%" valign="top" style="padding:8px 0 8px 12px;">
            <table cellpadding="0" cellspacing="0" style="background:#eff6ff;border-radius:10px;padding:16px;width:100%;">
              <tr>
                <td style="padding:0 0 8px;font-size:22px;">&#129302;</td>
              </tr>
              <tr>
                <td style="font-size:13px;font-weight:700;color:#1e3a5f;">Outils propulsés par l'IA</td>
              </tr>
              <tr>
                <td style="font-size:12px;color:#475569;line-height:1.5;padding-top:4px;">Notre concierge intelligent est prêt à vous aider 24/7.</td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td colspan="2" valign="top" style="padding:8px 0 0;">
            <table cellpadding="0" cellspacing="0" style="background:#eff6ff;border-radius:10px;padding:16px;width:100%;">
              <tr>
                <td style="padding:0 0 8px;font-size:22px;">&#127760;</td>
              </tr>
              <tr>
                <td style="font-size:13px;font-weight:700;color:#1e3a5f;">Bilingue et transfrontalier</td>
              </tr>
              <tr>
                <td style="font-size:12px;color:#475569;line-height:1.5;padding-top:4px;">Achetez ou vendez partout au Canada et aux États-Unis.</td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ═══════ DIVIDER ═══════ -->
  <tr>
    <td style="padding:0 32px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="border-top:2px solid #e2e8f0;height:1px;font-size:0;line-height:0;">&nbsp;</td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ═══════ ENGLISH SECTION ═══════ -->
  <tr>
    <td style="padding:24px 32px 36px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="border-left:4px solid #2563eb;padding-left:16px;">
            <p style="margin:0 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:#2563eb;font-weight:700;">English</p>
            <h2 style="margin:0;color:#0f172a;font-size:24px;font-weight:700;">Welcome to BidVex, {user_name}!</h2>
          </td>
        </tr>
      </table>
      <p style="color:#475569;font-size:15px;line-height:1.7;margin:18px 0;">
        You've just joined North America's most advanced all-in-one marketplace. Whether you are looking for a fleet of trucks, a single rare collectible, or liquidating an entire warehouse of industrial equipment, BidVex is built to handle it all.
      </p>

      <!-- Advantage Grid EN -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 0;">
        <tr>
          <td width="50%" valign="top" style="padding:8px 12px 8px 0;">
            <table cellpadding="0" cellspacing="0" style="background:#eff6ff;border-radius:10px;padding:16px;width:100%;">
              <tr>
                <td style="padding:0 0 8px;font-size:22px;">&#128722;</td>
              </tr>
              <tr>
                <td style="font-size:13px;font-weight:700;color:#1e3a5f;">All-In-One Marketplace</td>
              </tr>
              <tr>
                <td style="font-size:12px;color:#475569;line-height:1.5;padding-top:4px;">From vehicles and heavy machinery to multi-item lots.</td>
              </tr>
            </table>
          </td>
          <td width="50%" valign="top" style="padding:8px 0 8px 12px;">
            <table cellpadding="0" cellspacing="0" style="background:#eff6ff;border-radius:10px;padding:16px;width:100%;">
              <tr>
                <td style="padding:0 0 8px;font-size:22px;">&#129302;</td>
              </tr>
              <tr>
                <td style="font-size:13px;font-weight:700;color:#1e3a5f;">AI-Powered Tools</td>
              </tr>
              <tr>
                <td style="font-size:12px;color:#475569;line-height:1.5;padding-top:4px;">Our intelligent concierge is ready to help you 24/7.</td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td colspan="2" valign="top" style="padding:8px 0 0;">
            <table cellpadding="0" cellspacing="0" style="background:#eff6ff;border-radius:10px;padding:16px;width:100%;">
              <tr>
                <td style="padding:0 0 8px;font-size:22px;">&#127760;</td>
              </tr>
              <tr>
                <td style="font-size:13px;font-weight:700;color:#1e3a5f;">Bilingual &amp; Cross-Border</td>
              </tr>
              <tr>
                <td style="font-size:12px;color:#475569;line-height:1.5;padding-top:4px;">Seamlessly buy or sell across Canada and the US.</td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ═══════ CTA BUTTON ═══════ -->
  <tr>
    <td style="padding:0 32px 40px;text-align:center;">
      <table cellpadding="0" cellspacing="0" align="center">
        <tr>
          <td style="background-color:#1e40af;border-radius:12px;padding:18px 48px;">
            <a href="{MARKETPLACE_URL}" style="color:#ffffff;text-decoration:none;font-size:16px;font-weight:700;display:inline-block;letter-spacing:0.3px;">
              Explorer le marché / Explore the Marketplace
            </a>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ═══════ FOOTER ═══════ -->
  <tr>
    <td style="background-color:#f8fafc;padding:24px 32px;border-top:1px solid #e2e8f0;border-radius:0 0 16px 16px;">
      <p style="margin:0;font-size:12px;color:#94a3b8;text-align:center;line-height:1.6;">
        &copy; 2026 BidVex Inc. Based in Sherbrooke, QC.<br/>
        <a href="{PRIVACY_URL}" style="color:#2563eb;text-decoration:none;">Privacy Policy</a> &nbsp;|&nbsp;
        <a href="{TERMS_URL}" style="color:#2563eb;text-decoration:none;">Terms of Service</a>
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""

    result = await _send_via_unified(
        to_email=user_email,
        subject="Welcome to the BidVex Ecosystem! / Bienvenue dans l'écosystème BidVex !",
        html_content=html
    )

    logger.info(f"[EMAIL_DEBUG] Welcome Email result for {user_email}: {result}")
    return result


async def send_invoice_created_email(invoice: Dict[str, Any]) -> Dict[str, Any]:
    """Send email when a new invoice is generated. iter249 — language-aware."""
    lang = _detect_language(invoice)
    is_fr = lang == "fr"
    title = "Facture générée" if is_fr else "Invoice Generated"
    intro = (
        "Félicitations ! Votre enchère gagnante a été traitée. Voici les détails de votre facture :"
        if is_fr else
        "Congratulations! Your winning bid has been processed. Here are your invoice details:"
    )
    lbl_inv = "Facture nº :" if is_fr else "Invoice #:"
    lbl_veh = "Véhicule :" if is_fr else "Vehicle:"
    lbl_hammer = "Prix marteau :" if is_fr else "Hammer Price:"
    lbl_total = "Total à payer :" if is_fr else "Total Due:"
    lbl_due = "Échéance :" if is_fr else "Due Date:"
    cta = "Voir et payer la facture" if is_fr else "View & Pay Invoice"
    fine_print = (
        "Le paiement est dû dans les 14 jours. Tout retard peut entraîner une pénalité mensuelle de 2 %."
        if is_fr else
        "Payment is due within 14 days. Late payments may incur a 2% monthly penalty."
    )
    fmt_money = _format_currency_fr if is_fr else _format_currency

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #1e293b;">{title}</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        {intro}
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #f8fafc; border-radius: 8px; padding: 20px;">
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_inv}</strong></td>
                <td style="padding: 8px 0; text-align: right;">{invoice.get('invoice_number', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_veh}</strong></td>
                <td style="padding: 8px 0; text-align: right;">{invoice.get('vehicle_title', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_hammer}</strong></td>
                <td style="padding: 8px 0; text-align: right;">{fmt_money(invoice.get('hammer_price', 0))}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_total}</strong></td>
                <td style="padding: 8px 0; text-align: right; font-size: 18px; color: #2563eb; font-weight: bold;">
                    {fmt_money(invoice.get('total_amount', 0))}
                </td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_due}</strong></td>
                <td style="padding: 8px 0; text-align: right; color: #f59e0b;">
                    {_format_date(invoice.get('due_at', invoice.get('payment_deadline')))}
                </td>
            </tr>
        </table>
    </td></tr></table>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #2563eb; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/invoices/{invoice.get('id')}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">{cta}</a>
            </td>
        </tr>
    </table>
    
    <p style="color: #64748b; font-size: 13px; line-height: 1.6;">
        {fine_print}
    </p>
    """
    subject = (
        f"Facture nº{invoice.get('invoice_number')} — {invoice.get('vehicle_title')}"
        if is_fr else
        f"Invoice #{invoice.get('invoice_number')} - {invoice.get('vehicle_title')}"
    )
    return await _send_via_unified(
        to_email=invoice.get('buyer_email'),
        subject=subject,
        html_content=_base_template(content, title)
    )


async def send_payment_confirmation_email(invoice: Dict[str, Any]) -> Dict[str, Any]:
    """Send email when payment is received. iter249 — language-aware."""
    lang = _detect_language(invoice)
    is_fr = lang == "fr"
    title = "✓ Paiement reçu" if is_fr else "✓ Payment Received"
    intro = (
        "Merci ! Votre paiement a été traité avec succès."
        if is_fr else
        "Thank you! Your payment has been successfully processed."
    )
    confirmed_lbl = "Paiement confirmé" if is_fr else "Payment Confirmed"
    lbl_inv = "Facture nº :" if is_fr else "Invoice #:"
    lbl_veh = "Véhicule :" if is_fr else "Vehicle:"
    lbl_date = "Date de paiement :" if is_fr else "Payment Date:"
    seller_note = (
        "Le vendeur a été notifié et coordonnera la prise en charge ou la livraison du véhicule avec vous."
        if is_fr else
        "The seller has been notified and will coordinate vehicle pickup/delivery with you."
    )
    cta = "Voir le reçu" if is_fr else "View Receipt"
    fmt_money = _format_currency_fr if is_fr else _format_currency

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">{title}</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        {intro}
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #d1fae5; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">        <p style="margin: 0; color: #065f46; font-size: 14px;">{confirmed_lbl}</p>
        <p style="margin: 10px 0 0 0; color: #065f46; font-size: 28px; font-weight: bold;">
            {fmt_money(invoice.get('paid_amount', invoice.get('total_amount', 0)))}
        </p></td></tr></table>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #f8fafc; border-radius: 8px; padding: 20px;">
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_inv}</strong></td>
                <td style="padding: 8px 0; text-align: right;">{invoice.get('invoice_number', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_veh}</strong></td>
                <td style="padding: 8px 0; text-align: right;">{invoice.get('vehicle_title', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_date}</strong></td>
                <td style="padding: 8px 0; text-align: right;">{_format_date(invoice.get('paid_at', datetime.now(timezone.utc)))}</td>
            </tr>
        </table>
    </td></tr></table>
    
    <p style="color: #475569; line-height: 1.6;">
        {seller_note}
    </p>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #f1f5f9; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/invoices/{invoice.get('id')}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">{cta}</a>
            </td>
        </tr>
    </table>
    """
    subject = (
        f"Paiement confirmé — Facture nº{invoice.get('invoice_number')}"
        if is_fr else
        f"Payment Confirmed - Invoice #{invoice.get('invoice_number')}"
    )
    return await _send_via_unified(
        to_email=invoice.get('buyer_email'),
        subject=subject,
        html_content=_base_template(content, title)
    )


async def send_invoice_overdue_email(invoice: Dict[str, Any], days_overdue: int) -> Dict[str, Any]:
    """Send reminder for overdue invoice. iter482 P2 fix — language-aware EN/FR."""
    lang = _detect_language(invoice)
    is_fr = lang == "fr"
    fmt_money = _format_currency_fr if is_fr else _format_currency

    title = "⚠️ Paiement en retard" if is_fr else "⚠️ Payment Overdue"
    intro = (
        f"Le paiement de votre facture est maintenant <strong>en retard de {days_overdue} jour(s)</strong>. "
        "Veuillez effectuer le règlement immédiatement pour éviter des pénalités supplémentaires."
        if is_fr else
        f"Your invoice payment is now <strong>{days_overdue} days overdue</strong>. "
        "Please make payment immediately to avoid additional penalties."
    )
    lbl_inv = "Facture nº :" if is_fr else "Invoice #:"
    lbl_original = "Montant initial :" if is_fr else "Original Amount:"
    lbl_penalty = "Pénalité de retard :" if is_fr else "Late Penalty:"
    lbl_total = "Total à payer maintenant :" if is_fr else "Total Due Now:"
    warn = (
        "<strong>Avertissement :</strong> Le non-paiement continu peut entraîner la suspension "
        "du compte et des actions de recouvrement supplémentaires."
        if is_fr else
        "<strong>Warning:</strong> Continued non-payment may result in account suspension and "
        "additional collection actions."
    )
    cta = "Payer maintenant" if is_fr else "Pay Now"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #dc2626;">{title}</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        {intro}
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 20px;">
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_inv}</strong></td>
                <td style="padding: 8px 0; text-align: right;">{invoice.get('invoice_number', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_original}</strong></td>
                <td style="padding: 8px 0; text-align: right;">{fmt_money(invoice.get('total_amount', 0))}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_penalty}</strong></td>
                <td style="padding: 8px 0; text-align: right; color: #dc2626;">
                    +{fmt_money(invoice.get('penalty_amount', 0))}
                </td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_total}</strong></td>
                <td style="padding: 8px 0; text-align: right; font-size: 18px; color: #dc2626; font-weight: bold;">
                    {fmt_money(invoice.get('total_amount', 0) + invoice.get('penalty_amount', 0))}
                </td>
            </tr>
        </table>
    </td></tr></table>
    
    <p style="color: #991b1b; font-size: 13px; line-height: 1.6; background-color: #fef2f2; padding: 15px; border-radius: 8px;">
        {warn}
    </p>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #dc2626; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/invoices/{invoice.get('id')}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">{cta}</a>
            </td>
        </tr>
    </table>
    """
    subject = (
        f"⚠️ EN RETARD : Facture nº{invoice.get('invoice_number')} — action requise"
        if is_fr else
        f"⚠️ OVERDUE: Invoice #{invoice.get('invoice_number')} - Action Required"
    )
    return await _send_via_unified(
        to_email=invoice.get('buyer_email'),
        subject=subject,
        html_content=_base_template(content, "Paiement en retard" if is_fr else "Payment Overdue")
    )


async def send_document_approved_email(
    user_email: str,
    user_name: str,
    document_type: str
) -> Dict[str, Any]:
    """Send email when a document is approved"""
    doc_name = document_type.replace('_', ' ').title()
    
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">✓ Document Approved</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Hi {user_name},
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Great news! Your <strong>{doc_name}</strong> document has been reviewed and approved.
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #d1fae5; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">        <p style="margin: 0; color: #065f46; font-size: 18px; font-weight: bold;">
            ✓ {doc_name} Verified
        </p></td></tr></table>
    
    <p style="color: #475569; line-height: 1.6;">
        You can now continue with your seller verification process. Once all required documents 
        are approved, you'll be able to list vehicles for auction.
    </p>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #10b981; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/seller/register" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">View Verification Status</a>
            </td>
        </tr>
    </table>
    """
    
    return await _send_via_unified(
        to_email=user_email,
        subject=f"✓ Document Approved: {doc_name}",
        html_content=_base_template(content, "Document Approved")
    )


async def send_document_rejected_email(
    user_email: str,
    user_name: str,
    document_type: str,
    rejection_reason: str
) -> Dict[str, Any]:
    """Send email when a document is rejected"""
    doc_name = document_type.replace('_', ' ').title()
    
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #f59e0b;">Document Needs Attention</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Hi {user_name},
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Unfortunately, your <strong>{doc_name}</strong> document could not be approved.
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 20px; margin: 20px 0;">        <p style="margin: 0 0 10px 0; color: #92400e; font-weight: bold;">Reason:</p>
        <p style="margin: 0; color: #92400e;">{rejection_reason}</p></td></tr></table>
    
    <p style="color: #475569; line-height: 1.6;">
        Please upload a new document that addresses the issue above. Make sure your document:
    </p>
    
    <ul style="color: #475569; line-height: 1.8;">
        <li>Is clearly legible and not blurry</li>
        <li>Shows all required information</li>
        <li>Is current and not expired</li>
        <li>Is in PDF, JPG, or PNG format</li>
    </ul>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #f59e0b; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/seller/register" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">Re-upload Document</a>
            </td>
        </tr>
    </table>
    """
    
    return await _send_via_unified(
        to_email=user_email,
        subject=f"Action Required: {doc_name} - Re-upload Needed",
        html_content=_base_template(content, "Document Needs Attention")
    )


async def send_seller_approved_email(
    user_email: str,
    user_name: str,
    seller_type: str
) -> Dict[str, Any]:
    """Send email when seller account is fully approved"""
    seller_type_name = seller_type.replace('_', ' ').title()
    
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">🎉 Congratulations!</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Hi {user_name},
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Your <strong>{seller_type_name}</strong> seller account has been fully verified and approved!
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #d1fae5; border-radius: 8px; padding: 30px; margin: 20px 0; text-align: center;">        <p style="margin: 0; color: #065f46; font-size: 14px;">Account Status</p>
        <p style="margin: 10px 0 0 0; color: #065f46; font-size: 24px; font-weight: bold;">
            ✓ APPROVED
        </p></td></tr></table>
    
    <p style="color: #475569; line-height: 1.6;">
        You can now:
    </p>
    
    <ul style="color: #475569; line-height: 1.8;">
        <li>List vehicles for auction</li>
        <li>Set your own starting prices and reserves</li>
        <li>Track bids in real-time</li>
        <li>Receive payments directly to your account</li>
    </ul>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #10b981; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/create" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">List Your First Vehicle</a>
            </td>
        </tr>
    </table>
    """
    
    return await _send_via_unified(
        to_email=user_email,
        subject="🎉 Your Seller Account is Approved!",
        html_content=_base_template(content, "Seller Account Approved")
    )


async def send_subscription_reminder_email(
    user_email: str,
    user_name: str,
    plan: str,
    days_remaining: int,
    end_date: str,
    lang: Optional[str] = None,
) -> Dict[str, Any]:
    """Send reminder email 3 days before subscription expires. iter482 P2 fix — language-aware EN/FR."""
    if lang is None:
        lang = "en"
    is_fr = str(lang).lower().startswith("fr")
    plan_name = plan.title()

    title = "⏰ Abonnement bientôt expiré" if is_fr else "⏰ Subscription Expiring Soon"
    greet = f"Bonjour {user_name}," if is_fr else f"Hi {user_name},"
    intro = (
        f"Votre abonnement <strong>{plan_name}</strong> expirera dans <strong>{days_remaining} jour(s)</strong>."
        if is_fr else
        f"Your <strong>{plan_name}</strong> subscription will expire in <strong>{days_remaining} days</strong>."
    )
    lbl_current = "Forfait actuel :" if is_fr else "Current Plan:"
    lbl_exp = "Expire le :" if is_fr else "Expires On:"
    lbl_days = "Jours restants :" if is_fr else "Days Remaining:"
    benefits_note = (
        f"Pour continuer à profiter des avantages {plan_name} (frais réduits, soutien prioritaire, etc.), "
        "veuillez contacter le service à la clientèle pour renouveler votre abonnement."
        if is_fr else
        f"To continue enjoying {plan_name} benefits (reduced fees, priority support, and more), "
        "please contact support to renew your subscription."
    )
    downgrade_note = (
        "Si votre abonnement expire, votre compte sera automatiquement rétrogradé au forfait Gratuit."
        if is_fr else
        "If your subscription expires, your account will be downgraded to the Free plan automatically."
    )
    cta = "Voir mon abonnement" if is_fr else "View Subscription"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #f59e0b;">{title}</h2>

    <p style="color: #475569; line-height: 1.6;">
        {greet}
    </p>

    <p style="color: #475569; line-height: 1.6;">
        {intro}
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 20px;">
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_current}</strong></td>
                <td style="padding: 8px 0; text-align: right;">{plan_name}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_exp}</strong></td>
                <td style="padding: 8px 0; text-align: right;">{end_date}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_days}</strong></td>
                <td style="padding: 8px 0; text-align: right; color: #d97706; font-weight: bold;">{days_remaining}</td>
            </tr>
        </table>
    </td></tr></table>

    <p style="color: #475569; line-height: 1.6;">
        {benefits_note}
    </p>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #f59e0b; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/settings/subscription" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">{cta}</a>
            </td>
        </tr>
    </table>

    <p style="color: #64748b; font-size: 13px; line-height: 1.6;">
        {downgrade_note}
    </p>
    """
    subject = (
        f"⏰ Votre abonnement {plan_name} expire dans {days_remaining} jour(s)"
        if is_fr else
        f"⏰ Your {plan_name} Subscription Expires in {days_remaining} Days"
    )
    return await _send_via_unified(
        to_email=user_email,
        subject=subject,
        html_content=_base_template(content, "Rappel d'abonnement" if is_fr else "Subscription Reminder")
    )


async def send_subscription_expired_email(
    user_email: str,
    user_name: str,
    previous_plan: str,
    lang: Optional[str] = None,
) -> Dict[str, Any]:
    """Send confirmation email when subscription expires. iter482 P2 fix — language-aware EN/FR."""
    if lang is None:
        lang = "en"
    is_fr = str(lang).lower().startswith("fr")
    plan_name = previous_plan.title()

    title = "Abonnement expiré" if is_fr else "Subscription Expired"
    greet = f"Bonjour {user_name}," if is_fr else f"Hi {user_name},"
    intro = (
        f"Votre abonnement <strong>{plan_name}</strong> est expiré. "
        f"Votre compte a été rétrogradé au forfait <strong>Gratuit</strong>."
        if is_fr else
        f"Your <strong>{plan_name}</strong> subscription has expired. Your account has been "
        f"downgraded to the <strong>Free</strong> plan."
    )
    changes_title = "Ce qui a changé :" if is_fr else "What's Changed:"
    changes = (
        [
            "Limite mensuelle d'annonces réduite",
            "Remises sur la prime acheteur retirées",
            "Remises sur la commission vendeur retirées",
            "Soutien prioritaire non disponible",
        ] if is_fr else [
            "Monthly listing limit reduced",
            "Buyer premium discounts removed",
            "Seller commission discounts removed",
            "Priority support no longer available",
        ]
    )
    outro = (
        f"Pas d'inquiétude ! Vos annonces existantes restent actives. "
        f"Pour retrouver vos avantages {plan_name}, veuillez contacter le service à la clientèle "
        f"pour renouveler votre abonnement."
        if is_fr else
        f"Don't worry! Your existing listings will remain active. To regain your {plan_name} benefits, "
        f"please contact support to renew your subscription."
    )
    thanks = (
        f"Merci d'avoir été membre {plan_name}. Au plaisir de vous revoir bientôt !"
        if is_fr else
        f"Thank you for being a {plan_name} member. We hope to see you back soon!"
    )
    cta = "Renouveler mon abonnement" if is_fr else "Renew Subscription"
    changes_html = "".join(f"<li>{c}</li>" for c in changes)

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #64748b;">{title}</h2>

    <p style="color: #475569; line-height: 1.6;">
        {greet}
    </p>

    <p style="color: #475569; line-height: 1.6;">
        {intro}
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #f1f5f9; border-radius: 8px; padding: 20px; margin: 20px 0;">        <h4 style="margin: 0 0 15px 0; color: #334155;">{changes_title}</h4>
        <ul style="margin: 0; padding: 0 0 0 20px; color: #475569; line-height: 1.8;">
            {changes_html}
        </ul></td></tr></table>

    <p style="color: #475569; line-height: 1.6;">
        {outro}
    </p>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #1e3a5f; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/settings/subscription" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">{cta}</a>
            </td>
        </tr>
    </table>

    <p style="color: #64748b; font-size: 13px; line-height: 1.6;">
        {thanks}
    </p>
    """
    subject = (
        f"Votre abonnement {plan_name} est expiré"
        if is_fr else
        f"Your {plan_name} Subscription Has Expired"
    )
    return await _send_via_unified(
        to_email=user_email,
        subject=subject,
        html_content=_base_template(content, title)
    )


async def send_subscription_upgraded_email(
    user_email: str,
    user_name: str,
    new_plan: str,
    end_date: str,
    lang: Optional[str] = None,
) -> Dict[str, Any]:
    """Send confirmation when subscription is upgraded/changed by admin. iter482 P2 fix — language-aware EN/FR."""
    if lang is None:
        lang = "en"
    is_fr = str(lang).lower().startswith("fr")
    plan_name = new_plan.title()

    title = "🎉 Abonnement mis à jour" if is_fr else "🎉 Subscription Updated"
    greet = f"Bonjour {user_name}," if is_fr else f"Hi {user_name},"
    intro = (
        f"Bonne nouvelle ! Votre abonnement a été mis à jour à <strong>{plan_name}</strong>."
        if is_fr else
        f"Great news! Your subscription has been updated to <strong>{plan_name}</strong>."
    )
    active_lbl = f"Actif jusqu'au {end_date}" if is_fr else f"Active until {end_date}"
    benefits_title = f"Vos avantages {plan_name} :" if is_fr else f"Your {plan_name} Benefits:"

    if is_fr:
        benefits = []
        if new_plan in ("premium", "vip"):
            benefits += [
                "Frais de prime acheteur réduits",
                "Taux de commission vendeur réduits",
                "Soutien à la clientèle prioritaire",
            ]
        if new_plan == "vip":
            benefits += [
                "Tableau de bord analytique avancé",
                "Gestionnaire de compte dédié",
            ]
    else:
        benefits = []
        if new_plan in ("premium", "vip"):
            benefits += [
                "Reduced buyer premium fees",
                "Lower seller commission rates",
                "Priority customer support",
            ]
        if new_plan == "vip":
            benefits += [
                "Advanced analytics dashboard",
                "Dedicated account manager",
            ]
    benefits_html = "".join(f"<li>{b}</li>" for b in benefits)
    cta = "Commencer à explorer" if is_fr else "Start Exploring"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">{title}</h2>

    <p style="color: #475569; line-height: 1.6;">
        {greet}
    </p>

    <p style="color: #475569; line-height: 1.6;">
        {intro}
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #d1fae5; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">        <p style="margin: 0; color: #065f46; font-size: 24px; font-weight: bold;">
            {plan_name}
        </p>
        <p style="margin: 10px 0 0 0; color: #10b981; font-size: 14px;">
            {active_lbl}
        </p></td></tr></table>

    <h4 style="margin: 25px 0 15px 0; color: #334155;">{benefits_title}</h4>
    <ul style="margin: 0; padding: 0 0 0 20px; color: #475569; line-height: 1.8;">
        {benefits_html}
    </ul>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #10b981; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/marketplace" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">{cta}</a>
            </td>
        </tr>
    </table>
    """
    subject = (
        f"🎉 Bienvenue chez {plan_name} !"
        if is_fr else
        f"🎉 Welcome to {plan_name}!"
    )
    return await _send_via_unified(
        to_email=user_email,
        subject=subject,
        html_content=_base_template(content, "Abonnement mis à jour" if is_fr else "Subscription Updated")
    )


async def send_payment_reminder_email(
    winner_email: str,
    winner_name: str,
    item_title: str,
    final_price: float,
    listing_id: str,
    days_remaining: int,
    payment_deadline: str,
    lang: Optional[str] = None,
) -> Dict[str, Any]:
    """Send payment reminder email (day 10). iter482 P2 fix — language-aware EN/FR."""
    if lang is None:
        lang = "en"
    is_fr = str(lang).lower().startswith("fr")
    fmt_money = _format_currency_fr if is_fr else _format_currency
    checkout_url = f"{FRONTEND_URL}/checkout/{listing_id}"
    price_display = fmt_money(final_price)
    deadline_display = _format_date(payment_deadline) if payment_deadline else ("bientôt" if is_fr else "soon")

    title = "Rappel de paiement" if is_fr else "Payment Reminder"
    greet = f"Bonjour {winner_name}," if is_fr else f"Hi {winner_name},"
    intro = (
        f"Nous vous rappelons que le paiement pour <strong>{item_title}</strong> "
        f"est exigible dans <strong>{days_remaining} jour(s)</strong>."
        if is_fr else
        f"This is a reminder that your payment for <strong>{item_title}</strong> "
        f"is due in <strong>{days_remaining} days</strong>."
    )
    box_title = "Détails du paiement" if is_fr else "Payment Details"
    amount_lbl = "Montant" if is_fr else "Amount"
    fees_note = (
        "(+ frais et taxes applicables)" if is_fr else "(+ applicable fees &amp; taxes)"
    )
    deadline_lbl = "Échéance" if is_fr else "Deadline"
    penalty_note = (
        "Passé ce délai, une <strong>pénalité mensuelle de 2 %</strong> sera appliquée à votre solde."
        if is_fr else
        "After the deadline, a <strong>2% monthly late penalty</strong> will be applied to your balance."
    )
    cta = "Payer maintenant" if is_fr else "Pay Now"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #f59e0b;">{title}</h2>

    <p style="color: #475569; line-height: 1.6;">
        {greet}
    </p>

    <p style="color: #475569; line-height: 1.6;">
        {intro}
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
            <td style="background-color: #fffbeb; border: 1px solid #fbbf24; border-radius: 8px; padding: 20px;">
                <p style="margin: 0 0 8px 0; color: #92400e; font-weight: bold;">{box_title}</p>
                <p style="margin: 0; color: #92400e;">{amount_lbl}: <strong>{price_display}</strong> {fees_note}</p>
                <p style="margin: 8px 0 0 0; color: #dc2626; font-weight: bold;">{deadline_lbl}: {deadline_display}</p>
            </td>
        </tr>
    </table>

    <p style="color: #475569; line-height: 1.6; margin-top: 20px;">
        {penalty_note}
    </p>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #f59e0b; padding: 14px 30px; border-radius: 8px;">
                <a href="{checkout_url}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">{cta}</a>
            </td>
        </tr>
    </table>
    """

    subject = (
        f"Rappel de paiement : {item_title} — {days_remaining} jour(s) restant(s)"
        if is_fr else
        f"Payment Reminder: {item_title} - {days_remaining} Days Left"
    )
    return await _send_via_unified(
        to_email=winner_email,
        subject=subject,
        html_content=_base_template(content, title)
    )


async def send_payment_overdue_email(
    winner_email: str,
    winner_name: str,
    item_title: str,
    final_price: float,
    listing_id: str,
    penalty_amount: float,
    total_with_penalty: float,
    lang: Optional[str] = None,
) -> Dict[str, Any]:
    """Send payment overdue notice with penalty (day 14+). iter482 P2 fix — language-aware EN/FR."""
    if lang is None:
        lang = "en"
    is_fr = str(lang).lower().startswith("fr")
    fmt_money = _format_currency_fr if is_fr else _format_currency
    checkout_url = f"{FRONTEND_URL}/checkout/{listing_id}"
    price_display = fmt_money(final_price)
    penalty_display = fmt_money(penalty_amount)
    total_display = fmt_money(total_with_penalty)

    title = "Paiement en retard" if is_fr else "Payment Overdue"
    greet = f"Bonjour {winner_name}," if is_fr else f"Hi {winner_name},"
    intro = (
        f"Le paiement pour <strong>{item_title}</strong> est maintenant <strong>en retard</strong>. "
        "Une pénalité de retard a été appliquée."
        if is_fr else
        f"Your payment for <strong>{item_title}</strong> is now <strong>overdue</strong>. "
        "A late penalty has been applied."
    )
    lbl_original = "Montant initial :" if is_fr else "Original Amount:"
    lbl_penalty = "Pénalité de retard (2 %/mois) :" if is_fr else "Late Penalty (2%/month):"
    lbl_new_total = "Nouveau total à payer :" if is_fr else "New Total Due:"
    escalation = (
        "Veuillez régler immédiatement pour éviter d'autres pénalités. "
        "La pénalité augmente de 2 % pour chaque mois de retard supplémentaire."
        if is_fr else
        "Please complete your payment immediately to avoid further penalties. "
        "The late penalty increases by 2% for each additional month."
    )
    cta = "Payer maintenant" if is_fr else "Pay Now"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #dc2626;">{title}</h2>

    <p style="color: #475569; line-height: 1.6;">
        {greet}
    </p>

    <p style="color: #475569; line-height: 1.6;">
        {intro}
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
            <td style="background-color: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px; padding: 20px;">
                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td style="color: #991b1b; font-size: 14px; padding: 4px 0;">{lbl_original}</td>
                        <td style="color: #991b1b; font-size: 14px; text-align: right;">{price_display}</td>
                    </tr>
                    <tr>
                        <td style="color: #dc2626; font-size: 14px; padding: 4px 0;">{lbl_penalty}</td>
                        <td style="color: #dc2626; font-size: 14px; font-weight: bold; text-align: right;">+{penalty_display}</td>
                    </tr>
                    <tr>
                        <td colspan="2" style="border-top: 1px solid #fca5a5; padding-top: 8px; margin-top: 8px;"></td>
                    </tr>
                    <tr>
                        <td style="color: #991b1b; font-size: 16px; font-weight: bold; padding: 4px 0;">{lbl_new_total}</td>
                        <td style="color: #dc2626; font-size: 20px; font-weight: bold; text-align: right;">{total_display}</td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>

    <p style="color: #475569; line-height: 1.6; margin-top: 20px;">
        {escalation}
    </p>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #dc2626; padding: 14px 30px; border-radius: 8px;">
                <a href="{checkout_url}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">{cta}</a>
            </td>
        </tr>
    </table>
    """
    subject = (
        f"EN RETARD : paiement requis pour {item_title}"
        if is_fr else
        f"OVERDUE: Payment Required for {item_title}"
    )
    return await _send_via_unified(
        to_email=winner_email,
        subject=subject,
        html_content=_base_template(content, title)
    )


async def send_review_request_email(
    buyer_email: str,
    buyer_name: str,
    item_title: str,
    transaction_id: str,
    seller_name: str,
) -> Dict[str, Any]:
    """Send 'How was your purchase?' email 24h after payment confirmation."""
    review_url = f"{FRONTEND_URL}/review/{transaction_id}"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #1e3a8a;">How was your purchase?</h2>

    <p style="color: #475569; line-height: 1.6;">
        Hi {buyer_name},
    </p>

    <p style="color: #475569; line-height: 1.6;">
        You recently purchased <strong>{item_title}</strong> from <strong>{seller_name}</strong>.
        We'd love to hear about your experience!
    </p>

    <p style="color: #475569; line-height: 1.6;">
        Your review helps other buyers make informed decisions and helps sellers improve.
    </p>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td style="padding: 4px;">
                <span style="font-size: 36px; color: #f59e0b;">&#9733;&#9733;&#9733;&#9733;&#9733;</span>
            </td>
        </tr>
    </table>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 20px auto;">
        <tr>
            <td align="center" style="background-color: #1e3a8a; padding: 14px 30px; border-radius: 8px;">
                <a href="{review_url}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">Leave a Review</a>
            </td>
        </tr>
    </table>

    <p style="color: #94a3b8; font-size: 12px; text-align: center;">
        If the button doesn't work, copy this link: {review_url}
    </p>
    """

    return await _send_via_unified(
        to_email=buyer_email,
        subject=f"How was your purchase of {item_title}?",
        html_content=_base_template(content, "Leave a Review")
    )


async def send_manual_subscription_active_email(
    *, user: dict, account_kind: str, amount_cad: float,
    method: str, renewal_until: str, reference: str = "",
) -> bool:
    if not user or not user.get("email"):
        return False
    name = user.get("name") or user.get("email")
    kind_label_en = {
        "partner": "Partner",
        "vehicle_dealer": "Vehicle Dealer",
        "storage_facility": "Storage Facility",
    }.get(account_kind, "Annual Subscription")
    kind_label_fr = {
        "partner": "Partenaire",
        "vehicle_dealer": "Concessionnaire de véhicules",
        "storage_facility": "Facilité d'entreposage",
    }.get(account_kind, "Abonnement annuel")
    method_label_en = {
        "e_transfer": "Interac e-Transfer",
        "cash": "Cash",
        "cheque": "Cheque",
        "wire": "Wire / Bank Transfer",
    }.get(method, method.replace("_", " ").title())
    method_label_fr = {
        "e_transfer": "Virement Interac",
        "cash": "Comptant",
        "cheque": "Chèque",
        "wire": "Virement bancaire",
    }.get(method, method.replace("_", " ").title())
    renewal_short = (renewal_until or "")[:10]
    ref_html = f"<p style='margin:6px 0;font-size:12px;color:#64748b;'>Reference / Référence: <code>{reference}</code></p>" if reference else ""
    html = f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f8fafc;">
      <tr><td align="center" style="padding:20px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;background-color:#ffffff;border:1px solid #e2e8f0;border-radius:12px;font-family:Arial,sans-serif;">
          <tr><td style="padding:24px;">
        <h2 style="color:#16a34a;margin:0 0 10px;">✅ Your annual subscription is active</h2>
        <p style="color:#334155;line-height:1.6;">Hi <strong>{name}</strong>,</p>
        <p style="color:#334155;line-height:1.6;">Your <strong>BidVex {kind_label_en}</strong> annual subscription payment has been confirmed by our team.</p>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:12px 0;">
          <tr><td bgcolor="#ecfdf5" style="background-color:#ecfdf5;border:1px solid #16a34a;border-radius:8px;padding:14px;">
            <p style="margin:4px 0;"><strong>Amount paid:</strong> CA${amount_cad:,.2f}</p>
            <p style="margin:4px 0;"><strong>Method:</strong> {method_label_en}</p>
            <p style="margin:4px 0;"><strong>Active until:</strong> {renewal_short}</p>
            {ref_html}
          </td></tr>
        </table>
        <p style="color:#334155;line-height:1.6;">All features are now unlocked on your dashboard.</p>

        <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">

        <h2 style="color:#16a34a;margin:0 0 10px;">✅ Votre abonnement annuel est actif</h2>
        <p style="color:#334155;line-height:1.6;">Bonjour <strong>{name}</strong>,</p>
        <p style="color:#334155;line-height:1.6;">Votre paiement d'abonnement annuel BidVex <strong>{kind_label_fr}</strong> a été confirmé par notre équipe.</p>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:12px 0;">
          <tr><td bgcolor="#ecfdf5" style="background-color:#ecfdf5;border:1px solid #16a34a;border-radius:8px;padding:14px;">
            <p style="margin:4px 0;"><strong>Montant payé :</strong> {amount_cad:,.2f} $ CAD</p>
            <p style="margin:4px 0;"><strong>Méthode :</strong> {method_label_fr}</p>
            <p style="margin:4px 0;"><strong>Actif jusqu'au :</strong> {renewal_short}</p>
          </td></tr>
        </table>
        <p style="color:#334155;line-height:1.6;">Toutes les fonctionnalités sont maintenant débloquées sur votre tableau de bord.</p>

        <p style="color:#94a3b8;font-size:11px;text-align:center;margin-top:24px;">
          BidVex Inc. · GST# 706766367RT0001 · QST# 1233530880TQ0001 · All amounts in CAD
        </p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    """
    return await _send_via_unified(
        to_email=user["email"],
        subject="✅ Your annual subscription is active · Votre abonnement annuel est actif — BidVex",
        html_content=html,
    )


async def send_auction_thread_opened_email(
    *,
    recipient: dict,
    role: str,                # 'winner' | 'seller'
    counterparty: dict,
    listing_title: str,
    listing_id: str,
    conversation_id: str,
    winning_amount: float,
) -> bool:
    """Notify a winner or seller that a new message thread has been opened."""
    if not recipient or not recipient.get("email"):
        return False
    name = recipient.get("name") or recipient.get("first_name") or recipient.get("email")
    cp_name = (counterparty or {}).get("name") or "Your counterparty"
    amount_str = f"CA${float(winning_amount or 0):,.2f}"
    msg_link = f"https://www.bidvex.com/messages?conversation={conversation_id}"

    if role == "winner":
        subject = f"🎉 You won — message thread opened for {listing_title}"
        body_en = (
            f"Hi <strong>{name}</strong>,<br/><br/>"
            f"Congratulations — you won the auction for <strong>{listing_title}</strong> "
            f"with a final bid of <strong>{amount_str}</strong>.<br/><br/>"
            f"A direct message thread has been opened between you and the seller "
            f"(<strong>{cp_name}</strong>) to coordinate payment and pickup."
        )
        body_fr = (
            f"Bonjour <strong>{name}</strong>,<br/><br/>"
            f"Félicitations — vous avez remporté l'enchère pour <strong>{listing_title}</strong> "
            f"avec une mise finale de <strong>{amount_str}</strong>.<br/><br/>"
            f"Un fil de messages direct a été ouvert entre vous et le vendeur "
            f"(<strong>{cp_name}</strong>) pour coordonner le paiement et la cueillette."
        )
    else:  # seller
        subject = f"✅ Sold — message thread opened with the winning bidder ({listing_title})"
        body_en = (
            f"Hi <strong>{name}</strong>,<br/><br/>"
            f"Great news — your listing <strong>{listing_title}</strong> has sold for "
            f"<strong>{amount_str}</strong>.<br/><br/>"
            f"A direct message thread has been opened between you and the winning bidder "
            f"(<strong>{cp_name}</strong>) so you can coordinate payment and pickup."
        )
        body_fr = (
            f"Bonjour <strong>{name}</strong>,<br/><br/>"
            f"Bonne nouvelle — votre annonce <strong>{listing_title}</strong> a été vendue pour "
            f"<strong>{amount_str}</strong>.<br/><br/>"
            f"Un fil de messages direct a été ouvert entre vous et l'enchérisseur gagnant "
            f"(<strong>{cp_name}</strong>) pour coordonner le paiement et la cueillette."
        )

    html = f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f8fafc;">
      <tr><td align="center" style="padding:20px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;background-color:#ffffff;border-radius:8px;font-family:Arial,sans-serif;">
          <tr><td style="padding:20px;">
        <h2 style="color:#1e40af;margin:0 0 12px;">{subject}</h2>
        <p style="color:#334155;line-height:1.6;">{body_en}</p>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">
        <p style="color:#334155;line-height:1.6;">{body_fr}</p>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr><td align="center" style="padding-top:20px;">
            <a href="{msg_link}" style="display:inline-block;padding:12px 28px;background-color:#2563eb;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;">
              Open message thread · Ouvrir le fil
            </a>
          </td></tr>
        </table>
        <p style="color:#64748b;font-size:11px;text-align:center;margin-top:24px;">
          BidVex — Listing #{listing_id[:8]}
        </p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    """
    return await _send_via_unified(to_email=recipient["email"], subject=subject, html_content=html)


async def send_promotion_confirmation_email(
    seller_email: str,
    seller_name: str,
    listing_title: str,
    listing_id: str,
    listing_type: str,
    tier: str,
    boost_days: int,
    start_date,
    end_date,
    base_price: float,
    gst: float,
    qst: float,
    stripe_fee: float,
    grand_total: float,
    features,
) -> Dict[str, Any]:
    """Sent after Stripe confirms payment for a listing promotion."""
    _lt = (listing_type or "marketplace").lower()
    _brand_type = "lots" if _lt in ("lots", "partner") else ("storage" if _lt == "storage" else "marketplace")
    label = _section_label(_brand_type)

    feats = "".join([f"<li style='color:#1e293b;padding:2px 0;'>{f}</li>" for f in (features or [])])

    def _fmt(d):
        try:
            return d.strftime("%Y-%m-%d")
        except Exception:
            return str(d)

    tier_label = {"basic": "Basic Boost", "standard": "Standard Boost", "premium": "Premium Boost"}.get(tier, tier.title())

    content = f"""
    <h2 style="margin:0 0 20px 0;color:#10b981;">✅ Your listing is now boosted / Votre annonce est propulsée</h2>

    <p style="color:#475569;line-height:1.6;">Hi {seller_name},</p>
    <p style="color:#475569;line-height:1.6;">
        Your {label['name_en']} listing has been successfully promoted.
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0;">
      <tr><td style="background:#ecfdf5;border:2px solid #10b981;border-radius:8px;padding:25px;">
        <p style="margin:0 0 12px 0;color:#065f46;font-size:18px;font-weight:bold;">{listing_title}</p>
        <table width="100%" style="font-size:14px;color:#1e293b;">
          <tr><td>Tier:</td><td style="text-align:right;"><strong>{tier_label} ({boost_days} days)</strong></td></tr>
          <tr><td>Start:</td><td style="text-align:right;">{_fmt(start_date)}</td></tr>
          <tr><td>End:</td><td style="text-align:right;">{_fmt(end_date)}</td></tr>
        </table>
        <p style="margin:16px 0 6px;color:#065f46;font-weight:bold;">Features activated:</p>
        <ul style="margin:0 0 0 20px;padding:0;">{feats}</ul>
      </td></tr>
    </table>

    <h3 style="margin:20px 0 10px;color:#0f172a;">Payment receipt</h3>
    <table width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;color:#1e293b;">
      <tr><td>Base price:</td><td style="text-align:right;">{_format_currency(base_price)}</td></tr>
      <tr><td>GST (5%):</td><td style="text-align:right;">{_format_currency(gst)}</td></tr>
      <tr><td>QST (9.975%):</td><td style="text-align:right;">{_format_currency(qst)}</td></tr>
      <tr><td>Payment Processing:</td><td style="text-align:right;">{_format_currency(stripe_fee)}</td></tr>
      <tr><td style="border-top:1px solid #e2e8f0;padding-top:6px;"><strong>Total Charged:</strong></td>
          <td style="border-top:1px solid #e2e8f0;padding-top:6px;text-align:right;font-weight:bold;">{_format_currency(grand_total)} CAD</td></tr>
    </table>

    <table cellpadding="0" cellspacing="0" align="center" style="margin:30px auto;">
      <tr><td align="center" style="background:#10b981;padding:14px 30px;border-radius:8px;">
        <a href="{FRONTEND_URL}/listing/{listing_id}" style="color:#fff;text-decoration:none;font-weight:bold;">View Your Listing</a>
      </td></tr>
    </table>

    <p style="color:#64748b;font-size:12px;">Questions? <a href="mailto:service@bidvex.com">service@bidvex.com</a></p>

    <hr style="border:0;border-top:1px solid #e2e8f0;margin:24px 0;" />
    <p style="color:#475569;line-height:1.6;">
        Bonjour {seller_name}, votre annonce {label['name_fr']} a été promue avec succès ({tier_label}, {boost_days} jours).
    </p>
    """
    return await _send_via_unified(
        to_email=seller_email,
        subject=f"✅ Your listing is now boosted — {listing_title} | {label['name_en']}",
        html_content=_base_template(content, "Listing Promoted", auction_type=_brand_type),
    )


async def send_deposit_refunded_email(
    db, *, user_id: str, auction_id: str, amount: float, currency: str = "CAD"
) -> bool:
    """Send refund-confirmation email after non-winner deposit is refunded."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "name": 1})
    if not user or not user.get("email"):
        return False
    listing = (
        await db.listings.find_one({"id": auction_id}, {"_id": 0, "title": 1})
        or await db.multi_item_listings.find_one({"id": auction_id}, {"_id": 0, "title": 1})
        or await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0, "unit_number": 1})
        or {}
    )
    title = listing.get("title") or listing.get("unit_number") or auction_id
    cur = (currency or "CAD").upper()
    name = user.get("name") or user.get("email").split("@")[0]
    content = f"""
    <h2 style="color:#1e40af">Your deposit has been refunded · Votre dépôt a été remboursé</h2>
    <p>Hi {name},</p>
    <p><strong>EN:</strong> Your deposit of <strong>${amount:,.2f} {cur}</strong> for auction
    <em>“{title}”</em> has been refunded. It will appear on your statement within 5–7 business days.</p>
    <p><strong>FR:</strong> Votre dépôt de <strong>{amount:,.2f} $ {cur}</strong> pour
    l’enchère <em>« {title} »</em> a été remboursé. Il apparaîtra sur votre relevé d’ici 5 à 7 jours ouvrables.</p>
    <p>— The BidVex Team / L’équipe BidVex</p>
    """
    return await _send_via_unified(
        to_email=user["email"],
        subject=f"Deposit refunded · Dépôt remboursé — ${amount:,.2f} {cur}",
        html_content=_base_template(content, "Deposit Refunded"),
    )


async def send_charge_confirmation_email(
    db, *, user_id: str, auction_id: str, amount: float, currency: str = "CAD",
    charge_type: str = "buyer_commission",
) -> bool:
    """Notify user of a successful charge (winner full / commission / seller)."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "name": 1})
    if not user or not user.get("email"):
        return False
    listing = (
        await db.listings.find_one({"id": auction_id}, {"_id": 0, "title": 1})
        or await db.multi_item_listings.find_one({"id": auction_id}, {"_id": 0, "title": 1})
        or {}
    )
    title = listing.get("title") or auction_id
    cur = (currency or "CAD").upper()
    label_en = {
        "buyer_commission": "BidVex Buyer Commission",
        "buyer_full_payment": "BidVex Purchase",
        "buy_now_payment": "Buy Now Purchase",
        "seller_commission": "BidVex Seller Commission",
        "seller_payout": "BidVex Sale Payout",
    }.get(charge_type, "BidVex Charge")
    label_fr = {
        "buyer_commission": "Commission acheteur BidVex",
        "buyer_full_payment": "Achat BidVex",
        "buy_now_payment": "Achat immédiat",
        "seller_commission": "Commission vendeur BidVex",
        "seller_payout": "Paiement vendeur BidVex",
    }.get(charge_type, "Charge BidVex")
    name = user.get("name") or user.get("email").split("@")[0]
    content = f"""
    <h2 style="color:#1e40af">{label_en} · {label_fr}</h2>
    <p>Hi {name},</p>
    <p><strong>EN:</strong> Your card has been charged <strong>${amount:,.2f} {cur}</strong>
    ({label_en}) for auction <em>“{title}”</em>.</p>
    <p><strong>FR:</strong> Votre carte a été débitée de <strong>{amount:,.2f} $ {cur}</strong>
    ({label_fr}) pour l’enchère <em>« {title} »</em>.</p>
    <p>— The BidVex Team / L’équipe BidVex</p>
    """
    return await _send_via_unified(
        to_email=user["email"],
        subject=f"{label_en} · {label_fr} — ${amount:,.2f} {cur}",
        html_content=_base_template(content, label_en),
    )


async def send_payout_confirmation_email(
    db, *, seller_id: str, auction_id: str, amount: float, currency: str = "CAD",
) -> bool:
    """Notify seller their Connect payout was initiated."""
    seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "email": 1, "name": 1})
    if not seller or not seller.get("email"):
        return False
    listing = (
        await db.listings.find_one({"id": auction_id}, {"_id": 0, "title": 1})
        or await db.multi_item_listings.find_one({"id": auction_id}, {"_id": 0, "title": 1})
        or {}
    )
    title = listing.get("title") or auction_id
    cur = (currency or "CAD").upper()
    name = seller.get("name") or seller.get("email").split("@")[0]
    content = f"""
    <h2 style="color:#1e40af">Sale payout initiated · Paiement de vente initié</h2>
    <p>Hi {name},</p>
    <p><strong>EN:</strong> Your sale payout of <strong>${amount:,.2f} {cur}</strong> for
    auction <em>“{title}”</em> has been initiated through Stripe Connect.</p>
    <p><strong>FR:</strong> Le paiement de votre vente de <strong>{amount:,.2f} $ {cur}</strong>
    pour l’enchère <em>« {title} »</em> a été initié via Stripe Connect.</p>
    <p>— The BidVex Team / L’équipe BidVex</p>
    """
    return await _send_via_unified(
        to_email=seller["email"],
        subject=f"Sale payout · Paiement de vente — ${amount:,.2f} {cur}",
        html_content=_base_template(content, "Payout Initiated"),
    )


async def send_promotion_expired_email(
    *, seller_email: str, seller_name: str, listing_title: str,
    listing_id: str, listing_type: str, tier: str = "basic",
) -> bool:
    """Notify seller their boost expired and prompt them to renew."""
    renew_path = {
        "marketplace": f"/listing/{listing_id}",
        "lots": f"/lots-auction/{listing_id}",
        "vehicle": f"/vehicle-auctions/{listing_id}",
        "storage": f"/storage-auctions/{listing_id}",
    }.get(listing_type, f"/listing/{listing_id}")
    tier_label = {"basic": "Basic", "standard": "Standard", "premium": "Premium"}.get(tier, tier.title())
    content = f"""
    <h2 style="color:#1e40af">Your boost has ended · Votre promotion est terminée</h2>
    <p>Hi {seller_name or 'Seller'},</p>
    <p><strong>EN:</strong> Your <strong>{tier_label}</strong> boost for
    <em>"{listing_title}"</em> has ended. Your listing is no longer featured —
    <a href="https://bidvex.com{renew_path}" style="color:#2563eb">renew to stay featured</a>.</p>
    <p><strong>FR:</strong> Votre promotion <strong>{tier_label}</strong> pour
    <em>« {listing_title} »</em> est terminée. Votre annonce n'est plus en vedette —
    <a href="https://bidvex.com{renew_path}" style="color:#2563eb">renouvelez pour rester en vedette</a>.</p>
    <p>— The BidVex Team / L'équipe BidVex</p>
    """
    return await _send_via_unified(
        to_email=seller_email,
        subject=f"Your boost ended · Votre promotion est terminée — {listing_title}",
        html_content=_base_template(content, "Boost Ended"),
    )


async def send_promotion_email_blast(
    *, to_email: str, listing_title: str, listing_id: str,
    listing_type: str, category: str = "",
) -> bool:
    """T+24h email blast to category subscribers for premium-boosted listings."""
    path = {
        "marketplace": f"/listing/{listing_id}",
        "lots": f"/lots-auction/{listing_id}",
        "vehicle": f"/vehicle-auctions/{listing_id}",
        "storage": f"/storage-auctions/{listing_id}",
    }.get(listing_type, f"/listing/{listing_id}")
    content = f"""
    <h2 style="color:#1e40af">Featured · En vedette : {listing_title}</h2>
    <p><strong>EN:</strong> Don't miss this featured auction —
    <a href="https://bidvex.com{path}" style="color:#2563eb">view auction</a>.</p>
    <p><strong>FR:</strong> Ne manquez pas cette enchère en vedette —
    <a href="https://bidvex.com{path}" style="color:#2563eb">voir l'enchère</a>.</p>
    <p>— The BidVex Team / L'équipe BidVex</p>
    """
    return await _send_via_unified(
        to_email=to_email,
        subject=f"Featured: {listing_title} — Don't Miss This Auction · En vedette : Ne manquez pas",
        html_content=_base_template(content, "Featured Auction"),
    )


async def send_new_message_email(
    recipient: dict,
    sender_name: str,
    preview: str,
    listing_id: str = None,
    conversation_id: str = None,
) -> bool:
    """
    Send a bilingual notification when an offline user receives a new in-app message.
    """
    if not recipient or not recipient.get("email"):
        return False

    safe_preview = (preview or "").strip().replace("<", "&lt;").replace(">", "&gt;")
    if len(safe_preview) > 200:
        safe_preview = safe_preview[:200] + "…"

    cta_url = "https://bidvex.com/messages"
    if conversation_id:
        cta_url += f"?conversation={conversation_id}"

    body_en = (
        f"<strong>{sender_name}</strong> sent you a message on BidVex:<br/><br/>"
        f"<em style='border-left:3px solid #2563eb;padding-left:10px;display:block;margin:10px 0;color:#475569;'>"
        f"{safe_preview}</em>"
        f"<br/>Reply directly inside BidVex to keep your conversation secure."
    )
    body_fr = (
        f"<strong>{sender_name}</strong> vous a envoyé un message sur BidVex :<br/><br/>"
        f"<em style='border-left:3px solid #2563eb;padding-left:10px;display:block;margin:10px 0;color:#475569;'>"
        f"{safe_preview}</em>"
        f"<br/>Répondez directement dans BidVex pour garder votre conversation sécurisée."
    )

    return await _send_via_unified(
        to_email=recipient["email"],
        subject=f"💬 New message from {sender_name} · Nouveau message",
        html_content=_storage_panel(
            "You have a new message", "Vous avez un nouveau message",
            body_en, body_fr,
            cta_url=cta_url,
            cta_en="Open Conversation",
            cta_fr="Ouvrir la conversation",
        ),
    )



# ═══════════════════════════════════════════════════════════════════
# iter298 BUG 4 — Buyer receipts + seller statements + payment links
# ═══════════════════════════════════════════════════════════════════

def _letterhead() -> str:
    """BidVex Inc. legal letterhead — appended to every receipt/statement."""
    return """
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 28px; border-top: 1px solid #e2e8f0;">
      <tr><td style="padding-top: 14px; color: #94a3b8; font-size: 12px; line-height: 1.6;">
        <strong style="color: #64748b;">BidVex Inc.</strong><br/>
        761 Rue Chalifoux, Sherbrooke (Qu&eacute;bec) J1G 0A8, Canada<br/>
        Corporation Number 1175253974
      </td></tr>
    </table>
    """


def _money_row(label: str, amount: float, bold: bool = False, color: str = "#0f172a") -> str:
    weight = "700" if bold else "400"
    return f"""
      <tr>
        <td style="padding: 8px 0; color: #475569; font-size: 14px; border-bottom: 1px solid #f1f5f9;">{label}</td>
        <td align="right" style="padding: 8px 0; color: {color}; font-size: 14px; font-weight: {weight}; border-bottom: 1px solid #f1f5f9;">${amount:,.2f} CAD</td>
      </tr>
    """


async def send_buyer_receipt_email(buyer: dict, receipt: dict) -> Dict[str, Any]:
    """iter366 — Redesigned professional buyer receipt.

    Structure:
      1. Header (BidVex logo via base template) + "Payment Successful ✓" heading
      2. Purchase Information card (Item, Seller, Order #, Date)
      3. Price Breakdown table with prominent TOTAL PAID row
      4. Pickup Section (large monospace code + instructions)
      5. Payment Information (card last-4 + transaction id)
      6. Legal letterhead (BidVex Inc. address + corporation #)
    """
    from datetime import datetime
    lang = _detect_language(buyer)
    title = receipt.get("listing_title", "Item")
    last4 = receipt.get("payment_method_last4")
    txn = receipt.get("transaction_id") or receipt.get("id", "")
    seller_name = receipt.get("seller_name") or "BidVex Seller"
    order_number = receipt.get("order_number") or (receipt.get("id", "")[:8].upper() if receipt.get("id") else "")
    # Purchase date — formatted per language.
    try:
        created = receipt.get("created_at")
        dt = datetime.fromisoformat(created.replace("Z", "+00:00")) if isinstance(created, str) else datetime.utcnow()
    except Exception:
        dt = datetime.utcnow()
    if lang == "fr":
        purchase_date = dt.strftime("%d %B %Y")
    else:
        purchase_date = dt.strftime("%B %d, %Y")

    # ─── Bilingual copy ─────────────────────────────────────────────────
    if lang == "fr":
        heading         = "Paiement r&eacute;ussi"
        subhead         = "Merci pour votre achat&nbsp;!"
        buyer_greeting  = f"Bonjour {buyer.get('name', '')},"
        purchase_h      = "Informations d'achat"
        lbl_item        = "Article"
        lbl_seller      = "Vendeur"
        lbl_order       = "Commande"
        lbl_date        = "Date d'achat"
        breakdown_h     = "D&eacute;tail du paiement"
        row_hammer      = "Prix d'adjudication"
        row_platform    = "Frais acheteur BidVex"
        row_taxes       = "Taxes"
        row_processing  = "Traitement du paiement"
        row_total       = "TOTAL PAY&Eacute;"
        pickup_h        = "VOTRE CODE DE COLLECTE"
        pickup_help     = "Pr&eacute;sentez ce code au vendeur lors de la collecte de votre article."
        payinfo_h       = "Informations de paiement"
        card_prefix     = "Carte se terminant par"
        txn_prefix      = "ID de transaction&nbsp;:"
        subject         = f"BidVex — Paiement re&ccedil;u pour {title}"
    else:
        heading         = "Payment Successful"
        subhead         = "Thank you for your purchase!"
        buyer_greeting  = f"Hi {buyer.get('name', '')},"
        purchase_h      = "Purchase Information"
        lbl_item        = "Item"
        lbl_seller      = "Seller"
        lbl_order       = "Order"
        lbl_date        = "Purchase Date"
        breakdown_h     = "Price Breakdown"
        row_hammer      = "Hammer Price"
        row_platform    = "BidVex Buyer Fee"
        row_taxes       = "Taxes"
        row_processing  = "Payment Processing"
        row_total       = "TOTAL PAID"
        pickup_h        = "YOUR PICKUP CODE"
        pickup_help     = "Show this code to the seller when collecting your item."
        payinfo_h       = "Payment Information"
        card_prefix     = "Card ending in"
        txn_prefix      = "Transaction ID:"
        subject         = f"BidVex — Payment received for {title}"

    # ─── Section 1: Success header ──────────────────────────────────────
    header_block = f"""
    <div style="text-align:center;padding:18px 0 4px;">
      <div style="display:inline-block;width:56px;height:56px;border-radius:50%;background:#dcfce7;line-height:56px;text-align:center;font-size:30px;color:#16a34a;">&#10003;</div>
      <h1 style="margin:14px 0 6px;color:#0f172a;font-size:26px;font-weight:800;">{heading}</h1>
      <p style="margin:0;color:#475569;font-size:15px;">{subhead}</p>
    </div>
    <p style="color:#475569;line-height:1.6;margin:20px 0 12px;">{buyer_greeting}</p>
    """

    # ─── Section 2: Purchase information ────────────────────────────────
    def _info_row(label, value):
        return f"""
        <tr>
          <td style="padding:8px 0;color:#64748b;font-size:13px;text-transform:uppercase;letter-spacing:0.05em;font-weight:600;width:40%;">{label}</td>
          <td style="padding:8px 0;color:#0f172a;font-size:15px;font-weight:600;text-align:right;">{value}</td>
        </tr>
        """
    purchase_info = f"""
    <table role='presentation' width='100%' cellpadding='0' cellspacing='0' border='0'
           style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px 20px;margin:18px 0;">
      <tr><td>
        <h3 style="margin:0 0 8px;color:#0f172a;font-size:14px;text-transform:uppercase;letter-spacing:0.08em;font-weight:800;">{purchase_h}</h3>
        <table role='presentation' width='100%' cellpadding='0' cellspacing='0' border='0'>
          {_info_row(lbl_item,   title)}
          {_info_row(lbl_seller, seller_name)}
          {_info_row(lbl_order,  order_number)}
          {_info_row(lbl_date,   purchase_date)}
        </table>
      </td></tr>
    </table>
    """

    # ─── Section 3: Price breakdown ─────────────────────────────────────
    breakdown_rows = (
        _money_row(row_hammer,     receipt.get("hammer_price", 0))
        + _money_row(row_platform, receipt.get("platform_fee", 0))
        + _money_row(row_taxes,    receipt.get("taxes", 0))
        + _money_row(row_processing, receipt.get("processing_fee", 0))
    )
    total_row = f"""
    <tr>
      <td style="padding:14px 0 0;color:#0f172a;font-size:16px;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;border-top:2px solid #0f172a;">{row_total}</td>
      <td align="right" style="padding:14px 0 0;color:#0ea5e9;font-size:22px;font-weight:800;border-top:2px solid #0f172a;">${receipt.get("total_charged", 0):,.2f} CAD</td>
    </tr>
    """
    breakdown_block = f"""
    <h3 style="margin:22px 0 10px;color:#0f172a;font-size:14px;text-transform:uppercase;letter-spacing:0.08em;font-weight:800;">{breakdown_h}</h3>
    <table role='presentation' width='100%' cellpadding='0' cellspacing='0' border='0'>
      {breakdown_rows}
      {total_row}
    </table>
    """

    # ─── Section 4: Pickup code ─────────────────────────────────────────
    pickup_code = receipt.get("pickup_code")
    pickup_block = ""
    if pickup_code:
        pickup_block = f"""
        <table role='presentation' width='100%' cellpadding='0' cellspacing='0'
               style="background:#eff6ff;border:2px dashed #2563eb;border-radius:12px;margin:22px 0;">
          <tr><td align='center' style='padding:22px 18px;'>
            <p style='margin:0 0 6px;color:#1e3a8a;font-size:12px;font-weight:800;letter-spacing:0.12em;'>{pickup_h}</p>
            <p style='margin:6px 0 8px;font-size:34px;font-weight:800;letter-spacing:4px;color:#1d4ed8;font-family:"Courier New",monospace;'>{pickup_code}</p>
            <p style='margin:10px 0 0;color:#475569;font-size:13px;line-height:1.5;'>{pickup_help}</p>
          </td></tr>
        </table>
        """

    # ─── Section 5: Payment information ─────────────────────────────────
    payment_info = f"""
    <h3 style="margin:22px 0 10px;color:#0f172a;font-size:14px;text-transform:uppercase;letter-spacing:0.08em;font-weight:800;">{payinfo_h}</h3>
    <table role='presentation' width='100%' cellpadding='0' cellspacing='0' border='0'
           style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px 20px;">
      <tr><td style='padding:6px 0;'>
        {("<div style='color:#0f172a;font-size:14px;margin-bottom:6px;'>" + card_prefix + " <strong>&bull;&bull;&bull;&bull; " + last4 + "</strong></div>") if last4 else ""}
        <div style='color:#64748b;font-size:12px;'>{txn_prefix} <strong style='color:#0f172a;font-family:"Courier New",monospace;'>{txn}</strong></div>
      </td></tr>
    </table>
    """

    content = header_block + purchase_info + breakdown_block + pickup_block + payment_info + _letterhead()

    return await _send_via_unified(
        to_email=buyer["email"],
        subject=subject,
        html_content=_base_template(content, heading,
                                    auction_type=receipt.get("section")),
    )


async def send_seller_statement_email(seller: dict, statement: dict) -> Dict[str, Any]:
    """Sale statement for the seller — hammer, 2.5% platform fee deducted,
    net payout, payout timeline, buyer first name."""
    lang = _detect_language(seller)
    title = statement.get("listing_title", "Item")
    buyer_first = statement.get("buyer_first_name") or "—"

    if lang == "fr":
        heading = "Relev&eacute; de vente"
        intro = (f"Bonjour {seller.get('name', '')}, votre article <strong>{title}</strong> "
                 f"a &eacute;t&eacute; vendu &agrave; <strong>{buyer_first}</strong>.")
        rows = (
            _money_row("Prix d'adjudication", statement.get("hammer_price", 0))
            + _money_row("Frais de plateforme d&eacute;duits (2,5\u00a0%)", -abs(statement.get("platform_fee", 0)), color="#dc2626")
            + _money_row("Versement net", statement.get("net_payout", 0), bold=True, color="#059669")
        )
        timeline = ("<p style='color:#64748b;font-size:13px;'>D&eacute;lai de versement&nbsp;: "
                    "sous <strong>14 jours</strong> apr&egrave;s confirmation de la transaction.</p>")
        subject = f"Relev\u00e9 de vente BidVex — {title}"
    else:
        heading = "Sale Statement"
        intro = (f"Hi {seller.get('name', '')}, your item <strong>{title}</strong> "
                 f"was sold to <strong>{buyer_first}</strong>.")
        rows = (
            _money_row("Hammer price", statement.get("hammer_price", 0))
            + _money_row("Platform fee deducted (2.5%)", -abs(statement.get("platform_fee", 0)), color="#dc2626")
            + _money_row("Net payout", statement.get("net_payout", 0), bold=True, color="#059669")
        )
        timeline = ("<p style='color:#64748b;font-size:13px;'>Payout timeline: within "
                    "<strong>14 days</strong> after transaction confirmation.</p>")
        subject = f"BidVex Sale Statement — {title}"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #0f172a;">{heading}</h2>
    <p style="color: #475569; line-height: 1.6;">{intro}</p>
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;">
      {rows}
    </table>
    {timeline}
    {_letterhead()}
    """
    return await _send_via_unified(
        to_email=seller["email"],
        subject=subject,
        html_content=_base_template(content, heading,
                                    auction_type=statement.get("section")),
    )


async def send_payment_link_email(
    buyer: dict, listing_title: str, listing_id: str,
    total_due: float, payment_link_url: Optional[str], deadline_iso: str,
) -> Dict[str, Any]:
    """Buyer has no saved payment method — email a Stripe payment link
    with a 72-hour deadline (iter302)."""
    lang = _detect_language(buyer)
    link = payment_link_url or f"{FRONTEND_URL}/dashboard/buyer"
    deadline_h = _format_date(deadline_iso)

    if lang == "fr":
        heading = "Paiement requis — 72 heures"
        body = (f"F&eacute;licitations, vous avez remport&eacute; <strong>{listing_title}</strong>&nbsp;! "
                f"Aucune carte n'est enregistr&eacute;e sur votre compte. Veuillez payer "
                f"<strong>${total_due:,.2f} CAD</strong> avant le <strong>{deadline_h}</strong> "
                f"pour finaliser votre achat. Pass&eacute; ce d&eacute;lai, l'annonce sera signal&eacute;e en retard de paiement.")
        cta = "Payer maintenant"
        subject = f"Paiement requis sous 48 h — {listing_title}"
    else:
        heading = "Payment Required — 48 Hours"
        body = (f"Congratulations, you won <strong>{listing_title}</strong>! "
                f"There is no payment method saved on your account. Please pay "
                f"<strong>${total_due:,.2f} CAD</strong> before <strong>{deadline_h}</strong> "
                f"to complete your purchase. After the deadline this purchase will be flagged as payment overdue.")
        cta = "Pay Now"
        subject = f"Payment required within 48h — {listing_title}"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #d97706;">{heading}</h2>
    <p style="color: #475569; line-height: 1.6;">{body}</p>
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
      <tr><td align="center" style="background-color: #0ea5e9; padding: 14px 30px; border-radius: 8px;">
        <a href="{link}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px;">{cta}</a>
      </td></tr>
    </table>
    {_letterhead()}
    """
    return await _send_via_unified(
        to_email=buyer["email"],
        subject=subject,
        html_content=_base_template(content, heading),
    )


async def send_payment_failed_email(
    buyer: dict, listing_title: str, listing_id: str, amount: float,
) -> Dict[str, Any]:
    """Stripe charge on the saved card failed — ask the buyer to update
    their payment method."""
    lang = _detect_language(buyer)
    settings_url = f"{FRONTEND_URL}/settings?tab=payments"

    if lang == "fr":
        heading = "&Eacute;chec du paiement"
        body = (f"Le paiement de <strong>${amount:,.2f} CAD</strong> pour "
                f"<strong>{listing_title}</strong> a &eacute;chou&eacute;. "
                f"Veuillez mettre &agrave; jour votre m&eacute;thode de paiement pour finaliser votre achat.")
        cta = "Mettre &agrave; jour ma carte"
        subject = f"\u00c9chec du paiement — {listing_title}"
    else:
        heading = "Payment Failed"
        body = (f"The payment of <strong>${amount:,.2f} CAD</strong> for "
                f"<strong>{listing_title}</strong> could not be processed. "
                f"Please update your payment method to complete your purchase.")
        cta = "Update Payment Method"
        subject = f"Payment failed — {listing_title}"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #dc2626;">{heading}</h2>
    <p style="color: #475569; line-height: 1.6;">{body}</p>
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
      <tr><td align="center" style="background-color: #dc2626; padding: 14px 30px; border-radius: 8px;">
        <a href="{settings_url}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px;">{cta}</a>
      </td></tr>
    </table>
    {_letterhead()}
    """
    return await _send_via_unified(
        to_email=buyer["email"],
        subject=subject,
        html_content=_base_template(content, heading),
    )



# ═══════════════════════════════════════════════════════════════════
# iter299 P1 — Marketplace moderation decision emails
# ═══════════════════════════════════════════════════════════════════

async def send_listing_approved_email(
    seller: dict, listing_title: str, listing_id: str, section: str = "marketplace",
) -> Dict[str, Any]:
    """Listing approved by the moderation team — it is now live."""
    lang = _detect_language(seller)
    link = f"{FRONTEND_URL}/listing/{listing_id}" if section == "marketplace" else f"{FRONTEND_URL}/lots/{listing_id}"

    if lang == "fr":
        subject = f"Annonce approuvée — {listing_title}"
        heading = "Votre annonce est en ligne&nbsp;!"
        body = (f"Bonne nouvelle, {seller.get('name','')}&nbsp;! Votre annonce "
                f"<strong>{listing_title}</strong> a &eacute;t&eacute; approuv&eacute;e et est maintenant visible par les acheteurs.")
        cta = "Voir mon annonce"
    else:
        subject = f"Listing approved — {listing_title}"
        heading = "Your listing is live!"
        body = (f"Good news, {seller.get('name','')}! Your listing "
                f"<strong>{listing_title}</strong> was approved and is now visible to buyers.")
        cta = "View My Listing"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #059669;">{heading}</h2>
    <p style="color: #475569; line-height: 1.6;">{body}</p>
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
      <tr><td align="center" style="background-color: #2B8FD0; padding: 14px 30px; border-radius: 8px;">
        <a href="{link}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px;">{cta}</a>
      </td></tr>
    </table>
    """
    return await _send_via_unified(
        to_email=seller["email"],
        subject=subject,
        html_content=_base_template(content, heading),
    )


async def send_listing_rejected_email(
    seller: dict, listing_title: str, listing_id: str, reason: str,
    section: str = "marketplace",
) -> Dict[str, Any]:
    """Listing rejected by the moderation team — includes the admin's reason."""
    lang = _detect_language(seller)
    link = f"{FRONTEND_URL}/seller/dashboard"

    if lang == "fr":
        subject = f"Annonce refusée — {listing_title}"
        heading = "Votre annonce n'a pas &eacute;t&eacute; approuv&eacute;e"
        body = (f"Bonjour {seller.get('name','')}, votre annonce "
                f"<strong>{listing_title}</strong> n'a pas pass&eacute; la mod&eacute;ration.")
        reason_label = "Raison"
        cta = "Voir mon tableau de bord"
        footer = "Corrigez le probl&egrave;me et soumettez une nouvelle annonce quand vous &ecirc;tes pr&ecirc;t."
    else:
        subject = f"Listing rejected — {listing_title}"
        heading = "Your listing was not approved"
        body = (f"Hi {seller.get('name','')}, your listing "
                f"<strong>{listing_title}</strong> did not pass moderation.")
        reason_label = "Reason"
        cta = "Go to My Dashboard"
        footer = "Fix the issue and submit a new listing when you're ready."

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #dc2626;">{heading}</h2>
    <p style="color: #475569; line-height: 1.6;">{body}</p>
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 16px 0; background-color: #fef2f2; border-radius: 8px;">
      <tr><td style="padding: 14px 16px;">
        <p style="margin: 0; color: #991b1b; font-size: 13px; font-weight: 700;">{reason_label}</p>
        <p style="margin: 6px 0 0 0; color: #7f1d1d; font-size: 14px; line-height: 1.5;">{reason}</p>
      </td></tr>
    </table>
    <p style="color: #475569; line-height: 1.6;">{footer}</p>
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
      <tr><td align="center" style="background-color: #0B2545; padding: 14px 30px; border-radius: 8px;">
        <a href="{link}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px;">{cta}</a>
      </td></tr>
    </table>
    """
    return await _send_via_unified(
        to_email=seller["email"],
        subject=subject,
        html_content=_base_template(content, heading),
    )



# ══════════════════════════════════════════════════════════════════════════
# iter468 — Final document delivery for confirmed Stripe auction payments.
# BidVex is the current document issuer. No partner co-branding, no PDF
# attachments, no cash / e-transfer / escrow / fee / tax changes.
# Bilingual EN/FR preserved via the standard `_detect_language` helper.
# ══════════════════════════════════════════════════════════════════════════

async def send_buyer_final_invoice_link_email(
    *, buyer: dict, invoice_link: str, invoice_number: str,
    listing_title: str, amount_paid_display: str,
) -> Dict[str, Any]:
    """One buyer email with ONE secure link to the buyer's final paid
    invoice. Content mirrors the existing receipt copy tone — no new
    financial data, no attachment, just a stable signed link the buyer
    can revisit to view / download their paid invoice PDF.
    """
    lang = _detect_language(buyer)
    if lang == "fr":
        heading = "Votre facture finale est pr&ecirc;te"
        greeting = f"Bonjour {buyer.get('name', '')},"
        body = (
            f"Votre paiement pour <strong>{listing_title}</strong> a &eacute;t&eacute; confirm&eacute;. "
            f"Vous pouvez consulter et t&eacute;l&eacute;charger votre facture finale (n° "
            f"<strong>{invoice_number}</strong>) via le lien s&eacute;curis&eacute; ci-dessous."
        )
        total_label = f"Total pay&eacute;&nbsp;: <strong>{amount_paid_display}</strong>"
        cta = "Consulter ma facture"
        note = ("Ce lien est priv&eacute; et sp&eacute;cifique &agrave; votre compte. "
                "Veuillez ne pas le partager.")
        subject = f"BidVex — Votre facture pour {listing_title}"
    else:
        heading = "Your final invoice is ready"
        greeting = f"Hi {buyer.get('name', '')},"
        body = (
            f"Your payment for <strong>{listing_title}</strong> has been confirmed. "
            f"You can view and download your final invoice (No "
            f"<strong>{invoice_number}</strong>) via the secure link below."
        )
        total_label = f"Total paid: <strong>{amount_paid_display}</strong>"
        cta = "View my invoice"
        note = "This link is private and specific to your account. Please do not share it."
        subject = f"BidVex — Your invoice for {listing_title}"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #0f172a;">{heading}</h2>
    <p style="color: #475569; line-height: 1.6;">{greeting}</p>
    <p style="color: #475569; line-height: 1.6;">{body}</p>
    <p style="color: #0f172a; font-size: 15px; margin: 20px 0;">{total_label}</p>
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
      <tr><td align="center" style="background-color: #0B2545; padding: 14px 30px; border-radius: 8px;">
        <a href="{invoice_link}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px;" data-testid="buyer-final-invoice-link">{cta}</a>
      </td></tr>
    </table>
    <p style="color: #94a3b8; font-size: 12px; line-height: 1.5; margin-top: 24px;">{note}</p>
    """
    return await _send_via_unified(
        to_email=buyer["email"],
        subject=subject,
        html_content=_base_template(content, heading),
    )


async def send_seller_settlement_link_email(
    *, seller: dict, statement_link: str, statement_number: str,
    listing_title: str, net_payout_display: str,
) -> Dict[str, Any]:
    """One seller email with ONE secure link to the seller's settlement
    statement. Mirrors the existing statement email tone; no new financial
    data, no attachment, just the secure signed link.
    """
    lang = _detect_language(seller)
    if lang == "fr":
        heading = "Votre relev&eacute; de r&egrave;glement est pr&ecirc;t"
        greeting = f"Bonjour {seller.get('name', '')},"
        body = (
            f"Le paiement pour <strong>{listing_title}</strong> a &eacute;t&eacute; confirm&eacute;. "
            f"Votre relev&eacute; de r&egrave;glement (n° <strong>{statement_number}</strong>) "
            f"est disponible via le lien s&eacute;curis&eacute; ci-dessous."
        )
        net_label = f"Versement net&nbsp;: <strong>{net_payout_display}</strong>"
        cta = "Consulter mon relev&eacute;"
        note = ("Ce lien est priv&eacute; et sp&eacute;cifique &agrave; votre compte. "
                "Veuillez ne pas le partager.")
        subject = f"BidVex — Votre relev&eacute; de r&egrave;glement — {listing_title}"
    else:
        heading = "Your settlement statement is ready"
        greeting = f"Hi {seller.get('name', '')},"
        body = (
            f"Payment for <strong>{listing_title}</strong> has been confirmed. "
            f"Your settlement statement (No <strong>{statement_number}</strong>) "
            f"is available via the secure link below."
        )
        net_label = f"Net payout: <strong>{net_payout_display}</strong>"
        cta = "View my statement"
        note = "This link is private and specific to your account. Please do not share it."
        subject = f"BidVex — Your settlement statement — {listing_title}"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #0f172a;">{heading}</h2>
    <p style="color: #475569; line-height: 1.6;">{greeting}</p>
    <p style="color: #475569; line-height: 1.6;">{body}</p>
    <p style="color: #0f172a; font-size: 15px; margin: 20px 0;">{net_label}</p>
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
      <tr><td align="center" style="background-color: #0B2545; padding: 14px 30px; border-radius: 8px;">
        <a href="{statement_link}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px;" data-testid="seller-final-statement-link">{cta}</a>
      </td></tr>
    </table>
    <p style="color: #94a3b8; font-size: 12px; line-height: 1.5; margin-top: 24px;">{note}</p>
    """
    return await _send_via_unified(
        to_email=seller["email"],
        subject=subject,
        html_content=_base_template(content, heading),
    )
