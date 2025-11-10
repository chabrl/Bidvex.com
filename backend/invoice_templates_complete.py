"""
Complete Bilingual Invoice Templates for BidVex
Supports English (en) and French (fr)
Supports CAD and USD currencies with appropriate tax logic
"""

from datetime import datetime
from typing import Dict, Any
from logo_data import BIDVEX_LOGO_BASE64
from invoice_translations import get_translation as t

def payment_letter_template(data: Dict[str, Any], lang: str = "en") -> str:
    """
    Generate HTML for Payment Letter PDF
    Bilingual support: English (en) / French (fr)
    Currency support: CAD / USD
    """
    
    currency = data.get('currency', 'CAD')
    hammer_total = data['hammer_total']
    premium_amount = data['premium_amount']
    total_tax = data['total_tax']
    grand_total = data['grand_total']
    payment_deadline = data.get('payment_deadline', 'Within 3 business days')
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: letter;
                margin: 0.75in;
            }}
            body {{
                font-family: 'Arial', 'Helvetica', sans-serif;
                font-size: 11pt;
                line-height: 1.6;
                color: #333;
            }}
            .header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 30px;
                border-bottom: 3px solid #009BFF;
                padding-bottom: 20px;
            }}
            .header-logo {{
                width: 150px;
                height: auto;
            }}
            .header-text {{
                flex: 1;
                text-align: center;
            }}
            .header h1 {{
                color: #009BFF;
                margin: 0;
                font-size: 28pt;
                font-weight: bold;
            }}
            .header p {{
                margin: 5px 0;
                font-size: 10pt;
                color: #666;
            }}
            .letter-date {{
                text-align: right;
                margin: 20px 0;
                font-size: 10pt;
            }}
            .recipient {{
                margin: 20px 0;
            }}
            .recipient p {{
                margin: 3px 0;
                font-size: 10pt;
            }}
            .subject {{
                font-weight: bold;
                margin: 30px 0 20px 0;
                font-size: 12pt;
            }}
            .letter-body {{
                line-height: 1.8;
            }}
            .letter-body p {{
                margin: 15px 0;
            }}
            .highlight-box {{
                background: #e7f3ff;
                padding: 20px;
                border-left: 4px solid #009BFF;
                border-radius: 3px;
                margin: 20px 0;
            }}
            .highlight-box h3 {{
                color: #009BFF;
                font-weight: bold;
                margin: 10px 0;
            }}
            .amount-due {{
                font-size: 24pt;
                color: #009BFF;
                font-weight: bold;
                margin: 10px 0;
            }}
            .important {{
                background: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 20px 0;
            }}
            .payment-methods {{
                margin: 20px 0;
            }}
            .payment-methods ul {{
                list-style: none;
                padding-left: 0;
            }}
            .payment-methods li {{
                padding: 8px 0;
                border-bottom: 1px solid #e0e0e0;
            }}
            .payment-methods li:before {{
                content: "✓ ";
                color: #009BFF;
                font-weight: bold;
                margin-right: 10px;
            }}
            .closing {{
                margin-top: 40px;
            }}
            .signature {{
                margin-top: 50px;
            }}
            .signature p {{
                margin: 5px 0;
            }}
            .contact-box {{
                background: #f9f9f9;
                padding: 15px;
                border-radius: 5px;
                margin-top: 30px;
                text-align: center;
            }}
            .contact-box h4 {{
                color: #009BFF;
                margin: 0 0 10px 0;
            }}
            .footer {{
                margin-top: 40px;
                text-align: center;
                font-size: 9pt;
                color: #666;
                border-top: 1px solid #e0e0e0;
                padding-top: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <img src="{BIDVEX_LOGO_BASE64}" alt="BidVex Logo" class="header-logo" />
            <div class="header-text">
                <h1>BidVex</h1>
                <p>{t('online_auction_platform', lang)}</p>
                <p>www.bidvex.com | support@bidvex.com</p>
            </div>
        </div>

        <div class="letter-date">
            {datetime.now().strftime('%B %d, %Y')}
        </div>

        <div class="recipient">
            <p><strong>{data['buyer']['name']}</strong></p>
            {f"<p>{data['buyer']['company_name']}</p>" if data['buyer'].get('company_name') else ""}
            <p>{data['buyer'].get('billing_address', data['buyer'].get('address', ''))}</p>
            <p>{t('paddle_number', lang)}: <strong>{data['paddle_number']}</strong></p>
        </div>

        <div class="subject">
            {t('re_payment_due', lang, data['auction']['title'])}
        </div>

        <div class="letter-body">
            <p>{t('dear', lang, data['buyer']['name'].split()[0])}</p>

            <p>
                {t('congratulations_intro', lang, data['lots_count'], data['auction']['title'], data['auction']['auction_end_date'].strftime('%B %d, %Y'))}
            </p>

            <div class="highlight-box">
                <h3>{t('payment_information', lang)}</h3>
                <p style="margin: 5px 0;">{t('invoice_number', lang)}: <strong>{data['invoice_number']}</strong></p>
                <p style="margin: 5px 0;">{t('your_paddle_number', lang)}: <strong>{data['paddle_number']}</strong></p>
                <p class="amount-due">${grand_total:.2f} {currency}</p>
                <p style="font-size: 10pt; color: #666; margin: 0;">
                    {t('includes_details', lang, data.get('premium_percentage', 5.0))}
                </p>
            </div>
            
            <div class="important">
                <strong>{t('important_two_part_payment', lang)}</strong>
                <p style="margin: 10px 0 5px 0;">{t('payment_split_intro', lang)}</p>
                <ol style="margin: 5px 0; padding-left: 20px;">
                    <li style="margin: 5px 0;">{t('payment_seller_detail', lang, f'${hammer_total:.2f} {currency}')}</li>
                    <li style="margin: 5px 0;">{t('payment_bidvex_detail', lang, f'${premium_amount + total_tax:.2f} {currency}')}</li>
                </ol>
            </div>

            <p>
                {t('complete_purchase_intro', lang, f'${premium_amount + total_tax:.2f} {currency}', payment_deadline)}
            </p>

            <div class="payment-methods">
                <h4 style="color: #009BFF; margin-bottom: 10px;">{t('payment_methods_bidvex', lang)}</h4>
                <ul>
                    <li><strong>{t('credit_card', lang)}</strong></li>
                    <li><strong>{t('etransfer_reference', lang, data['invoice_number'])}</strong></li>
                </ul>
                <p style="font-size: 9pt; color: #666; margin-top: 10px;">
                    {t('seller_contact_note', lang)}
                </p>
            </div>

            <p>
                {t('payment_confirmation_note', lang)}
            </p>

            <div class="closing">
                <p>{t('closing_thank_you', lang)}</p>
                
                <div class="signature">
                    <p><strong>{t('sincerely', lang)}</strong></p>
                    <p>{t('bidvex_team', lang)}</p>
                    <p style="color: #009BFF; font-style: italic;">{t('online_auction_platform', lang)}</p>
                </div>
            </div>
        </div>

        <div class="contact-box">
            <h4>{t('need_assistance', lang)}</h4>
            <p style="margin: 5px 0;">{t('email', lang)}: <strong>support@bidvex.com</strong></p>
            <p style="margin: 5px 0;">{t('phone', lang)}: <strong>{data['buyer']['phone']}</strong></p>
            <p style="margin: 5px 0; font-size: 9pt; color: #666;">
                {t('business_hours', lang)}
            </p>
        </div>

        <div class="footer">
            <p>{t('automated_notification', lang)}</p>
            <p>BidVex © {datetime.now().year} | {t('all_rights_reserved', lang)}</p>
        </div>
    </body>
    </html>
    """
    
    return html
