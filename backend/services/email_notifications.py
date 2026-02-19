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
        
        response = sg.send(message)
        
        logger.info(f"Email sent to {to_email}: {subject} (status: {response.status_code})")
        
        return {
            "status": "sent",
            "status_code": response.status_code,
            "to": to_email,
            "subject": subject
        }
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
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
                            <td style="background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); padding: 30px; border-radius: 12px 12px 0 0;">
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

async def send_invoice_created_email(invoice: Dict[str, Any]) -> Dict[str, Any]:
    """Send email when a new invoice is generated"""
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #1e293b;">Invoice Generated</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Congratulations! Your winning bid has been processed. Here are your invoice details:
    </p>
    
    <div style="background-color: #f8fafc; border-radius: 8px; padding: 20px; margin: 20px 0;">
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
    </div>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{FRONTEND_URL}/vehicle-auctions/invoices/{invoice.get('id')}" 
           style="display: inline-block; background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); 
                  color: #ffffff; text-decoration: none; padding: 14px 30px; border-radius: 8px; 
                  font-weight: bold; font-size: 16px;">
            View & Pay Invoice
        </a>
    </div>
    
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
    
    <div style="background-color: #d1fae5; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">
        <p style="margin: 0; color: #065f46; font-size: 14px;">Payment Confirmed</p>
        <p style="margin: 10px 0 0 0; color: #065f46; font-size: 28px; font-weight: bold;">
            {_format_currency(invoice.get('paid_amount', invoice.get('total_amount', 0)))}
        </p>
    </div>
    
    <div style="background-color: #f8fafc; border-radius: 8px; padding: 20px; margin: 20px 0;">
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
    </div>
    
    <p style="color: #475569; line-height: 1.6;">
        The seller has been notified and will coordinate vehicle pickup/delivery with you.
    </p>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{FRONTEND_URL}/vehicle-auctions/invoices/{invoice.get('id')}" 
           style="display: inline-block; background-color: #f1f5f9; color: #1e293b; 
                  text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: 500;">
            View Receipt
        </a>
    </div>
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
    
    <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 20px; margin: 20px 0;">
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
    </div>
    
    <p style="color: #991b1b; font-size: 13px; line-height: 1.6; background-color: #fef2f2; padding: 15px; border-radius: 8px;">
        <strong>Warning:</strong> Continued non-payment may result in account suspension and 
        additional collection actions.
    </p>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{FRONTEND_URL}/vehicle-auctions/invoices/{invoice.get('id')}" 
           style="display: inline-block; background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%); 
                  color: #ffffff; text-decoration: none; padding: 14px 30px; border-radius: 8px; 
                  font-weight: bold; font-size: 16px;">
            Pay Now
        </a>
    </div>
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
    
    <div style="background-color: #d1fae5; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">
        <p style="margin: 0; color: #065f46; font-size: 18px; font-weight: bold;">
            ✓ {doc_name} Verified
        </p>
    </div>
    
    <p style="color: #475569; line-height: 1.6;">
        You can now continue with your seller verification process. Once all required documents 
        are approved, you'll be able to list vehicles for auction.
    </p>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{FRONTEND_URL}/vehicle-auctions/seller/register" 
           style="display: inline-block; background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                  color: #ffffff; text-decoration: none; padding: 14px 30px; border-radius: 8px; 
                  font-weight: bold; font-size: 16px;">
            View Verification Status
        </a>
    </div>
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
    
    <div style="background-color: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 20px; margin: 20px 0;">
        <p style="margin: 0 0 10px 0; color: #92400e; font-weight: bold;">Reason:</p>
        <p style="margin: 0; color: #92400e;">{rejection_reason}</p>
    </div>
    
    <p style="color: #475569; line-height: 1.6;">
        Please upload a new document that addresses the issue above. Make sure your document:
    </p>
    
    <ul style="color: #475569; line-height: 1.8;">
        <li>Is clearly legible and not blurry</li>
        <li>Shows all required information</li>
        <li>Is current and not expired</li>
        <li>Is in PDF, JPG, or PNG format</li>
    </ul>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{FRONTEND_URL}/vehicle-auctions/seller/register" 
           style="display: inline-block; background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); 
                  color: #ffffff; text-decoration: none; padding: 14px 30px; border-radius: 8px; 
                  font-weight: bold; font-size: 16px;">
            Re-upload Document
        </a>
    </div>
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
    
    <div style="background-color: #d1fae5; border-radius: 8px; padding: 30px; margin: 20px 0; text-align: center;">
        <p style="margin: 0; color: #065f46; font-size: 14px;">Account Status</p>
        <p style="margin: 10px 0 0 0; color: #065f46; font-size: 24px; font-weight: bold;">
            ✓ APPROVED
        </p>
    </div>
    
    <p style="color: #475569; line-height: 1.6;">
        You can now:
    </p>
    
    <ul style="color: #475569; line-height: 1.8;">
        <li>List vehicles for auction</li>
        <li>Set your own starting prices and reserves</li>
        <li>Track bids in real-time</li>
        <li>Receive payments directly to your account</li>
    </ul>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{FRONTEND_URL}/vehicle-auctions/create" 
           style="display: inline-block; background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                  color: #ffffff; text-decoration: none; padding: 14px 30px; border-radius: 8px; 
                  font-weight: bold; font-size: 16px;">
            List Your First Vehicle
        </a>
    </div>
    """
    
    return await send_email(
        to_email=user_email,
        subject="🎉 Your Seller Account is Approved!",
        html_content=_base_template(content, "Seller Account Approved")
    )


# ===== AUCTION EMAILS =====

async def send_auction_won_email(
    buyer_email: str,
    buyer_name: str,
    vehicle_title: str,
    final_price: float,
    invoice_id: str
) -> Dict[str, Any]:
    """Send email when a buyer wins an auction"""
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #2563eb;">🎉 You Won!</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Congratulations {buyer_name}!
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        You are the winning bidder for:
    </p>
    
    <div style="background-color: #eff6ff; border: 2px solid #2563eb; border-radius: 8px; padding: 25px; margin: 20px 0; text-align: center;">
        <p style="margin: 0; color: #1e40af; font-size: 20px; font-weight: bold;">
            {vehicle_title}
        </p>
        <p style="margin: 15px 0 0 0; color: #1e293b; font-size: 14px;">Winning Bid</p>
        <p style="margin: 5px 0 0 0; color: #2563eb; font-size: 32px; font-weight: bold;">
            {_format_currency(final_price)}
        </p>
    </div>
    
    <p style="color: #475569; line-height: 1.6;">
        An invoice has been generated with the full breakdown of fees and taxes. 
        Please complete payment within 14 days.
    </p>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{FRONTEND_URL}/vehicle-auctions/invoices/{invoice_id}" 
           style="display: inline-block; background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); 
                  color: #ffffff; text-decoration: none; padding: 14px 30px; border-radius: 8px; 
                  font-weight: bold; font-size: 16px;">
            View Invoice & Pay
        </a>
    </div>
    """
    
    return await send_email(
        to_email=buyer_email,
        subject=f"🎉 Congratulations! You Won: {vehicle_title}",
        html_content=_base_template(content, "Auction Won")
    )


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
    
    <div style="background-color: #d1fae5; border-radius: 8px; padding: 25px; margin: 20px 0; text-align: center;">
        <p style="margin: 0; color: #065f46; font-size: 18px; font-weight: bold;">
            {vehicle_title}
        </p>
    </div>
    
    <div style="background-color: #f8fafc; border-radius: 8px; padding: 20px; margin: 20px 0;">
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
    </div>
    
    <p style="color: #475569; line-height: 1.6;">
        Your payout will be processed once the buyer completes payment (typically within 14 days).
    </p>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{FRONTEND_URL}/vehicle-auctions/seller/financials" 
           style="display: inline-block; background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                  color: #ffffff; text-decoration: none; padding: 14px 30px; border-radius: 8px; 
                  font-weight: bold; font-size: 16px;">
            View Financials
        </a>
    </div>
    """
    
    return await send_email(
        to_email=seller_email,
        subject=f"🎉 Sold! {vehicle_title} - {_format_currency(final_price)}",
        html_content=_base_template(content, "Vehicle Sold")
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
    
    <div style="background-color: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 20px; margin: 20px 0;">
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
    </div>
    
    <p style="color: #475569; line-height: 1.6;">
        To continue enjoying {plan_name} benefits (reduced fees, priority support, and more), 
        please contact support to renew your subscription.
    </p>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{FRONTEND_URL}/settings/subscription" 
           style="display: inline-block; background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); 
                  color: #ffffff; text-decoration: none; padding: 14px 30px; border-radius: 8px; 
                  font-weight: bold; font-size: 16px;">
            View Subscription
        </a>
    </div>
    
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
    
    <div style="background-color: #f1f5f9; border-radius: 8px; padding: 20px; margin: 20px 0;">
        <h4 style="margin: 0 0 15px 0; color: #334155;">What's Changed:</h4>
        <ul style="margin: 0; padding: 0 0 0 20px; color: #475569; line-height: 1.8;">
            <li>Monthly listing limit reduced</li>
            <li>Buyer premium discounts removed</li>
            <li>Seller commission discounts removed</li>
            <li>Priority support no longer available</li>
        </ul>
    </div>
    
    <p style="color: #475569; line-height: 1.6;">
        Don't worry! Your existing listings will remain active. To regain your {plan_name} benefits, 
        please contact support to renew your subscription.
    </p>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{FRONTEND_URL}/settings/subscription" 
           style="display: inline-block; background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%); 
                  color: #ffffff; text-decoration: none; padding: 14px 30px; border-radius: 8px; 
                  font-weight: bold; font-size: 16px;">
            Renew Subscription
        </a>
    </div>
    
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
    
    <div style="background-color: #d1fae5; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">
        <p style="margin: 0; color: #065f46; font-size: 24px; font-weight: bold;">
            {plan_name}
        </p>
        <p style="margin: 10px 0 0 0; color: #10b981; font-size: 14px;">
            Active until {end_date}
        </p>
    </div>
    
    <h4 style="margin: 25px 0 15px 0; color: #334155;">Your {plan_name} Benefits:</h4>
    <ul style="margin: 0; padding: 0 0 0 20px; color: #475569; line-height: 1.8;">
        {"<li>Reduced buyer premium fees</li>" if new_plan in ['premium', 'vip'] else ""}
        {"<li>Lower seller commission rates</li>" if new_plan in ['premium', 'vip'] else ""}
        {"<li>Priority customer support</li>" if new_plan in ['premium', 'vip'] else ""}
        {"<li>Advanced analytics dashboard</li>" if new_plan == 'vip' else ""}
        {"<li>Dedicated account manager</li>" if new_plan == 'vip' else ""}
    </ul>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{FRONTEND_URL}/marketplace" 
           style="display: inline-block; background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                  color: #ffffff; text-decoration: none; padding: 14px 30px; border-radius: 8px; 
                  font-weight: bold; font-size: 16px;">
            Start Exploring
        </a>
    </div>
    """
    
    return await send_email(
        to_email=user_email,
        subject=f"🎉 Welcome to {plan_name}!",
        html_content=_base_template(content, "Subscription Updated")
    )

