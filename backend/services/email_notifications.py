"""
BidVex Email Notification Service
Sends transactional emails for vehicle auctions
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Email configuration
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@bidvex.com")
FROM_NAME = os.environ.get("SENDGRID_FROM_NAME", "BidVex")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://www.bidvex.com")

# Check if SendGrid is available
SENDGRID_AVAILABLE = False
sg = None

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType, Disposition
    if SENDGRID_API_KEY and SENDGRID_API_KEY != "SG.your-actual-sendgrid-key-here":
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        SENDGRID_AVAILABLE = True
        logger.info("SendGrid email service initialized")
    else:
        logger.warning("SendGrid API key not configured - emails will be logged only")
except ImportError:
    logger.warning("SendGrid not installed - emails will be logged only")


def _format_currency(amount) -> str:
    """Format amount as currency"""
    return f"${float(amount):,.2f}"


def _format_date(dt) -> str:
    """Format datetime for display"""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
    return dt.strftime("%B %d, %Y at %I:%M %p")


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    attachments: List[Dict] = None
) -> Dict[str, Any]:
    """
    Send email via SendGrid
    
    Falls back to logging if SendGrid is not available
    """
    if not SENDGRID_AVAILABLE:
        logger.info(f"[EMAIL LOG] To: {to_email}, Subject: {subject}")
        logger.debug(f"[EMAIL CONTENT] {html_content[:500]}...")
        return {"status": "logged", "message": "SendGrid not configured - email logged"}
    
    try:
        message = Mail(
            from_email=Email(FROM_EMAIL, FROM_NAME),
            to_emails=To(to_email),
            subject=subject,
            html_content=Content("text/html", html_content)
        )
        
        # Add attachments if any
        if attachments:
            for att in attachments:
                attachment = Attachment(
                    FileContent(att["content"]),
                    FileName(att["filename"]),
                    FileType(att["type"]),
                    Disposition("attachment")
                )
                message.add_attachment(attachment)
        
        logger.info(f"[EMAIL_DEBUG] Sending email to: {to_email} | Subject: {subject} | From: {FROM_EMAIL}")
        response = sg.send(message)
        
        logger.info(f"[EMAIL_DEBUG] SendGrid response for {to_email}: status_code={response.status_code}")
        
        return {
            "status": "sent",
            "status_code": response.status_code,
            "to": to_email,
            "subject": subject
        }
    except Exception as e:
        logger.error(f"[EMAIL_DEBUG] FAILED to send email to {to_email}: {e}")
        return {"status": "error", "message": str(e)}


# ===== EMAIL TEMPLATES =====

def _base_template(content: str, title: str = "BidVex Notification") -> str:
    """Base HTML email template"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f1f5f9;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f1f5f9; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="background-color: #2563eb; padding: 30px; border-radius: 12px 12px 0 0;">
                                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: bold;">
                                    🚗 BidVex Vehicle Auctions
                                </h1>
                            </td>
                        </tr>
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px 30px;">
                                {content}
                            </td>
                        </tr>
                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #f8fafc; padding: 20px 30px; border-radius: 0 0 12px 12px; border-top: 1px solid #e2e8f0;">
                                <p style="margin: 0; font-size: 12px; color: #64748b; text-align: center;">
                                    © 2026 BidVex Inc. All rights reserved.<br>
                                    <a href="{FRONTEND_URL}/privacy-policy" style="color: #2563eb;">Privacy Policy</a> | 
                                    <a href="{FRONTEND_URL}/terms-of-service" style="color: #2563eb;">Terms of Service</a>
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """


# ===== INVOICE EMAILS =====


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
    <td style="background:linear-gradient(135deg,#1e40af 0%,#2563eb 100%);padding:28px 32px;text-align:center;">
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
          <td style="background:linear-gradient(135deg,#1e40af 0%,#2563eb 100%);border-radius:12px;padding:18px 48px;">
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

    result = await send_email(
        to_email=user_email,
        subject="Welcome to the BidVex Ecosystem! / Bienvenue dans l'écosystème BidVex !",
        html_content=html
    )

    logger.info(f"[EMAIL_DEBUG] Welcome Email result for {user_email}: {result}")
    return result

async def send_invoice_created_email(invoice: Dict[str, Any]) -> Dict[str, Any]:
    """Send email when a new invoice is generated"""
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #1e293b;">Invoice Generated</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Congratulations! Your winning bid has been processed. Here are your invoice details:
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #f8fafc; border-radius: 8px; padding: 20px;">
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 8px 0;"><strong>Invoice #:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{invoice.get('invoice_number', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>Vehicle:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{invoice.get('vehicle_title', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>Hammer Price:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{_format_currency(invoice.get('hammer_price', 0))}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>Total Due:</strong></td>
                <td style="padding: 8px 0; text-align: right; font-size: 18px; color: #2563eb; font-weight: bold;">
                    {_format_currency(invoice.get('total_amount', 0))}
                </td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>Due Date:</strong></td>
                <td style="padding: 8px 0; text-align: right; color: #f59e0b;">
                    {_format_date(invoice.get('due_at', invoice.get('payment_deadline')))}
                </td>
            </tr>
        </table>
    </td></tr></table>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #2563eb; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/invoices/{invoice.get('id')}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">View & Pay Invoice</a>
            </td>
        </tr>
    </table>
    
    <p style="color: #64748b; font-size: 13px; line-height: 1.6;">
        Payment is due within 14 days. Late payments may incur a 2% monthly penalty.
    </p>
    """
    
    return await send_email(
        to_email=invoice.get('buyer_email'),
        subject=f"Invoice #{invoice.get('invoice_number')} - {invoice.get('vehicle_title')}",
        html_content=_base_template(content, "Invoice Generated")
    )


async def send_payment_confirmation_email(invoice: Dict[str, Any]) -> Dict[str, Any]:
    """Send email when payment is received"""
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">✓ Payment Received</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Thank you! Your payment has been successfully processed.
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #d1fae5; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">        <p style="margin: 0; color: #065f46; font-size: 14px;">Payment Confirmed</p>
        <p style="margin: 10px 0 0 0; color: #065f46; font-size: 28px; font-weight: bold;">
            {_format_currency(invoice.get('paid_amount', invoice.get('total_amount', 0)))}
        </p></td></tr></table>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #f8fafc; border-radius: 8px; padding: 20px;">
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 8px 0;"><strong>Invoice #:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{invoice.get('invoice_number', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>Vehicle:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{invoice.get('vehicle_title', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>Payment Date:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{_format_date(invoice.get('paid_at', datetime.now(timezone.utc)))}</td>
            </tr>
        </table>
    </td></tr></table>
    
    <p style="color: #475569; line-height: 1.6;">
        The seller has been notified and will coordinate vehicle pickup/delivery with you.
    </p>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #f1f5f9; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/invoices/{invoice.get('id')}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">View Receipt</a>
            </td>
        </tr>
    </table>
    """
    
    return await send_email(
        to_email=invoice.get('buyer_email'),
        subject=f"Payment Confirmed - Invoice #{invoice.get('invoice_number')}",
        html_content=_base_template(content, "Payment Confirmed")
    )


async def send_invoice_overdue_email(invoice: Dict[str, Any], days_overdue: int) -> Dict[str, Any]:
    """Send reminder for overdue invoice"""
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #dc2626;">⚠️ Payment Overdue</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Your invoice payment is now <strong>{days_overdue} days overdue</strong>. 
        Please make payment immediately to avoid additional penalties.
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 20px;">
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 8px 0;"><strong>Invoice #:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{invoice.get('invoice_number', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>Original Amount:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{_format_currency(invoice.get('total_amount', 0))}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>Late Penalty:</strong></td>
                <td style="padding: 8px 0; text-align: right; color: #dc2626;">
                    +{_format_currency(invoice.get('penalty_amount', 0))}
                </td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>Total Due Now:</strong></td>
                <td style="padding: 8px 0; text-align: right; font-size: 18px; color: #dc2626; font-weight: bold;">
                    {_format_currency(invoice.get('total_amount', 0) + invoice.get('penalty_amount', 0))}
                </td>
            </tr>
        </table>
    </td></tr></table>
    
    <p style="color: #991b1b; font-size: 13px; line-height: 1.6; background-color: #fef2f2; padding: 15px; border-radius: 8px;">
        <strong>Warning:</strong> Continued non-payment may result in account suspension and 
        additional collection actions.
    </p>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #dc2626; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/invoices/{invoice.get('id')}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">Pay Now</a>
            </td>
        </tr>
    </table>
    """
    
    return await send_email(
        to_email=invoice.get('buyer_email'),
        subject=f"⚠️ OVERDUE: Invoice #{invoice.get('invoice_number')} - Action Required",
        html_content=_base_template(content, "Payment Overdue")
    )


