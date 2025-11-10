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


def seller_statement_template(data: Dict[str, Any], lang: str = "en") -> str:
    """
    Generate HTML for Seller Statement PDF
    Bilingual support: English (en) / French (fr)
    Currency support: CAD / USD
    """
    
    currency = data.get('currency', 'CAD')
    
    # Calculate totals
    sold_lots = [lot for lot in data['lots'] if lot.get('status') == 'sold']
    unsold_lots = [lot for lot in data['lots'] if lot.get('status') == 'unsold']
    total_hammer = sum(lot.get('hammer_price', 0) for lot in sold_lots)
    
    # Generate lot rows
    lot_rows = ""
    for lot in data['lots']:
        status_class = "sold" if lot.get('status') == 'sold' else "unsold"
        status_text = t('sold', lang) if lot.get('status') == 'sold' else t('unsold', lang)
        
        hammer_price = f"${lot.get('hammer_price', 0):.2f} {currency}" if lot.get('status') == 'sold' else "-"
        buyer_info = f"{lot.get('buyer_name', '-')} (#{lot.get('paddle_number', '-')})" if lot.get('status') == 'sold' else "-"
        
        lot_rows += f"""
        <tr class="{status_class}">
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0;">{lot['lot_number']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0;">
                <strong>{lot['title']}</strong><br>
                <span style="font-size: 9pt; color: #666;">{lot['description'][:80]}...</span>
            </td>
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0; text-align: center;">
                <span class="status-badge {status_class}">{status_text}</span>
            </td>
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0; text-align: center;">{buyer_info}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0; text-align: right;">{hammer_price}</td>
        </tr>
        """
    
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
                line-height: 1.4;
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
            .document-title {{
                text-align: center;
                margin: 20px 0;
            }}
            .document-title h2 {{
                color: #333;
                font-size: 20pt;
                margin: 0;
            }}
            .info-section {{
                display: flex;
                justify-content: space-between;
                margin: 30px 0;
            }}
            .info-box {{
                width: 48%;
                background: #f9f9f9;
                padding: 15px;
                border-radius: 5px;
            }}
            .info-box h3 {{
                margin: 0 0 10px 0;
                font-size: 11pt;
                color: #009BFF;
            }}
            .info-box p {{
                margin: 3px 0;
                font-size: 10pt;
            }}
            .summary-box {{
                background: #e7f3ff;
                padding: 20px;
                border-left: 4px solid #009BFF;
                border-radius: 3px;
                margin: 20px 0;
            }}
            .summary-box h3 {{
                color: #009BFF;
                margin: 0 0 15px 0;
            }}
            .summary-row {{
                display: flex;
                justify-content: space-between;
                padding: 5px 0;
                border-bottom: 1px solid #d0e7ff;
            }}
            .summary-row.total {{
                font-weight: bold;
                font-size: 14pt;
                color: #009BFF;
                border-top: 2px solid #009BFF;
                padding-top: 10px;
                margin-top: 10px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th {{
                background: #009BFF;
                color: white;
                padding: 12px;
                text-align: left;
                font-weight: bold;
                font-size: 10pt;
            }}
            td {{
                padding: 10px;
                border-bottom: 1px solid #e0e0e0;
                font-size: 10pt;
            }}
            .status-badge {{
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 9pt;
                font-weight: bold;
            }}
            .status-badge.sold {{
                background: #d4edda;
                color: #155724;
            }}
            .status-badge.unsold {{
                background: #f8d7da;
                color: #721c24;
            }}
            tr.sold {{
                background: #f8fff8;
            }}
            tr.unsold {{
                background: #fff8f8;
            }}
            .note-box {{
                background: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 20px 0;
                font-size: 9pt;
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

        <div class="document-title">
            <h2>{t('seller_statement', lang)}</h2>
            <p style="color: #666; font-size: 10pt; margin: 5px 0;">{t('statement_number', lang)}: {data.get('statement_number', 'N/A')}</p>
            <p style="color: #666; font-size: 10pt; margin: 5px 0;">{t('date', lang)}: {datetime.now().strftime('%B %d, %Y')}</p>
        </div>

        <div class="info-section">
            <div class="info-box">
                <h3>{t('seller_information', lang)}</h3>
                <p><strong>{data['seller']['name']}</strong></p>
                {f"<p>{data['seller']['company_name']}</p>" if data['seller'].get('company_name') else ""}
                <p>{data['seller'].get('address', 'N/A')}</p>
                <p>{t('email', lang)}: {data['seller']['email']}</p>
                <p>{t('phone', lang)}: {data['seller']['phone']}</p>
            </div>
            <div class="info-box">
                <h3>{t('auction_summary', lang)}</h3>
                <p><strong>{data['auction']['title']}</strong></p>
                <p>{t('location', lang)}: {data['auction']['city']}, {data['auction']['region']}</p>
                <p>{t('auction_end_date', lang)}: {data['auction']['auction_end_date'].strftime('%B %d, %Y')}</p>
            </div>
        </div>

        <div class="summary-box">
            <h3>{t('auction_summary', lang)}</h3>
            <div class="summary-row">
                <span>{t('lots_submitted', lang)}:</span>
                <span>{len(data['lots'])}</span>
            </div>
            <div class="summary-row">
                <span>{t('lots_sold', lang)}:</span>
                <span style="color: #28a745; font-weight: bold;">{len(sold_lots)}</span>
            </div>
            <div class="summary-row">
                <span>{t('lots_unsold', lang)}:</span>
                <span style="color: #dc3545; font-weight: bold;">{len(unsold_lots)}</span>
            </div>
            <div class="summary-row total">
                <span>{t('total_hammer_value', lang)}:</span>
                <span>${total_hammer:.2f} {currency}</span>
            </div>
        </div>

        <h3 style="color: #009BFF; margin: 30px 0 10px 0;">{t('lot_details', lang)}</h3>
        <table>
            <thead>
                <tr>
                    <th style="width: 8%;">{t('lot', lang)} #</th>
                    <th style="width: 40%;">{t('description', lang)}</th>
                    <th style="width: 12%; text-align: center;">{t('status', lang)}</th>
                    <th style="width: 20%; text-align: center;">{t('buyer', lang)}</th>
                    <th style="width: 20%; text-align: right;">{t('hammer_price', lang)}</th>
                </tr>
            </thead>
            <tbody>
                {lot_rows}
            </tbody>
        </table>

        <div class="note-box">
            <strong>{t('commission_note', lang)}</strong>
        </div>

        <div class="footer">
            <p>{t('statement_footer', lang)}</p>
            <p>BidVex © {datetime.now().year} | {t('all_rights_reserved', lang)}</p>
        </div>
    </body>
    </html>
    """
    
    return html


def seller_receipt_template(data: Dict[str, Any], lang: str = "en") -> str:
    """
    Generate HTML for Seller Receipt PDF
    Shows net payout calculation (zero commission policy)
    Bilingual support: English (en) / French (fr)
    Currency support: CAD / USD
    """
    
    currency = data.get('currency', 'CAD')
    total_hammer = data['total_hammer']
    commission_rate = data.get('commission_rate', 0.0)
    commission_amount = total_hammer * (commission_rate / 100)
    
    # Tax on commission (GST/QST) - will be 0 if commission is 0
    tax_rate_gst = data.get('tax_rate_gst', 0.0) if currency == 'CAD' else 0.0
    tax_rate_qst = data.get('tax_rate_qst', 0.0) if currency == 'CAD' else 0.0
    
    gst_on_commission = commission_amount * (tax_rate_gst / 100)
    qst_on_commission = commission_amount * (tax_rate_qst / 100)
    total_tax = gst_on_commission + qst_on_commission
    
    total_deductions = commission_amount + total_tax
    net_payout = total_hammer - total_deductions
    
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
                line-height: 1.4;
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
            .document-title {{
                text-align: center;
                margin: 20px 0;
            }}
            .document-title h2 {{
                color: #333;
                font-size: 20pt;
                margin: 0;
            }}
            .info-box {{
                background: #f9f9f9;
                padding: 20px;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .info-box h3 {{
                margin: 0 0 15px 0;
                font-size: 12pt;
                color: #009BFF;
            }}
            .info-box p {{
                margin: 5px 0;
                font-size: 10pt;
            }}
            .calculation-section {{
                margin: 30px 0;
                padding: 25px;
                background: #f9f9f9;
                border-radius: 5px;
            }}
            .calc-row {{
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid #e0e0e0;
                font-size: 11pt;
            }}
            .calc-row.subtotal {{
                font-weight: bold;
                margin-top: 10px;
                padding-top: 15px;
                border-top: 2px solid #333;
            }}
            .calc-row.total {{
                background: #009BFF;
                color: white;
                font-weight: bold;
                font-size: 16pt;
                padding: 15px;
                margin-top: 15px;
                border-radius: 3px;
            }}
            .payment-info {{
                margin: 30px 0;
                padding: 20px;
                background: #e7f3ff;
                border-left: 4px solid #009BFF;
                border-radius: 3px;
            }}
            .payment-info h3 {{
                color: #009BFF;
                margin: 0 0 15px 0;
            }}
            .zero-commission-notice {{
                background: #e7f3ff;
                padding: 15px;
                margin: 20px 0;
                border-left: 4px solid #009BFF;
                border-radius: 3px;
            }}
            .zero-commission-notice p {{
                margin: 0;
                color: #0066cc;
                font-weight: bold;
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

        <div class="document-title">
            <h2>{t('seller_receipt', lang)}</h2>
            <p style="color: #666; font-size: 10pt; margin: 5px 0;">{t('receipt_number', lang)}: {data['receipt_number']}</p>
            <p style="color: #666; font-size: 10pt; margin: 5px 0;">{t('date', lang)}: {datetime.now().strftime('%B %d, %Y')}</p>
        </div>

        <div class="info-box">
            <h3>{t('seller_information', lang)}</h3>
            <p><strong>{data['seller']['name']}</strong></p>
            {f"<p>{data['seller']['company_name']}</p>" if data['seller'].get('company_name') else ""}
            <p>{data['seller'].get('address', 'N/A')}</p>
            <p>{t('email', lang)}: {data['seller']['email']}</p>
        </div>

        <div class="info-box">
            <h3>{t('auction_details', lang)}</h3>
            <p><strong>{data['auction']['title']}</strong></p>
            <p>{t('auction_end_date', lang)}: {data['auction']['auction_end_date'].strftime('%B %d, %Y')}</p>
            <p>{t('lots_sold_of_submitted', lang, data['lots_sold'], data['total_lots'])}</p>
        </div>

        <div class="calculation-section">
            <h3 style="color: #009BFF; margin: 0 0 20px 0;">{t('payout_calculation', lang)}</h3>
            
            <div class="calc-row">
                <span>{t('total_hammer_value_all_lots', lang)}:</span>
                <span><strong>${total_hammer:.2f} {currency}</strong></span>
            </div>
            
            <div class="calc-row">
                <span>{t('commission', lang, commission_rate)}:</span>
                <span>-${commission_amount:.2f} {currency}</span>
            </div>
            
            <div class="calc-row">
                <span>{t('gst_on_commission', lang, tax_rate_gst)}:</span>
                <span>-${gst_on_commission:.2f} {currency}</span>
            </div>
            
            <div class="calc-row">
                <span>{t('qst_on_commission', lang, tax_rate_qst)}:</span>
                <span>-${qst_on_commission:.2f} {currency}</span>
            </div>
            
            <div class="calc-row subtotal">
                <span>{t('total_deductions', lang)}:</span>
                <span>-${total_deductions:.2f} {currency}</span>
            </div>
            
            <div class="calc-row total">
                <span>{t('net_payout_to_seller', lang)}:</span>
                <span>${net_payout:.2f} {currency}</span>
            </div>
        </div>
        
        {f'<div class="zero-commission-notice"><p>{t("no_commission_notice", lang)}</p></div>' if commission_rate == 0.0 else ''}

        <div class="payment-info">
            <h3>{t('payment_information_seller', lang)}</h3>
            <p><strong>{t('payment_method', lang)}:</strong> {data.get('payment_method', 'Bank Transfer')}</p>
            <p><strong>{t('payment_date', lang)}:</strong> {data.get('payment_date', 'Within 5-7 business days')}</p>
            <p style="margin-top: 15px; font-size: 9pt; color: #666;">
                {t('payment_note', lang)}
            </p>
        </div>

        <div class="footer">
            <p>{t('thank_you', lang)}</p>
            <p>BidVex © {datetime.now().year} | {t('all_rights_reserved', lang)}</p>
        </div>
    </body>
    </html>
    """
    
    return html


def commission_invoice_template(data: Dict[str, Any], lang: str = "en") -> str:
    """
    Generate HTML for Commission Invoice PDF
    Invoice FROM BidVex TO Seller for commission on sold lots
    Bilingual support: English (en) / French (fr)
    Currency support: CAD / USD
    """
    
    currency = data.get('currency', 'CAD')
    commission_amount = data['commission_amount']
    
    # Tax rates based on currency
    tax_rate_gst = data.get('tax_rate_gst', 0.0) if currency == 'CAD' else 0.0
    tax_rate_qst = data.get('tax_rate_qst', 0.0) if currency == 'CAD' else 0.0
    
    gst_on_commission = commission_amount * (tax_rate_gst / 100)
    qst_on_commission = commission_amount * (tax_rate_qst / 100)
    total_due = commission_amount + gst_on_commission + qst_on_commission
    
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
                line-height: 1.4;
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
            .invoice-header {{
                display: flex;
                justify-content: space-between;
                margin: 30px 0;
            }}
            .invoice-title {{
                font-size: 24pt;
                color: #009BFF;
                font-weight: bold;
            }}
            .invoice-details {{
                text-align: right;
                font-size: 10pt;
            }}
            .invoice-details p {{
                margin: 3px 0;
            }}
            .parties {{
                display: flex;
                justify-content: space-between;
                margin: 30px 0;
            }}
            .party-box {{
                width: 48%;
                padding: 15px;
                background: #f9f9f9;
                border-radius: 5px;
            }}
            .party-box h3 {{
                margin: 0 0 10px 0;
                font-size: 11pt;
                color: #009BFF;
            }}
            .party-box p {{
                margin: 3px 0;
                font-size: 10pt;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 30px 0;
            }}
            th {{
                background: #009BFF;
                color: white;
                padding: 12px;
                text-align: left;
                font-weight: bold;
            }}
            td {{
                padding: 12px;
                border-bottom: 1px solid #e0e0e0;
            }}
            .totals {{
                float: right;
                width: 50%;
                margin-top: 20px;
            }}
            .total-row {{
                display: flex;
                justify-content: space-between;
                padding: 8px 15px;
                border-bottom: 1px solid #e0e0e0;
            }}
            .total-row.grand {{
                background: #009BFF;
                color: white;
                font-weight: bold;
                font-size: 14pt;
                margin-top: 10px;
                border-radius: 3px;
            }}
            .payment-terms {{
                clear: both;
                margin-top: 40px;
                padding: 20px;
                background: #fff3cd;
                border-left: 4px solid #ffc107;
                border-radius: 3px;
            }}
            .payment-terms h3 {{
                color: #856404;
                margin: 0 0 10px 0;
            }}
            .payment-terms.zero-commission {{
                background: #e7f3ff;
                border-left: 4px solid #009BFF;
            }}
            .payment-terms.zero-commission h3 {{
                color: #0066cc;
            }}
            .footer {{
                margin-top: 60px;
                text-align: center;
                font-size: 9pt;
                color: #666;
                border-top: 2px solid #009BFF;
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

        <div class="invoice-header">
            <div class="invoice-title">{t('commission_invoice', lang)}</div>
            <div class="invoice-details">
                <p><strong>{t('invoice_number', lang)}:</strong> {data['invoice_number']}</p>
                <p><strong>{t('date', lang)}:</strong> {datetime.now().strftime('%B %d, %Y')}</p>
                <p><strong>{t('due_date', lang)}:</strong> {data.get('due_date', 'Upon Receipt')}</p>
            </div>
        </div>

        <div class="parties">
            <div class="party-box">
                <h3>{t('from_service_provider', lang)}</h3>
                <p><strong>BidVex Inc.</strong></p>
                <p>123 Auction Street</p>
                <p>Montreal, QC H1A 1A1</p>
                <p>Canada</p>
                <p>{t('email', lang)}: billing@bidvex.com</p>
                <p>{t('phone', lang)}: 1-800-BIDVEX</p>
            </div>
            <div class="party-box">
                <h3>{t('to_consignor', lang)}</h3>
                <p><strong>{data['seller']['name']}</strong></p>
                {f"<p>{data['seller']['company_name']}</p>" if data['seller'].get('company_name') else ""}
                <p>{data['seller'].get('address', 'N/A')}</p>
                <p>{t('email', lang)}: {data['seller']['email']}</p>
                <p>{t('phone', lang)}: {data['seller']['phone']}</p>
            </div>
        </div>

        <h3 style="color: #009BFF; margin: 30px 0 10px 0;">{t('auction_services_provided', lang)}</h3>
        <table>
            <thead>
                <tr>
                    <th style="width: 60%;">{t('description', lang)}</th>
                    <th style="width: 20%; text-align: right;">{t('rate', lang)}</th>
                    <th style="width: 20%; text-align: right;">{t('amount', lang)}</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>
                        <strong>{t('auction_commission_services', lang)}</strong><br>
                        <span style="font-size: 10pt; color: #666;">
                            {t('auction', lang)}: {data['auction']['title']}<br>
                            {t('date', lang)}: {data['auction']['auction_end_date'].strftime('%B %d, %Y')}<br>
                            {t('total_hammer_value', lang)}: ${data['total_hammer']:.2f} {currency}<br>
                            {t('lots_sold', lang)}: {data['lots_sold']}
                        </span>
                    </td>
                    <td style="text-align: right; vertical-align: top;">{data['commission_rate']}%</td>
                    <td style="text-align: right; vertical-align: top;"><strong>${commission_amount:.2f} {currency}</strong></td>
                </tr>
            </tbody>
        </table>

        <div class="totals">
            <div class="total-row">
                <span>{t('subtotal_commission', lang)}:</span>
                <span>${commission_amount:.2f} {currency}</span>
            </div>
            <div class="total-row">
                <span>{t('gst', lang, tax_rate_gst)}:</span>
                <span>${gst_on_commission:.2f} {currency}</span>
            </div>
            <div class="total-row">
                <span>{t('qst', lang, tax_rate_qst)}:</span>
                <span>${qst_on_commission:.2f} {currency}</span>
            </div>
            <div class="total-row grand">
                <span>{t('total_due', lang)}:</span>
                <span>${total_due:.2f} {currency}</span>
            </div>
        </div>

        <div class="payment-terms {'zero-commission' if commission_amount == 0 else ''}">
            <h3>{t('commission_notice_header', lang) if commission_amount == 0 else t('payment_terms_header', lang)}</h3>
            {f'''
            <p style="margin: 5px 0; font-size: 11pt; color: #0066cc; font-weight: bold;">
                {t('no_commission_charged', lang)}
            </p>
            <p style="margin: 5px 0; font-size: 10pt;">
                {t('full_hammer_payout', lang, f'${data["total_hammer"]:.2f} {currency}')}
            </p>
            <p style="margin: 15px 0 0 0; font-size: 9pt; color: #666;">
                {t('zero_commission_explanation', lang)}
            </p>
            ''' if commission_amount == 0 else f'''
            <p style="margin: 5px 0; font-size: 10pt;">
                <strong>{t('commission_deducted_note', lang)}</strong>
            </p>
            <p style="margin: 5px 0; font-size: 10pt;">
                {t('net_payout_after_commission', lang, f'${data["net_payout"]:.2f} {currency}')}
            </p>
            <p style="margin: 15px 0 0 0; font-size: 9pt; color: #856404;">
                {t('commission_explanation', lang)}
            </p>
            '''}
        </div>

        <div class="footer">
            <p><strong>BidVex Inc.</strong> | {t('online_auction_platform', lang)}</p>
            <p>{t('gst_registration', lang)}: 123456789RT0001 | {t('qst_registration', lang)}: 1234567890TQ0001</p>
            <p style="margin-top: 10px;">{t('thank_you', lang)}</p>
            <p>BidVex © {datetime.now().year} | {t('all_rights_reserved', lang)}</p>
        </div>
    </body>
    </html>
    """
    
    return html