# ===== DOCUMENT EMAILS =====

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
    
    return await send_email(
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
    
    return await send_email(
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
    
    return await send_email(
        to_email=user_email,
        subject="🎉 Your Seller Account is Approved!",
        html_content=_base_template(content, "Seller Account Approved")
    )


# ===== AUCTION EMAILS =====
# Note: send_auction_won_email is defined further below (unified signature
# supporting both vehicle and non-vehicle auctions with EN/FR legal text).


async def send_auction_sold_email(
    seller_email: str,
    seller_name: str,
    vehicle_title: str,
    final_price: float,
    commission: float,
    net_payout: float
) -> Dict[str, Any]:
    """Send email to seller when vehicle is sold"""
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">🎉 Your Vehicle Sold!</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Congratulations {seller_name}!
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Your vehicle has been successfully sold at auction:
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #d1fae5; border-radius: 8px; padding: 25px; margin: 20px 0; text-align: center;">        <p style="margin: 0; color: #065f46; font-size: 18px; font-weight: bold;">
            {vehicle_title}
        </p></td></tr></table>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #f8fafc; border-radius: 8px; padding: 20px;">
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 8px 0;"><strong>Sale Price:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{_format_currency(final_price)}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>BidVex Commission:</strong></td>
                <td style="padding: 8px 0; text-align: right; color: #dc2626;">-{_format_currency(commission)}</td>
            </tr>
            <tr style="border-top: 2px solid #2563eb;">
                <td style="padding: 12px 0;"><strong>Your Payout:</strong></td>
                <td style="padding: 12px 0; text-align: right; font-size: 20px; color: #10b981; font-weight: bold;">
                    {_format_currency(net_payout)}
                </td>
            </tr>
        </table>
    </td></tr></table>
    
    <p style="color: #475569; line-height: 1.6;">
        Your payout will be processed once the buyer completes payment (typically within 14 days).
    </p>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #10b981; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/seller/financials" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">View Financials</a>
            </td>
        </tr>
    </table>
    """
    
    return await send_email(
        to_email=seller_email,
        subject=f"🎉 Sold! {vehicle_title} - {_format_currency(final_price)}",
        html_content=_base_template(content, "Vehicle Sold")
    )


# ===== BID NOTIFICATION EMAILS =====

async def send_bid_placed_email(
    bidder_email: str,
    bidder_name: str,
    listing_title: str,
    bid_amount: float,
    listing_id: str,
    auction_end_date: str,
    is_leading: bool = True
) -> Dict[str, Any]:
    """
    Send confirmation email when user places a bid
    
    Args:
        bidder_email: Email of the bidder
        bidder_name: Name of the bidder
        listing_title: Title of the item
        bid_amount: Amount of the bid placed
        listing_id: ID of the listing for link
        auction_end_date: When the auction ends
        is_leading: Whether this bid is currently leading
    """
    status_color = "#10b981" if is_leading else "#f59e0b"
    status_text = "You're in the lead!" if is_leading else "Your bid was placed"
    status_message = (
        "You are currently the highest bidder. We'll notify you if someone outbids you."
        if is_leading else 
        "Your bid has been recorded, but you're not currently in the lead."
    )
    
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: {status_color};">✓ Bid Confirmed</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Hi {bidder_name},
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Your bid has been successfully placed on:
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #eff6ff; border: 2px solid #2563eb; border-radius: 8px; padding: 25px;">
        <p style="margin: 0 0 15px 0; color: #1e40af; font-size: 18px; font-weight: bold;">
            {listing_title}
        </p>
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 6px 0;"><strong>Your Bid:</strong></td>
                <td style="padding: 6px 0; text-align: right; font-size: 20px; color: #2563eb; font-weight: bold;">
                    {_format_currency(bid_amount)}
                </td>
            </tr>
            <tr>
                <td style="padding: 6px 0;"><strong>Auction Ends:</strong></td>
                <td style="padding: 6px 0; text-align: right; color: #dc2626;">
                    {_format_date(auction_end_date)}
                </td>
            </tr>
        </table>
    </td></tr></table>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: {'#d1fae5' if is_leading else '#fef3c7'}; border-radius: 8px; padding: 15px; margin: 20px 0; text-align: center;">        <p style="margin: 0; color: {'#065f46' if is_leading else '#92400e'}; font-size: 16px; font-weight: bold;">
            {status_text}
        </p>
        <p style="margin: 8px 0 0 0; color: {'#065f46' if is_leading else '#92400e'}; font-size: 13px;">
            {status_message}
        </p></td></tr></table>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #2563eb; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/listing/{listing_id}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">View Auction</a>
            </td>
        </tr>
    </table>
    
    <p style="color: #64748b; font-size: 13px; line-height: 1.6;">
        <strong>Tip:</strong> Add this item to your watchlist to get notifications when the auction is about to end.
    </p>
    """
    
    return await send_email(
        to_email=bidder_email,
        subject=f"✓ Bid Confirmed: {_format_currency(bid_amount)} on {listing_title}",
        html_content=_base_template(content, "Bid Confirmed")
    )


async def send_outbid_email(
    user_email: str,
    user_name: str,
    listing_title: str,
    their_bid: float,
    new_high_bid: float,
    listing_id: str,
    auction_end_date: str
) -> Dict[str, Any]:
    """
    Send notification email when user is outbid
    
    Args:
        user_email: Email of the outbid user
        user_name: Name of the outbid user
        listing_title: Title of the item
        their_bid: The user's previous bid amount
        new_high_bid: The new highest bid
        listing_id: ID of the listing for link
        auction_end_date: When the auction ends
    """
    suggested_bid = new_high_bid + 1  # Minimum increment
    
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #dc2626;">🔔 You've Been Outbid!</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Hi {user_name},
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Someone has placed a higher bid on an item you're watching:
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #fef2f2; border: 2px solid #dc2626; border-radius: 8px; padding: 25px;">
        <p style="margin: 0 0 15px 0; color: #991b1b; font-size: 18px; font-weight: bold;">
            {listing_title}
        </p>
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 6px 0;"><strong>Your Bid:</strong></td>
                <td style="padding: 6px 0; text-align: right; text-decoration: line-through; color: #94a3b8;">
                    {_format_currency(their_bid)}
                </td>
            </tr>
            <tr>
                <td style="padding: 6px 0;"><strong>New High Bid:</strong></td>
                <td style="padding: 6px 0; text-align: right; font-size: 20px; color: #dc2626; font-weight: bold;">
                    {_format_currency(new_high_bid)}
                </td>
            </tr>
            <tr>
                <td style="padding: 6px 0;"><strong>Auction Ends:</strong></td>
                <td style="padding: 6px 0; text-align: right; color: #f59e0b;">
                    {_format_date(auction_end_date)}
                </td>
            </tr>
        </table>
    </td></tr></table>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #eff6ff; border-radius: 8px; padding: 15px; margin: 20px 0; text-align: center;">        <p style="margin: 0; color: #1e40af; font-size: 14px;">
            <strong>Suggested next bid:</strong> {_format_currency(suggested_bid)} or higher
        </p></td></tr></table>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #dc2626; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/listing/{listing_id}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">Bid Again Now</a>
            </td>
        </tr>
    </table>
    
    <p style="color: #64748b; font-size: 13px; line-height: 1.6;">
        Don't miss out! Place a higher bid to get back in the lead.
    </p>
    """
    
    return await send_email(
        to_email=user_email,
        subject=f"🔔 Outbid Alert: {listing_title} - Bid Now!",
        html_content=_base_template(content, "You've Been Outbid")
    )


# ===== SUBSCRIPTION EMAILS =====

async def send_subscription_reminder_email(
    user_email: str,
    user_name: str,
    plan: str,
    days_remaining: int,
    end_date: str
) -> Dict[str, Any]:
    """Send reminder email 3 days before subscription expires"""
    plan_name = plan.title()
    
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #f59e0b;">⏰ Subscription Expiring Soon</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Hi {user_name},
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Your <strong>{plan_name}</strong> subscription will expire in <strong>{days_remaining} days</strong>.
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 20px;">
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 8px 0;"><strong>Current Plan:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{plan_name}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>Expires On:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{end_date}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>Days Remaining:</strong></td>
                <td style="padding: 8px 0; text-align: right; color: #d97706; font-weight: bold;">{days_remaining}</td>
            </tr>
        </table>
    </td></tr></table>
    
    <p style="color: #475569; line-height: 1.6;">
        To continue enjoying {plan_name} benefits (reduced fees, priority support, and more), 
        please contact support to renew your subscription.
    </p>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #f59e0b; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/settings/subscription" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">View Subscription</a>
            </td>
        </tr>
    </table>
    
    <p style="color: #64748b; font-size: 13px; line-height: 1.6;">
        If your subscription expires, your account will be downgraded to the Free plan automatically.
    </p>
    """
    
    return await send_email(
        to_email=user_email,
        subject=f"⏰ Your {plan_name} Subscription Expires in {days_remaining} Days",
        html_content=_base_template(content, "Subscription Reminder")
    )


async def send_subscription_expired_email(
    user_email: str,
    user_name: str,
    previous_plan: str
) -> Dict[str, Any]:
    """Send confirmation email when subscription expires"""
    plan_name = previous_plan.title()
    
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #64748b;">Subscription Expired</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Hi {user_name},
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Your <strong>{plan_name}</strong> subscription has expired. Your account has been 
        downgraded to the <strong>Free</strong> plan.
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #f1f5f9; border-radius: 8px; padding: 20px; margin: 20px 0;">        <h4 style="margin: 0 0 15px 0; color: #334155;">What's Changed:</h4>
        <ul style="margin: 0; padding: 0 0 0 20px; color: #475569; line-height: 1.8;">
            <li>Monthly listing limit reduced</li>
            <li>Buyer premium discounts removed</li>
            <li>Seller commission discounts removed</li>
            <li>Priority support no longer available</li>
        </ul></td></tr></table>
    
    <p style="color: #475569; line-height: 1.6;">
        Don't worry! Your existing listings will remain active. To regain your {plan_name} benefits, 
        please contact support to renew your subscription.
    </p>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #1e3a5f; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/settings/subscription" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">Renew Subscription</a>
            </td>
        </tr>
    </table>
    
    <p style="color: #64748b; font-size: 13px; line-height: 1.6;">
        Thank you for being a {plan_name} member. We hope to see you back soon!
    </p>
    """
    
    return await send_email(
        to_email=user_email,
        subject=f"Your {plan_name} Subscription Has Expired",
        html_content=_base_template(content, "Subscription Expired")
    )


async def send_subscription_upgraded_email(
    user_email: str,
    user_name: str,
    new_plan: str,
    end_date: str
) -> Dict[str, Any]:
    """Send confirmation when subscription is upgraded/changed by admin"""
    plan_name = new_plan.title()
    
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">🎉 Subscription Updated</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Hi {user_name},
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Great news! Your subscription has been updated to <strong>{plan_name}</strong>.
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #d1fae5; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">        <p style="margin: 0; color: #065f46; font-size: 24px; font-weight: bold;">
            {plan_name}
        </p>
        <p style="margin: 10px 0 0 0; color: #10b981; font-size: 14px;">
            Active until {end_date}
        </p></td></tr></table>
    
    <h4 style="margin: 25px 0 15px 0; color: #334155;">Your {plan_name} Benefits:</h4>
    <ul style="margin: 0; padding: 0 0 0 20px; color: #475569; line-height: 1.8;">
        {"<li>Reduced buyer premium fees</li>" if new_plan in ['premium', 'vip'] else ""}
        {"<li>Lower seller commission rates</li>" if new_plan in ['premium', 'vip'] else ""}
        {"<li>Priority customer support</li>" if new_plan in ['premium', 'vip'] else ""}
        {"<li>Advanced analytics dashboard</li>" if new_plan == 'vip' else ""}
        {"<li>Dedicated account manager</li>" if new_plan == 'vip' else ""}
    </ul>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #10b981; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/marketplace" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">Start Exploring</a>
            </td>
        </tr>
    </table>
    """
    
    return await send_email(
        to_email=user_email,
        subject=f"🎉 Welcome to {plan_name}!",
        html_content=_base_template(content, "Subscription Updated")
    )



# ========== AUCTION WINNER EMAILS ==========

async def send_auction_won_email(
    to_email: str = "",
    to_name: str = "",
    auction_id: str = "",
    item_name: str = "",
    hammer_price: float = 0.0,
    platform_fee: float = 0.0,
    seller_name: str = "",
    seller_contact: str = "",
    is_vehicle: bool = False,
    is_cross_border: bool = False,
    buyer_province: str = "QC",
    payment_deadline: Optional[str] = None,
    # --- Back-compat aliases (older callers) ---
    winner_email: Optional[str] = None,
    winner_name: Optional[str] = None,
    item_title: Optional[str] = None,
    final_price: Optional[float] = None,
    listing_id: Optional[str] = None,
    buyer_email: Optional[str] = None,
    buyer_name: Optional[str] = None,
    vehicle_title: Optional[str] = None,
    invoice_id: Optional[str] = None,
    buyers_premium_rate: Optional[float] = None,  # noqa: ARG001 — legacy, ignored
) -> Dict[str, Any]:
    """
    Send 'You Won!' email to auction winner.

    Legal-compliant behavior:
      - For vehicles (is_vehicle=True), injects a bilingual EN/FR notice that
        the hammer price is settled DIRECTLY between buyer and seller and that
        BidVex only charges the 2.5% platform fee + taxes.
      - For non-vehicles, shows the standard checkout CTA (BidVex collects full
        hammer via Stripe Connect).
      - For cross-border (is_cross_border=True), appends the cross-border
        compliance notice in both languages.
    """
    # Back-compat normalization
    to_email = to_email or winner_email or buyer_email or ""
    to_name = to_name or winner_name or buyer_name or ""
    item_name = item_name or item_title or vehicle_title or "Item"
    auction_id = auction_id or listing_id or invoice_id or ""
    if hammer_price in (None, 0.0) and final_price is not None:
        hammer_price = final_price

    checkout_url = f"{FRONTEND_URL}/checkout/{auction_id}"
    invoice_url = f"{FRONTEND_URL}/vehicle-auctions/invoices/{auction_id}"
    hammer_display = _format_currency(hammer_price)
    fee_display = _format_currency(platform_fee)
    # French Canadian currency: "10 000,00 $" — suffix style
    def _fr_currency(amount):
        s = f"{float(amount):,.2f}"  # 10,000.00
        return s.replace(",", " ").replace(".", ",") + " $"
    hammer_display_fr = _fr_currency(hammer_price)
    fee_display_fr = _fr_currency(platform_fee)
    deadline_display = _format_date(payment_deadline) if payment_deadline else "14 days"

    # ── Vehicle-specific payment notice (EN + FR) ──
    vehicle_notice = ""
    if is_vehicle:
        seller_contact_line = seller_contact or "Available in your BidVex dashboard"
        seller_display = seller_name or "Seller"
        vehicle_notice = f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;">
      <tr><td style="background-color: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 8px; padding: 20px;">
        <p style="margin: 0 0 10px 0; color: #92400e; font-weight: bold; font-size: 15px;">
          ⚠️ VEHICLE PAYMENT NOTICE
        </p>
        <p style="margin: 0 0 10px 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          Payment for the vehicle (<strong>{hammer_display}</strong>) is arranged directly
          between you and the seller. BidVex does not process or hold vehicle purchase funds.
        </p>
        <p style="margin: 0 0 10px 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          <strong>Seller Contact:</strong> {seller_display} | {seller_contact_line}
        </p>
        <p style="margin: 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          BidVex Platform Fee of 2.5% (<strong>{fee_display}</strong>) has been charged
          separately to your card on file. This is the only amount BidVex collects.
        </p>
      </td></tr>
    </table>

    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;">
      <tr><td style="background-color: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 8px; padding: 20px;">
        <p style="margin: 0 0 10px 0; color: #92400e; font-weight: bold; font-size: 15px;">
          ⚠️ AVIS DE PAIEMENT DU VÉHICULE
        </p>
        <p style="margin: 0 0 10px 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          Le paiement du véhicule (<strong>{hammer_display_fr}</strong>) est organisé
          directement entre vous et le vendeur. BidVex ne traite pas et ne détient pas
          les fonds d'achat de véhicules.
        </p>
        <p style="margin: 0 0 10px 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          <strong>Contact du vendeur :</strong> {seller_display} | {seller_contact_line}
        </p>
        <p style="margin: 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          Les frais de plateforme BidVex de 2,5 % (<strong>{fee_display_fr}</strong>) ont été
          débités séparément de votre carte enregistrée. C'est le seul montant que BidVex perçoit.
        </p>
      </td></tr>
    </table>
    """

    # ── Cross-border compliance notice (EN + FR) ──
    cross_border_notice = ""
    if is_cross_border:
        cross_border_notice = f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;">
      <tr><td style="background-color: #eff6ff; border-left: 4px solid #2563eb; border-radius: 8px; padding: 20px;">
        <p style="margin: 0 0 8px 0; color: #1e40af; font-weight: bold; font-size: 14px;">
          🌐 Cross-Border Purchase Notice
        </p>
        <p style="margin: 0 0 8px 0; color: #1e293b; font-size: 13px; line-height: 1.6;">
          This purchase crosses provincial or international borders. You may be responsible
          for additional import duties, brokerage, GST/HST/QST on import, and compliance
          with your province's ({buyer_province}) vehicle registration rules.
        </p>
        <p style="margin: 0; color: #1e293b; font-size: 13px; line-height: 1.6;">
          Cet achat franchit des frontières provinciales ou internationales. Vous pourriez
          être responsable des droits d'importation, du courtage, de la TPS/TVH/TVQ à
          l'importation, et de la conformité aux règles d'immatriculation de votre
          province ({buyer_province}).
        </p>
      </td></tr>
    </table>
    """

    # ── CTA button ──
    cta_url = invoice_url if is_vehicle else checkout_url
    cta_label = "View Fee Invoice" if is_vehicle else "Complete Payment"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">Congratulations! You Won!</h2>

    <p style="color: #475569; line-height: 1.6;">
        Hi {to_name},
    </p>

    <p style="color: #475569; line-height: 1.6;">
        You've won the auction for <strong>{item_name}</strong>!
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
            <td style="background-color: #ecfdf5; border-radius: 8px; padding: 20px; margin: 20px 0;">
                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td style="color: #065f46; font-size: 14px; padding: 4px 0;">Item:</td>
                        <td style="color: #065f46; font-size: 14px; font-weight: bold; text-align: right;">{item_name}</td>
                    </tr>
                    <tr>
                        <td style="color: #065f46; font-size: 14px; padding: 4px 0;">Winning Bid:</td>
                        <td style="color: #065f46; font-size: 24px; font-weight: bold; text-align: right;">{hammer_display}</td>
                    </tr>
                    <tr>
                        <td style="color: #065f46; font-size: 14px; padding: 4px 0;">Payment Due By:</td>
                        <td style="color: #dc2626; font-size: 14px; font-weight: bold; text-align: right;">{deadline_display}</td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
    {vehicle_notice}
    {cross_border_notice}

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #10b981; padding: 14px 30px; border-radius: 8px;">
                <a href="{cta_url}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;" data-testid="auction-won-cta">{cta_label}</a>
            </td>
        </tr>
    </table>

    <p style="color: #94a3b8; font-size: 12px; text-align: center;">
        If the button doesn't work, copy this link: {cta_url}
    </p>
    """

    subject = (
        f"You Won! Vehicle {item_name} — Fee Invoice Ready"
        if is_vehicle
        else f"You Won! Complete Payment for {item_name}"
    )

    return await send_email(
        to_email=to_email,
        subject=subject,
        html_content=_base_template(content, "Auction Won")
    )


async def send_payment_reminder_email(
    winner_email: str,
    winner_name: str,
    item_title: str,
    final_price: float,
    listing_id: str,
    days_remaining: int,
    payment_deadline: str,
) -> Dict[str, Any]:
    """Send payment reminder email (day 10)"""
    checkout_url = f"{FRONTEND_URL}/checkout/{listing_id}"
    price_display = _format_currency(final_price)
    deadline_display = _format_date(payment_deadline) if payment_deadline else "soon"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #f59e0b;">Payment Reminder</h2>

    <p style="color: #475569; line-height: 1.6;">
        Hi {winner_name},
    </p>

    <p style="color: #475569; line-height: 1.6;">
        This is a reminder that your payment for <strong>{item_title}</strong> is due in <strong>{days_remaining} days</strong>.
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
            <td style="background-color: #fffbeb; border: 1px solid #fbbf24; border-radius: 8px; padding: 20px;">
                <p style="margin: 0 0 8px 0; color: #92400e; font-weight: bold;">Payment Details</p>
                <p style="margin: 0; color: #92400e;">Amount: <strong>{price_display}</strong> (+ applicable fees &amp; taxes)</p>
                <p style="margin: 8px 0 0 0; color: #dc2626; font-weight: bold;">Deadline: {deadline_display}</p>
            </td>
        </tr>
    </table>

    <p style="color: #475569; line-height: 1.6; margin-top: 20px;">
        After the deadline, a <strong>2% monthly late penalty</strong> will be applied to your balance.
    </p>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #f59e0b; padding: 14px 30px; border-radius: 8px;">
                <a href="{checkout_url}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">Pay Now</a>
            </td>
        </tr>
    </table>
    """

    return await send_email(
        to_email=winner_email,
        subject=f"Payment Reminder: {item_title} - {days_remaining} Days Left",
        html_content=_base_template(content, "Payment Reminder")
    )


async def send_payment_overdue_email(
    winner_email: str,
    winner_name: str,
    item_title: str,
    final_price: float,
    listing_id: str,
    penalty_amount: float,
    total_with_penalty: float,
) -> Dict[str, Any]:
    """Send payment overdue notice with penalty (day 14+)"""
    checkout_url = f"{FRONTEND_URL}/checkout/{listing_id}"
    price_display = _format_currency(final_price)
    penalty_display = _format_currency(penalty_amount)
    total_display = _format_currency(total_with_penalty)

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #dc2626;">Payment Overdue</h2>

    <p style="color: #475569; line-height: 1.6;">
        Hi {winner_name},
    </p>

    <p style="color: #475569; line-height: 1.6;">
        Your payment for <strong>{item_title}</strong> is now <strong>overdue</strong>. A late penalty has been applied.
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
            <td style="background-color: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px; padding: 20px;">
                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td style="color: #991b1b; font-size: 14px; padding: 4px 0;">Original Amount:</td>
                        <td style="color: #991b1b; font-size: 14px; text-align: right;">{price_display}</td>
                    </tr>
                    <tr>
                        <td style="color: #dc2626; font-size: 14px; padding: 4px 0;">Late Penalty (2%/month):</td>
                        <td style="color: #dc2626; font-size: 14px; font-weight: bold; text-align: right;">+{penalty_display}</td>
                    </tr>
                    <tr>
                        <td colspan="2" style="border-top: 1px solid #fca5a5; padding-top: 8px; margin-top: 8px;"></td>
                    </tr>
                    <tr>
                        <td style="color: #991b1b; font-size: 16px; font-weight: bold; padding: 4px 0;">New Total Due:</td>
                        <td style="color: #dc2626; font-size: 20px; font-weight: bold; text-align: right;">{total_display}</td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>

    <p style="color: #475569; line-height: 1.6; margin-top: 20px;">
        Please complete your payment immediately to avoid further penalties. The late penalty increases by 2% for each additional month.
    </p>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #dc2626; padding: 14px 30px; border-radius: 8px;">
                <a href="{checkout_url}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">Pay Now</a>
            </td>
        </tr>
    </table>
    """

    return await send_email(
        to_email=winner_email,
        subject=f"OVERDUE: Payment Required for {item_title}",
        html_content=_base_template(content, "Payment Overdue")
    )


# ========== REVIEW REQUEST EMAIL ==========

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

    return await send_email(
        to_email=buyer_email,
        subject=f"How was your purchase of {item_title}?",
        html_content=_base_template(content, "Leave a Review")
    )


# ============================================================================
# STORAGE UNIT AUCTIONS — bilingual EN+FR (iteration 169)
# ============================================================================
import os as _os
from datetime import datetime as _dt


def _storage_panel(title_en: str, title_fr: str, body_en: str, body_fr: str, cta_url: str = "", cta_en: str = "", cta_fr: str = "") -> str:
    cta_block = ""
    if cta_url and cta_en:
        cta_block = f"""
        <div style="text-align:center;margin:20px 0;">
          <a href="{cta_url}" style="background:#0F3060;color:#fff;text-decoration:none;font-weight:700;padding:12px 26px;border-radius:24px;display:inline-block;">
            {cta_en} / {cta_fr}
          </a>
        </div>
        """
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;background:#fff;">
      <div style="background:linear-gradient(135deg,#0B2545,#0F3060);color:#fff;padding:24px;border-radius:12px;margin-bottom:16px;">
        <p style="margin:0;font-size:11px;letter-spacing:2px;opacity:0.7;">🔒 BIDVEX STORAGE AUCTIONS</p>
        <h2 style="margin:6px 0 0 0;font-size:22px;">{title_en}</h2>
        <p style="margin:4px 0 0 0;font-size:14px;color:#3FB4CB;">{title_fr}</p>
      </div>
      <div style="color:#1e293b;font-size:14px;line-height:1.55;">
        <p><strong>EN:</strong> {body_en}</p>
        <hr style="border:none;border-top:1px solid #e5e7eb;margin:12px 0;"/>
        <p><strong>FR:</strong> {body_fr}</p>
      </div>
      {cta_block}
      <p style="font-size:11px;color:#94a3b8;text-align:center;margin-top:24px;">BidVex Canada — bilingual auction marketplace</p>
    </div>
    """


async def send_storage_bid_placed_email(buyer: dict, auction: dict, bid_state: dict) -> bool:
    if not buyer or not buyer.get("email"):
        return False
    a_id = (auction or {}).get("id", "")[:8]
    cur = bid_state.get("current_bid", 0)
    winning = bid_state.get("you_are_winning")
    body_en = (
        f"Your bid was placed on storage unit auction <strong>#{a_id}</strong>. "
        f"Current leading bid: <strong>${cur:,.2f}</strong>. "
        + ("You are currently winning. " if winning else "You are NOT currently winning — your maximum was outbid. ")
    )
    body_fr = (
        f"Votre offre a été placée sur l'enchère d'unité d'entreposage <strong>#{a_id}</strong>. "
        f"Offre actuelle en tête : <strong>{cur:,.2f} $</strong>. "
        + ("Vous êtes en tête. " if winning else "Vous N'êtes PAS en tête — votre maximum a été surenchéri. ")
    )
    return await send_email(
        to_email=buyer["email"],
        subject=f"Bid placed — Storage Auction #{a_id}",
        html_content=_storage_panel("Bid placed", "Offre placée", body_en, body_fr,
                                    cta_url=f"https://www.bidvex.com/storage-auctions/{auction.get('id','')}",
                                    cta_en="View auction", cta_fr="Voir l'enchère"),
    )


async def send_storage_outbid_email(buyer: dict, auction: dict, new_current: float) -> bool:
    if not buyer or not buyer.get("email"):
        return False
    a_id = (auction or {}).get("id", "")[:8]
    body_en = (
        f"You've been outbid on storage unit auction <strong>#{a_id}</strong>. "
        f"The leading bid is now <strong>${new_current:,.2f}</strong>. "
        f"Place a higher max bid to retake the lead."
    )
    body_fr = (
        f"Vous avez été surenchéri sur l'enchère d'unité d'entreposage <strong>#{a_id}</strong>. "
        f"L'offre en tête est maintenant <strong>{new_current:,.2f} $</strong>. "
        f"Placez une offre maximale plus élevée pour reprendre la tête."
    )
    return await send_email(
        to_email=buyer["email"],
        subject=f"⚠️ Outbid — Storage Auction #{a_id}",
        html_content=_storage_panel("You've been outbid", "Vous avez été surenchéri", body_en, body_fr,
                                    cta_url=f"https://www.bidvex.com/storage-auctions/{auction.get('id','')}",
                                    cta_en="Bid again", cta_fr="Enchérir à nouveau"),
    )


async def send_storage_auction_won_email(buyer: dict, auction: dict, facility: dict, pricing: dict = None) -> bool:
    """
    Bilingual winner email. Branches on auction.payment_method:
      • stripe   → BidVex charged buyer card (5% + stripe + tax); buyer pays hammer via Stripe to facility
      • cash     → buyer pays hammer CASH directly to facility
      • etransfer→ buyer sends Interac e-Transfer to facility's registered email

    Always includes a cleanup-deadline warning with forfeit clause.
    """
    if not buyer or not buyer.get("email"):
        return False

    unit = auction.get("unit_number", "—")
    bid = float(auction.get("winning_bid") or auction.get("current_bid") or 0)
    pm = (auction.get("payment_method") or "stripe").lower()
    fac_name = facility.get("company_name", "—")
    fac_contact = facility.get("contact_name", "—")
    fac_phone = facility.get("phone", "—")
    fac_email = facility.get("email", "—")
    pay_deadline = auction.get("payment_deadline") or auction.get("cleanup_deadline", "—")
    cleanup_deadline = auction.get("cleanup_deadline", "—")
    cleanup_deposit = float(auction.get("cleanup_deposit", 0) or 0)
    buyer_name = buyer.get("name") or buyer.get("full_name") or "—"

    # Optional BidVex charge (for Stripe path only)
    buyer_stripe_charge = 0.0
    if pricing and pricing.get("buyer_invoice"):
        # stripe path: platform_fee + stripe_recovery + tax (BidVex-collected portion)
        bi = pricing["buyer_invoice"]
        buyer_stripe_charge = float(bi.get("platform_fee", 0)) + float(bi.get("stripe_recovery", 0)) + float(bi.get("tax", 0))

    # ── Per-method body ──
    if pm == "stripe":
        body_en = (
            f"Congratulations! You won Unit <strong>#{unit}</strong> at <strong>{fac_name}</strong>.<br/>"
            f"Your winning bid: <strong>${bid:,.2f}</strong><br/><br/>"
            f"BidVex has charged your card <strong>${buyer_stripe_charge:,.2f}</strong> (platform fee + Stripe + taxes).<br/>"
            f"You must pay <strong>${bid:,.2f}</strong> to the facility via Stripe before <strong>{pay_deadline}</strong>.<br/><br/>"
            f"<strong>Facility contact:</strong> {fac_contact} | {fac_phone} | {fac_email}<br/>"
        )
        body_fr = (
            f"Félicitations! Vous avez remporté l'unité <strong>#{unit}</strong> à <strong>{fac_name}</strong>.<br/>"
            f"Votre offre gagnante : <strong>{bid:,.2f} $</strong><br/><br/>"
            f"BidVex a débité <strong>{buyer_stripe_charge:,.2f} $</strong> sur votre carte (frais de plateforme + Stripe + taxes).<br/>"
            f"Vous devez payer <strong>{bid:,.2f} $</strong> à la facilité via Stripe avant le <strong>{pay_deadline}</strong>.<br/><br/>"
            f"<strong>Contact facilité :</strong> {fac_contact} | {fac_phone} | {fac_email}<br/>"
        )
    elif pm == "cash":
        body_en = (
            f"Congratulations! You won Unit <strong>#{unit}</strong> at <strong>{fac_name}</strong> for "
            f"<strong>${bid:,.2f}</strong>.<br/><br/>"
            f"You must pay <strong>${bid:,.2f} CASH</strong> directly to the facility.<br/>"
            f"Contact the facility to arrange payment and pickup:<br/>"
            f"<strong>{fac_contact}</strong> | {fac_phone} | {fac_email}<br/>"
            f"<strong>Payment deadline:</strong> {pay_deadline}<br/>"
            f"<strong>Cleanup deadline:</strong> {cleanup_deadline}<br/>"
        )
        body_fr = (
            f"Félicitations! Vous avez remporté l'unité <strong>#{unit}</strong> à <strong>{fac_name}</strong> pour "
            f"<strong>{bid:,.2f} $</strong>.<br/><br/>"
            f"Vous devez payer <strong>{bid:,.2f} $ COMPTANT</strong> directement à la facilité.<br/>"
            f"Contactez la facilité pour organiser le paiement et le ramassage :<br/>"
            f"<strong>{fac_contact}</strong> | {fac_phone} | {fac_email}<br/>"
            f"<strong>Date limite de paiement :</strong> {pay_deadline}<br/>"
            f"<strong>Date limite de nettoyage :</strong> {cleanup_deadline}<br/>"
        )
    else:  # etransfer
        body_en = (
            f"Congratulations! You won Unit <strong>#{unit}</strong> at <strong>{fac_name}</strong> for "
            f"<strong>${bid:,.2f}</strong>.<br/><br/>"
            f"Send <strong>${bid:,.2f}</strong> via <strong>Interac e-Transfer</strong> to: <strong>{fac_email}</strong><br/>"
            f"<strong>Reference:</strong> BidVex Unit #{unit} — {buyer_name}<br/>"
            f"Contact the facility to confirm receipt:<br/>"
            f"<strong>{fac_contact}</strong> | {fac_phone}<br/>"
            f"<strong>Payment deadline:</strong> {pay_deadline}<br/>"
            f"<strong>Cleanup deadline:</strong> {cleanup_deadline}<br/>"
        )
        body_fr = (
            f"Félicitations! Vous avez remporté l'unité <strong>#{unit}</strong> à <strong>{fac_name}</strong> pour "
            f"<strong>{bid:,.2f} $</strong>.<br/><br/>"
            f"Envoyez <strong>{bid:,.2f} $</strong> par <strong>virement Interac</strong> à : <strong>{fac_email}</strong><br/>"
            f"<strong>Référence :</strong> BidVex Unité #{unit} — {buyer_name}<br/>"
            f"Contactez la facilité pour confirmer la réception :<br/>"
            f"<strong>{fac_contact}</strong> | {fac_phone}<br/>"
            f"<strong>Date limite de paiement :</strong> {pay_deadline}<br/>"
            f"<strong>Date limite de nettoyage :</strong> {cleanup_deadline}<br/>"
        )

    # ── Cleanup / forfeit notice (always appended, bilingual) ──
    pickup_code = auction.get("pickup_code")
    pickup_en = ""
    pickup_fr = ""
    if pickup_code:
        # Generate inline base64 QR image so it renders in every email client
        qr_img_tag = ""
        try:
            import base64 as _b64
            from routes.storage_auctions import _generate_pickup_qr_png_bytes
            qr_bytes = _generate_pickup_qr_png_bytes(pickup_code)
            qr_b64 = _b64.b64encode(qr_bytes).decode("ascii")
            qr_img_tag = (
                f"<div style='margin:12px auto;display:inline-block;background:#fff;"
                f"padding:10px;border-radius:8px;border:1px solid #fde68a'>"
                f"<img src='data:image/png;base64,{qr_b64}' alt='Pickup QR' "
                f"width='180' height='180' "
                f"style='display:block;width:180px;height:180px;image-rendering:pixelated'/>"
                f"</div>"
            )
        except Exception as e:
            logger.error(f"[STORAGE_EMAIL] QR embed failed: {e}")

        pickup_en = (
            f"<hr style='margin:16px 0;border:none;border-top:1px solid #e2e8f0'/>"
            f"<div style='background:#fef3c7;border:2px dashed #d97706;border-radius:10px;padding:16px;text-align:center;margin:12px 0'>"
            f"<div style='font-size:11px;letter-spacing:2px;color:#92400e;font-weight:700'>YOUR PICKUP CODE</div>"
            f"<div style='font-size:28px;font-weight:900;color:#78350f;letter-spacing:3px;font-family:monospace;margin-top:6px'>{pickup_code}</div>"
            f"{qr_img_tag}"
            f"<div style='font-size:11px;color:#92400e;margin-top:4px'>Scan at pickup · Show code to staff</div>"
            f"</div>"
            f"Present this code (or the QR) to facility staff when you arrive for pickup. "
            f"The facility will mark this code as used upon verification. "
            f"<strong>Do not share this code</strong> — it authorizes access to the unit."
        )
        pickup_fr = (
            f"<hr style='margin:16px 0;border:none;border-top:1px solid #e2e8f0'/>"
            f"<div style='background:#fef3c7;border:2px dashed #d97706;border-radius:10px;padding:16px;text-align:center;margin:12px 0'>"
            f"<div style='font-size:11px;letter-spacing:2px;color:#92400e;font-weight:700'>VOTRE CODE DE RÉCUPÉRATION</div>"
            f"<div style='font-size:28px;font-weight:900;color:#78350f;letter-spacing:3px;font-family:monospace;margin-top:6px'>{pickup_code}</div>"
            f"{qr_img_tag}"
            f"<div style='font-size:11px;color:#92400e;margin-top:4px'>Scanner à la récupération · Présentez le code</div>"
            f"</div>"
            f"Présentez ce code (ou le QR) au personnel de la facilité lors de votre arrivée. "
            f"La facilité marquera ce code comme utilisé après vérification. "
            f"<strong>Ne partagez pas ce code</strong> — il autorise l'accès à l'unité."
        )

    cleanup_en = (
        f"<hr style='margin:16px 0;border:none;border-top:1px solid #e2e8f0'/>"
        f"⚠️ <strong>IMPORTANT:</strong> You must completely empty the unit by "
        f"<strong>{cleanup_deadline}</strong>. Failure to empty the unit forfeits your "
        f"cleaning deposit of <strong>${cleanup_deposit:.2f}</strong> and will result in "
        f"account suspension.<br/>"
        f"Cleaning deposit: <strong>${cleanup_deposit:.2f}</strong> (refunded after the unit is confirmed empty)."
    )
    cleanup_fr = (
        f"<hr style='margin:16px 0;border:none;border-top:1px solid #e2e8f0'/>"
        f"⚠️ <strong>IMPORTANT :</strong> Vous devez vider complètement l'unité avant "
        f"<strong>{cleanup_deadline}</strong>. Le non-respect de cette date limite entraîne la "
        f"perte de votre dépôt de nettoyage de <strong>{cleanup_deposit:.2f} $</strong> et la "
        f"suspension de votre compte.<br/>"
        f"Dépôt de nettoyage : <strong>{cleanup_deposit:.2f} $</strong> (remboursé après confirmation que l'unité est vide)."
    )

    return bool(await send_email(
        to_email=buyer["email"],
        subject=f"🎉 You won — Storage Auction Unit #{unit}",
        html_content=_storage_panel(
            "You won the auction",
            "Vous avez gagné l'enchère",
            body_en + pickup_en + cleanup_en,
            body_fr + pickup_fr + cleanup_fr,
            cta_url=f"https://www.bidvex.com/storage-auctions/{auction.get('id','')}",
            cta_en="View auction",
            cta_fr="Voir l'enchère",
        ),
    ))


async def send_storage_auction_sold_email(facility: dict, auction: dict, buyer: dict) -> bool:
    """Bilingual notification to the facility when their unit sells."""
    if not facility or not facility.get("email"):
        return False
    a_id = auction.get("id", "")[:8]
    unit = auction.get("unit_number", "—")
    bid = float(auction.get("winning_bid") or auction.get("current_bid") or 0)
    pm = (auction.get("payment_method") or "stripe").lower()
    pm_label_en = {"stripe": "Stripe (online)", "cash": "Cash", "etransfer": "Interac e-Transfer"}.get(pm, pm)
    pm_label_fr = {"stripe": "Stripe (en ligne)", "cash": "Comptant", "etransfer": "Virement Interac"}.get(pm, pm)

    buyer_name = buyer.get("name") or buyer.get("full_name") or "—"
    buyer_email = buyer.get("email", "—")
    buyer_phone = buyer.get("phone", "—")

    body_en = (
        f"Storage auction for Unit <strong>#{unit}</strong> (#{a_id}) sold for "
        f"<strong>${bid:,.2f}</strong>.<br/><br/>"
        f"<strong>Payment method:</strong> {pm_label_en}<br/>"
        f"<strong>Winning bidder:</strong> {buyer_name} &lt;{buyer_email}&gt;<br/>"
        f"<strong>Phone:</strong> {buyer_phone}<br/><br/>"
        f"Contact the winner to coordinate payment and pickup. "
        f"Your BidVex commission invoice (5% + Stripe + applicable tax) will arrive separately."
    )
    body_fr = (
        f"L'enchère pour l'unité <strong>#{unit}</strong> (#{a_id}) a été vendue pour "
        f"<strong>{bid:,.2f} $</strong>.<br/><br/>"
        f"<strong>Mode de paiement :</strong> {pm_label_fr}<br/>"
        f"<strong>Enchérisseur gagnant :</strong> {buyer_name} &lt;{buyer_email}&gt;<br/>"
        f"<strong>Téléphone :</strong> {buyer_phone}<br/><br/>"
        f"Contactez le gagnant pour organiser le paiement et le ramassage. "
        f"Votre facture de commission BidVex (5 % + Stripe + taxes applicables) suivra séparément."
    )
    return bool(await send_email(
        to_email=facility["email"],
        subject=f"✅ Sold — Storage Auction Unit #{unit}",
        html_content=_storage_panel("Auction sold", "Enchère vendue", body_en, body_fr),
    ))


async def send_storage_ending_soon_email(buyer: dict, auction: dict) -> bool:
    if not buyer or not buyer.get("email"):
        return False
    a_id = auction.get("id", "")[:8]
    body_en = f"Auction <strong>#{a_id}</strong> ends in less than 1 hour. Place your final max bid now."
    body_fr = f"L'enchère <strong>#{a_id}</strong> se termine dans moins d'une heure. Placez votre offre maximale finale maintenant."
    return await send_email(
        to_email=buyer["email"],
        subject=f"⏰ Ending soon — Storage Auction #{a_id}",
        html_content=_storage_panel("Ending soon", "Se termine bientôt", body_en, body_fr,
                                    cta_url=f"https://www.bidvex.com/storage-auctions/{auction.get('id','')}",
                                    cta_en="Bid now", cta_fr="Enchérir"),
    )


async def send_storage_facility_approved_email(facility: dict) -> bool:
    if not facility or not facility.get("email"):
        return False
    body_en = (
        f"Welcome to BidVex Storage Auctions, <strong>{facility.get('company_name','')}</strong>! "
        f"Your facility has been verified. You can now log in and create your first storage unit auction. "
        f"BidVex charges a flat 5% commission on each successful sale — buyers pay no platform fee."
    )
    body_fr = (
        f"Bienvenue chez BidVex Enchères d'entreposage, <strong>{facility.get('company_name','')}</strong>! "
        f"Votre facilité a été vérifiée. Vous pouvez maintenant vous connecter et créer votre première enchère. "
        f"BidVex facture une commission fixe de 5% sur chaque vente réussie — les acheteurs ne paient aucun frais de plateforme."
    )
    return await send_email(
        to_email=facility["email"],
        subject="✅ Your BidVex Storage Facility account is approved",
        html_content=_storage_panel("Facility approved", "Facilité approuvée", body_en, body_fr,
                                    cta_url="https://www.bidvex.com/storage-dashboard",
                                    cta_en="Open dashboard", cta_fr="Ouvrir le tableau de bord"),
    )


async def send_storage_seller_commission_invoice(facility: dict, auction: dict, pricing: dict) -> bool:
    if not facility or not facility.get("email"):
        return False
    s = pricing["seller_invoice"]
    a_id = auction.get("id", "")[:8]
    body_en = (
        f"BidVex commission invoice for storage auction <strong>#{a_id}</strong>:<br/>"
        f"• Commission (5%): <strong>${s['commission']:.2f}</strong><br/>"
        f"• Stripe processing: ${s['stripe_recovery']:.2f}<br/>"
        f"• Tax — {s['tax_label']}: ${s['tax']:.2f}<br/>"
        f"<strong>Total due to BidVex: ${s['total']:.2f}</strong>"
    )
    body_fr = (
        f"Facture de commission BidVex pour l'enchère <strong>#{a_id}</strong> :<br/>"
        f"• Commission (5 %) : <strong>{s['commission']:.2f} $</strong><br/>"
        f"• Frais Stripe : {s['stripe_recovery']:.2f} $<br/>"
        f"• Taxe — {s['tax_label']} : {s['tax']:.2f} $<br/>"
        f"<strong>Total dû à BidVex : {s['total']:.2f} $</strong>"
    )
    return await send_email(
        to_email=facility["email"],
        subject=f"BidVex Commission Invoice — Storage Auction #{a_id}",
        html_content=_storage_panel("Commission invoice", "Facture de commission", body_en, body_fr),
    )


# Internal admin alert helpers (not in the 7 user-facing list, but referenced by routes)

async def send_storage_facility_registration_admin_alert(facility: dict) -> bool:
    admin_email = (
        _os.environ.get("ADMIN_NOTIFICATION_EMAIL")
        or _os.environ.get("ADMIN_EMAIL")
        or "info@bidvex.com"
    )
    body_en = (
        f"New storage facility registration awaiting verification:<br/>"
        f"<strong>{facility.get('company_name','—')}</strong><br/>"
        f"Contact: {facility.get('contact_name','—')} &lt;{facility.get('email','—')}&gt;<br/>"
        f"Phone: {facility.get('phone','—')}<br/>"
        f"Location: {facility.get('city','—')}, {facility.get('province','')}<br/>"
        f"Units available: {facility.get('units_available',0)}"
    )
    body_fr = "Nouvelle facilité d'entreposage en attente de vérification."
    return await send_email(
        to_email=admin_email,
        subject=f"[Storage Facility] New registration — {facility.get('company_name','')}",
        html_content=_storage_panel("New facility registration", "Nouvelle facilité", body_en, body_fr,
                                    cta_url="https://www.bidvex.com/admin", cta_en="Review", cta_fr="Examiner"),
    )


async def send_storage_facility_pending_user_email(facility: dict) -> bool:
    if not facility or not facility.get("email"):
        return False
    body_en = (
        "Thanks for registering your storage facility with BidVex! Your application "
        "is under review by our team. You'll receive a confirmation email within "
        "1–2 business days once your account is verified."
    )
    body_fr = (
        "Merci d'avoir inscrit votre facilité d'entreposage chez BidVex! Votre demande "
        "est en cours d'examen par notre équipe. Vous recevrez un courriel de confirmation "
        "dans 1 à 2 jours ouvrables une fois votre compte vérifié."
    )
    return await send_email(
        to_email=facility["email"],
        subject="Application received — BidVex Storage Auctions",
        html_content=_storage_panel("Application received", "Demande reçue", body_en, body_fr),
    )


# ─────────────────────────────────────────────────────────────
# iter175 — Vehicle deposit auto-captured (bilingual EN+FR per Bill 96)
# ─────────────────────────────────────────────────────────────
async def send_vehicle_deposit_captured_email(
    buyer: dict,
    invoice: dict,
    deposit: dict,
    captured_amount: float,
) -> bool:
    """
    Sent automatically when the auto-capture cron job captures a $500 vehicle
    bidding deposit because the winner's 2.5% platform-fee invoice remained
    unpaid past `payment_deadline + 48h`. EN+FR per Bill 96.
    """
    if not buyer or not buyer.get("email"):
        return False

    inv_no = invoice.get("invoice_number", "—")
    veh_title = invoice.get("vehicle_title", "your vehicle")
    fee_total = invoice.get("total_amount") or invoice.get("platform_fee") or 0
    amt = captured_amount or deposit.get("amount") or 500.0

    body_en = (
        f"Your $500 bidding deposit for <strong>{veh_title}</strong> has been "
        f"captured because invoice <strong>{inv_no}</strong> "
        f"(${fee_total:.2f} CAD platform fee) was not paid within 48 hours of "
        f"the deadline. Amount captured: <strong>${amt:.2f} CAD</strong>. "
        f"This brings your account into good standing — no further action is required. "
        f"If you believe this was in error, contact support@bidvex.com within 14 days."
    )
    body_fr = (
        f"Votre dépôt d'enchère de 500 $ pour <strong>{veh_title}</strong> a été "
        f"saisi parce que la facture <strong>{inv_no}</strong> "
        f"({fee_total:.2f} $ CAD de frais de plateforme) n'a pas été payée dans les "
        f"48 heures suivant l'échéance. Montant saisi : <strong>{amt:.2f} $ CAD</strong>. "
        f"Votre compte est maintenant en règle — aucune autre action requise. "
        f"Si vous croyez qu'il s'agit d'une erreur, contactez support@bidvex.com dans les 14 jours."
    )

    html = _storage_panel(
        "Bidding deposit captured",
        "Dépôt d'enchère saisi",
        body_en,
        body_fr,
        cta_url="https://www.bidvex.com/profile/settings?tab=billing",
        cta_en="View invoices",
        cta_fr="Voir les factures",
    )
    return await send_email(
        to_email=buyer["email"],
        subject=f"[BidVex] Bidding deposit captured · Dépôt saisi — Invoice {inv_no}",
        html_content=html,
    )

